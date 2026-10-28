#!/usr/bin/env python3
"""Render smoke test (E68): a ~1 minute cut of a real pilot through the whole render path (voice, footage, assembly,
QA, package, thumbnail) on every PR that touches production code, so a break shows in minutes, not after a 2.5 h render.

usage: smoke.py script PILOT_SCRIPT OUT_SCRIPT     keep the first two segments, the first Scripture segment and the last
       smoke.py verdict WORK_DIR                   fail on a missing output or a QA failure other than the length rules
"""
import json
import sys
from pathlib import Path

# the cut is short by design: only the rules about the full length may fail. speech_presence is one: the opening and
# closing music tails are a fixed few seconds, a large share of a 1-minute cut (0.79 on the first smoke) and a small
# share of a 16-minute render (0.857 on 008); the real render still needs 0.85
LENGTH_ONLY = {"duration_min", "speech_presence"}
# qa_pilot.main emits these for every grammar/version. A partial or malformed report is not evidence that a
# render passed. Grammar-specific rows remain mandatory when emitted, including UNKNOWN/None values.
CORE_CHECKS = {"full_decode_without_errors", "video_format", "duration_min", "integrated_lufs", "true_peak",
               "speech_presence", "no_singing", "wer_vs_script", "words_per_minute", "first_word_onset",
               "hook_second_person", "music_owned", "voice_model_pinned"}


def qa_problems(path):
    try:
        report = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ["QA_UNREADABLE"]
    if not isinstance(report, dict) or report.get("version") != "pilot-qa-v1":
        return ["QA_INVALID_REPORT"]
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks:
        return ["QA_MISSING_CHECKS"]
    problems = [f"QA_MISSING {k}" for k in sorted(CORE_CHECKS - checks.keys())]
    # The real shortened render is normally FAIL because of duration/presence. Its aggregate status must still
    # agree with its measurements; only a measured boolean False in the two length rows can be forgiven.
    expected = "PASS" if all(v is True for v in checks.values()) else "FAIL"
    if report.get("status") != expected:
        problems.append("QA_STATUS_MISMATCH")
    for key, value in checks.items():
        if type(value) is not bool:
            problems.append(f"QA_UNKNOWN {key}")
        elif value is False and key not in LENGTH_ONLY:
            problems.append(f"QA_FAIL {key}")
    return problems


def cut(script):
    segs = script["segments"]
    keep = segs[:2] + [s for s in segs[2:-1] if s.get("reference")][:1] + segs[-1:]
    out = dict(script, segments=keep)
    out["pilot_id"] = script.get("pilot_id", "pilot") + "-smoke"
    return out


def verdict(work):
    work = Path(work)
    problems = []
    for f in ("pilot.mp4", "manifest.json", "qa.json", "package/package.json", "package/thumbnail.jpg",
              "package/thumbnail_check.json"):
        if not (work / f).exists():
            problems.append(f"MISSING {f}")
    if (work / "qa.json").exists():
        problems += qa_problems(work / "qa.json")
    if (work / "package/thumbnail_check.json").exists():
        tc = json.loads((work / "package/thumbnail_check.json").read_text())
        if tc.get("status") != "PASS":
            problems.append(f"THUMBNAIL {tc.get('fails')}")
    return problems


def main(argv):
    if argv[0] == "script":
        Path(argv[2]).write_text(json.dumps(cut(json.loads(Path(argv[1]).read_text())), ensure_ascii=False))
        return 0
    problems = verdict(argv[1])
    print(json.dumps({"smoke": "FAIL" if problems else "PASS", "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
