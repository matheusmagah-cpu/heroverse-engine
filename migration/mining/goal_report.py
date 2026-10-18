#!/usr/bin/env python3
"""Daily goal report: where the channel stands against the YouTube Partner
Program, how fast it must move to qualify by day 14 (30 at most), how the
published videos perform, and whether the production pipeline is healthy.

Our channel (the owner's credential): subscribers and public views from the
Data API; watch hours, subscribers gained and average view percentage from the
YouTube Analytics API when the credential carries its scope (otherwise marked
UNAVAILABLE, never guessed). Pipeline: scheduled pilots, render, approval and
review status, and the script runway (days of videos written ahead).
Writes daily-report/latest.md (read by every check-in) and daily-report/<day>.json.
usage: goal_report.py PRODUCTION_DIR LEDGER OUT_DIR [START_DATE]
"""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import market_panel as mp  # noqa: E402
from packaging_mining import seconds  # noqa: E402

ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
# titles that read as fear-bait or fabricated prophecy (owner policy; YouTube misleading-metadata risk at YPP review)
RISK = re.compile(r"(?i)prophec|warning|warnig|hiding from you|they don.?t want you|before it.?s too late|don.?t ignore|"
                  r"is here!|exposed|banned")
YPP = {"subscribers": 1000, "watch_hours_365d": 4000, "shorts_views_90d": 10_000_000}
TARGET_DAYS, MAX_DAYS = 14, 30


