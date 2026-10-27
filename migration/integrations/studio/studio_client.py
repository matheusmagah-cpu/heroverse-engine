"""Unofficial, READ-ONLY YouTube Studio analytics client (owner decision, 2026-10-27).

It reads the owner's own Studio analytics with the owner's logged-in Studio session cookies, which the MCP host
injects as the environment variable YT_STUDIO_COOKIES. Read-only by construction:

- every request goes through `guard()` (host exactly studio.youtube.com, a fixed set of read endpoints, a fixed
  method per endpoint, a fixed query, forbidden words refused, only the body keys of that endpoint's builder);
- request bodies are built here from typed, validated arguments; there is no raw-request path;
- only fixed error codes leave this module, and `scrub()` removes every cookie value from any text that does.

Endpoints and request shapes: README.md "Endpoints". Anything marked UNVERIFIED there waits for the live check.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "studio.youtube.com"
ORIGIN = "https://" + HOST
COOKIE_ENV = "YT_STUDIO_COOKIES"
# Studio web client (clientName 62), as in every cited source.
CLIENT_NAME = 62
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0.0.0 Safari/537.36")

# The only endpoints this client may call: path -> (method, the only top-level body keys).
PAGE = "/"
CHANNELS = "/youtubei/v1/creator/get_creator_channels"
VIDEOS = "/youtubei/v1/creator/list_creator_videos"
SCREEN = "/youtubei/v1/analytics_data/get_screen"
ENDPOINTS = {
    PAGE: ("GET", frozenset()),
    CHANNELS: ("POST", frozenset({"context", "channelIds", "mask"})),
    VIDEOS: ("POST", frozenset({"context", "filter", "order", "pageSize", "mask", "pageToken"})),
    SCREEN: ("POST", frozenset({"context", "screenConfig", "desktopState", "fetchingType"})),
}
# Words that name a write. A path holding any of them is refused even if someone adds it to ENDPOINTS
# ("creator" is the one allowed word that contains "create").
FORBIDDEN_WORDS = ("delete", "update", "edit", "set", "upload", "comment", "create", "remove", "mutate",
                   "publish", "privacy")
# Analytics tabs: OVERVIEW and REACH are in the cited sources; ENGAGEMENT and AUDIENCE are UNVERIFIED.
TABS = {"overview": "ANALYTICS_TAB_ID_OVERVIEW", "reach": "ANALYTICS_TAB_ID_REACH",
        "engagement": "ANALYTICS_TAB_ID_ENGAGEMENT", "audience": "ANALYTICS_TAB_ID_AUDIENCE"}

MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_JSON_BYTES = 3 * 1024 * 1024
MAX_COOKIE_TEXT = 64 * 1024
MIN_INTERVAL = 2.5      # seconds between two requests, plus up to JITTER more: a person's pace
JITTER = 1.5
MAX_CALLS = 40          # requests per server process (one MCP session)
TIMEOUT = 20

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")
API_KEY = re.compile(r"AIza[0-9A-Za-z_-]{35}")
METRIC = re.compile(r"[A-Z][A-Z0-9_]{1,79}")
FIRST_DAY = dt.date(2005, 4, 23)   # the first YouTube upload

# Friendly name -> the Studio metric names it may come back as (UNVERIFIED until the live check, except
# VIEWS, read by Rehike, and the REACH tab's first key metric being impressions, read by YouTube-operational-API).
FIELDS = {
    "impressions": ("VIDEO_THUMBNAIL_IMPRESSIONS",),
    "impressions_ctr": ("VIDEO_THUMBNAIL_IMPRESSIONS_VTR",),
    "views": ("EXTERNAL_VIEWS", "VIEWS"),
    "unique_viewers": ("UNIQUE_VIEWERS", "TOTAL_UNIQUE_VIEWERS", "EXTERNAL_UNIQUE_VIEWERS"),
    "average_view_duration": ("AVERAGE_WATCH_TIME", "AVERAGE_VIEW_DURATION", "EXTERNAL_AVERAGE_VIEW_DURATION"),
    "average_percentage_viewed": ("AVERAGE_PERCENTAGE_WATCHED", "AVERAGE_VIEW_PERCENTAGE",
                                  "EXTERNAL_AVERAGE_VIEW_PERCENTAGE"),
    "subscribers_gained": ("SUBSCRIBERS_GAINED", "SUBSCRIBERS_NET_CHANGE"),
    "watch_time": ("EXTERNAL_WATCH_TIME", "WATCH_TIME"),
}
PRIVATE = "Private Studio data: never copy it into public logs, receipts or evidence."


class StudioError(Exception):
    """Only locally defined error codes may leave this boundary."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Studio redirects a signed-out session to the Google sign-in page; never follow it.
        raise StudioError("STUDIO_SIGNED_OUT_REDIRECT")


