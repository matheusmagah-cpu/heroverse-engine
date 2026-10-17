#!/usr/bin/env python3
"""Publish one rendered HeroVerse video to the exact channel.

Owner authorization 2026-10-17: automatic publication on HeroVerse
(@heroverse74) once the pipeline is validated. Owner rule: every validation
runs BEFORE upload; a video goes up PUBLIC, or private with publishAt only
when it is scheduled to open at a chosen hour. Idempotent: ledger.json maps
publish_key -> video_id; an existing key is never uploaded again, the run only
finishes missing steps. Steps: resumable videos.insert (private, or scheduled
with publishAt) -> thumbnails.set -> captions.insert (SRT from the narration
timeline) -> playlist add -> verify. Writes a receipt.
usage: publish_video.py PACKAGE_JSON MANIFEST_JSON VIDEO THUMBNAIL LEDGER RECEIPT [PUBLISH_AT_ISO]
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

CHANNEL = "UCuMF6pJQkyMzaVoAxFL86yA"
API = "https://www.googleapis.com/youtube/v3/"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/"


def session():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession, Request
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["HERO_YT_AUTHORIZED_USER_JSON"]))
    creds.refresh(Request())
    return AuthorizedSession(creds)


def check(response, what):
    if response.status_code >= 300:
        raise RuntimeError(f"{what}_HTTP_{response.status_code}: {response.text[:300]}")
    return response.json() if response.content else {}


def srt(sentences):
    def stamp(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text']}\n" for i, s in enumerate(sentences, 1))


def upload(s, path, body):
    size = Path(path).stat().st_size
    init = s.post(UPLOAD + "videos", params={"uploadType": "resumable", "part": "snippet,status"}, json=body,
                  headers={"X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    if init.status_code >= 300:
        raise RuntimeError(f"UPLOAD_INIT_HTTP_{init.status_code}: {init.text[:300]}")
    location = init.headers["Location"]
    for attempt in range(6):
        probe = s.put(location, headers={"Content-Range": f"bytes */{size}"})
        if probe.status_code in (200, 201):
            return probe.json()
        offset = int(probe.headers["Range"].split("-")[1]) + 1 if "Range" in probe.headers else 0
        with open(path, "rb") as handle:
            handle.seek(offset)
            done = s.put(location, data=handle, headers={"Content-Range": f"bytes {offset}-{size - 1}/{size}"})
        if done.status_code in (200, 201):
            return done.json()
        time.sleep(2 ** attempt)
    raise RuntimeError("UPLOAD_NOT_COMPLETED")


def ensure_playlist(s, title, description):
    for p in check(s.get(API + "playlists", params={"part": "snippet", "mine": "true", "maxResults": 50}), "PLAYLISTS")["items"]:
        if p["snippet"]["title"] == title:
            return p["id"]
    return check(s.post(API + "playlists", params={"part": "snippet,status"},
                        json={"snippet": {"title": title, "description": description, "defaultLanguage": "en"},
                              "status": {"privacyStatus": "public"}}), "PLAYLIST_CREATE")["id"]


def main(package_path, manifest_path, video, thumbnail, ledger_path, receipt_path, publish_at=None):
    package = json.loads(Path(package_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"version": "publish-ledger-v1", "entries": {}}
    key = f"{package['pilot_id']}:{manifest['output_sha256']}"
    s = session()
    if [c["id"] for c in check(s.get(API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    entry = ledger["entries"].get(key, {"steps": {}})
    status = {"privacyStatus": "private" if publish_at else "public", "selfDeclaredMadeForKids": False,
              "embeddable": True, "license": "youtube", "publicStatsViewable": True, "containsSyntheticMedia": True}
    if publish_at:
        status["publishAt"] = publish_at  # opens automatically at this time
    if "video_id" not in entry:
        body = {"snippet": {"title": package["title"], "description": package["description"], "tags": package["tags"],
                            "categoryId": package.get("category_id", "22"), "defaultLanguage": "en",
                            "defaultAudioLanguage": "en"}, "status": status}
        entry.update({"video_id": upload(s, video, body)["id"], "uploaded_at": datetime.now(timezone.utc).isoformat()})
        ledger["entries"][key] = entry
        ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")  # durable before any further step
    vid = entry["video_id"]
    if not entry["steps"].get("thumbnail"):
        check(s.post(UPLOAD + "thumbnails/set", params={"videoId": vid}, data=Path(thumbnail).read_bytes(),
                     headers={"Content-Type": "image/jpeg"}), "THUMBNAIL")
        entry["steps"]["thumbnail"] = True
    if not entry["steps"].get("captions") and manifest.get("sentences"):
        boundary = "heroverse-caption-boundary"
        meta = json.dumps({"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{boundary}\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n{srt(manifest['sentences'])}\r\n--{boundary}--")
        check(s.post(UPLOAD + "captions", params={"uploadType": "multipart", "part": "snippet"}, data=body.encode(),
                     headers={"Content-Type": f"multipart/related; boundary={boundary}"}), "CAPTIONS")
        entry["steps"]["captions"] = True
    if not entry["steps"].get("playlist") and package.get("playlist"):
        pid = ensure_playlist(s, package["playlist"]["title"], package["playlist"]["description"])
        check(s.post(API + "playlistItems", params={"part": "snippet"},
                     json={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}), "PLAYLIST_ADD")
        entry["steps"]["playlist"] = pid
    ledger["entries"][key] = entry
    ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")
    final = check(s.get(API + "videos", params={"part": "status,snippet", "id": vid}), "VERIFY")["items"][0]
    receipt = {"version": "publish-receipt-v1", "key": key, "video_id": vid, "url": f"https://youtu.be/{vid}",
               "channel_id": final["snippet"]["channelId"], "title": final["snippet"]["title"],
               "privacy": final["status"]["privacyStatus"], "publish_at": final["status"].get("publishAt"),
               "steps": entry["steps"], "verified_at": datetime.now(timezone.utc).isoformat()}
    Path(receipt_path).write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main(*sys.argv[1:8])
