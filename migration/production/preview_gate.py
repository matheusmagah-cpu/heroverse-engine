#!/usr/bin/env python3
"""Preview before the full render (owner, 2026-10-24: "the structure must already produce only 9.5 and up").

A full long render takes about 2.5 h; 008 v2 spent one to learn its footage still showed daylight (E71). Now every
script is first previewed (~15 min): the opening rendered for real, every assigned footage clip on one sheet, and the
thumbnail. Claude reviews the preview against the same rubric (ops/CLAUDE_REVIEW.md) and records
inspection/preview_review.json bound to the script's hash. The full render refuses to start without a review of the
current script at the owner's floor, so a script can only reach the long render once it is built for 9.5.

usage: preview_gate.py cut PILOT_SCRIPT OUT_SCRIPT   the opening segments (+ the first Scripture), all footage kept
       preview_gate.py gate PILOT_DIR                exit 1 PREVIEW_REVIEW_REQUIRED unless the current script passed
       preview_gate.py record PILOT_DIR RUN_LABEL    write inspection/preview/preview.json for the current script
"""
import hashlib
import json
from pathlib import Path
import sys

FLOOR = 9.5          # the owner's overall floor
OPENING_SEGMENTS = 4  # hook, roadmap, invitation and the first Scripture: the first ~60 s, where viewers decide


def script_sha(pilot_dir):
    return hashlib.sha256((Path(pilot_dir) / "script.json").read_bytes()).hexdigest()


def _json(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def cut(script):
    """The opening as the viewer meets it; footage stays complete so the footage sheet shows every clip."""
    segs = script["segments"]
    keep = segs[:OPENING_SEGMENTS]
    if not any(s.get("reference") for s in keep):
        keep += [s for s in segs[OPENING_SEGMENTS:] if s.get("reference")][:1]
    return dict(script, segments=keep, pilot_id=script.get("pilot_id", "pilot") + "-preview")


def previewed(pilot_dir):
    """A preview of the current script exists (built, maybe not yet reviewed)."""
    return _json(Path(pilot_dir) / "inspection" / "preview" / "preview.json").get("script_sha256") == script_sha(pilot_dir)


def review(pilot_dir):
    r = _json(Path(pilot_dir) / "inspection" / "preview_review.json")
    return r if r.get("script_sha256") == script_sha(pilot_dir) else {}


def approved(pilot_dir):
    r = review(pilot_dir)
    try:
        return float(r.get("overall")) >= FLOOR
    except (TypeError, ValueError):
        return False


def main(argv):
    if argv[0] == "cut":
        Path(argv[2]).write_text(json.dumps(cut(json.loads(Path(argv[1]).read_text())), ensure_ascii=False))
    elif argv[0] == "gate":
        if not approved(argv[1]):
            r = review(argv[1])
            print("PREVIEW_REVIEW_REQUIRED" if not r else f"PREVIEW_BELOW_FLOOR {r.get('overall')}")
            return 1
        print("PREVIEW_APPROVED")
    elif argv[0] == "record":
        d = Path(argv[1])
        script = json.loads((d / "script.json").read_text())
        out = d / "inspection" / "preview"
        out.mkdir(parents=True, exist_ok=True)
        (out / "preview.json").write_text(json.dumps(
            {"version": "preview-v1", "pilot_id": d.name, "script_sha256": script_sha(d), "run": argv[2],
             "footage": script.get("footage") or [],
             "sheets": ["opening-sheet.jpg", "footage-sheet.jpg", "thumbnail.jpg"]}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
