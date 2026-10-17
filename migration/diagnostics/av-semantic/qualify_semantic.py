#!/usr/bin/env python3
"""Qualify av_semantic against criteria.json with ground truth by construction.

Inputs are built offline: c03/c04 from the hash-pinned control recipe, pink
noise from ffmpeg, known English speech from espeak-ng, and that same speech
mixed over each real opening at a fixed +6 dB speech-to-music RMS ratio over
its span. No network or provider call; models are local, hash-pinned files.
"""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import numpy as np

import av_semantic as sem

HERE = Path(__file__).resolve().parent
CRITERIA = json.loads((HERE / "criteria.json").read_text())
RECIPE = HERE.parents[1] / "evidence/av-evaluator-controls-20261016/scripts/build_and_verify.py"
TEXT = ("The blue train arrived after midnight. There are seven yellow lamps near the old bridge. "
        "Please bring three small boxes to the kitchen before noon.")
SPEECH_OFFSET_SECONDS, SPEECH_OVER_MUSIC_DB = 10.0, 6.0
NUMBERS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
           "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten", "12": "twelve"}


def tokens(text):
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [NUMBERS.get(w, w) for w in words]


def wer(reference, hypothesis):
    ref, hyp = tokens(reference), tokens(hypothesis)
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        previous, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (r != h))
    return row[-1] / len(ref)


def run(args):
    subprocess.run(args, check=True, capture_output=True)


def wav_f32(path, rate=sem.RATE):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
                                         "-f", "f32le", "pipe:1"], check=True, capture_output=True).stdout, "<f4").copy()


def write_wav(path, samples):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(sem.RATE), "-ac", "1",
                    "-i", "pipe:0", str(path)], input=samples.astype("<f4").tobytes(),
                   check=True, capture_output=True)


def span(samples, threshold=1e-3):
    active = np.flatnonzero(np.abs(samples) >= threshold)
    return active[0] / sem.RATE, (active[-1] + 1) / sem.RATE


def speech_fraction(result, start, end, classes=("speech", "singing")):
    frames = [f for f in result["frames"] if f["start_seconds"] < end and start < f["end_seconds"]]
    return sum(bool(set(classes) & set(f["present"])) for f in frames) / max(1, len(frames))


def main(output, yamnet, whisper_dir, openings):
    rules, results = CRITERIA["rules"], []
    with tempfile.TemporaryDirectory(prefix="av_sem_") as tmp:
        tmp = Path(tmp)
        spec = importlib.util.spec_from_file_location("recipe", RECIPE)
        recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recipe)
        recipe.build(tmp / "controls")
        cases = {"c03_digital_silence": tmp / "controls/stimuli/c03.mp4",
                 "c04_tones": tmp / "controls/stimuli/c04.mp4"}
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "anoisesrc=color=pink:amplitude=0.0316:sample_rate=16000:seed=11", "-t", "8", str(tmp / "noise.wav")])
        cases["pink_noise"] = tmp / "noise.wav"
        run(["espeak-ng", "-v", "en-us", "-s", "150", "-w", str(tmp / "speech_raw.wav"), TEXT])
        speech = wav_f32(tmp / "speech_raw.wav")
        speech = np.concatenate([np.zeros(sem.RATE), speech, np.zeros(sem.RATE)])
        write_wav(tmp / "speech.wav", speech)
        speech_span = span(speech)

        def record(name, result, checks):
            results.append({"case": name, "status": "PASS" if all(checks.values()) else "FAIL",
                            "checks": checks, "label_counts": result["label_counts"],
                            "presence_fraction": result["presence_fraction"],
                            "transcript": result.get("transcript"),
                            "rejected_word_count": len(result.get("rejected_words", []))})

        for name in ("c03_digital_silence", "c04_tones", "pink_noise"):
            r = sem.analyze(cases[name], yamnet, whisper_dir)
            checks = {"no_speech_segment": r["label_counts"]["speech"] == 0,
                      "zero_accepted_words": not r["words"]}
            if name == "c03_digital_silence":
                checks["no_singing_or_music"] = r["label_counts"]["singing"] == r["label_counts"]["music"] == 0
            else:
                checks["no_raw_word_probability_ge_0_5"] = not any(
                    w["probability"] >= 0.5 for w in r["rejected_words"])
            record(name, r, checks)

        r = sem.analyze(tmp / "speech.wav", yamnet, whisper_dir)
        error = wer(TEXT, r["transcript"])
        record("known_speech_clean", r, {
            "speech_fraction_ge_0_70": speech_fraction(r, *speech_span, classes=("speech",)) >= 0.70,
            "wer_le_0_15": error <= 0.15})
        results[-1]["wer"] = round(error, 4)

        for opening in openings:
            music = wav_f32(opening)
            plain = sem.analyze(opening, yamnet)
            mix = music.copy()
            start = int(SPEECH_OFFSET_SECONDS * sem.RATE)
            seg = mix[start:start + len(speech)]
            voiced = speech[:len(seg)]
            music_rms = float(np.sqrt(np.mean(seg ** 2))) or 1e-4
            speech_rms = float(np.sqrt(np.mean(voiced[np.abs(voiced) >= 1e-3] ** 2)))
            gain = music_rms * 10 ** (SPEECH_OVER_MUSIC_DB / 20) / speech_rms
            mix[start:start + len(seg)] = np.clip(seg + gain * voiced, -1, 1)
            write_wav(tmp / "mix.wav", mix)
            r = sem.analyze(tmp / "mix.wav", yamnet, whisper_dir)
            error = wer(TEXT, r["transcript"])
            a, b = speech_span
            name = Path(opening).name.split("-0-40s")[0]
            record(f"speech_over_{name}", r, {
                "wer_le_0_30": error <= 0.30,
                "speech_fraction_ge_0_50": speech_fraction(r, start / sem.RATE + a, start / sem.RATE + b) >= 0.50,
                "plain_opening_music_fraction_ge_0_80": plain["presence_fraction"]["music"] >= 0.80})
            results[-1]["wer"] = round(error, 4)
            results[-1]["plain_opening_presence"] = plain["presence_fraction"]
            results[-1]["plain_opening_top_segments"] = plain["segments"][:6]

    record_out = {"version": "av-semantic-qualification-v1",
                  "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
                  "criteria_sha256": sem.sha256(HERE / "criteria.json"),
                  "semantic_sha256": sem.sha256(HERE / "av_semantic.py"),
                  "yamnet_sha256": sem.sha256(yamnet), "known_text": TEXT,
                  "speech_over_music_db": SPEECH_OVER_MUSIC_DB, "results": results,
                  "provider_calls": 0, "paid_calls": 0,
                  "production_authorized": False, "publication_authorized": False}
    Path(output).write_text(json.dumps(record_out, indent=2) + "\n")
    print(json.dumps({"status": record_out["status"],
                      "cases": [(r["case"], r["status"], r.get("wer")) for r in results]}, indent=1))
    return 0 if record_out["status"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("usage: qualify_semantic.py OUT.json YAMNET WHISPER_DIR [OPENING ...]")
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]))
