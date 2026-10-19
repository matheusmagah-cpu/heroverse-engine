#!/usr/bin/env python3
"""Native window measurements; descriptive estimates are not instrument qualification.

Usage: native_metrics.py PROFILES_DIR LEDGER MEASURED_JSON STRUCTURE_DIR OUT_JSON
Bootstrap units are videos (never windows), using their within-video medians.
All videos are described; only validated winner groups can supply target candidates.
"""
import json
import math
from pathlib import Path
import random
import re
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from accuracy_check import words, records, classify

VERSION = "native-metrics-v1"
SEED = 20261019
RESAMPLES = 2000
METRICS = ("speech_fraction", "music_fraction", "wpm", "you_per_100",
           "kjv_markers_per_min", "picture_changes_per_minute", "integrated_lufs", "agreement")
KJV = frozenset("thou thee thy thine hath doth unto ye shalt saith".split())
NAME = re.compile(r"acq-(.+)-(\d+)-(\d+)-v(\d+)\.json$")


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def window_metrics(video_id, start, end, profile, mined_windows):
    """Measure only this native profile; preserve unknowns and their causes."""
    row = {"video_id": video_id, "start": start, "end": end, "reasons": {}}
    reasons = row["reasons"]
    sound = profile.get("sound_classes") or {}
    presence = sound.get("presence_fraction") or {}
    for key, source in (("speech_fraction", "speech"), ("music_fraction", "music")):
        value = presence.get(source)
        row[key] = value if number(value) and 0 <= value <= 1 else None
        if row[key] is None:
            reasons[key] = "missing or invalid sound_classes.presence_fraction." + source
    transcript = sound.get("transcript")
    asr = words(transcript) if isinstance(transcript, str) else []
    duration = end - start
    spoken = row["speech_fraction"] * duration if row["speech_fraction"] is not None and duration > 0 else None
    for key in ("wpm", "you_per_100", "kjv_markers_per_min"):
        row[key] = None
    if not isinstance(transcript, str):
        for key in ("wpm", "you_per_100", "kjv_markers_per_min"):
            reasons[key] = "missing ASR transcript"
    else:
        if spoken is not None and spoken >= 10:
            row["wpm"] = len(asr) / spoken * 60
        else:
            reasons["wpm"] = "speech duration unknown" if spoken is None else "speech duration below 10 seconds"
        if asr:
            row["you_per_100"] = asr.count("you") / len(asr) * 100
        else:
            reasons["you_per_100"] = "no ASR words; denominator is zero"
        if spoken is not None and spoken > 0:
            row["kjv_markers_per_min"] = sum(w in KJV or w.endswith("eth") for w in asr) / spoken * 60
        else:
            reasons["kjv_markers_per_min"] = "spoken duration unknown or zero"
    for key, section in (("picture_changes_per_minute", "editing"), ("integrated_lufs", "loudness")):
        value = (profile.get(section) or {}).get(key)
        row[key] = value if number(value) else None
        if row[key] is None:
            reasons[key] = "missing or invalid " + section + "." + key
    row["opening_words"] = asr[:20] if start == 0 and isinstance(transcript, str) else None
    if row["opening_words"] is None:
        reasons["opening_words"] = "not an opening window" if start != 0 else "missing ASR transcript"
    comparison = classify(mined_windows, start, end, asr) if isinstance(transcript, str) else {"status": "ASR_MISSING"}
    row["comparison"] = comparison
    row["agreement"] = comparison.get("transcript_agreement") if comparison["status"] == "COMPARED" else None
    if row["agreement"] is None:
        reasons["agreement"] = comparison["status"]
    return row


def percentile(values, fraction):
    """Linearly interpolated percentile of sorted values."""
    pos = (len(values) - 1) * fraction
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def bootstrap(values):
    """Sample median and deterministic central 90% percentile interval, 2,000 video resamples."""
    values = sorted(v for v in values if number(v))
    if not values:
        return {"median": None, "interval_90": None, "n": 0, "reason": "no measured video values"}
    rng = random.Random(SEED)
    samples = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(RESAMPLES))
    return {"median": statistics.median(values), "interval_90": [percentile(samples, .05), percentile(samples, .95)],
            "n": len(values), "reason": None}


