#!/usr/bin/env python3
"""Publish one Bible-series episode (owner, 2026-10-24: Bible stories from Genesis, one at a time; Shorts first).

The episode record (migration/production/bible/episodes/<id>.json) holds the metadata and the hash of the exact file.
Idempotent like publish_video: the ledger maps "bible:<id>:<sha256>" -> video_id, an existing key is never uploaded
again and a re-run only finishes missing steps. Public at once, or private with publishAt. AI scenes and voice are
declared (containsSyntheticMedia).
usage: publish_episode.py EPISODE_JSON VIDEO LEDGER RECEIPT [PUBLISH_AT_ISO]
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv  # noqa: E402

TITLE_MAX = 100
DESCRIPTION_MAX = 4900   # YouTube allows 5,000


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def problems(episode, video):
    out = []
    if sha256_file(video) != episode["output_sha256"]:
        out.append("OUTPUT_SHA256_MISMATCH")
    if not 0 < len(episode["title"]) <= TITLE_MAX:
        out.append("TITLE_LENGTH")
    if len(episode["description"]) > DESCRIPTION_MAX:
        out.append("DESCRIPTION_LENGTH")
    if "(public domain)" not in episode["description"] or "AI" not in episode["description"]:
        out.append("DISCLOSURE_MISSING")   # KJV source and AI disclosure are always stated
    return out


def main(episode_path, video, ledger_path, receipt_path, publish_at=None):
    episode = json.loads(Path(episode_path).read_text())
    bad = problems(episode, video)
    if bad:
        raise SystemExit("EPISODE_REFUSED " + " ".join(bad))
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    key = f"bible:{episode['id']}:{episode['output_sha256']}"
    entry = ledger["entries"].get(key, {"steps": {}})
    s = pv.session()
    if [c["id"] for c in pv.check(s.get(pv.API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [pv.CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")

    def save():
        ledger["entries"][key] = entry
        ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")
    if "video_id" not in entry:
        status = {"privacyStatus": "private" if publish_at else "public", "selfDeclaredMadeForKids": False,
                  "embeddable": True, "license": "youtube", "publicStatsViewable": True, "containsSyntheticMedia": True}
        if publish_at:
            status["publishAt"] = publish_at
        body = {"snippet": {"title": episode["title"], "description": episode["description"], "tags": episode["tags"],
                            "categoryId": episode.get("category_id", "29"), "defaultLanguage": "en",
                            "defaultAudioLanguage": "en"}, "status": status}
        entry.update({"video_id": pv.upload(s, video, body)["id"], "uploaded_at": datetime.now(timezone.utc).isoformat()})
        save()   # durable before any further step
    vid = entry["video_id"]
    if episode.get("first_comment") and not pv.comment_done(entry["steps"].get("first_comment")):
        entry["steps"]["first_comment"] = pv.first_comment(s, vid, episode["first_comment"])
        save()
    final = pv.check(s.get(pv.API + "videos", params={"part": "status,snippet", "id": vid}), "VERIFY")["items"][0]
    receipt = {"version": "publish-receipt-v1", "key": key, "video_id": vid, "url": f"https://youtube.com/shorts/{vid}",
               "channel_id": final["snippet"]["channelId"], "title": final["snippet"]["title"],
               "privacy": final["status"]["privacyStatus"], "publish_at": final["status"].get("publishAt"),
               "upload_status": final["status"].get("uploadStatus"), "steps": entry["steps"],
               "verified_at": datetime.now(timezone.utc).isoformat()}
    Path(receipt_path).write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main(*sys.argv[1:6])
