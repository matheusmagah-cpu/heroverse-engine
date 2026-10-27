#!/usr/bin/env python3
"""Impressions, thumbnail CTR and clicks of every video, every day (owner, 2026-10-27: "são os dados mais importantes").

The YouTube Analytics API v2 (goal_report.py) has no impressions or CTR. The YouTube Reporting API has them in its
reach reports (https://developers.google.com/youtube/reporting/v1/reports/channel_reports, added 2026-01-15):
channel_reach_basic_a1 = date, channel_id, video_id, video_thumbnail_impressions, video_thumbnail_impressions_ctr.
CTR is "clicks divided by impressions" (reports/metrics); the reports carry it as a fraction 0..1 (our own report of
2026-10-12: 175 impressions, ctr 0.0057142857 = 1/175; evidence/owned-reach-two-report-receipt.json). The `date`
column is the Pacific-time day. Clicks are DERIVED here: round(impressions x ctr) per row.

Each run, with the owner's credential (HERO_YT_AUTHORIZED_USER_JSON, scope yt-analytics.readonly, the same token as
goal_report.py through market_panel.access_token): make sure ONE reporting job for channel_reach_basic_a1 exists (list
the jobs, create only when none has that report type), list its reports, download those not yet ingested (or
regenerated with a newer createTime), and keep the rows per day in daily-report/reach.json (compact; raw CSVs are
never stored). YouTube makes the first report ~48 h after a job is created and backfills the 30 days before it;
reports stay downloadable 60 days (30 for backfill), so a missed day is caught up the next run.

It appends an "Impressions and CTR" section to daily-report/latest.md: per video (impressions, CTR, clicks, views,
dates, Shorts or long as goal_report classified it) and per day. With no report yet it says PENDING with the job's
creation date; when the token lacks the scope, the API is disabled in the Google Cloud project or anything else
fails, it says UNKNOWN with the reason and keeps the last numbers it had. It never fails the daily report.
usage: reach_report.py DAILY_REPORT_DIR [PUBLISH_LEDGER]
"""
import csv
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

