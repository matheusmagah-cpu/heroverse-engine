#!/usr/bin/env python3
"""Hide the Portuguese uploads of HeroVerse (owner instruction 2026-10-17:
the channel is English-only). Reversible: privacy -> private, nothing is
deleted; the receipt keeps each video's previous privacy so it can be undone.

  plan  : list every upload of the exact channel and classify language
  apply : set privacyStatus=private for the videos in a reviewed plan file
usage: channel_privacy.py plan OUT_JSON | apply PLAN_JSON OUT_RECEIPT
"""
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"
CHANNEL = "UCuMF6pJQkyMzaVoAxFL86yA"
PT_WORDS = re.compile(r"(?i)\b(você|voce|não|nao|deus|são|está|para|com|uma|mais|seu|sua|vida|quando|porque|"
                      r"liderança|lideranca|talento|sucesso|nunca|sempre|hoje|isso|como|ninguém|coração|fé)\b")
EN_WORDS = re.compile(r"(?i)\b(you|your|the|god|is|not|and|this|what|why|when|are|to|of|for)\b")


def token():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["HERO_YT_AUTHORIZED_USER_JSON"]))
    creds.refresh(Request())
    return creds.token


def call(tok, method, endpoint, params, body=None):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def language(video):
    s = video["snippet"]
    declared = (s.get("defaultAudioLanguage") or s.get("defaultLanguage") or "").lower()
    text = s.get("title", "") + " " + s.get("description", "")[:300]
    pt, en = len(PT_WORDS.findall(text)), len(EN_WORDS.findall(text))
    if declared.startswith("pt") or (pt >= 2 and pt > en):
        return "pt"
    if declared.startswith("en") or en > pt:
        return "en"
    return "unknown"


def channel_uploads(get, parts):
    """Every upload of the exact channel, as videos.list items with `parts`; shared by plan() and
    captions_audit.py (review of #424). `get(endpoint, params)` returns the decoded answer. Returns (videos, calls),
    each call 1 Data API unit. Refuses any other channel (CHANNEL_IDENTITY_MISMATCH)."""
    me = get("channels", {"part": "id,contentDetails", "mine": "true"})["items"]
    if [c["id"] for c in me] != [CHANNEL]:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    playlist = me[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page, calls = [], None, 1
    while True:
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50}
        if page:
            params["pageToken"] = page
        res = get("playlistItems", params)
        calls += 1
        ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
        page = res.get("nextPageToken")
        if not page:
            break
    videos = []
    for start in range(0, len(ids), 50):
        videos += get("videos", {"part": parts, "id": ",".join(ids[start:start + 50])}).get("items", [])
        calls += 1
    return videos, calls


def plan(out):
    tok = token()
    raw, _ = channel_uploads(lambda endpoint, params: call(tok, "GET", endpoint, params),
                             "snippet,status,statistics,contentDetails")
    videos = [{"video_id": v["id"], "title": v["snippet"]["title"], "published_at": v["snippet"]["publishedAt"],
               "privacy": v["status"]["privacyStatus"], "language": language(v),
               "declared_language": v["snippet"].get("defaultAudioLanguage") or v["snippet"].get("defaultLanguage"),
               "views": int(v.get("statistics", {}).get("viewCount", 0)), "duration": v["contentDetails"].get("duration")}
              for v in raw]
    to_hide = [v["video_id"] for v in videos if v["language"] == "pt" and v["privacy"] != "private"]
    record = {"version": "channel-privacy-plan-v1", "channel_id": CHANNEL, "uploads": len(videos),
              "by_language": {k: sum(v["language"] == k for v in videos) for k in ("pt", "en", "unknown")},
              "to_hide": to_hide, "videos": videos}
    Path(out).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: record[k] for k in ("uploads", "by_language")} | {"to_hide": len(to_hide)}))


