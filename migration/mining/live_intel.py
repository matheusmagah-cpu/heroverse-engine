#!/usr/bin/env python3
"""Live intelligence for the Bible series (owner, 2026-10-24: "we cannot get the live intelligence wrong").

Deterministic, so a verdict never depends on how a stats table was read that day:
1. Each episode record carries its `attributes` (hook type, title pattern, first visual, length, slot, AI scenes...).
2. A stats snapshot (vidIQ, saved under evidence/learning/stats-<day>.json) gives views, likes and comments per video
   and when they were captured.
3. Each episode is compared with the series median AT A SIMILAR AGE (other episodes' snapshots at 0.75-1.33x its age;
   snapshots accumulate in the stats file's history). Under 48 h, or under MIN_VIEWS, the verdict is "inconclusive":
   no change is ever decided on noise.
4. One change at a time: a hypothesis names one attribute and its new value. It is KEPT after KEEP_AFTER consecutive
   episodes carrying it are "good", REVERTED after the same number "bad", otherwise it keeps RUNNING. While one
   hypothesis runs, no other may start (the effect must be attributable).
5. The authenticity layer is never an attribute: KJV text, references, our own reflection and prayer, the AI
   disclosure and no copied scripts are fixed (PROTECTED); a hypothesis touching them is refused.

usage: live_intel.py EPISODES_DIR STATS_JSON STATE_JSON OUT_JSON
"""
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys

AGES = (("2h", 2), ("24h", 24), ("48h", 48), ("7d", 168))
DECIDE_FROM_H = 48
MIN_VIEWS = 100
GOOD, BAD = 1.2, 0.8           # ratio to the series median at the same age
KEEP_AFTER = 2
REQUIRED_ATTRIBUTES = ("hook_type", "title_pattern", "first_visual", "ai_scenes", "seconds", "slot_utc", "transition")
PROTECTED = {"scripture_text", "references", "reflection", "prayer", "ai_disclosure", "script_source"}


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def age_bucket(hours):
    """The largest standard age the video has reached (2 h, 24 h, 48 h, 7 d), or None below 2 h."""
    reached = [name for name, h in AGES if hours >= h]
    return reached[-1] if reached else None


def rows(episodes, stats):
    """One row per published episode with a snapshot: age, bucket, views, like rate."""
    by_id = {v["id"]: v for v in stats["videos"]}
    captured = when(stats["captured_at"])
    out = []
    for ep in episodes:
        v = by_id.get(ep.get("video_id"))
        if not v or not v.get("published_at"):
            continue
        hours = (captured - when(v["published_at"])).total_seconds() / 3600
        views = int(v.get("views") or 0)
        out.append({"id": ep["id"], "part": ep.get("part"), "video_id": v["id"], "age_h": round(hours, 1),
                    "bucket": age_bucket(hours), "views": views,
                    "like_rate": round(int(v.get("likes") or 0) / views, 3) if views else None,
                    "attributes": ep.get("attributes") or {}})
    return sorted(out, key=lambda r: (r["part"] or 0, r["id"]))


AGE_BAND = (0.75, 1.33)        # a 60 h video is compared with others seen at 45-80 h, never with 7-day totals


def baseline(history, age_h, exclude):
    """Series median of views among snapshots of OTHER episodes taken at a similar age (the past included)."""
    lo, hi = age_h * AGE_BAND[0], age_h * AGE_BAND[1]
    vals = [h["views"] for h in history if h["id"] != exclude and lo <= h["age_h"] <= hi]
    return statistics.median(vals) if vals else None


def verdict(row, history):
    if row["age_h"] < DECIDE_FROM_H or row["views"] < MIN_VIEWS and row["age_h"] < AGES[-1][1]:
        return {"verdict": "inconclusive", "reason": f"age {row['age_h']} h / views {row['views']}"}
    med = baseline(history, row["age_h"], row["id"])
    if not med:
        return {"verdict": "inconclusive", "reason": f"no other episode seen at about {row['age_h']} h yet"}
    ratio = round(row["views"] / med, 2)
    v = "good" if ratio >= GOOD else "bad" if ratio <= BAD else "neutral"
    return {"verdict": v, "ratio_to_median": ratio, "median": med, "bucket": row["bucket"]}


def evaluate(hypothesis, judged):
    """KEPT / REVERTED / RUNNING from the episodes that carry the hypothesis' attribute value, in story order."""
    carrying = [j for j in judged if j["attributes"].get(hypothesis["attribute"]) == hypothesis["value"]
                and j["verdict"]["verdict"] != "inconclusive"]
    tail = [j["verdict"]["verdict"] for j in carrying][-KEEP_AFTER:]
    if len(tail) == KEEP_AFTER and all(v == "good" for v in tail):
        return "KEPT"
    if len(tail) == KEEP_AFTER and all(v == "bad" for v in tail):
        return "REVERTED"
    return "RUNNING"


def can_start(hypotheses, new):
    if new["attribute"] in PROTECTED:
        return False, "PROTECTED_AUTHENTICITY_LAYER"
    if any(h.get("status") == "RUNNING" for h in hypotheses):
        return False, "ONE_CHANGE_AT_A_TIME"
    return True, "OK"


def main(episodes_dir, stats_path, state_path, out_path):
    """STATE (evidence/learning/state.json) persists across days: every snapshot ever taken (history) and the
    hypotheses; STATS is today's snapshot; OUT is today's verdict file."""
    episodes = [json.loads(p.read_text()) for p in sorted(Path(episodes_dir).glob("*.json"))]
    stats = json.loads(Path(stats_path).read_text())
    state = json.loads(Path(state_path).read_text()) if Path(state_path).exists() else {"history": [], "hypotheses": []}
    current = rows(episodes, stats)
    judged = [dict(r, verdict=verdict(r, state["history"] + current)) for r in current]
    for h in state["hypotheses"]:
        if h.get("status") == "RUNNING":
            h["status"] = evaluate(h, judged)
    seen = {(h["id"], h["age_h"]) for h in state["history"]}
    state["history"] += [{k: r[k] for k in ("id", "age_h", "views")} for r in current if (r["id"], r["age_h"]) not in seen]
    Path(state_path).write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
    Path(out_path).write_text(json.dumps({"version": "live-intel-v1", "captured_at": stats["captured_at"],
                                          "episodes": judged, "hypotheses": state["hypotheses"]},
                                         indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({j["id"]: j["verdict"]["verdict"] for j in judged}))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
