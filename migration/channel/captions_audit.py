#!/usr/bin/env python3
"""Caption tracks of the HeroVerse channel: a read-only audit and a reviewed repair (E107).

  audit  : list every upload's caption tracks (captions.list: status serving/syncing/failed, failureReason,
           trackKind, isDraft) and write a receipt with one verdict per video. Read-only: GET calls only.
  repair : for each video of a reviewed plan file, re-upload our English track from the manifest whose hash is the
           video's ledger key (delete our failed track, never the automatic ASR one, insert, then wait for serving).
           The publish ledger entry follows each step, so publish_video never polls a deleted track; the receipt is
           written after every delete and insert. Only by hand: channel-privacy.yml mode captions-repair.
Quota: captions.list is 50 units a video, so the audit stops at UNITS_MAX and lists what it left out.
The receipts hold ids, titles, statuses and counts; never the token or any header.
usage: captions_audit.py audit OUT_JSON LEDGER [SCOPE engine|english|all] [UNITS_MAX]
       captions_audit.py repair PLAN_JSON OUT_RECEIPT LEDGER
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "publish"))
import captions  # noqa: E402
import channel_privacy as cp  # noqa: E402
import publish_video as pv  # noqa: E402

LIST_UNITS = 50
CHANNEL = pv.CHANNEL
# a repair run must end inside channel-privacy.yml's timeout-minutes (a test ties JOB_SECONDS to it): each track
# waits at most WAIT_CALLS x WAIT_SECONDS, plus its delete, insert and listings
JOB_SECONDS = 30 * 60
MARGIN_SECONDS = 5 * 60          # setup (venv, pip) and the commit
SECONDS_PER_TRACK = captions.WAIT_CALLS * captions.WAIT_SECONDS + 60
MAX_PLAN = (JOB_SECONDS - MARGIN_SECONDS) // SECONDS_PER_TRACK


def session():
    return pv.session()


def ledger_sources(ledger_path):
    """video_id -> the engine's source (pilot-008, bible:genesis-01-short, short:pilot-004...)."""
    entries = json.loads(Path(ledger_path).read_text()).get("entries", {})
    return {e["video_id"]: k.rsplit(":", 1)[0] for k, e in entries.items() if e.get("video_id")}


def uploads(s):
    """Every upload of the exact channel, through channel_privacy's one paging helper. Returns (videos, units)."""
    return cp.channel_uploads(lambda endpoint, params: pv.check(s.get(pv.API + endpoint, params=params),
                                                                endpoint.upper()), "snippet,status,contentDetails")


def audit(out, ledger_path, scope="engine", units_max=3000, run_id=None):
    s = session()
    sources = ledger_sources(ledger_path)
    videos, units = uploads(s)
    if scope == "engine":
        videos = [v for v in videos if v["id"] in sources]
    elif scope == "english":
        videos = [v for v in videos if cp.language(v) != "pt"]   # the channel's one language rule
    elif scope != "all":
        raise SystemExit("CAPTIONS_AUDIT_SCOPE (engine, english or all)")
    rows, skipped = [], []
    for v in videos:
        if units + LIST_UNITS > units_max:
            skipped.append(v["id"])
            continue
        listing = pv.check(s.get(pv.API + "captions", params={"part": "snippet", "videoId": v["id"]}), "CAPTIONS_LIST")
        units += LIST_UNITS
        found = captions.tracks(listing)
        rows.append({"video_id": v["id"], "source": sources.get(v["id"]), "title": v["snippet"].get("title"),
                     "privacy": v.get("status", {}).get("privacyStatus"),
                     "publish_at": v.get("status", {}).get("publishAt"),
                     "upload_status": v.get("status", {}).get("uploadStatus"),
                     "duration": v.get("contentDetails", {}).get("duration"),
                     "verdict": captions.verdict(found), "tracks": found})
    by = {}
    for r in rows:
        by.setdefault(r["verdict"], []).append(r["video_id"])
    record = {"version": "captions-audit-v1", "channel_id": CHANNEL, "run_id": run_id,
              "audited_at": datetime.now(timezone.utc).isoformat(), "scope": scope, "units_spent": units,
              "units_max": units_max, "audited": len(rows), "by_verdict": by,
              "not_audited_unit_cap": skipped, "videos": rows}
    Path(out).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"audited": len(rows), "units_spent": units, "not_audited": len(skipped),
                      "by_verdict": {k: len(v) for k, v in by.items()}, "failed": by.get("FAILED", [])}))
    for vid in by.get("FAILED", []):
        print(f"::warning::CAPTIONS_FAILED {vid}: see the audit receipt; repair only through a reviewed plan")
    return record


