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
        err = {"status": "ERROR", "error": "ProviderFailure: HTTP_429_RESOURCE_EXHAUSTED:QUOTA", "failed_at": "2026-10-19T01:30:00Z"}
        self.assertTrue(rq.quota_spent(err, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))    # before the 07:00 reset
        self.assertFalse(rq.quota_spent(err, datetime(2026, 10, 19, 7, 5, tzinfo=timezone.utc)))   # after it: retried
        self.assertFalse(rq.quota_spent({**err, "error": "TimeoutError"}, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))
        self.assertFalse(rq.quota_spent({k: v for k, v in err.items() if k != "failed_at"}, datetime(2026, 10, 19, 5, 0, tzinfo=timezone.utc)))

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
                (d / "out" / "qa.json").write_text(json.dumps({"status": "PASS", "output_sha256": "x"}))
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
            self.assertEqual(buf.getvalue().split("\n")[:-1], ["approve pilot-003", "publish pilot-004", "shorts pilot-005", "approve pilot-006", "shorts pilot-006"])


if __name__ == "__main__":
    unittest.main()
