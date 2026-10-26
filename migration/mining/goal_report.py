#!/usr/bin/env python3
"""Daily goal report: where the channel stands against the YouTube Partner
Program, how fast it must move to qualify by day 14 (30 at most), how the
published videos perform, and whether the production pipeline is healthy.

Our channel (the owner's credential): subscribers and public views from the
Data API; watch hours, subscribers gained and average view percentage from the
YouTube Analytics API when the credential carries its scope (otherwise marked
UNAVAILABLE, never guessed). Pipeline: scheduled pilots, render, approval and
review status, and the long script runway: days of Bible-story long scripts written ahead on their registered
structure (structures/bible-story-long.json). Prayer pilots are retired (owner, 2026-10-26) and never count.
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
from learning_loop import capture_existing, save_capture
from packaging_mining import seconds  # noqa: E402
sys.path.insert(0, str(HERE.parent / "production"))
import render_queue  # noqa: E402  (story_long: only a Bible-story long counts)
sys.path.insert(0, str(HERE.parent / "ops"))
import runway as long_runway  # noqa: E402  (long_stage: the one stage rule of a long, shared with the runway section)

COUNTED_STAGES = ("script", "rendered", "approved", "uploaded")

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


def per_video(token, start, end, metrics):
    """{video_id: (content_type or None, *metric values)} for the channel's videos in the period. The content type
    (LONG_FORM_CONTENT, SHORTS, ...) comes from Analytics when the report accepts it; otherwise None."""
    extra = {"sort": "-" + metrics.split(",")[0], "maxResults": 200}
    try:
        rows = analytics(token, start, end, metrics, dimensions="video,creatorContentType", extra=extra).get("rows", [])
        return {r[0]: (r[1], *r[2:]) for r in rows}, "analytics creatorContentType"
    except Exception:
        rows = analytics(token, start, end, metrics, dimensions="video", extra=extra).get("rows", [])
        return {r[0]: (None, *r[1:]) for r in rows}, "duration <= 180 s (Analytics content type unavailable)"


def eligible(videos, per365, per90):
    """Own calculation of the two YPP counters from Analytics rows, restricted to what YPP counts: watch hours of
    videos that are PUBLIC and long-form now (365 days), views of PUBLIC Shorts (90 days). Not YouTube's own counter
    (it can still remove invalid views or count differently); reported as an estimate next to it."""
    def kind(v, row):
        if row and row[0]:
            return "short" if row[0] == "SHORTS" else ("long" if row[0] == "LONG_FORM_CONTENT" else row[0].lower())
        return "short" if v["short"] else "long"
    hours = sum((per365.get(v["id"]) or (None, 0))[1] for v in videos if kind(v, per365.get(v["id"])) == "long") / 60
    shorts = sum((per90.get(v["id"]) or (None, 0))[1] for v in videos if kind(v, per90.get(v["id"])) == "short")
    all_hours = sum(r[1] for r in per365.values()) / 60
    return {"public_long_form_watch_hours_365d": round(hours, 1), "public_shorts_views_90d": int(shorts),
            "all_content_watch_hours_365d_top200": round(all_hours, 1)}


def funnel(rows):
    """Short -> long funnel of ONE long video from its Analytics rows by traffic source
    ([insightTrafficSourceType, views, estimatedMinutesWatched, averageViewDuration]). The market shows no such funnel
    (evidence/vidiq/20261026/bible_story_long.json#funnel), so ours is measured, never assumed (owner, 2026-10-26):
    how many of the long's views come from Shorts, and whether those viewers watch as long as the rest."""
    views = sum(r[1] for r in rows)
    shorts = [r for r in rows if r[0] == "SHORTS"]
    other = [r for r in rows if r[0] != "SHORTS"]

    def avg(rs):
        v = sum(r[1] for r in rs)
        return round(sum(r[1] * r[3] for r in rs) / v, 1) if v else None
    out = {"views": views, "views_from_shorts": sum(r[1] for r in shorts),
           "share_from_shorts": round(sum(r[1] for r in shorts) / views, 3) if views else None,
           "avg_view_s_from_shorts": avg(shorts), "avg_view_s_other": avg(other),
           "sources": {r[0]: r[1] for r in sorted(rows, key=lambda r: -r[1])}}
    if not out["views_from_shorts"]:
        out["verdict"] = "NO_SHORTS_TRAFFIC"
    elif out["avg_view_s_other"] and out["avg_view_s_from_shorts"] >= out["avg_view_s_other"]:
        out["verdict"] = "SHORTS_VIEWERS_STAY"     # they watch at least as long as the long's other viewers
    else:
        out["verdict"] = "SHORTS_VIEWERS_LEAVE_EARLIER"
    return out


def pipeline(production, ledger, now, observed_privacy=None):
    observed_privacy = observed_privacy or {}
    rows = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        try:   # one malformed file never stops the whole report (review of #415)
            t = datetime.fromisoformat(render_queue.object_or_empty(d / "schedule.json")["publish_at"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, TypeError, ValueError):
            continue
        if t < now - timedelta(days=2):
            continue
        man = render_queue.object_or_empty(d / "out" / "manifest.json")
        qa = render_queue.object_or_empty(d / "out" / "qa.json")
        rev = render_queue.object_or_empty(d / "out" / "review.json")
        sha = man.get("output_sha256")
        current = rev.get("output_sha256") == sha
        try:   # the script is parsed once, tolerantly
            script = json.loads((d / "script.json").read_bytes()) if (d / "script.json").exists() else None
        except (OSError, ValueError):
            script = "UNREADABLE"
        story = render_queue.story_long(script)
        fmt = ("bible-story-long" if story else "script.json unreadable" if script == "UNREADABLE"
               else "no script" if script is None else "prayer (retired)")
        # the same stage rule as ops/runway.py (review of #415): a long past its script keeps its stage
        stage, problems = long_runway.long_stage(d, ledger) if story else (None, [])
        rows.append({"pilot": d.name, "publish_at": t.strftime("%Y-%m-%d %H:%M UTC"),
                     "format": fmt, "stage": stage, "problems": problems,
                     "rendered": bool(man), "qa": qa.get("status") if qa.get("output_sha256") == sha else None,
                     "review": rev.get("status") if current else None,
                     "uploaded": "video_id" in ledger.get("entries", {}).get(f"{d.name}:{sha}", {}),
                     "published": (observed_privacy[ledger['entries'][f'{d.name}:{sha}']['video_id']]=='public')
                         if ledger.get('entries',{}).get(f'{d.name}:{sha}',{}).get('video_id') in observed_privacy else None,
                     "title": script.get("working_title") if isinstance(script, dict) else None})
    # owner, 2026-10-26: the runway counts only Bible-story longs whose script passed (or that are already rendered,
    # approved or uploaded), never prayer pilots
    ahead = [r for r in rows if datetime.strptime(r["publish_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc) > now
             and r["format"] == "bible-story-long" and r["stage"] in COUNTED_STAGES]
    last = max((datetime.strptime(r["publish_at"], "%Y-%m-%d %H:%M UTC") for r in ahead), default=None)
    runway = round((last.replace(tzinfo=timezone.utc) - now).total_seconds() / 86400, 1) if last else 0.0
    return rows, runway


def pipeline_alerts(rows, runway):
    """The pipeline's alerts. The runway alert asks for Bible-story long scripts on their structure (owner,
    2026-10-26: prayer longs stopped); a story script off its structure is named with what it misses."""
    alerts = []
    if runway < 2:
        alerts.append(f"LONG SCRIPT RUNWAY {runway} days (< 2): write the next Bible-story long script "
                      "(structures/bible-story-long.json); prayer longs are stopped")
    alerts += [f"{r['pilot']} Bible-story long script FAIL: {'; '.join(r['problems'][:6])}"
               + (f" (+{len(r['problems']) - 6} more)" if len(r["problems"]) > 6 else "")
               for r in rows if r.get("format") == "bible-story-long" and r.get("stage") == "script-fail"]
    alerts += [f"{r['pilot']} script.json unreadable" for r in rows if r.get("format") == "script.json unreadable"]
    alerts += [f"{r['pilot']} review FAIL: read out/review.json" for r in rows if r["review"] == "FAIL"]
    alerts += [f"{r['pilot']} QA FAIL" for r in rows if r["qa"] == "FAIL"]
    return alerts


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
    captured_per = {}; captured_status = 'UNAVAILABLE'
    end = now.date().isoformat()
    range_start = (now.date() - timedelta(days=365)).isoformat()
    try:
        end = now.date().isoformat()
        tot = analytics(token, (now.date() - timedelta(days=365)).isoformat(), end,
                        "estimatedMinutesWatched,views,subscribersGained,averageViewPercentage")
        r = (tot.get("rows") or [[0, 0, 0, 0]])[0]
        a = {"status": "OK", "watch_hours_365d": round(r[0] / 60, 1), "views_365d": r[1], "subscribers_gained_365d": r[2],
             "average_view_percentage": r[3]}
        per, method = per_video(token, (now.date() - timedelta(days=365)).isoformat(), end,
                                "estimatedMinutesWatched,views,averageViewPercentage,subscribersGained")
        captured_per = per; captured_status = 'OBSERVED'
        a["per_video"] = {k: {"watch_hours": round(r[1] / 60, 1), "views": r[2], "average_view_percentage": round(r[3], 1),
                              "subscribers_gained": r[4], "content_type": r[0]} for k, r in per.items()}
        per90, _ = per_video(token, (now.date() - timedelta(days=90)).isoformat(), end, "views")
        a["eligible_estimate"] = {**eligible(videos, per, per90), "classification": method}
        a["funnel"] = {}
        for v in [v for v in videos if not v["short"]][:10]:
            rows = analytics(token, (now.date() - timedelta(days=90)).isoformat(), end,
                             "views,estimatedMinutesWatched,averageViewDuration", dimensions="insightTrafficSourceType",
                             extra={"filters": f"video=={v['id']}"}).get("rows", [])
            a["funnel"][v["id"]] = {"title": v["title"], **funnel(rows)}
    except Exception as e:
        if captured_status != 'OBSERVED': captured_status = 'ERROR'
        a["error"] = type(e).__name__
    subs = int(st.get("subscriberCount", 0))
    day = (now.date() - date.fromisoformat(start)).days + 1
    left = max(TARGET_DAYS - day + 1, 1)
    shorts_views = sum(v["views"] for v in videos if v["short"])
    need = {"subscribers_per_day": round(max(YPP["subscribers"] - subs, 0) / left, 1)}
    est = a.get("eligible_estimate")
    if est:
        need["watch_hours_per_day"] = round(max(YPP["watch_hours_365d"] - est["public_long_form_watch_hours_365d"], 0) / left, 1)
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows, runway = pipeline(production, ledger, now, {v['id']:v['status']['privacyStatus'] for v in vids})
    for v in videos:
        v.update((a.get("per_video") or {}).get(v["id"], {}))
        v["policy_risk_title"] = bool(RISK.search(v["title"]))
    risky = [v for v in videos if v["policy_risk_title"]]
    risk_hours = round(sum(v.get("watch_hours", 0) for v in risky), 1)
    alerts = pipeline_alerts(rows, runway)
    report = {"version": "goal-report-v2", "at": now.isoformat(), "day": day, "target_day": TARGET_DAYS, "max_day": MAX_DAYS,
              "subscribers": subs, "views_total": int(st.get("viewCount", 0)), "public_videos": len(videos),
              "shorts_views_public_lifetime": shorts_views, "analytics": a, "needed_from_today": need, "ypp": YPP,
              "videos": sorted(videos, key=lambda v: v["published"], reverse=True)[:20], "pipeline": rows,
              "script_runway_days": runway, "alerts": alerts, "data_api_units": client.units,
              "policy_risk_videos": [{k: v.get(k) for k in ("id", "title", "views", "watch_hours", "subscribers_gained", "short")} for v in risky],
              "policy_risk_watch_hours": risk_hours}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    snapshot=capture_existing(vids,captured_per,captured_at=now.isoformat(),start=range_start,end=end,
                              analytics_status=captured_status)
    snapshot['data_api_units']=client.units
    capture_path=save_capture(snapshot,out/'learning')
    report['learning_capture_path']=str(capture_path)
    (out / f"{now:%Y%m%d}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    wh = f"{est['public_long_form_watch_hours_365d']} / 4,000" if est else a["status"]
    sv = f"{est['public_shorts_views_90d']:,} / 10,000,000" if est else a["status"]
    allh = f"{a['watch_hours_365d']} h" if a["status"] == "OK" else a["status"]
    md = [f"# HeroVerse daily report — {now:%Y-%m-%d %H:%M} UTC (day {day} of {TARGET_DAYS}, max {MAX_DAYS})", "",
          "## YPP progress",
          "Sources: [official] YouTube Data API count; [own] our calculation from YouTube Analytics rows (an estimate of",
          "the YPP counter, which only YouTube Studio shows and which can differ); [plan] our arithmetic toward day 14.", "",
          f"- Subscribers [official]: **{subs} / 1,000** — [plan] {need['subscribers_per_day']}/day to reach it by day {TARGET_DAYS}",
          f"- Public long-form watch hours, last 365 d [own]: **{wh}**" + (f" — [plan] {need['watch_hours_per_day']}/day" if "watch_hours_per_day" in need else ""),
          f"- Public Shorts views, last 90 d [own]: {sv} (the alternative YPP path)",
          f"- For contrast, NOT the YPP counters: all-content watch hours 365 d incl. Shorts and private/removed videos [own] {allh}; "
          f"lifetime views of public Shorts [official] {shorts_views:,}",
          f"- Classification of long vs Shorts: {est['classification'] if est else '-'}",
          f"- Public videos [official]: {len(videos)}; total channel views {int(st.get('viewCount', 0)):,}", "",
          "## Short -> long funnel (each public long, last 90 d, by traffic source)",
          "| long | views | from Shorts | share | avg view s (Shorts / other) | verdict |", "|---|---|---|---|---|---|",
          *((f"| {f['title'][:50]} | {f['views']} | {f['views_from_shorts']} | {f['share_from_shorts']} | "
            f"{f['avg_view_s_from_shorts']} / {f['avg_view_s_other']} | {f['verdict']} |"
            for f in a["funnel"].values()) if a.get("funnel") else ["- no public long yet, or Analytics unavailable"]), "",
          "## Alerts", *(f"- ⚠ {x}" for x in alerts or ["none"]), "",
          f"## Pipeline (long script runway {runway} days: Bible-story longs on their structure; prayer longs stopped)",
          "| pilot | format | publishes | rendered | QA | review | uploaded | public observed | title |", "|---|---|---|---|---|---|---|---|---|",
          *(f"| {r['pilot']} | {r['format']} | {r['publish_at']} | {'yes' if r['rendered'] else 'no'} | {r['qa'] or '-'} | {r['review'] or '-'} | "
            f"{'yes' if r['uploaded'] else 'no'} | {'UNKNOWN' if r['published'] is None else ('yes' if r['published'] else 'no')} | {r['title'] or ''} |" for r in rows), "",
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
