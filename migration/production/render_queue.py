#!/usr/bin/env python3
"""The nightly queue: which pilots need images, and which one to render next.

A pilot is due when its schedule.json opens within HORIZON hours and it is not
yet on YouTube. It needs images while any image its script uses has no
images/<id>.json record; it needs a render when its images are complete and no
render manifest exists for the current script (manifest.script_sha256).
usage: render_queue.py PRODUCTION_DIR LEDGER {images|render|reconcile} [HOURS]
  images: prints "PILOT id,id,..." for every pilot with images still missing
  render: prints the next pilot to render (earliest publish time) or nothing
  reconcile: prints "approve PILOT" (QA PASS, no approval, review missing or ERROR, or final decision UNKNOWN),
  "shorts PILOT" (Shorts inputs handed off, Shorts never made) and
             "publish PILOT" (approved for this file, not on YouTube) so failed steps are retried
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def needed_images(d, script):
    spec = json.loads((d / "images.json").read_text()) if (d / "images.json").exists() else {"images": []}
    ids = {i["id"] for i in spec["images"]} | set(script["backgrounds"]) | {script["figure"], script["overlay"]["title_image"]}
    return sorted(i for i in ids if not (d / "images" / f"{i}.json").exists())


def due(production, ledger, now, hours):
    entries = ledger.get("entries", {})
    out = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        if not (d / "schedule.json").exists() or not (d / "script.json").exists():
            continue
        t = when(json.loads((d / "schedule.json").read_text())["publish_at"])
        if not now - timedelta(hours=6) <= t <= now + timedelta(hours=hours):
            continue
        manifest = d / "out" / "manifest.json"
        m = json.loads(manifest.read_text()) if manifest.exists() else {}
        if m and "video_id" in entries.get(f"{d.name}:{m.get('output_sha256')}", {}):
            continue  # already on YouTube
        script_sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        out.append({"pilot": d.name, "publish_at": t, "missing_images": needed_images(d, json.loads((d / "script.json").read_text())),
                    "rendered": m.get("script_sha256") == script_sha})
    return sorted(out, key=lambda x: x["publish_at"])


def reviewed_shorts(path):
    """True when Shorts exist and at least one got a verdict (PASS or FAIL) from the watched review; Shorts left
    unreviewed (provider quota or error, NOT_REVIEWED_*) are made again."""
    if not path.exists():
        return False
    return any((s.get("review") or {}).get("status") in ("PASS", "FAIL") for s in json.loads(path.read_text())["shorts"])


RETRY_AFTER = timedelta(minutes=30)


def quota_spent(rev, now):
    """True while a retry would only hit the same quota again. E29: only a quota the provider names as per day
    (quotaId containing "PerDay") waits for the 07:00 UTC reset; a per-minute or unnamed quota waits RETRY_AFTER,
    never a whole day (pilot-003 waited 5 h on 2026-10-19 while pilot-004 was approved on the same quota)."""
    if rev.get("status") != "ERROR" or "QUOTA" not in str(rev.get("error", "")) or not rev.get("failed_at"):
        return False
    failed = datetime.fromisoformat(rev["failed_at"].replace("Z", "+00:00"))
    if any("PerDay" in q for q in rev.get("quota_ids") or []):
        reset = now.replace(hour=7, minute=0, second=0, microsecond=0)
        if now < reset:
            reset -= timedelta(days=1)
        return failed >= reset
    return now - failed < RETRY_AFTER


def main(production, ledger_path, mode, hours="48"):
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    now = datetime.now(timezone.utc)
    rows = due(production, ledger, now, int(hours))
    if mode == "images":  # "PILOT id,id": only the images still missing (never regenerate a recorded one)
        for r in rows:
            if r["missing_images"]:
                print(r["pilot"], ",".join(r["missing_images"]))
    elif mode == "reconcile":
        # E25: approve.yml keeps ONE pending run (concurrency group): dispatching several approvals cancels all but the
        # last, i.e. the farthest slot. So only the earliest due approval is sent, and Shorts wait until no approval is
        # pending, because both spend the same free Gemini quota and the long video publishes first.
        approve, publish, shorts = [], [], []
        for r in rows:
            d = Path(production) / r["pilot"]
            try:
                qa = json.loads((d / "out" / "qa.json").read_text())
            except (FileNotFoundError, ValueError):
                continue
            if not r["rendered"] or qa.get("status") != "PASS":
                continue
            ap = json.loads((d / "inspection" / "APPROVAL.json").read_text()) if (d / "inspection" / "APPROVAL.json").exists() else {}
            rev = json.loads((d / "out" / "review.json").read_text()) if (d / "out" / "review.json").exists() else {}
            gate = json.loads((d / "out" / "gate.json").read_text()) if (d / "out" / "gate.json").exists() else {}
            unknown = gate.get("output_sha256") == qa["output_sha256"] and gate.get("decision") == "UNKNOWN"
            if ap.get("approved") and ap.get("output_sha256") == qa["output_sha256"]:
                publish.append(r["pilot"])  # due rows are never already on YouTube
            elif quota_spent(rev, now):
                pass  # the free Gemini quota resets at 07:00 UTC; retrying before that only spends Actions minutes
            elif rev.get("output_sha256") != qa["output_sha256"] or rev.get("status") == "ERROR" or unknown:
                approve.append(r["pilot"])
            # Shorts handed off by the render but never made (provider quota or error): made again
            if (d / "shorts" / "inputs.json").exists() and not reviewed_shorts(d / "shorts" / "shorts.json"):
                shorts.append(r["pilot"])
        for p in publish:
            print("publish", p)
        if approve:
            print("approve", approve[0])  # rows are sorted by publish time: the earliest slot first
        else:
            for p in shorts:
                print("shorts", p)
    else:
        nxt = next((r for r in rows if not r["missing_images"] and not r["rendered"]), None)
        if nxt:
            print(nxt["pilot"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
