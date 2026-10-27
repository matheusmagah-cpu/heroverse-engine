"""Offline tests of the read-only Studio client: allowlist, credential secrecy, SAPISIDHASH, parsing, pacing.

Every cookie and response here is synthetic; no request leaves the process.
"""
import contextlib
import datetime as dt
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import sys
import unittest
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio_client as sc  # noqa: E402
from studio_client import (ENDPOINTS, FORBIDDEN_WORDS, ORIGIN, NoRedirect, Pace, StudioClient,  # noqa: E402
                           StudioError, UrllibTransport, guard, parse_cookies, period, sapisidhash)

KEY = "AIza" + "S" * 35                       # synthetic, shaped like the public web key
CHANNEL = "UC" + "a" * 22
VIDEO = "abcdefghijk"
SAPISID = "SYNTHETIC-sapisid-0001/abcdef"
SID = "SYNTHETIC-sid-value-0002"
HEADER_COOKIES = f"SID={SID}; HSID=SYNTHETIC-hsid-03; SAPISID={SAPISID}; LOGIN_INFO=SYNTHETIC-login-04"
NETSCAPE = "\n".join([
    "# Netscape HTTP Cookie File",
    "# synthetic test file",
    f".youtube.com\tTRUE\t/\tTRUE\t4102444800\tSAPISID\t{SAPISID}",
    f"#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t4102444800\tSID\t{SID}",
    "studio.youtube.com\tFALSE\t/\tTRUE\t0\tSTUDIO_ONLY\tSYNTHETIC-studio-05",
    ".youtube.com\tTRUE\t/\tTRUE\t1000\tOLD\tSYNTHETIC-expired-06",
    ".google.com\tTRUE\t/\tTRUE\t4102444800\tNID\tSYNTHETIC-google-07",
    "www.youtube.com\tFALSE\t/\tTRUE\t4102444800\tWWW_ONLY\tSYNTHETIC-www-08",
])
SECRETS = (SAPISID, SID, "SYNTHETIC-hsid-03", "SYNTHETIC-login-04", "SYNTHETIC-studio-05", "SYNTHETIC-google-07")
PAGE_HTML = ('<html><script>ytcfg.set({"INNERTUBE_API_KEY":"%s","CHANNEL_ID":"%s",'
             '"INNERTUBE_CONTEXT_CLIENT_VERSION":"1.20261020.01.00","DELEGATED_SESSION_ID":"123456",'
             '"SESSION_INDEX":0});</script></html>' % (KEY, CHANNEL))
