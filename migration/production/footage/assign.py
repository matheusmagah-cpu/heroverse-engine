#!/usr/bin/env python3
"""Choose a pilot's footage from the vetted library (pilot-qa-criteria-v4), so new pilots need no hand picking.

Night scripts take night themes and morning scripts take daylight themes (water and clouds fit both). Clips are
interleaved theme by theme, so consecutive footage scenes change subject; at least script_check.FOOTAGE_MIN.
usage: assign.py PILOT_DIR [LIBRARY_DIR]      (writes script.json["footage"]; prints the choice)
"""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from script_check import FOOTAGE_LICENCES, FOOTAGE_MIN  # noqa: E402

MOOD_THEMES = {
    "night": ["candle", "night", "ocean", "lake", "mist", "rain", "snow", "waterfall", "river", "sunset", "clouds"],
    "morning": ["sunrise", "clouds", "meadow", "forest", "field", "grass", "river", "waterfall", "lake", "ocean", "mist", "snow"],
}


def mood(script):
    return "night" if re.search(r"(?i)night|sleep|bedtime", script.get("working_title", "")) else "morning"


def usable(rec):
    return rec.get("vetting") == "APPROVED" and rec.get("licence") in FOOTAGE_LICENCES and rec.get("release_asset")


def choose(script, library, n=None):
    themes = MOOD_THEMES[mood(script)]
    by_theme = {t: sorted(r["id"] for r in library if r.get("theme") == t and usable(r)) for t in themes}
    out = []
    while any(by_theme.values()):
        for t in themes:
            if by_theme[t]:
                out.append(by_theme[t].pop(0))
    if len(out) < FOOTAGE_MIN:
        raise SystemExit(f"FOOTAGE_SHORTAGE {mood(script)}: {len(out)} vetted clips < {FOOTAGE_MIN}")
    return out[:n] if n else out


def main(pilot_dir, library_dir=None):
    d = Path(pilot_dir)
    lib = Path(library_dir) if library_dir else d.parent / "footage" / "library"
    library = [json.loads(p.read_text()) for p in sorted(lib.glob("clip-*.json"))]
    path = d / "script.json"
    raw = path.read_text()
    script = json.loads(raw)
    script["footage"] = choose(script, library)
    indent = len(raw.split("\n")[1]) - len(raw.split("\n")[1].lstrip())
    path.write_text(json.dumps(script, indent=indent or 1, ensure_ascii=False) + "\n")
    print(json.dumps({"pilot": d.name, "mood": mood(script), "footage": len(script["footage"])}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
