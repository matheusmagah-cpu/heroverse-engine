#!/usr/bin/env python3
"""Market opportunity report from the preserved official observer snapshots.

Public YouTube Data API metadata only. For every video seen in two or more
captures, growth is measured as views gained per day between captures (not
lifetime views/day). Cohorts are formed within the same channel and duration
stratum, as the monetization decision requires: winner = top third, weak =
bottom third by interval growth. Title vocabulary of winners versus weak
videos is compared as a hypothesis source, not a causal claim. Nothing here
is CTR, retention, revenue or a forecast for HeroVerse.
"""
from collections import Counter, defaultdict
import datetime as dt
import glob
import json
from pathlib import Path
import re
import statistics
import sys

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"
MIN_INTERVAL_HOURS = 20
STOP = set("""a an the and or of to in on for with your you my me i is are be at by from this that it
as we our us his her he she they them their what how why who when all into not no do does
will can just more most very so if but about up out new full hour hours minutes minute min
1 2 3 4 5 6 7 8 9 10 12 24 30 60 hr hrs""".split())
STRATA = ("181_600_SECONDS", "601_1800_SECONDS", "1801_3600_SECONDS", "3601_PLUS_SECONDS")


def parse_time(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_snapshots(pattern=str(EVIDENCE / "observer-[0-9]*.json")):
    series = defaultdict(list)
    meta = {}
    for path in sorted(glob.glob(pattern)):
        record = json.loads(Path(path).read_text())
        for row in record.get("market_snapshots", []):
            if row.get("entity_type") != "VIDEO":
                continue
            p = row["payload"]
            if p.get("view_count") is None or p.get("duration_seconds") is None:
                continue
            series[row["entity_id"]].append((parse_time(row["captured_at"]), int(p["view_count"])))
            meta[row["entity_id"]] = {"title": p.get("title", ""), "channel_id": p.get("channel_id_public"),
                                      "duration_seconds": p["duration_seconds"],
                                      "published": dt.datetime.fromtimestamp(p["timestamp"], dt.timezone.utc),
                                      "stratum": p.get("duration_stratum"),
                                      "language": p.get("default_audio_language")}
    return series, meta


def growth(points):
    points = sorted(set(points))
    first, last = points[0], points[-1]
    hours = (last[0] - first[0]).total_seconds() / 3600
    if hours < MIN_INTERVAL_HOURS:
        return None
    rate = (last[1] - first[1]) / (hours / 24)
    accel = None
    if len(points) >= 3:
        mid = points[len(points) // 2]
        h1 = (mid[0] - first[0]).total_seconds() / 3600
        h2 = (last[0] - mid[0]).total_seconds() / 3600
        if h1 >= 6 and h2 >= 6:
            r1 = (mid[1] - first[1]) / (h1 / 24)
            r2 = (last[1] - mid[1]) / (h2 / 24)
            accel = round(r2 - r1, 1)
    return {"views_per_day_interval": round(rate, 1), "interval_hours": round(hours, 1),
            "captures": len(points), "acceleration_views_per_day": accel, "last_views": last[1],
            "last_capture": last[0]}


def tokens(title):
    return {w for w in re.findall(r"[a-z']+", title.lower()) if w not in STOP and len(w) > 2}


def report(series, meta):
    rows = []
    for vid, points in series.items():
        g = growth(points)
        m = meta[vid]
        if not g or m["stratum"] not in STRATA:
            continue
        age = (g["last_capture"] - m["published"]).total_seconds() / 86400
        rows.append({"video_id": vid, **m, **g, "age_days": round(age, 1)})
    groups = defaultdict(list)
    for r in rows:
        groups[(r["channel_id"], r["stratum"])].append(r)
    for members in groups.values():
        members.sort(key=lambda r: r["views_per_day_interval"], reverse=True)
        n = len(members)
        for i, r in enumerate(members):
            r["cohort"] = ("WINNER" if i < n / 3 else "WEAK" if i >= 2 * n / 3 else "MEDIAN") if n >= 3 else "INSUFFICIENT_GROUP"
    strata = {}
    for s in STRATA:
        subset = [r for r in rows if r["stratum"] == s]
        if not subset:
            continue
        rates = [r["views_per_day_interval"] for r in subset]
        strata[s] = {"videos": len(subset), "channels": len({r["channel_id"] for r in subset}),
                     "median_views_per_day": round(statistics.median(rates), 1),
                     "p90_views_per_day": round(sorted(rates)[int(0.9 * (len(rates) - 1))], 1),
                     "share_recent_30d": round(sum(r["age_days"] <= 30 for r in subset) / len(subset), 2),
                     "top": [{k: r[k] for k in ("video_id", "title", "channel_id", "views_per_day_interval",
                                                "age_days", "acceleration_views_per_day")}
                             for r in sorted(subset, key=lambda r: -r["views_per_day_interval"])[:5]]}
    winners = [r for r in rows if r.get("cohort") == "WINNER"]
    weak = [r for r in rows if r.get("cohort") == "WEAK"]
    wc, kc = Counter(), Counter()
    for r in winners:
        wc.update(tokens(r["title"]))
    for r in weak:
        kc.update(tokens(r["title"]))
    lift = []
    for word, count in wc.items():
        if count >= 4:
            share_w, share_k = count / len(winners), (kc[word] + 1) / (len(weak) + 2)
            lift.append({"word": word, "winner_titles": count, "weak_titles": kc[word],
                         "lift": round(share_w / share_k, 2)})
    lift.sort(key=lambda x: -x["lift"])
    return rows, {"version": "market-opportunity-v1",
                  "cutoff": max(r["last_capture"] for r in rows).isoformat(),
                  "videos_with_interval_growth": len(rows),
                  "channels": len({r["channel_id"] for r in rows}),
                  "strata": strata,
                  "cohort_counts": Counter(r.get("cohort") for r in rows),
                  "title_terms_winner_vs_weak": lift[:15],
                  "limitations": [
                      "Public view counts only; CTR, retention, revenue and subscribers gained are UNKNOWN for other channels.",
                      "Interval growth over about two days is descriptive; it is not a forecast.",
                      "Reference channels were pre-selected for a prayer/worship music hypothesis; this is not a whole-market sample.",
                      "Title-term lift is a hypothesis source, not a causal effect."]}


def acquisition_plan(rows, stratum="601_1800_SECONDS", per_channel=3, already=()):
    """Winner, median and weak per channel in the stratum: opening window first."""
    plan = []
    by_channel = defaultdict(dict)
    for r in rows:
        if r["stratum"] == stratum and r.get("cohort") in ("WINNER", "MEDIAN", "WEAK"):
            current = by_channel[r["channel_id"]].get(r["cohort"])
            if current is None or r["views_per_day_interval"] > current["views_per_day_interval"]:
                by_channel[r["channel_id"]][r["cohort"]] = r
    for channel, cohorts in by_channel.items():
        for kind in ("WINNER", "MEDIAN", "WEAK")[:per_channel]:
            r = cohorts.get(kind)
            if r and (r["video_id"], 0, 40) not in already:
                plan.append({"video_id": r["video_id"], "start": 0, "end": 40, "cohort": kind,
                             "channel_id": channel, "views_per_day_interval": r["views_per_day_interval"],
                             "title": r["title"]})
    return plan


def main(out):
    series, meta = load_snapshots()
    rows, summary = report(series, meta)
    summary["cohort_counts"] = dict(summary["cohort_counts"])
    acquired = {("BeFOHnncaeQ", 0, 40), ("j2rk8ycXe3c", 0, 40), ("VA3qvxoZr4Q", 0, 40),
                ("EkT0XMVln3s", 0, 40), ("ksMAEHpzkZo", 0, 40)}
    summary["acquisition_plan_10_30_min"] = acquisition_plan(rows, already=acquired)
    Path(out).write_text(json.dumps(summary, indent=1, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in ("cutoff", "videos_with_interval_growth", "channels", "cohort_counts")},
                     default=str))
    for s, v in summary["strata"].items():
        print(s, {k: v[k] for k in ("videos", "channels", "median_views_per_day", "p90_views_per_day", "share_recent_30d")})
    print("terms", [(t["word"], t["lift"]) for t in summary["title_terms_winner_vs_weak"][:10]])
    print("plan", len(summary["acquisition_plan_10_30_min"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout")