SCREENS = {
    "ANALYTICS_TAB_ID_OVERVIEW": {"cards": [
        {"keyMetricCardData": {"keyMetricTabs": [
            {"primaryContent": {"metric": "EXTERNAL_VIEWS", "total": "1234"}},
            {"primaryContent": {"metric": "EXTERNAL_WATCH_TIME", "total": 5600000}},
            {"primaryContent": {"metric": "SUBSCRIBERS_NET_CHANGE", "total": 12}}]}},
        {"realtimeCardData": {"realtimeViews": {"values": [3, 5, 8, 2]}}}]},
    "ANALYTICS_TAB_ID_REACH": {"cards": [
        {"keyMetricCardData": {"keyMetricTabs": [
            {"primaryContent": {"metric": "VIDEO_THUMBNAIL_IMPRESSIONS", "total": 20000}},
            {"primaryContent": {"metric": "VIDEO_THUMBNAIL_IMPRESSIONS_VTR", "total": 6.1}},
            {"primaryContent": {"metric": "EXTERNAL_VIEWS", "total": 1300}},
            {"primaryContent": {"metric": "UNIQUE_VIEWERS", "total": 900}}]}},
        {"trafficSourceCardData": {"rows": [{"label": "Shorts feed", "value": 70.5},
                                            {"label": "YouTube search", "value": 12},
                                            {"label": "https://bad.example/x", "value": 1},
                                            {"label": "x SYNTHETIC-sid-value-0002", "value": 2}]}}]},
    "ANALYTICS_TAB_ID_ENGAGEMENT": {"cards": [
        {"keyMetricCardData": {"keyMetricTabs": [
            {"primaryContent": {"metric": "AVERAGE_WATCH_TIME", "total": 41000}},
            {"primaryContent": {"metric": "AVERAGE_PERCENTAGE_WATCHED", "total": 78.2}}]}},
        {"audienceRetentionCardData": {"points": [{"x": 0, "y": 100}, {"x": 0.5, "y": 80}, {"x": 1, "y": 60}]}}]},
    "ANALYTICS_TAB_ID_AUDIENCE": {"cards": [{"otherCard": {"metric": "RETURNING_VIEWERS", "total": 300}}]},
}
VIDEOS = {"videos": [
    {"videoId": "AAAAAAAAAAA", "title": "Noah builds the ark", "contentType": "CREATOR_CONTENT_TYPE_SHORTS",
     "timePublishedSeconds": "1793000000", "lengthSeconds": "58",
     "publicMetrics": {"externalViewCount": "500", "likeCount": "40", "commentCount": "3"}},
    {"videoId": "BBBBBBBBBBB", "title": f"echo {SAPISID}", "publicMetrics": {"externalViewCount": "900"}},
    {"videoId": "bad id", "title": "dropped"}]}
CHANNELS = {"channels": [{"channelId": CHANNEL, "title": "HeroVerse",
                          "metric": {"subscriberCount": "321", "videoCount": "40"}}]}


class Fake:
    """A fake HTTP layer: answers by path; records every call."""

    def __init__(self, page=PAGE_HTML, error=None, status=200):
        self.calls, self.page, self.error, self.status = [], page, error, status

    def __call__(self, method, url, headers, data, limit):
        self.calls.append((method, url, headers, json.loads(data) if data else None))
        if self.error:
            raise self.error
        path = url.split("?")[0][len(ORIGIN):]
        if path == "/":
            return self.status, self.page.encode()
        body = json.loads(data)
        if path.endswith("get_screen"):
            return self.status, json.dumps(SCREENS[body["desktopState"]["tabId"]]).encode()
        if path.endswith("list_creator_videos"):
            return self.status, json.dumps(VIDEOS).encode()
        return self.status, json.dumps(CHANNELS).encode()


def no_wait():
    return Pace(min_interval=0, jitter=0, sleep=lambda s: None)


def make(cookies=HEADER_COOKIES, **kw):
    fake = kw.pop("fake", None) or Fake()
    return StudioClient(cookies, fake, kw.pop("pace", None) or no_wait(), now=lambda: 1793000000), fake


def screen_url():
    return ORIGIN + "/youtubei/v1/analytics_data/get_screen?alt=json&key=" + KEY