def apply(plan_path, out):
    plan_record = json.loads(Path(plan_path).read_text())
    if plan_record["channel_id"] != CHANNEL:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    tok = token()
    receipt = []
    limit = int(os.environ.get("MAX_CHANGES", "40"))  # 50 quota units per update
    for vid in plan_record["to_hide"]:
        if sum(r["result"] == "HIDDEN" for r in receipt) >= limit:
            break
        current = call(tok, "GET", "videos", {"part": "status,snippet", "id": vid})["items"]
        if current and current[0]["status"]["privacyStatus"] == "private":
            continue
        if not current or current[0]["snippet"]["channelId"] != CHANNEL:
            receipt.append({"video_id": vid, "result": "SKIPPED_NOT_OWNED_OR_MISSING"})
            continue
        status = current[0]["status"]
        before = status["privacyStatus"]
        if before == "private":
            receipt.append({"video_id": vid, "before": before, "result": "ALREADY_PRIVATE"})
            continue
        body = {"id": vid, "status": {"privacyStatus": "private", "embeddable": status.get("embeddable", True),
                                      "license": status.get("license", "youtube"),
                                      "publicStatsViewable": status.get("publicStatsViewable", True),
                                      "selfDeclaredMadeForKids": status.get("madeForKids", False)}}
        after = call(tok, "PUT", "videos", {"part": "status"}, body)["status"]["privacyStatus"]
        receipt.append({"video_id": vid, "before": before, "after": after, "result": "HIDDEN" if after == "private" else "UNEXPECTED"})
    Path(out).write_text(json.dumps({"version": "channel-privacy-receipt-v1", "channel_id": CHANNEL,
                                     "plan": Path(plan_path).name, "undo": "set each video back to its 'before' privacy",
                                     "changes": receipt}, indent=1) + "\n")
    print(json.dumps({"hidden": sum(r["result"] == "HIDDEN" for r in receipt), "total": len(receipt)}))


def unschedule(plan_path, out):
    """Owner hold: each listed video becomes private with no pending publishAt (a scheduled upload already is
    private, so apply() would skip it and it would still go public at its time). Reversible: the receipt keeps
    the old publishAt.
    A hold only stops what is not public yet (owner, 2026-10-26: the scheduled prayer longs): a video that is already
    public is never changed here (SKIPPED_ALREADY_PUBLIC; hiding a public video is apply() with its own reviewed
    plan), and one already private with no publishAt is left as it is (ALREADY_UNSCHEDULED, no write)."""
    plan_record = json.loads(Path(plan_path).read_text())
    if plan_record["channel_id"] != CHANNEL:
        raise SystemExit("CHANNEL_IDENTITY_MISMATCH")
    tok = token()
    receipt = []
    for vid in plan_record["to_unschedule"]:
        current = call(tok, "GET", "videos", {"part": "status,snippet", "id": vid})["items"]
        if not current or current[0]["snippet"]["channelId"] != CHANNEL:
            receipt.append({"video_id": vid, "result": "SKIPPED_NOT_OWNED_OR_MISSING"})
            continue
        status = current[0]["status"]
        before = {"privacy": status["privacyStatus"], "publishAt": status.get("publishAt")}
        if before["privacy"] == "public":
            receipt.append({"video_id": vid, "before": before, "result": "SKIPPED_ALREADY_PUBLIC"})
            continue
        if before["privacy"] == "private" and not before["publishAt"]:
            receipt.append({"video_id": vid, "before": before, "result": "ALREADY_UNSCHEDULED"})
            continue
        body = {"id": vid, "status": {"privacyStatus": "private", "embeddable": status.get("embeddable", True),
                                      "license": status.get("license", "youtube"),
                                      "publicStatsViewable": status.get("publicStatsViewable", True),
                                      "selfDeclaredMadeForKids": status.get("madeForKids", False)}}
        after = call(tok, "PUT", "videos", {"part": "status"}, body)["status"]
        ok = after["privacyStatus"] == "private" and not after.get("publishAt")
        receipt.append({"video_id": vid, "before": before, "after": {"privacy": after["privacyStatus"],
                        "publishAt": after.get("publishAt")}, "result": "UNSCHEDULED" if ok else "UNEXPECTED"})
    public = [r["video_id"] for r in receipt if r["result"] == "SKIPPED_ALREADY_PUBLIC"]
    Path(out).write_text(json.dumps({"version": "channel-unschedule-receipt-v1", "channel_id": CHANNEL,
                                     "plan": Path(plan_path).name, "undo": "set each video back to its 'before'",
                                     "already_public_not_changed": public,
                                     "changes": receipt}, indent=1) + "\n")
    for vid in public:   # a skip, never a hide: stated plainly in the log and as an Actions warning
        print(f"HELD_VIDEO_ALREADY_PUBLIC {vid}: it was public before this run; left public, not changed "
              f"(hiding it is channel_privacy.py apply with a reviewed plan)")
        print(f"::warning::HELD_VIDEO_ALREADY_PUBLIC {vid} was already public; the hold did not change it")
    print(json.dumps({"unscheduled": sum(r["result"] == "UNSCHEDULED" for r in receipt), "total": len(receipt),
                      "already_public_not_changed": public, "changes": receipt}))  # public ids and statuses only
    if any(r["result"] not in ("UNSCHEDULED", "ALREADY_UNSCHEDULED", "SKIPPED_ALREADY_PUBLIC") for r in receipt):
        raise SystemExit("UNSCHEDULE_INCOMPLETE")


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        plan(sys.argv[2])
    elif sys.argv[1] == "apply":
        apply(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "unschedule":
        unschedule(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
