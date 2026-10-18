#!/usr/bin/env python3
"""Whole-file signal scan of a render, every frame and every audio sample (ffmpeg detectors). It complements
the watched review, which samples pictures at 0.5 frames/s and can miss a short defect.

Criteria fixed 2026-10-18 before any render was scanned (SCAN_CRITERIA). The first and last EDGE_S seconds are
excluded (title fade-in and closing fade-out are intended). Blocking rows: black picture >= 0.5 s, digital
silence (< -60 dB) >= 3 s; our renders always carry a music bed, so neither occurs in a correct file. Frozen
picture is reported only until it is calibrated on known-good renders (slow camera moves can look frozen).
usage: signal_scan.py VIDEO_MP4 OUT_JSON   (exit 0 when no blocking row fails)
"""
import json
import re
import subprocess
import sys

VERSION = "signal-scan-v1"
EDGE_S = 2.0
SCAN_CRITERIA = {"black_max_s": 0.5, "black_pic_th": 0.98, "silence_max_s": 3.0, "silence_db": -60,
                 "freeze_report_s": 5.0, "freeze_noise": 0.003}


def duration(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def events(log, start_key, end_key):
    starts = [float(x) for x in re.findall(start_key + r"[:=]\s*(-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(end_key + r"[:=]\s*(-?[\d.]+)", log)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def scan(video):
    c = SCAN_CRITERIA
    total = duration(video)
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", video,
                          "-vf", f"blackdetect=d=0.1:pic_th={c['black_pic_th']},freezedetect=n={c['freeze_noise']}:d=1",
                          "-af", f"silencedetect=n={c['silence_db']}dB:d=0.5", "-f", "null", "-"],
                         capture_output=True, text=True).stderr

    def inner(spans):
        out = []
        for a, b in spans:
            b = total if b is None else b
            a, b = max(a, EDGE_S), min(b, total - EDGE_S)
            if b > a:
                out.append((round(a, 2), round(b, 2), round(b - a, 2)))
        return out
    black = inner(events(log, "black_start", "black_end"))
    silence = inner(events(log, "silence_start", "silence_end"))
    freeze = inner(events(log, "freeze_start", "freeze_end"))
    longest = lambda spans: max((s[2] for s in spans), default=0.0)
    rows = {"black_picture": {"longest_s": longest(black), "max_s": c["black_max_s"], "blocking": True,
                              "pass": longest(black) < c["black_max_s"], "spans": black[:20]},
            "digital_silence": {"longest_s": longest(silence), "max_s": c["silence_max_s"], "blocking": True,
                                "pass": longest(silence) < c["silence_max_s"], "spans": silence[:20]},
            "frozen_picture": {"longest_s": longest(freeze), "report_s": c["freeze_report_s"], "blocking": False,
                               "inside": longest(freeze) < c["freeze_report_s"], "spans": freeze[:20]}}
    status = "PASS" if all(r["pass"] for r in rows.values() if r["blocking"]) else "FAIL"
    return {"version": VERSION, "criteria": c, "edge_excluded_s": EDGE_S, "duration_s": round(total, 2),
            "status": status, "rows": rows}


def main(video, out_json):
    try:
        r = scan(video)
    except Exception as e:  # a scan that could not run is missing evidence, never a pass
        r = {"version": VERSION, "status": "ERROR", "error": f"{type(e).__name__}: {e}"[:300]}
    open(out_json, "w").write(json.dumps(r, indent=1) + "\n")
    print(json.dumps({k: r.get(k) for k in ("status", "error") if k in r} |
                     {k: v.get("longest_s") for k, v in r.get("rows", {}).items()}))
    return 0 if r["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
