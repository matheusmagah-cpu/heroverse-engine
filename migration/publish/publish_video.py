#!/usr/bin/env python3
"""Publish one rendered HeroVerse video to the exact channel.

Owner authorization 2026-10-17: automatic publication on HeroVerse
(@heroverse74) once the pipeline is validated. Owner rule: every validation
runs BEFORE upload; a video goes up PUBLIC, or private with publishAt only
when it is scheduled to open at a chosen hour. Idempotent: ledger.json maps
publish_key -> video_id; an existing key is never uploaded again, the run only
finishes missing steps. Steps: resumable videos.insert (private, or scheduled
with publishAt) -> thumbnails.set -> captions.insert (SRT from the narration
timeline) -> playlist add -> first comment (commentThreads.insert, from the
package's first_comment; a refusal is recorded as "PENDING: <reason>" and never
fails the publication, first_comment.py retries it once the video is public;
pinning is manual, the API cannot pin) -> verify. Writes a receipt.
usage: publish_video.py PACKAGE_JSON MANIFEST_JSON VIDEO THUMBNAIL LEDGER RECEIPT [PUBLISH_AT_ISO]
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owner_quality_policy

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


def retry(call, what, tries=4):
    """YouTube answers 409 ABORTED / 5xx when a backend is briefly unavailable; retry those, never other errors."""
    for i in range(tries):
        r = call()
        if r.status_code < 300 or (r.status_code not in (409, 500, 502, 503, 504)) or i == tries - 1:
            return check(r, what)
        time.sleep(5 * 2 ** i)


def ensure_playlist(s, title, description):
    for p in check(s.get(API + "playlists", params={"part": "snippet", "mine": "true", "maxResults": 50}), "PLAYLISTS")["items"]:
        if p["snippet"]["title"] == title:
            return p["id"]
    return check(s.post(API + "playlists", params={"part": "snippet,status"},
                        json={"snippet": {"title": title, "description": description, "defaultLanguage": "en"},
                              "status": {"privacyStatus": "public"}}), "PLAYLIST_CREATE")["id"]


def comment_done(value):
    """A recorded comment id; None, empty and "PENDING: ..." are not done."""
    return isinstance(value, str) and bool(value) and not value.startswith("PENDING")


def api_reason(response):
    try:
        err = response.json()["error"]
        reason = (err.get("errors") or [{}])[0].get("reason") or err.get("status") or ""
        return f"HTTP_{response.status_code} {reason}: {err.get('message', '')}".strip()[:200]
    except (ValueError, KeyError, TypeError, AttributeError):
        return f"HTTP_{response.status_code}: {response.text[:150]}"


def existing_comment(s, vid, text):
    """The channel's own top-level comment with this exact text, if one is already there (a run that stopped
    before recording it); any listing error just means "not known", never a failure."""
    try:
        r = s.get(API + "commentThreads", params={"part": "snippet", "videoId": vid, "maxResults": 100, "order": "time"})
        if r.status_code >= 300:
            return None
        for t in (r.json() or {}).get("items", []):
            c = t.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            if c.get("authorChannelId", {}).get("value") == CHANNEL and text in (c.get("textOriginal"), c.get("textDisplay")):
                return t.get("id")
    except Exception:  # noqa: BLE001 - best effort only
        return None
    return None


def first_comment(s, vid, text, tries=3):
    """Post the channel's first comment. Returns the comment-thread id, or "PENDING: <reason>" when YouTube refuses
    (missing scope, comments disabled, private or scheduled video) or stays unavailable. Never raises."""
    text = (text or "").strip()
    if not text or len(text) > 300:
        return "PENDING: FIRST_COMMENT_TEXT_INVALID (empty or over 300 characters)"
    found = existing_comment(s, vid, text)
    if found:
        return found
    body = {"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": text}}}}
    reason = "NOT_ATTEMPTED"
    for i in range(tries):
        try:
            r = s.post(API + "commentThreads", params={"part": "snippet"}, json=body)
        except Exception as e:  # noqa: BLE001 - a network failure leaves the comment pending, never the video
            reason = f"{type(e).__name__}"
        else:
            if r.status_code < 300:
                cid = (r.json() or {}).get("id")
                return cid if cid else "PENDING: NO_ID_IN_RESPONSE"
            reason = api_reason(r)
            if r.status_code not in (409, 500, 502, 503, 504):
                break
        if i < tries - 1:
            time.sleep(5 * 2 ** i)
    return f"PENDING: {reason}"


def check_new_upload(manifest_path, manifest, video):
    """Bind the additional owner floor to the bytes being newly uploaded.

    Canonical QA/approval revalidation remains in publication_binding. Existing
    ledger video IDs never enter this gate or require local media after cleanup.
    """
    try:
        review = json.loads((Path(manifest_path).parent / "review.json").read_text())
        digest = hashlib.sha256()
        with Path(video).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        actual_sha256 = digest.hexdigest()
    except (OSError, ValueError) as exc:
        raise SystemExit("OWNER_QUALITY_POLICY_BLOCKED:EVIDENCE_UNREADABLE:" + type(exc).__name__) from exc
    if not isinstance(review, dict):
        raise SystemExit("OWNER_QUALITY_POLICY_BLOCKED:REVIEW_NOT_OBJECT")
    problems = []
    if manifest.get("output_sha256") != actual_sha256:
        problems.append("MANIFEST_NOT_FOR_THIS_FILE")
    if review.get("status") != "PASS":
        problems.append("TOP_LEVEL_REVIEW_NOT_PASS")
    if review.get("output_sha256") != actual_sha256:
        problems.append("TOP_LEVEL_REVIEW_NOT_FOR_THIS_FILE")
    if problems:
        raise SystemExit("OWNER_QUALITY_POLICY_BLOCKED:" + ",".join(problems))
    watched = review.get("watched_review")
    # Long evidence binds the watched review at the top level. Adapt a new
    # in-memory copy only, after checking that binding against the actual MP4.
    bound_review = {**watched, "output_sha256": review["output_sha256"]} if isinstance(watched, dict) else watched
    problems = owner_quality_policy.check(bound_review, actual_sha256, owner_quality_policy.LONG_REVIEWER)
    if problems:
        raise SystemExit("OWNER_QUALITY_POLICY_BLOCKED:" + ",".join(problems))


def main(package_path, manifest_path, video, thumbnail, ledger_path, receipt_path, publish_at=None):
    package = json.loads(Path(package_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    ledger_path = Path(ledger_path)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"version": "publish-ledger-v1", "entries": {}}
    key = f"{package['pilot_id']}:{manifest['output_sha256']}"
    entry = ledger["entries"].get(key, {"steps": {}})
    if "video_id" not in entry:
        check_new_upload(manifest_path, manifest, video)
    s = session()
    if [c["id"] for c in check(s.get(API + "channels", params={"part": "id", "mine": "true"}), "CHANNEL")["items"]] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
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

    def save():  # every finished step is durable, so a re-run repeats nothing
        ledger["entries"][key] = entry
        ledger_path.write_text(json.dumps(ledger, indent=1) + "\n")
    if not entry["steps"].get("thumbnail"):
        check(s.post(UPLOAD + "thumbnails/set", params={"videoId": vid}, data=Path(thumbnail).read_bytes(),
                     headers={"Content-Type": "image/jpeg"}), "THUMBNAIL")
        entry["steps"]["thumbnail"] = True
        save()
    if not entry["steps"].get("captions") and manifest.get("sentences") and any(
            c["snippet"].get("language") == "en" for c in
            check(s.get(API + "captions", params={"part": "snippet", "videoId": vid}), "CAPTIONS_LIST")["items"]):
        entry["steps"]["captions"] = True  # inserted by an earlier run that stopped before recording it
        save()
    if not entry["steps"].get("captions") and manifest.get("sentences"):
        boundary = "heroverse-caption-boundary"
        meta = json.dumps({"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{boundary}\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n{srt(manifest['sentences'])}\r\n--{boundary}--")
        check(s.post(UPLOAD + "captions", params={"uploadType": "multipart", "part": "snippet"}, data=body.encode(),
                     headers={"Content-Type": f"multipart/related; boundary={boundary}"}), "CAPTIONS")
        entry["steps"]["captions"] = True
        save()
    if not entry["steps"].get("playlist") and package.get("playlist"):
        # the playlist is a convenience: a failure is recorded in the receipt and never blocks verification
        try:
            pid = ensure_playlist(s, package["playlist"]["title"], package["playlist"]["description"])
            present = check(s.get(API + "playlistItems", params={"part": "id", "playlistId": pid, "videoId": vid}),
                            "PLAYLIST_ITEMS")["items"]
            if not present:
                retry(lambda: s.post(API + "playlistItems", params={"part": "snippet"}, json={"snippet": {
                    "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}), "PLAYLIST_ADD")
            entry["steps"]["playlist"] = pid
        except RuntimeError as e:
            entry["steps"]["playlist_error"] = str(e)[:200]
    save()
    if package.get("first_comment") and not comment_done(entry["steps"].get("first_comment")):
        # a refused comment (scope, comments off, video still private/scheduled) is PENDING, never a failed publication
        entry["steps"]["first_comment"] = first_comment(s, vid, package["first_comment"])
        save()
    final = check(s.get(API + "videos", params={"part": "status,snippet", "id": vid}), "VERIFY")["items"][0]
    receipt = {"version": "publish-receipt-v1", "key": key, "video_id": vid, "url": f"https://youtu.be/{vid}",
               "channel_id": final["snippet"]["channelId"], "title": final["snippet"]["title"],
               "privacy": final["status"]["privacyStatus"], "publish_at": final["status"].get("publishAt"),
               "upload_status": final["status"].get("uploadStatus"),
               "steps": entry["steps"], "verified_at": datetime.now(timezone.utc).isoformat()}
    Path(receipt_path).write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main(*sys.argv[1:8])
