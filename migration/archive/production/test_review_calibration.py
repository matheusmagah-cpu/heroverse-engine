#!/usr/bin/env python3
"""Offline checks of the backup reviewer qualification (known-answer cases, two renders, same verdicts)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_calibration as rc  # noqa: E402

REF = "gemini-3.8-flash"


def run(model, render, flip=None, error=None):
    cases = {}
    for name, (_, expected, items) in rc.CASES.items():
        status = expected
        if name == flip:
            status = "PASS" if expected == "FAIL" else "FAIL"
        review = {"status": "ERROR"} if name == error else {"status": status}
        for item in items:  # the expected items drop on a caught defect
            review[item] = 3 if status == "FAIL" else 9
        cases[name] = {"expected": expected, "verdict": status, "review": review}
    return {"model": model, "render": render, "cases": cases}


class Qualification(unittest.TestCase):
    def full(self, model, **kw):
        return [run(REF, "pilot-005.mp4"), run(REF, "pilot-006.mp4"),
                run(model, "pilot-005.mp4", **kw), run(model, "pilot-006.mp4")]

    def test_identical_on_two_renders_is_qualified(self):
        self.assertEqual(rc.qualification(self.full("m"), REF)["m"]["verdict"], "QUALIFIED")

    def test_one_missed_defect_is_not_qualified(self):
        defect = next(n for n, c in rc.CASES.items() if c[1] == "FAIL")
        r = rc.qualification(self.full("m", flip=defect), REF)["m"]
        self.assertEqual(r["verdict"], "NOT_QUALIFIED")
        self.assertTrue(any("FALSE_APPROVAL" in x for x in r["reasons"]))

    def test_one_false_rejection_is_not_qualified(self):
        r = rc.qualification(self.full("m", flip="control"), REF)["m"]
        self.assertTrue(any("FALSE_REJECTION" in x for x in r["reasons"]))

    def test_differs_from_reference_is_not_qualified(self):
        runs = self.full("m")
        runs[0]["cases"]["control_repeat"]["review"]["status"] = "FAIL"  # the reference itself disagrees
        r = rc.qualification(runs, REF)["m"]
        self.assertTrue(any("DIFFERS_FROM_REFERENCE" in x for x in r["reasons"]))

    def test_error_or_missing_is_never_qualification(self):
        r = rc.qualification(self.full("m", error="control"), REF)["m"]
        self.assertEqual(r["verdict"], "NOT_QUALIFIED")
        runs = self.full("m")
        del runs[2]["cases"]["control"]
        self.assertTrue(any("MISSING_CASE" in x for x in rc.qualification(runs, REF)["m"]["reasons"]))

    def test_one_render_or_no_reference_is_not_qualified(self):
        r = rc.qualification([run(REF, "pilot-005.mp4"), run("m", "pilot-005.mp4")], REF)["m"]
        self.assertTrue(any("FEW_RENDERS" in x for x in r["reasons"]))
        r = rc.qualification([run("m", "pilot-005.mp4"), run("m", "pilot-006.mp4")], REF)["m"]
        self.assertTrue(any("NO_REFERENCE_RUN" in x for x in r["reasons"]))

    def test_failing_for_the_wrong_reason_is_not_qualified(self):
        # Dot's counterexample (#159): status FAIL on a defect, but the expected items kept high
        runs = self.full("m")
        defect, (_, _, items) = next((n, c) for n, c in rc.CASES.items() if c[1] == "FAIL" and c[2])
        for item in items:
            runs[2]["cases"][defect]["review"][item] = 10
        r = rc.qualification(runs, REF)["m"]
        self.assertTrue(any("EXPECTED_ITEM_NOT_DROPPED" in x for x in r["reasons"]))

    def test_too_slow_or_invalid_timing_is_not_qualified(self):
        runs = self.full("m")
        runs[2]["timing"] = {"seconds_per_180s_case": 2000}   # 2000 * 1680 / 180 = 18,667 s > 5 h
        runs[3]["timing"] = {"seconds_per_180s_case": 1900}   # 17,733 s < 5 h
        r = rc.qualification(runs, REF)["m"]
        self.assertTrue(any("TOO_SLOW" in x for x in r["reasons"]))
        self.assertEqual(sum("TOO_SLOW" in x for x in r["reasons"]), 1)
        runs[2]["timing"] = {"seconds_per_180s_case": None}
        self.assertTrue(any("TIMING_INVALID" in x for x in rc.qualification(runs, REF)["m"]["reasons"]))

    def test_reference_is_never_graded_as_a_backup(self):
        self.assertNotIn(REF, rc.qualification(self.full("m"), REF))


if __name__ == "__main__":
    unittest.main()
