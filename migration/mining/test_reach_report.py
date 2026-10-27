#!/usr/bin/env python3
"""Offline checks of the impressions / CTR / clicks report (YouTube Reporting API reach reports; no network)."""
from datetime import datetime, timezone
import contextlib
import email.message
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import urllib.response

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reach_report as rr  # noqa: E402

NOW = datetime(2026, 10, 27, 13, 0, tzinfo=timezone.utc)
HEAD = "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
# the real shape of our 2026-10-12 report (evidence/owned-reach-two-report-receipt.json): ctr is a fraction
CSV_12 = (HEAD + "20261012,UCx,FifnlNUQKNk,175,0.0057142857142857143\n").encode()
CSV_13 = (HEAD + "20261013,UCx,FifnlNUQKNk,70,0.057142857142857141\n20261013,UCx,SHORT01,30,0\n"
          "20261013,UCx,LONG002,1,1\n").encode()
VIDEOS = [{"id": "FifnlNUQKNk", "title": "Noah", "views": 900, "published": "2026-10-11T10:00", "short": False,
           "content_type": "LONG_FORM_CONTENT"},
          {"id": "SHORT01", "title": "Eve", "views": 5000, "published": "2026-10-12T10:00", "short": True},
          {"id": "LONG002", "title": "Cain", "views": 40, "published": "2026-10-13T10:00", "short": False}]
DL = "https://youtubereporting.googleapis.com/v1/media/CHANNEL/jobs/J1/reports/{}?alt=media"


def report(rid, day, created):
    return {"id": rid, "startTime": f"{day}T07:00:00Z", "endTime": "x", "createTime": created,
            "downloadUrl": DL.format(rid)}


class FakeHttp:
    def __init__(self, jobs=(), reports=(), files=None, fail=None):
        self.jobs, self.reports, self.files, self.fail = list(jobs), list(reports), files or {}, fail
        self.calls = []

    def json(self, method, path, params=None, body=None):
        self.calls.append((method, path, body))
        if self.fail:
            raise self.fail
        if path == "jobs" and method == "GET":
            return {"jobs": self.jobs}
        if path == "jobs" and method == "POST":
            job = {"id": "NEW", "reportTypeId": body["reportTypeId"], "name": body["name"],
                   "createTime": "2026-10-27T13:00:00Z"}
            self.jobs.append(job)
            return job
        if path.endswith("/reports"):
            return {"reports": self.reports}
        raise AssertionError(path)

    def download(self, url):
        self.calls.append(("DOWNLOAD", url, None))
        return self.files[url]


def http_error(code, body):
    return urllib.error.HTTPError("https://youtubereporting.googleapis.com/v1/jobs", code, "Forbidden", {},
                                  io.BytesIO(json.dumps(body).encode()))


class Csv(unittest.TestCase):
    def test_columns_by_name_dates_and_fraction_ctr(self):
        self.assertEqual(rr.parse_csv(CSV_12), [("2026-10-12", "FifnlNUQKNk", 175, 0.0057142857142857143)])
        swapped = ("video_id,date,video_thumbnail_impressions_ctr,video_thumbnail_impressions,channel_id\n"
                   "V,20261013,0.5,10,UC\n").encode()
        self.assertEqual(rr.parse_csv(swapped), [("2026-10-13", "V", 10, 0.5)])
        self.assertEqual(rr.parse_csv(HEAD.encode()), [])          # a day with no impressions

    def test_refuses_missing_columns_and_a_percent_scale(self):
        with self.assertRaisesRegex(ValueError, "REPORT_COLUMNS_MISSING video_thumbnail_impressions_ctr"):
            rr.parse_csv(b"date,channel_id,video_id,video_thumbnail_impressions\n20261012,UC,V,3\n")
        with self.assertRaisesRegex(ValueError, "CTR_NOT_A_FRACTION"):
            rr.parse_csv((HEAD + "20261012,UC,V,100,4.5\n").encode())