class Allowlist(unittest.TestCase):
    def refused(self, method, url, body=None):
        with self.assertRaises(StudioError) as ctx:
            guard(method, url, body)
        self.assertEqual(str(ctx.exception), "STUDIO_ENDPOINT_REFUSED", url)

    def test_the_fixed_read_endpoints_pass(self):
        guard("GET", ORIGIN + "/")
        for path in ("/youtubei/v1/creator/get_creator_channels", "/youtubei/v1/creator/list_creator_videos",
                     "/youtubei/v1/analytics_data/get_screen"):
            guard("POST", ORIGIN + path + "?alt=json&key=" + KEY, {"context": {}})
        self.assertEqual(len(ENDPOINTS), 4)

    def test_each_forbidden_word_is_refused_even_when_added_to_the_allowlist(self):
        for word in FORBIDDEN_WORDS:
            for path in (f"/youtubei/v1/{word}", f"/youtubei/v1/creator/{word}_video", f"/youtubei/v1/video_{word}s",
                         f"/youtubei/v1/creator/x{word}y"):
                self.refused("POST", ORIGIN + path + "?alt=json&key=" + KEY, {"context": {}})
                ENDPOINTS[path] = ("POST", frozenset({"context"}))
                try:
                    self.refused("POST", ORIGIN + path + "?alt=json&key=" + KEY, {"context": {}})
                finally:
                    del ENDPOINTS[path]
        # the real write endpoints the cited libraries call
        for path in ("/youtubei/v1/video_manager/metadata_update", "/youtubei/v1/video/delete",
                     "/youtubei/v1/upload/createvideo", "/youtubei/v1/video_editor/edit_video",
                     "/youtubei/v1/playlist/create", "/youtubei/v1/comment/create_comment"):
            self.refused("POST", ORIGIN + path + "?alt=json&key=" + KEY, {"context": {}})

    def test_other_hosts_and_url_tricks_are_refused(self):
        tail = "/youtubei/v1/analytics_data/get_screen?alt=json&key=" + KEY
        for url in ("https://www.youtube.com" + tail, "https://youtube.com" + tail, "https://evil.example" + tail,
                    "https://studio.youtube.com.evil.example" + tail, "https://studio.youtube.com:443" + tail,
                    "https://user@studio.youtube.com" + tail, "http://studio.youtube.com" + tail,
                    "https://STUDIO.youtube.com" + tail, "https://studio.youtube.com" + tail + "#frag",
                    "https://accounts.google.com/ServiceLogin", "studio.youtube.com" + tail, ""):
            self.refused("POST", url, {"context": {}})

    def test_raw_and_unknown_paths_are_refused(self):
        for path in ("/youtubei/v1/creator/get_creator_videos", "/youtubei/v1/analytics_data/get_screen/",
                     "/youtubei/v1/analytics_data/../creator/list_creator_videos", "/youtubei/v1/analytics_data/%67et_screen",
                     "/youtubei/v1/Analytics_data/get_screen", "//youtubei/v1/analytics_data/get_screen",
                     "/youtubei/v1/browse", "/youtubei/v1/player", "/channel/" + CHANNEL, "/video/" + VIDEO + "/edit"):
            self.refused("POST", ORIGIN + path + "?alt=json&key=" + KEY, {"context": {}})

    def test_method_query_and_body_must_match_the_endpoint(self):
        self.refused("GET", screen_url())
        self.refused("DELETE", screen_url(), {"context": {}})
        self.refused("PUT", screen_url(), {"context": {}})
        self.refused("POST", ORIGIN + "/", {"context": {}})
        self.refused("GET", ORIGIN + "/?next=x")
        self.refused("GET", ORIGIN + "/", {"context": {}})
        base = ORIGIN + "/youtubei/v1/analytics_data/get_screen"
        for query in ("", "?alt=json", "?key=" + KEY, "?alt=json&key=bad", "?alt=json&key=%s&prettyPrint=false" % KEY,
                      "?alt=proto&key=" + KEY, "?key=%s&alt=json" % KEY):
            self.refused("POST", base + query, {"context": {}})
        self.refused("POST", screen_url(), None)
        self.refused("POST", screen_url(), {"screenConfig": {}})                    # no context
        self.refused("POST", screen_url(), {"context": {}, "videoUpdate": {}})      # a key no builder sends
        self.refused("POST", screen_url(), [{"context": {}}])

    def test_a_refused_request_never_reaches_the_network_or_the_budget(self):
        client, fake = make()
        client._ensure_config()
        before = (len(fake.calls), client.pace.calls)
        for bad in ("/youtubei/v1/video/delete", "/youtubei/v1/creator/get_creator_videos"):
            with self.assertRaises(StudioError):
                client._request("POST", bad, {"context": {}})
        with self.assertRaises(StudioError):
            client._screen("delete", {"videoId": VIDEO}, "lifetime", None, None)
        self.assertEqual((len(fake.calls), client.pace.calls), before)

    def test_every_request_of_every_tool_is_on_the_allowlist(self):
        client, fake = make()
        client.status()
        client.video_metrics(VIDEO, "2026-09-01", "2026-09-28")
        client.channel_metrics("lifetime", "", 10, 2)
        client.retention(VIDEO)
        self.assertEqual(len(fake.calls), 2 + 4 + 2 + 1 + 2 + 1)
        for method, url, headers, body in fake.calls:
            guard(method, url, body)
            self.assertNotIn(method, ("PUT", "DELETE", "PATCH"))

    def test_no_generic_request_surface(self):
        public = {n for n in dir(StudioClient) if not n.startswith("_")}
        self.assertEqual(public, {"status", "video_metrics", "channel_metrics", "retention", "scrub"})
        server = (Path(__file__).with_name("server.py")).read_text()
        self.assertEqual(sorted(re.findall(r"^def (studio_\w+)", server, re.M)),
                         ["studio_channel_metrics", "studio_retention", "studio_status", "studio_video_metrics"])
        self.assertNotIn("_request", server)
        params = set(re.findall(r"(\w+): (?:str|int|bool)", server))
        self.assertEqual(params, {"video_id", "start", "end", "limit", "per_video", "verify"})


