#!/usr/bin/env python3
"""plan_check.py: a Short's plan is refused before any voice or Pavo call when it breaks the Shorts v2 grammar
(owner, 2026-10-26 after the mining: open on the conflict spoken, characters speak lip-synced, the Keeper only at the
close, 170-179 s, the lesson at most a quarter) or the part-6 Short rules."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import plan_check as pc  # noqa: E402

EXAMPLE = HERE / "plans" / "genesis-07-short.json"
KEEPER_LOOK = "an elderly storyteller with a silver beard"
EVE_LOOK = "a woman of about twenty-five with long black hair"
CHARS = {
    "keeper": {"status": "APPROVED", "look": KEEPER_LOOK, "refs": ["front"], "voice": "am_michael",
               "wardrobe": {"fire": "seated by a small campfire"}},
    "eve": {"status": "APPROVED", "look": EVE_LOOK, "refs": ["full"], "voice": "af_heart"},
    "adam": {"status": "DRAFT", "look": "a man of about thirty", "refs": [], "voice": "am_fenrir"},
    "mute": {"status": "APPROVED", "look": "a quiet shepherd boy", "refs": ["front"]},
}
STYLE = "Painterly cinematic realism, cinema camera."
STORM = (f"{STYLE} Extreme wide shot, slow push-in. Black storm clouds roll over the plain, lightning inside them. "
         "Dusk, a hard wind. Ominous. No people, no text, no logos.")
GOD_LINE = "The end of all flesh is come before me; for the earth is filled with violence through them."
STORY = "Ten generations after Eden the earth is full of people and noise, and nobody looks up at the sky."   # 20


def keeper(sid, lines):
    return {"id": sid, "kind": "keeper", "lines": lines,
            "prompt": f"{STYLE} Medium close-up, static camera. The narrator, {KEEPER_LOOK}, seated by a small campfire, "
                      "holds his head level, looks straight into the camera and speaks to the camera. Night in the "
                      "desert, firelight. Warm and grave."}


def scene(sid, lines, chars=(), seconds=12, look=None, **extra):
    who = look if look is not None else ", ".join({"eve": EVE_LOOK}.get(c, c) for c in chars) or "a crowd seen from behind"
    s = {"id": sid, "kind": "scene", "lines": lines, "seconds": seconds, "characters": list(chars),
         "prompt": f"{STYLE} Wide shot, slow tracking shot. {who} walks through the tents. Dusk, torchlight. Restless."}
    if not chars and "establishing" not in extra:
        s["figures"] = "anonymous"
    s.update(extra)
    return s


def god(sid, line=GOD_LINE, reference="Genesis 6:13 (KJV)", seconds=8, prompt=STORM, **extra):
    s = {"id": sid, "kind": "scene", "speaker": "god", "line": line, "reference": reference, "seconds": seconds,
         "characters": [], "prompt": prompt}
    s.update(extra)
    return s


# 17 words at Eve's measured 3.73 words a second: 4.56-5.57 s from the normal to the slowest pace, all of it
# reachable (15 words cross the 3.94-4.14 s band no clip reaches within the retime: TALK_LINE_UNREACHABLE, review of
# #412; 12 words are under TALK_MIN)
SPEAKER_LINE = "Why do you hide from the voice of the Lord in the garden this night, my son?"
EVE_SLOWEST = pc.VOICE_PACE["eve"] * pc.SLOW_RATIO


def speaker(sid, who="eve", line=SPEAKER_LINE, look=EVE_LOOK, **extra):
    s = {"id": sid, "kind": "scene", "speaker": who, "line": line, "characters": [who],
         "prompt": f"{STYLE} Medium close-up, slow push-in. {who.title()}, {look}, turns and speaks to him, her lips "
                   "moving clearly with every word. A garden at dusk, low gold light. Tense."}
    s.update(extra)
    return s


def plan(shots=None, narration=None):
    narration = narration or [
        {"kind": "story", "text": " ".join([STORY] * 4)},                                         # 0
        {"kind": "scripture", "reference": "Genesis 6:5 (KJV)", "text": "And God saw that the wickedness of man was "
         "great in the earth, and that every imagination of the thoughts of his heart was only evil continually."},
        {"kind": "story", "text": " ".join([STORY] * 8)},                                         # 2
        {"kind": "story", "text": " ".join([STORY] * 8)},                                         # 3
        {"kind": "insight", "text": "Notice the order. Grief comes before judgment. The flood is not the story of a "
         "cold God, but of a wounded heart."},                                                    # 4
        # 12 words (4.36-5.33 s); the old "... Part eight tomorrow." was 11 words, 4.0 s at the normal pace: inside
        # the band no clip reaches within the retime (TALK_LINE_UNREACHABLE, review of #408)
        {"kind": "cta", "text": "The full story is in the long video. Part eight is tomorrow."},     # 5
    ]
    shots = shots or [god("g-open"), scene("s-a", [0]), scene("s-b", [0]), speaker("s-eve"),
                      scene("s-c", [1], ["eve"]),
                      scene("s-d", [2]), scene("s-e", [2]), scene("s-f", [2]), scene("s-g", [2], climax=True),
                      scene("s-h", [3]), scene("s-i", [3]), scene("s-j", [3]), scene("s-k", [3]),
                      keeper("k-insight", [4]), keeper("k-close", [5])]
    return {"version": "bible-plan-v2", "episode": "genesis-07-short", "part": 7, "aspect_ratio": "9:16",
            "narration": narration, "shots": shots}


def codes(result):
    return [p.split()[0] for p in result["problems"]]


class Plan(unittest.TestCase):
    def test_the_fixture_plan_passes(self):
        r = pc.check(plan(), CHARS)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["pending"], [])
        self.assertTrue(170 <= r["estimate"]["seconds"] <= 179, r["estimate"])
        self.assertEqual(r["estimate"]["spoken_lines"], 2)

    def test_the_genesis_7_example_passes_against_the_real_character_bible(self):
        p = json.loads(EXAMPLE.read_text())
        r = pc.check(p)
        self.assertEqual(r["problems"], [])
        keeper_status = pc.ch.registry()["keeper"]["status"]
        self.assertEqual(r["pending"], [] if keeper_status == "APPROVED" else r["pending"][:1])
        # the owner's Genesis 7 rules: God's Genesis 6:13 line opens, the Keeper only for the insight and the close
        self.assertEqual((p["shots"][0]["speaker"], p["shots"][0]["reference"]), ("god", "Genesis 6:13 (KJV)"))
        self.assertTrue(p["shots"][0]["line"].startswith("The end of all flesh is come before me"))
        self.assertNotIn("noah", {c for s in p["shots"] for c in s.get("characters", [])})
        self.assertIn("Part eight tomorrow: Noah builds the ark", p["narration"][-1]["text"])
        self.assertLessEqual(r["estimate"]["lesson_share"], 0.15)

    def test_a_talking_keeper_faces_the_lens_on_a_static_camera(self):
        # E98: a push-in, a pull-back or a head bowed toward the fire lost the face or the lips in the lips check
        for old, new in (("static camera", "slow push-in"), ("looks straight into the camera", "leans toward the fire"),
                         ("static camera", "static camera, then a slow push-in"),
                         ("holds his head level", "bows his head")):
            p = plan()
            p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace(old, new)
            self.assertIn("KEEPER_POSE", codes(pc.check(p, CHARS)), new)
        p = plan()
        p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace("static camera", "Static camera")
        self.assertNotIn("KEEPER_POSE", codes(pc.check(p, CHARS)))

    def test_the_old_grammar_is_refused(self):
        p = plan()
        p["version"] = "bible-plan-v1"
        self.assertIn("PLAN_VERSION", codes(pc.check(p, CHARS)))

    def test_the_keeper_never_opens(self):
        p = plan()
        p["shots"][0] = keeper("k-open", [0])
        p["shots"][1:3] = []
        found = codes(pc.check(p, CHARS))
        self.assertIn("KEEPER_OPENS", found)
        self.assertIn("KEEPER_BEFORE_CLIMAX", found)

    def test_the_first_shot_carries_a_spoken_line(self):
        p = plan()
        del p["shots"][0]
        self.assertIn("OPEN_NOT_SPOKEN", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0:4] = [speaker("s-eve"), scene("s-a", [0]), scene("s-b", [0]), god("g-mid")]   # a character opens
        self.assertEqual(pc.check(p, CHARS)["problems"], [])

    def test_the_keeper_only_after_the_climax_and_only_for_the_lesson(self):
        p = plan()
        p["shots"][8].pop("climax")
        p["shots"][-3]["climax"] = True                     # the climax after the Keeper's first shot is refused
        p["shots"][-2], p["shots"][-3] = p["shots"][-3], p["shots"][-2]
        self.assertIn("LINES_OUT_OF_ORDER", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][9:13] = [keeper("k-story", [3])]
        found = codes(pc.check(p, CHARS))
        self.assertIn("KEEPER_LINE_KIND", found)

    def test_the_keeper_share_over_25_percent_is_refused(self):
        narration = plan()["narration"]
        narration[3] = {"kind": "insight", "text": " ".join(["Notice the order, grief comes before judgment."] * 3)}
        narration.insert(4, {"kind": "insight", "text": " ".join(["Grief comes before the judgment of the flood."] * 3)})
        narration.insert(5, {"kind": "insight", "text": " ".join(["The flood is the story of a wounded heart."] * 3)})
        shots = plan()["shots"][:9] + [keeper("k-a", [3]), keeper("k-b", [4]), keeper("k-c", [5]),
                                       keeper("k-insight", [6]), keeper("k-close", [7])]
        found = codes(pc.check(plan(shots, narration), CHARS))
        self.assertIn("KEEPER_SHARE", found)
        self.assertIn("LESSON_SHARE", found)

    def test_the_lesson_share_counts_insight_and_cta_lines_outside_the_keeper_too(self):
        p = plan()
        p["narration"][3] = {"kind": "insight", "text": p["narration"][3]["text"]}   # ~45 s of preaching over scenes
        r = pc.check(p, CHARS)
        self.assertIn("LESSON_SHARE", codes(r))
        self.assertNotIn("KEEPER_SHARE", codes(r))

    def test_a_missing_climax_or_a_landscape_climax_is_refused(self):
        p = plan()
        p["shots"][8].pop("climax")
        self.assertIn("CLIMAX_MISSING", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][1] = scene("s-a", [0], establishing=True, climax=True, look="a vast city of tents")
        self.assertIn("CLIMAX_NOT_ACTED", codes(pc.check(p, CHARS)))

    def test_an_unknown_or_unapproved_speaker_is_refused(self):
        for who, look, code in (("moses", "a man", "SPEAKER_UNKNOWN"), ("adam", "a man of about thirty",
                                                                           "SPEAKER_NOT_APPROVED"),
                                ("mute", "a quiet shepherd boy", "SPEAKER_NO_VOICE"),
                                ("keeper", KEEPER_LOOK, "SPEAKER_KEEPER")):
            p = plan()
            p["shots"][3] = speaker("s-eve", who=who, look=look)
            self.assertIn(code, codes(pc.check(p, CHARS)), who)

    def test_a_speaker_must_be_in_the_shot_speak_and_take_its_length_from_the_line(self):
        p = plan()
        p["shots"][3] = speaker("s-eve", characters=[])
        self.assertIn("SPEAKER_NOT_IN_SHOT", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", seconds=6)
        self.assertIn("SPEAKER_SHOT_FIELDS", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3]["prompt"] = p["shots"][3]["prompt"].replace("speaks to", "looks at")
        self.assertIn("SPEAKER_NOT_SPEAKING", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", line=" ".join(["Why do you hide from the voice?"] * 6))   # 42 words
        self.assertIn("SPEAKER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", line="Why?")
        self.assertIn("SPEAKER_LINE_TOO_SHORT", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = dict(speaker("s-eve"), lines=[0])
        self.assertIn("SPEAKER_SHOT_KIND", codes(pc.check(p, CHARS)))

    def test_a_misquoted_spoken_line_is_refused(self):
        p = plan()
        p["shots"][0]["line"] = GOD_LINE.replace("violence", "wickedness")
        self.assertIn("KJV", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", line="Hath God said, Ye shall not eat of every tree of the orchard?",
                                reference="Genesis 3:1 (KJV)")
        self.assertIn("KJV", codes(pc.check(p, CHARS)))
        p["shots"][3]["line"] = "Hath God said, Ye shall not eat of every tree of the garden?"
        self.assertNotIn("KJV", codes(pc.check(p, CHARS)))

    def test_god_speaks_only_scripture_over_a_scene_with_no_one_in_it(self):
        p = plan()
        p["shots"][0].pop("reference")
        self.assertIn("GOD_LINE_NOT_SCRIPTURE", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["prompt"] = STORM.replace("Black storm clouds roll over the plain", "An old man raises his face")
        self.assertIn("GOD_SHOT_WITH_A_PERSON", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["figures"] = "anonymous"
        self.assertIn("GOD_SHOT_WITH_A_PERSON", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["prompt"] = (f"{STYLE} Wide shot, slow push-in. A dry valley of stones. Dusk over the hills. "
                                   "Quiet. No people, no text, no logos.")
        self.assertIn("GOD_SHOT_NO_MEDIUM", codes(pc.check(p, CHARS)))

    def test_a_person_written_around_the_word_list_is_still_refused_in_gods_shot(self):
        """Review of #400: "an old bearded elder in a white robe lifts his staff" and "a winged angel of light"
        passed, putting God's voice over a visible man (the clip is also face-checked in episode_build)."""
        for person in ("An old bearded elder in a white robe lifts his staff against the storm",
                       "A winged angel of light descends through the storm clouds",
                       "A shepherd boy looks up at the lightning", "A king on a hill raises her hands to the sky"):
            p = plan()
            p["shots"][0]["prompt"] = STORM.replace("Black storm clouds roll over the plain", person)
            self.assertIn("GOD_SHOT_WITH_A_PERSON", codes(pc.check(p, CHARS)), person)
        self.assertEqual(pc.check(plan(), CHARS)["problems"], [])     # "No people" in the tail is not a person

    def test_the_climax_is_acted_never_a_god_voice_over_sky(self):
        """E92: genesis-07's only climax was s-judgment, God's voice over lightning on an empty plain, and the gate
        let it through. The climax shows people: approved characters or anonymous figures."""
        p = plan()
        p["shots"][8].pop("climax")
        p["shots"][0]["climax"] = True                         # God's voice-over storm
        self.assertIn("CLIMAX_NOT_ACTED", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][8].pop("figures")
        p["shots"][8]["establishing"] = False                  # a scene with no one in it
        self.assertIn("CLIMAX_NOT_ACTED", " ".join(pc.check(p, CHARS)["problems"]))
        p = plan()
        p["shots"][8].pop("climax")
        p["shots"][4]["climax"] = True                         # an approved character acting: accepted
        self.assertNotIn("CLIMAX_NOT_ACTED", codes(pc.check(p, CHARS)))
        g7 = json.loads(EXAMPLE.read_text())
        climax = [s for s in g7["shots"] if s.get("climax")]
        self.assertTrue(climax)
        for s in climax:
            self.assertNotEqual(s.get("speaker"), "god", s["id"])
            self.assertTrue(s.get("characters") or s.get("figures") == "anonymous", s["id"])

    def test_a_kjv_quote_without_a_reference_is_refused_and_is_not_our_words(self):
        self.assertEqual(pc.kjv_quote("Hath God said, Ye shall not eat of every tree of the garden?")[0],
                         "Genesis 3:1 (KJV)")
        self.assertIsNone(pc.kjv_quote("Ten generations after Eden the earth is full of people and noise."))
        p = plan()
        p["shots"][3] = speaker("s-eve", line="Hath God said, Ye shall not eat of every tree of the garden?")
        self.assertIn("KJV_UNREFERENCED", codes(pc.check(p, CHARS)))
        verse = ("And God saw that the wickedness of man was great in the earth, and that every imagination of the "
                 "thoughts of his heart was only evil continually.")
        p = plan()
        for k, n in ((0, 3), (2, 6), (3, 6)):                     # the "story" lines are the verse, unreferenced
            p["narration"][k] = {"kind": "story", "text": " ".join([verse] * n)}
        found = " ".join(pc.check(p, CHARS)["problems"])
        self.assertIn("KJV_UNREFERENCED line 0", found)
        self.assertIn("ORIGINAL_SHARE", found)                     # counted as Scripture, not our words
        self.assertEqual([p for p in pc.check(json.loads(EXAMPLE.read_text()))["problems"]
                          if p.startswith("KJV_UNREFERENCED")], [])

    def test_a_reference_that_is_not_text_is_a_problem_not_a_crash(self):
        p = plan()
        p["narration"][1]["reference"] = 6
        self.assertIn("REFERENCE_NOT_TEXT", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["reference"] = ["Genesis 6:13"]
        self.assertIn("REFERENCE_NOT_TEXT", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["reference"] = "Hezekiah 99:1"
        self.assertIn("KJV", codes(pc.check(p, CHARS)))

    def test_a_talking_line_fits_one_clip_pavo_keeps_its_audio_in(self):
        """E95: a talking clip is ceil(speech) s (4-12) with the speech 0.25-0.65 s shorter; the gap or the tail is a
        held frame, so the ceiling is 12 - 0.45 s and the floor a 4 s clip within the 10 % retime."""
        self.assertAlmostEqual(pc.TALK_LINE_MAX, 12.0 - 0.45)
        self.assertAlmostEqual(pc.TALK_PAD_TARGET, sum(pc.TALK_PAD) / 2)
        self.assertAlmostEqual(pc.TALK_MIN, 3.55 / 1.1)
        self.assertEqual((pc.TALK_CLIP, pc.TALK_PAD, pc.TALK_RETIME_MAX, pc.TALK_HOLD_MAX),
                         ((4, 12), (0.25, 0.65), 0.10, 1.3))
        p = plan()
        p["shots"][3] = speaker("s-eve", line=" ".join(["Why do you hide from the voice?"] * 5) +
                                " Answer me.")   # 37 words: 12.1 s at Eve's slowest pace
        self.assertGreater(37 / EVE_SLOWEST, pc.TALK_LINE_MAX)
        self.assertIn("SPEAKER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", line="Why do you hide?")   # 4 words: 1.5 s, no 4 s clip within 10 %
        self.assertIn("SPEAKER_LINE_TOO_SHORT", codes(pc.check(p, CHARS)))

    def test_one_talking_ceiling_for_every_talking_shot(self):
        """Review of #408: the closing Keeper had its own ceiling (KEEPER_LAST_MAX) beside TALK_MAX, and the build
        let 11.56-11.75 s through elsewhere; one limit, from TALK_CLIP and TALK_PAD, now serves plan and build."""
        self.assertFalse(hasattr(pc, "KEEPER_LAST_MAX"))
        self.assertFalse(hasattr(pc, "TALK_MAX"))
        self.assertAlmostEqual(pc.TALK_LINE_MAX, pc.TALK_CLIP[1] - (pc.TALK_PAD[0] + pc.TALK_PAD[1]) / 2)
        target, stretch = pc.talk_retime(11.7)                         # fits a 12 s clip, but retimed under the limit
        self.assertAlmostEqual(target, pc.TALK_LINE_MAX, places=3)
        self.assertAlmostEqual(stretch, 11.55 / 11.7, places=4)
        self.assertEqual(pc.talk_retime(11.55)[0], 11.55)

    def test_a_characters_line_is_timed_at_its_own_voices_measured_pace(self):
        """Review of #418 (arc-1 voice measurement): every line was estimated at WPS 2.75, a character's too; Kokoro speaks Eve at 3.73 words a second, so a
        12-word line of hers estimated 4.36 s, measured ~3.2 s (under TALK_MIN) and died at the build after the Pavo
        generations were spent. One measured table (voice_pace.py) times both the Short and the long."""
        import long_plan_check as lc
        import voice_pace
        self.assertIs(pc.VOICE_PACE, voice_pace.VOICE_PACE)
        self.assertIs(lc.VOICE_PACE, voice_pace.VOICE_PACE)
        self.assertEqual(pc.pace({"kind": "story", "text": "x"}), pc.WPS)          # the narrator keeps WPS
        self.assertEqual(pc.pace({"kind": "story", "text": "x", "speaker": "eve"}), voice_pace.VOICE_PACE["eve"])
        old = "Why do you hide from the voice of the Lord this night?"               # 12 words: 4.36 s at WPS
        self.assertGreater(pc.words(old) / pc.WPS, pc.TALK_MIN)
        self.assertLess(pc.words(old) / voice_pace.VOICE_PACE["eve"], pc.TALK_MIN)
        p = plan()
        p["shots"][3] = speaker("s-eve", line=old)
        self.assertIn("SPEAKER_LINE_TOO_SHORT", codes(pc.check(p, CHARS)))
        # a talking voice nobody measured is refused before its first line is voiced
        chars = dict(CHARS, serpent={"status": "APPROVED", "look": "a serpent", "refs": ["full"], "voice": "bm_fable"})
        p = plan()
        p["shots"][3] = speaker("s-eve", who="serpent", look="a serpent")
        self.assertIn("VOICE_PACE_UNMEASURED", codes(pc.check(p, chars)))

    def test_each_measured_pace_is_of_the_voice_the_speaker_still_has(self):
        """A pace belongs to a Kokoro voice: when characters.json gives a speaker another voice, measure it again."""
        import voice_pace
        reg = pc.ch.registry()
        god = json.loads((pc.ch.HERE / "characters.json").read_text())["god"]
        for who, voice in voice_pace.MEASURED_WITH.items():
            have = (god["voice"], god["speed"]) if who == pc.ch.GOD else (reg[who]["voice"], 1.0)
            self.assertEqual(have, voice, who)
        self.assertEqual(set(voice_pace.MEASURED_WITH), set(voice_pace.VOICE_PACE))
        for who in ("noah", "scoffer"):
            self.assertIn(who, voice_pace.VOICE_PACE)

    def test_a_talking_line_no_clip_reaches_within_the_retime_is_refused_at_plan_time(self):
        """Review of #408: 3.944-4.136 s needs -11.25 % into a 4 s clip or +13.75 % into a 5 s one, over the 10 %
        retime, so the build refused it (TALK_LINE_RETIME_OVER) after plan_check had passed it."""
        for speech in (3.95, 4.0, 4.13):
            self.assertIsNone(pc.talk_retime(speech), speech)
        for speech, target in ((3.94, 3.55), (4.14, 4.55), (3.3, 3.55), (5.2, 5.55)):
            self.assertAlmostEqual(pc.talk_retime(speech)[0], target, places=3, msg=speech)
        line = "Why do you hide from the voice of the Lord in the garden, my son?"   # 15 words: 4.02 s at Eve's pace
        self.assertTrue(3.944 < pc.words(line) / pc.VOICE_PACE["eve"] < 4.136)
        p = plan()
        p["shots"][3] = speaker("s-eve", line=line)
        self.assertIn("TALK_LINE_UNREACHABLE", codes(pc.check(p, CHARS)))
        p = plan()      # the fixture's old CTA, 11 words: 4.0 s at the normal pace
        p["narration"][5]["text"] = "The full story is in the long video. Part eight tomorrow."
        self.assertIn("TALK_LINE_UNREACHABLE shot 14 k-close", " ".join(pc.check(p, CHARS)["problems"]))
        p = plan()
        p["shots"][3] = speaker("s-eve", line=SPEAKER_LINE)   # 17 words
        self.assertNotIn("TALK_LINE_UNREACHABLE", codes(pc.check(p, CHARS)))

    def test_the_band_is_judged_at_every_kokoro_pace_not_the_normal_one_only(self):
        """Review of #412: the build retimes the measured Kokoro length, 2.18-3.63 words a second a line (WPS 2.75 is
        the average, WPS_SLOWEST 2.25): a line estimated at 3.64 s can be measured in 3.94-4.14 s and die at build.
        It is refused when any pace from WPS_SLOWEST to WPS puts it where no clip reaches."""
        self.assertIsNone(pc.talk_reach_gap(3.3, 3.9))                 # all in a 4 s clip
        self.assertIsNone(pc.talk_reach_gap(4.2, 11.5))                # 5-12 s clips overlap
        self.assertAlmostEqual(pc.talk_reach_gap(3.6, 4.4), 3.55 / 0.9, places=3)   # slowest pace in the band
        self.assertAlmostEqual(pc.talk_reach_gap(4.0, 4.6), 4.0, places=3)          # normal pace in the band
        self.assertIsNotNone(pc.talk_reach_gap(3.9, 3.95))
        for words, gaps in ((3.3, 0), (3.95, 0), (4.0, 0), (4.14, 0), (11.7, 0), (3.80, 0.35), (3.85, 0.35)):
            self.assertEqual(pc.talk_reach_gap(words, words, gaps) is None, pc.talk_retime(words, gaps) is not None,
                             (words, gaps))
        line = "Why do you hide from the voice of the Lord in the garden?"   # 13 words: 3.48 s normal, 4.26 s slowest
        self.assertLess(pc.words(line) / pc.VOICE_PACE["eve"], 3.944)
        self.assertGreater(pc.words(line) / EVE_SLOWEST, 4.136)
        p = plan()
        p["shots"][3] = speaker("s-eve", line=line)
        self.assertIn("TALK_LINE_UNREACHABLE", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = speaker("s-eve", line="Why do you hide from me?")   # 6 words: too short, not unreachable
        self.assertEqual([c for c in codes(pc.check(p, CHARS)) if c.startswith(("TALK_", "SPEAKER_LINE"))],
                         ["SPEAKER_LINE_TOO_SHORT"])

    def test_the_talking_floor_counts_the_gaps_atempo_does_not_stretch(self):
        """Review of #412: TALK_MIN (3.23 s) is a single line's floor. A shot of 2.90 s of words + a 0.35 s gap passed
        it and then read TALK_LINE_UNREACHABLE; the floor is the gaps + the shortest words a 4 s clip takes."""
        self.assertAlmostEqual(pc.talk_min(0.0), pc.TALK_MIN)
        self.assertAlmostEqual(pc.talk_min(0.35), 0.35 + 3.2 / 1.1)
        self.assertGreater(pc.talk_min(0.35), 2.90 + 0.35)
        self.assertIsNone(pc.talk_retime(2.90, 0.35))
        self.assertIsNotNone(pc.talk_retime(3.2 / 1.1 + 1e-6, 0.35))

    def test_the_retime_cap_is_on_the_words_atempo_stretches_not_on_the_fixed_gaps(self):
        """Review of #408: atempo changes only the words; the 0.35 s gaps between a talking shot's lines stay. Words
        3.80 s + one gap = 4.15 s: the whole is +9.6 % from 4.55 s, but the words would be stretched +10.5 %."""
        self.assertIsNone(pc.talk_retime(3.80, 0.35))
        target, stretch = pc.talk_retime(3.85, 0.35)       # words 3.85 s -> 4.20 s: +9.1 %
        self.assertAlmostEqual(target, 4.55, places=3)
        self.assertAlmostEqual(stretch, 4.20 / 3.85, places=4)
        target, stretch = pc.talk_retime(3.2, 0.35)       # 3.55 s fits a 4 s clip untouched
        self.assertAlmostEqual(target, 3.55, places=3)
        self.assertEqual(stretch, 1.0)

    def test_the_voice_track_puts_each_spoken_line_where_its_shot_is(self):
        items, carried = pc.sequence(plan())
        self.assertEqual(items[0]["speaker"], "god")
        self.assertEqual(items[0]["kind"], "scripture")
        self.assertEqual([x.get("line") for x in items], [None, 0, None, 1, 2, 3, 4, 5])
        self.assertEqual(items[2], {"kind": "story", "text": SPEAKER_LINE,
                                    "speaker": "eve", "shot": "s-eve"})
        self.assertEqual(carried[:5], [[0], [1], [1], [2], [3]])
        runs = pc.groups(plan()["shots"], carried)
        self.assertEqual([(a, b) for a, b, _ in runs][:4], [(0, 0), (1, 2), (3, 3), (4, 4)])

    def test_the_length_from_part_7_is_170_to_179_s(self):
        p = plan()
        p["narration"][3]["text"] = " ".join([STORY] * 3)          # ~22 s shorter
        self.assertIn("SHORT_LENGTH", " ".join(pc.check(p, CHARS)["problems"]))
        p = plan()
        p["narration"][3]["text"] = " ".join([STORY] * 10)         # ~15 s longer
        p["shots"][9:13] += [scene("s-l", [3])]
        self.assertIn("SHORT_LENGTH", " ".join(pc.check(p, CHARS)["problems"]))

    def test_an_unapproved_character_is_refused(self):
        p = plan()
        p["shots"][4] = scene("s-c", [1], ["adam"], look="a man of about thirty")
        self.assertIn("CHARACTER_NOT_APPROVED", codes(pc.check(p, CHARS)))

    def test_a_look_that_is_not_word_for_word_is_refused(self):
        p = plan()
        p["shots"][4] = scene("s-c", [1], ["eve"], look="a woman with long dark hair")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][-1]["prompt"] = p["shots"][-1]["prompt"].replace("silver beard", "white beard")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(pc.check(p, CHARS)))

    def test_a_keeper_line_over_12_seconds_is_refused(self):
        p = plan()
        p["narration"][4]["text"] = " ".join(["Notice the order, grief comes before judgment."] * 4)   # 28 words
        self.assertIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))
        # the closing clip: its tail is a held frame (E95), so the same 11.55 s ceiling
        p = plan()
        p["narration"][5]["text"] = ("The full story is in the long video on the channel, and part eight comes tomorrow. "
                                     "Noah builds the ark, so come and see it there.")   # 26 words: ~11.56 s
        self.assertLess(26 / pc.WPS_SLOWEST, pc.KEEPER_AUDIO[1])
        self.assertIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))
        p["narration"][5]["text"] = ("The full story is in the long video on the channel, and part eight comes tomorrow. "
                                     "Noah builds the ark, come and see it.")   # 24 words: 10.7 s, refused at 10.2 before
        self.assertNotIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))

    def test_establishing_shots_are_held_short_and_at_most_15_percent(self):
        p = plan()
        for i in (1, 2):
            p["shots"][i] = scene(p["shots"][i]["id"], p["shots"][i]["lines"], establishing=True,
                                  look="a vast city of tents")
        p["shots"][9:9] = [scene(f"s-x{k}", [2], establishing=True, look="a vast city of tents") for k in range(12)]
        found = codes(pc.check(p, CHARS))
        self.assertIn("ESTABLISHING_SHARE", found)
        self.assertIn("ESTABLISHING_ONLY", found)   # line 0 over landscape alone

    def test_a_scene_without_people_must_be_marked(self):
        p = plan()
        p["shots"][1] = scene("s-a", [0], look="a vast city of tents", figures=None)
        del p["shots"][1]["figures"]
        self.assertIn("SCENE_WITHOUT_CHARACTERS", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][1] = scene("s-a", [0], look="a crowd of men")
        self.assertIn("FIGURES_NOT_ANONYMOUS", codes(pc.check(p, CHARS)))

    def test_god_is_never_a_visible_figure(self):
        for prompt in ("God stands on a cloud above the tents", "the Lord appears as an old man with a beard",
                       "the hands of God reach down", "God watches the earth"):
            self.assertTrue(pc.god_problem(prompt), prompt)
        for prompt in ("the presence of God as a warm golden light breaking through storm clouds",
                       "the voice of the Lord carried by a strong wind over the plain", "a crowd of men walking"):
            self.assertIsNone(pc.god_problem(prompt), prompt)
        p = plan()
        p["shots"][5]["prompt"] += " God stands above the city."
        self.assertIn("GOD_AS_A_FIGURE", codes(pc.check(p, CHARS)))

    def test_the_keeper_closes_and_never_acts(self):
        p = plan()
        p["shots"][-1] = scene("s-close", [5])
        self.assertIn("KEEPER_MUST_CLOSE", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][5] = scene("s-d", [2], ["keeper"], look=KEEPER_LOOK)
        self.assertIn("KEEPER_IN_SCENE", codes(pc.check(p, CHARS)))

    def test_every_line_is_carried_in_order(self):
        p = plan()
        del p["shots"][9:13]
        self.assertIn("LINES_OUT_OF_ORDER", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][1]["lines"] = [0, 2]
        self.assertIn("SHOT_LINES", codes(pc.check(p, CHARS)))
        p = plan()   # a spoken line between two shots of the same narration line would cut that line in two
        p["shots"][2:2] = [speaker("s-eve2")]
        self.assertIn("LINES_OUT_OF_ORDER", codes(pc.check(p, CHARS)))

    def test_scene_seconds_and_prompt_form(self):
        p = plan()
        p["shots"][1]["seconds"] = 3
        p["shots"][2]["prompt"] = "a crowd seen from behind in the tents, " * 3
        found = codes(pc.check(p, CHARS))
        self.assertIn("SCENE_SECONDS", found)
        self.assertIn("PROMPT_NO_CINEMATOGRAPHY", found)
        self.assertIn("PROMPT_NOT_FIVE_PARTS", found)

    def test_a_misquoted_verse_and_the_short_rules(self):
        p = plan()
        p["narration"][1]["text"] = p["narration"][1]["text"].replace("continually", "always")
        p["narration"][5]["text"] = "Part eight tomorrow, see you there."
        found = " ".join(pc.check(p, CHARS)["problems"])
        self.assertIn("KJV line 1", found)
        self.assertIn("CTA_NOT_TO_THE_LONG", found)

    def test_a_draft_keeper_is_one_pending_row_not_a_crash(self):
        chars = copy.deepcopy(CHARS)
        chars["keeper"].update(status="DRAFT", refs=[])
        r = pc.check(plan(), chars)
        self.assertEqual(r["problems"], [])
        self.assertEqual(len(r["pending"]), 1)
        self.assertTrue(r["pending"][0].startswith("CHARACTER_PENDING keeper (DRAFT)"))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            ok = Path(d, "ok.json")
            ok.write_text(EXAMPLE.read_text())
            bad = Path(d, "bad.json")
            p = json.loads(EXAMPLE.read_text())
            p["shots"][-1]["kind"] = "scene"
            bad.write_text(json.dumps(p))
            run = lambda *a: subprocess.run([sys.executable, "-I", "-B", str(HERE / "plan_check.py"), *a],
                                            capture_output=True, text=True).returncode
            self.assertEqual(run(str(ok)), 0)
            self.assertEqual(run(str(bad)), 1)


# the long's plan (bible-long-plan-v1) and story QA v2/v3 run here too, so pr-checks.yml runs them unchanged
from test_long_plan_check import DraftArc1, Grammar as LongGrammar, NoRendererReadsTheNewQaYet, StoryQa  # noqa: E402,F401,E501

if __name__ == "__main__":
    unittest.main()
