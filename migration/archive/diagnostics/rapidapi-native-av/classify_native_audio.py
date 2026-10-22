"""CPU-only, hash-bound sound-event evidence; never emits perceptual approval."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time
import wave
import zipfile

import numpy as np
from ai_edge_litert.interpreter import Interpreter


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    started = time.monotonic()
    assert sha(args.input) == '420e1a1bec95c5582e817093aee326fc4cf0c98bfca0ea078dfb7baf090043dc'
    assert sha(args.model) == '10c95ea3eb9a7bb4cb8bddf6feb023250381008177ac162ce169694d05c317de'
    with wave.open(str(args.input)) as w:
        assert (w.getnchannels(), w.getframerate(), w.getsampwidth()) == (2, 44100, 2)
        native = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, 2)
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(args.input),
        '-f', 'f32le', '-ac', '1', '-ar', '16000', 'pipe:1'],
        capture_output=True, check=True, timeout=30)
    assert not decoded.stderr
    samples = np.frombuffer(decoded.stdout, '<f4').copy()
    assert np.isfinite(samples).all() and 640000 <= len(samples) <= 641600
    with zipfile.ZipFile(args.model) as z:
        labels = z.read('yamnet_label_list.txt').decode().splitlines()
    assert len(labels) == 521
    model = Interpreter(model_path=str(args.model), num_threads=2)
    model.allocate_tensors()
    inp, out = model.get_input_details()[0], model.get_output_details()[0]
    assert list(inp['shape']) == [15600] and list(out['shape']) == [1, 521]
    rows = []
    for start in range(0, len(samples), 7680):
        frame = samples[start:start + 15600]
        frame = np.pad(frame, (0, 15600 - len(frame)))
        model.set_tensor(inp['index'], frame)
        model.invoke()
        scores = model.get_tensor(out['index'])[0]
        assert np.isfinite(scores).all()
        rows.append((start / 16000, scores.copy()))
    def ranks(values):
        return [{'label': labels[i], 'score': float(values[i])}
                for i in np.argsort(values)[-8:][::-1]]
    means = np.mean([s for _, s in rows], axis=0)
    windows = []
    for start, end in [(0, 10), (10, 20), (20, 30), (30, len(samples) / 16000)]:
        subset = [s for t, s in rows if start <= t < end]
        windows.append({'start_seconds': start, 'end_seconds': end,
                        'top_events': ranks(np.mean(subset, axis=0))})
    result = {
        'version': 'native-audio-events-v1', 'input_pcm_sha256': sha(args.input),
        'source_video_sha256': '5dca962757c952c8048c746f23f96a325cf15258f429e1e79e7b5ddf72fb0fb5',
        'model': 'Google YAMNet classification TFLite v1',
        'model_source': 'https://tfhub.dev/google/lite-model/yamnet/classification/tflite/1?lite-format=tflite',
        'model_sha256': sha(args.model), 'model_bytes': args.model.stat().st_size,
        'runtime': 'ai-edge-litert ' + importlib.metadata.version('ai-edge-litert'),
        'threads': 2, 'inference_frames': len(rows), 'hop_seconds': .48,
        'frame_seconds': .975, 'last_frame_zero_padded': True,
        'asr_derivative_sha256': hashlib.sha256(decoded.stdout).hexdigest(),
        'native_pcm_unchanged': True, 'top_mean_events': ranks(means), 'windows': windows,
        'sample_clipping_count': int(np.sum((native == -32768) | (native == 32767))),
        'exact_zero_stereo_samples': int(np.sum(np.all(native == 0, axis=1))),
        'native_samples_per_channel': len(native),
        'elapsed_seconds': time.monotonic() - started,
        'audio_uploaded_to_external_inference_service': False,
        'inference_api_calls': 0, 'human_or_direct_model_listening_completed': False,
        'perceptual_audio_approved': False, 'recurring_capacity_qualified': False,
        'limitations': ['Event scores are uncalibrated model outputs, not certified probabilities.',
                        'Classification cannot establish artistic quality, rights, spoken language or absence of speech.',
                        'Only the registered opening is covered; no full-video approval.']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