# ---------------------------------------------------------------- the allowlist: every request goes through it
def guard(method, url, body=None):
    """Refuse, before any network, everything that is not one of the fixed read endpoints."""
    refused = StudioError("STUDIO_ENDPOINT_REFUSED")
    if not isinstance(method, str) or not isinstance(url, str) or len(url) > 300:
        raise refused
    try:
        parts = urlsplit(url)
    except ValueError:
        raise refused from None
    if parts.scheme != "https" or parts.netloc != HOST or parts.fragment:
        raise refused
    path = parts.path
    if not re.fullmatch(r"/(?:[a-z0-9_]+/)*[a-z0-9_]*", path) or "//" in path:
        raise refused
    if any(word in path.replace("creator", "") for word in FORBIDDEN_WORDS):
        raise refused
    if path not in ENDPOINTS:
        raise refused
    allowed_method, body_keys = ENDPOINTS[path]
    if method != allowed_method:
        raise refused
    if method == "GET":
        if parts.query or body is not None:
            raise refused
        return
    try:
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise refused from None
    if len(query) != 2 or query[0] != ("alt", "json") or query[1][0] != "key" or \
            not API_KEY.fullmatch(query[1][1]):
        raise refused
    if not isinstance(body, dict) or "context" not in body or not set(body) <= body_keys:
        raise refused


# ---------------------------------------------------------------- credential handling
def parse_cookies(text):
    """Cookies for studio.youtube.com from Netscape cookies.txt content or a `name=value; ...` header string."""
    if not isinstance(text, str) or not text.strip():
        raise StudioError("STUDIO_COOKIES_MISSING")
    if len(text) > MAX_COOKIE_TEXT:
        raise StudioError("STUDIO_COOKIES_INVALID")
    cookies = {}
    netscape = "\t" in text or text.lstrip().startswith("# Netscape")
    if netscape:
        now = time.time()
        for line in text.splitlines():
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            elif not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) < 7:
                continue
            domain = fields[0].strip().lower().lstrip(".")
            if not domain or not (HOST == domain or HOST.endswith("." + domain)):
                continue
            try:
                expires = int(fields[4] or 0)
            except ValueError:
                expires = 0
            if 0 < expires < now:
                continue
            _keep(cookies, fields[5].strip(), fields[6].strip())
    else:
        header = text.strip()
        if header.lower().startswith("cookie:"):
            header = header[len("cookie:"):]
        for pair in header.split(";"):
            name, sep, value = pair.strip().partition("=")
            if sep:
                _keep(cookies, name.strip(), value.strip())
    if not cookies:
        raise StudioError("STUDIO_COOKIES_INVALID")
    return cookies


def _keep(cookies, name, value):
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name) and 1 <= len(value) <= 4096 and \
            all(33 <= ord(c) <= 126 and c not in ";," for c in value):
        cookies[name] = value


def sapisidhash(sapisid, timestamp, origin=ORIGIN):
    """The Authorization value of the Studio web client: SAPISIDHASH <ts>_<sha1("<ts> <SAPISID> <origin>")>."""
    digest = hashlib.sha1(f"{int(timestamp)} {sapisid} {origin}".encode()).hexdigest()
    return f"SAPISIDHASH {int(timestamp)}_{digest}"


def number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and not re.fullmatch(r"-?[0-9]{1,18}(?:\.[0-9]{1,12})?", value.strip()):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(result) or abs(result) > 1e15:
        return None
    return int(result) if result.is_integer() else result


