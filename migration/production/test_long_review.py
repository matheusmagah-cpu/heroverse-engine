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

    def test_overloaded_reviewer_is_asked_again_and_only_the_reviewer(self):
        # E58: pilot-010's review gave up after one minute of 503 "high demand" (run 40017605277)
        busy = lr.sm.ProviderFailure("HTTP_503_UNAVAILABLE")
        waits, calls = [], []

        def fake(file, title, key):
            calls.append(title)
            if len(calls) < 3:
                raise busy
            return {"status": "PASS"}
        with mock.patch.object(lr, "watch", side_effect=fake):
            self.assertEqual(lr.watch_with_patience(FILE, "T", "k", wait=waits.append), {"status": "PASS"})
        self.assertEqual(waits, list(lr.OVERLOAD_WAITS[:2]))
        with mock.patch.object(lr, "watch", side_effect=busy):
            with self.assertRaises(lr.sm.ProviderFailure):
                lr.watch_with_patience(FILE, "T", "k", wait=lambda s: None)
        quota = lr.sm.ProviderFailure("HTTP_429_RESOURCE_EXHAUSTED:QUOTA")
        waits = []
        with mock.patch.object(lr, "watch", side_effect=quota):        # a used-up allowance is never retried
            with self.assertRaises(lr.sm.ProviderFailure):
                lr.watch_with_patience(FILE, "T", "k", wait=waits.append)
        self.assertEqual(waits, [])
        self.assertLessEqual(sum(lr.OVERLOAD_WAITS) / 60, 60)          # fits the 120-minute approve job

    def test_scorecard_hard_has_exactly_the_hard_keys(self):
        with tempfile.TemporaryDirectory() as t:
            out, _ = self.run_main(pilot(t), audit_raises=False)
        self.assertEqual(set(out["scorecard_hard"]), set(lr.HARD))
        row = out["scorecard_hard"]["minutes"]
        self.assertEqual(row, {"value": 14.47, "band": list(lr.HARD["minutes"]), "pass": True})


if __name__ == "__main__":
    unittest.main()