class Credentials(unittest.TestCase):
    def test_missing_cookie_is_a_clear_code_and_no_request(self):
        for empty in ("", "   \n"):
            client, fake = make(empty)
            self.assertEqual(client.status()["error"], "STUDIO_COOKIES_MISSING")
            for call in (lambda: client.video_metrics(VIDEO), lambda: client.channel_metrics(),
                         lambda: client.retention(VIDEO), lambda: client.status(verify=True) and client._ensure_config()):
                with self.assertRaises(StudioError) as ctx:
                    call()
                self.assertEqual(str(ctx.exception), "STUDIO_COOKIES_MISSING")
            self.assertEqual(fake.calls, [])

    def test_environment_variable_is_the_default_source(self):
        import os
        old = os.environ.pop(sc.COOKIE_ENV, None)
        try:
            client = StudioClient(transport=Fake(), pace=no_wait())
            self.assertFalse(client.status()["cookies_configured"])
            os.environ[sc.COOKIE_ENV] = HEADER_COOKIES
            self.assertTrue(StudioClient(transport=Fake(), pace=no_wait()).status(verify=False)["sapisid_present"])
        finally:
            os.environ.pop(sc.COOKIE_ENV, None)
            if old is not None:
                os.environ[sc.COOKIE_ENV] = old

    def test_cookie_without_sapisid_is_invalid(self):
        client, fake = make("SID=SYNTHETIC-sid-only-99")
        self.assertEqual(client.status()["error"], "STUDIO_COOKIES_INVALID")
        with self.assertRaises(StudioError) as ctx:
            client.video_metrics(VIDEO)
        self.assertEqual(str(ctx.exception), "STUDIO_COOKIES_INVALID")
        self.assertEqual(fake.calls, [])

    def test_both_cookie_formats_and_domain_filter(self):
        header = parse_cookies("Cookie: " + HEADER_COOKIES)
        self.assertEqual(header["SAPISID"], SAPISID)
        self.assertEqual(set(header), {"SID", "HSID", "SAPISID", "LOGIN_INFO"})
        netscape = parse_cookies(NETSCAPE)
        self.assertEqual(netscape, {"SAPISID": SAPISID, "SID": SID, "STUDIO_ONLY": "SYNTHETIC-studio-05"})
        self.assertEqual(parse_cookies("__Secure-3PAPISID=SYNTHETIC-3p-value")["__Secure-3PAPISID"],
                         "SYNTHETIC-3p-value")
        with self.assertRaises(StudioError):
            parse_cookies("not a cookie")

    def test_sapisidhash_format_and_value(self):
        value = sapisidhash(SAPISID, 1793000000)
        self.assertRegex(value, r"^SAPISIDHASH 1793000000_[0-9a-f]{40}$")
        expected = hashlib.sha1(f"1793000000 {SAPISID} https://studio.youtube.com".encode()).hexdigest()
        self.assertEqual(value, "SAPISIDHASH 1793000000_" + expected)
        client, fake = make(NETSCAPE)
        client.status()
        method, url, headers, body = fake.calls[1]
        self.assertEqual(headers["Authorization"], value)
        self.assertEqual(headers["X-Origin"], ORIGIN)
        self.assertEqual(headers["Cookie"], f"SAPISID={SAPISID}; SID={SID}; STUDIO_ONLY=SYNTHETIC-studio-05")
        self.assertNotIn("SYNTHETIC-google-07", json.dumps(fake.calls))       # other domains never sent
        self.assertNotIn(SAPISID, url + json.dumps(body))                       # only in headers

    def test_the_cookie_never_appears_in_errors_logs_or_results(self):
        log = io.StringIO()
        handler = logging.StreamHandler(log)
        root = logging.getLogger()
        root.addHandler(handler)
        old_level = root.level
        root.setLevel(logging.DEBUG)
        out, err = io.StringIO(), io.StringIO()
        texts = []
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                for cookies in (HEADER_COOKIES, NETSCAPE):
                    for error in (RuntimeError("Cookie: " + cookies), ValueError(SAPISID), KeyError(SID),
                                  StudioError("STUDIO_UNREACHABLE"), OSError(cookies)):
                        client, _ = make(cookies, fake=Fake(error=error))
                        for call in (client.status, lambda: client.video_metrics(VIDEO)):
                            try:
                                call()
                            except StudioError as exc:
                                texts += [str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__)]
                    client, _ = make(cookies)
                    texts.append(json.dumps(client.status()))
                    texts.append(json.dumps(client.channel_metrics("lifetime", "", 10, 0)))
                    texts.append(json.dumps(client.video_metrics(VIDEO)))
                    texts.append(client.scrub("leak " + cookies + " " + SAPISID))
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        texts += [log.getvalue(), out.getvalue(), err.getvalue()]
        blob = "\n".join(texts)
        for secret in SECRETS:
            self.assertNotIn(secret, blob)
        self.assertIn("STUDIO_TRANSPORT_ERROR", blob)
        self.assertIn("[redacted]", blob)
        # a title echoing a cookie value is dropped, not returned
        self.assertIn('"title": null', blob)