# ---------------------------------------------------------------- pacing
class Pace:
    """At least MIN_INTERVAL (+ random jitter) between requests and at most MAX_CALLS per session."""

    def __init__(self, min_interval=MIN_INTERVAL, jitter=JITTER, max_calls=MAX_CALLS,
                 clock=time.monotonic, sleep=time.sleep, rand=random.random):
        self.min_interval, self.jitter, self.max_calls = min_interval, jitter, max_calls
        self.clock, self.sleep, self.rand = clock, sleep, rand
        self.calls = 0
        self.last = None

    def acquire(self):
        if self.calls >= self.max_calls:
            raise StudioError("STUDIO_CALL_BUDGET_EXHAUSTED")
        if self.last is not None:
            wait = self.last + self.min_interval + self.jitter * self.rand() - self.clock()
            if wait > 0:
                self.sleep(wait)
        self.last = self.clock()
        self.calls += 1

    def remaining(self):
        return self.max_calls - self.calls


# ---------------------------------------------------------------- transport (replaced by a fake in the tests)
class UrllibTransport:
    def __init__(self, opener=None):
        self._opener = opener or build_opener(NoRedirect())

    def __call__(self, method, url, headers, data, limit):
        request = Request(url, data=data, headers=headers, method=method)
        code = None
        try:
            with self._opener.open(request, timeout=TIMEOUT) as response:
                status = response.status
                raw = response.read(limit + 1)
        except StudioError:
            raise
        except HTTPError as exc:
            code = {401: "STUDIO_SESSION_EXPIRED", 403: "STUDIO_ACCESS_REFUSED",
                    429: "STUDIO_RATE_LIMITED"}.get(exc.code, "STUDIO_HTTP_REFUSED")
            exc.close()
        except (URLError, TimeoutError, OSError, ValueError):
            code = "STUDIO_UNREACHABLE"
        if code:
            raise StudioError(code)     # outside the except block: no __context__ carrying request details
        return status, raw


# ---------------------------------------------------------------- dates
def period(start, end, today=None):
    """("lifetime", "") or two YYYY-MM-DD dates (inclusive, at most 366 days, not in the future)."""
    if start == "lifetime" and end in ("", "lifetime"):
        return "lifetime", None, None
    today = today or dt.date.today()
    if start == "" and end == "":
        last = today - dt.timedelta(days=1)
        return "range", last - dt.timedelta(days=27), last
    days = []
    for value in (start, end):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise StudioError("INVALID_DATE")
        try:
            days.append(dt.date.fromisoformat(value))
        except ValueError:
            raise StudioError("INVALID_DATE") from None
    first, last = days
    if first < FIRST_DAY or last > today or first > last or (last - first).days > 365:
        raise StudioError("INVALID_DATE_RANGE")
    return "range", first, last


def time_period(kind, first, last):
    if kind == "lifetime":   # Rehike, ChannelUtils.php
        return {"timePeriodType": "ANALYTICS_TIME_PERIOD_TYPE_LIFETIME"}
    # UNVERIFIED: the custom-range shape; the live check confirms or corrects it (README "Live check").
    return {"timePeriodType": "ANALYTICS_TIME_PERIOD_TYPE_CUSTOM",
            "startDate": {"year": first.year, "month": first.month, "day": first.day},
            "endDate": {"year": last.year, "month": last.month, "day": last.day}}


def video_id_ok(video_id):
    if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id):
        raise StudioError("INVALID_VIDEO_ID")
    return video_id


