#!/usr/bin/env python3
"""Measured blueprint from structure records (code, not model opinion).

Groups videos by format (prayer / teaching) and role (winner / latest /
weak_contrast) and reports, per group, the medians of every measured field plus
the beat map: which beat types happen in each part of the video (first 15 s,
15-60 s, 1-3 min, middle, last 10%), how long they last, and the opening words
of the first beats (verbatim, as heard). Only records with >= 90% coverage, narration
(>= 40 wpm) and policy-clean sources count toward targets; the others are listed with the reason.
usage: blueprint_stats.py STRUCTURE_DIR OUT_JSON
"""
import glob
import json
from pathlib import Path
import re
import statistics
import sys

PRAYER = re.compile(r"(?i)\b(prayer|pray|praying|blessing|declaration|psalm 91)\b")
# sources whose growth rests on someone else's identity or recordings: never targets (impersonation / reused content)
BORROWED = re.compile(r"(?i)\b(apostle|pastor|bishop|prophet|evangelist|billy graham|fulton sheen|joshua selman|"
                      r"t\.?d\.? jakes|joel osteen|charles stanley|myles munroe)\b")
# narrated formats only: a channel whose uploads carry almost no speech (livestreams, ASMR) is off-format
MIN_WPM = 40
PHASES = (("first_15s", 0, 15), ("15_60s", 15, 60), ("1_3min", 60, 180))


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def phase_of(t, total):
    for name, a, b in PHASES:
        if a <= t < b:
            return name
    return "last_10pct" if t >= 0.9 * total else "middle"


def video_row(r):
    v, m = r["video"], r["measured"] or {}
    sp = m.get("speech") or {}
    beats = [b for w in r["windows"] for b in w["beats"]]
    thumb = r.get("thumbnail_analysis") or {}
    borrowed = bool(BORROWED.search(v["title"] + " " + v["description"][:600] + " " + str(thumb.get("text_on_thumbnail", ""))))
    return {
        "video_id": v["video_id"], "channel": v["channel"], "role": v.get("role"), "title": v["title"],
        "format": "prayer" if PRAYER.search(v["title"]) else "teaching", "views": v["views"],
        "coverage": m.get("coverage_fraction"), "policy_clean": not borrowed,
        "minutes": m.get("minutes"), "title_words": m.get("title_words"), "title_upper_ratio": round(
            sum(c.isupper() for c in v["title"]) / max(1, sum(c.isalpha() for c in v["title"])), 2),
        "chapters": m.get("chapters"), "likes_per_1k": m.get("likes_per_1k_views"), "comments_per_1k": m.get("comments_per_1k_views"),
        "wpm": sp.get("words_per_minute"), "sentence_words": sp.get("sentence_words_median"),
        "you_per_100": sp.get("you_per_100_words"), "questions_per_min": sp.get("questions_per_minute"),
        "shots_per_min": m.get("shots_per_minute_model_counted"), "beats_per_min": m.get("beats_per_minute"),
        "beat_seconds": m.get("beat_seconds_median"), "scripture_per_10min": m.get("scripture_per_10_min"),
        "thumb_words": thumb.get("words"), "thumb_faces": thumb.get("faces"), "thumb_text": thumb.get("text_on_thumbnail"),
        "first_15s": sp.get("first_15s_words"),
        "opening_beats": [{"t": b["start_seconds"], "beat": b["beat"], "words": b["opening_words_verbatim"], "device": b["device"]}
                          for b in beats if b["start_seconds"] < 180],
        "beat_phases": {p: [b["beat"] for b in beats if phase_of(b["start_seconds"], v["seconds"]) == p]
                        for p in ("first_15s", "15_60s", "1_3min", "middle", "last_10pct")},
        "picture": [w["picture"] for w in r["windows"][:2]], "sound": [w["sound"] for w in r["windows"][:1]],
    }


def summarize(rows):
    keys = ("minutes", "wpm", "sentence_words", "you_per_100", "questions_per_min", "shots_per_min", "beats_per_min",
            "beat_seconds", "scripture_per_10min", "title_words", "title_upper_ratio", "chapters", "likes_per_1k",
            "comments_per_1k", "thumb_words", "thumb_faces")
    out = {k: med([r[k] for r in rows]) for k in keys}
    out["n"] = len(rows)
    out["videos"] = [r["video_id"] for r in rows]
    phase_mix = {}
    for p in ("first_15s", "15_60s", "1_3min", "middle", "last_10pct"):
        counts = {}
        for r in rows:
            for b in r["beat_phases"][p]:
                counts[b] = counts.get(b, 0) + 1
        total = sum(counts.values()) or 1
        phase_mix[p] = {k: round(c / total, 2) for k, c in sorted(counts.items(), key=lambda x: -x[1])[:6]}
    out["beat_mix_by_phase"] = phase_mix
    return out


def main(structure_dir, out_path):
    rows = [video_row(json.load(open(f))) for f in sorted(glob.glob(str(Path(structure_dir) / "structure-*.json")))]
    def reason(r):
        if not r["policy_clean"]:
            return "borrowed identity or recordings (policy)"
        if (r["coverage"] or 0) < 0.9:
            return f"coverage {r['coverage']}"
        if (r["wpm"] or 0) < MIN_WPM:
            return f"no narration ({r['wpm']} wpm): off-format"
        return None
    usable = [r for r in rows if reason(r) is None]
    excluded = [{"video_id": r["video_id"], "channel": r["channel"], "reason": reason(r)} for r in rows if reason(r)]
    groups = {}
    for r in usable:
        groups.setdefault(r["format"], {}).setdefault(r["role"], []).append(r)
    result = {"version": "blueprint-stats-v1", "source": str(structure_dir), "usable": len(usable), "excluded": excluded,
              "by_format": {f: {role: summarize(rs) for role, rs in g.items()} for f, g in groups.items()},
              "videos": rows}
    Path(out_path).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    for f, g in result["by_format"].items():
        for role, s in g.items():
            print(f, role, {k: s[k] for k in ("n", "minutes", "wpm", "shots_per_min", "beats_per_min", "you_per_100", "thumb_words", "likes_per_1k")})
    print("excluded:", excluded)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
