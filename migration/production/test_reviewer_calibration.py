#!/usr/bin/env python3
"""Offline: the reviewer qualification rule is strict and fixed."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reviewer_calibration as rc  # noqa: E402


def row(ds, do, cs, co):
    return {"designated_status": ds, "designated_overall": do, "candidate_status": cs, "candidate_overall": co}


class Qualification(unittest.TestCase):
    def test_rule(self):
        self.assertTrue(rc.qualify([row("PASS", 9.0, "PASS", 9.2), row("FAIL", 8.0, "FAIL", 7.8)])["qualified"])
        self.assertFalse(rc.qualify([row("FAIL", 8.0, "PASS", 8.6)])["qualified"])           # different verdict
        self.assertFalse(rc.qualify([row("PASS", 8.8, "PASS", 9.6)] * 3)["qualified"])        # more lenient
        self.assertFalse(rc.qualify([row("PASS", 9.0, "PASS", 8.0)] * 3)["qualified"])        # too far apart
        self.assertFalse(rc.qualify([{**row("PASS", 9, "PASS", 9), "error": "x"}])["qualified"])
        self.assertFalse(rc.qualify([])["qualified"])


if __name__ == "__main__":
    unittest.main()
