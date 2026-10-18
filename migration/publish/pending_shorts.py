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


def states(pilot_dir, ledger, now=None):
    """Every Short of a pilot in exactly one state: failed (QA or watched review not PASS), not_selected (passed,
    left out by the one-Short-per-video rule), approved_awaiting_slot (approved, not uploaded yet), scheduled
    (uploaded, slot ahead) or published (uploaded, slot passed)."""
    now = now or datetime.now(timezone.utc)
    spec = json.loads((Path(pilot_dir) / "shorts" / "shorts.json").read_text())
    entries = ledger.get("entries", {})
    out = []
    for s in spec["shorts"]:
        entry = entries.get(f"short:{spec['source_pilot']}:{s['sha256']}", {})
        passed = (s.get("review") or {}).get("status") == "PASS" and (s.get("qa") or {}).get("status", "PASS") == "PASS"
        if "video_id" in entry:
            state = "scheduled" if entry.get("slot") and when(entry["slot"]) > now else "published"
        elif not passed:
            state = "failed"
        elif not s.get("publish"):
            state = "not_selected"
        else:
            state = "approved_awaiting_slot"
        out.append({"file": s["file"], "sha256": s["sha256"], "state": state, "video_id": entry.get("video_id")})
    return out


def todo_files(pilot_dir, ledger):
    """file and sha256 of the approved Shorts still to upload (the only files a publish run downloads)."""
    return [(r["file"], r["sha256"]) for r in states(pilot_dir, ledger) if r["state"] == "approved_awaiting_slot"]


if __name__ == "__main__":
    if sys.argv[1] == "--todo":  # pending_shorts.py --todo PILOT_DIR LEDGER
        for f, sha in todo_files(sys.argv[2], json.loads(Path(sys.argv[3]).read_text())):
            print(f, sha)
        sys.exit(0)
    if sys.argv[1] == "--states":  # pending_shorts.py --states PILOT_DIR LEDGER
        print(json.dumps(states(sys.argv[2], json.loads(Path(sys.argv[3]).read_text()))))
        sys.exit(0)
    found = pending(sys.argv[1], json.loads(Path(sys.argv[2]).read_text()))
    if found:
        print(found[0], ",".join(found[1]))
