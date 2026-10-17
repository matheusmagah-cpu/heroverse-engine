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


if __name__ == "__main__":
    unittest.main()
