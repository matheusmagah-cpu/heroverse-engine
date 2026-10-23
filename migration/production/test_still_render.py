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
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": list("abcdefghijklmn")}
        sents = [{"start": 2.5, "end": 80.0, "text": "x"}, {"start": 81.0, "end": 85.0, "text": "y"}]
        plan = sr.holds(script, {"sentences": sents}, 120.0)
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
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": list("abcdefghijklmn")}
        sents = [{"start": 2.5, "end": 80.0, "text": "x"}, {"start": 81.0, "end": 85.0, "text": "y"},
                 {"start": 110.0, "end": 140.0, "text": "z"}, {"start": 160.0, "end": 190.0, "text": "w"}]
        for total in (120.0, 150.0, 200.0, 260.0):
            plan = sr.holds(script, {"sentences": sents}, total)
            self.assertTrue(all(a["image"] != b["image"] for a, b in zip(plan[1:], plan[2:])), total)


class RepeatGap(unittest.TestCase):
    """E46: split holds made 11 backgrounds come back after ~260 s (pilot-009, pilot-011 QA FAIL 2026-10-20/21)."""

    @staticmethod
    def plan(n):
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": [f"bg-{i}" for i in range(n)]}
        sents = [{"start": 2.5 + 40.0 * k, "end": 2.5 + 40.0 * k + 30.0, "text": "x"} for k in range(40)]
        return sr.holds(script, {"sentences": sents}, 1610.0)

    def test_split_holds_with_eleven_backgrounds_refused_before_render(self):
        with self.assertRaises(SystemExit) as e:
            self.plan(11)
        self.assertIn("REPEAT_GAP_VIOLATION", str(e.exception))

    def test_eighteen_backgrounds_keep_the_gap(self):
        plan, seen = self.plan(18), {}
        for h in plan[1:]:
            if h["image"] in seen:
                self.assertGreaterEqual(h["start"] - seen[h["image"]], sr.REPEAT_GAP - 1e-6, h)
            seen[h["image"]] = h["end"]


class SpeechText(unittest.TestCase):
    """E47: the voice spelled "G-O-D" for the KJV "Lord GOD" (pilot-008 review, 17:36)."""

    def test_divine_names_in_capitals_are_spoken_as_words(self):
        from pilot_render import speech_text
        self.assertEqual(speech_text("For thus saith the Lord GOD; Behold, I, even I."),
                         "For thus saith the Lord God; Behold, I, even I.")
        self.assertEqual(speech_text("The LORD is my shepherd."), "The Lord is my shepherd.")
        self.assertEqual(speech_text("GODLY men and LORDS"), "GODLY men and LORDS")  # whole words only

    def test_captions_keep_the_kjv_text(self):
        line = "For thus saith the Lord GOD"
        self.assertIn("GOD", " ".join(sr.chunks(line)))


class Reference(unittest.TestCase):
    def test_reference_leaves_before_the_closing_words_pilot_003(self):
        timeline = json.loads((HERE / "pilot-003/out/timeline.json").read_text())
        seg = next(s for s in timeline["segments"] if s["id"] == "blessing")
        end = sr.reference_end(seg, timeline["sentences"])
        amen = next(s for s in timeline["sentences"] if s["segment"] == "blessing" and "amen" in s["text"])
        self.assertLessEqual(end, amen["start"])
        peace = next(s for s in timeline["sentences"] if s["segment"] == "blessing" and "give thee peace" in s["text"])
        self.assertAlmostEqual(end, peace["end"], places=3)        # end of "...and give thee peace.", from the timeline

    def test_whole_segment_when_no_kjv_sentence(self):
        seg = {"id": "s", "start": 1.0, "end": 9.0}
        self.assertEqual(sr.reference_end(seg, [{"segment": "s", "text": "Be still and know.", "end": 4.0}]), 9.0)


class StandardV1(unittest.TestCase):
    """migration/STANDARD.md R1-R6 on the real narration timelines of the rendered pilots."""
    PILOTS = ("pilot-003", "pilot-004", "pilot-005", "pilot-006")

    def plan(self, pilot):
        script = json.loads((HERE / pilot / "script.json").read_text())
        timeline = json.loads((HERE / pilot / "out/timeline.json").read_text())
        total = timeline["voice_seconds"] + sr.TAIL
        return script, timeline, total, sr.holds(script, timeline, total)

    def test_scenes_no_figure_lengths_and_repeat_gap(self):
        for pilot in self.PILOTS:
            script, timeline, total, plan = self.plan(pilot)
            self.assertFalse(any(h["figure"] for h in plan), pilot)                       # R1
            self.assertLessEqual(plan[0]["end"] - plan[0]["start"], 3.0, pilot)           # title card
            for h in plan[1:]:                                                            # R3
                self.assertGreaterEqual(h["end"] - h["start"], sr.HOLD_MIN - 1e-6, (pilot, h))
                self.assertLessEqual(h["end"] - h["start"], sr.HOLD_MAX + 1e-6, (pilot, h))
            seen = {}
            for h in plan[1:]:
                if h["image"] in seen:
                    self.assertGreaterEqual(h["start"] - seen[h["image"]], sr.REPEAT_GAP - 1e-6, (pilot, h))
                seen[h["image"]] = h["end"]

    def test_too_few_backgrounds_refused(self):
        with self.assertRaises(SystemExit):
            sr.scene_target(["a"] * 6)

    def test_captions_cards_and_cta(self):
        for pilot in self.PILOTS:
            script, timeline, total, _ = self.plan(pilot)
            script.setdefault("overlay", {}).setdefault("subtitle", "")
            ass = sr.build_ass(script, timeline, total)
            self.assertNotIn(",Box,", ass)                                                # R4: no box
            self.assertNotIn(",Amen,", ass)                                               # R6
            self.assertNotIn(script["overlay"].get("amen", "Type AMEN"), ass)
            ctas = sr.cta_events(total)
            self.assertLessEqual(len(ctas), 2)
            self.assertTrue(all(c["end"] - c["start"] <= 10 and c["start"] >= 45 for c in ctas), pilot)
            self.assertEqual(ass.count(",Badge,"), len(ctas))
            for c in sr.scripture_cards(script, timeline):                                # R5
                seg = next(s for s in timeline["segments"] if s["id"] == c["segment"])
                self.assertLessEqual(c["end"], sr.reference_end(seg, timeline["sentences"]) + 1e-6)
                self.assertGreaterEqual(c["start"], seg["start"] - 1e-6)
            self.assertTrue(all(len(e["text"].split()) <= sr.CAPTION_WORDS_MAX for e in sr.caption_events(timeline["sentences"])))


if __name__ == "__main__":
    unittest.main()
