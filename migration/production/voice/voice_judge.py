#!/usr/bin/env python3
"""Objective voice ruler (owner, 2026-10-23: "the voice must be perfect"; "you define the ruler and judge it yourself").

Every candidate narration of the same text is measured and must pass every line of RULER; among those that pass, the
most expressive one inside the natural band wins. The bands come from what listeners hear as a calm, warm, mature male
prayer voice (the measured winners: male, warm, slow, 1-2 s pauses, evidence/vidiq/20261023/hook_audit.md) and from
what YouTube's inauthentic-content policy names as the synthetic-voice signal: flat, emotionless narration.

usage: voice_judge.py TEXT_FILE NAME=AUDIO [NAME=AUDIO ...]      prints one JSON line per candidate and a verdict
"""
import json
import re
import sys

RULER = {
    "wer_max": 0.05,              # intelligibility: at most 1 word in 20 misheard by an ASR
    "f0_median_hz": (80, 150),     # mature male register
    "f0_std_semitones": (2.0, 5.5),  # below 2 st reads as monotone/robotic; above 5.5 st as over-acted
    "wpm": (105, 150),             # calm prayer pace
    "pause_mean_s": (0.25, 1.3),   # breathing between sentences, never dead air
    "pause_max_s": 3.5,
    "clipped_fraction_max": 0.0005,
    "loudness_std_db_max": 3.0,    # sentence-to-sentence loudness steadiness
    "glitch_count_max": 0,         # sudden energy jumps inside speech (> 24 dB within 20 ms)
}


def words(text):
    return re.findall(r"[a-z']+", text.lower())


def wer(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(len(r), 1)


def measure(path, text, asr):
    import librosa
    import numpy as np
    y, sr = librosa.load(path, sr=16000, mono=True)
    dur = len(y) / sr
    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=300, sr=sr, frame_length=1024)
    f0 = f0[voiced & ~np.isnan(f0)]
    semis = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.array([0.0])
    hop = int(0.02 * sr)
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    speech = db > (db.max() - 35)
    pauses, run = [], 0
    for s in speech:
        if not s:
            run += 1
        else:
            if run:
                pauses.append(run * 0.02)
            run = 0
    pauses = [p for p in pauses if p >= 0.2]
    segs, cur = [], []
    for v, s in zip(db, speech):
        if s:
            cur.append(v)
        elif len(cur) > 25:
            segs.append(np.mean(cur)); cur = []
        else:
            cur = []
    jumps = np.abs(np.diff(db))
    glitch = int(np.sum((jumps > 24) & speech[1:] & speech[:-1]))
    # the 16 kHz array, not the path: faster-whisper's PyAV decoder broke on the runner's PyAV (run 39989082891)
    segments, _ = asr.transcribe(y.astype(np.float32), language="en", beam_size=5)
    hyp = " ".join(s.text for s in segments)
    n = len(words(text))
    return {"duration_s": round(dur, 1), "wer": round(wer(text, hyp), 3),
            "f0_median_hz": round(float(np.median(f0)), 1) if len(f0) else 0.0,
            "f0_std_semitones": round(float(np.std(semis)), 2), "wpm": round(n / (dur / 60), 1),
            "pause_mean_s": round(float(np.mean(pauses)), 2) if pauses else 0.0,
            "pause_max_s": round(max(pauses), 2) if pauses else 0.0,
            "clipped_fraction": round(float(np.mean(np.abs(y) > 0.99)), 5),
            "loudness_std_db": round(float(np.std(segs)), 2) if len(segs) > 1 else 0.0, "glitch_count": glitch}


def verdict(m):
    fails = []
    lo_hi = lambda k: RULER[k][0] <= m[k] <= RULER[k][1]
    if m["wer"] > RULER["wer_max"]: fails.append("WER")
    for k in ("f0_median_hz", "f0_std_semitones", "wpm", "pause_mean_s"):
        if not lo_hi(k): fails.append(k.upper())
    if m["pause_max_s"] > RULER["pause_max_s"]: fails.append("PAUSE_MAX")
    if m["clipped_fraction"] > RULER["clipped_fraction_max"]: fails.append("CLIPPING")
    if m["loudness_std_db"] > RULER["loudness_std_db_max"]: fails.append("LOUDNESS_UNSTEADY")
    if m["glitch_count"] > RULER["glitch_count_max"]: fails.append("GLITCH")
    return fails


def main(text_file, *candidates):
    from faster_whisper import WhisperModel
    text = open(text_file).read()
    asr = WhisperModel("base.en", device="cpu", compute_type="int8")
    results = {}
    for c in candidates:
        name, path = c.split("=", 1)
        m = measure(path, text, asr)
        m["fails"] = verdict(m)
        results[name] = m
        print(json.dumps({"candidate": name, **m}))
    passing = {k: v for k, v in results.items() if not v["fails"]}
    best = max(passing, key=lambda k: (passing[k]["f0_std_semitones"], -passing[k]["wer"])) if passing else None
    print(json.dumps({"VOICE_VERDICT": best, "passing": sorted(passing), "ruler": RULER}))


if __name__ == "__main__":
    main(*sys.argv[1:])
