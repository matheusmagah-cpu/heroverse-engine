#!/usr/bin/env python3
"""Offline c01-to-WAV builder. Code/proof only in Git; media stays runner-local.

Install at migration/diagnostics/synthetic-audio-c01/build_audio.py.
The CLI accepts one NEW output directory. It has no network/provider actions.
proof.json is operator-only and must never be included in provider requests.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave

SOURCE_SHA256 = '5562d675416107eb9ec70643edd43e5375b85aa74051730f1d357a88d34e79df'
SOURCE_BYTES = 19083
SOURCE_BUILDER_SHA256 = '7e207de57792eb6689df84d956b637e8e41ecbc7093fad9285113874751a6c02'
DECODED_F32_SHA256 = '5efda979496abfda7a03ae21f255319f24524f58b4726f21666fa905bf5beae0'
TRIMMED_F32_SHA256 = '02c73b990852858d14ca6a29be9dcbeb07f049f2fab908743117c6991d2e162e'
PCM16_SHA256 = '6434c16155d75c81933f30efabb4aea450718027f42db376119287b8dcf7f0f4'
WAV_SHA256 = 'ed00a94f25785cd763f1dc23f33447c317d0bea9cf8f0a11232d8d00f619a45b'
SAMPLE_RATE, CHANNELS, SECONDS = 48000, 1, 6
SAMPLES, DECODED_SAMPLES, WAV_BYTES = 288000, 288768, 576044


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, code):
    if not ok:
        raise ValueError(code)


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


def verified_samples(pcm_f32):
    require(len(pcm_f32) == DECODED_SAMPLES * 4, 'DECODED_SAMPLE_COUNT_MISMATCH')
    require(digest(pcm_f32) == DECODED_F32_SHA256, 'DECODED_F32_HASH_MISMATCH')
    samples = [value[0] for value in struct.iter_unpack('<f', pcm_f32)]
    require(all(math.isfinite(value) for value in samples), 'NONFINITE_PCM')
    require(all(value == 0 for value in samples[SAMPLES:]), 'NONZERO_AAC_TAIL')
    require(digest(pcm_f32[:SAMPLES * 4]) == TRIMMED_F32_SHA256, 'TRIMMED_F32_HASH_MISMATCH')
    return samples[:SAMPLES]


def canonical_wav(pcm_f32):
    """Pure, deterministic conversion of the verified decoded c01 float bytes.

    Keep samples 0..287999 at their original 48 kHz time positions; remove
    only 768 verified-zero decoder-padding samples beyond the six-second track.
    Quantization is Python round (nearest, ties-to-even), then signed-16 clamp.
    No resampling, channel conversion, normalization, dithering, or time shift.
    """
    samples = verified_samples(pcm_f32)
    pcm = b''.join(struct.pack('<h', max(-32768, min(32767, round(value * 32768))))
                   for value in samples)
    require(digest(pcm) == PCM16_SHA256, 'PCM16_HASH_MISMATCH')
    header = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36 + len(pcm), b'WAVE',
                         b'fmt ', 16, 1, CHANNELS, SAMPLE_RATE, SAMPLE_RATE * 2,
                         2, 16, b'data', len(pcm))
    result = header + pcm
    require(len(result) == WAV_BYTES and digest(result) == WAV_SHA256, 'WAV_HASH_MISMATCH')
    return result


def decode_source(path):
    """Verify exact original MP4 before invoking its audio decoder."""
    source = Path(path).read_bytes()
    require(len(source) == SOURCE_BYTES and digest(source) == SOURCE_SHA256,
            'ORIGINAL_C01_BYTE_IDENTITY_REQUIRED')
    probe = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'a',
                           '-show_streams', '-of', 'json', str(path)]))
    streams = probe.get('streams', [])
    require(len(streams) == 1, 'ONE_AUDIO_STREAM_REQUIRED')
    audio = streams[0]
    require(audio.get('codec_name') == 'aac' and audio.get('channels') == CHANNELS
            and int(audio.get('sample_rate', 0)) == SAMPLE_RATE
            and float(audio.get('duration', -1)) == SECONDS
            and float(audio.get('start_time', -1)) == 0, 'SOURCE_AUDIO_SPEC_MISMATCH')
    # Deliberately no -ar, -ac, -af, -ss, or -t: decode the original track once.
    return run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:a:0',
                '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])


def tone_intervals(samples):
    active = []
    for start in range(0, len(samples), 48):
        block = samples[start:start + 48]
        if math.sqrt(sum(value * value for value in block) / len(block)) >= .02:
            index = start // 48
            if not active or index != active[-1][-1] + 1:
                active.append([])
            active[-1].append(index)
    return [{'start_seconds': group[0] / 1000,
             'end_seconds_exclusive': (group[-1] + 1) / 1000} for group in active]


def make_proof(pcm_f32, wav):
    """Operator-only evidence, including timing values; never a model payload."""
    floats = verified_samples(pcm_f32)
    require(wav == canonical_wav(pcm_f32), 'NONCANONICAL_WAV')
    with wave.open(io.BytesIO(wav), 'rb') as reader:
        require(reader.getparams()[:4] == (CHANNELS, 2, SAMPLE_RATE, SAMPLES), 'WAV_SPEC_MISMATCH')
        pcm = reader.readframes(SAMPLES)
        require(reader.readframes(1) == b'', 'EXTRA_WAV_SAMPLES')
    integers = [value[0] for value in struct.iter_unpack('<h', pcm)]
    output = [value / 32768 for value in integers]
    max_error = max(abs(a - b) for a, b in zip(floats, output))
    clipping = sum(not -32768 <= round(value * 32768) <= 32767 for value in floats)
    require(clipping == 0 and max_error <= .5 / 32768, 'QUANTIZATION_ERROR')
    before, after = tone_intervals(floats), tone_intervals(output)
    require(before == after and len(after) == 3, 'TONE_INTERVALS_CHANGED')
    expected = [1.5, 3.5, 5.5]
    for interval, onset in zip(after, expected):
        require(abs(interval['start_seconds'] - onset) < .015, 'ONSET_TOLERANCE')
        require(abs(interval['end_seconds_exclusive'] - onset - .1) < .015, 'OFFSET_TOLERANCE')
    return {
        'schema_version': 1, 'scope': 'SINGLE_C01_AUDIO_ONLY_OFFLINE_PREPARATION',
        'operator_only': True, 'do_not_send_to_provider': True,
        'contains_user_data': False, 'generated_media_is_not_model_validation': True,
        'media_permitted_in_repository': False, 'media_permitted_in_artifacts': False,
        'source': {'filename': 'c01.mp4', 'size_bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA256,
                   'must_be_byte_identical_before_decode': True,
                   'decoded_f32le_sha256': digest(pcm_f32), 'decoded_sample_count': DECODED_SAMPLES,
                   'trimmed_f32le_sha256': digest(pcm_f32[:SAMPLES * 4]),
                   'removed_tail_samples': DECODED_SAMPLES - SAMPLES,
                   'removed_tail_exactly_zero': True},
        'output': {'filename': 'control.wav', 'mime_type': 'audio/wav', 'size_bytes': len(wav),
                   'sha256': digest(wav), 'pcm_s16le_sha256': digest(pcm),
                   'sample_rate': SAMPLE_RATE, 'channels': CHANNELS,
                   'bits_per_sample': 16, 'sample_count': SAMPLES, 'duration_seconds': SECONDS,
                   'header_bytes': 44, 'pcm_format': 'signed 16-bit little-endian'},
        'conversion': {'resampled': False, 'time_shift_seconds': 0, 'dithered': False,
                       'normalized': False, 'clipped_samples': clipping,
                       'quantization': 'round(sample * 32768), nearest ties-to-even; clamp signed16',
                       'max_absolute_quantization_error': max_error,
                       'max_permitted_error': .5 / 32768},
        'timing': {'method': 'Nonoverlapping 48-sample (1 ms) RMS windows >= 0.02 full scale',
                   'source_intervals_seconds': before, 'wav_intervals_seconds': after,
                   'intervals_exactly_preserved': True,
                   'maximum_measured_onset_change_seconds': 0,
                   'onset_tolerance_seconds': .015,
                   'nominal_tone_onsets_seconds': expected,
                   'limitations': 'Operational RMS onset; not perceptual/sample-exact timing.'},
        'all_checks_passed': True,
    }


def load_source_builder():
    # Resolve only the preserved sibling helper in the final repository layout.
    path = Path(__file__).resolve().parents[1] / 'gemini-files-delivery/build_c01.py'
    require(digest(path.read_bytes()) == SOURCE_BUILDER_SHA256, 'SOURCE_BUILDER_HASH_MISMATCH')
    spec = importlib.util.spec_from_file_location('verified_c01_source_builder', path)
    require(spec is not None and spec.loader is not None, 'SOURCE_BUILDER_LOAD_FAILED')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(output):
    output = Path(output).resolve()
    require(not output.exists(), 'NEW_OUTPUT_DIRECTORY_REQUIRED')
    source_builder = load_source_builder()
    output.mkdir(parents=True)
    source_root = output / 'operator-only/source-build'
    source_builder.build(source_root)
    # A regenerated-but-different MP4 fails here, before decode or any upload.
    pcm_f32 = decode_source(source_root / 'stimuli/c01.mp4')
    wav = canonical_wav(pcm_f32)
    proof = make_proof(pcm_f32, wav)
    proof['source']['regenerated_by_preserved_builder'] = True
    proof['source']['builder_sha256'] = SOURCE_BUILDER_SHA256
    proof['tools'] = {'ffmpeg': run(['ffmpeg', '-version']).decode().splitlines()[0],
                      'ffprobe': run(['ffprobe', '-version']).decode().splitlines()[0]}
    (output / 'control.wav').write_bytes(wav)
    require(digest((output / 'control.wav').read_bytes()) == WAV_SHA256, 'WAV_WRITE_HASH_MISMATCH')
    (output / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'status': 'OFFLINE_AUDIO_ONLY_VERIFIED', 'size_bytes': len(wav),
                      'sha256': WAV_SHA256, 'proof_operator_only': True}))
    return proof


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: build_audio.py NEW_OUTPUT_DIRECTORY')
    build(Path(sys.argv[1]))
