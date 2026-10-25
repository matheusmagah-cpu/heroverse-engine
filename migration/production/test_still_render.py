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


class FootageV4(unittest.TestCase):
    """Owner, 2026-10-23: real licensed footage alternates with the stills in 6-14 s scenes (pilot-qa-criteria-v4)."""
    CRIT = json.loads((HERE / "qa_criteria_v4.json").read_text())

    @staticmethod
    def plan(n_still, n_clip, total=1610.0):
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0},
                  "backgrounds": [f"bg-{i}" for i in range(n_still)], "footage": [f"clip-{i}" for i in range(n_clip)]}
        # sentences every 5 s, like the narration (scenes then measure ~10 s, as on the 008/010/011 timelines)
        sents = [{"start": 2.5 + 5.0 * k, "end": 2.5 + 5.0 * k + 4.0, "text": "x"} for k in range(int(total // 5.0))]
        return sr.holds(script, {"sentences": sents}, total)

    def manifest(self, plan, vetting="APPROVED", licence="CC BY 4.0"):
        clips = [{"id": c, "licence": licence, "vetting": vetting, "credit": "Footage: x", "sha256": "a" * 64}
                 for c in sorted({h["image"].partition("#")[0] for h in plan if h.get("kind") == "footage"})]
        for h in plan:
            h["motion"] = "footage" if h.get("kind") == "footage" else "dolly_in"
        return {"holds": plan, "clips": clips, "captions": [{"start": 3.0, "end": 6.0, "text": "a b", "segment": "s"}],
                "sentences": [{"start": 3.0, "end": 6.0, "segment": "s"}], "cta": [], "caption_style": {"box": False},
                "persistent_overlays": ["brand"], "crossfade_seconds": sr.FADE, "scripture_cards": [],
                "images": {"bg-0": {"models": {"m": {"license": "apache-2.0", "revision": "r"}}}}}

    def test_scenes_are_real_footage_within_bounds_and_gap(self):
        # E66: the 009 review found the AI stills (a third of the picture) visibly painterly between real footage
        plan = self.plan(20, 22)
        self.assertEqual({h.get("kind") for h in plan}, {"footage"})
        few = self.plan(80, 4)                          # too few clips for the repeat gap: stills fill, never a repeat
        self.assertIn("still", {h.get("kind") for h in few})
        last = {}
        for h in few:
            if h["image"] in last:
                self.assertGreaterEqual(h["start"] - last[h["image"]], sr.REPEAT_GAP - 1e-6, h)
            last[h["image"]] = h["end"]
        for h in plan[:-1]:
            self.assertTrue(sr.FOOTAGE_HOLD_MIN - 1e-6 <= h["end"] - h["start"] <= sr.FOOTAGE_HOLD_MAX + 1e-6, h)
        self.assertEqual(self.CRIT["grammar"]["scene_seconds"], [sr.FOOTAGE_HOLD_MIN, sr.FOOTAGE_HOLD_MAX])
        self.assertEqual(plan[0]["start"], 0.0)          # no still title card: the hook opens on footage
        self.assertEqual(plan[0]["kind"], "footage")

    def test_cuts_land_in_4_to_7_s_and_shots_reuse_clip_segments(self):
        plan = self.plan(20, 22)
        self.assertTrue(all(4.0 - 1e-6 <= h["end"] - h["start"] <= 7.0 + 1e-6 for h in plan), plan[:5])
        footage = [h["image"] for h in plan if h.get("kind") == "footage"]
        self.assertIn("#1", "".join(footage))          # each clip yields several distinct shots
        self.assertGreater(sum(h["end"] - h["start"] for h in plan if h.get("kind") == "footage") / plan[-1]["end"], 0.6)

    def test_hook_line_is_large_centred_text_from_frame_zero(self):
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0, "title": "T", "subtitle": "S", "brand": "B"},
                  "footage": ["clip-a"], "segments": []}
        timeline = {"segments": [], "sentences": [
            {"segment": "hook", "start": 0.3, "end": 3.4, "text": "Before you sleep tonight, give God the worry you cannot fix."},
            {"segment": "hook", "start": 3.6, "end": 6.0, "text": "This prayer will help you rest."}]}
        ass = sr.build_ass(script, timeline, 600.0)
        hook = [l for l in ass.splitlines() if ",Hook," in l]
        self.assertEqual(len(hook), 1)
        self.assertTrue(hook[0].startswith("Dialogue: 2,0:00:00.00,0:00:03.40,Hook"))
        self.assertIn("Before you sleep tonight,\\Ngive God the worry you\\Ncannot fix.", hook[0])
        self.assertNotIn(",Title,", ass)
        self.assertNotIn("Before you sleep", "".join(l for l in ass.splitlines() if ",Caption," in l))

    def test_no_cta_badges_over_footage_pilots(self):
        # 3 reviews named the Subscribe/Like badges as breaking the immersion (pilot-004, 007, 012)
        self.assertEqual(sr.cta_events(1600.0, {"footage": ["clip-a"]}), [])
        self.assertEqual(len(sr.cta_events(1600.0, {})), 2)

    def test_too_few_clips_refused_before_render(self):
        with self.assertRaises(SystemExit) as e:
            self.plan(18, 6)
        self.assertIn("REPEAT_GAP_VIOLATION", str(e.exception))

    def test_qa_v4_rights_and_share(self):
        import qa_pilot
        plan = self.plan(20, 22)
        ok = qa_pilot.grammar_checks_v4(self.CRIT, self.manifest(plan))
        self.assertTrue(ok["footage_picture_share"])
        self.assertTrue(ok["footage_licensed_vetted_and_credited"])
        self.assertTrue(ok["scene_seconds"])
        self.assertNotIn("no_third_party_footage", ok)
        self.assertFalse(qa_pilot.grammar_checks_v4(self.CRIT, self.manifest(plan, vetting="PENDING"))[
            "footage_licensed_vetted_and_credited"])
        self.assertFalse(qa_pilot.grammar_checks_v4(self.CRIT, self.manifest(plan, licence="CC BY-SA 4.0"))[
            "footage_licensed_vetted_and_credited"])

    def test_footage_only_render_has_no_image_to_license(self):
        # E68: the fixture always carried a generated image, so QA never met a real footage-only manifest (008 FAIL)
        import qa_pilot
        plan = self.plan(20, 22)
        m = self.manifest(plan)
        m["images"] = {}
        self.assertTrue(qa_pilot.grammar_checks_v4(self.CRIT, m)["images_open_licence_with_revision"])
        mixed = self.manifest(self.plan(80, 4))         # a still on screen: its model must be recorded
        mixed["images"] = {}
        self.assertFalse(qa_pilot.grammar_checks_v4(self.CRIT, mixed)["images_open_licence_with_revision"])


class StoryStills(unittest.TestCase):
    """SERIES.md (owner 2026-10-25): a Bible-story long shows each story moment's still inside its own segment and
    real footage everywhere else, so QA v4's footage share (>= 0.6) still holds."""
    def test_stills_land_in_their_segment_and_footage_keeps_the_rest(self):
        total = 900.0
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0},
                  "backgrounds": ["st-sword", "st-fruit", "st-serpent"], "footage": [f"clip-{i}" for i in range(24)],
                  "segments": [{"id": "hook", "text": "x"}, {"id": "chapter-1", "text": "x", "stills": ["st-sword"]},
                               {"id": "chapter-2", "text": "x", "stills": ["st-serpent", "st-fruit"]}]}
        sents = [{"start": 2.5 + 5.0 * k, "end": 2.5 + 5.0 * k + 4.0, "text": "x"} for k in range(int(total // 5.0))]
        segs = [{"id": "hook", "start": 0.3, "end": 30.0}, {"id": "chapter-1", "start": 30.0, "end": 400.0},
                {"id": "chapter-2", "start": 400.0, "end": total}]
        plan = sr.holds(script, {"sentences": sents, "segments": segs}, total)
        stills = [(h["image"], h["start"]) for h in plan if h.get("kind") == "still"]
        self.assertEqual([i for i, _ in stills], ["st-sword", "st-serpent", "st-fruit"])
        self.assertTrue(30.0 <= stills[0][1] < 400.0 and all(400.0 <= t for _, t in stills[1:]), stills)
        self.assertEqual(plan[0]["kind"], "footage")          # the hook still opens on real footage
        share = sum(h["end"] - h["start"] for h in plan if h.get("kind") == "footage") / total
        self.assertGreater(share, 0.6)

    def test_a_repeated_moment_still_never_breaks_the_gap(self):
        # review of 36ff9b5: the same still in two segments 160 s apart aborted the render (REPEAT_GAP_VIOLATION)
        total = 900.0
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": ["st-a"],
                  "footage": [f"clip-{i}" for i in range(24)],
                  "segments": [{"id": "hook", "text": "x"}, {"id": "chapter-1", "text": "x", "stills": ["st-a"]},
                               {"id": "chapter-2", "text": "x", "stills": ["st-a"]}]}
        sents = [{"start": 2.5 + 5.0 * k, "end": 2.5 + 5.0 * k + 4.0, "text": "x"} for k in range(int(total // 5.0))]
        segs = [{"id": "hook", "start": 0.3, "end": 30.0}, {"id": "chapter-1", "start": 30.0, "end": 190.0},
                {"id": "chapter-2", "start": 190.0, "end": total}]
        plan = sr.holds(script, {"sentences": sents, "segments": segs}, total)   # no SystemExit
        starts = [h["start"] for h in plan if h["image"] == "st-a"]
        self.assertTrue(all(b - a >= sr.REPEAT_GAP - 1e-6 for a, b in zip(starts, starts[1:])), starts)


class StoryShots(unittest.TestCase):
    """Owner, 2026-10-25: "the videos must talk with the story and what is being said". A segment's own clips (mined
    for its words) fill its cuts; the library cycle never puts an unrelated landscape over them."""
    def test_each_segment_shows_the_clips_mined_for_its_words(self):
        total = 120.0
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0}, "backgrounds": ["st-a"],
                  "footage": [f"clip-landscape-{i}" for i in range(8)] + ["clip-serpent", "clip-serpent-b", "clip-river",
                                                                    "clip-river-b", "clip-fruit", "clip-fruit-b"],
                  "segments": [{"id": "hook", "text": "x", "shots": ["clip-serpent", "clip-serpent-b"]},
                               {"id": "river", "text": "x", "shots": ["clip-river", "clip-river-b"]},
                               {"id": "fruit", "text": "x", "shots": ["clip-fruit", "clip-fruit-b"]}]}
        sents = [{"start": 0.3 + 5.0 * k, "end": 0.3 + 5.0 * k + 4.0, "text": "x"} for k in range(int(total // 5.0))]
        segs = [{"id": "hook", "start": 0.3, "end": 18.0}, {"id": "river", "start": 18.0, "end": 36.0},
                {"id": "fruit", "start": 36.0, "end": 54.0}, {"id": "rest", "start": 54.0, "end": total}]
        plan = sr.holds(script, {"sentences": sents, "segments": segs}, total)
        for lo, hi, clip in ((0.0, 18.0, "clip-serpent"), (18.0, 36.0, "clip-river"), (36.0, 54.0, "clip-fruit")):
            inside = [h["image"] for h in plan if lo <= (h["start"] + h["end"]) / 2 < hi]
            self.assertTrue(inside and all(i.startswith(clip) for i in inside), (clip, inside))
        self.assertTrue(all(b - a >= 0 for a, b in zip([h["start"] for h in plan], [h["start"] for h in plan][1:])))

    def test_a_segment_longer_than_its_clips_never_borrows_another_segments_clip(self):
        # review of 0bef573: with every clip owned (script_check refuses filler), an exhausted segment fell back to the
        # whole footage list and showed the hook's serpent over the river's words
        total = 400.0   # past REPEAT_GAP, so the hook's clips are free again while the river is still being told
        script = {"overlay": {"title_image": "t", "title_card_seconds": 2.0},
                  "backgrounds": [f"st-{i}" for i in range(90)], "footage": ["clip-serpent", "clip-river"],
                  "segments": [{"id": "hook", "text": "x", "shots": ["clip-serpent"]},
                               {"id": "river", "text": "x", "shots": ["clip-river"]}]}
        sents = [{"start": 0.3 + 5.0 * k, "end": 0.3 + 5.0 * k + 4.0, "text": "x"} for k in range(int(total // 5.0))]
        segs = [{"id": "hook", "start": 0.3, "end": 18.0}, {"id": "river", "start": 18.0, "end": total}]
        plan = sr.holds(script, {"sentences": sents, "segments": segs}, total)
        river = [h["image"] for h in plan if (h["start"] + h["end"]) / 2 >= 18.0]
        self.assertFalse([i for i in river if i.startswith("clip-serpent")], river)
        self.assertGreaterEqual(sum(i.startswith("clip-river") for i in river), 3)


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

    def test_card_for_a_verse_without_archaic_words_pilot_012(self):
        script = {"segments": [{"id": "scripture-thanks", "reference": "1 Thessalonians 5:18 (KJV)"}]}
        timeline = {"segments": [{"id": "scripture-thanks", "start": 30.0, "end": 40.0}],
                    "sentences": [{"segment": "scripture-thanks", "start": 30.5, "end": 38.0,
                                   "text": "In every thing give thanks: for this is the will of God in Christ Jesus concerning you."}]}
        self.assertEqual(sr.scripture_cards(script, timeline),
                         [{"segment": "scripture-thanks", "reference": "1 Thessalonians 5:18 (KJV)", "start": 30.5, "end": 38.0}])

    def test_whole_segment_when_no_kjv_sentence(self):
        seg = {"id": "s", "start": 1.0, "end": 9.0}
        # R5: the card leaves when the verse ends (its last sentence), not at the end of the pause after it
        self.assertEqual(sr.reference_end(seg, [{"segment": "s", "text": "Be still and know.", "end": 4.0}]), 4.0)
        self.assertEqual(sr.reference_end(seg, []), 9.0)


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
