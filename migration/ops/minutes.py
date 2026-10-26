#!/usr/bin/env python3
"""GitHub Actions minutes of the private engine, for the daily report: billable minutes per workflow (each run rounded
up to a whole minute, as GitHub bills each job; most of the engine's workflows are single-job), the last 24 h / 7 d /
30 d, the 30-day projection from the last 7 days, the pace, and alerts against the budget the owner pays for.
usage: minutes.py RUNS_JSON REPORT_MD [NOW_ISO]   (RUNS_JSON: the REST list of workflow runs, any number of pages merged)
       minutes.py check RUNS_JSON [NOW_ISO]        (heartbeat, hourly, E100: the last 24 h only; a ::warning:: line when
                                                    the day is over the pace; never fails the beat)
The pace (E100): the budget is a rolling 30 days, so the next 24 h may use at most the budget minus the 29 days before
them, and the sustainable pace is budget / 30 a day. A run is counted from run_started_at to updated_at: a multi-job
run (a matrix) is under-counted and a run that waited on a concurrency group over-counted (within ~7 % over all runs
of 2026-10-23..26 against the jobs' own times).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import math
import sys

MONTH_BUDGET = 7000   # minutes per 30 days (2,000 included + paid overage; E21)
DAILY_TARGET = MONTH_BUDGET / 30


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def billable(run):
    if not run.get("run_started_at") or run.get("status") != "completed" or run.get("conclusion") in ("skipped",):
        return 0
    secs = (ts(run["updated_at"]) - ts(run["run_started_at"])).total_seconds()
    return max(1, math.ceil(secs / 60)) if secs > 0 else 0


def pace(win, last29):
    """E100: what the rolling budget still allows. allowed_next_24h = budget - the 29 days before the last 24 h;
    days_left_at_7d_pace = the 30-day headroom at the last 7 days' daily pace (None when nothing ran); cut_pct = how
    far the 7-day pace must fall to reach budget / 30 a day (0 when it is already there)."""
    daily7 = win["7d"] / 7
    headroom = max(0, MONTH_BUDGET - win["30d"])
    return {"daily_target": round(DAILY_TARGET), "daily_7d": round(daily7),
            "allowed_next_24h": max(0, MONTH_BUDGET - last29), "headroom_30d": headroom,
            "days_left_at_7d_pace": round(headroom / daily7, 1) if daily7 else None,
            "cut_pct": max(0, round(100 * (1 - DAILY_TARGET / daily7))) if daily7 else 0}


def summary(runs, now):
    per = defaultdict(lambda: [0, 0])
    win = {"24h": 0, "7d": 0, "30d": 0}
    last29 = 0
    for r in runs:
        m = billable(r)
        age = now - ts(r["created_at"])
        if timedelta(hours=24) < age <= timedelta(days=30):
            last29 += m   # still inside the 30-day window during the next 24 h
        if age <= timedelta(days=30):
            win["30d"] += m
            per[r.get("name", "?")][0] += m
            per[r.get("name", "?")][1] += 1
        if age <= timedelta(days=7):
            win["7d"] += m
        if age <= timedelta(hours=24):
            win["24h"] += m
    projection = round(win["7d"] / 7 * 30)
    p = pace(win, last29)
    alerts = []
    if win["24h"] > DAILY_TARGET * 1.5:
        alerts.append(f"last 24 h used {win['24h']} min (target {DAILY_TARGET:.0f}/day)")
    if projection > MONTH_BUDGET * 0.9:
        alerts.append(f"30-day projection {projection} min ≥ 90 % of the {MONTH_BUDGET} min budget")
    if win["30d"] >= MONTH_BUDGET * 0.8:
        alerts.append(f"{win['30d']} of the {MONTH_BUDGET} min used in the last 30 days: the next 24 h may use at most "
                      f"{p['allowed_next_24h']} min")
    top = sorted(per.items(), key=lambda kv: -kv[1][0])[:8]
    return {"windows": win, "projection_30d": projection, "budget": MONTH_BUDGET, "alerts": alerts, "pace": p,
            "top": [{"workflow": k, "minutes": v[0], "runs": v[1]} for k, v in top]}


def check(runs, now):
    """The hourly guard (heartbeat.yml, E100): from the last 24 h of runs alone, a warning line or None."""
    used = sum(billable(r) for r in runs if now - ts(r["created_at"]) <= timedelta(hours=24))
    if used > DAILY_TARGET * 1.5:
        return (f"::warning::ACTIONS_MINUTES_OVER_PACE last 24 h used {used} min; the budget allows "
                f"{DAILY_TARGET:.0f}/day ({MONTH_BUDGET} / 30 days): cut repeated builds first (SYSTEM.md)")
    return None


def main(runs_json, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    with open(runs_json) as f:
        s = summary(json.load(f), now)
    w, p = s["windows"], s["pace"]
    md = ["", f"## Actions minutes (private engine; budget {s['budget']} min / 30 days)",
          *([f"- ⚠ {a}" for a in s["alerts"]] or ["- within budget"]),
          f"- last 24 h {w['24h']} · last 7 d {w['7d']} · last 30 d {w['30d']} · 30-day projection {s['projection_30d']}",
          f"- pace: {p['daily_7d']} min/day over the last 7 days against {p['daily_target']}/day"
          + (f" (cut {p['cut_pct']} %)" if p["cut_pct"] else "")
          + f"; headroom {p['headroom_30d']} min"
          + (f", gone in {p['days_left_at_7d_pace']} days at this pace" if p["days_left_at_7d_pace"] is not None else "")
          + f"; the next 24 h may use at most {p['allowed_next_24h']} min",
          "| workflow (30 d) | minutes | runs |", "|---|---|---|",
          *(f"| {t['workflow']} | {t['minutes']} | {t['runs']} |" for t in s["top"])]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": s["alerts"], "projection_30d": s["projection_30d"], "pace": p}))


if __name__ == "__main__":
    if sys.argv[1:2] == ["check"]:
        try:   # the guard never stops the scheduler: a bad listing is reported, not raised
            when = ts(sys.argv[3]) if len(sys.argv) > 3 else datetime.now(timezone.utc)
            with open(sys.argv[2]) as f:
                line = check(json.load(f), when)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
            line = f"::warning::ACTIONS_MINUTES_CHECK_FAILED {type(e).__name__}"
        print(line or "ACTIONS_MINUTES_WITHIN_PACE")
    else:
        main(*sys.argv[1:4])
