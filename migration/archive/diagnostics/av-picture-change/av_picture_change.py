#!/usr/bin/env python3
"""Classify the picture changes found by av-event-meter as SCENE (most of the
frame replaced) or LOCAL (caption / text box / overlay over a persistent
picture). Frozen rules in criteria.json. Deterministic, offline."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "av-event-meter"))
import av_event_meter as meter  # noqa: E402

VERSION = "av-picture-change-v1"
PROXY = (96, 54)
GRID = (12, 6)
BEFORE, AFTER = (-0.40, -0.15), (0.15, 0.40)
CELL_DIFF = 12.0
SCENE_FRACTION = 0.45
CENTRE = (slice(1, 5), slice(4, 8))
CENTRE_KEPT_MAX_CHANGED = 0.25


def gray_frames(path):
    info = meter.probe(path)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in video.get("avg_frame_rate", "30/1").split("/"))
    fps = num / den if den else 30.0
    width, height = PROXY
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
                          "-vf", f"scale={width}:{height}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width).astype(np.float32), fps


def window_mean(frames, fps, start, end):
    a, b = max(0, int(round(start * fps))), min(len(frames), int(round(end * fps)) + 1)
    return frames[a:b].mean(0) if b > a else None


def cell_diff(before, after):
    cols, rows = GRID
    h, w = before.shape
    d = np.abs(after - before).reshape(rows, h // rows, cols, w // cols).mean((1, 3))
    return d > CELL_DIFF


def classify_at(frames, fps, t):
    before = window_mean(frames, fps, t + BEFORE[0], t + BEFORE[1])
    after = window_mean(frames, fps, t + AFTER[0], t + AFTER[1])
    if before is None or after is None:
        return {"time": round(t, 3), "kind": "EDGE", "changed_fraction": None}
    changed = cell_diff(before, after)
    fraction = float(changed.mean())
    record = {"time": round(t, 3), "changed_fraction": round(fraction, 3)}
    if fraction >= SCENE_FRACTION:
        record["kind"] = "SCENE"
        record["centre_kept"] = bool(changed[CENTRE].mean() <= CENTRE_KEPT_MAX_CHANGED)
    else:
        record["kind"] = "LOCAL"
        rows, cols = np.nonzero(changed)
        record["region"] = None if not len(rows) else {
            "rows": [int(rows.min()), int(rows.max())], "cols": [int(cols.min()), int(cols.max())]}
    return record


def summarize(changes, duration):
    minutes = duration / 60 if duration else None
    scene = [c for c in changes if c["kind"] == "SCENE"]
    local = [c for c in changes if c["kind"] == "LOCAL"]

    def rate(items):
        return round(len(items) / minutes, 2) if minutes else None

    def median_gap(items):
        times = [0.0] + [c["time"] for c in items] + [duration]
        return round(float(np.median(np.diff(times))), 3)
    return {"changes": len(changes), "scene_changes": len(scene), "local_changes": len(local),
            "scene_changes_per_minute": rate(scene), "local_changes_per_minute": rate(local),
            "median_scene_hold_seconds": median_gap(scene),
            "scene_changes_with_centre_kept": sum(c.get("centre_kept", False) for c in scene),
            "local_region_rows_median": [int(np.median([c["region"]["rows"][i] for c in local if c.get("region")]))
                                         for i in (0, 1)] if any(c.get("region") for c in local) else None}


def analyze(path):
    measured = meter.measure(path)
    duration = float(meter.probe(path)["format"].get("duration") or 0)
    times = [e["onset_seconds"] for e in measured["video"].get("events", [])]
    frames, fps = gray_frames(path)
    changes = [classify_at(frames, fps, t) for t in times]
    return {"version": VERSION, "media_file": Path(path).name, "duration_seconds": round(duration, 3),
            "summary": summarize(changes, duration), "changes": changes,
            "scope": "MEASUREMENTS_OF_THIS_FILE_NOT_QUALITY_OR_AUDIENCE_PREDICTION"}


if __name__ == "__main__":
    print(json.dumps([analyze(p) for p in sys.argv[1:]], indent=1))
