import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import still_render as sr  # noqa: E402
from pilot_render import sentences  # noqa: E402

HERE = Path(__file__).resolve().parent


class Captions(unittest.TestCase):
    def test_no_caption_over_limit_in_pilot_002(self):
        script = json.loads((HERE / "pilot-002/script.json").read_text())
        lines = [c for seg in script["segments"] for x in sentences(seg["text"]) for c in sr.chunks(x)]
        self.assertLessEqual(max(len(c) for c in lines), sr.CAPTION_CHARS_MAX)

    def test_long_sentence_split(self):
        out = sr.chunks("Six words that turn your attention from the size of the problem to the faithfulness of the One who is already in it.")
        self.assertTrue(all(len(c) <= sr.CAPTION_CHARS_MAX for c in out))
        self.assertEqual(" ".join(out), "Six words that turn your attention from the size of the problem to the faithfulness of the One who is already in it.")


class Holds(unittest.TestCase):
    def test_hold_cap_and_no_repeat(self):
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": ["a", "b", "c"]}
        sents = [{"start": 2.5, "end": 40.0, "text": "x"}, {"start": 41.0, "end": 45.0, "text": "y"}]
        plan = sr.holds(script, {"sentences": sents}, 60.0)
        self.assertTrue(all(h["end"] - h["start"] <= sr.HOLD_MAX + 1e-6 for h in plan[1:]))
        self.assertTrue(all(a["image"] != b["image"] for a, b in zip(plan[1:], plan[2:])))

    def test_no_repeat_after_a_split_hold_pilot_004(self):
        # the pilot-004 render (QA FAIL 2026-10-18) had bg-dusk-field twice in a row: a long hold was split and
        # the next hold's image, chosen before the split, was the same as the split's last piece
        script = json.loads((HERE / "pilot-004/script.json").read_text())
        timeline = json.loads((HERE / "pilot-004/out/timeline.json").read_text())
        plan = sr.holds(script, timeline, timeline["voice_seconds"] + sr.TAIL)
        self.assertTrue(all(a["image"] != b["image"] for a, b in zip(plan[1:], plan[2:])))
        self.assertTrue(all(h["end"] - h["start"] <= sr.HOLD_MAX + 1e-6 for h in plan[1:]))

    def test_split_then_next_hold_never_repeats(self):
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": ["a", "b", "c", "d"]}
        sents = [{"start": 2.5, "end": 40.0, "text": "x"}, {"start": 41.0, "end": 45.0, "text": "y"},
                 {"start": 55.0, "end": 70.0, "text": "z"}, {"start": 80.0, "end": 90.0, "text": "w"}]
        for total in (60.0, 75.0, 95.0, 120.0):
            plan = sr.holds(script, {"sentences": sents}, total)
            self.assertTrue(all(a["image"] != b["image"] for a, b in zip(plan[1:], plan[2:])), total)


class Reference(unittest.TestCase):
    def test_reference_leaves_before_the_closing_words_pilot_003(self):
        timeline = json.loads((HERE / "pilot-003/out/timeline.json").read_text())
        seg = next(s for s in timeline["segments"] if s["id"] == "blessing")
        end = sr.reference_end(seg, timeline["sentences"])
        amen = next(s for s in timeline["sentences"] if s["segment"] == "blessing" and "amen" in s["text"])
        self.assertLessEqual(end, amen["start"])
        self.assertAlmostEqual(end, 840.795, places=2)            # end of "...and give thee peace."

    def test_whole_segment_when_no_kjv_sentence(self):
        seg = {"id": "s", "start": 1.0, "end": 9.0}
        self.assertEqual(sr.reference_end(seg, [{"segment": "s", "text": "Be still and know.", "end": 4.0}]), 9.0)


if __name__ == "__main__":
    unittest.main()