def video_summary(video_id, windows, metadata):
    row = {"video_id": video_id, "n_windows": len(windows), "format": metadata.get("format"),
           "role": metadata.get("role"), "reasons": {}}
    for key in METRICS:
        values = [w[key] for w in windows if number(w.get(key))]
        row[key] = statistics.median(values) if values else None
        if not values:
            row["reasons"][key] = "no measured window values"
    for key in ("format", "role"):
        if row[key] is None:
            row["reasons"][key] = "video absent from measured.json" if not metadata else "missing " + key + " in measured.json"
    row["opening_words"] = next((w["opening_words"] for w in windows if w["start"] == 0 and w["opening_words"] is not None), None)
    if row["opening_words"] is None:
        row["reasons"]["opening_words"] = "no measured opening window"
    statuses = [w["comparison"]["status"] for w in windows]
    row["n_compared"] = statuses.count("COMPARED")
    bad = {"MINED_WINDOW_INVALID", "MINED_WINDOW_MISSING", "MINED_OMISSION", "ASR_SILENT_MINED_SPEECH"}
    reason = None
    if len(windows) < 3:
        reason = "FEW_WINDOWS"
    elif row["n_compared"] < 2:
        reason = "FEW_COMPARED"
    elif any(w["comparison"]["status"] == "COMPARED" and w["agreement"] < .85 for w in windows):
        reason = "LOW_AGREEMENT"
    elif any(status in bad for status in statuses):
        reason = "BAD_WINDOW:" + next(status for status in statuses if status in bad)
    row["validated"] = reason is None
    row["validation_reason"] = reason
    return row


def group_summary(videos):
    """Group by unmodified format/role values; missing values remain JSON null."""
    grouped = {}
    for video in videos:
        grouped.setdefault((video["format"], video["role"]), []).append(video)
    out = []
    for (fmt, role), rows in sorted(grouped.items(), key=lambda x: tuple((v is None, str(v)) for v in x[0])):
        validated = sum(r["validated"] for r in rows)
        out.append({"format": fmt, "role": role, "n_videos": len(rows), "n_validated": validated,
                    "status": "MEASURED" if validated >= 8 else "INSUFFICIENT",
                    "reason": None if validated >= 8 else "fewer than 8 validated videos",
                    "measures": {key: bootstrap([r[key] for r in rows]) for key in METRICS}})
    return out


def measure(profiles_dir, ledger_path, measured_path, structure_dir):
    for directory in (profiles_dir, structure_dir):
        if not Path(directory).is_dir():
            raise ValueError("input directory does not exist: " + str(directory))
    ledger = json.loads(Path(ledger_path).read_text())
    metadata = {v["video_id"]: v for v in json.loads(Path(measured_path).read_text())["videos"]}
    recs = records(structure_dir)
    claims = {(c["video_id"], c["start_seconds"], c["end_seconds"]) for c in ledger["claims"]}
    windows, notes, seen = [], [], set()
    for path in sorted(Path(profiles_dir).glob("acq-*.json")):
        match = NAME.fullmatch(path.name)
        if not match:
            notes.append({"profile": path.name, "reason": "invalid acquisition filename"})
            continue
        video_id, start, end = match[1], int(match[2]), int(match[3])
        identity = (video_id, start, end)
        if identity in seen:
            raise ValueError("duplicate native window: " + str(identity))
        seen.add(identity)
        document = json.loads(path.read_text())
        profiles = document.get("profiles") or []
        profile = profiles[0] if profiles else {}
        row = window_metrics(video_id, start, end, profile, (recs.get(video_id) or {}).get("windows", []))
        row["profile"] = path.name
        row["ledger_recorded"] = identity in claims
        if not row["ledger_recorded"]:
            row["reasons"]["ledger_recorded"] = "native window absent from ledger"
        windows.append(row)
    for video_id, start, end in sorted(claims - seen):
        notes.append({"video_id": video_id, "start": start, "end": end, "reason": "ledger window has no native profile; not counted as measured"})
    videos = []
    for video_id in sorted(set(metadata) | set(recs) | {w["video_id"] for w in windows}):
        videos.append(video_summary(video_id, [w for w in windows if w["video_id"] == video_id], metadata.get(video_id, {})))
    return {"version": VERSION, "windows": windows, "videos": videos, "by_format_and_role": group_summary(videos),
            "bootstrap": {"resamples": RESAMPLES, "seed": SEED, "unit": "video", "interval": "central 90% percentile"},
            "notes": notes,
            "scope": "Descriptive native measurements, not instrument qualification. Group statistics include all measured video medians; only validated winners can inform targets."}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 5:
        raise SystemExit("usage: native_metrics.py PROFILES_DIR LEDGER MEASURED_JSON STRUCTURE_DIR OUT_JSON")
    result = measure(*args[:4])
    Path(args[4]).write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(result["by_format_and_role"], ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
