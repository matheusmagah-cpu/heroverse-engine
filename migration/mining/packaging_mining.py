#!/usr/bin/env python3
"""Packaging and channel-setup mining (titles, descriptions, tags, hashtags,
thumbnails, upload hour and cadence, channel settings) of the fastest young
channels, measured in code from public Data API fields.

Channels: the model's fast <= 90-day faith channels (policy-clean, English) plus,
optionally, young fast channels of other niches found by EXTRA_QUERIES (search
by views, last 90 days): what converts viewers into subscribers fastest there
can be borrowed as packaging, never as content or identity.

Per video (latest uploads): title shape, description shape (first line, length,
hashtags, links, chapters, scripture refs, CTAs), tags, category, language,
made-for-kids, upload hour/weekday, duration, views/day, likes and comments per
1k. Per channel: description, keywords, country, language, trailer, playlists,
cadence, subscribers per 1k views. The top third of videos by views/day is
compared with the rest. Thumbnails of each channel's best videos are described
by a free Gemini model (MODEL_REPORTED).
usage: packaging_mining.py MODEL_JSON OUT_DIR [EXTRA_QUERIES (; separated)] [THUMBS_PER_CHANNEL]
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import market_panel as mp  # noqa: E402
from blueprint_stats import BORROWED  # noqa: E402

UNITS = 500
LATEST = 30
HASHTAG = re.compile(r"(?<!\w)#(\w{2,40})")
LINK = re.compile(r"https?://\S+")
CHAPTER = re.compile(r"^\s*\(?(\d{1,2}:)?\d{1,2}:\d{2}\)?\s+\S", re.M)
SCRIPTURE = re.compile(r"\b(?:[1-3] )?[A-Z][a-z]+ \d{1,3}:\d{1,3}\b")
CTA = {"subscribe": r"\bsubscrib", "comment": r"\bcomment", "amen": r"\bamen\b", "like": r"\blike\b",
       "share": r"\bshare\b", "bell": r"\bbell\b|notification"}
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
STOP = set("the a an to of and or in on at for with your you my is be this that it i me we our god's".split())


def seconds(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def english(titles):
    text = " ".join(titles)
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) >= 0.95


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def share(rows, key):
    return round(sum(1 for r in rows if r[key]) / len(rows), 2) if rows else None


def video_row(v, now):
    sn, st, cd = v["snippet"], v.get("statistics", {}), v.get("contentDetails", {})
    title, desc = sn["title"], sn.get("description", "")
    published = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
    age = max((now - published).total_seconds() / 86400, 0.5)
    views = int(st.get("viewCount", 0))
    words = title.split()
    tags = sn.get("tags", [])
    return {
        "video_id": v["id"], "title": title, "published_at": sn["publishedAt"],
        "hour_utc": published.hour, "weekday": published.strftime("%a"), "seconds": seconds(cd.get("duration")),
        "short": seconds(cd.get("duration")) <= 180, "views": views, "views_per_day": round(views / age, 1),
        "likes_per_1k": round(1000 * int(st.get("likeCount", 0)) / views, 1) if views else None,
        "comments_per_1k": round(1000 * int(st.get("commentCount", 0)) / views, 2) if views else None,
        "title_chars": len(title), "title_words": len(words),
        "title_upper_ratio": round(sum(w.isupper() and len(w) > 1 for w in words) / max(len(words), 1), 2),
        "title_emoji": bool(EMOJI.search(title)), "title_separator": bool(re.search(r"[|:–—-]\s", title)),
        "title_number": bool(re.search(r"\d", title)), "title_question": "?" in title,
        "title_you": bool(re.search(r"\byou(r)?\b", title, re.I)),
        "desc_chars": len(desc), "desc_first_line": desc.split("\n", 1)[0][:160],
        "hashtags": [h.lower() for h in HASHTAG.findall(desc + " " + title)], "links": len(LINK.findall(desc)),
        "chapters": len(CHAPTER.findall(desc)), "scripture_refs": len(SCRIPTURE.findall(desc)),
        "ctas": [k for k, p in CTA.items() if re.search(p, desc, re.I)],
        "tags": tags, "tag_count": len(tags), "tag_chars": sum(len(t) + 1 for t in tags),
        "category": sn.get("categoryId"), "audio_language": sn.get("defaultAudioLanguage"),
        "made_for_kids": v.get("status", {}).get("madeForKids"), "thumbnail": (sn.get("thumbnails", {}).get("high") or {}).get("url"),
    }


def channel_record(client, c, now, group):
    sn, br, stc = c["snippet"], c.get("brandingSettings", {}).get("channel", {}), c["statistics"]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["contentDetails"]["videoId"] for i in client.get(
        "playlistItems", {"part": "contentDetails", "playlistId": uploads, "maxResults": LATEST}, 1)["items"]]
    vids = client.get("videos", {"part": "snippet,contentDetails,statistics,status", "id": ",".join(ids)}, 1)["items"] if ids else []
    rows = [video_row(v, now) for v in vids]
    playlists = client.get("playlists", {"part": "id", "channelId": c["id"], "maxResults": 50}, 1).get("pageInfo", {}).get("totalResults")
    created = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
    times = sorted(datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")) for r in rows)
    span = max((times[-1] - times[0]).total_seconds() / 86400, 1) if len(times) > 1 else None
    views, subs = int(stc.get("viewCount", 0)), int(stc.get("subscriberCount", 0))
    return {"channel_id": c["id"], "title": sn["title"], "group": group, "age_days": (now - created).days,
            "subscribers": subs, "views": views, "subs_per_1k_views": round(1000 * subs / views, 2) if views else None,
            "subs_per_day": round(subs / max((now - created).days, 1), 1), "country": sn.get("country"),
            "default_language": sn.get("defaultLanguage") or br.get("defaultLanguage"),
            "description_chars": len(sn.get("description", "")), "description": sn.get("description", "")[:600],
            "keywords": br.get("keywords", ""), "keyword_count": len(re.findall(r'"[^"]+"|\S+', br.get("keywords", ""))),
            "has_trailer": bool(br.get("unsubscribedTrailer")), "playlists": playlists,
            "uploads_per_day": round(len(times) / span, 2) if span else None, "videos": rows}


def summary(rows):
    def block(rs):
        return {"n": len(rs), "title_chars": med([r["title_chars"] for r in rs]), "title_words": med([r["title_words"] for r in rs]),
                "title_upper_ratio": med([r["title_upper_ratio"] for r in rs]), "emoji": share(rs, "title_emoji"),
                "separator": share(rs, "title_separator"), "number": share(rs, "title_number"),
                "question": share(rs, "title_question"), "you": share(rs, "title_you"),
                "desc_chars": med([r["desc_chars"] for r in rs]), "hashtags": med([len(r["hashtags"]) for r in rs]),
                "links": med([r["links"] for r in rs]), "chapters_share": round(sum(r["chapters"] > 0 for r in rs) / len(rs), 2) if rs else None,
                "scripture_refs": med([r["scripture_refs"] for r in rs]), "tag_count": med([r["tag_count"] for r in rs]),
                "tag_chars": med([r["tag_chars"] for r in rs]), "seconds": med([r["seconds"] for r in rs]),
                "likes_per_1k": med([r["likes_per_1k"] for r in rs]), "comments_per_1k": med([r["comments_per_1k"] for r in rs]),
                "cta_share": {k: round(sum(k in r["ctas"] for r in rs) / len(rs), 2) for k in CTA} if rs else {},
                "hour_utc": Counter(r["hour_utc"] for r in rs).most_common(6),
                "weekday": Counter(r["weekday"] for r in rs).most_common(7)}
    out = {}
    for kind in ("long", "short"):
        rs = sorted([r for r in rows if r["short"] == (kind == "short")], key=lambda r: r["views_per_day"], reverse=True)
        if not rs:
            continue
        top = rs[: max(1, len(rs) // 3)]
        words = Counter(w for r in top for w in re.findall(r"[a-z']+", r["title"].lower()) if w not in STOP and len(w) > 2)
        out[kind] = {"top_third": block(top), "rest": block(rs[len(top):]),
                     "top_title_words": words.most_common(25),
                     "top_tags": Counter(t.lower() for r in top for t in r["tags"]).most_common(30),
                     "top_hashtags": Counter(h for r in top for h in r["hashtags"]).most_common(20),
                     "top_examples": [{k: r[k] for k in ("title", "views_per_day", "desc_first_line", "tag_count", "hour_utc")} for r in top[:8]]}
    return out


def discover_other(client, queries, now):
    after = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found = {}
    for q in queries:
        if not client.can(101):
            break
        for it in client.get("search", {"part": "snippet", "type": "video", "q": q, "order": "viewCount",
                                        "publishedAfter": after, "relevanceLanguage": "en", "maxResults": 50}, 100)["items"]:
            found.setdefault(it["snippet"]["channelId"], q)
    return found


def main(model_json, out_dir, extra_queries="", thumbs_per_channel="2"):
    now = datetime.now(timezone.utc)
    client = mp.Client(mp.access_token(), UNITS)
    model = json.loads(Path(model_json).read_text())
    groups = {c["channel_id"]: "faith_fast_90d" for c in model["fast_le_90d_channels"]}
    queries = [q.strip() for q in extra_queries.split(";") if q.strip()]
    other = discover_other(client, queries, now) if queries else {}
    ids = list(groups) + [c for c in other if c not in groups]
    channels, excluded = [], []
    for k in range(0, len(ids), 50):
        for c in client.get("channels", {"part": "snippet,statistics,contentDetails,brandingSettings", "id": ",".join(ids[k:k + 50])}, 1)["items"]:
            group = groups.get(c["id"])
            if not group:  # other niche: keep only young, fast, sizeable channels
                age = (now - datetime.fromisoformat(c["snippet"]["publishedAt"].replace("Z", "+00:00"))).days
                subs = int(c["statistics"].get("subscriberCount", 0))
                if age > 180 or subs < 10000 or subs / max(age, 1) < 100:
                    continue
                group = "other:" + other[c["id"]]
            if BORROWED.search(c["snippet"]["title"] + " " + c["snippet"].get("description", "")[:600]):
                excluded.append({"channel": c["snippet"]["title"], "reason": "borrowed identity or recordings (policy)"})
                continue
            if not client.can(3):
                break
            rec = channel_record(client, c, now, group)
            if not english([v["title"] for v in rec["videos"]]):
                excluded.append({"channel": rec["title"], "reason": "not English"})
                continue
            channels.append(rec)
    key = os.environ.get("HERO_GEMINI_API_KEY", "")
    if key:
        import structure_mining as sm
        for rec in channels:
            for v in sorted(rec["videos"], key=lambda r: r["views_per_day"], reverse=True)[: int(thumbs_per_channel)]:
                try:
                    v["thumbnail_analysis"] = sm.thumbnail(v, key, sm.FREE_MODELS)
                except Exception as e:  # one unreadable thumbnail never stops the run
                    v["thumbnail_analysis"] = {"status": f"UNAVAILABLE_{type(e).__name__}"}
    by_group = {}
    for g in sorted({c["group"].split(":")[0] for c in channels}):
        cs = [c for c in channels if c["group"].split(":")[0] == g]
        by_group[g] = {"channels": len(cs), "videos": summary([v for c in cs for v in c["videos"]]),
                       "channel_settings": {
                           "description_chars": med([c["description_chars"] for c in cs]),
                           "keyword_count": med([c["keyword_count"] for c in cs]),
                           "has_trailer": share(cs, "has_trailer"), "playlists": med([c["playlists"] for c in cs]),
                           "uploads_per_day": med([c["uploads_per_day"] for c in cs]),
                           "subs_per_1k_views": med([c["subs_per_1k_views"] for c in cs]),
                           "country": Counter(c["country"] for c in cs).most_common(5),
                           "default_language": Counter(c["default_language"] for c in cs).most_common(5)},
                       "best_converting": [{k: c[k] for k in ("title", "group", "subscribers", "age_days", "subs_per_day", "subs_per_1k_views", "uploads_per_day", "keywords")}
                                           for c in sorted(cs, key=lambda c: c["subs_per_1k_views"] or 0, reverse=True)[:10]]}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = {"version": "packaging-mining-v1", "captured_at": now.isoformat(), "data_api_units": client.units,
              "queries": queries, "by_group": by_group, "excluded": excluded, "channels": channels,
              "note": "public fields only; CTR and retention are not public. Thumbnail descriptions are MODEL_REPORTED."}
    (out / "packaging.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"channels": len(channels), "excluded": len(excluded), "units": client.units,
                      "groups": {g: v["channels"] for g, v in by_group.items()}}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
