#!/usr/bin/env python3
"""Content runway: the engine must never run out of videos. For every publication slot of the next DAYS days
(night 00:00 UTC, morning 10:00 UTC) report the stage of its pilot and alert when a stage is late:
  no script while the slot is < SCRIPT_LEAD away (Dot needs a card cycle + images + render + gate);
  no render while < RENDER_LEAD away; no APPROVAL.json (gate PASS) while < APPROVAL_LEAD away.
FIRST_NIGHT: the two-a-day format starts with pilot-004 (night of 2026-10-20 00:00); earlier night slots are not alerts.
usage: runway.py PRODUCTION_DIR LEDGER REPORT_MD [NOW_ISO]   (appends to REPORT_MD, prints alerts as JSON)
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

DAYS = 4
FIRST_NIGHT = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
SCRIPT_LEAD, RENDER_LEAD, APPROVAL_LEAD = timedelta(hours=72), timedelta(hours=20), timedelta(hours=6)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def slots(now, days=DAYS):
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(days + 1):
        for h in (0, 10):
            t = day + timedelta(days=i, hours=h)
            if now < t <= now + timedelta(days=days) and (h == 10 or t >= FIRST_NIGHT):
                out.append(t)
    return out


def stage(d, ledger):
    if any(k.startswith(f"{d.name}:") and v.get("video_id") for k, v in ledger.get("entries", {}).items()):
        return "uploaded"
    if (d / "inspection" / "APPROVAL.json").exists():
        return "approved"
    if (d / "out" / "manifest.json").exists():
        return "rendered"
    return "script"


def check(production, ledger, now):
    by_slot = {}
    for f in Path(production).glob("pilot-[0-9][0-9][0-9]/schedule.json"):
        at = json.loads(f.read_text()).get("publish_at")
        if at:
            by_slot[ts(at)] = f.parent
    rows, alerts = [], []
    for t in slots(now):
        d = by_slot.get(t)
        st = stage(d, ledger) if d else "missing"
        left = t - now
        late = ((st == "missing" and left < SCRIPT_LEAD) or (st == "script" and left < RENDER_LEAD)
                or (st == "rendered" and left < APPROVAL_LEAD))
        rows.append({"slot": t.strftime("%Y-%m-%dT%H:%MZ"), "pilot": d.name if d else None, "stage": st, "late": late})
        if late:
            alerts.append(f"{t:%Y-%m-%d %H:%M} UTC ({str(left).split('.')[0]} left): {d.name if d else 'NO PILOT'} is at '{st}'")
    return rows, alerts


def main(production, ledger_path, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows, alerts = check(production, ledger, now)
    md = ["", f"## Content runway (next {DAYS} days; the engine must never run out of videos)",
          *([f"- ⚠ {a}" for a in alerts] or ["- every slot is on time"]),
          "| slot (UTC) | pilot | stage |", "|---|---|---|",
          *(f"| {r['slot']} | {r['pilot'] or '—'} | {r['stage']}{' ⚠' if r['late'] else ''} |" for r in rows)]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": alerts}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
