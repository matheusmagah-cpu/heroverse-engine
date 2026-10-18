#!/usr/bin/env python3
"""Offline checks of the final pre-publication decision: good, bad and missing-evidence cases."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepublish_gate as g  # noqa: E402

PROD = Path(__file__).resolve().parent.parent / "production"
CRITERIA = (PROD / "pilot-002" / "qa_criteria.json").read_bytes()
SHA = "f" * 64
CHECKS = sorted({c for spec in g.DIMENSIONS.values() for c in spec["qa"]})
RUBRIC = sorted({c for spec in g.DIMENSIONS.values() for c in spec["review"]})


def good():
    qa = {"output_sha256": SHA, "status": "PASS", "criteria_version": "pilot-qa-criteria-v2",
          "criteria_sha256": hashlib.sha256(CRITERIA).hexdigest(), "checks": {c: True for c in CHECKS}}
    review = {"output_sha256": SHA, "status": "PASS", "watched_review": {**{c: 9 for c in RUBRIC}, "overall": 9, "model": "gemini-3.8-flash"},
              "scorecard_hard": {n: {"pass": True, "value": 1} for n in g.SCORE_HARD},
              "scorecard_reported": {"beats_per_minute": {"value": 1.0, "inside": False}}}
    return qa, {"output_sha256": SHA}, review


SCAN = {"status": "PASS", "rows": {"black_picture": {"longest_s": 0, "pass": True, "blocking": True},
                                   "digital_silence": {"longest_s": 0, "pass": True, "blocking": True},
                                   "frozen_picture": {"longest_s": 9, "inside": False, "blocking": False}}}


def run(qa, manifest, review, preflight=(), video_bytes=None, criteria=CRITERIA, scan=SCAN):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "pilot-009"
        (d / "out").mkdir(parents=True)
        (d / "qa_criteria.json").write_bytes(criteria)
        for name, obj in (("qa", qa), ("manifest", manifest), ("review", review), ("scan", scan)):
            if obj is not None:
                (d / "out" / f"{name}.json").write_text(json.dumps(obj))
        video = None
        if video_bytes is not None:
            video = d / "v.mp4"
            video.write_bytes(video_bytes)
        return g.evaluate(d, video, None if preflight is None else list(preflight))


class Gate(unittest.TestCase):
    def test_good_case_passes_and_informative_rows_do_not_decide(self):
        r = run(*good())
        self.assertEqual(r["decision"], "PASS")
        self.assertTrue(r["eligible_for_automatic_publication"])
        self.assertIn("beats_per_minute", r["informative_not_deciding"])  # outside its band, still PASS
        self.assertIn("scan_frozen_picture", r["informative_not_deciding"])  # reported until calibrated

    def test_bad_cases_fail(self):
        qa, man, rev = good()
        bad_qa = copy.deepcopy(qa); bad_qa["checks"]["true_peak"] = False
        self.assertEqual(run(bad_qa, man, rev)["dimensions"]["audio"], "FAIL")
        bad_rev = copy.deepcopy(rev); bad_rev["watched_review"]["figure_and_background_integrity"] = 5
        r = run(qa, man, bad_rev)
        self.assertEqual((r["decision"], r["dimensions"]["image"]), ("FAIL", "FAIL"))
        low = copy.deepcopy(rev); low["watched_review"]["overall"] = 7.5
        self.assertEqual(run(qa, man, low)["decision"], "FAIL")
        hard = copy.deepcopy(rev); hard["scorecard_hard"]["minutes"]["pass"] = False
        self.assertEqual(run(qa, man, hard)["decision"], "FAIL")
        miner = copy.deepcopy(rev); miner["scorecard_hard"]["coverage"] = {"pass": False, "value": 0.69}  # proven miner row
        self.assertEqual(run(qa, man, miner)["decision"], "FAIL")
        self.assertEqual(run(qa, man, rev, preflight=["THUMBNAIL_SIZE"])["decision"], "FAIL")
        gap = copy.deepcopy(SCAN); gap["status"] = "FAIL"; gap["rows"]["black_picture"].update(longest_s=1.0, **{"pass": False})
        self.assertEqual(run(qa, man, rev, scan=gap)["dimensions"]["full_file_scan"], "FAIL")   # 1 s black gap
        # a render whose QA criteria were edited after the freeze never passes
        self.assertEqual(run(qa, man, rev, criteria=CRITERIA + b" ")["dimensions"]["binding"], "FAIL")
        # the file given is not the approved one
        self.assertEqual(run(qa, man, rev, video_bytes=b"other")["dimensions"]["binding"], "FAIL")

    def test_missing_or_errored_evidence_is_unknown_never_pass(self):
        qa, man, rev = good()
        self.assertEqual(run(qa, man, None)["decision"], "UNKNOWN")                      # no watched review
        self.assertEqual(run(None, man, rev)["decision"], "UNKNOWN")                     # no QA
        err = {"output_sha256": SHA, "status": "ERROR", "error": "HTTPError 429 quota"}
        self.assertEqual(run(qa, man, err)["decision"], "UNKNOWN")                       # quota / provider error
        timeout = {"output_sha256": SHA, "status": "ERROR", "error": "TimeoutError"}
        self.assertFalse(run(qa, man, timeout)["eligible_for_automatic_publication"])
        other = copy.deepcopy(rev); other["output_sha256"] = "0" * 64
        self.assertEqual(run(qa, man, other)["decision"], "UNKNOWN")                     # review of another file
        gap = copy.deepcopy(qa); del gap["checks"]["wer_vs_script"]
        self.assertEqual(run(gap, man, rev)["dimensions"]["transcript"], "UNKNOWN")     # check absent
        miss = copy.deepcopy(rev); del miss["watched_review"]["policy_safe"]
        self.assertEqual(run(qa, man, miss)["decision"], "UNKNOWN")                      # score absent
        self.assertEqual(run(qa, man, rev, preflight=None)["decision"], "UNKNOWN")       # preflight could not run
        fallback = copy.deepcopy(rev); fallback["watched_review"].update({"model": "gemini-3.6-flash", "policy_safe": 6})
        self.assertEqual(run(qa, man, fallback)["decision"], "UNKNOWN")                  # uncalibrated reviewer: no verdict
        lite = copy.deepcopy(rev); lite["watched_review"]["model"] = "gemini-3.5-flash-lite"
        self.assertFalse(run(qa, man, lite)["eligible_for_automatic_publication"])     # not even when it says 9
        self.assertEqual(run(qa, {}, rev)["decision"], "UNKNOWN")                        # no manifest hash
        self.assertEqual(run(qa, man, rev, scan=None)["decision"], "UNKNOWN")            # whole-file scan missing
        self.assertEqual(run(qa, man, rev, scan={"status": "ERROR", "error": "x"})["decision"], "UNKNOWN")

    def test_market_evidence_never_decides(self):
        r = run(*good())
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(r["market_evidence_not_deciding"]["status"], "UNKNOWN")   # no opinion: shown, not blocking

    def test_fail_outranks_unknown(self):
        qa, man, _ = good()
        qa["checks"]["no_third_party_footage"] = False
        self.assertEqual(run(qa, man, None)["decision"], "FAIL")

    def test_matching_video_file_passes(self):
        data = b"video bytes"
        qa, man, rev = good()
        sha = hashlib.sha256(data).hexdigest()
        for o in (qa, man, rev):
            o["output_sha256"] = sha
        self.assertEqual(run(qa, man, rev, video_bytes=data)["decision"], "PASS")


if __name__ == "__main__":
    unittest.main()
