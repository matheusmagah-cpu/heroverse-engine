#!/usr/bin/env python3
"""short_engine.py: shots tile the Short, clips are never looped or slowed past MAX_SLOW, captions stay short."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short_engine as se


class Plan(unittest.TestCase):
    def test_shots_must_tile_the_short(self):
        ok = [{"start": 0.0, "end": 5.0}, {"start": 5.0, "end": 10.0}]
        self.assertEqual(se.check_shots(ok, 10.0), [])
        gap = [{"start": 0.0, "end": 5.0}, {"start": 5.5, "end": 10.0}]
        self.assertTrue(any(p.startswith("SHOT_GAP_OR_OVERLAP") for p in se.check_shots(gap, 10.0)))
        self.assertTrue(any(p.startswith("SHOTS_END") for p in se.check_shots(ok, 12.0)))
        self.assertIn("SHOT_TOO_SHORT 1", se.check_shots([{"start": 0.0, "end": 9.5}, {"start": 9.5, "end": 10.0}], 10.0))

    def test_clip_is_slowed_at_most_max_slow_never_looped(self):
        self.assertEqual(se.speed({"start": 0, "end": 5, "src_start": 0}, 6.58), 1.0)
        self.assertAlmostEqual(se.speed({"start": 0, "end": 9.65, "src_start": 0}, 8.0), 9.65 / 8.0)
        self.assertIsNone(se.speed({"start": 0, "end": 9.0, "src_start": 1.0}, 6.58))

    def test_captions_two_words_inside_the_sentence(self):
        cards = se.chunks({"start": 1.0, "end": 4.0, "text": "And Enoch walked with God:"})
        self.assertEqual([c["text"] for c in cards], ["And Enoch", "walked with", "God:"])
        self.assertAlmostEqual(cards[0]["start"], 1.0)
        self.assertAlmostEqual(cards[-1]["end"], 4.0)
        ass = se.build_ass([{"start": 0.3, "end": 2.0, "text": "a {b} c\\d"}])
        self.assertNotIn("{b}", ass)
        self.assertIn("WrapStyle: 0", ass)


if __name__ == "__main__":
    unittest.main()
