#!/usr/bin/env python3
"""The nightly queue: which pilots need images, and which one to render next.

A pilot is due when its schedule.json opens within HORIZON hours and it is not
yet on YouTube. It needs images while any image its script uses has no
images/<id>.json record; it needs a render when its images are complete and no
completed frozen-v3 render exists for the current script and matching output hash.
A completed v3 QA FAIL is not rerendered repeatedly; it awaits an input correction.
usage: render_queue.py PRODUCTION_DIR LEDGER {images|render|reconcile} [HOURS]
  images: prints "PILOT id,id,..." for every pilot with images still missing
  render: prints the next pilot to render (earliest publish time) or nothing
  stale: prints "STALE PILOT PUBLISH_AT" for pilots whose slot passed more than 6 h ago (within STALE_DAYS) and that
         have no video on YouTube: due() no longer sees them, so they must be rescheduled (E49)
  reconcile: prints "approve PILOT" (QA PASS, no approval, review missing or ERROR, or final decision UNKNOWN),
  "shorts PILOT" (Shorts inputs handed off, Shorts never made) and
             "publish PILOT" (approved for this file, not on YouTube) so failed steps are retried
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publish"))
from shorts_prerequisite import ready as shorts_ready


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def needed_images(d, script):
    spec = json.loads((d / "images.json").read_text()) if (d / "images.json").exists() else {"images": []}
    ids = {i["id"] for i in spec["images"]} | set(script["backgrounds"]) | {script["figure"], script["overlay"]["title_image"]}
    return sorted(i for i in ids if not (d / "images" / f"{i}.json").exists())


STANDARD_QA = "pilot-qa-criteria-v3"  # migration/STANDARD.md v1: the only renders that may be approved or published
# v4 (owner, 2026-10-23: licensed real footage) is the same standard with the footage grammar; both may publish
STANDARD_QAS = {"pilot-qa-criteria-v3": "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3",
                "pilot-qa-criteria-v4": "6b7c5e4bdb5537d4ecb0cad64ab5a9ceda8a8c6c3fbd970d6425819d04cd27af"}

STANDARD_QA_SHA256 = "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3"


def object_or_empty(path):
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def current_render(manifest, qa, script_sha):
    """Completed current render, not a publication verdict. FAIL must not loop."""
    if not isinstance(manifest, dict) or not isinstance(qa, dict):
        return False
    output = manifest.get("output_sha256")
    return (isinstance(output, str) and re.fullmatch(r"[0-9a-f]{64}", output) is not None
            and manifest.get("script_sha256") == script_sha
            and qa.get("output_sha256") == output
            and qa.get("criteria_version") in STANDARD_QAS
            and qa.get("criteria_sha256") == STANDARD_QAS[qa.get("criteria_version")]
            and qa.get("status") in ("PASS", "FAIL"))


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
        m = object_or_empty(manifest)
        if m and "video_id" in entries.get(f"{d.name}:{m.get('output_sha256')}", {}):
            continue  # already on YouTube
        script_sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        out.append({"pilot": d.name, "publish_at": t, "missing_images": needed_images(d, json.loads((d / "script.json").read_text())),
                    "rendered": current_render(m, object_or_empty(d / "out" / "qa.json"), script_sha)})
    return sorted(out, key=lambda x: x["publish_at"])


STALE_DAYS = 7


def stale(production, ledger, now, days=STALE_DAYS):
    """E49: pilot-008..011 left the queue silently once their slot was more than 6 h old (the reviewer returned 503
    and two renders failed QA), and nothing reported it for a day. Any ledger entry with a video_id for the pilot
    counts as published, whichever render it came from."""
    entries = ledger.get("entries", {})
    out = []
    for d in sorted(Path(production).glob("pilot-[0-9][0-9][0-9]")):
        if not (d / "schedule.json").exists() or not (d / "script.json").exists():
            continue
        t = when(json.loads((d / "schedule.json").read_text())["publish_at"])
        if not now - timedelta(days=days) <= t < now - timedelta(hours=6):
            continue
        if any(k.split(":", 1)[0] == d.name and "video_id" in v for k, v in entries.items()):
            continue
        qa = object_or_empty(d / "out" / "qa.json")
        if qa and qa.get("criteria_version") not in STANDARD_QAS:
            continue  # rendered before migration/STANDARD.md: retired, never published (pilot-003)
        out.append({"pilot": d.name, "publish_at": t})
    return out


def reviewed_shorts(path):
    """True when Shorts exist and at least one got a verdict (PASS or FAIL) from the watched review; Shorts left
    unreviewed (provider quota or error, NOT_REVIEWED_*) are made again."""
    if not path.exists():
        return False
    return any((s.get("review") or {}).get("status") in ("PASS", "FAIL") for s in json.loads(path.read_text())["shorts"])


HOLD = Path(__file__).resolve().parents[1] / "ops" / "PUBLICATION_HOLD"
# while present, the runner renders nothing (e.g. scripts are being moved to a new standard: a render of the old
# script would only be thrown away and would hold the single runner for ~2 h)
RENDER_HOLD = Path(__file__).resolve().parents[1] / "ops" / "RENDER_HOLD"
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
    if mode == "stale":
        for r in stale(production, ledger, now):
            print("STALE", r["pilot"], r["publish_at"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    elif mode == "images":  # "PILOT id,id": only the images still missing (never regenerate a recorded one)
        for r in rows:
            if r["missing_images"]:
                print(r["pilot"], ",".join(r["missing_images"]))
    elif mode == "reconcile" and HOLD.exists():
        print("PUBLICATION_HOLD", file=sys.stderr)  # owner pause: no approval, publication or Shorts is dispatched
    elif mode == "reconcile":
        # E25: approve.yml keeps ONE pending run (concurrency group): dispatching several approvals cancels all but the
        # last, i.e. the farthest slot. So only the earliest due approval is sent, and Shorts wait until no approval is
        # pending, because both spend the same free Gemini quota and the long video publishes first.
        approve, publish, shorts = [], [], []
        long_quota_pending = False
        for r in rows:
            d = Path(production) / r["pilot"]
            try:
                qa = json.loads((d / "out" / "qa.json").read_text())
            except (FileNotFoundError, ValueError):
                continue
            if not r["rendered"] or qa.get("status") != "PASS":
                continue
            if qa.get("criteria_version") not in STANDARD_QAS:
                continue  # renders made before migration/STANDARD.md (owner: "amateur") are never approved or published
            ap = json.loads((d / "inspection" / "APPROVAL.json").read_text()) if (d / "inspection" / "APPROVAL.json").exists() else {}
            rev = json.loads((d / "out" / "review.json").read_text()) if (d / "out" / "review.json").exists() else {}
            gate = json.loads((d / "out" / "gate.json").read_text()) if (d / "out" / "gate.json").exists() else {}
            unknown = gate.get("output_sha256") == qa["output_sha256"] and gate.get("decision") == "UNKNOWN"
            if ap.get("approved") and ap.get("output_sha256") == qa["output_sha256"]:
                publish.append(r["pilot"])  # due rows are never already on YouTube
            elif quota_spent(rev, now):
                long_quota_pending = True  # reserve shared review quota for the waiting long
            elif rev.get("output_sha256") != qa["output_sha256"] or rev.get("status") == "ERROR" or unknown:
                approve.append(r["pilot"])
            # Shorts handed off by the render but never made (provider quota or error): made again
            if (d / "shorts" / "inputs.json").exists() and not reviewed_shorts(d / "shorts" / "shorts.json") and shorts_ready(d):
                shorts.append(r["pilot"])
        for p in publish:
            print("publish", p)
        if approve:
            print("approve", approve[0])  # rows are sorted by publish time: the earliest slot first
        elif not long_quota_pending:
            for p in shorts:
                print("shorts", p)
    elif RENDER_HOLD.exists():
        print("RENDER_HOLD", file=sys.stderr)
    else:
        nxt = next((r for r in rows if not r["missing_images"] and not r["rendered"]), None)
        if nxt:
            print(nxt["pilot"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