class Aggregate(unittest.TestCase):
    def test_per_video_per_day_and_split_with_derived_clicks(self):
        days = {"2026-10-12": {"FifnlNUQKNk": [175, 0.0057142857142857143]},
                "2026-10-13": {"FifnlNUQKNk": [70, 0.057142857142857141], "SHORT01": [30, 0.0], "LONG002": [1, 1.0],
                               "PRIVATE9": [4, 0.25]}}
        pv, pd, split = rr.aggregate(days, VIDEOS)
        noah = pv["FifnlNUQKNk"]
        self.assertEqual((noah["impressions"], noah["clicks"], noah["ctr"]), (245, 5, round(5 / 245, 4)))
        self.assertEqual((noah["kind"], noah["views"], noah["first_day"], noah["last_day"]),
                         ("long", 900, "2026-10-12", "2026-10-13"))
        self.assertEqual((pv["SHORT01"]["kind"], pv["SHORT01"]["ctr"]), ("short", 0.0))
        self.assertEqual(pv["PRIVATE9"]["kind"], "unclassified")      # not in the report's public videos
        self.assertEqual(pd["2026-10-13"]["impressions"], 105)
        self.assertEqual(pd["2026-10-13"]["clicks"], 6)
        self.assertEqual(pd["2026-10-13"]["by_kind"]["long"], {"impressions": 71, "clicks": 5, "ctr": round(5 / 71, 4)})
        self.assertEqual(split["long"]["videos"], 2)
        self.assertEqual(split["short"], {"videos": 1, "impressions": 30, "clicks": 0, "ctr": 0.0})

    def test_no_impressions_gives_no_ctr(self):
        pv, pd, _ = rr.aggregate({"2026-10-13": {"V": [0, 0.0]}}, [])
        self.assertIsNone(pv["V"]["ctr"])
        self.assertIsNone(pd["2026-10-13"]["ctr"])


class Job(unittest.TestCase):
    def test_existing_job_is_reused_never_duplicated(self):
        h = FakeHttp(jobs=[{"id": "OTHER", "reportTypeId": "channel_basic_a2", "createTime": "2026-10-01T00:00:00Z"},
                           {"id": "J2", "reportTypeId": rr.REPORT_TYPE, "createTime": "2026-10-14T00:00:00Z"},
                           {"id": "J1", "reportTypeId": rr.REPORT_TYPE, "createTime": "2026-10-13T00:00:00Z"}])
        job, created = rr.ensure_job(h)
        self.assertEqual((job["id"], created), ("J1", False))
        self.assertNotIn("POST", [c[0] for c in h.calls])

    def test_missing_job_is_created_once_then_reused(self):
        h = FakeHttp(jobs=[{"id": "OTHER", "reportTypeId": "channel_basic_a2"}])
        job, created = rr.ensure_job(h)
        self.assertEqual((job["id"], created), ("NEW", True))
        self.assertEqual([c for c in h.calls if c[0] == "POST"],
                         [("POST", "jobs", {"reportTypeId": "channel_reach_basic_a1", "name": rr.JOB_NAME})])
        job, created = rr.ensure_job(h)       # the next run
        self.assertEqual((job["id"], created), ("NEW", False))
        self.assertEqual(len([c for c in h.calls if c[0] == "POST"]), 1)


