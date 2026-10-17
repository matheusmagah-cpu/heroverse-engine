#!/usr/bin/env python3
"""Market-only model of time-to-YPP for English Christian channels.

Input: one or more compact market panels (market_panel.py). For every channel
whose recent uploads were fetched and whose upload sample is complete, the
"activity age" is the time since its first public upload (channel creation
date is misleading: many channels are old accounts started recently).

Eligibility proxy (public data only, never a claim of approval):
  LONG route : subscribers >= 1000 and public long-form hours >= 4000, where
               hours = sum(views x duration) x r, r = average fraction watched.
               r is unknown for other channels, so three scenarios are kept:
               r = 0.20 (low), 0.30 (mid), 0.45 (high).
  SHORTS route: subscribers >= 1000 and Shorts views >= 10M (lifetime of a
               channel younger than 90 days, so within the 90-day window).
Output: cross-sectional share of channels already over the proxy by activity
age band, with Wilson 90% intervals, and the profile (cadence, Shorts share,
long duration, dependence on one hit) of fast vs slow channels.
usage: ypp_market_model.py OUT_JSON PANEL_JSON...
"""
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys

RETENTION_SCENARIOS = {"low": 0.20, "mid": 0.30, "high": 0.45}
AGE_BANDS = ((0, 30), (31, 60), (61, 90), (91, 180), (181, 365))
Z90 = 1.645


def wilson(k, n, z=Z90):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def channel_rows(panel):
    captured = parse(panel["captured_at"])
    rows = []
    for c in panel["channels"]:
        s = c.get("sample")
        if not s or s.get("truncated") or c.get("subscribers") is None:
            continue
        activity_days = max(1, (captured - parse(s["first_upload"])).days)
        row = {"channel_id": c["channel_id"], "title": c["title"], "activity_days": activity_days,
               "subscribers": c["subscribers"], "videos": s["videos"], "long_videos": s["long_videos"],
               "short_videos": s["short_videos"], "long_views": s["long_views"], "short_views": s["short_views"],
               "uploads_per_day": round(s["videos"] / activity_days, 3),
               "short_share": round(s["short_videos"] / s["videos"], 3) if s["videos"] else None,
               "median_long_seconds": s["median_long_seconds"],
               "top_share": round(s["top_video_views"] / max(1, s["long_views"] + s["short_views"]), 3),
               "queries": c.get("discovery_queries"), "subs_per_day": round(c["subscribers"] / activity_days, 2)}
        for name, r in RETENTION_SCENARIOS.items():
            hours = s["long_view_hours_if_full"] * r
            row[f"long_hours_{name}"] = round(hours, 1)
            row[f"eligible_long_{name}"] = c["subscribers"] >= 1000 and hours >= 4000
        row["eligible_shorts"] = c["subscribers"] >= 1000 and activity_days <= 90 and s["short_views"] >= 10_000_000
        rows.append(row)
    return rows


def profile(rows):
    if not rows:
        return None

    def med(key):
        values = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.median(values), 3) if values else None
    return {"channels": len(rows), "median_uploads_per_day": med("uploads_per_day"), "median_short_share": med("short_share"),
            "median_long_seconds": med("median_long_seconds"), "median_top_video_share": med("top_share"),
            "median_subscribers": med("subscribers"), "median_subs_per_day": med("subs_per_day")}


def model(rows):
    bands = []
    for lo, hi in AGE_BANDS:
        group = [r for r in rows if lo <= r["activity_days"] <= hi]
        band = {"activity_days": [lo, hi], "channels": len(group)}
        for name in RETENTION_SCENARIOS:
            k = sum(r[f"eligible_long_{name}"] or r["eligible_shorts"] for r in group)
            band[f"eligible_{name}"] = {"k": k, "share": round(k / len(group), 4) if group else None,
                                        "wilson90": wilson(k, len(group))}
        band["subs_1000"] = {"k": sum(r["subscribers"] >= 1000 for r in group),
                             "wilson90": wilson(sum(r["subscribers"] >= 1000 for r in group), len(group))}
        bands.append(band)
    fast = [r for r in rows if r["activity_days"] <= 90 and (r["eligible_long_mid"] or r["eligible_shorts"])]
    slow = [r for r in rows if r["activity_days"] <= 90 and not (r["eligible_long_mid"] or r["eligible_shorts"])]
    return {"bands": bands, "fast_le_90d_profile": profile(fast), "rest_le_90d_profile": profile(slow),
            "fast_le_90d_channels": sorted(fast, key=lambda r: r["activity_days"])}


def main(out, paths):
    panels = [json.loads(Path(p).read_text()) for p in paths]
    latest = max(panels, key=lambda p: p["captured_at"])
    rows = channel_rows(latest)
    result = {"version": "ypp-market-model-v1", "panel_captured_at": latest["captured_at"],
              "channels_in_panel": len(latest["channels"]), "channels_modelled": len(rows),
              "retention_scenarios": RETENTION_SCENARIOS, **model(rows),
              "limits": ["Public statistics only: real watch hours, retention, CTR, monetization status and RPM of other "
                         "channels are unknown; eligibility is a proxy under stated retention scenarios.",
                         "Cross-sectional: share of channels of a given activity age already over the proxy, not a "
                         "followed cohort. Daily panels add trajectories.",
                         "Discovery requires an upload in the last 30 days that search returns; channels that "
                         "stopped or were removed are missing (survivorship).",
                         "Upload samples are the most recent 50-200 videos; channels with longer histories are "
                         "excluded from activity-age bands (marked truncated)."]}
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k] for k in ("channels_in_panel", "channels_modelled")}))
    for b in result["bands"]:
        print(b["activity_days"], b["channels"], b["eligible_low"]["share"], b["eligible_mid"]["share"], b["eligible_high"]["share"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
