"""Import an existing private edit without reconstructing its voice or inventing word timing.

An import is DRAFT evidence, never a plan pass, source approval or publishing record.
The regular generated-voice pipeline must not write into this workspace. Render via
the existing draft renderer, which copies the bound final audio packet stream.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import draft_render as dr

RECEIPT = 'existing-edit.json'
PENDING = 'existing-edit.pending'
SCHEMA = 'heroverse-existing-edit-v1'


def refuse_rebuild(work):
    if any(os.path.lexists(Path(work) / name) for name in (RECEIPT, PENDING)):
        raise SystemExit('EXISTING_EDIT_IMMUTABLE use render-imported; no voice reconstruction')


def relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('EXISTING_EDIT_RELATIVE_PATH_REQUIRED')
    return PurePosixPath(value)


def snapshot(root, record, snapshots):
    """Read a regular file through confined directory descriptors; consume sealed bytes."""
    path = relative(record['path'])
    digest = record['sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('EXISTING_EDIT_SHA256_REQUIRED')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('EXISTING_EDIT_REGULAR_FILE_REQUIRED')
            return snapshots.data(stream.read(dr.MAX_BYTES + 1), digest)
    except OSError as exc:
        raise ValueError('EXISTING_EDIT_PATH_REFUSED') from exc
    finally:
        os.close(fd)


def integer(value):
    if type(value) is not int:
        raise ValueError('EXISTING_EDIT_INTEGER_REQUIRED')
    return value


def span(row, start, limit):
    if integer(row['start_frame']) != start or not start < integer(row['end_frame']) <= limit:
        raise ValueError('EXISTING_EDIT_FRAME_COVERAGE')
    return row['end_frame']


def encoded(doc):
    return (json.dumps(doc, indent=2, ensure_ascii=False) + '\n').encode()


def verify(work):
    """Idempotent resume refuses missing, changed or symlinked imported bytes."""
    work = Path(work)
    if work.is_symlink() or (work / RECEIPT).is_symlink():
        raise ValueError('EXISTING_EDIT_OUTPUT_CHANGED')
    try:
        receipt = json.loads((work / RECEIPT).read_text())
        if receipt['schema'] != SCHEMA or receipt['status'] != 'IMPORTED_NOT_APPROVED':
            raise ValueError('receipt status')
        with dr.Snapshots() as snapshots:
            for name, digest in receipt['outputs'].items():
                snapshot(work, {'path': name, 'sha256': digest}, snapshots)
        if not {'plan.json', 'binding.json', 'manifest.json', 'narration.wav', 'captions.ass'} <= receipt['outputs'].keys():
            raise ValueError('receipt outputs')
        return receipt
    except (KeyError, OSError, ValueError, TypeError) as exc:
        raise ValueError('EXISTING_EDIT_OUTPUT_CHANGED') from exc


def import_edit(binding_path, bundle_root, work, engine):
    root, work = Path(bundle_root).absolute(), Path(work).absolute()
    raw = Path(binding_path).read_bytes()
    binding = json.loads(raw)
    binding_sha = hashlib.sha256(raw).hexdigest()
    if work.exists() or work.is_symlink():
        if not (work / RECEIPT).is_file():
            raise ValueError('EXISTING_EDIT_OUTPUT_EXISTS')
        receipt = verify(work)
        if receipt['binding_sha256'] != binding_sha:
            raise ValueError('EXISTING_EDIT_INPUT_CHANGED')
        return receipt
    if binding.get('schema') != SCHEMA or binding.get('fps') != 30:
        raise ValueError('EXISTING_EDIT_SCHEMA_OR_FPS')
    frames = integer(binding['frames'])
    if not 0 < frames <= 3600 * 30:
        raise ValueError('EXISTING_EDIT_FRAMES')
    seconds = frames / 30
    with dr.Snapshots() as snapshots:
        inputs = {key: snapshot(root, binding[key], snapshots)
                  for key in ('plan', 'manifest', 'master_audio', 'final_mix', 'captions')}
        plan = json.loads(dr.read_fd(inputs['plan'].fd))
        manifest = json.loads(dr.read_fd(inputs['manifest'].fd))
        if binding['episode'] != plan['episode']:
            raise ValueError('EXISTING_EDIT_EPISODE')
        if (manifest.get('narrator') != binding['master_audio']['path']
                or manifest.get('ass') != binding['captions']['path']
                or manifest.get('audio_copy') != {'source': binding['final_mix']['path'],
                                                  'sha256': binding['final_mix']['sha256']}):
            raise ValueError('EXISTING_EDIT_MANIFEST_BINDING')
        master = dr.read_fd(inputs['master_audio'].fd)
        with wave.open(io.BytesIO(master), 'rb') as audio:
            params = audio.getparams()
            pcm = audio.readframes(params.nframes)
        width = params.nchannels * params.sampwidth
        if (params.comptype != 'NONE' or params.sampwidth != 2 or params.nchannels != 1
                or params.nframes * 30 != frames * params.framerate
                or len(pcm) != params.nframes * width or params.framerate % 30):
            raise ValueError('EXISTING_EDIT_AUDIO_FORMAT_OR_DURATION')
        dr.validate_audio(inputs['final_mix'], seconds, snapshots)
        mix_streams = dr.probe(inputs['final_mix'], snapshots)['streams']
        if any(s.get('codec_name') != 'aac' for s in mix_streams if s['codec_type'] == 'audio'):
            raise ValueError('AUDIO_COPY_REQUIRES_AAC')
        items, carried = engine.plan_check.sequence(plan)
        script = engine.voice_script(plan)
        expected_units = [dict({k: item[k] for k in ('kind', 'text', 'reference') if k in item},
                               voice=voice.get('voice_id', script['voice']['voice_id']))
                          for item, voice in zip(items, script['segments'])]
        visuals, segments = binding['visuals'], manifest['segments']
        if not visuals or len(visuals) != len(segments):
            raise ValueError('EXISTING_EDIT_VISUALS')
        cursor, ids, logical_ids, unit_indices, shot_spans = 0, [], [], [], {}
        output = {'narration.wav': inputs['master_audio'], 'captions.ass': inputs['captions'],
                  'plan.json': inputs['plan']}
        mix_name = 'final-mix' + relative(binding['final_mix']['path']).suffix
        output[mix_name] = inputs['final_mix']
        for i, (visual, segment) in enumerate(zip(visuals, segments)):
            end = span(visual, cursor, frames)
            if (visual['id'] != segment['id'] or visual['id'] in ids
                    or type(segment['seconds']) not in (int, float)
                    or not math.isfinite(segment['seconds'])
                    or abs(segment['seconds'] * 30 - (end - cursor)) > 1e-6):
                raise ValueError('EXISTING_EDIT_SEGMENT_TIMING')
            ids.append(visual['id'])
            logical_cursor = cursor
            visual_units = []
            for shot in visual['logical_shots']:
                logical_cursor = span(shot, logical_cursor, end)
                logical_ids.append(shot['shot'])
                shot_spans[shot['shot']] = (shot['start_frame'], shot['end_frame'])
                plan_index = next((k for k, s in enumerate(plan['shots']) if s['id'] == shot['shot']), None)
                if plan_index is None:
                    raise ValueError('EXISTING_EDIT_SHOT_UNKNOWN')
                for unit in carried[plan_index]:
                    if unit not in visual_units:
                        visual_units.append(unit)
            if logical_cursor != end:
                raise ValueError('EXISTING_EDIT_LOGICAL_COVERAGE')
            if visual['narration_units'] != [expected_units[k] for k in visual_units]:
                raise ValueError('EXISTING_EDIT_VISUAL_WORDS')
            for unit in visual_units:
                if unit not in unit_indices:
                    unit_indices.append(unit)
            media = snapshot(root, {'path': segment['source'], 'sha256': segment['sha256']}, snapshots)
            name = f'media/{i:03d}' + relative(segment['source']).suffix
            output[name] = media
            segment['source'] = name
            cursor = end
        if (cursor != frames or logical_ids != [shot['id'] for shot in plan['shots']]
                or unit_indices != list(range(len(expected_units))) or len(set(logical_ids)) != len(logical_ids)):
            raise ValueError('EXISTING_EDIT_PLAN_OR_COVERAGE')
        # Group timing is known; no sentence/phoneme boundaries are fabricated.
        keeper = {}
        for shot in plan['shots']:
            if shot['kind'] != 'keeper':
                continue
            sid = shot['id']
            if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', sid):
                raise ValueError('EXISTING_EDIT_SHOT_ID')
            start, end = shot_spans[sid]
            sample_start, sample_end = start * params.framerate // 30, end * params.framerate // 30
            data = io.BytesIO()
            with wave.open(data, 'wb') as clip:
                clip.setparams(params)
                clip.writeframes(pcm[sample_start * width:sample_end * width])
            name = f'keeper/{sid}.wav'
            output[name] = snapshots.data(data.getvalue())
            keeper[sid] = {'path': name, 'sha256': output[name].sha256,
                           'start_frame': start, 'end_frame': end, 'speech_boundaries': None,
                           'provider_submitted': False}
        manifest.update(status='DRAFT_NOT_APPROVED', narrator='narration.wav', ass='captions.ass',
                        audio_copy={'source': mix_name, 'sha256': inputs['final_mix'].sha256})
        output['manifest.json'] = snapshots.data(encoded(manifest))
        output['binding.json'] = snapshots.data(raw)
        checked = engine.check_plan(plan)
        receipt = {'schema': SCHEMA, 'status': 'IMPORTED_NOT_APPROVED', 'episode': binding['episode'],
                   'binding_sha256': binding_sha, 'plan_sha256': inputs['plan'].sha256,
                   'fps': 30, 'frames': frames, 'seconds': seconds, 'keeper': keeper,
                   'plan_blockers': checked['problems'] + checked['pending'],
                   'word_boundaries': None, 'production_approved': False, 'publication_approved': False,
                   'outputs': {name: snap.sha256 for name, snap in output.items()}}
        # Exclusive creation: an interrupted import remains visible and is never overwritten on retry.
        work.parent.mkdir(parents=True, exist_ok=True)
        work.mkdir(mode=0o700)
        with (work / PENDING).open('xb') as stream:
            stream.write(binding_sha.encode())
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(work, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        for name, snap in output.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(dr.read_fd(snap.fd))
        with (work / RECEIPT).open('xb') as stream:
            stream.write(encoded(receipt))
            stream.flush()
            os.fsync(stream.fileno())
        (work / PENDING).unlink()
        return receipt


def render_imported(work, output):
    work, output = Path(work).resolve(), Path(output).resolve()
    receipt = verify(work)
    if output.is_relative_to(work):
        raise ValueError('EXISTING_EDIT_OUTPUT_OVERLAP')
    return dr.render(work / 'manifest.json', output,
                     expected_manifest_sha256=receipt['outputs']['manifest.json'],
                     expected_subtitle_sha256=receipt['outputs']['captions.ass'])