class Run(unittest.TestCase):
    def test_pending_right_after_the_job_is_created(self):
        h = FakeHttp()
        s = rr.run(lambda: h, {}, VIDEOS, NOW)
        self.assertEqual((s["status"], s["job"]["id"], s["job"]["created_this_run"]), ("PENDING", "NEW", True))
        md = "\n".join(rr.section(s, NOW))
        self.assertIn("**PENDING**: reach job created on 2026-10-27; first data ~48 h later (from 2026-10-29)", md)

    def test_ok_ingests_only_new_or_regenerated_reports(self):
        job = {"id": "J1", "reportTypeId": rr.REPORT_TYPE, "createTime": "2026-10-13T00:00:00Z"}
        files = {DL.format("r12"): CSV_12, DL.format("r13"): CSV_13}
        h = FakeHttp(jobs=[job], reports=[report("r12", "2026-10-12", "2026-10-14T05:30:29Z"),
                                          report("r13", "2026-10-13", "2026-10-15T10:25:30Z")], files=files)
        s = rr.run(lambda: h, {}, VIDEOS, NOW)
        self.assertEqual((s["status"], s["downloaded"]), ("OK", 2))
        self.assertEqual(s["per_video"]["FifnlNUQKNk"]["clicks"], 5)
        # next run: nothing new, nothing downloaded
        h.calls.clear()
        s = rr.run(lambda: h, s, VIDEOS, NOW)
        self.assertEqual((s["status"], s["downloaded"]), ("OK", 0))
        self.assertNotIn("DOWNLOAD", [c[0] for c in h.calls])
        # YouTube regenerates 10-13 later: that day is replaced, not added to
        h.reports.append(report("r13b", "2026-10-13", "2026-10-20T00:00:00Z"))
        h.files[DL.format("r13b")] = (HEAD + "20261013,UCx,FifnlNUQKNk,80,0.05\n").encode()
        s = rr.run(lambda: h, s, VIDEOS, NOW)
        self.assertEqual(s["downloaded"], 1)
        self.assertEqual(s["days"]["2026-10-13"], {"FifnlNUQKNk": [80, 0.05]})
        self.assertEqual(s["per_video"]["FifnlNUQKNk"]["impressions"], 255)
        md = "\n".join(rr.section(s, NOW))
        self.assertIn(rr.HEADING, md)
        self.assertIn("| Noah (FifnlNUQKNk) | long | 255 | 1.96 % | 5 | 900 | 2026-10-11 | 2026-10-12 .. 2026-10-13 |", md)
        self.assertIn("clicks (derived)", md)
        s["per_video"]["FifnlNUQKNk"]["title"] = "Noah | the ark"
        self.assertIn("| Noah / the ark (FifnlNUQKNk) | long |", "\n".join(rr.section(s, NOW)))

    def test_a_bad_report_or_foreign_download_host_is_skipped_not_fatal(self):
        job = {"id": "J1", "reportTypeId": rr.REPORT_TYPE}
        bad = report("evil", "2026-10-14", "2026-10-16T00:00:00Z")
        bad["downloadUrl"] = "https://example.com/steal"
        h = FakeHttp(jobs=[job], reports=[report("r12", "2026-10-12", "2026-10-14T00:00:00Z"), bad],
                     files={DL.format("r12"): CSV_12})
        h.download = lambda url, real=rr.Http("TOKEN", opener=self._never): (
            real.download(url) if "example.com" in url else CSV_12)
        s = rr.run(lambda: h, {}, VIDEOS, NOW)
        self.assertEqual((s["status"], s["downloaded"]), ("OK", 1))
        self.assertIn("DOWNLOAD_HOST_REFUSED", " ".join(s["problems"]))
        self.assertNotIn("2026-10-14", s["reports"])            # retried next run

    @staticmethod
    def _never(*a, **k):
        raise AssertionError("the token must never be sent to a foreign host")

    def test_scope_missing_and_api_disabled_are_unknown_with_reason(self):
        scope = http_error(403, {"error": {"code": 403, "status": "PERMISSION_DENIED", "details": [
            {"reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}]}})
        s = rr.run(lambda: FakeHttp(fail=scope), {}, VIDEOS, NOW)
        self.assertEqual(s["status"], "UNKNOWN")
        self.assertTrue(s["reason"].startswith("SCOPE_MISSING (HTTP 403)"))
        off = http_error(403, {"error": {"errors": [{"reason": "accessNotConfigured"}], "status": "PERMISSION_DENIED"}})
        s = rr.run(lambda: FakeHttp(fail=off), {}, VIDEOS, NOW)
        self.assertTrue(s["reason"].startswith("API_DISABLED (HTTP 403): enable the YouTube Reporting API"))
        self.assertIn("| UNKNOWN | API_DISABLED", "\n".join(rr.section(s, NOW)))

    def test_unknown_keeps_the_last_numbers_and_never_raises(self):
        prior = {"days": {"2026-10-12": {"FifnlNUQKNk": [175, 0.0057142857142857143]}}, "reports": {}}

        def no_credential():
            raise PermissionError("CREDENTIAL_MISSING")
        s = rr.run(no_credential, prior, VIDEOS, NOW)
        self.assertEqual(s["status"], "UNKNOWN")
        self.assertIn("CREDENTIAL_MISSING", s["reason"])
        md = "\n".join(rr.section(s, NOW))
        self.assertIn("Last known numbers below", md)
        self.assertIn("| Noah (FifnlNUQKNk) | long | 175 |", md)

    def test_reason_never_carries_the_error_text_or_the_token(self):
        body = {"error": {"message": "bearer FAKE-SECRET-TEXT invalid", "status": "UNAUTHENTICATED"}}
        r = rr.reason(http_error(401, body))
        self.assertNotIn("SECRET", r)
        self.assertTrue(r.startswith("HTTP 401"))


class Redirect(urllib.request.BaseHandler):
    """A fake HTTPS layer: the Reporting API answers 302 to another host; records what each host received."""
    handler_order = 100

    def __init__(self):
        self.seen = []

    def https_open(self, req):
        auth = req.get_header("Authorization") or req.unredirected_hdrs.get("Authorization")
        self.seen.append((req.host, auth))
        if req.host == "youtubereporting.googleapis.com":
            hdrs = email.message.Message()
            hdrs["Location"] = "https://evil.example/steal"
            return self.answer(b"", hdrs, req.full_url, 302, "Found")
        return self.answer(b"{}", email.message.Message(), req.full_url, 200, "OK")

    @staticmethod
    def answer(body, hdrs, url, code, msg):
        r = urllib.response.addinfourl(io.BytesIO(body), hdrs, url, code)
        r.msg = msg
        return r


class TokenNeverFollowsARedirect(unittest.TestCase):
    """Review of #463: urllib copies request headers to a redirected host; the token must never reach it."""
    def test_a_redirect_is_refused_and_the_other_host_gets_nothing(self):
        fake = Redirect()
        h = rr.Http("TOKEN", opener=rr.make_opener(urllib.request.ProxyHandler({}), fake))
        with self.assertRaises(urllib.error.HTTPError) as e:
            h.json("GET", "jobs")
        self.assertEqual((e.exception.code, e.exception.reason), (302, "REDIRECT_REFUSED"))
        self.assertEqual(fake.seen, [("youtubereporting.googleapis.com", "Bearer TOKEN")])
        self.assertTrue(rr.reason(e.exception).startswith("HTTP 302"))

    def test_even_an_opener_that_follows_redirects_never_forwards_the_token(self):
        fake = Redirect()
        h = rr.Http("TOKEN", opener=urllib.request.build_opener(urllib.request.ProxyHandler({}), fake).open)
        h.json("GET", "jobs")
        self.assertEqual(fake.seen, [("youtubereporting.googleapis.com", "Bearer TOKEN"), ("evil.example", None)])

    def test_a_redirected_download_is_a_problem_and_the_run_goes_on(self):
        job = {"id": "J1", "reportTypeId": rr.REPORT_TYPE}
        h = FakeHttp(jobs=[job], reports=[report("r12", "2026-10-12", "2026-10-14T00:00:00Z")])
        fake = Redirect()
        h.download = rr.Http("TOKEN", opener=rr.make_opener(urllib.request.ProxyHandler({}), fake)).download
        s = rr.run(lambda: h, {}, VIDEOS, NOW)
        self.assertEqual((s["status"], s["downloaded"]), ("PENDING", 0))
        self.assertIn("REDIRECT_REFUSED", " ".join(s["problems"]))
        self.assertNotIn("evil.example", [x[0] for x in fake.seen])


class TimeCap(unittest.TestCase):
    def test_downloads_stop_after_the_time_cap_and_resume_next_run(self):
        job = {"id": "J1", "reportTypeId": rr.REPORT_TYPE}
        h = FakeHttp(jobs=[job], reports=[report("r12", "2026-10-12", "2026-10-14T00:00:00Z"),
                                          report("r13", "2026-10-13", "2026-10-15T00:00:00Z")],
                     files={DL.format("r12"): CSV_12, DL.format("r13"): CSV_13})
        ticks = iter([0, 10, 200, 200])
        state = {}
        got, problems = rr.ingest(h, job, state, clock=lambda: next(ticks))
        self.assertEqual(got, 1)
        self.assertEqual(problems, ["1 reports left for the next run (time cap 120 s)"])
        got, problems = rr.ingest(h, job, state)            # next run picks up the rest
        self.assertEqual((got, problems), (1, []))
        self.assertEqual(sorted(state["days"]), ["2026-10-12", "2026-10-13"])


class Classification(unittest.TestCase):
    """Review of #463: the goal report's `videos` keeps the 20 newest, so older public videos with impressions were
    'unclassified'; Analytics' content type sits under analytics.per_video."""
    def test_every_public_video_is_classified_from_the_full_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = {f"V{i:02d}": {"title": f"t{i}", "published": f"2026-10-{i + 1:02d}T10:00", "views": i,
                                   "short": i % 2 == 0, "content_type": None} for i in range(22)}
            newest = [dict(index[k], id=k) for k in sorted(index, reverse=True)[:20]]
            (Path(tmp) / "20261027.json").write_text(json.dumps({"videos": newest, "video_index": index}))
            videos = rr.latest_videos(tmp)
            days = {"2026-10-26": {k: [10, 0.1] for k in index}}
            pv, _, split = rr.aggregate(days, videos)
            self.assertNotIn("unclassified", split)
            self.assertEqual((pv["V00"]["kind"], pv["V01"]["kind"], pv["V00"]["title"]), ("short", "long", "t0"))

    def test_analytics_content_type_and_the_ledger_fill_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = {"videos": [{"id": "A", "title": "a", "short": False, "views": 3}],
                   "analytics": {"per_video": {"A": {"content_type": "SHORTS"},
                                               "OLD": {"content_type": "LONG_FORM_CONTENT", "views": 9}}}}
            (Path(tmp) / "20261027.json").write_text(json.dumps(rep))
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps({"entries": {"pilot-002:abc": {"video_id": "L"},
                                                      "short:pilot-002:def": {"video_id": "S"}}}))
            kinds = {v["id"]: rr.kind_of(v) for v in rr.latest_videos(tmp, ledger)}
            self.assertEqual(kinds, {"A": "short", "OLD": "long", "L": "long", "S": "short"})


class Cli(unittest.TestCase):
    """Review of #463: whatever happens, the step exits 0 and latest.md says UNKNOWN with the reason."""
    def test_a_reach_json_that_is_not_an_object_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "reach.json").write_text("[1, 2]")
            (Path(tmp) / "latest.md").write_text("# r\n")
            s = rr.main(tmp, now=NOW, http_factory=lambda: FakeHttp(fail=PermissionError("CREDENTIAL_MISSING")))
            self.assertEqual(s["status"], "UNKNOWN")
            self.assertIsInstance(json.loads((Path(tmp) / "reach.json").read_text()), dict)

    def test_a_crash_writes_unknown_and_exits_zero(self):
        def boom(*a):
            raise KeyError("x")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "latest.md").write_text("# r\n")
            (Path(tmp) / "reach.json").write_text("not json")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rr.cli([tmp], main=boom), 0)
            md = (Path(tmp) / "latest.md").read_text()
            self.assertIn("| UNKNOWN | CRASH KeyError", md)
            self.assertEqual(json.loads((Path(tmp) / "reach.json").read_text())["status"], "UNKNOWN")
            good = {"days": {"2026-10-12": {"V": [1, 1.0]}}}
            (Path(tmp) / "reach.json").write_text(json.dumps(good))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rr.cli([tmp], main=boom), 0)
            self.assertEqual(json.loads((Path(tmp) / "reach.json").read_text()), good)   # history kept

    def test_the_workflow_fallback_after_a_timeout_writes_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "latest.md").write_text("# r\n")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(rr.cli(["--step-failed", "124", tmp]), 0)
            self.assertIn("| UNKNOWN | STEP_FAILED exit 124 (timed out)", (Path(tmp) / "latest.md").read_text())
            self.assertEqual(json.loads((Path(tmp) / "reach.json").read_text())["status"], "UNKNOWN")


