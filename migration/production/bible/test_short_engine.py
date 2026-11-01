#!/usr/bin/env python3
"""short_engine.py: shots tile the Short, clips are never looped or slowed past MAX_SLOW, captions stay short."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import short_engine as se


class Plan(unittest.TestCase):
    def test_e146_native_picture_and_audio_use_the_same_measured_source_onset(self):
        import episode_build as eb
        import long_build as lb
        import pavo_native as pn
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            clip = d / "native.mp4"
            clip.write_bytes(b"approved native clip")
            layout = {"lines": [{"start": 0.0, "end": 2.0}], "total": 3.2}
            spans = {"s-eve": ([0], 0.6, 2.6)}
            approvals = {"s-eve": {"clip_sha256": eb.sha256(clip),
                                    "speech": {"gain_db": 1.0, "onset": 0.6, "end": 2.6}}}
            mixed = []
            with patch.object(eb, "native_spans", return_value=spans), \
                    patch.object(eb.clip_timing, "measure", return_value={"clip_sha256": eb.sha256(clip),
                                 "video_seconds": 4.0, "audio_seconds": 4.0}), \
                    patch.object(pn, "premix", side_effect=lambda voice, places, out, total: mixed.extend(places)):
                voice, seconds, onsets = eb.native_voice({}, d, layout, {"s-eve": str(clip)},
                                                        {"s-eve": 4.0}, approvals)
            cuts = eb.shift_onsets([{"shot": "s-eve", "clip": str(clip), "start": 0.0, "end": 3.2,
                                     "src_start": 0.0, "speed": 1.0, "talk": {"start": 0.0, "end": 2.0}}], onsets)
            self.assertEqual(cuts[0]["src_start"], mixed[0]["src_start"])
            timeline = d / "timeline.json"
            timeline.write_text(json.dumps({"voice_seconds": 2.0, "sentences": layout["lines"]}))
            cplan = {"voice": voice, "timeline": str(timeline), "music": "unused", "shots": cuts,
                     "native_onsets": onsets}
            # The real renderer must reach its media stage after validating this synchronized plan. Stop exactly
            # there: no encode is needed to reproduce the former PLAN_REFUSED at the producer/consumer boundary.
            with patch.object(se, "duration", return_value=4.0), \
                    patch.object(lb, "run", side_effect=RuntimeError("media stage reached")):
                with self.assertRaisesRegex(RuntimeError, "media stage reached"):
                    lb.render(cplan, d / "out.mp4")
            self.assertEqual(se.talk_problems(cuts, layout["lines"], onsets), [])
            for change in ({"src_start": 0.0}, {"src_start": 0.7}, {"speed": 1.1}, {"end": 1.9}, {"start": 0.1}):
                wrong = [dict(cuts[0], **change)]
                self.assertIn("TALK_NOT_ALIGNED 0", se.talk_problems(wrong, layout["lines"], onsets), change)
            # A positive offset without an actual native audio placement is still refused; Kokoro remains at 0.
            self.assertIn("TALK_NOT_ALIGNED 0", se.talk_problems(cuts, layout["lines"]))
            kokoro = copy.deepcopy(cuts)
            kokoro[0]["src_start"] = 0.0
            self.assertEqual(se.talk_problems(kokoro, layout["lines"]), [])
            kokoro[0]["src_start"] = 0.0005
            self.assertIn("TALK_NOT_ALIGNED 0", se.talk_problems(kokoro, layout["lines"]))
            for invalid in (float("nan"), float("inf"), -float("inf"), -0.1):
                self.assertIn("TALK_NOT_ALIGNED 0", se.talk_problems(cuts, layout["lines"], {"s-eve": invalid}))

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

    def test_e249_scripture_is_styled_apart_and_cited_with_chapter_and_verse(self):
        ass = se.build_ass([
            {"start": 0.0, "end": 2.0, "text": "our own words here"},
            {"start": 2.0, "end": 5.0, "text": "There went in two and two", "kind": "scripture",
             "reference": "Genesis 7:9 (KJV)"}])
        lines = [x for x in ass.splitlines() if x.startswith("Dialogue")]
        own = [x for x in lines if ",Cap,," in x]
        scr = [x for x in lines if ",Scr,," in x]
        ref = [x for x in lines if ",Ref,," in x]
        self.assertEqual(len(own), 2)                     # our commentary stays in the normal captions
        self.assertTrue(scr and not any("our own" in x for x in scr))
        self.assertEqual(len(ref), 1)                     # one citation for the whole quotation
        self.assertTrue(ref[0].endswith("Genesis 7:9 · KJV"))
        self.assertIn(",0:00:02.00,0:00:05.00,Ref,", ref[0])
        self.assertIn("Style: Scr,DejaVu Serif", ass)     # its own typography
        self.assertEqual(se.citation("Genesis 6:13 (KJV)"), "Genesis 6:13 · KJV")
        self.assertEqual(se.citation(None), "")
        # scripture without a reference is never silently shown as plain captions with a made-up citation
        plain = se.build_ass([{"start": 0, "end": 1, "text": "x y", "kind": "scripture"}])
        self.assertNotIn(",Ref,,", plain)

    def test_e249_compose_timeline_carries_kind_and_reference_to_the_captions(self):
        src = (Path(__file__).resolve().parent / "episode_build.py").read_text()
        self.assertIn('who.update(kind="scripture", reference=items[k]["reference"])', src)


if __name__ == "__main__":
    unittest.main()