def repair(plan_path, out, ledger_path, root=None):
    root = Path(root) if root else HERE.parents[1]
    plan = json.loads(Path(plan_path).read_text())
    if plan.get("channel_id") != CHANNEL:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    if len(plan.get("to_repair", [])) > MAX_PLAN:
        raise SystemExit(f"CAPTIONS_REPAIR_PLAN_TOO_LONG ({len(plan['to_repair'])} > {MAX_PLAN} tracks a run)")
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    entries = ledger.get("entries", {})
    changes = []

    def flush():  # after every delete and insert: a timeout or an exception never loses what was done
        Path(out).write_text(json.dumps({"version": "captions-repair-receipt-v1", "channel_id": CHANNEL,
                                         "plan": Path(plan_path).name, "changes": changes}, indent=1,
                                        ensure_ascii=False) + "\n")
        ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")

    s = session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    for item in plan.get("to_repair", []):
        vid, pilot = item["video_id"], item["pilot"]
        man = json.loads((root / item["manifest"]).read_text())
        key = f"{pilot}:{man.get('output_sha256')}"
        if entries.get(key, {}).get("video_id") != vid:
            changes.append({"video_id": vid, "pilot": pilot, "result": "SKIPPED_NOT_IN_LEDGER"})
            flush()
            continue
        steps = entries[key].setdefault("steps", {})
        bad = pv.srt_problems(man)
        if bad:
            changes.append({"video_id": vid, "pilot": pilot, "result": "SRT_INVALID", "problems": bad[:10]})
            flush()
            continue
        before = captions.ours(pv.caption_tracks(s, vid))
        row = {"video_id": vid, "pilot": pilot, "before": before}
        changes.append(row)
        if before and before["status"] == "serving" and not item.get("force"):
            row["result"] = "ALREADY_SERVING"
            steps.update({"captions": True, "captions_track": before["id"], "captions_status": "serving"})
            steps.pop("captions_failure_reason", None)
            flush()
            continue
        if before:
            pv.check(s.delete(pv.API + "captions", params={"id": before["id"]}), "CAPTIONS_DELETE")
            row.update({"deleted": before["id"], "result": "DELETED_NOT_REINSERTED"})
            steps.update({"captions_track": before["id"], "captions_status": "deleted"})
            flush()
        new_id = pv.insert_captions(s, vid, man["sentences"], man.get("output_seconds"), man.get("caption_track"))
        row.update({"inserted": new_id, "result": "INSERTED_NOT_VERIFIED"})
        steps.update({"captions": True, "captions_track": new_id, "captions_status": "inserted"})
        for k in ("captions_failure_reason", "captions_srt_invalid"):
            steps.pop(k, None)
        flush()
        after = captions.wait(lambda: pv.caption_tracks(s, vid), new_id)
        status = after["status"] if after else "not_listed"
        row.update({"after": after, "result": {"serving": "REPAIRED", "failed": "FAILED_AGAIN"}.get(status, "STILL_SYNCING")})
        steps["captions_status"] = status
        if after and after.get("failure_reason"):
            steps["captions_failure_reason"] = after["failure_reason"]
        flush()
    flush()
    print(json.dumps({"changes": [{k: c.get(k) for k in ("video_id", "pilot", "result")} for c in changes]}))
    if any(c["result"] not in ("REPAIRED", "ALREADY_SERVING", "STILL_SYNCING") for c in changes):
        raise SystemExit("CAPTIONS_REPAIR_INCOMPLETE")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "audit":
        audit(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "engine",
              int(sys.argv[5]) if len(sys.argv) > 5 else 3000, os.environ.get("GITHUB_RUN_ID"))
    elif len(sys.argv) == 5 and sys.argv[1] == "repair":
        repair(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
