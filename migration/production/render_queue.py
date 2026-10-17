#!/usr/bin/env python3
"""The nightly queue: which pilots need images, and which one to render next.

A pilot is due when its schedule.json opens within HORIZON hours and it is not
yet on YouTube. It needs images while any image its script uses has no
images/<id>.json record; it needs a render when its images are complete and no
render manifest exists for the current script (manifest.script_sha256).
usage: render_queue.py PRODUCTION_DIR LEDGER {images|render} [HOURS]
  images: prints "PILOT id,id,..." for every pilot with images still missing
  render: prints the next pilot to render (earliest publish time) or nothing
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


def main(production, ledger_path, mode, hours="48"):
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {}
    rows = due(production, ledger, datetime.now(timezone.utc), int(hours))
    if mode == "images":  # "PILOT id,id": only the images still missing (never regenerate a recorded one)
        for r in rows:
            if r["missing_images"]:
                print(r["pilot"], ",".join(r["missing_images"]))
    else:
        nxt = next((r for r in rows if not r["missing_images"] and not r["rendered"]), None)
        if nxt:
            print(nxt["pilot"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
