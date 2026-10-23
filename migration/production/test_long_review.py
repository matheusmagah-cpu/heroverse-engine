#!/usr/bin/env python3
"""Offline checks of the long-video review: own rows and the watched review decide; the production audit only reports."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_review as lr  # noqa: E402

HERE = Path(__file__).resolve().parent
FILE = {"uri": "https://files/abc", "name": "files/abc"}
# sha256 of review_prompt("X") before issue #178: the reviewer's prompt must not move
REVIEW_PROMPT_X_SHA256 = "4223b620c248c6e717f93413292f8aa65fcacdb81e971c2891c304a7f5eae30c"


def pilot(root, seconds=868.26):
    d = Path(root) / "pilot-x"
    (d / "out").mkdir(parents=True)
    segs = [{"id": f"s{i}", "reference": f"Psalm {i}:1" if i % 2 else None} for i in range(30)]
    (d / "script.json").write_text(json.dumps({"pilot_id": "pilot-x", "working_title": "T", "segments": segs}))
    (d / "out" / "manifest.json").write_text(json.dumps({"output_seconds": seconds, "output_sha256": "abc"}))
    (d / "out" / "timeline.json").write_text(json.dumps({"segments": [{"id": s["id"]} for s in segs]}))
    return d


class Review(unittest.TestCase):
    def test_pilot_003_own_rows(self):
        script = json.loads((HERE / "pilot-003/script.json").read_text())
        timeline = json.loads((HERE / "pilot-003/out/timeline.json").read_text())
        own = lr.own_measures(script, timeline, 868.26)
        self.assertEqual(own["minutes"], 14.47)
        self.assertGreaterEqual(own["scripture_per_10_min"], 4)       # 14 references read in 14.5 min

    def test_reviewer_model_matches_the_gate(self):
        sys.path.insert(0, str(HERE.parent / "publish"))
        import prepublish_gate
        self.assertEqual(lr.REVIEW_MODELS, prepublish_gate.REVIEW_MODELS)
        self.assertEqual(lr.sr.REVIEW_MODELS, prepublish_gate.REVIEW_MODELS)    # Shorts review: same reviewer

    def test_review_prompt_unchanged(self):
        self.assertEqual(hashlib.sha256(lr.review_prompt("X").encode()).hexdigest(), REVIEW_PROMPT_X_SHA256)

    def test_audit_uses_support_models_never_the_reviewer(self):
        seen = []

        def call(payload, key, models):
            seen.append((payload, models))
            return models[0], {"first_30s": "a", "amateur_elements": []}
        with mock.patch.object(lr.sm, "call", call):
            r = lr.audit(FILE, "k")
        payload, models = seen[0]
        self.assertEqual(models, list(lr.sm.SUPPORT_MODELS))
        self.assertFalse(set(models) & set(lr.REVIEW_MODELS))
        self.assertEqual(r["model"], lr.sm.SUPPORT_MODELS[0])
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["fileData"], {"fileUri": FILE["uri"], "mimeType": "video/mp4"})
        self.assertEqual(parts[0]["videoMetadata"], {"fps": lr.WATCH_FPS})
        self.assertEqual(parts[1]["text"], lr.AUDIT_PROMPT)
        self.assertEqual(payload["generationConfig"]["mediaResolution"], "MEDIA_RESOLUTION_LOW")

    def run_main(self, d, audit_raises, scores=9):
        calls = []

        def call(payload, key, models):
            calls.append(models)
            if models == list(lr.REVIEW_MODELS):
                return models[0], {**{k: scores for k in lr.RUBRIC}, "overall": scores, "issues": []}
            if audit_raises:
                raise RuntimeError("quota exhausted")
            return models[0], {"first_30s": "a", "amateur_elements": []}
        with mock.patch.object(lr.sm, "call", call), mock.patch.object(lr.sr, "upload", lambda p, k: FILE), \
                mock.patch.object(lr, "reviewer_healthy", lambda key: True), \
                mock.patch.object(lr.sr, "request", lambda *a, **k: None), \
                mock.patch.dict(lr.os.environ, {"HERO_GEMINI_API_KEY": "k"}), mock.patch("builtins.print"):
            lr.main(str(d), "video.mp4")
        return json.loads((d / "out" / "review.json").read_text()), calls

    def test_raising_audit_never_changes_the_status(self):
        with tempfile.TemporaryDirectory() as t:
            out, calls = self.run_main(pilot(t), audit_raises=True)
        self.assertEqual(calls[0], list(lr.REVIEW_MODELS))               # audit runs after watch()
        self.assertEqual(calls[1], list(lr.sm.SUPPORT_MODELS))
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["watched_review"]["status"], "PASS")
        self.assertEqual(out["audit"], {"status": "ERROR", "error": "RuntimeError: quota exhausted"})
        self.assertEqual(out["scorecard_reported"], {})
        for k in ("version", "pilot_id", "output_sha256", "usage"):
            self.assertIn(k, out)

    def test_status_still_from_watch_and_hard_rows(self):
        with tempfile.TemporaryDirectory() as t:
            out, _ = self.run_main(pilot(t), audit_raises=False, scores=6)
        self.assertEqual(out["status"], "FAIL")                          # watched review FAIL decides
        self.assertEqual(out["audit"]["model"], lr.sm.SUPPORT_MODELS[0])
        with tempfile.TemporaryDirectory() as t:
            out, _ = self.run_main(pilot(t, seconds=540), audit_raises=False)
        self.assertEqual(out["status"], "FAIL")                          # 9 minutes: hard row FAIL decides
        self.assertFalse(out["scorecard_hard"]["minutes"]["pass"])

    def test_down_reviewer_costs_one_tiny_call_and_no_video_call(self):
        # E58: the designated reviewer did not answer even a 5-token text call; video retries only burned the allowance
        class Ok:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        self.assertTrue(lr.reviewer_healthy("k", opener=lambda req, timeout: Ok()))
        def down(req, timeout):
            raise TimeoutError()
        self.assertFalse(lr.reviewer_healthy("k", opener=down))
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t)
            with mock.patch.dict(lr.os.environ, {"HERO_GEMINI_API_KEY": "k"}), \
                 mock.patch.object(lr, "reviewer_healthy", return_value=False), \
                 mock.patch.object(lr.sr, "upload") as upload, mock.patch.object(lr, "watch") as watch:
                lr.main(str(d), "video.mp4")
            out = json.loads((d / "out" / "review.json").read_text())
        upload.assert_not_called()
        watch.assert_not_called()
        self.assertEqual(out["status"], "ERROR")
        self.assertIn("REVIEWER_UNAVAILABLE", out["error"])
        self.assertFalse(hasattr(lr, "watch_with_patience"))   # no in-run retries of a down reviewer

    def test_scorecard_hard_has_exactly_the_hard_keys(self):
        with tempfile.TemporaryDirectory() as t:
            out, _ = self.run_main(pilot(t), audit_raises=False)
        self.assertEqual(set(out["scorecard_hard"]), set(lr.HARD))
        row = out["scorecard_hard"]["minutes"]
        self.assertEqual(row, {"value": 14.47, "band": list(lr.HARD["minutes"]), "pass": True})


if __name__ == "__main__":
    unittest.main()
