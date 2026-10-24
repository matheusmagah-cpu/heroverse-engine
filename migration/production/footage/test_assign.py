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
        out = assign.choose({"working_title": "Night Prayer for Peace"}, lib(["candle", "night", "sunrise"], 10, vetting_luma=[30]))
        self.assertTrue(all(not c.startswith("clip-sunrise") for c in out))
        self.assertEqual(out[:4], ["clip-candle-0", "clip-night-0", "clip-candle-1", "clip-night-1"])

    def test_pilots_of_one_mood_get_different_openings_and_orders(self):
        library = lib(["candle", "night", "ocean", "lake"], 10, vetting_luma=[30])
        a = assign.choose({"working_title": "Night Prayer"}, library, turn=8)
        b = assign.choose({"working_title": "Night Prayer"}, library, turn=10)
        self.assertNotEqual(a[0], b[0])
        self.assertTrue(a[0].startswith(("clip-candle", "clip-night")) and b[0].startswith(("clip-candle", "clip-night")))
        self.assertEqual(sorted(a), sorted(b))   # the same vetted clips, in another order

    def test_only_vetted_licensed_stored_clips(self):
        bad = lib(["sunrise"], 30, vetting="PENDING") + lib(["clouds"], 30, licence="CC BY-SA 4.0")
        with self.assertRaises(SystemExit):
            assign.choose({"working_title": "Morning Prayer"}, bad)

    def test_night_takes_only_dark_clips(self):
        # E69: the 008 night prayer showed sunlit waterfalls and snowy peaks chosen by theme alone
        library = lib(["candle", "night"], 12, vetting_luma=[40, 42]) + lib(["waterfall"], 12, vetting_luma=[120, 125])
        library += [{**lib(["river"], 1)[0], "id": "clip-river-unmeasured"}]
        out = assign.choose({"working_title": "Before You Sleep, Night Prayer"}, library)
        self.assertFalse([c for c in out if c.startswith(("clip-waterfall", "clip-river"))])
        day = assign.choose({"working_title": "Morning Prayer"}, lib(["waterfall", "river"], 12, vetting_luma=[120]))
        self.assertEqual(len(day), 24)                        # morning keeps bright clips

    def test_shortage_refused(self):
        with self.assertRaises(SystemExit) as e:
            assign.choose({"working_title": "Morning Prayer"}, lib(["sunrise"], 5))
        self.assertIn("FOOTAGE_SHORTAGE", str(e.exception))


    def test_night_never_takes_day_themes(self):
        # E71: dark-mean snow, waterfall and mist clips still showed a daytime sky in the 008 night prayer
        library = lib(["candle", "night", "rain", "river"], 6, vetting_luma=[30]) + lib(["snow", "waterfall", "mist", "clouds"], 6, vetting_luma=[40])
        out = assign.choose({"working_title": "Night Prayer"}, library)
        self.assertFalse([c for c in out if c.split("-")[1] in ("snow", "waterfall", "mist", "clouds")])

    def test_seen_clips_first_once_there_are_enough(self):
        # E74: each reassignment of 011 brought unseen clips (and new modern ones) into the next preview
        unseen = lib(["sunrise", "clouds"], 15, vetting_luma=[120])
        seen = [dict(r, id=r["id"].replace("clip-", "clip-seen-"), claude_seen="pilot-011 preview") for r in lib(["sunrise", "clouds"], 12, vetting_luma=[120])]
        out = assign.choose({"working_title": "Morning Prayer"}, unseen + seen)
        self.assertTrue(out and all("seen" in c for c in out))
        few = seen[:4]
        self.assertTrue(any("seen" not in c for c in assign.choose({"working_title": "Morning Prayer"}, unseen + few)))

if __name__ == "__main__":
    unittest.main()
