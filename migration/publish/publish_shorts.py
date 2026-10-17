#!/usr/bin/env python3
"""Publish the Shorts cut from a published long video, each scheduled at its slot.

Gates, all BEFORE upload (owner rule): the long video is already in the ledger
(uploaded, public or scheduled) so every Short can point to it; each Short
passes shorts_qa (vertical 1080x1920, 15-60 s, loudness, true peak, decode) and
its file hash matches shorts.json. Idempotent per Short hash through the same
ledger as publish_video.py. The Data API has no field for the Shorts "related
video", so the link to the full video is the first line of the description.
usage: publish_shorts.py SHORTS_JSON SHORTS_DIR LONG_KEY LEDGER RECEIPT SLOT_ISO[,SLOT_ISO...]
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402
import shorts_qa  # noqa: E402


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def title_for(short):
    if short.get("title") and short["title"] != short.get("hook"):
        t = short["title"].strip()
        return t if "#shorts" in t.lower() or len(t) > 90 else t + " #shorts"
    hook = short["hook"].rstrip(".!?")
    title = f"{hook} 🙏 #shorts"
    return title if len(title) <= 100 else hook[:88] + "… #shorts"


def description_for(short, long_url, long_title):
    ref = f"\n\n📖 {short['reference']}" if short.get("reference") else ""
    return (f"▶ Full prayer: {long_url}\n{long_title}{ref}\n\n"
            "Pray this with me and type AMEN if you receive it.\n\n#prayer #morningprayer #jesus #faith #shorts")


def main(shorts_json, shorts_dir, long_key, ledger_path, receipt_path, slots):
    spec = json.loads(Path(shorts_json).read_text())
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    long_entry = ledger["entries"].get(long_key)
    if not long_entry or "video_id" not in long_entry:
        raise SystemExit("LONG_VIDEO_NOT_PUBLISHED")
    slots = [s for s in slots.split(",") if s]
    if len(slots) < len(spec["shorts"]):
        raise SystemExit("NOT_ENOUGH_SLOTS")
    spec["shorts"] = [r for r in spec["shorts"] if r.get("publish")]
    if not spec["shorts"]:
        raise SystemExit("NO_SHORT_APPROVED_BY_REVIEW")
    reports = []
    for short in spec["shorts"]:
        if (short.get("review") or {}).get("status") != "PASS":
            raise SystemExit("SHORT_NOT_REVIEWED_PASS " + short["file"])
        path = Path(shorts_dir) / short["file"]
        if sha256_file(path) != short["sha256"]:
            raise SystemExit("SHORT_HASH_MISMATCH " + short["file"])
        report = shorts_qa.check(path)
        reports.append(report)
        if report["status"] != "PASS":
            raise SystemExit("SHORT_QA_FAIL " + json.dumps(report))
    s = pv.session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    long_id = long_entry["video_id"]
    long = pv.check(s.get(pv.API + "videos", params={"part": "snippet", "id": long_id}), "LONG")["items"][0]
    out = []
    for short, slot, report in zip(spec["shorts"], slots, reports):
        key = f"short:{spec['source_pilot']}:{short['sha256']}"
        entry = ledger["entries"].get(key, {"steps": {}})
        if "video_id" not in entry:
            body = {"snippet": {"title": title_for(short), "description": description_for(short, f"https://youtu.be/{long_id}", long["snippet"]["title"]),
                                "tags": ["prayer", "morning prayer", "jesus", "faith", "bible", "shorts"],
                                "categoryId": "22", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                    "status": {"privacyStatus": "private", "publishAt": slot, "selfDeclaredMadeForKids": False,
                               "embeddable": True, "license": "youtube", "publicStatsViewable": True,
                               "containsSyntheticMedia": True}}
            entry.update({"video_id": pv.upload(s, Path(shorts_dir) / short["file"], body)["id"],
                          "uploaded_at": datetime.now(timezone.utc).isoformat(), "long_video_id": long_id, "slot": slot,
                          "qa": report})
            ledger["entries"][key] = entry
            ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")  # durable before any further step
        st = pv.check(s.get(pv.API + "videos", params={"part": "status", "id": entry["video_id"]}), "VERIFY")["items"][0]["status"]
        out.append({"key": key, "file": short["file"], "upload_status": st.get("uploadStatus"), "video_id": entry["video_id"], "url": f"https://youtube.com/shorts/{entry['video_id']}",
                    "slot": entry["slot"], "title": title_for(short)})
    Path(receipt_path).write_text(json.dumps({"version": "shorts-receipt-v1", "long_video_id": long_id, "shorts": out,
                                              "verified_at": datetime.now(timezone.utc).isoformat()}, indent=1) + "\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main(*sys.argv[1:7])