# ---------------------------------------------------------------- the client
class StudioClient:
    def __init__(self, cookie_text=None, transport=None, pace=None, now=time.time):
        self._cookie_text = os.environ.get(COOKIE_ENV, "") if cookie_text is None else cookie_text
        self._transport = transport or UrllibTransport()
        self.pace = pace or Pace()
        self._now = now
        self._config = None
        self._cookies = None
        self._secrets = ()
        try:
            self._cookies = parse_cookies(self._cookie_text)
        except StudioError:
            self._cookies = None
        self._secrets = self._secret_values()

    # -- secrets
    def _secret_values(self):
        """The cookie text and every cookie value in it, of any domain and either format."""
        values = set()
        text = self._cookie_text if isinstance(self._cookie_text, str) else ""
        if text.strip():
            values.update({text, text.strip()})
        for line in text.splitlines():
            fields = line.split("\t")
            if len(fields) >= 7:
                values.add(fields[6].strip())
                continue
            for pair in line.split(";"):
                name, sep, value = pair.partition("=")
                if sep:
                    values.add(value.strip())
        values.update((self._cookies or {}).values())
        return tuple(sorted((v for v in values if len(v) >= 6), key=len, reverse=True))

    def scrub(self, text):
        """Remove every cookie value (and the cookie text) from a message that may leave the process."""
        text = str(text)
        for secret in self._secrets:
            text = text.replace(secret, "[redacted]")
        return text

    def _sapisid(self):
        if not isinstance(self._cookie_text, str) or not self._cookie_text.strip():
            raise StudioError("STUDIO_COOKIES_MISSING")
        if not self._cookies:
            raise StudioError("STUDIO_COOKIES_INVALID")
        value = self._cookies.get("SAPISID") or self._cookies.get("__Secure-3PAPISID")
        if not value:
            raise StudioError("STUDIO_COOKIES_INVALID")
        return value

    # -- the one request function
    def _request(self, method, path, body=None):
        sapisid = self._sapisid()
        url = ORIGIN + path
        if method == "POST":
            url += "?alt=json&key=" + self._config["api_key"]
        guard(method, url, body)          # refused before any pacing or network
        self.pace.acquire()
        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        headers = {
            "Authorization": sapisidhash(sapisid, self._now()),
            "Cookie": cookie_header,
            "Origin": ORIGIN, "X-Origin": ORIGIN, "Referer": ORIGIN + "/",
            "User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9",
        }
        data = None
        limit = MAX_PAGE_BYTES
        if method == "POST":
            limit = MAX_JSON_BYTES
            headers.update({"Content-Type": "application/json", "Accept": "application/json",
                            "X-Goog-AuthUser": self._config["session_index"],
                            "X-YouTube-Client-Name": str(CLIENT_NAME),
                            "X-YouTube-Client-Version": self._config["client_version"]})
            data = json.dumps(body, separators=(",", ":")).encode()
        failed = False
        try:
            status, raw = self._transport(method, url, headers, data, limit)
        except StudioError:
            raise
        except Exception:
            failed = True
        if failed:
            # An unexpected transport error may carry request details (the Cookie header): it is dropped, and
            # raised outside the except block so it is not even kept as __context__.
            raise StudioError("STUDIO_TRANSPORT_ERROR")
        if status != 200:
            raise StudioError("STUDIO_HTTP_REFUSED")
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > limit:
            raise StudioError("STUDIO_RESPONSE_TOO_LARGE")
        if method == "GET":
            return raw.decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise StudioError("STUDIO_INVALID_RESPONSE") from None
        if not isinstance(payload, dict):
            raise StudioError("STUDIO_INVALID_RESPONSE")
        if "error" in payload:
            raise StudioError("STUDIO_REQUEST_REFUSED")
        return payload

    def _ensure_config(self):
        if self._config:
            return self._config
        self._sapisid()
        html = self._request("GET", PAGE)

        def find(key, pattern):
            m = re.search(r'"%s"\s*:\s*"?(%s)"?' % (key, pattern), html)
            return m.group(1) if m else None
        api_key = find("INNERTUBE_API_KEY", r"AIza[0-9A-Za-z_-]{35}")
        channel = find("CHANNEL_ID", r"UC[A-Za-z0-9_-]{22}")
        version = find("INNERTUBE_CONTEXT_CLIENT_VERSION", r"[0-9][0-9.]{0,31}")
        if not api_key or not channel or not version:
            # A signed-out session gets a page without the creator config.
            raise StudioError("STUDIO_CONFIG_NOT_FOUND")
        self._config = {"api_key": api_key, "channel_id": channel, "client_version": version,
                        "delegated": find("DELEGATED_SESSION_ID", r"[0-9]{1,30}"),
                        "session_index": find("SESSION_INDEX", r"[0-9]{1,2}") or "0"}
        return self._config

    def _context(self):
        c = self._config
        user = {"delegationContext": {"externalChannelId": c["channel_id"],
                                      "roleType": {"channelRoleType": "CREATOR_CHANNEL_ROLE_TYPE_OWNER"}}}
        if c["delegated"]:
            user["onBehalfOfUser"] = c["delegated"]
        return {"client": {"clientName": CLIENT_NAME, "clientVersion": c["client_version"], "hl": "en", "gl": "US"},
                "user": user, "request": {"returnLogEntry": True, "internalExperimentFlags": []}}

    # -- body builders (typed arguments only)
    def _screen(self, tab, entity, kind, first, last):
        if tab not in TABS:
            raise StudioError("STUDIO_ENDPOINT_REFUSED")
        body = {"context": self._context(),
                "screenConfig": {"entity": entity, "timePeriod": time_period(kind, first, last),
                                 "currency": "USD", "timeZoneOffsetSecs": 0},
                "desktopState": {"tabId": TABS[tab]},
                "fetchingType": "FETCHING_TYPE_FOREGROUND"}
        return self._request("POST", SCREEN, body)

    def _channel(self):
        body = {"context": self._context(), "channelIds": [self._config["channel_id"]],
                "mask": {"channelId": True, "title": True, "metric": {"all": True}}}
        return self._request("POST", CHANNELS, body)

    def _videos(self, page_size):
        ch = self._config["channel_id"]
        body = {"context": self._context(),
                "filter": {"and": {"operands": [{"channelIdIs": {"value": ch}},
                                                {"videoOriginIs": {"value": "VIDEO_ORIGIN_UPLOAD"}}]}},
                "order": "VIDEO_ORDER_DISPLAY_TIME_DESC", "pageSize": page_size,
                "mask": {"videoId": True, "title": True, "contentType": True, "lengthSeconds": True,
                         "timePublishedSeconds": True, "publicMetrics": {"all": True}}}
        return self._request("POST", VIDEOS, body)

    # -- safe text
    def _text(self, value, limit=200):
        if not isinstance(value, str):
            return None
        value = value.strip()[:limit]
        if any(ord(c) < 32 for c in value) or self.scrub(value) != value:
            return None
        return value

    # -- tools
    def status(self, verify=True):
        out = {"unofficial": True, "read_only": True, "host": HOST, "transport": "stdio",
               "cookies_configured": bool(isinstance(self._cookie_text, str) and self._cookie_text.strip()),
               "cookies_parsed": bool(self._cookies),
               "sapisid_present": bool(self._cookies and (self._cookies.get("SAPISID")
                                                           or self._cookies.get("__Secure-3PAPISID"))),
               "session_verified": False, "calls_remaining": self.pace.remaining()}
        if not verify or not out["sapisid_present"]:
            if not out["cookies_configured"]:
                out["error"] = "STUDIO_COOKIES_MISSING"
            elif not out["sapisid_present"]:
                out["error"] = "STUDIO_COOKIES_INVALID"
            return out
        self._ensure_config()
        data = self._channel()
        channels = data.get("channels")
        row = channels[0] if isinstance(channels, list) and channels and isinstance(channels[0], dict) else {}
        metric = row.get("metric") if isinstance(row.get("metric"), dict) else {}
        out.update({"session_verified": True, "channel_id": self._config["channel_id"],
                    "channel_title": self._text(row.get("title"), 100),
                    "subscribers": number(metric.get("subscriberCount")),
                    "videos": number(metric.get("videoCount")),
                    "calls_remaining": self.pace.remaining(), "notice": PRIVATE})
        return out

    def video_metrics(self, video_id, start="", end=""):
        video_id_ok(video_id)
        kind, first, last = period(start, end)
        self._ensure_config()
        merged, extra, cards, traffic = {}, {}, set(), []
        for tab in ("overview", "reach", "engagement", "audience"):
            screen = self._screen(tab, {"videoId": video_id}, kind, first, last)
            key, other = key_metrics(screen)
            for k, v in key.items():
                merged.setdefault(k, v)
            for k, v in other.items():
                extra.setdefault(k, v)
            cards |= card_types(screen)
            if tab == "reach":
                traffic = [r for r in traffic_sources(screen) if self._text(r["source"], 80) == r["source"]]
        return {"video_id": video_id, "period": period_label(kind, first, last),
                **friendly(merged, extra), "metrics": merged, "other_metrics": extra,
                "traffic_sources": traffic, "card_types": sorted(cards)[:60],
                "unverified": "metric names, units, custom range and traffic-source shape until the live check",
                "calls_remaining": self.pace.remaining(), "notice": PRIVATE}

    def channel_metrics(self, start="", end="", limit=10, per_video=3):
        if type(limit) is not int or not 1 <= limit <= 50 or type(per_video) is not int or not 0 <= per_video <= 5:
            raise StudioError("INVALID_LIMIT")
        kind, first, last = period(start, end)
        self._ensure_config()
        ch = {"channelId": self._config["channel_id"]}
        merged, extra, cards = {}, {}, set()
        traffic, realtime = [], []
        for tab in ("overview", "reach"):
            screen = self._screen(tab, ch, kind, first, last)
            key, other = key_metrics(screen)
            for k, v in key.items():
                merged.setdefault(k, v)
            for k, v in other.items():
                extra.setdefault(k, v)
            cards |= card_types(screen)
            if tab == "reach":
                traffic = [r for r in traffic_sources(screen) if self._text(r["source"], 80) == r["source"]]
            else:
                realtime = series(screen, "realtime")
        rows = parse_videos(self._videos(limit), self._text)
        rows.sort(key=lambda r: -(r["lifetime_views"] or 0))
        for row in rows[:per_video]:
            key, other = key_metrics(self._screen("reach", {"videoId": row["video_id"]}, kind, first, last))
            f = friendly(key, other)
            row["period"] = {k: f[k] for k in ("impressions", "impressions_ctr", "views", "unique_viewers")}
        def period_views(row):
            views = (row.get("period") or {}).get("views")
            return views["value"] if isinstance(views, dict) else None
        rows.sort(key=lambda r: (period_views(r) is None, -(period_views(r) or 0), -(r["lifetime_views"] or 0)))
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank
        return {"channel_id": self._config["channel_id"], "period": period_label(kind, first, last),
                **friendly(merged, extra), "metrics": merged, "other_metrics": extra,
                "traffic_sources": traffic, "realtime": realtime[:60], "videos": rows,
                "card_types": sorted(cards)[:60],
                "unverified": "metric names, units, custom range, traffic-source and realtime shapes until the live "
                              "check; lifetime_views comes from the video list (publicMetrics)",
                "calls_remaining": self.pace.remaining(), "notice": PRIVATE}

    def retention(self, video_id, start="lifetime", end=""):
        video_id_ok(video_id)
        kind, first, last = period(start, end)
        self._ensure_config()
        screen = self._screen("engagement", {"videoId": video_id}, kind, first, last)
        key, other = key_metrics(screen)
        return {"video_id": video_id, "period": period_label(kind, first, last),
                "retention": series(screen, "retention"), **friendly(key, other), "metrics": key,
                "card_types": sorted(card_types(screen))[:60],
                "unverified": "the ENGAGEMENT tab id and the retention curve shape until the live check",
                "calls_remaining": self.pace.remaining(), "notice": PRIVATE}


