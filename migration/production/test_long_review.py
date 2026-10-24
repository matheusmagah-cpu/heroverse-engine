#!/usr/bin/env python3
"""Offline checks of the long-video review: own rows and the designated reviewer's (Claude) review decide."""
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


def claude(sha="abc", **over):
    r = {"version": "claude-review-v1", "model": lr.REVIEW_MODELS[0], "output_sha256": sha,
         **{k: 9.6 for k in lr.RUBRIC}, "overall": 9.6, "issues": ["0:12 one caption a little early"],
         "strongest_moment": "0:00 hook", "evidence": ["inspection/review-sheet.jpg", "out/timeline.json"]}
    r.update(over)
    return r


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
        self.assertEqual(lr.REVIEW_MODELS, ("claude-session-reviewer",))   # owner 2026-10-24: gemini-3.8-flash replaced

    def test_review_prompt_unchanged(self):
        self.assertEqual(hashlib.sha256(lr.review_prompt("X").encode()).hexdigest(), REVIEW_PROMPT_X_SHA256)

    def write(self, d, review):
        (d / "inspection").mkdir(exist_ok=True)
        (d / lr.CLAUDE_REVIEW).write_text(json.dumps(review))

    def test_claude_review_decides_with_the_hard_rows(self):
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t)
            self.write(d, claude())
            with mock.patch("builtins.print"):
                lr.main(str(d))
            out = json.loads((d / "out" / "review.json").read_text())
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["watched_review"]["model"], "claude-session-reviewer")
        self.assertEqual(out["watched_review"]["overall"], 9.6)
        self.assertEqual(set(out["scorecard_hard"]), set(lr.HARD))
        self.assertEqual(out["scorecard_hard"]["minutes"], {"value": 14.47, "band": list(lr.HARD["minutes"]), "pass": True})
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t)
            self.write(d, claude(pacing_and_visual_variety=6.5))           # one item under 7 fails
            with mock.patch("builtins.print"):
                lr.main(str(d))
            self.assertEqual(json.loads((d / "out" / "review.json").read_text())["status"], "FAIL")
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t, seconds=540)                                    # 9 minutes: the hard row fails
            self.write(d, claude())
            with mock.patch("builtins.print"):
                lr.main(str(d))
            self.assertEqual(json.loads((d / "out" / "review.json").read_text())["status"], "FAIL")

    def test_no_valid_review_for_this_file_is_awaiting_never_a_verdict(self):
        for bad in (None, claude(sha="other"), claude(model="gemini-3.8-flash"), claude(overall=11),
                    claude(evidence=[]), claude(opening_and_promise="9")):
            with tempfile.TemporaryDirectory() as t:
                d = pilot(t)
                if bad is not None:
                    self.write(d, bad)
                with mock.patch("builtins.print"):
                    lr.main(str(d))
                out = json.loads((d / "out" / "review.json").read_text())
            self.assertEqual(out["status"], "AWAITING_REVIEW", bad)
            self.assertNotIn("watched_review", out)

    def test_down_reviewer_costs_one_tiny_call_and_no_video_call(self):
        # E58: the old reviewer did not answer even a 5-token call; the review now never calls a provider at all
        src = (HERE / "long_review.py").read_text()
        main_src = src[src.index("def main("):]
        for call in ("sr.upload", "sm.call", "urlopen", "HERO_GEMINI_API_KEY", "watch("):
            self.assertNotIn(call, main_src)


if __name__ == "__main__":
    unittest.main()
