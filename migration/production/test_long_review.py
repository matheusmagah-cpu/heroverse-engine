#!/usr/bin/env python3
"""Offline checks of the long-video review: own rows and an explicitly designated session review decide."""
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
    def test_e208_malformed_review_evidence_never_becomes_a_verdict(self):
        for field, values in {
                "evidence": ("viewed", True, {"file": "x"}, [None], [""], ["   "]),
                "issues": ("none", [None], [True], [{}], [" "]),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertIn("CLAUDE_REVIEW_EVIDENCE", lr.claude_problems(claude(**{field: value}), "abc"))

    def test_story_reads_real_sentence_ids_and_its_existing_story_band_not_prayer_density(self):
        script = {'archetype': 'bible-story-long', 'criteria_version': 'story-qa-criteria-v5',
                  'segments': [{'id': 'n00', 'reference': 'Genesis 1:1 (KJV)'}, {'id': 'n01'}]}
        measured = lr.own_measures(script, {'sentences': [{'segment': 'n00'}, {'segment': 'n01'}]}, 900)
        self.assertEqual(measured['scripture_per_10_min'], 0.67)
        self.assertEqual(lr.hard_bands(script), {'minutes': (14, 18)})
        self.assertEqual(lr.hard_bands({'archetype': 'prayer'}), lr.HARD)

    def test_pilot_003_own_rows(self):
        script = json.loads((HERE / "pilot-003/script.json").read_text())
        timeline = json.loads((HERE / "pilot-003/out/timeline.json").read_text())
        own = lr.own_measures(script, timeline, 868.26)
        self.assertEqual(own["minutes"], 14.47)
        self.assertGreaterEqual(own["scripture_per_10_min"], 4)       # 14 references read in 14.5 min

    def test_reviewer_model_matches_the_gate(self):
        sys.path.insert(0, str(HERE.parent / "publish"))
        import prepublish_gate
        import owner_quality_policy
        self.assertIs(lr.REVIEW_MODELS, owner_quality_policy.LONG_REVIEWERS)
        self.assertIs(prepublish_gate.REVIEW_MODELS, owner_quality_policy.LONG_REVIEWERS)

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
                    claude(model="gpt-6-astra-session-reviewer-other"),
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

    def test_gpt_review_keeps_its_real_identity_and_evidence(self):
        record = claude(model="gpt-6-astra-session-reviewer")
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t)
            self.write(d, record)
            with mock.patch("builtins.print"):
                lr.main(str(d))
            out = json.loads((d / "out" / "review.json").read_text())
            self.assertEqual(json.loads((d / lr.CLAUDE_REVIEW).read_text()), record)
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["watched_review"]["model"], "gpt-6-astra-session-reviewer")
        self.assertEqual(out["watched_review"]["evidence"], record["evidence"])
        self.assertEqual(out["output_sha256"], record["output_sha256"])

    def test_gpt_review_needs_the_same_binding_evidence_and_rubric(self):
        for changes, expected in (({"output_sha256": "other"}, "AWAITING_REVIEW"),
                                  ({"evidence": []}, "AWAITING_REVIEW"),
                                  ({"overall": 11}, "AWAITING_REVIEW"),
                                  ({"picture_quality": 6.5}, "FAIL")):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as t:
                d = pilot(t)
                self.write(d, claude(model="gpt-6-astra-session-reviewer", **changes))
                with mock.patch("builtins.print"):
                    lr.main(str(d))
                self.assertEqual(json.loads((d / "out" / "review.json").read_text())["status"], expected)

    def test_down_reviewer_costs_one_tiny_call_and_no_video_call(self):
        # E58: the old reviewer did not answer even a 5-token call; the review now never calls a provider at all
        src = (HERE / "long_review.py").read_text()
        main_src = src[src.index("def main("):]
        for call in ("sr.upload", "sm.call", "urlopen", "HERO_GEMINI_API_KEY", "watch("):
            self.assertNotIn(call, main_src)


if __name__ == "__main__":
    unittest.main()