class Parsing(unittest.TestCase):
    def test_config_is_read_from_the_studio_page(self):
        client, fake = make()
        status = client.status()
        self.assertTrue(status["session_verified"])
        self.assertEqual((status["channel_id"], status["channel_title"], status["subscribers"]),
                         (CHANNEL, "HeroVerse", 321))
        ctx = fake.calls[1][3]["context"]
        self.assertEqual(ctx["client"], {"clientName": 62, "clientVersion": "1.20261020.01.00", "hl": "en", "gl": "US"})
        self.assertEqual(ctx["user"]["delegationContext"]["externalChannelId"], CHANNEL)
        self.assertEqual(ctx["user"]["onBehalfOfUser"], "123456")
        self.assertEqual(fake.calls[1][2]["X-YouTube-Client-Version"], "1.20261020.01.00")

    def test_a_signed_out_page_is_reported(self):
        client, _ = make(fake=Fake(page="<html>Sign in - Google Accounts</html>"))
        with self.assertRaises(StudioError) as ctx:
            client.status()
        self.assertEqual(str(ctx.exception), "STUDIO_CONFIG_NOT_FOUND")

    def test_video_metrics_from_synthetic_screens(self):
        client, fake = make()
        result = client.video_metrics(VIDEO, "2026-09-01", "2026-09-28")
        self.assertEqual(result["impressions"], {"value": 20000, "metric": "VIDEO_THUMBNAIL_IMPRESSIONS"})
        self.assertEqual(result["impressions_ctr"]["value"], 6.1)
        self.assertEqual(result["views"], {"value": 1234, "metric": "EXTERNAL_VIEWS"})   # overview read first
        self.assertEqual(result["unique_viewers"]["value"], 900)
        self.assertEqual(result["average_view_duration"]["value"], 41000)
        self.assertEqual(result["average_percentage_viewed"]["value"], 78.2)
        self.assertEqual(result["subscribers_gained"]["value"], 12)
        self.assertEqual(result["other_metrics"], {"RETURNING_VIEWERS": 300})
        self.assertEqual(result["traffic_sources"], [{"source": "Shorts feed", "value": 70.5},
                                                     {"source": "YouTube search", "value": 12}])
        self.assertEqual(result["period"], "2026-09-01..2026-09-28")
        bodies = [c[3] for c in fake.calls[1:]]
        self.assertEqual([b["desktopState"]["tabId"] for b in bodies],
                         ["ANALYTICS_TAB_ID_OVERVIEW", "ANALYTICS_TAB_ID_REACH", "ANALYTICS_TAB_ID_ENGAGEMENT",
                          "ANALYTICS_TAB_ID_AUDIENCE"])
        self.assertEqual(bodies[0]["screenConfig"]["entity"], {"videoId": VIDEO})
        self.assertEqual(bodies[0]["screenConfig"]["timePeriod"]["startDate"], {"year": 2026, "month": 9, "day": 1})

    def test_channel_ranking_and_retention(self):
        client, fake = make()
        result = client.channel_metrics("lifetime", "", 10, 1)
        self.assertEqual(fake.calls[1][3]["screenConfig"]["timePeriod"],
                         {"timePeriodType": "ANALYTICS_TIME_PERIOD_TYPE_LIFETIME"})
        self.assertEqual(fake.calls[1][3]["screenConfig"]["entity"], {"channelId": CHANNEL})
        self.assertEqual(result["realtime"][:2], [{"x": 0, "y": 3}, {"x": 1, "y": 5}])
        videos = result["videos"]
        self.assertEqual([v["video_id"] for v in videos], ["BBBBBBBBBBB", "AAAAAAAAAAA"])
        self.assertEqual(videos[0]["period"]["views"]["value"], 1300)
        self.assertNotIn("period", videos[1])
        self.assertEqual((videos[1]["short"], videos[1]["lifetime_views"], videos[1]["published"]),
                         (True, 500, "2026-10-26"))
        self.assertEqual([v["rank"] for v in videos], [1, 2])
        self.assertEqual(fake.calls[3][3]["pageSize"], 10)
        self.assertNotIn("privacy", json.dumps(fake.calls[3][3]["mask"]))
        retention = client.retention(VIDEO)
        self.assertEqual(retention["retention"], [{"x": 0, "y": 100}, {"x": 0.5, "y": 80}, {"x": 1, "y": 60}])

    def test_inputs_are_validated_before_any_request(self):
        client, fake = make()
        for bad in ("abc", "abcdefghijk/", "abcdefghij?", "../../../aa", 12345678901, None):
            with self.assertRaises(StudioError) as ctx:
                client.video_metrics(bad)
            self.assertEqual(str(ctx.exception), "INVALID_VIDEO_ID")
        today = dt.date.today()
        for start, end, code in (("2026-13-01", "2026-12-01", "INVALID_DATE"), ("yesterday", "", "INVALID_DATE"),
                                 ("2026-09-10", "2026-09-01", "INVALID_DATE_RANGE"),
                                 ("2024-01-01", "2025-06-01", "INVALID_DATE_RANGE"),
                                 ("2001-01-01", "2001-01-02", "INVALID_DATE_RANGE"),
                                 (today.isoformat(), (today + dt.timedelta(days=1)).isoformat(), "INVALID_DATE_RANGE")):
            with self.assertRaises(StudioError) as ctx:
                client.video_metrics(VIDEO, start, end)
            self.assertEqual(str(ctx.exception), code)
        for limit, per_video in ((0, 0), (51, 0), (10, 6), ("10", 0), (True, 0)):
            with self.assertRaises(StudioError):
                client.channel_metrics("", "", limit, per_video)
        self.assertEqual(fake.calls, [])
        kind, first, last = period("", "", today=dt.date(2026, 10, 27))
        self.assertEqual((first, last), (dt.date(2026, 9, 29), dt.date(2026, 10, 26)))


