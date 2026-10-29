#!/usr/bin/env python3
"""Hash-bound Linux offline DRAFT montage, never an approval or publication path.

Usage: draft_render.py MANIFEST --output draft.mp4 [--work CACHE]
Manifest segments require source, sha256, kind, seconds; crop/start/speed optional.
Images require explicit reuse_existing_stills=true (manifest or image reuse=true).
Audio: audio_copy={source,sha256}, or narrator with optional narrator_sha256.
Optional ass/subtitles; only local files. Native source audio is never mixed in.
No network, provider, scheduler, quality score, or reviewer identity is created.
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

MAX_BYTES = 512 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
# Linux UAPI constants (linux/fcntl.h); some Python builds do not expose them.
ADD_SEALS, GET_SEALS, ALL_SEALS = 1033, 1034, 0x000f


class RenderError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def read_fd(fd):
    chunks, offset = [], 0
    while True:
        b = os.pread(fd, 1024 * 1024, offset)
        if not b:
            return b''.join(chunks)
        chunks.append(b)
        offset += len(b)
        if offset > MAX_BYTES:
            raise RenderError('RESOURCE_FILE_SIZE')


@dataclass(frozen=True)
class Snapshot:
    fd: int
    sha256: str
    size: int

    @property
    def path(self):
        return f'/proc/self/fd/{self.fd}'


class Snapshots:
    """Every consumer gets sealed bytes, never a mutable pathname already checked."""
    def __init__(self):
        self.fds, self.memo, self.total = [], {}, 0

    def __enter__(self):
        if not hasattr(os, 'memfd_create') or not Path('/proc/self/fd').is_dir():
            raise RenderError('LINUX_SEALED_MEMFD_REQUIRED')
        return self

    def __exit__(self, *args):
        for fd in reversed(self.fds):
            os.close(fd)

    def writable(self):
        fd = os.memfd_create('draft-media', os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC)
        self.fds.append(fd)
        return fd

    def sealed(self, fd, expected=None):
        fcntl.fcntl(fd, ADD_SEALS, ALL_SEALS)
        if fcntl.fcntl(fd, GET_SEALS) != ALL_SEALS:
            raise RenderError('SEALS_NOT_APPLIED')
        size = os.fstat(fd).st_size
        self.total += size
        if size > MAX_BYTES or self.total > MAX_TOTAL:
            raise RenderError('RESOURCE_FILE_SIZE')
        actual = sha(read_fd(fd))
        if expected is not None and actual != expected:
            raise RenderError('SOURCE_HASH_MISMATCH')
        return Snapshot(fd, actual, size)

    def data(self, data, expected=None):
        if len(data) > MAX_BYTES:
            raise RenderError('RESOURCE_FILE_SIZE')
        fd = self.writable()
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            view = view[count:]
        return self.sealed(fd, expected)

    def file(self, path, expected=None):
        key = (str(Path(path).resolve()), expected)
        if key not in self.memo:
            if expected is not None and not re.fullmatch('[0-9a-f]{64}', expected):
                raise RenderError('SHA256_REQUIRED')
            with Path(path).open('rb') as f:
                data = f.read(MAX_BYTES + 1)
            self.memo[key] = self.data(data, expected)
        return self.memo[key]

    def call(self, args):
        # Local media may contain external references; deny network protocols in
        # the demuxer as well as in the manifest's pathname validation.
        if args[0] == 'ffprobe':
            args = [args[0], '-protocol_whitelist', 'file,pipe', *args[1:]]
        elif args[0] == 'ffmpeg':
            restricted = []
            for arg in args:
                if arg == '-i':
                    restricted += ['-protocol_whitelist', 'file,pipe']
                restricted.append(arg)
            args = restricted
        p = subprocess.run(args, pass_fds=tuple(self.fds), capture_output=True, timeout=1800)
        if p.returncode:
            raise RenderError(f'COMMAND_FAILED {args[0]}: {p.stderr.decode(errors="replace")[-1800:]}')
        return p.stdout

    def mp4(self, args):
        fd = self.writable()
        self.call(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-y', *args,
                   '-write_tmcd', '0', '-fs', str(MAX_BYTES), '-f', 'mp4', f'/proc/self/fd/{fd}'])
        return self.sealed(fd)


def probe(snap, snapshots):
    return json.loads(snapshots.call(['ffprobe', '-v', 'error', '-show_streams',
                                     '-show_format', '-of', 'json', snap.path]))


def positive(value, label):
    x = float(value)
    if not math.isfinite(x) or x <= 0:
        raise RenderError(f'{label}_MUST_BE_POSITIVE')
    return x


def validate_video(snap, frames, geometry, fps, snapshots):
    info = probe(snap, snapshots)
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    if len(videos) != 1:
        raise RenderError('VIDEO_STREAM_COUNT')
    v = videos[0]
    # The video stream itself must be complete even if audio makes the container longer.
    if abs(float(v.get('duration', -1)) - frames / fps) > 1 / fps / 2:
        raise RenderError('VIDEO_DURATION')
    if abs(float(v.get('start_time', -1))) > 1 / fps / 2:
        raise RenderError('VIDEO_START')
    if (v['width'], v['height'], v['r_frame_rate']) != (*geometry, f'{fps}/1'):
        raise RenderError('VIDEO_FORMAT')
    # Count actual decoded frames, not packets or container metadata. Decode audio too.
    progress = snapshots.call(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
                               '-err_detect', 'explode', '-i', snap.path,
                               '-map', '0:v:0', '-map', '0:a:0?', '-progress', 'pipe:1',
                               '-nostats', '-f', 'null', '-']).decode()
    counts = re.findall(r'^frame=(\d+)\s*$', progress, re.M)
    if not counts or int(counts[-1]) != frames:
        raise RenderError('VIDEO_FRAMES')
    return {'video_frames': frames, 'video_seconds': frames / fps,
            'width': geometry[0], 'height': geometry[1], 'fps': fps, 'full_decode': 'PASS'}


def validate_audio(snap, seconds, snapshots):
    audio = [s for s in probe(snap, snapshots)['streams'] if s['codec_type'] == 'audio']
    if (len(audio) != 1 or abs(float(audio[0].get('start_time', -1))) > 1/30
            or abs(float(audio[0].get('duration', -1))-seconds) > 1/30):
        raise RenderError('OUTPUT_AUDIO_DURATION_OR_START')


def audio_signature(snap, snapshots):
    data = json.loads(snapshots.call([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_streams', '-show_data_hash', 'sha256', '-of', 'json', snap.path]))
    streams = data.get('streams', [])
    packets = data.get('packets', [])
    if len(streams) != 1 or not packets:
        raise RenderError('AUDIO_REQUIRED')
    stream = streams[0]
    keys = ('codec_name', 'sample_rate', 'channels', 'time_base', 'extradata_hash')
    packet_keys = ('pts', 'dts', 'duration', 'size', 'data_hash', 'side_data_list')
    return {'stream': {k: stream.get(k) for k in keys},
            'packets': [{k: p.get(k) for k in packet_keys} for p in packets]}


def local(value, base):
    if not isinstance(value, str) or '://' in value:
        raise RenderError('LOCAL_PATH_REQUIRED')
    p = Path(value)
    return p if p.is_absolute() else base / p


def prepare(raw, index, doc, base, geometry, fps, snapshots):
    expected = raw.get('sha256')
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise RenderError('SHA256_REQUIRED')
    kind = raw.get('kind')
    if kind not in ('video', 'image'):
        raise RenderError('KIND_UNSUPPORTED')
    if kind == 'image' and doc.get('reuse_existing_stills') is not True and raw.get('reuse') is not True:
        raise RenderError('EXISTING_STILL_REUSE_REQUIRED')
    source = snapshots.file(local(raw['source'], base), expected)
    info = probe(source, snapshots)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if not video:
        raise RenderError('SOURCE_VIDEO_REQUIRED')
    if kind == 'image' and (video.get('codec_name') not in ('mjpeg', 'png', 'webp', 'bmp', 'tiff')
                            or info['format']['format_name'] in ('mov,mp4,m4a,3gp,3g2,mj2', 'avi')):
        raise RenderError('STILL_SOURCE_IS_NOT_AN_IMAGE')
    frames = round(positive(raw['seconds'], 'SECONDS') * fps)
    if not 1 <= frames <= 3600 * fps:
        raise RenderError('FRAMES_OUT_OF_RANGE')
    seconds = frames / fps
    start, speed = float(raw.get('start', 0)), float(raw.get('speed', 1))
    if not math.isfinite(start) or start < 0:
        raise RenderError('START_OUT_OF_RANGE')
    if kind == 'video':
        available = positive(video.get('duration') or info['format'].get('duration'), 'DURATION') - start
        if 'speed' not in raw and available < seconds:
            speed = available / seconds
        if not math.isfinite(speed) or not .85 <= speed <= 1.2:
            raise RenderError('SPEED_OUT_OF_RANGE')
        if seconds * speed > available + .001:
            raise RenderError('VIDEO_TOO_SHORT_NO_LOOP_OR_PADDING')
    elif start or speed != 1:
        raise RenderError('IMAGE_START_OR_SPEED')
    crop = raw.get('crop')
    prefix = ''
    if crop is not None:
        if isinstance(crop, dict):
            crop = [crop[k] for k in ('x', 'y', 'width', 'height')]
        if not isinstance(crop, list) or len(crop) != 4 or any(type(x) is not int for x in crop):
            raise RenderError('CROP_INVALID')
        x, y, w, h = crop
        if min(x, y) < 0 or min(w, h) < 2 or x+w > video['width'] or y+h > video['height']:
            raise RenderError('CROP_OUT_OF_BOUNDS')
        prefix = f'crop={w}:{h}:{x}:{y},'
    w, h = geometry
    if kind == 'image':
        denom = max(1, frames-1)
        ease = f'(3*pow(on/{denom},2)-2*pow(on/{denom},3))'
        vf = (prefix + f'scale={2*w}:{2*h}:force_original_aspect_ratio=increase,crop={2*w}:{2*h},'
              f"zoompan=z='1+0.015*{ease}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
              f'd={frames}:s={w}x{h}:fps={fps},trim=end_frame={frames},')
    else:
        vf = (f'trim=start={start:.9f}:duration={seconds*speed:.9f},'
              f'setpts=(PTS-STARTPTS)/{speed:.12f},fps={fps},' + prefix +
              f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},trim=end_frame={frames},')
    vf += 'setsar=1,format=yuv420p'
    return {'index': index, 'snapshot': source, 'frames': frames, 'filter': vf,
            'source_sha256': source.sha256, 'kind': kind}


def encode_segment(segment, snapshots, fps):
    return snapshots.mp4(['-i', segment['snapshot'].path, '-map', '0:v:0',
                          '-vf', segment['filter'], '-an', '-sn', '-dn', '-map_metadata', '-1',
                          '-frames:v', str(segment['frames']), '-c:v', 'libx264',
                          '-preset', 'veryfast', '-crf', '18', '-threads', '2',
                          '-r', str(fps), '-video_track_timescale', '15360'])


@contextmanager
def output_lock(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(output) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise RenderError('OUTPUT_LOCKED') from e
        yield
    finally:
        os.close(fd)


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def render(manifest, output, work=None, audio_copy=None, audio_copy_sha256=None,
           *, geometry=(1080, 1920), fps=30):
    """Low-resolution geometry is an API-only fixture seam, never a CLI switch."""
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if fps != 30 or len(geometry) != 2 or any(type(x) is not int or x <= 0 or x % 2 for x in geometry):
        raise RenderError('GEOMETRY_INVALID')
    with output_lock(output), Snapshots() as snapshots:
        raw = manifest.read_bytes()
        doc = json.loads(raw)
        if not isinstance(doc, dict) or not isinstance(doc.get('segments'), list) or not doc['segments']:
            raise RenderError('SEGMENTS_REQUIRED')
        if doc.get('music'):
            raise RenderError('MUSIC_UNSUPPORTED_USE_PREMIXED_AUDIO')
        base = manifest.parent
        # Protect all caller inputs, including a receipt path or shared cache.
        copy_config = ({'source': str(audio_copy), 'sha256': audio_copy_sha256}
                       if audio_copy is not None else doc.get('audio_copy'))
        inputs = [manifest, *[local(s['source'], base) for s in doc['segments']]]
        for value in (doc.get('ass') or doc.get('subtitles'),
                      copy_config.get('source') if isinstance(copy_config, dict) else doc.get('narrator')):
            if value:
                inputs.append(local(value, base))
        inputs = [p.resolve() for p in inputs]
        receipt_path = output.with_suffix('.receipt.json')
        if output in inputs or receipt_path in inputs:
            raise RenderError('OUTPUT_OVERLAPS_INPUT')
        cache = Path(work).resolve() if work else Path(str(output) + '.work')
        if any(p.is_relative_to(cache) for p in inputs) or output.is_relative_to(cache):
            raise RenderError('CACHE_OVERLAPS_INPUT_OR_OUTPUT')
        segments = [prepare(s, i, doc, base, geometry, fps, snapshots) for i, s in enumerate(doc['segments'])]
        total_frames = sum(s['frames'] for s in segments)
        seconds = total_frames / fps
        if seconds > 3600:
            raise RenderError('DURATION_OUT_OF_RANGE')
        ac = doc.get('audio_copy')
        if audio_copy is not None:
            ac = {'source': str(audio_copy), 'sha256': audio_copy_sha256}
        if ac:
            expected = ac.get('sha256')
            if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                raise RenderError('AUDIO_COPY_SHA256_REQUIRED')
            voice = snapshots.file(local(ac['source'], base), expected)
            original_audio = audio_signature(voice, snapshots)
            if original_audio['stream']['codec_name'] != 'aac':
                raise RenderError('AUDIO_COPY_REQUIRES_AAC')
        else:
            voice = snapshots.file(local(doc['narrator'], base), doc.get('narrator_sha256'))
            original_audio = None
        ai = [s for s in probe(voice, snapshots)['streams'] if s['codec_type'] == 'audio']
        if not ai or abs(float(ai[0].get('duration', -1)) - seconds) > 1/fps:
            raise RenderError('AUDIO_DURATION_MUST_MATCH_NO_TRUNCATION')
        sub = None
        sub_value = doc.get('ass') or doc.get('subtitles')
        if sub_value:
            sub = snapshots.file(local(sub_value, base))
            data = read_fd(sub.fd)
            if b'[Script Info]' not in data or b'[Events]' not in data:
                raise RenderError('SUBTITLES_NOT_ASS')
        version = snapshots.call(['ffmpeg', '-version']).decode().splitlines()[0]
        engine_sha = sha(Path(__file__).read_bytes())
        options = {'geometry': geometry, 'fps': fps, 'ffmpeg': version, 'engine_sha256': engine_sha}
        recipe = sha(canonical({'manifest_sha256': sha(raw), 'options': options,
                                'sources': [s['source_sha256'] for s in segments],
                                'voice': voice.sha256, 'subtitles': sub.sha256 if sub else None,
                                'audio_copy': bool(ac)}))
        if output.is_file() and receipt_path.is_file():
            try:
                old = json.loads(receipt_path.read_text())
                if not isinstance(old, dict):
                    old = {}
            except json.JSONDecodeError:
                old = {}
            if old.get('recipe_sha256') == recipe:
                try:
                    final = snapshots.file(output, old['output_sha256'])
                except (RenderError, KeyError):
                    final = None
                if final is not None:
                    validation = validate_video(final, total_frames, geometry, fps, snapshots)
                    validate_audio(final, seconds, snapshots)
                    if ac and audio_signature(final, snapshots) != original_audio:
                        raise RenderError('AUDIO_COPY_PACKET_TIMING_MISMATCH')
                    return {**old, 'reused_final': True, 'validation': {**validation,
                            'audio_packets_identical': bool(ac)}}
        cache.mkdir(parents=True, exist_ok=True)
        with output_lock(cache / 'cache'):
            rendered, reused = [], []
            for seg in segments:
                path = cache / f'segment-{seg["index"]:03d}.mp4'
                recpath = path.with_suffix('.json')
                key = sha(canonical({'options': options, 'filter': seg['filter'],
                                     'frames': seg['frames'], 'source': seg['source_sha256']}))
                snap = None
                if path.is_file() and recpath.is_file():
                    try:
                        rec = json.loads(recpath.read_text())
                        if rec['key'] == key:
                            snap = snapshots.file(path, rec['sha256'])
                            validate_video(snap, seg['frames'], geometry, fps, snapshots)
                            reused.append(seg['index'])
                    except (RenderError, KeyError, json.JSONDecodeError):
                        snap = None
                if snap is None:
                    snap = encode_segment(seg, snapshots, fps)
                    validate_video(snap, seg['frames'], geometry, fps, snapshots)
                    atomic_write(path, read_fd(snap.fd))
                    atomic_write(recpath, canonical({'key': key, 'sha256': snap.sha256}))
                rendered.append(snap)
            listing = snapshots.data(''.join(f"file '{s.path}'\n" for s in rendered).encode())
            picture = snapshots.mp4(['-protocol_whitelist', 'file', '-f', 'concat', '-safe', '0',
                                     '-i', listing.path, '-map', '0:v:0', '-c:v', 'copy', '-an', '-sn', '-dn',
                                     '-map_metadata', '-1', '-video_track_timescale', '15360'])
            validate_video(picture, total_frames, geometry, fps, snapshots)
            filters = []
            if sub:
                filters.append('ass=filename=' + sub.path)
            filters.append("drawtext=text='DRAFT / NOT FOR PUBLICATION':fontsize=20:fontcolor=white@0.75:"
                           "box=1:boxcolor=black@0.25:boxborderw=5:x=(w-tw)/2:y=24")
            args = ['-copyts', '-i', picture.path, '-i', voice.path, '-map', '0:v:0', '-map', '1:a:0',
                    '-vf', ','.join(filters), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                    '-threads', '2', '-r', str(fps), '-video_track_timescale', '15360',
                    '-avoid_negative_ts', 'disabled', '-use_editlist', '1', '-map_metadata', '-1']
            if ac:
                args += ['-c:a', 'copy']
            else:
                args += ['-af', 'loudnorm=I=-14:TP=-1.7:LRA=11,volume=-0.3dB',
                         '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2']
            final = snapshots.mp4(args)
            validation = validate_video(final, total_frames, geometry, fps, snapshots)
            validate_audio(final, seconds, snapshots)
            if ac and audio_signature(final, snapshots) != original_audio:
                raise RenderError('AUDIO_COPY_PACKET_TIMING_MISMATCH')
            validation['audio_packets_identical'] = bool(ac)
            receipt = {'version': 'draft-render-v1', 'status': 'DRAFT_TECHNICAL_ONLY_NOT_APPROVED',
                       'recipe_sha256': recipe, 'output_sha256': final.sha256,
                       'manifest_sha256': sha(raw), 'options': options, 'validation': validation,
                       'source_sha256': [s['source_sha256'] for s in segments],
                       'subtitle_sha256': sub.sha256 if sub else None, 'audio_sha256': voice.sha256,
                       'audio_copy': bool(ac), 'reused_final': False, 'reused_segments': reused,
                       'listened': False, 'audiovisual_review': False, 'publication_approved': False}
            atomic_write(output, read_fd(final.fd))
            atomic_write(receipt_path, canonical(receipt) + b'\n')
            return receipt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--work', type=Path)
    ap.add_argument('--audio-copy', type=Path)
    ap.add_argument('--audio-copy-sha256')
    args = ap.parse_args(argv)
    if bool(args.audio_copy) != bool(args.audio_copy_sha256):
        ap.error('--audio-copy and --audio-copy-sha256 are required together')
    result = render(args.manifest, args.output, args.work, args.audio_copy, args.audio_copy_sha256)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
