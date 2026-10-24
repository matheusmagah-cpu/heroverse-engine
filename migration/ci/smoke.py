#!/usr/bin/env python3
"""Render smoke test (E68): a ~1 minute cut of a real pilot through the whole render path (voice, footage, assembly,
QA, package, thumbnail) on every PR that touches production code, so a break shows in minutes, not after a 2.5 h render.

usage: smoke.py script PILOT_SCRIPT OUT_SCRIPT     keep the first two segments, the first Scripture segment and the last
       smoke.py verdict WORK_DIR                   fail on a missing output or a QA failure other than the length rules
"""
import json
import sys
from pathlib import Path

# the cut is short by design: only the rules about the full length may fail
LENGTH_ONLY = {"duration_min"}


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
        checks = json.loads((work / "qa.json").read_text()).get("checks", {})
        problems += [f"QA_FAIL {k}" for k, ok in checks.items() if not ok and k not in LENGTH_ONLY]
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
