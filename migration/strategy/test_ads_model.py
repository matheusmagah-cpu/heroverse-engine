#!/usr/bin/env python3
"""Offline: the ads model keeps paid results out of the YPP counter and states the real break-even."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ads_model as m  # noqa: E402


class Ads(unittest.TestCase):
    def test_paid_watch_time_never_counts_for_ypp(self):
        o = m.outcome(100, 0, "mid")
        self.assertEqual(o["paid_views"], 2000)
        self.assertEqual(o["organic_watch_hours_counted_for_ypp"], 0)   # only views the ads cause organically count

    def test_ad_revenue_alone_does_not_repay_the_spend(self):
        o = m.outcome(100, 0, "mid")
        self.assertLess(o["return_on_spend"], 0.1)                      # 2,000 views x $3.30/1,000 = $6.60
        self.assertAlmostEqual(m.break_even_k("mid"), 14.2, places=1)   # 14 organic views per paid view to break even

    def test_organic_multiplier_drives_ypp_hours(self):
        self.assertEqual(m.outcome(100, 1, "mid")["organic_watch_hours_counted_for_ypp"], round(2000 * 7 / 60, 1))


if __name__ == "__main__":
    unittest.main()
