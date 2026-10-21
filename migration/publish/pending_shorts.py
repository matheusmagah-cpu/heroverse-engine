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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owner_quality_policy

DAILY = (14, 20, 23)
REVIEW_MODELS = ("gemini-3.8-flash",)  # only the designated reviewer's PASS publishes (publish/prepublish_gate.py)


def approved(s):
    r = s.get("review") or {}
    return (s.get("publish") is True and (s.get("qa") or {}).get("status") == "PASS"
            and not owner_quality_policy.check(r, s.get("sha256")))
LEAD = timedelta(minutes=45)


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def slots_for(n, schedule, opens, now, taken=frozenset()):
    """taken: times already used by uploaded Shorts or reserved by another pilot's schedule; a late Short that rolls
    forward never lands on them (two Shorts at the same minute)."""
    floor = max(now + LEAD, opens + timedelta(minutes=30))
    out = [when(s) for s in schedule.get("shorts_slots", []) if when(s) >= floor and when(s) not in taken][:n]
    day = floor.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(out) < n:
        for h in DAILY:
            t = day.replace(hour=h)
            if t >= floor and t not in out and t not in taken and (not out or t > max(out)):
                out.append(t)
                if len(out) == n:
                    break
        day += timedelta(days=1)
    return [iso(t) for t in sorted(out)]


def taken(production, entries, pilot):
    out = {when(e["slot"]) for e in entries.values() if isinstance(e, dict) and e.get("slot")}
    for f in Path(production).glob("pilot-[0-9][0-9][0-9]/schedule.json"):
        first = (json.loads(f.read_text()).get("shorts_slots") or [None])[0]
        if first and f.parent.name != pilot:
            out.add(when(first))
    return out


def recovery_context(spec, pilot_dir):
    """Identify the bounded recovery from trusted directory OR manifest identity."""
    return Path(pilot_dir).name == "pilot-006" or spec.get("source_pilot") == "pilot-006"


def recovery_gate(spec, pilot_dir, now):
    """Pure eligibility guard. An uploaded ID is handled before this gate."""
    import review_recovery as rr
    d = Path(pilot_dir)
    if d.name != rr.PILOT or spec.get("source_pilot") != rr.PILOT:
        raise ValueError("RECOVERY_PILOT_CONTEXT_MISMATCH")
    if ".." in d.parts or any(p.is_symlink() for p in (d, *d.parents)):
        raise ValueError("RECOVERY_PATH_SYMLINK")
    bound = rr.binding(spec)
    if now > when(bound["release_deadline"]):
        raise ValueError("TARGET_SLOT_LEAD_MISSED")
    return bound


def pending(production, ledger, now=None):
    now = now or datetime.now(timezone.utc)
    entries = ledger.get("entries", {})
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        shorts_path, manifest = d / "shorts" / "shorts.json", d / "out" / "manifest.json"
        if not shorts_path.exists() or not manifest.exists():
            continue
        spec = json.loads(shorts_path.read_text())
        ok = [s for s in spec["shorts"] if approved(s)]
        todo = [s for s in ok if "video_id" not in entries.get(f"short:{spec['source_pilot']}:{s['sha256']}", {})]
        long_entry = entries.get(f"{d.name}:{json.loads(manifest.read_text())['output_sha256']}", {})
        if not todo or "video_id" not in long_entry:
            continue
        schedule = json.loads((d / "schedule.json").read_text()) if (d / "schedule.json").exists() else {}
        opens = when(schedule["publish_at"]) if schedule.get("publish_at") else now
        if recovery_context(spec, d):
            try:
                bound = recovery_gate(spec, d, now)
                target = when(bound["target_slot"])
                if (len(todo) != 1 or todo[0]["sha256"] != bound["output_sha256"]
                        or opens + timedelta(minutes=30) > target
                        or target in taken(production, entries, d.name)):
                    continue
            except (ValueError, TypeError, KeyError):
                continue
            return d.name, [bound["target_slot"]]
        return d.name, slots_for(len(todo), schedule, opens, now, taken(production, entries, d.name))
    return None


def states(pilot_dir, ledger, now=None):
    """Every Short of a pilot in exactly one state: failed (QA or watched review not PASS), not_selected (passed,
    left out by the one-Short-per-video rule), approved_awaiting_slot (approved, not uploaded yet), scheduled
    (uploaded, slot ahead) or published (uploaded, slot passed)."""
    now = now or datetime.now(timezone.utc)
    spec = json.loads((Path(pilot_dir) / "shorts" / "shorts.json").read_text())
    entries = ledger.get("entries", {})
    out = []
    recovery_blocked = False
    if recovery_context(spec, pilot_dir):
        try:
            recovery_gate(spec, pilot_dir, now)
        except (ValueError, TypeError, KeyError):
            recovery_blocked = True
    for s in spec["shorts"]:
        entry = entries.get(f"short:{spec['source_pilot']}:{s['sha256']}", {})
        passed = (s.get("review") or {}).get("status") == "PASS" and (s.get("qa") or {}).get("status", "PASS") == "PASS"
        if "video_id" in entry:
            state = "scheduled" if entry.get("slot") and when(entry["slot"]) > now else "published"
        elif recovery_blocked:
            state = "temporal_recovery_blocked"
        elif not passed:
            state = "failed"
        elif not s.get("publish"):
            state = "not_selected"
        elif (s.get("review") or {}).get("model") not in REVIEW_MODELS:
            state = "review_by_undesignated_model"
        elif not approved(s):
            state = "owner_quality_policy_blocked"
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
