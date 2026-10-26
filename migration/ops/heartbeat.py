#!/usr/bin/env python3
"""The engine's only scheduler. GitHub drops scheduled runs under load (2026-10-17/18: every daily cron of this
repository was dropped; only 2 of the 4-hourly ones ran, 24 min late), so one heartbeat workflow fires 48 times a
day and dispatches whatever is due, deciding from the real run history, never from a single clock tick.

A task is due in a slot when the slot time has passed today (UTC) and no run of its workflow was created since
that slot. A run that failed is retried after RETRY_AFTER, up to the task's attempts per slot. A condition (work
actually waiting) keeps idle tasks from running at all. Each workflow keeps its own idempotency (ledger, queue,
files of the day), so a duplicate dispatch is harmless; this table only decides when.

usage: heartbeat.py RUNS_JSON CONDITIONS_JSON [NOW_ISO]   (prints one workflow file per line to dispatch)
  RUNS_JSON: {"workflow.yml": [{"createdAt": ISO, "status": "...", "conclusion": "...", "updatedAt": ISO}, ...]}
  CONDITIONS_JSON: {"images_missing": bool, "reconcile_todo": bool, "shorts_pending": bool, "production_idle": bool,
                    "tiktok_pending": bool}
"""
from datetime import datetime, timedelta, timezone
import json
import sys

RETRY_AFTER = timedelta(minutes=45)
# workflow, slots "HH:MM" UTC, attempts per slot, condition, weekdays (Mon=0) or None
TASKS = [
    # Cloudflare's free allocation resets at 00:00 UTC: tries right after it, and once at midday for pilots
    # written during the day (an exhausted allocation fails fast and is not retried before the next slot)
    {"workflow": "nightly-images.yml", "slots": ["00:30", "01:30", "03:30", "12:30"], "attempts": 1, "when": "images_missing"},
    {"workflow": "market-panel.yml", "slots": ["07:17"], "attempts": 2},
    {"workflow": "reconcile.yml", "slots": ["07:20", "10:20", "13:20", "16:20", "19:20", "22:20"], "attempts": 1,
     "when": "reconcile_todo"},
    {"workflow": "publish-shorts.yml", "slots": ["07:35", "13:35", "19:35"], "attempts": 2, "when": "shorts_pending"},
    {"workflow": "goal-report.yml", "slots": ["07:45"], "attempts": 2, "after": "market-panel.yml", "wait_max": "09:30"},
    {"workflow": "channel-privacy.yml", "slots": ["08:05"], "attempts": 1},
    # E90: tiktok.yml's own cron never fired (0 scheduled runs since 2026-10-25); every heartbeat mirrors the next
    # Short already public on YouTube (owner, 2026-10-26: "published on YouTube, it must go to TikTok")
    {"workflow": "tiktok.yml", "slots": [f"{h:02d}:40" for h in range(24)], "attempts": 2, "when": "tiktok_pending"},
]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def at(now, hhmm):
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def slot_now(task, now):
    """The latest slot of today that has passed, or None."""
    passed = [at(now, s) for s in task["slots"] if at(now, s) <= now]
    return max(passed) if passed else None


def decide(runs, conditions, now):
    out = []
    for task in TASKS:
        if task.get("weekdays") is not None and now.weekday() not in task["weekdays"]:
            continue
        slot = slot_now(task, now)
        if slot is None or (task.get("when") and not conditions.get(task["when"])):
            continue
        if task.get("after") and now < at(now, task["wait_max"]):
            before = [r for r in runs.get(task["after"], []) if ts(r["createdAt"]) >= now.replace(hour=0, minute=0, second=0, microsecond=0)]
            if not before or any(r["status"] != "completed" for r in before):
                continue  # the report waits for the panel of the day (at most until wait_max)
        since = sorted((r for r in runs.get(task["workflow"], []) if ts(r["createdAt"]) >= slot), key=lambda r: r["createdAt"])
        if not since:
            out.append(task["workflow"])
        elif (len(since) < task["attempts"] and since[-1]["status"] == "completed" and since[-1]["conclusion"] == "failure"
              and now - ts(since[-1].get("updatedAt") or since[-1]["createdAt"]) >= RETRY_AFTER):
            out.append(task["workflow"])
    return out


def main(runs_json, conditions_json, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    for w in decide(json.load(open(runs_json)), json.load(open(conditions_json)), now):
        print(w)


if __name__ == "__main__":
    main(*sys.argv[1:4])
