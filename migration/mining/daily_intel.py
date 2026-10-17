#!/usr/bin/env python3
"""Living intelligence, market side: today's production directives from the raw
daily panel (market_panel.py). Run once a day after the panel.

1. Fast channels today: activity age <= 45 days and >= 1,000 subscribers (or the
   top subscriber pace), per niche (christian / cross), with their profile.
2. Winning videos: uploads of the last 14 days ranked by views per day since
   publication, Christian niche, with title features, duration and publish hour.
3. Directives: duration band, publish hour, title features and topic terms that
   separate the top quartile from the rest (lift, with counts), derived only
   from today's data and written with their evidence.
usage: daily_intel.py RAW_PANEL_JSON OUT_JSON
"""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import statistics
import sys

STOP = set("the a an of to for and in on with your you my me is are be this that it at from by your our i we he his "
           "god jesus lord prayer pray christ".split())
WORD = re.compile(r"[A-Za-z']{3,}")


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def features(title):
    words = title.split()
    return {"length": len(title), "has_number": bool(re.search(r"\d", title)), "has_pipe": "|" in title,
            "has_colon": ":" in title, "has_emoji": bool(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", title)),
            "caps_words": sum(1 for w in words if len(w) > 2 and w.isupper()),
            "second_person": bool(re.search(r"(?i)\byou(r)?\b", title)),
            "says_prayer": bool(re.search(r"(?i)\bpray", title))}


def lift(top, rest, key):
    a = sum(1 for v in top if v["features"][key]) / len(top) if top else 0
    b = sum(1 for v in rest if v["features"][key]) / len(rest) if rest else 0
    return {"top_share": round(a, 3), "rest_share": round(b, 3), "lift": round(a / b, 2) if b else None}


def main(raw_path, out):
    panel = json.loads(Path(raw_path).read_text())
    now = parse(panel["captured_at"])
    fast, videos = [], []
    for c in panel["channels"]:
        ups = c.get("uploads") or []
        if not ups or c.get("uploads_truncated") or c.get("subscribers") is None:
            continue
        first = min(parse(u["published_at"]) for u in ups)
        activity = max(1, (now - first).days)
        longs = [u for u in ups if (u["duration_seconds"] or 0) > 180]
        profile = {"channel_id": c["channel_id"], "title": c["title"], "niche": c.get("niche", "christian"),
                   "activity_days": activity, "subscribers": c["subscribers"], "subs_per_day": round(c["subscribers"] / activity, 1),
                   "uploads_per_day": round(len(ups) / activity, 2), "short_share": round(1 - len(longs) / len(ups), 2),
                   "median_long_minutes": round(statistics.median(u["duration_seconds"] for u in longs) / 60, 1) if longs else None}
        if activity <= 45 and c["subscribers"] >= 1000:
            fast.append(profile)
        if c.get("niche", "christian") != "christian":
            continue
        for u in ups:
            age_days = (now - parse(u["published_at"])).total_seconds() / 86400
            if 0.5 <= age_days <= 14 and (u["duration_seconds"] or 0) > 180:
                videos.append({"video_id": u["video_id"], "channel_id": c["channel_id"], "channel": c["title"],
                               "title": u["title"], "minutes": round(u["duration_seconds"] / 60, 1),
                               "views": u["views"], "views_per_day": round(u["views"] / age_days, 1),
                               "publish_hour_utc": parse(u["published_at"]).hour, "features": features(u["title"])})
    videos.sort(key=lambda v: v["views_per_day"], reverse=True)
    q = max(1, len(videos) // 4)
    top, rest = videos[:q], videos[q:]
    terms_top = Counter(w.lower() for v in top for w in set(WORD.findall(v["title"])) if w.lower() not in STOP)
    terms_rest = Counter(w.lower() for v in rest for w in set(WORD.findall(v["title"])) if w.lower() not in STOP)
    term_lift = sorted(((t, n, terms_rest.get(t, 0)) for t, n in terms_top.items() if n >= 3),
                       key=lambda x: (x[1] / len(top)) / ((x[2] + 1) / (len(rest) + 1)), reverse=True)[:20]
    directives = {
        "duration_minutes_top_quartile": [round(statistics.quantiles([v["minutes"] for v in top], n=4)[0], 1),
                                          round(statistics.median(v["minutes"] for v in top), 1),
                                          round(statistics.quantiles([v["minutes"] for v in top], n=4)[2], 1)] if len(top) >= 4 else None,
        "publish_hour_utc_top_quartile": Counter(v["publish_hour_utc"] for v in top).most_common(4),
        "title_feature_lift": {k: lift(top, rest, k) for k in features("x")},
        "title_terms_lift": [{"term": t, "top": a, "rest": b} for t, a, b in term_lift],
    }
    fast.sort(key=lambda r: r["subs_per_day"], reverse=True)
    result = {"version": "daily-intel-v1", "panel_captured_at": panel["captured_at"],
              "fast_channels": {"christian": [f for f in fast if f["niche"] == "christian"][:25],
                                "cross_niche": [f for f in fast if f["niche"] != "christian"][:25]},
              "winning_videos_christian_14d": [{k: v[k] for k in v if k != "features"} for v in videos[:30]],
              "videos_considered": len(videos), "directives": directives,
              "scope": "Public data of today's panel. Associations, not causal effects; applied as hypotheses one variable at a time."}
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"fast_christian": len(result["fast_channels"]["christian"]),
                      "fast_cross": len(result["fast_channels"]["cross_niche"]), "videos": len(videos)}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
