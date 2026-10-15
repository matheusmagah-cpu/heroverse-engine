"""One scoped offline ASR measurement of preserved BeFOHnncaeQ; never approval."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import resource
import shutil
import signal
import stat
import subprocess
import time
import zipfile

REPO = 'matheusmagah-cpu/heroverse-engine'
RELEASE = 411926125
MEDIA = {'id': 645199434, 'bytes': 33379395, 'sha256': '66d410ff0fbe8f750bb95663d6563857a2736e4da4a716818d44b4b1ee6d99bc'}
MODEL = {'id': 638696861, 'bytes': 147769996, 'sha256': '78634f845a29c523d117a29a1a14b293220787f5ede2c6c0f33a9b06c2f805cb'}
FILES = {
    'config.json': 'f3bc3821e9fc76a27bae538e11ae5b677dcdd352b4600429ce7951d398569aeb',
    'model.bin': '2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef',
    'tokenizer.json': '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df',
    'vocabulary.txt': 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf',
}
EXTRACT_CAP = 256 * 1024**2
OUTPUT_CAP = 1024**2

class ScopeError(ValueError):
    pass

def require(value, code):
    if not value:
        raise ScopeError(code)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def verify(path, record):
    require(path.stat().st_size == record['bytes'], 'SIZE_MISMATCH')
    require(digest(path) == record['sha256'], 'HASH_MISMATCH')

def gate(env):
    require(env.get('GITHUB_REPOSITORY') == REPO, 'REPOSITORY_MISMATCH')
    require(env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'MANUAL_ONLY')
    require(env.get('GITHUB_REF') == 'refs/heads/main', 'MAIN_ONLY')
    require(env.get('GITHUB_RUN_NUMBER') == '1' and env.get('GITHUB_RUN_ATTEMPT') == '1', 'ONE_RUN_ONE_ATTEMPT_ONLY')

def limit_output(cap):
    def apply():
        resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    return apply

def gh_json(endpoint):
    # Bound stdout on disk as well as subprocess duration; never print response bodies.
    import tempfile
    with tempfile.TemporaryFile() as f:
        p = subprocess.run(['gh', 'api', endpoint], stdout=f, stderr=subprocess.DEVNULL,
                           timeout=30, preexec_fn=limit_output(256*1024))
        require(p.returncode == 0, 'PRIVATE_RELEASE_READ_FAILED_NO_PERMISSION_EXPANSION')
        f.seek(0)
        return json.load(f)

def check_release(release):
    require(release.get('id') == RELEASE and release.get('draft') is False, 'RELEASE_ID_OR_STATE_MISMATCH')
    for expected in (MEDIA, MODEL):
        matches = [a for a in release.get('assets', []) if a.get('id') == expected['id']]
        require(len(matches) == 1, 'ASSET_NOT_UNIQUE')
        a = matches[0]
        require(a.get('state') == 'uploaded' and a.get('size') == expected['bytes']
                and a.get('digest') == 'sha256:' + expected['sha256'], 'ASSET_METADATA_CHANGED')

def download_asset(expected, destination):
    # Official gh handles the authenticated API/CDN redirect; credentials are never logged.
    with destination.open('xb') as f:
        p = subprocess.run(['gh', 'api', f'repos/{REPO}/releases/assets/{expected["id"]}',
                            '-H', 'Accept: application/octet-stream'], stdout=f,
                           stderr=subprocess.DEVNULL, timeout=150,
                           preexec_fn=limit_output(expected['bytes'] + 1))
    require(p.returncode == 0, 'PRIVATE_ASSET_READ_FAILED_NO_RETRY')
    verify(destination, expected)

def extract_model(archive, destination, expected=FILES):
    destination.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        require(0 < len(entries) <= 64, 'ZIP_ENTRY_COUNT')
        require(sum(i.file_size for i in entries) <= EXTRACT_CAP, 'ZIP_SIZE_CAP')
        seen = set(); selected = {}
        for i in entries:
            p = PurePosixPath(i.filename)
            require(i.filename and not p.is_absolute() and '..' not in p.parts
                    and '\\' not in i.filename and ':' not in i.filename, 'ZIP_UNSAFE_PATH')
            require(i.filename not in seen, 'ZIP_DUPLICATE_PATH'); seen.add(i.filename)
            mode = i.external_attr >> 16
            require(not stat.S_ISLNK(mode) and not (i.flag_bits & 1), 'ZIP_LINK_OR_ENCRYPTED')
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'ZIP_SPECIAL_FILE')
            if not i.is_dir() and p.name in expected:
                require(p.name not in selected, 'ZIP_DUPLICATE_MODEL_FILE')
                selected[p.name] = i
        require(set(selected) == set(expected), 'ZIP_MISSING_MODEL_FILES')
        require(len({str(PurePosixPath(i.filename).parent) for i in selected.values()}) == 1, 'ZIP_SPLIT_MODEL_DIRECTORY')
        for name, i in selected.items():
            target = destination / name
            written = 0
            with z.open(i) as src, target.open('xb') as dst:
                for block in iter(lambda: src.read(1024**2), b''):
                    written += len(block)
                    require(written <= i.file_size and written <= EXTRACT_CAP, 'ZIP_STREAM_SIZE_CAP')
                    dst.write(block)
            require(written == i.file_size and digest(target) == expected[name], 'MODEL_FILE_HASH_MISMATCH')
    return destination

def pcm_guard(path):
    source = Path(__file__).parent / 'diagnostics/rapidapi-native-av/run_audio_reviewer.py'
    spec = importlib.util.spec_from_file_location('second_opening_pcm_guard', source)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.inspect_pcm_wave(path.read_bytes()), digest(source)

def write_receipt(path, result):
    data = (json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    require(len(data) <= OUTPUT_CAP, 'RECEIPT_OUTPUT_CAP')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def transcribe(model_dir, audio):
    import numpy as np
    from faster_whisper import WhisperModel
    samples = np.frombuffer(audio, dtype='<f4').copy()
    require(len(samples) > 0 and np.isfinite(samples).all(), 'INVALID_ASR_SAMPLES')
    model = WhisperModel(str(model_dir), device='cpu', compute_type='int8', cpu_threads=1,
                         num_workers=1, local_files_only=True)
    segments, info = model.transcribe(samples, language='en', beam_size=5, vad_filter=True,
                                      word_timestamps=True, condition_on_previous_text=False)
    rows = []
    for s in segments:
        require(len(rows) < 200, 'ASR_SEGMENT_CAP')
        rows.append({'start': s.start, 'end': s.end, 'text': s.text, 'avg_logprob': s.avg_logprob,
                     'no_speech_prob': s.no_speech_prob,
                     'words': [{'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability}
                               for w in (s.words or [])]})
    return rows, info

def terminate(signum, frame):
    raise TimeoutError('BOUNDED_RUNTIME_EXPIRED')

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); started = time.monotonic()
    signal.signal(signal.SIGTERM, terminate)
    result = {'version': 'second-opening-offline-asr-v1', 'source_video_id': 'BeFOHnncaeQ',
              'requested_source_seconds': [0, 40], 'status': 'NOT_STARTED', 'semantic_approval': False,
              'perceptual_audio_approved': False, 'speech_absence_established': False,
              'production_approved': False, 'publication_authorized': False,
              'direct_listening_performed': False, 'model_inference_performed': False,
              'provider_media_requests': 0, 'external_inference_calls': 0, 'new_vendor_model_downloads': 0,
              'run_id': os.environ.get('GITHUB_RUN_ID'), 'commit': os.environ.get('GITHUB_SHA')}
    try:
        gate(os.environ)
        require(os.environ.get('HF_HUB_OFFLINE') == '1', 'OFFLINE_MODEL_LOADING_REQUIRED')
        repo = gh_json(f'repos/{REPO}')
        require(repo.get('private') is True and repo.get('full_name') == REPO, 'PRIVATE_REPO_REQUIRED')
        check_release(gh_json(f'repos/{REPO}/releases/{RELEASE}'))
        work = Path(os.environ['RUNNER_TEMP']) / 'second-opening-asr-v1'
        work.mkdir(exist_ok=False)
        require(shutil.disk_usage(work).free >= 1024**3, 'DISK_PREFLIGHT_1GIB_POLICY_CAP_NOT_PREDICTION')
        require(shutil.which('ffmpeg') is not None, 'FFMPEG_REQUIRED')
        media = work/'source.mp4'; archive = work/'model.zip'
        download_asset(MEDIA, media); download_asset(MODEL, archive)
        model = extract_model(archive, work/'model')
        result.update(media=MEDIA, model_archive=MODEL, model_file_sha256=FILES,
                      transferred_asset_bytes=MEDIA['bytes']+MODEL['bytes'])
        wav = work/'audio.wav'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(media), '-map', '0:a:0',
                        '-vn', '-t', '40.1', '-c:a', 'pcm_s16le', str(wav)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                       preexec_fn=limit_output(8*1024**2))
        guard, guard_hash = pcm_guard(wav)
        result.update(pcm_guard=guard, pcm_guard_script_sha256=guard_hash, wav_sha256=digest(wav))
        require(guard['status'] in ('DIGITAL_SILENCE', 'NONZERO_PCM'), 'INVALID_PCM')
        require(guard['channels'] == 2 and guard['sample_rate'] == 44100
                and guard['frames'] == 1765376, 'PCM_SHAPE_CHANGED')
        if guard['digital_silence']:
            result.update(status='SKIPPED_EXACT_DIGITAL_SILENCE', segments=[])
        else:
            derivative = work/'asr.f32le'
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(wav), '-f', 'f32le',
                            '-ac', '1', '-ar', '16000', str(derivative)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                           preexec_fn=limit_output(3*1024**2))
            raw = derivative.read_bytes()
            result.update(status='ASR_RUNNING', model_inference_started=True)
            write_receipt(args.output, result)
            t = time.monotonic(); rows, info = transcribe(model, raw)
            result.update(status='ASR_MEASURED', model_inference_performed=True, segments=rows,
                          inference_elapsed_seconds=time.monotonic()-t, duration_seconds=info.duration,
                          duration_after_vad_seconds=info.duration_after_vad,
                          model='faster-whisper 1.2.1 / preserved base.en / cpu int8', cpu_threads=1,
                          local_files_only=True, language='en', language_basis='FORCED_ENGLISH_MODEL_ASSUMPTION',
                          asr_derivative={'sha256': digest(derivative), 'bytes': len(raw),
                                          'sample_rate': 16000, 'channels': 1, 'format': 'f32le'})
        result['limitations'] = ['Machine transcription only; no perceptual or full-reference approval.',
                                 'Empty segments or zero VAD duration do not establish absence of speech.',
                                 'Only this second reference opening was processed; prior evidence was not repeated.']
    except Exception as e:
        result.update(status='BLOCKED', error_type=type(e).__name__)
        if isinstance(e, ScopeError):
            result['error_code'] = str(e)[:120]
    finally:
        result.update(elapsed_seconds=time.monotonic()-started,
                      process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                      resource_scope='Separate process maxima; not simultaneous aggregate memory or capacity approval.')
        write_receipt(args.output, result)
    print(json.dumps({'status': result['status'], 'semantic_approval': False}))
    return 2 if result['status'] == 'BLOCKED' else 0

if __name__ == '__main__':
    raise SystemExit(main())
