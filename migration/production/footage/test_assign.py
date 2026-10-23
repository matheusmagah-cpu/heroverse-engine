#!/usr/bin/env python3
"""Offline: footage is chosen by mood from vetted, licensed clips only, interleaved by theme."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assign  # noqa: E402


def lib(themes, n, **kw):
    return [{"id": f"clip-{t}-{i}", "theme": t, "vetting": "APPROVED", "licence": "CC0", "release_asset": "a.mp4", "frame": [2560, 1440], **kw}
            for t in themes for i in range(n)]


class Assign(unittest.TestCase):
    def test_night_takes_night_themes_interleaved(self):
        out = assign.choose({"working_title": "Night Prayer for Peace"}, lib(["candle", "night", "sunrise"], 10))
        self.assertTrue(all(not c.startswith("clip-sunrise") for c in out))
        self.assertEqual(out[:4], ["clip-candle-0", "clip-night-0", "clip-candle-1", "clip-night-1"])

    def test_pilots_of_one_mood_get_different_openings_and_orders(self):
        library = lib(["candle", "night", "ocean", "lake"], 10)
        a = assign.choose({"working_title": "Night Prayer"}, library, turn=8)
        b = assign.choose({"working_title": "Night Prayer"}, library, turn=10)
        self.assertNotEqual(a[0], b[0])
        self.assertTrue(a[0].startswith(("clip-candle", "clip-night")) and b[0].startswith(("clip-candle", "clip-night")))
        self.assertEqual(sorted(a), sorted(b))   # the same vetted clips, in another order

    def test_only_vetted_licensed_stored_clips(self):
        bad = lib(["sunrise"], 30, vetting="PENDING") + lib(["clouds"], 30, licence="CC BY-SA 4.0")
        with self.assertRaises(SystemExit):
            assign.choose({"working_title": "Morning Prayer"}, bad)

    def test_shortage_refused(self):
        with self.assertRaises(SystemExit) as e:
            assign.choose({"working_title": "Morning Prayer"}, lib(["sunrise"], 5))
        self.assertIn("FOOTAGE_SHORTAGE", str(e.exception))


if __name__ == "__main__":
    unittest.main()