class Pacing(unittest.TestCase):
    def test_minimum_interval_and_session_budget(self):
        clock = [100.0]
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            clock[0] += seconds
        pace = Pace(min_interval=2.5, jitter=1.5, max_calls=4, clock=lambda: clock[0], sleep=sleep, rand=lambda: 0.5)
        client, fake = make(pace=pace)
        client.status()                      # page + channel
        clock[0] += 1.0
        client.retention(VIDEO)               # one more
        self.assertEqual(sleeps, [3.25, 2.25])
        client.retention(VIDEO)               # the fourth
        with self.assertRaises(StudioError) as ctx:
            client.retention(VIDEO)
        self.assertEqual(str(ctx.exception), "STUDIO_CALL_BUDGET_EXHAUSTED")
        self.assertEqual(len(fake.calls), 4)
        defaults = Pace()
        self.assertGreaterEqual(defaults.min_interval, 2)
        self.assertLessEqual(defaults.max_calls, 60)


class Transport(unittest.TestCase):
    def test_http_errors_map_to_fixed_codes_and_redirects_are_refused(self):
        class Opener:
            def __init__(self, exc):
                self.exc = exc

            def open(self, request, timeout):
                raise self.exc
        for exc, code in ((HTTPError(ORIGIN, 401, "x", {}, io.BytesIO()), "STUDIO_SESSION_EXPIRED"),
                          (HTTPError(ORIGIN, 403, "x", {}, io.BytesIO()), "STUDIO_ACCESS_REFUSED"),
                          (HTTPError(ORIGIN, 429, "x", {}, io.BytesIO()), "STUDIO_RATE_LIMITED"),
                          (HTTPError(ORIGIN, 500, SAPISID, {}, io.BytesIO()), "STUDIO_HTTP_REFUSED"),
                          (URLError(SAPISID), "STUDIO_UNREACHABLE"), (TimeoutError(), "STUDIO_UNREACHABLE")):
            with self.assertRaises(StudioError) as ctx:
                UrllibTransport(Opener(exc))("GET", ORIGIN + "/", {}, None, 10)
            self.assertEqual(str(ctx.exception), code)
            self.assertIsNone(ctx.exception.__cause__)
            self.assertIsNone(ctx.exception.__context__)
        with self.assertRaises(StudioError) as ctx:
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://accounts.google.com/ServiceLogin")
        self.assertEqual(str(ctx.exception), "STUDIO_SIGNED_OUT_REDIRECT")

    def test_bad_responses(self):
        for fake, code in ((Fake(status=204), "STUDIO_HTTP_REFUSED"),):
            client, _ = make(fake=fake)
            with self.assertRaises(StudioError) as ctx:
                client.status()
            self.assertEqual(str(ctx.exception), code)

        class Broken(Fake):
            def __call__(self, method, url, headers, data, limit):
                if url.endswith("/"):
                    return super().__call__(method, url, headers, data, limit)
                return 200, b'{"error": {"message": "' + SAPISID.encode() + b'"}}'
        client, _ = make(fake=Broken())
        with self.assertRaises(StudioError) as ctx:
            client.status()
        self.assertEqual(str(ctx.exception), "STUDIO_REQUEST_REFUSED")


if __name__ == "__main__":
    unittest.main()
