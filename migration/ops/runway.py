#!/usr/bin/env python3
"""Content runway of the long videos: the engine must never run out of Bible-story longs.

The long cadence (owner, 2026-10-26: "stop the prayer videos; the channel is going in another direction"; SERIES.md
calendar): one Bible-story long every LONG_EVERY days at 10:00 UTC from FIRST_STORY_LONG (29/10 10:00), so never more
than LONG_EVERY days between two longs. Only a Bible-story long counts (script archetype bible-story-long,
render_queue.story_pilot); a prayer pilot never fills a slot, and its retired slots (00:00 and 10:00 every day) are not
slots any more. A story script counts as written only when it follows its registered structure
(structures/bible-story-long.json via the full script_check, structure_problems included: 14-18 min, the conflict spoken in the cold open,
>= 6 re-hooks, the climax at 0.6-0.85, the Keeper <= 25 % and never in the cold open, no burned captions).

For every long slot of the next DAYS days, report the stage of its pilot and alert when a stage is late:
  no structured script while the slot is < SCRIPT_LEAD away; no render while < RENDER_LEAD away;
  no APPROVAL.json (gate PASS) while < APPROVAL_LEAD away.
usage: runway.py PRODUCTION_DIR LEDGER REPORT_MD [NOW_ISO]   (appends to REPORT_MD, prints alerts as JSON)
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
import render_queue  # noqa: E402  (story_pilot: the one test of "this is a Bible-story long")
import script_check  # noqa: E402  (structure_problems: the registered beat map)

DAYS = 6
LONG_EVERY = timedelta(days=2)                                    # SERIES.md: the long every other day
FIRST_STORY_LONG = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)   # arc 1 (owner 28/10: arc-01 on 29/10, then every other day)
# owner 2026-10-19: approval (gate PASS) one full day ahead, so a provider hiccup or a FAIL has a day to be fixed
# without missing the slot; the render comes 12 h before that (E24)
SCRIPT_LEAD, RENDER_LEAD, APPROVAL_LEAD = timedelta(hours=72), timedelta(hours=36), timedelta(hours=24)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def slots(now, days=DAYS):
    """The Bible-story long slots in (now, now + days]."""
    t = FIRST_STORY_LONG
    if now > t:
        t += LONG_EVERY * ((now - t) // LONG_EVERY)
    out = []
    while t <= now + timedelta(days=days):
        if t > now:
            out.append(t)
        t += LONG_EVERY
    return out


def uploaded(d, ledger):
    return any(k.startswith(f"{Path(d).name}:") and v.get("video_id") for k, v in ledger.get("entries", {}).items())


def long_stage(d, ledger):
    """The one stage rule of a Bible-story long, shared by this runway and the daily report (goal_report.py):
    uploaded > approved > rendered (a long past its script is never re-judged by later gate fields) > "script" only
    when the full script_check passes (structure included) > "script-fail" with its problems. Never raises: an
    unreadable script is a "script-fail"."""
    d = Path(d)
    if uploaded(d, ledger):
        return "uploaded", []
    if (d / "inspection" / "APPROVAL.json").exists():
        return "approved", []
    if (d / "out" / "manifest.json").exists():
        return "rendered", []
    try:
        problems = list(script_check.check(d, d.parent)[0])
    except Exception as e:  # a malformed file must not crash the report; it is a failed script
        problems = [f"SCRIPT_CHECK_ERROR {type(e).__name__}: {str(e)[:120]}"]
    return ("script-fail", problems) if problems else ("script", [])


def check(production, ledger, now):
    by_slot, alerts = {}, []
    for f in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]/schedule.json")):
        sched = render_queue.object_or_empty(f)
        try:
            at = ts(sched["publish_at"])
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if render_queue.story_pilot(f.parent):
            by_slot[at] = f.parent
        elif at > now:
            # review of #415: a prayer long with a pending slot is shown, never dropped silently
            state = "uploaded" if uploaded(f.parent, ledger) else "not uploaded"
            alerts.append(f"PRAYER_LONG_SCHEDULED {f.parent.name} at {at:%Y-%m-%d %H:%M} UTC ({state}; prayer longs "
                          "stopped 2026-10-26: hold the upload with channel-privacy.yml unschedule and retire its "
                          "schedule.json)")
    rows = []
    for t in slots(now):
        d = by_slot.get(t)
        st = long_stage(d, ledger)[0] if d else "missing"
        left = t - now
        late = ((st in ("missing", "script-fail") and left < SCRIPT_LEAD) or (st == "script" and left < RENDER_LEAD)
                or (st == "rendered" and left < APPROVAL_LEAD))
        rows.append({"slot": t.strftime("%Y-%m-%dT%H:%MZ"), "pilot": d.name if d else None, "stage": st, "late": late})
        if late:
            alerts.append(f"{t:%Y-%m-%d %H:%M} UTC ({str(left).split('.')[0]} left): "
                          f"{d.name if d else 'NO BIBLE-STORY LONG'} is at '{st}'")
    return rows, alerts


def main(production, ledger_path, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows, alerts = check(production, ledger, now)
    md = ["", f"## Long runway (Bible-story longs, one every {LONG_EVERY.days} days at 10:00 UTC; next {DAYS} days; "
              "prayer longs stopped 2026-10-26)",
          *([f"- ⚠ {a}" for a in alerts] or ["- every long slot is on time"]),
          "| slot (UTC) | pilot | stage |", "|---|---|---|",
          *(f"| {r['slot']} | {r['pilot'] or '—'} | {r['stage']}{' ⚠' if r['late'] else ''} |" for r in rows)]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": alerts}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
