#!/usr/bin/env python3
"""Choose a pilot's footage from the vetted library (pilot-qa-criteria-v4), so new pilots need no hand picking.

Night scripts take night themes and morning scripts take daylight themes (water and clouds fit both); a night clip must
also be dark (E69: themes alone let sunlit waterfalls and snowy peaks into the 008 night prayer). Clips are
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
    # E71: snow, waterfall, mist, clouds, ocean, lake and sunset clips are shot by day; even with a dark mean their sky
    # reads as daylight in a night prayer, so night takes only themes that are night by nature (and dark, E69);
    # E76: river too (a dark autumn creek filmed by day reached the 013 night preview)
    "night": ["candle", "night", "rain"],
    "morning": ["sunrise", "clouds", "meadow", "forest", "field", "grass", "river", "waterfall", "lake", "ocean", "mist", "snow"],
}


NIGHT_LUMA_MAX = 80   # mean luma (0-255) of the vetting frames; the 008 daylight clips measured 82-166


def luma(rec):
    vals = rec.get("vetting_luma") or []
    return sum(vals) / len(vals) if vals else None


def mood(script):
    return "night" if re.search(r"(?i)night|sleep|bedtime", script.get("working_title", "")) else "morning"


def usable(rec):
    return (rec.get("vetting") == "APPROVED" and rec.get("licence") in FOOTAGE_LICENCES and rec.get("release_asset")
            and rec.get("frame") == [2560, 1440])   # v4 frame: >= 1440p (1080p clips of the first library are not)


def seen(rec):
    """E74: a clip Claude has looked at on a preview footage sheet (all three frames) and kept."""
    return bool(rec.get("claude_seen"))


def choose(script, library, n=None, turn=0):
    """Clips Claude has already seen first: once the seen clips of the mood reach FOOTAGE_MIN, only they are used, so a
    reassignment never brings unseen clips into a preview again (E74: every reassignment of 011 added new modern clips)."""
    seen_lib = [r for r in library if seen(r)]
    try:
        return _choose(script, seen_lib, n, turn)
    except SystemExit:
        return _choose(script, library, n, turn)


def _choose(script, library, n=None, turn=0):
    """turn rotates the theme order and each theme's clips, so pilots of the same mood open on different
    footage and never share a shot order."""
    night = mood(script) == "night"
    themes = MOOD_THEMES[mood(script)]
    anchors, rest = themes[:2], themes[2:]   # the hook shot comes from the mood's own themes (candle/night, sunrise/clouds)
    themes = anchors[turn % 2:] + anchors[:turn % 2] + rest[turn % len(rest):] + rest[:turn % len(rest)]
    by_theme = {}
    for t in themes:
        ids = sorted(r["id"] for r in library if r.get("theme") == t and usable(r)
                     and (not night or (luma(r) is not None and luma(r) <= NIGHT_LUMA_MAX)))
        k = turn % len(ids) if ids else 0
        by_theme[t] = ids[k:] + ids[:k]
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
    turn = int(re.sub(r"\D", "", d.name) or 0)
    script["footage"] = choose(script, library, turn=turn)
    indent = len(raw.split("\n")[1]) - len(raw.split("\n")[1].lstrip())
    path.write_text(json.dumps(script, indent=indent or 1, ensure_ascii=False) + "\n")
    print(json.dumps({"pilot": d.name, "mood": mood(script), "footage": len(script["footage"])}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
