#!/usr/bin/env python3
"""Offline checks of the Dot card lint."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_check as c  # noqa: E402

GOOD = """```allowed
migration/production/pilot-009/*.json
```
- `schedule.json`: `publish_at` `2026-10-22T10:00:00Z`; `shorts_slots` `["2026-10-22T20:00:00Z"]` (exactly one entry).
- qa SHA-256 `49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d`
**DEADLINE (UTC)** — 2026-10-19 09:00
"""


class Card(unittest.TestCase):
    def test_good_card(self):
        self.assertEqual(c.check(GOOD), [])

    def test_deadline_after_the_runway_fails(self):
        bad = GOOD.replace("2026-10-19 09:00", "2026-10-20 18:00")
        self.assertTrue(c.check(bad)[0].startswith("DEADLINE_AFTER_RUNWAY"))

    def test_wrong_short_slot_and_missing_parts(self):
        bad = GOOD.replace('["2026-10-22T20:00:00Z"]', '["2026-10-23T14:00:00Z","2026-10-23T20:00:00Z"]')
        bad = bad.replace("```allowed", "```").replace("49fedd2e", "00000000")
        p = c.check(bad)
        self.assertTrue(any(x.startswith("SHORT_SLOT") for x in p))
        self.assertIn("NO_ALLOWED_BLOCK", p)
        self.assertIn("FROZEN_QA_SHA_MISSING", p)

    def test_code_card_interfaces_must_exist_verbatim(self):
        root = str(Path(__file__).resolve().parents[2])
        ok = "```interfaces\nmigration/production/long_review.py: def watch(file, title, key, models=REVIEW_MODELS):\n```"
        self.assertEqual(c.check(ok, root), [])
        bad = ok.replace("models=REVIEW_MODELS):", "models=REVIEW_MODELS, extra):")
        self.assertTrue(c.check(bad, root)[0].startswith("INTERFACE_NOT_IN_FILE"))
        self.assertTrue(c.check("```interfaces\nno/such.py: x\n```", root)[0].startswith("INTERFACE_FILE_MISSING"))

    def test_not_a_script_card(self):
        self.assertEqual(c.check("a code task"), [])


if __name__ == "__main__":
    unittest.main()
