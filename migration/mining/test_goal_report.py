#!/usr/bin/env python3
"""Offline checks of the YPP counters estimate: only public long-form hours (365 d) and public Shorts views (90 d)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goal_report as gr  # noqa: E402


class Eligible(unittest.TestCase):
    def test_counts_only_what_ypp_counts(self):
        videos = [{"id": "L1", "short": False}, {"id": "S1", "short": True}, {"id": "L2", "short": False}]  # public now
        per365 = {"L1": ("LONG_FORM_CONTENT", 600), "S1": ("SHORTS", 1200), "L2": ("LONG_FORM_CONTENT", 120),
                  "GONE": ("LONG_FORM_CONTENT", 6000)}  # GONE: private or removed, not counted
        per90 = {"S1": ("SHORTS", 900), "L1": ("LONG_FORM_CONTENT", 50), "OLD": ("SHORTS", 10_000)}
        e = gr.eligible(videos, per365, per90)
        self.assertEqual(e["public_long_form_watch_hours_365d"], 12.0)   # (600 + 120) / 60, no Shorts, no GONE
        self.assertEqual(e["public_shorts_views_90d"], 900)              # public Shorts only, 90 days
        self.assertEqual(e["all_content_watch_hours_365d_top200"], 132.0)

    def test_duration_fallback_when_type_unknown(self):
        videos = [{"id": "A", "short": True}, {"id": "B", "short": False}]
        e = gr.eligible(videos, {"A": (None, 60), "B": (None, 120)}, {"A": (None, 5), "B": (None, 7)})
        self.assertEqual((e["public_long_form_watch_hours_365d"], e["public_shorts_views_90d"]), (2.0, 5))


if __name__ == "__main__":
    unittest.main()