API = "https://youtubereporting.googleapis.com/v1/"
REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "heroverse-reach-basic"
IMPRESSIONS, CTR = "video_thumbnail_impressions", "video_thumbnail_impressions_ctr"
DOWNLOAD_HOST = "youtubereporting.googleapis.com"   # the bearer token goes to this host only
MAX_REPORT_BYTES = 20_000_000
MAX_DOWNLOADS = 120          # per run; the rest next run (60 days of history fit in one run)
MAX_SECONDS = 120            # wall clock spent downloading per run; the rest next run (the step has 3 minutes)
HEADING = "## Impressions and CTR (thumbnail impressions, YouTube Reporting API channel_reach_basic_a1)"
DAYS_SHOWN = 14


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx is an error, never followed: urllib copies request headers to the redirected host (review of #463)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "REDIRECT_REFUSED", headers, None)


def make_opener(*handlers):
    return urllib.request.build_opener(*handlers, NoRedirect()).open


class Http:
    """The only network layer (tests pass a fake with the same two methods)."""
    def __init__(self, token, opener=None):
        self.token, self.opener = token, opener or make_opener()

    def _open(self, req, cap):
        # unredirected: even a redirect followed by another opener never carries the token
        req.add_unredirected_header("Authorization", "Bearer " + self.token)
        with self.opener(req, timeout=60) as r:
            body = r.read(cap + 1)
        if len(body) > cap:
            raise ValueError("RESPONSE_CAP")
        return body

    def json(self, method, path, params=None, body=None):
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json"})
        if data is not None:
            req.add_header("Content-Type", "application/json")
        return json.loads(self._open(req, 4_000_000) or b"{}")

    def download(self, url):
        u = urllib.parse.urlsplit(url)
        if u.scheme != "https" or u.hostname != DOWNLOAD_HOST:
            raise ValueError("DOWNLOAD_HOST_REFUSED")    # never send the token anywhere else
        return self._open(urllib.request.Request(url), MAX_REPORT_BYTES)


def pages(http, path, key, params=None):
    out, token = [], None
    for _ in range(50):
        p = dict(params or {}, **({"pageToken": token} if token else {}))
        r = http.json("GET", path, p or None)
        out += r.get(key, [])
        token = r.get("nextPageToken")
        if not token:
            break
    return out


def ensure_job(http):
    """(job, created): the job of REPORT_TYPE, created only when none exists (idempotent; the oldest one wins)."""
    jobs = sorted((j for j in pages(http, "jobs", "jobs") if j.get("reportTypeId") == REPORT_TYPE),
                  key=lambda j: j.get("createTime", ""))
    if jobs:
        return jobs[0], False
    return http.json("POST", "jobs", body={"reportTypeId": REPORT_TYPE, "name": JOB_NAME}), True


def parse_csv(raw):
    """[(iso_date, video_id, impressions, ctr)] of one reach report; columns found by name, never by position."""
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    head = next(csv.reader(io.StringIO(text)), [])
    missing = [c for c in ("date", "video_id", IMPRESSIONS, CTR) if c not in head]
    if missing:
        raise ValueError("REPORT_COLUMNS_MISSING " + ",".join(missing))
    out = []
    for r in rows:
        d = r["date"].strip()
        d = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d
        ctr = float(r[CTR] or 0)
        if not 0 <= ctr <= 1:
            raise ValueError("CTR_NOT_A_FRACTION")   # the scale was verified as 0..1; refuse rather than misreport
        out.append((d, r["video_id"].strip(), int(float(r[IMPRESSIONS] or 0)), ctr))
    return out


def ingest(http, job, state, limit=MAX_DOWNLOADS, seconds=MAX_SECONDS, clock=time.monotonic):
    """Download the job's reports not yet in state (or regenerated later); returns (downloaded, skipped reasons)."""
    days, seen = state.setdefault("days", {}), state.setdefault("reports", {})
    todo = [r for r in pages(http, f"jobs/{urllib.parse.quote(job['id'])}/reports", "reports")
            if seen.get(r.get("startTime", "")[:10], {}).get("created", "") < r.get("createTime", "")]
    todo.sort(key=lambda r: (r.get("startTime", ""), r.get("createTime", "")))
    got, problems, start = 0, [], clock()
    for n, r in enumerate(todo[:limit]):
        if clock() - start > seconds:
            problems.append(f"{len(todo) - n} reports left for the next run (time cap {seconds} s)")
            return got, problems
        day = r.get("startTime", "")[:10]   # Pacific midnight is 07:00/08:00Z of the same calendar date
        if len(day) != 10 or not r.get("downloadUrl"):
            problems.append(f"report {r.get('id')}: no startTime or downloadUrl")
            continue
        try:
            rows = parse_csv(http.download(r["downloadUrl"]))
        except Exception as e:  # one bad report never stops the others
            problems.append(f"{day}: {type(e).__name__} {str(e)[:60]}")
            continue
        for d in {d for d, *_ in rows} | {day}:
            days[d] = {v: [i, c] for dd, v, i, c in rows if dd == d}
        seen[day] = {"id": r.get("id"), "created": r.get("createTime", "")}
        got += 1
    if len(todo) > limit:
        problems.append(f"{len(todo) - limit} reports left for the next run")
    return got, problems


def kind_of(video):
    ct = (video or {}).get("content_type")
    if ct:
        return "short" if ct == "SHORTS" else "long" if ct == "LONG_FORM_CONTENT" else ct.lower()
    if video and "short" in video:
        return "short" if video["short"] else "long"
    return "unclassified"


def aggregate(days, videos):
    """Per video and per day: impressions, clicks (derived = round(impressions x ctr) per row), CTR = clicks /
    impressions; per day also split by Shorts / long as goal_report classified the video."""
    info = {v["id"]: v for v in videos}
    per_video, per_day = {}, {}
    for d in sorted(days):
        day = per_day.setdefault(d, {"impressions": 0, "clicks": 0, "by_kind": {}})
        for vid, (imp, ctr) in days[d].items():
            clicks = round(imp * ctr)
            k = kind_of(info.get(vid))
            pv = per_video.setdefault(vid, {"impressions": 0, "clicks": 0, "first_day": d, "kind": k})
            pv["impressions"] += imp
            pv["clicks"] += clicks
            pv["last_day"] = d
            day["impressions"] += imp
            day["clicks"] += clicks
            bk = day["by_kind"].setdefault(k, {"impressions": 0, "clicks": 0})
            bk["impressions"] += imp
            bk["clicks"] += clicks
    for x in [*per_video.values(), *per_day.values(), *(b for d in per_day.values() for b in d["by_kind"].values())]:
        x["ctr"] = round(x["clicks"] / x["impressions"], 4) if x["impressions"] else None
    for vid, pv in per_video.items():
        v = info.get(vid, {})
        pv.update(title=v.get("title"), views=v.get("views"), published=v.get("published"))
    split = {}
    for pv in per_video.values():
        s = split.setdefault(pv["kind"], {"videos": 0, "impressions": 0, "clicks": 0})
        s["videos"] += 1
        s["impressions"] += pv["impressions"]
        s["clicks"] += pv["clicks"]
    for s in split.values():
        s["ctr"] = round(s["clicks"] / s["impressions"], 4) if s["impressions"] else None
    return per_video, per_day, split


def reason(exc):
    """A short, secret-free reason for an UNKNOWN state (the error body is read only for Google's reason codes)."""
    if isinstance(exc, PermissionError) and "CREDENTIAL_MISSING" in str(exc):
        return "CREDENTIAL_MISSING: HERO_YT_AUTHORIZED_USER_JSON is not set"
    if type(exc).__name__ == "RefreshError":
        return "TOKEN_REFRESH_FAILED: the owner's credential was refused; re-consent it"
    if isinstance(exc, urllib.error.HTTPError):
        try:
            err = json.loads(exc.read(65536) or b"{}").get("error", {})
        except Exception:
            err = {}
        codes = {err.get("status", "")} | {e.get("reason", "") for e in err.get("errors", []) if isinstance(e, dict)} \
            | {d.get("reason", "") for d in err.get("details", []) if isinstance(d, dict)}
        if codes & {"SERVICE_DISABLED", "accessNotConfigured"}:
            return (f"API_DISABLED (HTTP {exc.code}): enable the YouTube Reporting API in the Google Cloud project "
                    "of the OAuth client")
        if codes & {"ACCESS_TOKEN_SCOPE_INSUFFICIENT", "insufficientPermissions"}:
            return f"SCOPE_MISSING (HTTP {exc.code}): the credential lacks yt-analytics.readonly; re-consent with it"
        return f"HTTP {exc.code} {sorted(c for c in codes if c)[:2] or exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return "NETWORK: " + type(exc.reason).__name__
    return type(exc).__name__ + (f" {str(exc)[:60]}" if isinstance(exc, ValueError) else "")


def run(http_factory, state, videos, now):
    """Mutates and returns state with status OK, PENDING or UNKNOWN; never raises."""
    state.update(version="reach-v1", report_type=REPORT_TYPE, at=now.isoformat())
    state.pop("reason", None)
    state["problems"], state["downloaded"] = [], 0
    try:
        http = http_factory()
        job, created = ensure_job(http)
        state["job"] = {"id": job.get("id"), "create_time": job.get("createTime"), "created_this_run": created}
        state["downloaded"], problems = ingest(http, job, state)
        state["problems"] = problems
        state["status"] = "OK" if state.get("days") else "PENDING"
    except Exception as e:
        state["status"], state["reason"] = "UNKNOWN", reason(e)
    state["per_video"], state["per_day"], state["split"] = aggregate(state.get("days", {}), videos)
    return state


def pct(x):
    return "-" if x is None else f"{x * 100:.2f} %"


def section(s, now):
    md = ["", HEADING,
          "Impressions: thumbnail shown > 1 s, >= 50 % visible. CTR: clicks / impressions. Clicks: DERIVED "
          "(impressions x CTR). Days are Pacific time; YouTube publishes a day ~48 h later. Shorts swiped in the "
          "Shorts feed are mostly not thumbnail impressions, so a Short's numbers here are its thumbnail surfaces only."]
    job = s.get("job") or {}
    if s["status"] == "UNKNOWN":
        md += ["| status | reason |", "|---|---|", f"| UNKNOWN | {s['reason']} |"]
        if s.get("per_video"):
            md.append(f"Last known numbers below (from earlier runs, last report day {max(s['per_day'])}).")
    elif s["status"] == "PENDING":
        created = (job.get("create_time") or now.isoformat())[:10]
        first = (date.fromisoformat(created) + timedelta(days=2)).isoformat()
        md.append(f"- **PENDING**: reach job created on {created}; first data ~48 h later (from {first}), "
                  "with YouTube's backfill of the 30 days before the job.")
    if s.get("per_video"):
        sp = s["split"]
        md.append("- Totals: " + " · ".join(f"{k} ({v['videos']} videos): {v['impressions']:,} impressions, "
                                             f"CTR {pct(v['ctr'])}, {v['clicks']:,} clicks" for k, v in sorted(sp.items())))
        md += ["", "| video | type | impressions | CTR | clicks (derived) | views (lifetime) | published | report days |",
               "|---|---|---|---|---|---|---|---|"]
        for vid, v in sorted(s["per_video"].items(), key=lambda kv: -kv[1]["impressions"]):
            name = (v.get("title") or vid)[:50].replace("|", "/")   # a title never breaks the table
            md.append(f"| {name} ({vid}) | {v['kind']} | {v['impressions']:,} | {pct(v['ctr'])} | {v['clicks']:,} | "
                      f"{'-' if v.get('views') is None else v['views']} | {(v.get('published') or '-')[:10]} | "
                      f"{v['first_day']} .. {v['last_day']} |")
        kinds = sorted({k for d in s["per_day"].values() for k in d["by_kind"]})
        md += ["", "| day (PT) | impressions | CTR | clicks | " + " | ".join(f"{k} impr / CTR" for k in kinds) + " |",
               "|---|---|---|---|" + "---|" * len(kinds)]
        for d in sorted(s["per_day"], reverse=True)[:DAYS_SHOWN]:
            x = s["per_day"][d]
            md.append(f"| {d} | {x['impressions']:,} | {pct(x['ctr'])} | {x['clicks']:,} | " + " | ".join(
                f"{x['by_kind'][k]['impressions']:,} / {pct(x['by_kind'][k]['ctr'])}" if k in x["by_kind"] else "-"
                for k in kinds) + " |")
    if s.get("problems"):
        md.append("- Reports not read this run: " + "; ".join(s["problems"][:5]))
    return md


def latest_videos(out, ledger_path=None):
    """Every video we can classify (review of #463: the report's `videos` keeps only the 20 newest): the newest goal
    report's `video_index` (all public videos), else its `videos` with Analytics' content type from
    `analytics.per_video`; then the publish ledger (a `short:` entry is a Short, any other a long) for the rest."""
    index = {}
    days = sorted(p for p in Path(out).glob("[0-9]" * 8 + ".json"))
    try:
        rep = json.loads(days[-1].read_text()) if days else {}
    except (OSError, ValueError):
        rep = {}
    rep = rep if isinstance(rep, dict) else {}
    per = ((rep.get("analytics") or {}).get("per_video") or {}) if isinstance(rep.get("analytics"), dict) else {}
    for v in rep.get("videos") or []:
        if isinstance(v, dict) and v.get("id"):
            index[v["id"]] = dict(v, content_type=v.get("content_type") or (per.get(v["id"]) or {}).get("content_type"))
    for vid, v in (rep.get("video_index") or {}).items():
        if isinstance(v, dict):
            index[vid] = dict(index.get(vid, {}), **{k: x for k, x in v.items() if x is not None}, id=vid)
    for vid, p in per.items():
        if vid not in index and isinstance(p, dict) and p.get("content_type"):
            index[vid] = {"id": vid, "content_type": p["content_type"], "views": p.get("views")}
    try:
        ledger = json.loads(Path(ledger_path).read_text()) if ledger_path and Path(ledger_path).exists() else {}
    except (OSError, ValueError):
        ledger = {}
    entries = ledger.get("entries", {}) if isinstance(ledger, dict) else {}
    for key, e in (entries.items() if isinstance(entries, dict) else []):
        vid = isinstance(e, dict) and e.get("video_id")
        if vid and vid not in index:
            index[vid] = {"id": vid, "short": key.startswith("short:"), "published": (e.get("uploaded_at") or "")[:16]}
    return list(index.values())


def main(out_dir, ledger_path=None, now=None, http_factory=None):
    now = now or datetime.now(timezone.utc)
    out = Path(out_dir)
    path = out / "reach.json"
    try:
        state = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    if http_factory is None:
        def http_factory():
            import market_panel as mp     # the same token refresh as goal_report.py
            return Http(mp.access_token())
    s = run(http_factory, state, latest_videos(out, ledger_path), now)
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    with open(out / "latest.md", "a") as f:
        f.write("\n".join(section(s, now)) + "\n")
    print(json.dumps({"reach": s["status"], "reason": s.get("reason"), "days": len(s.get("days", {})),
                      "videos": len(s["per_video"]), "downloaded": s.get("downloaded")}))
    return s


def write_unknown(out, why):
    """Append an UNKNOWN row to latest.md; write reach.json only when it holds no good history."""
    out = Path(out)
    path = out / "reach.json"
    try:
        ok = isinstance(json.loads(path.read_text()), dict)
    except (OSError, ValueError):
        ok = False
    if not ok:    # never overwrite good history with a crash note
        path.write_text(json.dumps({"version": "reach-v1", "status": "UNKNOWN", "reason": why}) + "\n")
    with open(out / "latest.md", "a") as f:
        f.write("\n".join(["", HEADING, "| status | reason |", "|---|---|", f"| UNKNOWN | {why} |"]) + "\n")
    print(json.dumps({"reach": "UNKNOWN", "reason": why}))


def cli(argv, main=main):
    """The workflow's entry point: whatever goes wrong, latest.md says UNKNOWN with the reason and the exit is 0, so
    the daily report and its later steps always go on (review of #463). `--step-failed RC DIR` is the workflow's
    fallback when the run was killed by its `timeout` (exit 124) or died before cli could report."""
    try:
        if argv[:1] == ["--step-failed"]:
            rc = argv[1] if len(argv) > 1 and argv[1].isdigit() else "?"
            write_unknown(argv[2], f"STEP_FAILED exit {rc}" + (" (timed out)" if rc == "124" else "")
                          + ": reach_report.py did not finish; the rest of the daily report is unaffected")
            return 0
        main(*argv[:2])
    except Exception as e:
        try:
            write_unknown(argv[0] if argv else ".", f"CRASH {type(e).__name__}: reach_report.py failed; "
                          "the rest of the daily report is unaffected")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:4]))
