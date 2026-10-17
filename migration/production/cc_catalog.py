#!/usr/bin/env python3
"""Creative Commons visual catalog for production (F5). Read-only Data API.

Searches YouTube for high-definition videos marked Creative Commons (CC BY 3.0)
on morning/nature/prayer b-roll themes, then re-verifies every candidate with
videos.list: status.license must be 'creativeCommon', public, not made for
kids, HD, at least 90 s. Only the picture is used in production (audio is
dropped), and every clip used is credited with its attribution line. Licence
flags are set by uploaders, so a clip is a candidate until its rights record
is kept with the production manifest; risky titles (re-upload markers,
music/film/TV names) are excluded.
"""
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"
QUERIES = (
    "sunrise timelapse stock footage",
    "morning light forest b-roll",
    "clouds sky timelapse free footage",
    "ocean waves sunrise stock footage",
    "mountain sunrise drone footage",
    "candle light church b-roll",
    "flower field morning light footage",
    "river stream nature footage",
)
EXCLUDE = re.compile(r"(?i)\b(official|music video|lyrics?|trailer|movie|film|episode|full album|cover|remix|"
                     r"reupload|re-upload|tiktok|compilation|nightcore|8d audio|ft\.|feat\.)\b")
ISO = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def seconds(iso):
    match = ISO.fullmatch(iso or "")
    if not match:
        return None
    h, m, s = (int(x or 0) for x in match.groups())
    return h * 3600 + m * 60 + s


def access_token():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    raw = os.environ.get("HERO_YT_AUTHORIZED_USER_JSON", "")
    if not raw:
        raise PermissionError("CREDENTIAL_MISSING")
    credentials = Credentials.from_authorized_user_info(json.loads(raw))
    credentials.refresh(Request())
    return credentials.token


def get(token, endpoint, params, units, ledger):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("RESPONSE_CAP")
    ledger.append({"endpoint": endpoint, "units": units})
    return json.loads(body)


def eligible(video):
    snippet, status, details = video["snippet"], video["status"], video["contentDetails"]
    duration = seconds(details.get("duration"))
    reasons = []
    if status.get("license") != "creativeCommon":
        reasons.append("NOT_CREATIVE_COMMON")
    if status.get("privacyStatus") != "public":
        reasons.append("NOT_PUBLIC")
    if status.get("madeForKids"):
        reasons.append("MADE_FOR_KIDS")
    if details.get("definition") != "hd":
        reasons.append("NOT_HD")
    if not duration or duration < 90:
        reasons.append("TOO_SHORT")
    if EXCLUDE.search(snippet.get("title", "")):
        reasons.append("RISKY_TITLE")
    return reasons, duration


def build(token, max_units=1000):
    ledger, found = [], {}
    for query in QUERIES:
        if sum(x["units"] for x in ledger) + 100 > max_units:
            break
        result = get(token, "search", {"part": "snippet", "type": "video", "q": query, "maxResults": 25,
                                       "videoLicense": "creativeCommon", "videoDefinition": "high",
                                       "videoDuration": "medium", "safeSearch": "strict"}, 100, ledger)
        for item in result.get("items", []):
            found.setdefault(item["id"]["videoId"], query)
    ids, catalog, rejected = list(found), [], []
    for start in range(0, len(ids), 50):
        result = get(token, "videos", {"part": "snippet,status,contentDetails", "id": ",".join(ids[start:start + 50]),
                                       "maxResults": 50}, 1, ledger)
        for video in result.get("items", []):
            reasons, duration = eligible(video)
            row = {"video_id": video["id"], "title": video["snippet"]["title"],
                   "channel_title": video["snippet"]["channelTitle"], "channel_id": video["snippet"]["channelId"],
                   "query": found[video["id"]], "duration_seconds": duration,
                   "license": video["status"].get("license")}
            if reasons:
                rejected.append(dict(row, reasons=reasons))
            else:
                row["attribution"] = (f'"{row["title"]}" by {row["channel_title"]} '
                                      f'(https://www.youtube.com/watch?v={row["video_id"]}), licensed CC BY 3.0')
                catalog.append(row)
    return {"version": "cc-visual-catalog-v1", "queries": list(QUERIES), "candidates": len(ids),
            "eligible": len(catalog), "catalog": catalog, "rejected": rejected,
            "data_api_units": sum(x["units"] for x in ledger),
            "rights_basis": "YouTube status.license=creativeCommon (CC BY 3.0); picture only; attribution in description",
            "rights_risk": "Uploader-declared licence; exclusions applied; clips stay candidates until listed in a production manifest.",
            "paid_calls": 0}


if __name__ == "__main__":
    record = build(access_token())
    Path(sys.argv[1]).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: record[k] for k in ("candidates", "eligible", "data_api_units")}))
