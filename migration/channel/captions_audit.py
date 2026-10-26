#!/usr/bin/env python3
"""Caption tracks of the HeroVerse channel: a read-only audit and a reviewed repair (E107).

  audit  : list every upload's caption tracks (captions.list: status serving/syncing/failed, failureReason,
           trackKind, isDraft) and write a receipt with one verdict per video. Read-only: GET calls only.
  repair : for each video of a reviewed plan file, re-upload our English track from the manifest whose hash is the
           video's ledger key (delete our failed track, never the automatic ASR one, insert, then wait for serving).
           Only by hand: channel-privacy.yml mode captions-repair, never the heartbeat.
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
sys.path.insert(0, str(HERE.parent / "publish"))
import captions  # noqa: E402
import publish_video as pv  # noqa: E402

LIST_UNITS = 50
CHANNEL = pv.CHANNEL
PT = ("pt",)


def session():
    return pv.session()


def ledger_sources(ledger_path):
    """video_id -> the engine's source (pilot-008, bible:genesis-01-short, short:pilot-004...)."""
    entries = json.loads(Path(ledger_path).read_text()).get("entries", {})
    return {e["video_id"]: k.rsplit(":", 1)[0] for k, e in entries.items() if e.get("video_id")}


def uploads(s):
    me = pv.check(s.get(pv.API + "channels", params={"part": "id,contentDetails", "mine": "true"}), "CHANNEL")["items"]
    if [c["id"] for c in me] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    playlist = me[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page, units = [], None, 1
    while True:
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50}
        if page:
            params["pageToken"] = page
        res = pv.check(s.get(pv.API + "playlistItems", params=params), "UPLOADS")
        units += 1
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        page = res.get("nextPageToken")
        if not page:
            break
    videos = []
    for start in range(0, len(ids), 50):
        res = pv.check(s.get(pv.API + "videos", params={"part": "snippet,status,contentDetails",
                                                        "id": ",".join(ids[start:start + 50])}), "VIDEOS")
        units += 1
        videos += res.get("items", [])
    return videos, units


def audit(out, ledger_path, scope="engine", units_max=3000, run_id=None):
    s = session()
    sources = ledger_sources(ledger_path)
    videos, units = uploads(s)
    if scope == "engine":
        videos = [v for v in videos if v["id"] in sources]
    elif scope == "english":
        videos = [v for v in videos if not (v["snippet"].get("defaultAudioLanguage") or v["snippet"].get(
            "defaultLanguage") or "").lower().startswith(PT)]
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
    entries = json.loads(Path(ledger_path).read_text()).get("entries", {})
    s = session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    changes = []
    for item in plan.get("to_repair", []):
        vid, pilot = item["video_id"], item["pilot"]
        man = json.loads((root / item["manifest"]).read_text())
        if entries.get(f"{pilot}:{man.get('output_sha256')}", {}).get("video_id") != vid:
            changes.append({"video_id": vid, "pilot": pilot, "result": "SKIPPED_NOT_IN_LEDGER"})
            continue
        text = captions.srt(man.get("sentences") or [])
        bad = captions.problems(text.encode("utf-8"), man.get("output_seconds"))
        if bad:
            changes.append({"video_id": vid, "pilot": pilot, "result": "SRT_INVALID", "problems": bad[:10]})
            continue
        before = captions.ours(pv.caption_tracks(s, vid))
        row = {"video_id": vid, "pilot": pilot, "before": before}
        if before and before["status"] == "serving" and not item.get("force"):
            changes.append(row | {"result": "ALREADY_SERVING"})
            continue
        if before:
            pv.check(s.delete(pv.API + "captions", params={"id": before["id"]}), "CAPTIONS_DELETE")
        new_id = pv.insert_captions(s, vid, man["sentences"], man.get("output_seconds"))
        after = captions.wait(lambda: pv.caption_tracks(s, vid), new_id)
        status = after["status"] if after else "NOT_LISTED"
        result = {"serving": "REPAIRED", "failed": "FAILED_AGAIN"}.get(status, "STILL_SYNCING")
        changes.append(row | {"after": after, "result": result})
    Path(out).write_text(json.dumps({"version": "captions-repair-receipt-v1", "channel_id": CHANNEL,
                                     "plan": Path(plan_path).name, "changes": changes}, indent=1,
                                    ensure_ascii=False) + "\n")
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
