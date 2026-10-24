#!/usr/bin/env python3
"""Offline: the daily directives cover the Bible-story niche, Shorts and longs apart."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import daily_intel as di  # noqa: E402


def uploads(prefix, seconds):
    return [{"video_id": f"{prefix}{i}", "title": f"Noah's Ark Bible Story {i} | KJV #shorts", "duration_seconds": seconds,
             "views": 1000 * (i + 1), "published_at": "2026-10-20T13:00:00Z"} for i in range(8)]


class DailyIntel(unittest.TestCase):
    def test_bible_niche_directives_split_shorts_and_longs(self):
        panel = {"captured_at": "2026-10-24T12:00:00Z", "channels": [
            {"channel_id": "b1", "title": "Bible Tales", "niche": "bible", "subscribers": 5000,
             "uploads": uploads("s", 50) + uploads("l", 600)},
            {"channel_id": "c1", "title": "Prayer", "niche": "christian", "subscribers": 5000, "uploads": uploads("c", 700)}]}
        with tempfile.TemporaryDirectory() as t:
            Path(t, "p.json").write_text(json.dumps(panel))
            di.main(Path(t, "p.json"), Path(t, "o.json"))
            out = json.loads(Path(t, "o.json").read_text())
        self.assertEqual(out["bible"]["shorts"]["videos_considered"], 8)
        self.assertEqual(out["bible"]["longs"]["seconds_top_quartile_median"], 600)
        self.assertEqual(out["bible"]["shorts"]["winners"][0]["video_id"], "s7")   # most views per day first
        self.assertEqual(out["videos_considered"], 8)                              # the Christian longs as before


if __name__ == "__main__":
    unittest.main()