def analytics(token, start, end, metrics, dimensions=None, extra=None):
    q = {"ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": metrics, **(extra or {})}
    if dimensions:
        q["dimensions"] = dimensions
    req = urllib.request.Request(ANALYTICS + "?" + urllib.parse.urlencode(q), headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def pipeline(production, ledger, now):
    rows = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        if not (d / "schedule.json").exists():
            continue
        t = datetime.fromisoformat(json.loads((d / "schedule.json").read_text())["publish_at"].replace("Z", "+00:00"))
        if t < now - timedelta(days=2):
            continue
        man = json.loads((d / "out" / "manifest.json").read_text()) if (d / "out" / "manifest.json").exists() else {}
        qa = json.loads((d / "out" / "qa.json").read_text()) if (d / "out" / "qa.json").exists() else {}
        rev = json.loads((d / "out" / "review.json").read_text()) if (d / "out" / "review.json").exists() else {}
        sha = man.get("output_sha256")
        current = rev.get("output_sha256") == sha
        rows.append({"pilot": d.name, "publish_at": t.strftime("%Y-%m-%d %H:%M UTC"),
                     "rendered": bool(man), "qa": qa.get("status") if qa.get("output_sha256") == sha else None,
                     "review": rev.get("status") if current else None,
                     "published": "video_id" in ledger.get("entries", {}).get(f"{d.name}:{sha}", {}),
                     "title": json.loads((d / "script.json").read_text()).get("working_title") if (d / "script.json").exists() else None})
    ahead = [r for r in rows if datetime.strptime(r["publish_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc) > now]
    last = max((datetime.strptime(r["publish_at"], "%Y-%m-%d %H:%M UTC") for r in ahead), default=None)
    runway = round((last.replace(tzinfo=timezone.utc) - now).total_seconds() / 86400, 1) if last else 0.0
    return rows, runway


def main(production, ledger_path, out_dir, start="2026-10-18"):
    now = datetime.now(timezone.utc)
    token = mp.access_token()
    client = mp.Client(token, 50)
    ch = client.get("channels", {"part": "statistics,contentDetails,snippet", "mine": "true"}, 1)["items"][0]
    st = ch["statistics"]
    ids = [i["contentDetails"]["videoId"] for i in client.get(
        "playlistItems", {"part": "contentDetails", "playlistId": ch["contentDetails"]["relatedPlaylists"]["uploads"], "maxResults": 50}, 1)["items"]]
    vids = client.get("videos", {"part": "snippet,statistics,status,contentDetails", "id": ",".join(ids)}, 1)["items"] if ids else []
    public = [v for v in vids if v["status"]["privacyStatus"] == "public"]
    videos = [{"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"][:16],
               "views": int(v["statistics"].get("viewCount", 0)), "likes": int(v["statistics"].get("likeCount", 0)),
               "comments": int(v["statistics"].get("commentCount", 0)),
               "short": seconds(v["contentDetails"]["duration"]) <= 180}
              for v in public]
    a = {"status": "UNAVAILABLE (the credential lacks the yt-analytics.readonly scope)"}
    try:
        end = now.date().isoformat()
        tot = analytics(token, (now.date() - timedelta(days=365)).isoformat(), end,
                        "estimatedMinutesWatched,views,subscribersGained,averageViewPercentage")
        r = (tot.get("rows") or [[0, 0, 0, 0]])[0]
        a = {"status": "OK", "watch_hours_365d": round(r[0] / 60, 1), "views_365d": r[1], "subscribers_gained_365d": r[2],
             "average_view_percentage": r[3]}
        per = analytics(token, (now.date() - timedelta(days=365)).isoformat(), end,
                        "estimatedMinutesWatched,views,averageViewPercentage,subscribersGained",
                        dimensions="video", extra={"sort": "-estimatedMinutesWatched", "maxResults": 50})
        a["per_video"] = {r[0]: {"watch_hours": round(r[1] / 60, 1), "views": r[2], "average_view_percentage": r[3],
                                 "subscribers_gained": r[4]} for r in per.get("rows", [])}
    except Exception as e:
        a["error"] = type(e).__name__
    subs = int(st.get("subscriberCount", 0))
    day = (now.date() - date.fromisoformat(start)).days + 1
    left = max(TARGET_DAYS - day + 1, 1)
    shorts_views = sum(v["views"] for v in videos if v["short"])
    need = {"subscribers_per_day": round(max(YPP["subscribers"] - subs, 0) / left, 1)}
    if a["status"] == "OK":
        need["watch_hours_per_day"] = round(max(YPP["watch_hours_365d"] - a["watch_hours_365d"], 0) / left, 1)
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows, runway = pipeline(production, ledger, now)
    for v in videos:
        v.update((a.get("per_video") or {}).get(v["id"], {}))
        v["policy_risk_title"] = bool(RISK.search(v["title"]))
    risky = [v for v in videos if v["policy_risk_title"]]
    risk_hours = round(sum(v.get("watch_hours", 0) for v in risky), 1)
    alerts = []
    if runway < 2:
        alerts.append(f"SCRIPT RUNWAY {runway} days (< 2): write the next pilots now")
    alerts += [f"{r['pilot']} review FAIL: read out/review.json" for r in rows if r["review"] == "FAIL"]
    alerts += [f"{r['pilot']} QA FAIL" for r in rows if r["qa"] == "FAIL"]
    report = {"version": "goal-report-v1", "at": now.isoformat(), "day": day, "target_day": TARGET_DAYS, "max_day": MAX_DAYS,
              "subscribers": subs, "views_total": int(st.get("viewCount", 0)), "public_videos": len(videos),
              "shorts_views_public": shorts_views, "analytics": a, "needed_from_today": need, "ypp": YPP,
              "videos": sorted(videos, key=lambda v: v["published"], reverse=True)[:20], "pipeline": rows,
              "script_runway_days": runway, "alerts": alerts, "data_api_units": client.units,
              "policy_risk_videos": [{k: v.get(k) for k in ("id", "title", "views", "watch_hours", "subscribers_gained", "short")} for v in risky],
              "policy_risk_watch_hours": risk_hours}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{now:%Y%m%d}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    wh = f"{a['watch_hours_365d']} / 4,000" if a["status"] == "OK" else a["status"]
    md = [f"# HeroVerse daily report — {now:%Y-%m-%d %H:%M} UTC (day {day} of {TARGET_DAYS}, max {MAX_DAYS})", "",
          "## YPP progress",
          f"- Subscribers: **{subs} / 1,000** (need {need['subscribers_per_day']}/day to qualify by day {TARGET_DAYS})",
          f"- Watch hours (365 d, long-form): **{wh}**" + (f" (need {need['watch_hours_per_day']}/day)" if "watch_hours_per_day" in need else ""),
          f"- Public Shorts views: {shorts_views:,} / 10,000,000 (90 d path)",
          f"- Public videos: {len(videos)}; total views {int(st.get('viewCount', 0)):,}", "",
          "## Alerts", *(f"- ⚠ {x}" for x in alerts or ["none"]), "",
          f"## Pipeline (script runway {runway} days)",
          "| pilot | publishes | rendered | QA | review | published | title |", "|---|---|---|---|---|---|---|",
          *(f"| {r['pilot']} | {r['publish_at']} | {'yes' if r['rendered'] else 'no'} | {r['qa'] or '-'} | {r['review'] or '-'} | "
            f"{'yes' if r['published'] else 'no'} | {r['title'] or ''} |" for r in rows), "",
          "## Latest public videos", "| published | views | watch h | avg view % | subs gained | title |", "|---|---|---|---|---|---|",
          *(f"| {v['published']} | {v['views']} | {v.get('watch_hours', '-')} | {v.get('average_view_percentage', '-')} | "
            f"{v.get('subscribers_gained', '-')} | {v['title'][:70]} |" for v in report["videos"][:12]), "",
          f"## Public videos with fear-bait/prophecy-style titles ({len(risky)}; {risk_hours} of the channel's watch hours)",
          *(f"- {v['title'][:80]} — {v.get('watch_hours', 0)} h, {v['views']} views" for v in risky), "",
          "Market and production directives of the day: `migration/evidence/daily-intel/` (latest file)."]
    (out / "latest.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"day": day, "subscribers": subs, "analytics": a["status"], "runway": runway, "alerts": alerts}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
