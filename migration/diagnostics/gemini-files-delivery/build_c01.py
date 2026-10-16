#!/usr/bin/env python3
"""Build only c01 using the preserved control recipe; no network or credentials."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

RECIPE_SHA256 = '8b4b9ea021836045c74ec14bd3b881b4f69f9391720534607717de9c4a8fb95d'
ORIGINAL_SHA256 = '5562d675416107eb9ec70643edd43e5375b85aa74051730f1d357a88d34e79df'
MAX_BYTES = 262144


def load_recipe():
    path = Path(__file__).resolve().parents[2] / 'evidence/av-evaluator-controls-20261016/scripts/build_and_verify.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != RECIPE_SHA256:
        raise ValueError('PRESERVED_RECIPE_HASH_MISMATCH')
    spec = importlib.util.spec_from_file_location('preserved_control_recipe', path)
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    return recipe


def build(root):
    if root.exists():
        raise ValueError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    root.mkdir(parents=True)
    (root / 'stimuli').mkdir()
    r = load_recipe()
    # An isolated module instance selects one existing case. No shared source edit.
    r.CASES = [case for case in r.CASES if case[0] == 'c01.mp4']
    if r.CASES != [('c01.mp4', 'audio_late_500ms', True, .5)]:
        raise ValueError('EXACT_C01_RECIPE_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='c01_recipe_') as tmp:
        tmp = Path(tmp)
        r.make_video(tmp / 'v1.mp4', True)
        source = {'c01.mp4': r.make_pcm(tmp / 'audio.wav', .5)}
        r.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(tmp / 'v1.mp4'), '-i', str(tmp / 'audio.wav'),
               '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
               '-profile:a', 'aac_low', '-b:a', '128k', '-ar', str(r.SR), '-ac', '1',
               '-threads', '1', '-t', str(r.SECONDS), '-map_metadata', '-1',
               '-fflags', '+bitexact', '-flags:a', '+bitexact', '-movflags', '+faststart',
               str(root / 'stimuli/c01.mp4')])
    # Reuse all real decoded-pixel, PCM, duration, PTS and codec assertions.
    manifest = r.analyze(root, source)
    manifest['cross_file_checks'] = {'not_performed': 'Single c01 build; no cross-file claim.'}
    manifest['scope'] = 'ONE_REGENERATED_C01_CONTROL'
    manifest['recipe_source_sha256'] = RECIPE_SHA256
    manifest['original_reference_sha256'] = ORIGINAL_SHA256
    manifest['cross_toolchain_byte_identity_promised'] = False
    record = manifest['files'][0]
    if not 0 < record['size_bytes'] <= MAX_BYTES:
        raise ValueError('SYNTHETIC_FILE_SIZE_LIMIT')
    if any(abs(value - .5) > .015 for value in record['audio']['tone_onset_minus_flash_seconds']):
        raise ValueError('POSITIVE_500MS_CONTROL_REQUIRED')
    r.dump(root / 'operator-only/manifest.json', manifest)
    media = (root / 'stimuli/c01.mp4').read_bytes()
    preflight = {
        'version': 'heroverse-gemini-files-preflight-v1',
        'filename': 'c01.mp4', 'mime_type': 'video/mp4', 'size_bytes': len(media),
        'sha256': hashlib.sha256(media).hexdigest(), 'duration_seconds': 6,
        'nominal_audio_onset_minus_flash_seconds': .5,
        'pixels_and_pcm_verified': True, 'all_checks_passed': True,
        'manifest_sha256': hashlib.sha256((root / 'operator-only/manifest.json').read_bytes()).hexdigest(),
        'recipe_source_sha256': RECIPE_SHA256,
        'original_reference_sha256': ORIGINAL_SHA256,
        'byte_identical_to_original_reference': hashlib.sha256(media).hexdigest() == ORIGINAL_SHA256,
        'ffmpeg': manifest['tools']['ffmpeg'], 'ffprobe': manifest['tools']['ffprobe'],
        'generated_media_is_not_model_validation': True,
    }
    r.dump(root / 'preflight.json', preflight)
    print(json.dumps({'status': 'OFFLINE_PIXELS_PCM_VERIFIED', 'bytes': len(media),
                      'sha256': preflight['sha256'], 'nominal_offset_seconds': .5}))
    return preflight


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build_c01.py NEW_OUTPUT_DIRECTORY')
    build(Path(sys.argv[1]).resolve())
