#!/usr/bin/env python3
"""Content runway of the long videos: the engine must never run out of Bible-story longs.

The committed bible/arcs.json is the authoritative calendar, including moved deadlines (arc-01: 29/10 22:00 UTC).
An overdue arc remains visible until its upload is recorded. A production tree without that calendar uses the older
LONG_EVERY/FIRST_STORY_LONG cadence. Only a Bible-story long counts (script archetype bible-story-long,
render_queue.story_pilot); a prayer pilot never fills a slot, and its retired slots (00:00 and 10:00 every day) are not
slots any more. A story script counts as written only when it follows its registered structure
(structures/bible-story-long.json via the full script_check, structure_problems included: 14-18 min, the conflict spoken in the cold open,
>= 6 re-hooks, the climax at 0.6-0.85, the Keeper <= 25 % and never in the cold open, no burned captions).

For every named arc due by the next DAYS days, report its recorded stage and alert when a stage is late:
  no structured script while the slot is < SCRIPT_LEAD away; no render while < RENDER_LEAD away;
  no APPROVAL.json (gate PASS) while < APPROVAL_LEAD away. A Bible plan is only "planned"; its existence is never
  promoted to a rendered file or an approval. This report does not authorize publication.
usage: runway.py PRODUCTION_DIR LEDGER REPORT_MD [NOW_ISO]   (appends to REPORT_MD, prints alerts as JSON)
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
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


def arc_slots(production, ledger, now, alerts):
    """Use committed deadlines and keep unfulfilled overdue arcs; None means the legacy calendar is in use."""
    production = Path(production)
    calendar = production / "bible/arcs.json"
    if not calendar.exists():
        return None
    out = []
    try:
        arcs = json.loads(calendar.read_text())["arcs"]
        if not isinstance(arcs, list) or not arcs:
            raise ValueError("arcs must be a nonempty list")
        seen = set()
        for arc in arcs:
            arc_id = arc["id"]
            if not isinstance(arc_id, str) or not re.fullmatch(r"arc-[0-9]+", arc_id) or arc_id in seen:
                raise ValueError("invalid or duplicate arc id")
            seen.add(arc_id)
            at = ts(arc["long"]["slot"])
            if at.tzinfo is None:
                raise ValueError("arc slot must include timezone")
            at = at.astimezone(timezone.utc)
            episode = f"{arc_id}-long"
            name, stage = episode, "missing"
            episode_uploaded = any(k.startswith(f"bible:{episode}:") and value.get("video_id")
                                   for k, value in ledger.get("entries", {}).items())
            pilot = arc["long"].get("pilot")
            if episode_uploaded:
                stage = "uploaded"
            elif pilot and isinstance(pilot, str) and re.fullmatch(r"pilot-[0-9]{3}", pilot) and render_queue.story_pilot(production / pilot):
                name = pilot
                stage = long_stage(production / pilot, ledger)[0]
            else:
                plan = render_queue.object_or_empty(production / "bible/plans" / f"{episode}.json")
                if plan.get("version") == "bible-long-plan-v1" and plan.get("episode") == episode:
                    stage = "planned"
            if at <= now + timedelta(days=DAYS) and (at > now or stage != "uploaded"):
                out.append((at, name if stage != "missing" else None, stage))
    except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
        alerts.append(f"LONG_CALENDAR_INVALID {type(error).__name__}: {str(error)[:120]}")
        return []
    return sorted(out)


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
    calendar = arc_slots(production, ledger, now, alerts)
    if calendar is None:
        calendar = [(t, by_slot[t].name if t in by_slot else None,
                     long_stage(by_slot[t], ledger)[0] if t in by_slot else "missing") for t in slots(now)]
    for t, name, st in calendar:
        left = t - now
        late = ((left <= timedelta(0) and st != "uploaded")
                or (st in ("missing", "script-fail", "planned") and left < SCRIPT_LEAD) or (st == "script" and left < RENDER_LEAD)
                or (st == "rendered" and left < APPROVAL_LEAD))
        rows.append({"slot": t.strftime("%Y-%m-%dT%H:%MZ"), "pilot": name, "stage": st, "late": late})
        if late:
            alerts.append(f"{t:%Y-%m-%d %H:%M} UTC ({str(left).split('.')[0]} left): "
                          f"{name or 'NO BIBLE-STORY LONG'} is at '{st}'")
    return rows, alerts



def recovery_rows(production, ledger, now):
    """Read existing target calendar + publication receipts; never schedule, approve or move a target.

    A ledger ID alone is not a schedule/publication readback. A master record alone
    is not QA or audiovisual approval. Receipt confirmation expires after one hour
    for this supervisory report; the publisher must still perform its own live read.
    """
    production = Path(production)
    config = render_queue.object_or_empty(production / "bible/arcs.json").get("recovery")
    if not config:
        return []
    receipts = []
    for path in (production.parent / "publish/receipts").glob("*.json"):
        item = render_queue.object_or_empty(path)
        if item.get("version") == "publish-receipt-v1":
            receipts.append(item)
    rows = []
    for target in config["targets"]:
        episode, at = target["episode"], ts(target["slot"])
        if at > now + timedelta(days=DAYS):
            continue
        record = render_queue.object_or_empty(production / "bible/episodes" / (episode + ".json"))
        sha = record.get("output_sha256")
        keys = {k: v for k, v in ledger.get("entries", {}).items()
                if k.startswith("bible:" + episode + ":") and v.get("video_id")}
        # Long publication can retain its existing pilot ledger identity.
        calendar = render_queue.object_or_empty(production / "bible/arcs.json")
        for arc in calendar.get("arcs", []):
            pilot = arc.get("long", {}).get("pilot")
            if episode == arc["id"] + "-long" and pilot:
                keys.update({k: v for k, v in ledger.get("entries", {}).items()
                             if k.startswith(pilot + ":") and v.get("video_id")})
        confirmed = None
        for item in receipts:
            entry = keys.get(item.get("key"))
            if (not entry or entry["video_id"] != item.get("video_id")
                    or item.get("channel_id") != "UCuMF6pJQkyMzaVoAxFL86yA"
                    or item.get("upload_status") != "processed"):
                continue
            if sha and not item["key"].endswith(":" + sha):
                continue
            try:
                age = now - ts(item["verified_at"])
                if not timedelta(0) <= age <= timedelta(hours=1):
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            if item.get("privacy") == "public" and now >= at:
                confirmed = "PUBLIC_READBACK_CONFIRMED"
                break
            if item.get("privacy") == "private" and item.get("publish_at") == target["slot"] and now < at:
                confirmed = "SCHEDULE_READBACK_CONFIRMED"
        left = at - now
        if confirmed:
            state = confirmed
        elif left <= timedelta(0):
            state = "PUBLIC_READBACK_REQUIRED"
        elif left <= timedelta(hours=config["scheduled_readback_lead_hours"]):
            state = "NOT_SCHEDULED_CONFIRMED"
        elif left <= timedelta(hours=config["master_review_lead_hours"]):
            state = "MASTER_GATES_RECHECK_REQUIRED" if sha else "AT_RISK_NO_MASTER"
        else:
            state = "TARGET_ONLY"
        rows.append({**target, "state": state, "master_recorded": bool(sha),
                     "owner_stage": "publication" if left <= timedelta(hours=2) else "production/review"})
    return rows


def main(production, ledger_path, report_md, now=None):
    now = ts(now) if now else datetime.now(timezone.utc)
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows, alerts = check(production, ledger, now)
    md = ["", f"## Long runway (Bible-story arc deadlines, next {DAYS} days and overdue uploads; "
              "prayer longs stopped 2026-10-26)",
          *([f"- ⚠ {a}" for a in alerts] or ["- every long slot is on time"]),
          "| slot (UTC) | pilot | stage |", "|---|---|---|",
          *(f"| {r['slot']} | {r['pilot'] or '—'} | {r['stage']}{' ⚠' if r['late'] else ''} |" for r in rows)]
    recovery = recovery_rows(production, ledger, now)
    if recovery:
        md += ["", "## Recovery targets (no YouTube scheduling or media approval implied)",
               "Receipt confirmations require a matching processed ID/hash/channel and a readback within one hour. "
               "Makeups require the approved extra, both next-day regular Shorts ready and the long protected; "
               "move only the extra after an ineligible window. No episode is skipped.",
               "| target (UTC) | content | type | observed state | responsible stage |",
               "|---|---|---|---|---|",
               *(f"| {r['slot']} | {r['episode']} | {r['kind']} | {r['state']} | {r['owner_stage']} |" for r in recovery)]
    with open(report_md, "a") as f:
        f.write("\n".join(md) + "\n")
    print(json.dumps({"alerts": alerts}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
