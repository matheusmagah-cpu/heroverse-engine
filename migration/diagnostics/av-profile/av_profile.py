#!/usr/bin/env python3
"""Reference AV profile for mining: rhythm, editing, motion, loudness, colour
and image-sound relation, computed from av-event-meter output plus two small
ffmpeg measurements. Deterministic, offline, no model or provider call.

Every number is a measurement of the file given; none is a quality verdict or
a prediction of audience response.
"""
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "av-event-meter"))
import av_event_meter as meter  # noqa: E402

VERSION = "av-profile-v1"
TEMPO_BPM_RANGE = (50.0, 200.0)
TEMPO_BIN_SECONDS = 0.01
COLOR_PROXY = (32, 18)


def loudness(path):
    """EBU R128 integrated loudness, loudness range and true peak via ffmpeg."""
    err = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-map", "0:a:0",
                          "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    summary = err[err.rfind("Summary:"):]

    def value(label):
        match = re.search(label + r":\s+(-?[\d.]+|-inf)", summary)
        return None if not match or match.group(1) == "-inf" else float(match.group(1))
    return {"integrated_lufs": value("I"), "loudness_range_lu": value("LRA"),
            "true_peak_dbtp": value("Peak")}


def colour(path):
    """Mean brightness, saturation and their spread on a 32x18 RGB proxy."""
    width, height = COLOR_PROXY
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
                          "-vf", f"scale={width}:{height}:flags=area,format=rgb24", "-f", "rawvideo",
                          "pipe:1"], capture_output=True, check=True).stdout
    rgb = np.frombuffer(raw, np.uint8).reshape(-1, height * width, 3).astype(float) / 255
    high, low = rgb.max(2), rgb.min(2)
    saturation = np.where(high > 0, (high - low) / np.maximum(high, 1e-9), 0)
    brightness = rgb @ np.array([0.2126, 0.7152, 0.0722])
    per_frame_b, per_frame_s = brightness.mean(1), saturation.mean(1)
    return {"mean_brightness": round(float(per_frame_b.mean()), 4),
            "brightness_std_over_time": round(float(per_frame_b.std()), 4),
            "mean_saturation": round(float(per_frame_s.mean()), 4),
            "saturation_std_over_time": round(float(per_frame_s.std()), 4)}


def tempo(onsets, duration):
    """Dominant inter-onset periodicity by autocorrelation of an onset impulse
    train; confidence is the autocorrelation peak relative to lag-zero."""
    if len(onsets) < 4:
        return {"bpm": None, "confidence": 0.0, "reason": "fewer than 4 onsets"}
    bins = int(duration / TEMPO_BIN_SECONDS) + 1
    train = np.zeros(bins)
    train[np.minimum(bins - 1, (np.array(onsets) / TEMPO_BIN_SECONDS).astype(int))] = 1
    train = np.convolve(train, np.ones(3), "same")  # +/-10 ms jitter tolerance
    centered = train - train.mean()
    corr = np.correlate(centered, centered, "full")[bins - 1:]
    lo = int(60 / TEMPO_BPM_RANGE[1] / TEMPO_BIN_SECONDS)
    hi = min(len(corr) - 1, int(60 / TEMPO_BPM_RANGE[0] / TEMPO_BIN_SECONDS))
    if hi <= lo or corr[0] <= 0:
        return {"bpm": None, "confidence": 0.0, "reason": "no periodicity range"}
    lag = lo + int(np.argmax(corr[lo:hi + 1]))
    # Parabolic refinement of the peak lag.
    if 0 < lag < len(corr) - 1:
        a, b, c = corr[lag - 1], corr[lag], corr[lag + 1]
        shift = 0.5 * (a - c) / (a - 2 * b + c) if a - 2 * b + c else 0.0
    else:
        shift = 0.0
    period = (lag + shift) * TEMPO_BIN_SECONDS
    return {"bpm": round(60 / period, 2), "confidence": round(float(corr[lag] / corr[0]), 3)}


def cut_on_onset(cuts, onsets, window, duration):
    """Fraction of picture changes with an audio onset within +/-window, and the
    lift over the fraction expected if onsets were placed at random."""
    if not cuts or not onsets or duration <= 0:
        return {"fraction": None, "chance_fraction": None, "lift": None}
    onsets = np.array(sorted(onsets))
    hits = sum(bool(np.any(np.abs(onsets - c) <= window)) for c in cuts)
    chance = 1 - np.exp(-len(onsets) * 2 * window / duration)
    fraction = hits / len(cuts)
    return {"fraction": round(fraction, 3), "chance_fraction": round(float(chance), 3),
            "lift": round(fraction / chance, 2) if chance > 0 else None}


def profile(path, semantic=None):
    path = Path(path)
    measured = meter.measure(path)
    audio, video = measured["audio"], measured["video"]
    duration = float(meter.probe(path)["format"].get("duration") or audio.get("decoded_seconds", 0.0))
    minutes = duration / 60 if duration else None
    onsets = [e["onset_seconds"] for e in audio.get("events", [])]
    cuts = [e["onset_seconds"] for e in video.get("events", [])]
    shots = np.diff([0.0] + cuts + [duration]) if video.get("present") else np.array([])
    result = {
        "version": VERSION, "media_file": path.name, "duration_seconds": round(duration, 3),
        "editing": {
            "picture_changes": len(cuts),
            "picture_changes_per_minute": round(len(cuts) / minutes, 2) if minutes and video.get("present") else None,
            "median_shot_seconds": round(float(np.median(shots)), 3) if len(shots) else None,
            "longest_shot_seconds": round(float(shots.max()), 3) if len(shots) else None,
            "motion_median_top_decile_diff": video.get("diff_median"),
        },
        "rhythm": {
            "audio_onsets": len(onsets),
            "audio_onsets_per_minute": round(len(onsets) / minutes, 2) if minutes and audio.get("present") else None,
            "tempo": tempo(onsets, duration) if audio.get("present") else None,
        },
        "image_sound": {
            "cut_on_audio_onset": cut_on_onset(cuts, onsets, 1 / 30, duration),
            "sync": measured["sync"],
        },
        "loudness": loudness(path) if audio.get("present") else None,
        "colour": colour(path) if video.get("present") else None,
        "meter_version": measured["version"],
        "scope": "MEASUREMENTS_OF_THIS_FILE_NOT_QUALITY_OR_AUDIENCE_PREDICTION",
        "provider_calls": 0,
    }
    if semantic:
        words = semantic.get("words", [])
        result["sound_classes"] = {
            "presence_fraction": semantic["presence_fraction"],
            "label_counts": semantic["label_counts"],
            "words": len(words),
            "words_per_minute": round(len(words) / minutes, 1) if minutes else None,
            "transcript": semantic.get("transcript"),
        }
    return result


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: av_profile.py MEDIA [SEMANTIC_JSON]")
    semantic = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) == 3 else None
    print(json.dumps(profile(sys.argv[1], semantic), indent=1))
