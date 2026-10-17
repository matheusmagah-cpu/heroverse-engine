#!/usr/bin/env python3
"""Which pilot has Shorts the watched review approved that are not on YouTube
yet, and at which slots they should go public. Prints "PILOT SLOT,SLOT,..."
or nothing. Slots come from schedule.json while still ahead; otherwise the
daily slots (14:00, 20:00, 23:00 UTC = 11h, 17h, 20h BRT) from now on, always
after the long video opens (each Short links to it).
usage: pending_shorts.py PRODUCTION_DIR LEDGER
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

DAILY = (14, 20, 23)
LEAD = timedelta(minutes=45)


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def slots_for(n, schedule, opens, now):
    floor = max(now + LEAD, opens + timedelta(minutes=30))
    out = [when(s) for s in schedule.get("shorts_slots", []) if when(s) >= floor][:n]
    day = floor.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(out) < n:
        for h in DAILY:
            t = day.replace(hour=h)
            if t >= floor and t not in out and (not out or t > max(out)):
                out.append(t)
                if len(out) == n:
                    break
        day += timedelta(days=1)
    return [iso(t) for t in sorted(out)]


def pending(production, ledger, now=None):
    now = now or datetime.now(timezone.utc)
    entries = ledger.get("entries", {})
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        shorts_path, manifest = d / "shorts" / "shorts.json", d / "out" / "manifest.json"
        if not shorts_path.exists() or not manifest.exists():
            continue
        spec = json.loads(shorts_path.read_text())
        approved = [s for s in spec["shorts"] if s.get("publish") and (s.get("review") or {}).get("status") == "PASS"]
        todo = [s for s in approved if "video_id" not in entries.get(f"short:{spec['source_pilot']}:{s['sha256']}", {})]
        long_entry = entries.get(f"{d.name}:{json.loads(manifest.read_text())['output_sha256']}", {})
        if not todo or "video_id" not in long_entry:
            continue
        schedule = json.loads((d / "schedule.json").read_text()) if (d / "schedule.json").exists() else {}
        opens = when(schedule["publish_at"]) if schedule.get("publish_at") else now
        return d.name, slots_for(len(todo), schedule, opens, now)
    return None


if __name__ == "__main__":
    found = pending(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()))
    if found:
        print(found[0], ",".join(found[1]))