# ---------------------------------------------------------------- response parsing (bounded, defensive)
def _walk(node, depth=0, budget=None):
    budget = budget if budget is not None else [20000]
    if depth > 40 or budget[0] <= 0:
        return
    budget[0] -= 1
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value, depth + 1, budget)
    elif isinstance(node, list):
        for value in node[:500]:
            yield from _walk(value, depth + 1, budget)


def key_metrics(screen):
    """(key metrics, other metrics): `cards[].keyMetricCardData.keyMetricTabs[].primaryContent{metric,total}` is the
    shape both sources read; any other {metric, total} pair elsewhere in the screen goes to the second map."""
    key, other = {}, {}
    cards = screen.get("cards") if isinstance(screen, dict) else None
    for card in cards if isinstance(cards, list) else []:
        data = card.get("keyMetricCardData") if isinstance(card, dict) else None
        tabs = data.get("keyMetricTabs") if isinstance(data, dict) else None
        for tab in tabs if isinstance(tabs, list) else []:
            content = tab.get("primaryContent") if isinstance(tab, dict) else None
            if isinstance(content, dict):
                name, total = content.get("metric"), number(content.get("total"))
                if isinstance(name, str) and METRIC.fullmatch(name) and total is not None:
                    key.setdefault(name, total)
    for node in _walk(screen):
        if isinstance(node, dict) and isinstance(node.get("metric"), str) and METRIC.fullmatch(node["metric"]):
            total = number(node.get("total"))
            if total is not None and node["metric"] not in key:
                other.setdefault(node["metric"], total)
    return key, other


