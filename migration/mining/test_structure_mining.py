import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import structure_mining as sm  # noqa: E402


def window(start, end, cuts):
    edges = [start, *cuts, end]
    return {"video_id": "abcdefghijk", "window_start_seconds": start, "window_end_seconds": end,
            "audio_received": True, "visual_received": True,
            "beats": [{"start_seconds": a, "end_seconds": b, "beat": "hook" if a == 0 else "teaching",
                       "opening_words_verbatim": "x", "content": "x", "device": "none", "emotion": "calm"}
                      for a, b in zip(edges, edges[1:])],
            "picture": {"shots_counted": 30}, "sound": {}, "scripture_references": ["John 3:16"]}


class StructureMining(unittest.TestCase):
    def test_contiguous_window_is_valid(self):
        self.assertTrue(sm.valid_window(window(0, 300, [20, 140]), "abcdefghijk", 0, 300))

    def test_gap_or_foreign_video_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 60
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 300, [20]), "zzzzzzzzzzz", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 250, [20]), "abcdefghijk", 0, 300))

    def test_measured_fields_are_computed_not_asked(self):
        video = {"seconds": 600, "title": "Why Did God Bury Moses Himself?", "description": "0:00 Intro\n2:15 Moses",
                 "likes": 50, "views": 1000, "comments": 5}
        m = sm.measured(video, [window(0, 300, [20, 140]), window(300, 600, [450])])
        self.assertEqual(m["chapters"], 2)
        self.assertEqual(m["beats"], 5)
        self.assertEqual(m["coverage_fraction"], 1.0)
        self.assertEqual(m["shots_per_minute_model_counted"], 6.0)
        self.assertEqual(m["first_spoken_beat"], {"at": 0, "beat": "hook"})

    def test_looping_transcript_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["transcript"] = [{"start_seconds": i, "text": "By divine authority."} for i in range(12)]
        self.assertTrue(sm.degenerate(w))
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))

    def test_small_gaps_are_repaired_large_are_not(self):
        w = window(0, 300, [20, 140])
        w["beats"][0]["start_seconds"], w["beats"][1]["start_seconds"] = 5, 30
        self.assertTrue(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 80
        self.assertFalse(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))


if __name__ == "__main__":
    unittest.main()
