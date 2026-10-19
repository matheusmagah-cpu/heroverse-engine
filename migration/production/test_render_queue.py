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

NOW = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)


def pilot(root, name, publish_at, images_done=True, rendered=False):
    d = Path(root) / name
    (d / "images").mkdir(parents=True)
    script = {"backgrounds": ["bg-a", "bg-b"], "figure": "figure-a", "overlay": {"title_image": "bg-a"}}
    (d / "script.json").write_text(json.dumps(script))
    (d / "schedule.json").write_text(json.dumps({"publish_at": publish_at}))
    (d / "images.json").write_text(json.dumps({"images": [{"id": "bg-b"}]}))
    for i in (("figure-a", "bg-a", "bg-b") if images_done else ("figure-a", "bg-a")):
        (d / "images" / f"{i}.json").write_text("{}")
    if rendered:
        (d / "out").mkdir()
        sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        (d / "out" / "manifest.json").write_text(json.dumps({"script_sha256": sha, "output_sha256": "x"}))


class Queue(unittest.TestCase):
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

    def test_rendered_or_published_is_not_queued(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-003", "2026-10-19T10:00:00Z", rendered=True)
            self.assertTrue(rq.due(t, {}, NOW, 48)[0]["rendered"])
            self.assertEqual(rq.due(t, {"entries": {"pilot-003:x": {"video_id": "v"}}}, NOW, 48), [])

    def test_reconcile_retries_errors_and_failed_publications(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            for name, review, approved in (("pilot-003", "ERROR", False), ("pilot-004", None, True), ("pilot-005", "FAIL", False),
                                           ("pilot-006", "PASS", False), ("pilot-007", "PASS", False)):
                pilot(t, name, "2026-10-19T10:00:00Z", rendered=True)
                d = Path(t) / name
                (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "x", "criteria_version": rq.STANDARD_QA}))
                if review:
                    (d / "out" / "review.json").write_text(json.dumps({"status": review, "output_sha256": "x"}))
                if name in ("pilot-006", "pilot-007"):  # final decision UNKNOWN is retried, FAIL is not
                    gate = "UNKNOWN" if name == "pilot-006" else "FAIL"
                    (d / "out" / "gate.json").write_text(json.dumps({"decision": gate, "output_sha256": "x"}))
                if name in ("pilot-005", "pilot-006"):  # Shorts never made, or all left unreviewed -> made again
                    (d / "shorts").mkdir()
                    (d / "shorts" / "inputs.json").write_text("{}")
                if name == "pilot-006":
                    (d / "shorts" / "shorts.json").write_text(json.dumps({"shorts": [{"review": {"status": "NOT_REVIEWED_ProviderFailure"}}]}))
                if approved:
                    (d / "inspection").mkdir()
                    (d / "inspection" / "APPROVAL.json").write_text(json.dumps({"approved": True, "output_sha256": "x"}))
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
            for name in ("pilot-003", "pilot-006"):  # approvals done: the Shorts go
                (Path(t) / name / "out" / "review.json").write_text(json.dumps({"status": "FAIL", "output_sha256": "x"}))
            (Path(t) / "pilot-006" / "out" / "gate.json").write_text(json.dumps({"decision": "FAIL", "output_sha256": "x"}))
            buf = io.StringIO()
            rq.datetime = Fixed
            try:
                with contextlib.redirect_stdout(buf):
                    rq.main(t, str(Path(t) / "none.json"), "reconcile")
            finally:
                rq.datetime = real
            self.assertEqual(buf.getvalue().split("\n")[:-1], ["publish pilot-004", "shorts pilot-005", "shorts pilot-006"])

    def test_publication_hold_dispatches_nothing(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-005", "2026-10-19T10:00:00Z", rendered=True)
            (Path(t) / "pilot-005" / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "x", "criteria_version": rq.STANDARD_QA}))
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
                (Path(t) / name / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "x", "criteria_version": rq.STANDARD_QA}))
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
            (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "x",
                                                           "criteria_version": "pilot-qa-criteria-v2"}))
            (d / "inspection").mkdir()
            (d / "inspection" / "APPROVAL.json").write_text(json.dumps({"approved": True, "output_sha256": "x"}))
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
