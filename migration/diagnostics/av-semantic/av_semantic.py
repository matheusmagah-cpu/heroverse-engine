#!/usr/bin/env python3
"""Free offline semantic audio layer. No network, provider or paid call.

Sound classes: Google YAMNet TFLite (hash-pinned) on 0.975 s frames every
0.48 s, reduced to five coarse classes (speech, singing, music, other sound,
silence). A frame whose best coarse score is below ABSTAIN_BELOW is UNCERTAIN.
A frame whose samples are all exactly zero is SILENCE by measurement, not by
model. Speech: faster-whisper with word timestamps; a word is accepted only
if its probability is at least WORD_MIN_PROBABILITY and it overlaps a frame
where speech or singing is present, so the two models must agree. Timing,
count and sync of events stay with av-event-meter.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np

VERSION = "av-semantic-v1"
YAMNET_SHA256 = "10c95ea3eb9a7bb4cb8bddf6feb023250381008177ac162ce169694d05c317de"
RATE, FRAME, HOP = 16000, 15600, 7680
ABSTAIN_BELOW = 0.30
PRESENT_AT = 0.30
WORD_MIN_PROBABILITY = 0.5

SPEECH = {"Speech", "Child speech, kid speaking", "Conversation", "Narration, monologue",
          "Babbling", "Speech synthesizer", "Male speech, man speaking",
          "Female speech, woman speaking", "Whispering"}
SINGING = {"Singing", "Choir", "Yodeling", "Chant", "Mantra", "Male singing", "Female singing",
           "Child singing", "Synthetic singing", "Rapping", "Humming"}
CLASSES = ("speech", "singing", "music", "other", "silence")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decode_mono16k(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0",
                          "-ac", "1", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
                         check=True, capture_output=True).stdout
    samples = np.frombuffer(raw, "<f4").copy()
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("AUDIO_DECODE_INVALID")
    return samples


class SoundClasses:
    def __init__(self, model_path):
        if sha256(model_path) != YAMNET_SHA256:
            raise ValueError("YAMNET_HASH_MISMATCH")
        from ai_edge_litert.interpreter import Interpreter
        with zipfile.ZipFile(model_path) as bundle:
            self.labels = bundle.read("yamnet_label_list.txt").decode().splitlines()
        if len(self.labels) != 521:
            raise ValueError("YAMNET_LABELS")
        index = {label: i for i, label in enumerate(self.labels)}
        # AudioSet orders the whole music subtree contiguously from "Music" up to
        # the first non-music class, "Wind".
        self.music_subtree = set(range(index["Music"], index["Wind"]))
        self.speech = [index[x] for x in SPEECH]
        self.singing = [index[x] for x in SINGING]
        self.music = index["Music"]
        self.silence = index["Silence"]
        excluded = set(self.speech) | set(self.singing) | self.music_subtree | {self.silence}
        self.other = [i for i in range(len(self.labels)) if i not in excluded]
        self.model = Interpreter(model_path=str(model_path), num_threads=2)
        self.model.allocate_tensors()
        self.input = self.model.get_input_details()[0]["index"]
        self.output = self.model.get_output_details()[0]["index"]

    def frames(self, samples):
        rows = []
        for start in range(0, max(1, len(samples) - FRAME + HOP), HOP):
            frame = samples[start:start + FRAME]
            frame = np.pad(frame, (0, FRAME - len(frame)))
            self.model.set_tensor(self.input, frame.astype(np.float32))
            self.model.invoke()
            scores = self.model.get_tensor(self.output)[0].astype(float)
            coarse = {"speech": scores[self.speech].max(), "singing": scores[self.singing].max(),
                      "music": scores[self.music], "other": scores[self.other].max(),
                      "silence": scores[self.silence]}
            if not frame.any():
                coarse = {name: (1.0 if name == "silence" else 0.0) for name in CLASSES}
            best = max(coarse, key=coarse.get)
            top = np.argsort(scores)[-3:][::-1]
            rows.append({"start_seconds": round(start / RATE, 3),
                         "end_seconds": round(min(len(samples), start + FRAME) / RATE, 3),
                         "label": best if coarse[best] >= ABSTAIN_BELOW else "UNCERTAIN",
                         "present": sorted(n for n, v in coarse.items() if v >= PRESENT_AT),
                         "scores": {n: round(float(v), 3) for n, v in coarse.items()},
                         "top_labels": [[self.labels[i], round(float(scores[i]), 3)] for i in top]})
        return rows


def segments(frames):
    merged = []
    for frame in frames:
        if merged and merged[-1]["label"] == frame["label"]:
            merged[-1]["end_seconds"] = frame["end_seconds"]
            merged[-1]["frames"] += 1
        else:
            merged.append({"label": frame["label"], "start_seconds": frame["start_seconds"],
                           "end_seconds": frame["end_seconds"], "frames": 1})
    return merged


def transcribe(model_dir, samples, frames):
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", cpu_threads=2,
                         num_workers=1, local_files_only=True)
    found, _ = model.transcribe(samples, language="en", beam_size=5, vad_filter=True,
                                word_timestamps=True, condition_on_previous_text=False)
    vocal = [(f["start_seconds"], f["end_seconds"]) for f in frames
             if {"speech", "singing"} & set(f["present"])]
    accepted, rejected = [], []
    for segment in found:
        for word in segment.words or []:
            row = {"word": word.word.strip(), "start_seconds": round(word.start, 3),
                   "end_seconds": round(word.end, 3), "probability": round(word.probability, 3)}
            agrees = any(a < word.end and word.start < b for a, b in vocal)
            (accepted if word.probability >= WORD_MIN_PROBABILITY and agrees else rejected).append(row)
    return accepted, rejected


def analyze(path, yamnet_path, whisper_dir=None):
    samples = decode_mono16k(path)
    frames = SoundClasses(yamnet_path).frames(samples)
    counts = {label: sum(f["label"] == label for f in frames) for label in CLASSES + ("UNCERTAIN",)}
    result = {"version": VERSION, "media_file": Path(path).name,
              "duration_seconds": round(len(samples) / RATE, 3),
              "frame_seconds": FRAME / RATE, "hop_seconds": HOP / RATE,
              "abstain_below": ABSTAIN_BELOW, "label_counts": counts,
              "presence_fraction": {n: round(sum(n in f["present"] for f in frames) / len(frames), 3)
                                    for n in CLASSES},
              "segments": segments(frames), "frames": frames,
              "scope": "COARSE_SOUND_CLASSES_AND_ASR_NOT_PERCEPTUAL_APPROVAL",
              "provider_calls": 0}
    if whisper_dir:
        words, rejected = transcribe(whisper_dir, samples, frames)
        result["transcript"] = " ".join(w["word"] for w in words)
        result["words"] = words
        result["rejected_words"] = rejected
    return result


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: av_semantic.py MEDIA YAMNET_TFLITE [WHISPER_MODEL_DIR]")
    print(json.dumps(analyze(*sys.argv[1:]), indent=1))
