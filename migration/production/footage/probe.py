#!/usr/bin/env python3
"""One-off probe (2026-10-23): which licensed footage sources are reachable from GitHub Actions, and how much
1080p+ nature footage they return for our themes. Prints counts only; downloads nothing but one sample."""
import json
import os
import urllib.parse
import urllib.request

THEMES = ["sunrise clouds", "forest light rays", "ocean waves", "candle flame", "river stream", "starry night sky",
          "mountain lake", "rain window", "wheat field wind", "waterfall"]
UA = {"User-Agent": "HeroVerseProbe/1.0 (github actions)"}


def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def commons(q):
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
           f"&gsrsearch={urllib.parse.quote('filetype:video ' + q)}&gsrlimit=50&prop=imageinfo"
           "&iiprop=size|url|extmetadata&iiextmetadatafilter=LicenseShortName")
    pages = get(url).get("query", {}).get("pages", {}).values()
    hd = [p for p in pages if (p["imageinfo"][0].get("height") or 0) >= 1080]
    lic = sorted({p["imageinfo"][0].get("extmetadata", {}).get("LicenseShortName", {}).get("value", "?") for p in hd})
    return len(list(pages)), len(hd), lic[:6]


def pexels(q, key):
    d = get(f"https://api.pexels.com/videos/search?query={urllib.parse.quote(q)}&per_page=40&orientation=landscape",
            {"Authorization": key})
    hd = [v for v in d.get("videos", []) if any((f.get("height") or 0) >= 1080 for f in v.get("video_files", []))]
    return d.get("total_results"), len(hd)


key = os.environ.get("PEXELS_API_KEY", "")
print("PEXELS_KEY_PRESENT", bool(key))
for q in THEMES:
    try:
        print("COMMONS", q, commons(q))
    except Exception as e:  # noqa: BLE001
        print("COMMONS_ERR", q, type(e).__name__, str(e)[:120])
    if key:
        try:
            print("PEXELS", q, pexels(q, key))
        except Exception as e:  # noqa: BLE001
            print("PEXELS_ERR", q, type(e).__name__, str(e)[:120])
for name, url in (("pixabay", "https://pixabay.com/api/videos/?q=sunrise"), ("pexels_nokey", "https://api.pexels.com/videos/search?query=sunrise")):
    try:
        get(url)
        print("REACH", name, "200")
    except Exception as e:  # noqa: BLE001
        print("REACH", name, type(e).__name__, str(e)[:80])
