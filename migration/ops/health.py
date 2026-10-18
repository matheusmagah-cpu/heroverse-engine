#!/usr/bin/env python3
"""Scheduler health for the daily report: for every task of heartbeat.TASKS, the last run and whether a slot
passed more than LATE without a run (only tasks without a work condition can be judged from history alone);
plus the age of the last heartbeat and of the last render-runner run.
usage: health.py RUNS_JSON REPORT_MD [NOW_ISO]   (RUNS_JSON also holds "heartbeat.yml" and "runner")
"""
from datetime import datetime, timedelta, timezone
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import heartbeat as hb  # noqa: E402

LATE = timedelta(hours=3)
HEARTBEAT_MAX = timedelta(hours=2)


def check(runs, now):
    rows, alerts = [], []
    for task in hb.TASKS:
        mine = sorted(runs.get(task["workflow"], []), key=lambda r: r["createdAt"])
        last = mine[-1] if mine else None
        slot = hb.slot_now(task, now)
        weekly_off = task.get("weekdays") is not None and now.weekday() not in task["weekdays"]
        missed = (slot is not None and not task.get("when") and not weekly_off and now - slot > LATE
                  and not any(hb.ts(r["createdAt"]) >= slot for r in mine))
        rows.append({"workflow": task["workflow"], "last_run": last["createdAt"] if last else None,
                     "last_result": (last.get("conclusion") or last.get("status")) if last else None, "missed": missed})
        if missed:
            alerts.append(f"{task['workflow']}: slot {slot:%H:%M} UTC passed {LATE.seconds // 3600} h ago without a run")
    for name, limit in (("heartbeat.yml", HEARTBEAT_MAX), ("runner", timedelta(hours=3))):
        r = sorted(runs.get(name, []), key=lambda x: x["createdAt"])
        age = now - hb.ts(r[-1]["createdAt"]) if r else None
        rows.append({"workflow": name, "last_run": r[-1]["createdAt"] if r else None,
                     "last_result": (r[-1].get("conclusion") or r[-1].get("status")) if r else None,
                     "missed": age is None or age > limit})
        if age is None or age > limit:
            alerts.append(f"{name}: no run for {'ever' if age is None else str(age).split('.')[0]}")
    return rows, alerts


def main(runs_json, report_md, now=None):
    now = hb.ts(now) if now else datetime.now(timezone.utc)
    rows, alerts = check(json.load(open(runs_json)), now)
    md = ["", "## Scheduler health (heartbeat.yml; GitHub drops crons, the heartbeat catches up)",
          *([f"- ⚠ {a}" for a in alerts] or ["- all scheduled work ran"]),
          "| workflow | last run (UTC) | result |", "|---|---|---|",
          *(f"| {r['workflow']} | {(r['last_run'] or '-')[:16]} | {r['last_result'] or '-'}{' ⚠' if r['missed'] else ''} |" for r in rows)]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": alerts}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
