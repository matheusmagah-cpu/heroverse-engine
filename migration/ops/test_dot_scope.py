#!/usr/bin/env python3
"""Offline checks of the Dot scope check."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dot_scope as s  # noqa: E402

BODY = "x\n```allowed\nmigration/production/pilot-008/*.json\nmigration/production/pilot-008/images/*.json\n```\n"


class Scope(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(s.check(BODY, ["migration/production/pilot-008/script.json",
                                        "migration/production/pilot-008/images/figure-a.json"]), [])

    def test_outside_and_no_crossing_folders(self):
        self.assertEqual(s.check(BODY, ["migration/production/script_check.py",
                                        "migration/production/pilot-008/out/qa.json"]),
                         ["OUT_OF_SCOPE migration/production/script_check.py",
                          "OUT_OF_SCOPE migration/production/pilot-008/out/qa.json"])

    def test_missing_block_fails(self):
        self.assertTrue(s.check("no block", ["a"])[0].startswith("NO_ALLOWED_BLOCK"))

    def test_branch(self):
        self.assertEqual((s.issue_of("dot/114-pilot-008"), s.issue_of("fix/x")), (114, None))


if __name__ == "__main__":
    unittest.main()