class HttpLayer(unittest.TestCase):
    def test_requests_are_built_for_the_reporting_api_with_a_size_cap(self):
        seen = []

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout):
            seen.append((req.get_method(), req.full_url, req.unredirected_hdrs.get("Authorization"), req.data))
            return Resp(b'{"id": "NEW"}')
        h = rr.Http("TOKEN", opener=opener)
        h.json("POST", "jobs", body={"reportTypeId": rr.REPORT_TYPE, "name": rr.JOB_NAME})
        h.json("GET", "jobs/J1/reports", {"pageToken": "p2"})
        self.assertEqual(seen[0][:3], ("POST", "https://youtubereporting.googleapis.com/v1/jobs", "Bearer TOKEN"))
        self.assertEqual(json.loads(seen[0][3]), {"reportTypeId": "channel_reach_basic_a1", "name": rr.JOB_NAME})
        self.assertEqual(seen[1][1], "https://youtubereporting.googleapis.com/v1/jobs/J1/reports?pageToken=p2")
        self.assertEqual(h.download(DL.format("r1")), b'{"id": "NEW"}')
        big = rr.Http("TOKEN", opener=lambda req, timeout: Resp(b"x" * (rr.MAX_REPORT_BYTES + 1)))
        with self.assertRaisesRegex(ValueError, "RESPONSE_CAP"):
            big.download(DL.format("r1"))