def friendly(key, other):
    out = {}
    for field, names in FIELDS.items():
        out[field] = None
        for name in names:
            for source in (key, other):
                if name in source:
                    out[field] = {"value": source[name], "metric": name}
                    break
            if out[field]:
                break
    return out


def card_types(screen):
    cards = screen.get("cards") if isinstance(screen, dict) else None
    found = set()
    for card in cards if isinstance(cards, list) else []:
        if isinstance(card, dict):
            found |= {k for k in card if isinstance(k, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,60}", k)}
    return found


LABEL_KEYS = ("label", "displayName", "name", "title", "trafficSourceType", "dimensionValue")
VALUE_KEYS = ("value", "total", "count", "views", "percentage", "percent")


def traffic_sources(screen):
    """UNVERIFIED shape: rows (label, value) inside any object whose key mentions trafficSource."""
    rows, seen = [], set()
    for node in _walk(screen):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if "trafficsource" not in str(key).lower():
                continue
            for item in _walk(value):
                if not isinstance(item, dict) or len(rows) >= 30:
                    continue
                label = next((item[k] for k in LABEL_KEYS if isinstance(item.get(k), str)), None)
                amount = next((number(item[k]) for k in VALUE_KEYS if number(item.get(k)) is not None), None)
                if label is None or amount is None or len(label) > 80 or re.search(r"https?://", label) \
                        or any(ord(c) < 32 for c in label) or (label, amount) in seen:
                    continue
                seen.add((label, amount))
                rows.append({"source": label, "value": amount})
    return rows


def series(screen, word):
    """UNVERIFIED shape: the first numeric series under a key mentioning `word` (a list of numbers, or of objects
    with two numeric fields), at most 200 points."""
    for node in _walk(screen):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if word not in str(key).lower():
                continue
            for item in _walk(value):
                if isinstance(item, list) and len(item) >= 2:
                    nums = [number(x) for x in item[:200]]
                    if all(n is not None for n in nums):
                        return [{"x": i, "y": n} for i, n in enumerate(nums)]
                    pairs = []
                    for x in item[:200]:
                        vals = [number(v) for v in x.values()] if isinstance(x, dict) else []
                        vals = [v for v in vals if v is not None]
                        if len(vals) < 2:
                            pairs = []
                            break
                        pairs.append({"x": vals[0], "y": vals[1]})
                    if pairs:
                        return pairs
    return []


def parse_videos(data, text):
    rows = []
    videos = data.get("videos") if isinstance(data, dict) else None
    for v in videos if isinstance(videos, list) else []:
        if not isinstance(v, dict) or not isinstance(v.get("videoId"), str) or not VIDEO_ID.fullmatch(v["videoId"]):
            continue
        pm = v.get("publicMetrics") if isinstance(v.get("publicMetrics"), dict) else {}
        published = number(v.get("timePublishedSeconds"))
        rows.append({"video_id": v["videoId"], "title": text(v.get("title")),
                     "short": v.get("contentType") == "CREATOR_CONTENT_TYPE_SHORTS",
                     "published": (dt.datetime.fromtimestamp(published, dt.timezone.utc).date().isoformat()
                                   if published and 0 < published < 4e9 else None),
                     "length_seconds": number(v.get("lengthSeconds")),
                     "lifetime_views": number(pm.get("externalViewCount")),
                     "likes": number(pm.get("likeCount")), "comments": number(pm.get("commentCount"))})
    return rows


def period_label(kind, first, last):
    return "lifetime" if kind == "lifetime" else f"{first.isoformat()}..{last.isoformat()}"
