#!/usr/bin/env python3
"""Market panel for the English Christian niche (read-only Data API, no media).

Purpose: a market base rate for time-to-monetization that does not depend on
our own channel. Discovery samples RECENT uploads (order=date) as well as the
most viewed recent uploads (order=viewCount) for each niche query, so channels
that are failing are sampled too, not only winners. Every discovered channel
gets its public statistics (creation date, subscribers, views, videos,
country). Channels younger than YOUNG_DAYS also get their recent uploads with
durations and views, so their public long-form watch time can be bounded.

Repeated daily, the same panel yields per-channel growth trajectories.
usage: market_panel.py RAW_JSON MAX_UNITS [COMPACT_JSON]
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/youtube/v3/"
QUERIES = (
    "morning prayer", "night prayer before sleep", "prayer for protection", "powerful prayer",
    "god says", "god message for you today", "jesus message", "bible verses",
    "bible study", "bible stories", "psalm 91", "psalm 23", "scripture for sleep",
    "christian motivation", "sermon", "devotional", "daily devotion", "prayer for healing",
    "prayer for financial breakthrough", "worship songs", "christian music", "faith encouragement",
    "holy spirit", "end times prophecy", "jesus christ", "prayer for my family",
    "god is telling you", "christian shorts", "bible facts", "gospel",
    # opinion / commentary / critique structures (owner directive 2026-10-17)
    "what the bible really says about", "christian perspective on", "is it biblical",
    "should christians", "bible explained", "christian apologetics", "christian commentary",
    "the truth about christianity",
)
# Other faceless niches, only to find structures that grow very fast (mechanism
# references, kept apart from Christian demand comparators by the "niche" field).
CROSS_NICHE_QUERIES = (
    "bedtime stories for adults", "history documentary", "motivational speech", "stoic wisdom",
    "true story", "sleep stories", "life lessons", "meditation", "psychology facts", "audiobook",
    "manifestation", "affirmations",
)
VIEWCOUNT_CHRISTIAN = 12
DISCOVERY_RESERVE_UNITS = 900  # keep for channel statistics and upload histories
YOUNG_DAYS = 365
MAX_HISTORY_VIDEOS = 200
MAX_PAGES = 4
DISCOVERY_DAYS = 30
ISO = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def seconds(iso):
    match = ISO.fullmatch(iso or "")
    return None if not match else sum(int(x or 0) * k for x, k in zip(match.groups(), (3600, 60, 1)))


def access_token():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    raw = os.environ.get("HERO_YT_AUTHORIZED_USER_JSON", "")
    if not raw:
        raise PermissionError("CREDENTIAL_MISSING")
    credentials = Credentials.from_authorized_user_info(json.loads(raw))
    credentials.refresh(Request())
    return credentials.token


class Client:
    def __init__(self, token, max_units):
        self.token, self.max_units, self.units, self.calls = token, max_units, 0, 0

    def can(self, units):
        return self.units + units <= self.max_units

    def get(self, endpoint, params, units):
        if not self.can(units):
            raise RuntimeError("UNIT_BUDGET")
        url = API + endpoint + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token,
                                                       "Accept": "application/json"})
        self.units += units
        self.calls += 1
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise ValueError("RESPONSE_CAP")
        return json.loads(body)


def discover(client, now):
    """Christian queries by date (half of the 30 each day, alternating), cross-niche queries by views over the
    last 14 days, then Christian queries by views while the budget lasts."""
    after = (now - timedelta(days=DISCOVERY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    after_cross = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # half of the queries each day (all of them every 2 days): the 10k unit day must also carry the uploads
    today = QUERIES[now.toordinal() % 2::2]
    plan = ([("christian", "date", q, after) for q in today]
            + [("cross", "viewCount", q, after_cross) for q in CROSS_NICHE_QUERIES]
            + [("christian", "viewCount", q, after) for q in today[:VIEWCOUNT_CHRISTIAN // 2]])
    found = {}
    for niche, order, query, since in plan:
        if not client.can(100 + DISCOVERY_RESERVE_UNITS):
            break
        result = client.get("search", {"part": "snippet", "type": "video", "q": query, "maxResults": 50,
                                       "order": order, "publishedAfter": since, "relevanceLanguage": "en",
                                       "regionCode": "US", "safeSearch": "none"}, 100)
        for item in result.get("items", []):
            entry = found.setdefault(item["snippet"]["channelId"], {"queries": set(), "orders": set(), "niches": set()})
            entry["queries"].add(query)
            entry["orders"].add(order)
            entry["niches"].add(niche)
    return found


def channels(client, ids):
    out = {}
    ids = list(ids)
    for start in range(0, len(ids), 50):
        result = client.get("channels", {"part": "snippet,statistics,contentDetails,brandingSettings",
                                         "id": ",".join(ids[start:start + 50]), "maxResults": 50}, 1)
        for c in result.get("items", []):
            s, st = c["snippet"], c.get("statistics", {})
            out[c["id"]] = {
                "channel_id": c["id"], "title": s.get("title"), "custom_url": s.get("customUrl"),
                "published_at": s.get("publishedAt"), "country": s.get("country"),
                "default_language": s.get("defaultLanguage") or c.get("brandingSettings", {}).get("channel", {}).get("defaultLanguage"),
                "subscribers": int(st["subscriberCount"]) if "subscriberCount" in st else None,
                "subscribers_hidden": st.get("hiddenSubscriberCount", False),
                "views": int(st.get("viewCount", 0)), "videos": int(st.get("videoCount", 0)),
                "uploads_playlist": c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")}
    return out


def uploads(client, playlist, pages):
    ids, token = [], None
    for _ in range(pages):
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50}
        if token:
            params["pageToken"] = token
        result = client.get("playlistItems", params, 1)
        ids += [i["contentDetails"]["videoId"] for i in result.get("items", [])]
        token = result.get("nextPageToken")
        if not token:
            break
    videos = []
    for start in range(0, len(ids), 50):
        result = client.get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[start:start + 50]),
                                       "maxResults": 50}, 1)
        for v in result.get("items", []):
            st = v.get("statistics", {})
            videos.append({"video_id": v["id"], "published_at": v["snippet"]["publishedAt"],
                           "title": v["snippet"]["title"], "duration_seconds": seconds(v["contentDetails"].get("duration")),
                           "views": int(st.get("viewCount", 0)), "likes": int(st["likeCount"]) if "likeCount" in st else None,
                           "comments": int(st["commentCount"]) if "commentCount" in st else None,
                           "language": v["snippet"].get("defaultAudioLanguage") or v["snippet"].get("defaultLanguage")})
    return videos, token is not None


def tracked_ids(prior_dir):
    """Channels with fetched histories in earlier compact panels: always refreshed
    (1 unit per 50 channels) so trajectories and registered forecasts can be scored."""
    ids = set()
    for path in sorted(Path(prior_dir).glob("panel-*.json")) if prior_dir else []:
        for c in json.loads(path.read_text())["channels"]:
            if c.get("uploads_status") == "FETCHED":
                ids.add(c["channel_id"])
    return ids


def build(client, now, prior_dir=None):
    found = discover(client, now)
    for cid in tracked_ids(prior_dir):
        found.setdefault(cid, {"queries": {"TRACKED"}, "orders": {"tracked"}, "niches": {"tracked"}})
    info = channels(client, found)
    for cid, row in info.items():
        row["discovery_queries"] = sorted(found[cid]["queries"])
        row["discovery_orders"] = sorted(found[cid]["orders"])
        row["niche"] = "christian" if "christian" in found[cid]["niches"] else sorted(found[cid]["niches"])[0]
        age = (now - datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))).days if row["published_at"] else None
        row["age_days"] = age
    # Upload histories: channels created within YOUNG_DAYS first, then any channel
    # with a short public history (old accounts that started recently), so the
    # activity age can be measured from the first upload.
    wanted = [r for r in info.values() if r["uploads_playlist"] and r["videos"] > 0 and
              ((r["age_days"] is not None and r["age_days"] <= YOUNG_DAYS) or r["videos"] <= MAX_HISTORY_VIDEOS)]
    wanted.sort(key=lambda r: (not (r["age_days"] is not None and r["age_days"] <= YOUNG_DAYS), r["videos"]))
    for row in wanted:
        pages = min(MAX_PAGES, -(-row["videos"] // 50))
        if not client.can(pages * 2):
            row["uploads_status"] = "NOT_FETCHED_BUDGET"
            continue
        row["uploads"], row["uploads_truncated"] = uploads(client, row["uploads_playlist"], pages)
        row["uploads_status"] = "FETCHED"
    return {"version": "market-panel-v3", "captured_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "queries": list(QUERIES), "cross_niche_queries": list(CROSS_NICHE_QUERIES), "discovery_window_days": DISCOVERY_DAYS, "young_days": YOUNG_DAYS,
            "region_code": "US", "relevance_language": "en",
            "channels": sorted(info.values(), key=lambda r: r["channel_id"]),
            "data_api_units": client.units, "calls": client.calls, "paid_calls": 0,
            "scope": "PUBLIC_STATISTICS_ONLY; CTR, retention, revenue, RPM and monetization status are not public"}


SHORT_MAX_SECONDS = 180
LONG_MIN_SECONDS = 181


def compact(record):
    """Per-channel aggregates small enough for Git; raw uploads stay in the release."""
    rows = []
    for c in record["channels"]:
        row = {k: c.get(k) for k in ("channel_id", "title", "custom_url", "published_at", "age_days", "country",
                                     "default_language", "subscribers", "views", "videos", "discovery_orders", "niche",
                                     "discovery_queries", "uploads_status")}
        ups = c.get("uploads") or []
        if ups:
            longs = [u for u in ups if (u["duration_seconds"] or 0) >= LONG_MIN_SECONDS]
            shorts = [u for u in ups if 0 < (u["duration_seconds"] or 0) <= SHORT_MAX_SECONDS]
            row["sample"] = {
                "videos": len(ups), "truncated": c.get("uploads_truncated"),
                "long_videos": len(longs), "short_videos": len(shorts),
                "long_views": sum(u["views"] for u in longs), "short_views": sum(u["views"] for u in shorts),
                # Upper bound of public long-form hours if every view watched to the end.
                "long_view_hours_if_full": round(sum(u["views"] * u["duration_seconds"] for u in longs) / 3600, 1),
                "median_long_seconds": sorted(u["duration_seconds"] for u in longs)[len(longs) // 2] if longs else None,
                "first_upload": min(u["published_at"] for u in ups), "last_upload": max(u["published_at"] for u in ups),
                "top_video_views": max(u["views"] for u in ups),
            }
        rows.append(row)
    return {k: record[k] for k in record if k != "channels"} | {"version": "market-panel-compact-v1", "channels": rows}


if __name__ == "__main__":
    out = Path(sys.argv[1])
    client = Client(access_token(), int(sys.argv[2]) if len(sys.argv) > 2 else 7500)
    prior = Path(sys.argv[3]).parent if len(sys.argv) > 3 else None
    record = build(client, datetime.now(timezone.utc), prior)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False) + "\n")
    if len(sys.argv) > 3:
        Path(sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[3]).write_text(json.dumps(compact(record), ensure_ascii=False, indent=0) + "\n")
    young = [c for c in record["channels"] if c.get("uploads_status") == "FETCHED"]
    print(json.dumps({"channels": len(record["channels"]), "young_with_uploads": len(young),
                      "units": record["data_api_units"], "calls": record["calls"]}))
