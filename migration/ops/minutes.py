#!/usr/bin/env python3
"""GitHub Actions minutes of the private engine, for the daily report: billable minutes per workflow (each run rounded
up to a whole minute, as GitHub bills each job; the engine's workflows are single-job), the last 24 h / 7 d / 30 d,
the 30-day projection from the last 7 days, and alerts against the monthly budget the owner pays for.
usage: minutes.py RUNS_JSON REPORT_MD [NOW_ISO]   (RUNS_JSON: the REST list of workflow runs, any number of pages merged)
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
import sys

MONTH_BUDGET = 7000   # minutes per 30 days (2,000 included + paid overage; OPERATIONS.md "Budgets")
DAILY_TARGET = MONTH_BUDGET / 30


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
    projection = round(win["7d"] / 7 * 30)
    alerts = []
    if win["24h"] > DAILY_TARGET * 1.5:
        alerts.append(f"last 24 h used {win['24h']} min (target {DAILY_TARGET:.0f}/day)")
    if projection > MONTH_BUDGET * 0.9:
        alerts.append(f"30-day projection {projection} min ≥ 90 % of the {MONTH_BUDGET} min budget")
    top = sorted(per.items(), key=lambda kv: -kv[1][0])[:8]
    return {"windows": win, "projection_30d": projection, "budget": MONTH_BUDGET, "alerts": alerts,
            "top": [{"workflow": k, "minutes": v[0], "runs": v[1]} for k, v in top]}


def main(runs_json, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    s = summary(json.load(open(runs_json)), now)
    w = s["windows"]
    md = ["", f"## Actions minutes (private engine; budget {s['budget']} min / 30 days)",
          *([f"- ⚠ {a}" for a in s["alerts"]] or ["- within budget"]),
          f"- last 24 h {w['24h']} · last 7 d {w['7d']} · last 30 d {w['30d']} · 30-day projection {s['projection_30d']}",
          "| workflow (30 d) | minutes | runs |", "|---|---|---|",
          *(f"| {t['workflow']} | {t['minutes']} | {t['runs']} |" for t in s["top"])]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": s["alerts"], "projection_30d": s["projection_30d"]}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
