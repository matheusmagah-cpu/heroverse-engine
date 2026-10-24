#!/usr/bin/env python3
"""Offline checks of the nightly queue (images, then renders)."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_queue as rq  # noqa: E402

rq.HOLD = Path(tempfile.gettempdir()) / "no-such-hold-file"  # the live repo may be on hold; these tests are not
rq.RENDER_HOLD = Path(tempfile.gettempdir()) / "no-such-render-hold-file"

NOW = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)


def pilot(root, name, publish_at, images_done=True, rendered=False, previewed=True):
    d = Path(root) / name
    (d / "images").mkdir(parents=True)
    script = {"backgrounds": ["bg-a", "bg-b"], "figure": "figure-a", "overlay": {"title_image": "bg-a"}}
    (d / "script.json").write_text(json.dumps(script))
    (d / "schedule.json").write_text(json.dumps({"publish_at": publish_at}))
    (d / "images.json").write_text(json.dumps({"images": [{"id": "bg-b"}]}))
    for i in (("figure-a", "bg-a", "bg-b") if images_done else ("figure-a", "bg-a")):
        (d / "images" / f"{i}.json").write_text("{}")
    if previewed:  # the preview of this script reached the floor (preview_gate.py)
        (d / "inspection").mkdir(exist_ok=True)
        sha0 = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        (d / "inspection" / "preview_review.json").write_text(json.dumps({"script_sha256": sha0, "overall": 9.5}))
    if rendered:
        (d / "out").mkdir()
        sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        (d / "out" / "manifest.json").write_text(json.dumps({"script_sha256": sha, "output_sha256": "a"*64}))
        (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "a"*64, "criteria_version": rq.STANDARD_QA, "criteria_sha256": rq.STANDARD_QA_SHA256}))


class Queue(unittest.TestCase):
    def test_quota_pending_suppresses_same_and_other_shorts(self):
        import contextlib, io
        from unittest.mock import patch
        from datetime import timedelta
        for quota_ids, age in (([], 0), (['RequestsPerDay'], 0)):
            with tempfile.TemporaryDirectory() as t:
                for name in ('pilot-005','pilot-006'):
                    pilot(t,name,'2026-10-19T10:00:00Z',rendered=True)
                    d=Path(t)/name;(d/'shorts').mkdir();(d/'shorts/inputs.json').write_text('{}')
                    (d/'out/review.json').write_text(json.dumps({'status':'FAIL','output_sha256':'a'*64}))
                d=Path(t)/'pilot-005'
                (d/'out/review.json').write_text(json.dumps({'status':'ERROR','error':'QUOTA',
                    'failed_at':NOW.isoformat(),'quota_ids':quota_ids,'output_sha256':'a'*64}))
                class Fixed(rq.datetime):
                    @classmethod
                    def now(cls,tz=None): return NOW
                # Isolate scheduling from qualification, tested by test_shorts_prerequisite.
                with patch.object(rq,'datetime',Fixed), patch.object(rq,'shorts_ready',return_value=True):
                    buf=io.StringIO()
                    with contextlib.redirect_stdout(buf):rq.main(t,str(Path(t)/'none'),'reconcile')
                    self.assertEqual(buf.getvalue(),'')
                    (d/'out/review.json').write_text(json.dumps({'status':'ERROR','error':'QUOTA',
                        'failed_at':(NOW-timedelta(days=1)).isoformat(),'quota_ids':quota_ids,'output_sha256':'a'*64}))
                    buf=io.StringIO()
                    with contextlib.redirect_stdout(buf):rq.main(t,str(Path(t)/'none'),'reconcile')
                    self.assertEqual(buf.getvalue(),'approve pilot-005\n')

    def test_current_render_requires_complete_frozen_v3_binding(self):
        manifest={'output_sha256':'a'*64,'script_sha256':'script'}
        qa={'output_sha256':'a'*64,'criteria_version':rq.STANDARD_QA,'criteria_sha256':rq.STANDARD_QA_SHA256,'status':'PASS'}
        for status in ('PASS','FAIL'):
            self.assertTrue(rq.current_render(manifest,dict(qa,status=status),'script'))
        for key,value in [('criteria_version','pilot-qa-criteria-v2'),('criteria_version','unknown'),
                          ('criteria_sha256','wrong'),('output_sha256','b'*64),('status','UNKNOWN'),('status',None)]:
            self.assertFalse(rq.current_render(manifest,dict(qa,**{key:value}),'script'),(key,value))
        self.assertFalse(rq.current_render(manifest,qa,'changed'))
        for bad in (None,[],{},True):
            self.assertFalse(rq.current_render(manifest,bad,'script'))
            self.assertFalse(rq.current_render(bad,qa,'script'))
    def test_legacy_render_is_requeued_but_uploaded_is_excluded(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t,'pilot-005','2026-10-19T10:00:00Z',rendered=True)
            p=Path(t)/'pilot-005/out/qa.json';qa=json.loads(p.read_text());qa['criteria_version']='pilot-qa-criteria-v2';p.write_text(json.dumps(qa))
            self.assertFalse(rq.due(t,{},NOW,48)[0]['rendered'])
            self.assertEqual(rq.due(t,{'entries':{'pilot-005:'+ 'a'*64:{'video_id':'already'}}},NOW,48),[])
    def test_missing_malformed_nonobject_qa_and_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t,'pilot-005','2026-10-19T10:00:00Z',rendered=True)
            d=Path(t)/'pilot-005/out'
            for name in ('qa.json','manifest.json'):
                p=d/name;original=p.read_bytes()
                for content in ('{bad','[]','null'):
                    p.write_text(content);self.assertFalse(rq.due(t,{},NOW,48)[0]['rendered'])
                p.unlink();self.assertFalse(rq.due(t,{},NOW,48)[0]['rendered']);p.write_bytes(original)
    def test_current_failure_is_not_an_identical_rerender(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t,'pilot-005','2026-10-19T10:00:00Z',rendered=True)
            p=Path(t)/'pilot-005/out/qa.json';q=json.loads(p.read_text());q['status']='FAIL';p.write_text(json.dumps(q))
            self.assertTrue(rq.due(t,{},NOW,48)[0]['rendered'])
    def test_pinned_criteria_hash_matches_frozen_file(self):
        p=Path(__file__).resolve().parent/'qa_criteria_v3.json'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),rq.STANDARD_QA_SHA256)

    def test_no_approval_retry_while_the_gemini_quota_is_spent(self):
        err = {"status": "ERROR", "error": "ProviderFailure: HTTP_429_RESOURCE_EXHAUSTED:QUOTA", "failed_at": "2026-10-19T01:30:00Z",
               "quota_ids": ["GenerateRequestsPerDayPerProjectPerModel-FreeTier"]}
        self.assertTrue(rq.quota_spent(err, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))    # per day: until the 07:00 reset
        self.assertFalse(rq.quota_spent(err, datetime(2026, 10, 19, 7, 5, tzinfo=timezone.utc)))   # after it: retried
        self.assertFalse(rq.quota_spent({**err, "error": "TimeoutError"}, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))
        self.assertFalse(rq.quota_spent({k: v for k, v in err.items() if k != "failed_at"}, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))

    def test_per_minute_or_unnamed_quota_waits_minutes_not_a_day(self):
        # E29: on 2026-10-19 an unnamed 429 held pilot-003 for 5 h while the same quota approved pilot-004
        for ids in ([], ["GenerateContentInputTokensPerModelPerMinute-FreeTier"]):
            err = {"status": "ERROR", "error": "ProviderFailure: HTTP_429_RESOURCE_EXHAUSTED:QUOTA",
                   "failed_at": "2026-10-19T11:30:00Z", "quota_ids": ids}
            self.assertTrue(rq.quota_spent(err, datetime(2026, 10, 19, 11, 50, tzinfo=timezone.utc)))
            self.assertFalse(rq.quota_spent(err, datetime(2026, 10, 19, 12, 1, tzinfo=timezone.utc)))

    def test_images_then_render_by_publish_time(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-003", "2026-10-19T10:00:00Z", images_done=False)
            pilot(t, "pilot-004", "2026-10-19T23:00:00Z")
            pilot(t, "pilot-009", "2026-10-25T10:00:00Z")  # outside the horizon
            rows = rq.due(t, {}, NOW, 48)
            self.assertEqual([r["pilot"] for r in rows], ["pilot-003", "pilot-004"])
            self.assertEqual(rows[0]["missing_images"], ["bg-b"])
            nxt = next(r for r in rows if not r["missing_images"] and not r["rendered"])
            self.assertEqual(nxt["pilot"], "pilot-004")

    def test_passed_slot_without_video_is_reported_stale(self):
        # E49: pilot-008..011 dropped out of due() after their slots passed and nothing reported it
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-008", "2026-10-17T10:00:00Z", rendered=True)   # 15 h ago, not on YouTube
            pilot(t, "pilot-007", "2026-10-17T00:00:00Z", rendered=True)   # 25 h ago, published (older render)
            pilot(t, "pilot-009", "2026-10-17T22:00:00Z")                  # 3 h ago: still due, not stale
            pilot(t, "pilot-002", "2026-10-01T10:00:00Z")                  # older than STALE_DAYS
            pilot(t, "pilot-003", "2026-10-17T09:00:00Z", rendered=True)   # pre-standard render: retired
            qa = Path(t) / "pilot-003" / "out" / "qa.json"
            qa.write_text(json.dumps(dict(json.loads(qa.read_text()), criteria_version="pilot-qa-criteria-v2")))
            ledger = {"entries": {"pilot-007:" + "b" * 64: {"video_id": "v"}}}
            self.assertEqual([r["pilot"] for r in rq.stale(t, ledger, NOW)], ["pilot-008"])
            self.assertEqual([r["pilot"] for r in rq.due(t, ledger, NOW, 48)], ["pilot-009"])

    def test_render_hold_renders_nothing(self):
        import contextlib, io
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-004", "2026-10-19T23:00:00Z")
            hold = Path(t) / "RENDER_HOLD"
            with patch.object(rq, "RENDER_HOLD", hold), patch.object(rq, "datetime") as dt:
                dt.now.return_value = NOW
                dt.fromisoformat = datetime.fromisoformat
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rq.main(t, str(Path(t) / "ledger.json"), "render")
                self.assertEqual(out.getvalue().strip(), "pilot-004")
                hold.write_text("scripts moving to v4\n")
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rq.main(t, str(Path(t) / "ledger.json"), "render")
                self.assertEqual(out.getvalue().strip(), "")

    def test_rendered_or_published_is_not_queued(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-003", "2026-10-19T10:00:00Z", rendered=True)
            self.assertTrue(rq.due(t, {}, NOW, 48)[0]["rendered"])
            self.assertEqual(rq.due(t, {"entries": {"pilot-003:"+"a"*64: {"video_id": "v"}}}, NOW, 48), [])

    def test_review_lists_qa_passed_renders_without_a_claude_review_for_their_hash(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            for name in ("pilot-003", "pilot-004", "pilot-005"):
                pilot(t, name, "2026-10-19T10:00:00Z", rendered=True)
                d = Path(t) / name
                (d / "out" / "qa.json").write_text(json.dumps({"status": "FAIL" if name == "pilot-005" else "PASS", "output_sha256": "a" * 64,
                                                              "criteria_version": rq.STANDARD_QA, "criteria_sha256": rq.STANDARD_QA_SHA256}))
            (Path(t) / "pilot-004" / "inspection").mkdir(exist_ok=True)
            (Path(t) / "pilot-004" / "inspection" / "claude_review.json").write_text(json.dumps({"output_sha256": "a" * 64}))
            buf = io.StringIO()
            real = rq.datetime
            class Fixed(real):
                @classmethod
                def now(cls, tz=None):
                    return NOW
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "review")
            finally:
                rq.datetime = real
            self.assertEqual(buf.getvalue().split(), ["pilot-003", "a" * 64])

    def test_pending_first_comments_are_retried_once_the_video_is_public(self):
        # E61: 006, 007 and 010 kept "PENDING: HTTP_403" first comments for days; nothing dispatched the retry
        with tempfile.TemporaryDirectory() as t:
            for name, at in (("pilot-006", "2026-10-17T08:00:00Z"), ("pilot-007", "2026-10-18T00:55:00Z"),
                             ("pilot-008", "2026-10-17T08:00:00Z"), ("pilot-009", "2026-10-05T08:00:00Z")):
                pilot(t, name, at)
            pending = {"first_comment": "PENDING: HTTP_403 forbidden"}
            ledger = {"entries": {
                "pilot-006:" + "a" * 64: {"video_id": "v6", "steps": pending},          # public: retried
                "pilot-007:" + "a" * 64: {"video_id": "v7", "steps": pending},          # still scheduled: not yet
                "pilot-008:" + "a" * 64: {"video_id": "v8", "steps": {"first_comment": "Ugz1"}},  # posted: never again
                "pilot-009:" + "a" * 64: {"video_id": "v9", "steps": pending},          # older than a week: left
                "short:pilot-006:" + "b" * 64: {"video_id": "s6", "steps": pending}}}   # Shorts have no first comment
            self.assertEqual(rq.pending_comments(t, ledger, NOW), ["pilot-006"])
        wf = (Path(rq.__file__).resolve().parents[2] / ".github/workflows/reconcile.yml").read_text()
        self.assertIn("comment) gh workflow run first-comment.yml", wf)

    def test_pending_episode_comments_are_retried_once_public(self):
        # E70: the Genesis 2 Short was scheduled and its first comment came back PENDING (HTTP 403)
        with tempfile.TemporaryDirectory() as t:
            eps = Path(t, "bible", "episodes")
            eps.mkdir(parents=True)
            (eps / "g1.json").write_text(json.dumps({"id": "g1"}))
            (eps / "g2.json").write_text(json.dumps({"id": "g2", "slot": "2026-10-17T23:30:00Z"}))
            (eps / "g3.json").write_text(json.dumps({"id": "g3", "slot": "2026-10-18T05:00:00Z"}))
            pending = {"first_comment": "PENDING: HTTP_403 forbidden"}
            ledger = {"entries": {
                "bible:g1:" + "a" * 64: {"video_id": "v1", "uploaded_at": "2026-10-17T08:00:00+00:00", "steps": {"first_comment": "Ugw"}},
                "bible:g2:" + "a" * 64: {"video_id": "v2", "steps": pending},
                "bible:g3:" + "a" * 64: {"video_id": "v3", "steps": pending}}}
            self.assertEqual(rq.pending_episode_comments(t, ledger, NOW), ["g2"])
        wf = (Path(rq.__file__).resolve().parents[2] / ".github/workflows/reconcile.yml").read_text()
        self.assertIn("episode) gh workflow run publish-episode.yml", wf)

    def test_reconcile_retries_errors_and_failed_publications(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            for name, review, approved in (("pilot-003", "ERROR", False), ("pilot-004", None, True), ("pilot-005", "FAIL", False),
                                           ("pilot-006", "PASS", False), ("pilot-007", "PASS", False)):
                pilot(t, name, "2026-10-19T10:00:00Z", rendered=True)
                d = Path(t) / name
                (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "a"*64, "criteria_version": rq.STANDARD_QA, "criteria_sha256": rq.STANDARD_QA_SHA256}))
                if review:
                    (d / "out" / "review.json").write_text(json.dumps({"status": review, "output_sha256": "a"*64}))
                if name in ("pilot-006", "pilot-007"):  # final decision UNKNOWN is retried, FAIL is not
                    gate = "UNKNOWN" if name == "pilot-006" else "FAIL"
                    (d / "out" / "gate.json").write_text(json.dumps({"decision": gate, "output_sha256": "a"*64}))
                if name in ("pilot-005", "pilot-006"):  # Shorts never made, or all left unreviewed -> made again
                    (d / "shorts").mkdir()
                    (d / "shorts" / "inputs.json").write_text("{}")
                if name == "pilot-006":
                    (d / "shorts" / "shorts.json").write_text(json.dumps({"shorts": [{"review": {"status": "NOT_REVIEWED_ProviderFailure"}}]}))
                if approved:
                    (d / "inspection").mkdir(exist_ok=True)
                    (d / "inspection" / "APPROVAL.json").write_text(json.dumps({"approved": True, "output_sha256": "a"*64}))
            buf = io.StringIO()
            real = rq.datetime
            class Fixed(real):
                @classmethod
                def now(cls, tz=None):
                    return NOW
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.datetime = real
            # E25: one approval only, the earliest slot; Shorts wait while an approval is pending (same Gemini quota)
            self.assertEqual(buf.getvalue().split("\n")[:-1], ["publish pilot-004", "approve pilot-003"])
            for name in ("pilot-003", "pilot-006"):  # terminal failures: unqualified longs must not produce Shorts
                (Path(t) / name / "out" / "review.json").write_text(json.dumps({"status": "FAIL", "output_sha256": "a"*64}))
            (Path(t) / "pilot-006" / "out" / "gate.json").write_text(json.dumps({"decision": "FAIL", "output_sha256": "a"*64}))
            buf = io.StringIO()
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.datetime = real
            self.assertEqual(buf.getvalue().split("\n")[:-1], ["publish pilot-004"])

    def test_publication_hold_dispatches_nothing(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-005", "2026-10-19T10:00:00Z", rendered=True)
            (Path(t) / "pilot-005" / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "a"*64, "criteria_version": rq.STANDARD_QA, "criteria_sha256": rq.STANDARD_QA_SHA256}))
            hold = Path(t) / "PUBLICATION_HOLD"
            hold.write_text("owner pause")
            real_hold, real = rq.HOLD, rq.datetime
            class Fixed(real):
                @classmethod
                def now(cls, tz=None):
                    return NOW
            rq.HOLD, rq.datetime = hold, Fixed
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.HOLD, rq.datetime = real_hold, real
            self.assertEqual(buf.getvalue(), "")

    def test_only_the_earliest_approval_is_dispatched(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            for name, at in (("pilot-006", "2026-10-19T20:00:00Z"), ("pilot-005", "2026-10-19T10:00:00Z")):
                pilot(t, name, at, rendered=True)
                (Path(t) / name / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "a"*64, "criteria_version": rq.STANDARD_QA, "criteria_sha256": rq.STANDARD_QA_SHA256}))
            buf = io.StringIO()
            real = rq.datetime
            class Fixed(real):
                @classmethod
                def now(cls, tz=None):
                    return NOW
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.datetime = real
            self.assertEqual(buf.getvalue().split("\n")[:-1], ["approve pilot-005"])

    def test_renders_before_the_standard_are_never_approved_or_published(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-005", "2026-10-19T10:00:00Z", rendered=True)
            d = Path(t) / "pilot-005"
            (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "a"*64,
                                                           "criteria_version": "pilot-qa-criteria-v2"}))
            (d / "inspection").mkdir(exist_ok=True)
            (d / "inspection" / "APPROVAL.json").write_text(json.dumps({"approved": True, "output_sha256": "a"*64}))
            buf = io.StringIO()
            real = rq.datetime
            class Fixed(real):
                @classmethod
                def now(cls, tz=None):
                    return NOW
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.datetime = real
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
