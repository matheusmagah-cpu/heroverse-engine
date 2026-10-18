#!/usr/bin/env python3
"""Offline checks of the long-video scorecard: own rows always block; miner rows block only once proven."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_review as lr  # noqa: E402

HERE = Path(__file__).resolve().parent
MEASURED = {"speech": {"words_per_minute": 113.9, "you_per_100_words": 4.1}, "first_spoken_beat": {"at": 0},
            "beats_per_minute": 2.1, "shots_per_minute_model_counted": 7, "coverage_fraction": 0.691}


class Scorecard(unittest.TestCase):
    def test_pilot_003_own_rows(self):
        script = json.loads((HERE / "pilot-003/script.json").read_text())
        timeline = json.loads((HERE / "pilot-003/out/timeline.json").read_text())
        own = lr.own_measures(script, timeline, 868.26)
        self.assertEqual(own["minutes"], 14.47)
        self.assertGreaterEqual(own["scripture_per_10_min"], 4)       # 14 references read in 14.5 min

    def test_miner_rows_reported_until_proven(self):
        own = {"minutes": 14.47, "scripture_per_10_min": 9.7}
        hard, reported = lr.scorecard(MEASURED, own, proven=False)
        self.assertEqual(set(hard), {"minutes", "scripture_per_10_min"})
        self.assertTrue(all(v["pass"] for v in hard.values()))
        self.assertIn("note", reported["words_per_minute"])
        hard, _ = lr.scorecard(MEASURED, own, proven=True)          # once proven, the miner's 113.9 blocks
        self.assertFalse(hard["words_per_minute"]["pass"])
        self.assertFalse(hard["coverage"]["pass"])

    def test_own_rows_still_fail(self):
        hard, _ = lr.scorecard(MEASURED, {"minutes": 9.0, "scripture_per_10_min": 2.0})
        self.assertFalse(hard["minutes"]["pass"] or hard["scripture_per_10_min"]["pass"])

    def test_proven_only_on_holdout_pass(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertFalse(lr.miner_proven(root))
            d = root / "evidence/structure-mining/20261020"
            d.mkdir(parents=True)
            (d / "accuracy.json").write_text(json.dumps({"tuning": {"verdict": "PASS"}, "holdout": {"verdict": "UNKNOWN"}}))
            self.assertFalse(lr.miner_proven(root))
            (d / "accuracy.json").write_text(json.dumps({"holdout": {"verdict": "PASS"}}))
            self.assertTrue(lr.miner_proven(root))


    def test_reviewer_model_matches_the_gate(self):
        sys.path.insert(0, str(HERE.parent / "publish"))
        import prepublish_gate
        self.assertEqual(lr.REVIEW_MODELS, prepublish_gate.REVIEW_MODELS)
        self.assertEqual(lr.sr.REVIEW_MODELS, prepublish_gate.REVIEW_MODELS)    # Shorts review: same reviewer


if __name__ == "__main__":
    unittest.main()