class Main(unittest.TestCase):
    def test_appends_section_writes_compact_json_and_reads_the_goal_report_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "latest.md").write_text("# HeroVerse daily report\n")
            (out / "20261026.json").write_text(json.dumps({"videos": []}))
            (out / "20261027.json").write_text(json.dumps({"videos": VIDEOS}))
            job = {"id": "J1", "reportTypeId": rr.REPORT_TYPE}
            h = FakeHttp(jobs=[job], reports=[report("r13", "2026-10-13", "2026-10-15T00:00:00Z")],
                         files={DL.format("r13"): CSV_13})
            rr.main(tmp, now=NOW, http_factory=lambda: h)
            md = (out / "latest.md").read_text()
            self.assertTrue(md.startswith("# HeroVerse daily report\n"))
            self.assertIn("| Eve (SHORT01) | short | 30 | 0.00 % | 0 | 5000 |", md)
            s = json.loads((out / "reach.json").read_text())
            self.assertEqual((s["status"], s["split"]["short"]["impressions"]), ("OK", 30))
            self.assertNotIn("downloadUrl", json.dumps(s))     # no raw CSV, no URL kept


class Workflow(unittest.TestCase):
    def test_wired_after_the_goal_report_with_the_secret_only_in_env(self):
        wf = (Path(__file__).resolve().parents[2] / ".github/workflows/goal-report.yml").read_text()
        step = wf.split("- name: Impressions and CTR")[1].split("- name:")[0]
        self.assertLess(wf.index("goal_report.py"), wf.index("reach_report.py"))
        self.assertIn("HERO_YT_AUTHORIZED_USER_JSON: ${{ secrets.HERO_YT_AUTHORIZED_USER_JSON }}", step)
        run = step.split("run:")[1]
        self.assertNotIn("secrets.", run)
        self.assertNotIn("echo", run)
        self.assertIn("migration/mining/reach_report.py migration/evidence/daily-report migration/publish/ledger.json", run)
        # review of #463: a hung or crashed step never stops the report, its later steps or the Record step; without
        # continue-on-error, which test_learning_loop forbids in this workflow
        self.assertIn("timeout-minutes: 3", step)
        self.assertIn('timeout 150 "$RUNNER_TEMP/venv/bin/python" -I -B migration/mining/reach_report.py', run)
        self.assertIn('[ "$rc" = 0 ] || python3 -I -B migration/mining/reach_report.py --step-failed "$rc" '
                      "migration/evidence/daily-report", run)
        self.assertNotIn("continue-on-error", wf)


if __name__ == "__main__":
    unittest.main()
