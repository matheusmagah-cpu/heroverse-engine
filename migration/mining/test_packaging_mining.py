#!/usr/bin/env python3
"""Offline checks of the packaging measurements (no network)."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packaging_mining as pm  # noqa: E402

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def video(i, views, dur="PT15M", title="Morning Prayer | Start Your Day With God 🙏", desc="Psalm 91:1 #prayer #faith\nSubscribe and type Amen\n0:00 Intro\n2:10 Prayer"):
    return {"id": f"v{i}", "snippet": {"title": title, "description": desc, "publishedAt": "2026-10-10T09:30:00Z",
                                       "tags": ["morning prayer", "prayer"], "categoryId": "29"},
            "statistics": {"viewCount": str(views), "likeCount": "50", "commentCount": "10"},
            "contentDetails": {"duration": dur}, "status": {"madeForKids": False}}


class Measure(unittest.TestCase):
    def test_row(self):
        r = pm.video_row(video(1, 8000), NOW)
        self.assertEqual(r["seconds"], 900)
        self.assertEqual(r["hour_utc"], 9)
        self.assertTrue(r["title_emoji"] and r["title_separator"])
        self.assertEqual(sorted(r["hashtags"]), ["faith", "prayer"])
        self.assertEqual(r["chapters"], 2)
        self.assertEqual(r["scripture_refs"], 1)
        self.assertIn("subscribe", r["ctas"])
        self.assertIn("amen", r["ctas"])
        self.assertEqual(r["tag_count"], 2)
        self.assertAlmostEqual(r["views_per_day"], 8000 / 7.604, delta=0.2)

    def test_summary_splits_long_and_short(self):
        rows = [pm.video_row(video(i, 1000 * (i + 1)), NOW) for i in range(6)]
        rows += [pm.video_row(video(9, 500, dur="PT45S"), NOW)]
        s = pm.summary(rows)
        self.assertEqual(s["long"]["top_third"]["n"], 2)
        self.assertEqual(s["short"]["top_third"]["n"], 1)
        self.assertTrue(s["long"]["top_tags"])

    def test_english(self):
        self.assertTrue(pm.english(["Morning Prayer for Today"]))
        self.assertFalse(pm.english(["上帝之手 祷告"]))


if __name__ == "__main__":
    unittest.main()
