#!/usr/bin/env python3
"""GitHub Actions minutes of the engine, for the daily report, as a speed and wall-clock measure only. The engine
repository is public, and standard GitHub-hosted runners are free for public repositories (owner, 2026-10-26: it
stays public). There is no budget and no overage, so the report raises no spending alarm (E102). It lists the minutes
per workflow (each run rounded up to a whole minute) over the last 24 h, 7 d and 30 d, and the slowest workflows,
which are the first place to make CI faster. A repeated build still shows up here: it delays the work.
usage: minutes.py RUNS_JSON REPORT_MD [NOW_ISO]   (RUNS_JSON: the REST list of workflow runs, any number of pages merged)
A run is counted from run_started_at to updated_at. A multi-job run (a matrix) is under-counted. A run that waited
on a concurrency group is over-counted. Across all runs of 2026-10-23..26 the count was within ~7 % of the jobs'
own times.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
import sys

HEADING = "## Actions minutes (speed only; public repo: standard runners free)"


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def billable(run):
    if not run.get("run_started_at") or run.get("status") != "completed" or run.get("conclusion") in ("skipped",):
        return 0
    secs = (ts(run["updated_at"]) - ts(run["run_started_at"])).total_seconds()
    return max(1, math.ceil(secs / 60)) if secs > 0 else 0


def summary(runs, now):
    per = defaultdict(lambda: [0, 0])
    win = {"24h": 0, "7d": 0, "30d": 0}
    for r in runs:
        m = billable(r)
        age = now - ts(r["created_at"])
        if age <= timedelta(days=30):
            win["30d"] += m
            per[r.get("name", "?")][0] += m
            per[r.get("name", "?")][1] += 1
        if age <= timedelta(days=7):
            win["7d"] += m
        if age <= timedelta(hours=24):
            win["24h"] += m
    top = sorted(per.items(), key=lambda kv: -kv[1][0])[:8]
    return {"windows": win,
            "top": [{"workflow": k, "minutes": v[0], "runs": v[1], "per_run": round(v[0] / v[1], 1) if v[1] else 0}
                    for k, v in top]}


def main(runs_json, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    with open(runs_json) as f:
        s = summary(json.load(f), now)
    w = s["windows"]
    md = ["", HEADING,
          f"- last 24 h {w['24h']} · last 7 d {w['7d']} · last 30 d {w['30d']} min of runner time",
          "| workflow (30 d) | minutes | runs | min per run |", "|---|---|---|---|",
          *(f"| {t['workflow']} | {t['minutes']} | {t['runs']} | {t['per_run']} |" for t in s["top"])]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"windows": w}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
