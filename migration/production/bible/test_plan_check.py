#!/usr/bin/env python3
"""plan_check.py: a Short's plan is refused before any voice or Pavo call when it breaks the Shorts v2 grammar
(owner, 2026-10-26 after the mining: open on the conflict spoken, characters speak lip-synced, the Keeper only at the
close, 170-179 s, the lesson at most a quarter) or the part-6 Short rules."""
import copy
import json
import re
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
               "wardrobe": {"fire": "seated by a small campfire"}, "talk_refs": ["talk"]},
    "eve": {"status": "APPROVED", "look": EVE_LOOK, "refs": ["full"], "voice": "af_heart"},
    "adam": {"status": "DRAFT", "look": "a man of about thirty", "refs": [], "voice": "am_fenrir"},
    "mute": {"status": "APPROVED", "look": "a quiet shepherd boy", "refs": ["front"]},
}
STYLE = "Painterly cinematic realism, cinema camera."
# E108: every scene prompt of a Genesis story states its period and the exclusions, word for word (plan_check
# PERIOD_SETTING / PERIOD_EXCLUDE); written out here so the test fails while plan_check has no such rule
SETTING = "The ancient Near East before the flood: only goat-hair tents, open fires and torches on the open plain."
EXCLUDE = "No stone buildings, towers, churches, glass lanterns, modern clothing or roads."
PERIOD = f"{SETTING} {EXCLUDE}"
STORM = (f"{STYLE} Extreme wide shot, slow push-in. Black storm clouds roll over the plain, lightning inside them. "
         f"Dusk, a hard wind. Ominous. {PERIOD} No people, no text, no logos.")
GOD_LINE = "The end of all flesh is come before me; for the earth is filled with violence through them."
STORY = "Ten generations after Eden the earth is full of people and noise, and nobody looks up at the sky."   # 20


def keeper(sid, lines):
    return {"id": sid, "kind": "keeper", "lines": lines,
            "prompt": f"{STYLE} Medium close-up, static camera. The narrator, {KEEPER_LOOK}, seated by a small campfire, "
                      "holds his head level, looks straight into the camera and speaks to the camera. Night in the "
                      f"desert, firelight ({sid}). Warm and grave."}   # one picture per shot (PROMPT_REPEATED)


def scene(sid, lines, chars=(), seconds=12, look=None, **extra):
    who = look if look is not None else ", ".join({"eve": EVE_LOOK}.get(c, c) for c in chars) or "a crowd seen from behind"
    s = {"id": sid, "kind": "scene", "lines": lines, "seconds": seconds, "characters": list(chars),
         "prompt": f"{STYLE} Wide shot, slow tracking shot. {who} walks through the tents. Dusk, torchlight ({sid}). "
                   f"Restless. {PERIOD}"}
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
                   f"moving clearly with every word. A garden at dusk, low gold light. Tense. {PERIOD}"}
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
            "passage": "Genesis 6:5-13 (KJV)", "narration": narration, "shots": shots}


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
        chars = dict(CHARS, raven={"status": "APPROVED", "look": "a black raven", "refs": ["full"], "voice": "bm_lewis"})
        p = plan()
        p["shots"][3] = speaker("s-eve", who="raven", look="a black raven")
        self.assertIn("VOICE_PACE_UNMEASURED", codes(pc.check(p, chars)))

    def test_each_measured_pace_is_of_the_voice_the_speaker_still_has(self):
        """A pace belongs to a Kokoro voice: when characters.json gives a speaker another voice, measure it again."""
        import voice_pace
        for who, (voice, speed) in voice_pace.MEASURED_WITH.items():
            self.assertEqual(pc.ch.voice(who), {"voice_id": voice, "speed": speed}, who)
        self.assertEqual(set(voice_pace.MEASURED_WITH), set(voice_pace.VOICE_PACE))
        self.assertEqual(set(voice_pace.VOICE_SLOWEST), set(voice_pace.VOICE_PACE) - {pc.ch.NARRATOR})
        for who in ("noah", "scoffer", "serpent"):
            self.assertIn(who, voice_pace.VOICE_PACE)

    def test_a_speakers_bounds_are_never_looser_than_the_measurements(self):
        """E104, review of #421: keeping the fastest run and slowing it by SLOW_RATIO gave Eve a slowest pace of 3.05
        words a second, but her measured runs reach 3.42 and her lines 2.85: a 35-word line passed SPEAKER_LINE_TOO_LONG
        at ~11.5 s and measures ~12.3 s, over TALK_LINE_MAX. The fast bound is the fastest run (too short), the slow
        bound the slower of the slowest run x SLOW_RATIO and the slowest line (too long, unreachable)."""
        import voice_pace
        ev = HERE.parents[1] / "evidence"
        arc = json.loads((ev / "long/20261026/arc-01-voice.json").read_text())["pace_by_voice_words_per_s"]
        ns = json.loads((ev / "long/20261026/noah-scoffer-voice.json").read_text())["pace_by_voice_words_per_s"]
        kp = json.loads((ev / "voice/20261026/kokoro-pace.json").read_text())
        runs, lines = {}, {}
        for run in arc.values():
            for key, v in run.items():
                runs.setdefault(key.split()[0], []).append(v["pace"])
                if "line_min" in v:
                    lines.setdefault(key.split()[0], []).append(v["line_min"])
        for src in (ns, kp["probe_by_voice"]):
            for who, v in src.items():
                runs.setdefault(who, []).append(v["pace"])
                lines.setdefault(who, []).append(v["line_min"])
        for e in kp["short_plans_voiced"].values():
            for who, v in e["pace_by_speaker"].items():
                lines.setdefault(who, []).append(v["line_min"])
        short_god = kp["short_god"]["pace"]
        runs["god"].append(short_god)
        for who, slow in voice_pace.VOICE_SLOWEST.items():
            self.assertLessEqual(slow, min(runs[who]) * pc.SLOW_RATIO + 1e-3, who)
            self.assertLessEqual(slow, min(lines[who]) + 1e-3, who)
            self.assertGreaterEqual(pc.pace({"text": "x", "speaker": who}), max(runs[who]) - 1e-3, who)
        # God in a Short at the Short-measured pace; the long keeps the long's
        self.assertAlmostEqual(pc.pace({"text": "x", "speaker": "god"}), short_god, places=3)
        line = " ".join(["Why do you hide from the voice?"] * 5)                           # 35 words
        self.assertLessEqual(35 / (voice_pace.VOICE_PACE["eve"] * pc.SLOW_RATIO), pc.TALK_LINE_MAX)
        self.assertGreater(35 / min(runs["eve"]) / pc.SLOW_RATIO, pc.TALK_LINE_MAX)
        p = plan()
        p["shots"][3] = speaker("s-eve", line=line)
        self.assertIn("SPEAKER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))

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

    def test_a_compose_refusal_is_found_at_plan_time(self):
        # E106: three scenes sharing a 5-word line passed every plan rule, then short_engine would refuse each
        # cut under 1 s (SHOT_TOO_SHORT) only at the compose, after every Pavo clip was made
        p = plan()
        p["narration"].insert(1, {"kind": "story", "text": "Nobody listens to him now."})
        for s in p["shots"]:
            if s.get("lines"):
                s["lines"] = [k + 1 if k >= 1 else k for k in s["lines"]]
        at = [s["id"] for s in p["shots"]].index("s-c")
        p["shots"][at:at] = [scene("s-x1", [1]), scene("s-x2", [1]), scene("s-x3", [1])]
        found = pc.check(p, CHARS)["problems"]
        self.assertTrue(found and all(x.startswith("BUILD SHOT_TOO_SHORT") for x in found), found)

    def test_the_same_prompt_twice_is_refused(self):
        # E106 (owner: production comes out at 9.5, the review only confirms): the review's visual variety as a plan
        # rule: one prompt is one picture, so a repeated prompt shows the same shot twice
        p = plan()
        p["shots"][2]["prompt"] = p["shots"][1]["prompt"]
        self.assertEqual(codes(pc.check(p, CHARS)), ["PROMPT_REPEATED"])

    def test_a_missing_reference_record_is_found_at_plan_time(self):
        # E106: an APPROVED character whose kept reference has no record passed the plan, then refs_step refused
        # it (REFERENCE_RECORD_MISSING) in the build, after the voice
        chars = copy.deepcopy(CHARS)
        p = plan()
        p["shots"][4] = scene("s-c", [1], ["mute"], look="a quiet shepherd boy")
        found = pc.check(p, chars)["problems"]
        self.assertEqual([x.split()[:3] for x in found], [["BUILD", "REFERENCE_RECORD_MISSING", "ch-mute-front"]])

    def test_strict_refuses_a_path_or_episode_episode_yml_refuses(self):
        # E106: episode.yml refuses PLAN_PATH_REFUSED / PLAN_EPISODE_MISMATCH in its first step; strict says so first
        self.assertEqual(pc.path_problems(EXAMPLE, json.loads(EXAMPLE.read_text())), [])
        self.assertTrue(pc.path_problems(EXAMPLE, {"episode": "genesis-07"})[0].startswith("PLAN_EPISODE_MISMATCH"))
        self.assertTrue(pc.path_problems("/tmp/genesis-07-short.json", {"episode": "genesis-07-short"})[0]
                        .startswith("PLAN_PATH"))
        workflow = (pc.ROOT / ".github" / "workflows" / "episode.yml").read_text()
        self.assertIn(pc.PLAN_PATH.pattern, workflow)   # the same pattern, character for character

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


# genesis-07-short.json as main had it before plan B (#413, commit 1c1ed79): the lip-synced Keeper. Run 40307414749
# built its 30 scene and God clips from exactly these requests (its report.json: 30 of 30 prompts and seconds equal)
TALKING_COMMIT = "1c1ed79"


def talking_genesis_07():
    return subprocess.run(["git", "-C", str(HERE), "show",
                           f"{TALKING_COMMIT}:migration/production/bible/plans/genesis-07-short.json"],
                          capture_output=True, text=True, check=True).stdout


def keeper_vo(sid, lines, action="holds his head level and looks straight into the camera"):
    return {"id": sid, "kind": "keeper", "voiceover": True, "lines": lines,
            "prompt": f"{STYLE} Medium close-up, static camera. The narrator, {KEEPER_LOOK}, seated by a small campfire, "
                      f"{action}, his lips closed, silent, as the flames flicker. Night in the desert, firelight "
                      f"({sid}). Warm and grave."}


def vo_plan(**kw):
    p = plan(**kw)
    p["shots"][-2:] = [keeper_vo("k-insight", [4]),
                       keeper_vo("k-close", [5], "holds his head level, looks straight into the camera and rolls the "
                                                 "scroll closed")]
    return p


class KeeperVoiceover(unittest.TestCase):
    """Plan B (owner, 2026-10-26): an opt-in `"voiceover": true` Keeper shot shows him on screen with his mouth closed
    while his line plays from the voice track; the default (a talking, lip-synced Keeper) is unchanged."""

    def test_the_default_keeper_still_talks(self):
        p = plan()
        self.assertTrue(all(pc.talking(s) for s in p["shots"] if s["kind"] == "keeper"))
        self.assertFalse(any(pc.voiceover(s) for s in p["shots"]))

    def test_a_voiceover_keeper_is_not_a_talking_shot_and_passes(self):
        p = vo_plan()
        r = pc.check(p, CHARS)
        self.assertEqual(r["problems"], [])
        self.assertTrue(pc.voiceover(p["shots"][-1]))
        self.assertFalse(pc.talking(p["shots"][-1]))
        # his share and the lesson share count the voice-over shots exactly as the talking ones
        self.assertEqual(r["estimate"]["keeper_share"], pc.check(plan(), CHARS)["estimate"]["keeper_share"])
        self.assertEqual(r["estimate"]["lesson_share"], pc.check(plan(), CHARS)["estimate"]["lesson_share"])

    def test_its_line_is_narration_in_the_keepers_voice(self):
        items, carried = pc.sequence(vo_plan())
        for k in carried[-2:]:
            self.assertEqual(len(k), 1)
            self.assertNotIn("speaker", items[k[0]])      # narration: am_michael, carried by the voice track

    def test_the_prompt_must_say_his_lips_stay_closed_and_name_no_speech(self):
        for old, new in (("his lips closed, silent", "calm"), ("his lips closed, silent", "his lips closed"),
                         ("looks straight into the camera", "looks straight into the camera and speaks"),
                         ("looks straight into the camera", "looks straight into the camera and says a few words"),
                         ("looks straight into the camera", "looks straight into the camera, talking softly"),
                         ("looks straight into the camera", "looks straight into the camera, his lips moving")):
            p = vo_plan()
            p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace(old, new)
            self.assertIn("KEEPER_VO_PROMPT", codes(pc.check(p, CHARS)), new)
        # the talking rules are not asked of him: no "speaks", no KEEPER_POSE
        found = codes(pc.check(vo_plan(), CHARS))
        self.assertNotIn("KEEPER_NOT_SPEAKING", found)
        self.assertNotIn("KEEPER_POSE", found)

    def test_every_phrasing_that_lost_his_face_is_refused(self):
        # review of #423: the calibration prompts that lost the face, and the usual ways of saying the same
        for phrase in ("looking down at the scroll", "gazing into the flames", "glances down", "his eyes on the flames",
                       "eyes on the fire", "raises his eyes from the fire", "his head bowed", "his eyes lowered",
                       "stares into the embers", "looks at the scroll", "reads the scroll", "turns his head away",
                       "in profile", "seen from the side", "glancing at the fire", "lowering his gaze"):
            p = vo_plan()
            p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace(
                "his lips closed, silent", f"{phrase}, his lips closed, silent")
            self.assertIn("KEEPER_VO_POSE", codes(pc.check(p, CHARS)), phrase)
        # what passed stays allowed: rolling the scroll closed while facing the lens, the fire beside him
        p = vo_plan()
        p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace(
            "his lips closed, silent", "slowly rolls the old scroll closed in his hands, the fire beside him, his lips "
            "closed, silent")
        self.assertNotIn("KEEPER_VO_POSE", codes(pc.check(p, CHARS)))

    def test_a_voiceover_keeper_needs_his_talking_reference(self):
        # the front view failed the face 4 of 4 (keeper-vo/calibration.json): no silent fallback to it
        chars = copy.deepcopy(CHARS)
        del chars["keeper"]["talk_refs"]
        self.assertIn("KEEPER_VO_NO_TALK_REF", codes(pc.check(vo_plan(), chars)))
        self.assertNotIn("KEEPER_VO_NO_TALK_REF", codes(pc.check(plan(), chars)))   # a talking plan does not need it

    def test_the_cover_before_and_after_his_line_is_compose_s_own(self):
        p = vo_plan()
        n = len(p["shots"])
        self.assertEqual(pc.vo_cover(p["shots"], n - 1), (0.0, pc.TAIL))        # the closing tail, after a VO shot
        self.assertEqual(pc.vo_cover(p["shots"], n - 2), (0.0, pc.LINE_GAP))    # after scenes: the gap after it
        p["shots"][-2] = keeper("k-insight", [4])                                # a talking Keeper before it
        self.assertEqual(pc.vo_cover(p["shots"], n - 1), (pc.LINE_GAP, pc.TAIL))
        self.assertEqual(pc.vo_covered(6.0, p["shots"], n - 1), 6.0 + pc.LINE_GAP + pc.TAIL)

    def test_the_line_cap_counts_the_gap_before_and_the_tail_after(self):
        """Review of #423: the cap was the line + after only; a talking Keeper before a voice-over one leaves the gap
        before it on the voice-over clip too."""
        found = None
        for n in range(10, 60):
            text = " ".join(["the full story is in the long video"] * 8).split()[:n]
            text = " ".join(text) + " part eight tomorrow."
            vo = vo_plan()
            vo["narration"][5]["text"] = text
            mixed = copy.deepcopy(vo)
            mixed["shots"][-2] = keeper("k-insight", [4])
            a = [x for x in pc.check(vo, CHARS)["problems"] if x.startswith("KEEPER_LINE_TOO_LONG shot 14")]
            b = [x for x in pc.check(mixed, CHARS)["problems"] if x.startswith("KEEPER_LINE_TOO_LONG shot 14")]
            if not a and b:
                found = n
                break
        self.assertIsNotNone(found)   # some line fits after a voice-over shot but not after a talking one

    def test_a_voiceover_line_under_the_input_floor_is_refused_as_in_the_build(self):
        # lines_step refuses a Keeper line under KEEPER_AUDIO[0] (2.0 s); the plan refuses it first
        p = vo_plan()
        p["narration"][5]["text"] = "Part eight tomorrow."
        self.assertIn("KEEPER_LINE_TOO_SHORT", codes(pc.check(p, CHARS)))
        self.assertEqual(pc.VO_LINE_MIN, pc.KEEPER_AUDIO[0])

    def test_he_faces_the_lens_so_the_still_mouth_check_finds_his_face(self):
        # direct closed-mouth clips, 26/10: looking down into the fire the landmarker found his face in 2 % and 17 % of
        # the frames (FACE_NOT_FOUND); facing the lens with the talking reference, 100 %
        for old, new in (("looks straight into the camera", "looks down into the campfire"),
                         ("looks straight into the camera", "gazes into the fire"),
                         ("holds his head level and looks straight into the camera", "lowers his eyes"),
                         ("static camera", "slow push-in")):
            p = vo_plan()
            p["shots"][-2]["prompt"] = p["shots"][-2]["prompt"].replace(old, new)
            found = codes(pc.check(p, CHARS))
            self.assertIn("KEEPER_VO_POSE", found, new)
            self.assertNotIn("KEEPER_POSE", found, new)

    def test_his_look_and_wardrobe_stay_word_for_word(self):
        p = vo_plan()
        p["shots"][-1]["prompt"] = p["shots"][-1]["prompt"].replace("silver beard", "grey beard")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(pc.check(p, CHARS)))
        p = vo_plan()
        p["shots"][-1]["prompt"] = p["shots"][-1]["prompt"].replace("seated by a small campfire", "standing")
        self.assertIn("KEEPER_WARDROBE", codes(pc.check(p, CHARS)))

    def test_the_keeper_and_lesson_shares_still_count_voiceover_shots(self):
        narration = plan()["narration"]
        narration[3] = {"kind": "insight", "text": " ".join(["Notice the order, grief comes before judgment."] * 3)}
        narration.insert(4, {"kind": "insight", "text": " ".join(["Grief comes before the judgment of the flood."] * 3)})
        narration.insert(5, {"kind": "insight", "text": " ".join(["The flood is the story of a wounded heart."] * 3)})
        shots = plan()["shots"][:9] + [keeper_vo("k-a", [3]), keeper_vo("k-b", [4]), keeper_vo("k-c", [5]),
                                       keeper_vo("k-insight", [6]), keeper_vo("k-close", [7])]
        found = codes(pc.check(plan(shots, narration), CHARS))
        self.assertIn("KEEPER_SHARE", found)
        self.assertIn("LESSON_SHARE", found)

    def test_a_voiceover_keeper_never_opens_and_closes_after_the_climax(self):
        p = vo_plan()
        p["shots"][0] = keeper_vo("k-open", [0])
        p["shots"][1:3] = []
        self.assertIn("KEEPER_OPENS", codes(pc.check(p, CHARS)))
        p = vo_plan()
        p["shots"].insert(5, keeper_vo("k-early", [2]))
        p["shots"][6:9] = []
        self.assertIn("KEEPER_BEFORE_CLIMAX", codes(pc.check(p, CHARS)))

    def test_the_clip_length_comes_from_the_line_and_no_talk_rule_applies(self):
        p = vo_plan()
        p["shots"][-1]["seconds"] = 8
        self.assertIn("KEEPER_SHOT_FIELDS", codes(pc.check(p, CHARS)))
        # a 10-word close sits in the 3.94-4.14 s band no talking clip reaches (TALK_LINE_UNREACHABLE when he talks);
        # as a voice-over there is no Pavo audio and no retime, so it is not refused
        short = "The full story is in the long video, part eight tomorrow."
        talking = plan()
        talking["narration"][5]["text"] = short
        self.assertIn("TALK_LINE_UNREACHABLE", codes(pc.check(talking, CHARS)))
        p = vo_plan()
        p["narration"][5]["text"] = short
        self.assertNotIn("TALK_LINE_UNREACHABLE", codes(pc.check(p, CHARS)))
        self.assertEqual(pc.vo_clip_seconds(8.42 + pc.TAIL), 10)       # ceil(line + tail), 4-12 s
        self.assertEqual(pc.vo_clip_seconds(2.1 + pc.LINE_GAP), 4)
        self.assertEqual(pc.vo_clip_seconds(14.0 + pc.TAIL), 12)       # the compose slows it at most 1.3

    def test_a_voiceover_line_too_long_for_one_clip_is_refused(self):
        p = vo_plan()
        p["narration"][5]["text"] = " ".join(["The full story is in the long video, see you tomorrow."] * 4)
        self.assertIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))

    def test_voiceover_is_only_a_keeper_flag_and_only_true_or_false(self):
        p = vo_plan()
        p["shots"][1]["voiceover"] = True
        self.assertIn("VOICEOVER_FIELD", codes(pc.check(p, CHARS)))
        p = vo_plan()
        p["shots"][-1]["voiceover"] = "yes"
        self.assertIn("VOICEOVER_FIELD", codes(pc.check(p, CHARS)))

    def test_genesis_7_is_the_voiceover_plan_and_keeps_every_scene_and_god_shot(self):
        """Plan B for 27/10 (the lip-synced Keeper passed 1 in 45, #419): genesis-07's three Keeper shots switched to
        voice-over, their lines unchanged; every scene and God shot byte-identical to the plan run 40307414749 built
        from, so its resume keeps the 30 clips (E93)."""
        old_text = talking_genesis_07()
        base, vo = json.loads(old_text), json.loads(EXAMPLE.read_text())
        self.assertFalse(any(s.get("voiceover") for s in base["shots"]))
        r = pc.check(vo)
        self.assertEqual((r["problems"], r["pending"]), ([], []))
        self.assertEqual(vo["narration"], base["narration"])
        self.assertEqual({k: v for k, v in vo.items() if k not in ("shots", "period")},
                         {k: v for k, v in base.items() if k != "shots"})
        self.assertEqual(len(vo["shots"]), len(base["shots"]))
        for a, b in zip(base["shots"], vo["shots"]):
            if a["kind"] == "keeper":
                self.assertEqual((b["id"], b["lines"], b.get("voiceover")), (a["id"], a["lines"], True))
            else:   # E108: the scene prompts now carry the period (ScenePeriod); every other field is the same
                self.assertEqual({k: v for k, v in b.items() if k != "prompt"},
                                 {k: v for k, v in a.items() if k != "prompt"})
        self.assertEqual(sum(1 for s in vo["shots"] if s["kind"] == "scene"), 30)
        self.assertFalse((HERE / "plans" / "genesis-07-short-vo.json").exists())   # one genesis-07 plan, dispatchable


# the plan run 40341856955 built genesis-07 from (main at #422): its review found a man in a modern long coat with a
# glass kerosene lantern on a cobbled European street (s-walker) and a European town with church towers (s-family)
PERIOD_BASE_COMMIT = "04d6923"
# the shots whose clips showed an anachronism in that run's composed file (evidence/pavo/20261026/period/review.json)
ANACHRONISTIC = {"s-walker", "s-family", "s-wind", "s-theft", "s-quarrel", "s-ruins", "s-children", "s-knife"}
# review of #426: the root-cause words (city of tents, lane, room, table) reworded in these, nothing else changed
REWORDED = {"s-tents", "s-market", "s-plain", "s-mother", "s-scroll", "s-storm", "s-jar", "s-gathering", "s-flee",
            "s-still", "s-terror", "s-lamp", "s-noah"}


class ScenePeriod(unittest.TestCase):
    """E108 (review of genesis-07 run 40341856955): no scene prompt stated its period, and no gate checked it, so Pavo
    filled a lane or a horizon with a European street, a town of stone with church towers, a glass lantern, a modern
    coat or cap. Every scene prompt now states its story's period word for word and carries the exclusions."""

    def test_the_wording_is_one_shared_constant(self):
        self.assertEqual(pc.PERIOD_SETTING, SETTING)
        self.assertEqual(pc.PERIOD_EXCLUDE, EXCLUDE)
        self.assertEqual(pc.period(plan()), pc.PERIODS["before-the-flood"])

    def test_a_scene_without_the_setting_or_the_exclusions_is_refused(self):
        for drop in (SETTING, EXCLUDE):
            p = plan()
            p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace(drop, "")
            self.assertIn("SCENE_PERIOD_MISSING", codes(pc.check(p, CHARS)), drop)
        p = plan()   # God's voice-over shot and a speaking character are scenes too
        p["shots"][0]["prompt"] = p["shots"][0]["prompt"].replace(SETTING, "")
        p["shots"][3]["prompt"] = p["shots"][3]["prompt"].replace(EXCLUDE, "")
        self.assertEqual([x.split()[:4] for x in pc.check(p, CHARS)["problems"]],
                         [["SCENE_PERIOD_MISSING", "shot", "0", "g-open"], ["SCENE_PERIOD_MISSING", "shot", "3", "s-eve"]])

    def test_the_keeper_is_not_a_scene(self):
        p = plan()
        self.assertNotIn("ancient Near East", p["shots"][-1]["prompt"])
        self.assertEqual(pc.check(p, CHARS)["problems"], [])

    def test_a_scene_naming_what_the_period_excludes_is_refused(self):
        # review of #426: the root-cause words of run 40341856955 too (city of tents, lane, room...)
        for word in ("on the road out of the city", "carrying a glass lantern", "toward a church on the horizon",
                     "in a long coat", "down a cobbled street", "past a stone tower", "in a peaked cap",
                     "through the city of tents", "down a narrow lane", "into a quiet room", "past the buildings",
                     "along a mud-brick wall", "past brick houses", "under a dome", "into the village",
                     "to a wooden table", "past a glass jar", "past the town walls"):
            p = plan()
            p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", f"walks {word}")
            self.assertIn("SCENE_PERIOD_CONFLICT", codes(pc.check(p, CHARS)), word)
        # period-true words stay allowed: a stone well or altar, a tent's wall, water still as glass, snow caps
        for words in ("pulls at a stone well", "leans on the goat-hair tent wall", "walks past the goat-hair wall",
                      "walks by water still as glass", "walks toward the snow caps of far mountains"):
            p = plan()
            p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", words)
            self.assertEqual(pc.check(p, CHARS)["problems"], [], words)

    def test_the_scan_takes_out_both_period_sentences(self):
        # a setting that names an excluded word itself (here "city") is not a conflict of every prompt
        p = plan()
        own = {"setting": "Enoch's city of tents on the plain.", "exclude": "No stone buildings or roads."}
        p["period"] = own
        for s in p["shots"]:
            s["prompt"] = s["prompt"].replace(PERIOD, f"{own['setting']} {own['exclude']}")
        self.assertEqual(pc.check(p, CHARS)["problems"], [])
        p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", "walks to the city")
        self.assertIn("SCENE_PERIOD_CONFLICT", codes(pc.check(p, CHARS)))

    def test_a_custom_period_with_no_avoid_uses_the_shared_list(self):
        per, problem = pc.resolve_period({"period": {"setting": "S.", "exclude": "E."}})
        self.assertIsNone(problem)
        self.assertEqual(per["avoid"], list(pc.PERIOD_AVOID))
        self.assertTrue(per["avoid"])
        self.assertEqual(pc.resolve_period({"period": {"setting": "S.", "exclude": "E.", "avoid": []}})[1].split()[0],
                         "PERIOD_INVALID")

    def test_an_invalid_period_is_refused_by_name_never_a_crash_nor_the_passage(self):
        p = plan()   # a passage that has a period: a malformed `period` is still refused, not passed over
        for bad in ("the stone age", {"setting": "x"}, {"setting": "", "exclude": "No roads."}, 7, None,
                    {"setting": "S.", "exclude": "E.", "avoid": ["(unclosed"]},
                    {"setting": "S.", "exclude": "E.", "avoid": "roads?"}):
            p["period"] = bad
            r = pc.check(p, CHARS)
            self.assertEqual(codes(r).count("PERIOD_INVALID"), 1, bad)
            self.assertNotIn("SCENE_PERIOD_MISSING", codes(r), bad)
        p["period"] = {"setting": "S.", "exclude": "E.", "avoid": ["(unclosed"]}
        self.assertIn("is not a regular expression", pc.check(p, CHARS)["problems"][0])

    def test_a_story_with_no_period_is_refused_once_until_the_plan_states_one(self):
        p = plan()
        p["passage"] = "Exodus 2:1-10 (KJV)"
        self.assertEqual(pc.check(p, CHARS)["problems"], [pc.missing_period(p)])   # one message, not one a shot
        del p["passage"]
        self.assertEqual(codes(pc.check(p, CHARS)), ["SCENE_PERIOD_MISSING"])
        nile = {"setting": "Ancient Egypt on the Nile: reed boats, reeds and the river.",
                "exclude": "No glass, modern clothing or roads."}
        p["period"] = nile
        self.assertIn("SCENE_PERIOD_MISSING", codes(pc.check(p, CHARS)))
        for s in p["shots"]:
            s["prompt"] = s["prompt"].replace(PERIOD, f"{nile['setting']} {nile['exclude']}")
        self.assertEqual(pc.check(p, CHARS)["problems"], [])

    def test_the_whole_passage_decides_and_one_across_the_flood_is_ambiguous(self):
        self.assertEqual(pc.passage_chapters("Genesis 6:5-13 (KJV)"), ("Genesis", 6, 6))
        self.assertEqual(pc.passage_chapters("Genesis 6:14-7:5"), ("Genesis", 6, 7))
        self.assertEqual(pc.passage_chapters("Genesis 6-8"), ("Genesis", 6, 8))
        self.assertEqual(pc.passage_chapters("Genesis 7"), ("Genesis", 7, 7))
        self.assertEqual(pc.period({"passage": "Genesis 6:14-22 (KJV)"}), pc.PERIODS["before-the-flood"])  # G8
        self.assertEqual(pc.period({"passage": "Genesis 7:11-24 (KJV)"}), pc.PERIODS["the-flood"])          # G9
        self.assertEqual(pc.period({"passage": "Genesis 8:1-9:17 (KJV)"}), pc.PERIODS["the-flood"])         # G10
        self.assertIn("Ararat", pc.PERIODS["the-flood"]["setting"])
        for passage in ("Genesis 6:9-7:24 (KJV)", "Genesis 6-8", "Genesis 3:1-4:8"):
            p = plan()
            p["passage"] = passage
            self.assertEqual(codes(pc.check(p, CHARS)), ["PERIOD_AMBIGUOUS"], passage)
            p["period"] = "before-the-flood"   # the plan settles it
            self.assertEqual(pc.check(p, CHARS)["problems"], [], passage)

    def test_the_build_refuses_a_scene_without_its_period_by_the_same_function(self):
        import episode_build as eb
        p = plan()
        self.assertIsNone(eb.period_refusal(p, p["shots"][1]))
        self.assertIsNone(eb.period_refusal(p, p["shots"][-1]))      # the Keeper
        p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace(SETTING, "")
        self.assertTrue(eb.period_refusal(p, p["shots"][1]).startswith("SCENE_PERIOD_MISSING s-a"))
        p = plan()
        p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("through the tents", "down a cobbled street")
        self.assertTrue(eb.period_refusal(p, p["shots"][1]).startswith("SCENE_PERIOD_CONFLICT s-a"))
        p = plan()
        p["passage"] = "Exodus 2"
        self.assertEqual(eb.period_refusal(p, p["shots"][1]), f"{pc.missing_period(p)} (shot s-a)")
        p["period"] = "nowhere"
        self.assertTrue(eb.period_refusal(p, p["shots"][1]).startswith("PERIOD_INVALID"))

    def test_the_long_plan_runs_the_same_helper(self):
        import long_plan_check as lc
        self.assertIs(lc.pc.plan_period_problems, pc.plan_period_problems)
        text = (HERE / "long_plan_check.py").read_text()
        self.assertIn("pc.plan_period_problems(plan, plan[\"shots\"])", text)
        arc = json.loads((HERE / "plans" / "arc-01-long.json").read_text())
        self.assertEqual(pc.plan_period_problems(arc, arc["shots"]), [])
        arc["shots"][0]["prompt"] = arc["shots"][0]["prompt"].replace(pc.PERIODS["eden"]["setting"], "")
        self.assertIn("SCENE_PERIOD_MISSING", [x.split()[0] for x in lc.check(arc)["problems"]])

    def test_genesis_7_states_its_period_in_every_scene_and_rewrites_only_the_anachronistic_shots(self):
        base = json.loads(subprocess.run(["git", "-C", str(HERE), "show",
                                          f"{PERIOD_BASE_COMMIT}:migration/production/bible/plans/genesis-07-short.json"],
                                         capture_output=True, text=True, check=True).stdout)
        now = json.loads(EXAMPLE.read_text())
        self.assertEqual(now["period"], "before-the-flood")
        r = pc.check(now)
        self.assertEqual((r["problems"], r["pending"]), ([], []))
        self.assertEqual({k: v for k, v in now.items() if k not in ("shots", "period")},
                         {k: v for k, v in base.items() if k != "shots"})
        tail = re.compile(r"\s*(No people, no text, no logos\.|No text, no logos\.)$")
        for a, b in zip(base["shots"], now["shots"]):
            self.assertEqual({k: v for k, v in b.items() if k != "prompt"}, {k: v for k, v in a.items() if k != "prompt"})
            if a["kind"] == "keeper":     # his three voice-over clips are kept by the resume (E93: the same request)
                self.assertEqual(b["prompt"], a["prompt"])
                continue
            self.assertIn(PERIOD, b["prompt"], b["id"])
            m = tail.search(a["prompt"])
            if b["id"] not in ANACHRONISTIC | REWORDED:   # the period inserted before the standard tail, nothing else
                self.assertEqual(b["prompt"], f"{a['prompt'][:m.start()]} {PERIOD} {m.group(1)}", b["id"])
            else:
                self.assertNotEqual(b["prompt"].replace(f" {PERIOD}", ""), a["prompt"], b["id"])
        shots = {s["id"]: s["prompt"] for s in now["shots"]}
        self.assertIn("small clay oil lamp", shots["s-walker"])
        self.assertIn("tents of the camp", shots["s-walker"])
        self.assertIn("hillside path above the camp of tents", shots["s-family"])
        self.assertIn("above the camp of dark goat-hair tents", shots["s-noah"])
        self.assertIn("Inside a quiet goat-hair tent at night", shots["s-scroll"])
        for sid, prompt in shots.items():
            for word in ("city", "lane", "room", "table", "road"):
                self.assertNotRegex(prompt.replace(EXCLUDE, ""), rf"\b{word}s?\b", sid)



class SceneWriting(unittest.TestCase):
    """E110 (review of genesis-07 run 40357197063): s-scroll asked for "an old scroll ... the ink lines catching the
    light" beside "No text", and Pavo drew legible Arabic-looking script. A scene prompt that asks for writing is
    refused; the negated "No text" and the Keeper's own scroll are not."""

    def test_a_scene_prompt_that_asks_for_writing_is_refused(self):
        for words in ("unrolls an old scroll, the ink lines catching the light", "reads the letters on a stone",
                      "traces an inscription on the altar", "holds a clay tablet", "writes on parchment",
                      "turns the pages of a book", "points at carved symbols", "studies a written list",
                      "looks at the script on the wall of the tent", "touches the runes"):
            p = plan()
            p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", words)
            self.assertIn("SCENE_WRITING", codes(pc.check(p, CHARS)), words)
        # God's voice-over and a speaking character's shot are scenes too
        p = plan()
        p["shots"][0]["prompt"] = p["shots"][0]["prompt"].replace("lightning inside them", "letters of fire inside them")
        self.assertEqual([x.split()[:4] for x in pc.check(p, CHARS)["problems"]],
                         [["SCENE_WRITING", "shot", "0", "g-open"]])

    def test_negations_a_carved_idol_and_the_keepers_scroll_stay_allowed(self):
        for words in ("walks past a carved clay idol", "walks on, no letters anywhere",
                      "walks through the tents without any visible writing"):
            p = plan()
            p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", words)
            self.assertNotIn("SCENE_WRITING", codes(pc.check(p, CHARS)), words)
        p = plan()
        self.assertIn("no text", p["shots"][0]["prompt"])          # every standard tail says "No text"
        k = p["shots"][-1]
        k["prompt"] = k["prompt"].replace("seated by a small campfire", "seated by a small campfire, holding an old "
                                          "rolled scroll in both hands")
        self.assertEqual(pc.writing_problems(len(p["shots"]) - 1, k), [])
        self.assertEqual(pc.check(p, CHARS)["problems"], [])

    def test_the_build_and_the_long_refuse_it_by_the_same_function(self):
        import episode_build as eb
        import long_plan_check as lc
        p = plan()
        self.assertIsNone(eb.writing_refusal(p["shots"][1]))
        p["shots"][1]["prompt"] = p["shots"][1]["prompt"].replace("walks through the tents", "unrolls an old scroll")
        self.assertTrue(eb.writing_refusal(p["shots"][1]).startswith("SCENE_WRITING s-a"))
        with self.assertRaises(SystemExit) as e:
            eb.request(p["shots"][1], 1, p, None, {})
        self.assertTrue(str(e.exception).startswith("SCENE_WRITING s-a"))
        self.assertIs(lc.pc.plan_writing_problems, pc.plan_writing_problems)
        self.assertIn("pc.plan_writing_problems(plan[\"shots\"])", (HERE / "long_plan_check.py").read_text())
        arc = json.loads((HERE / "plans" / "arc-01-long.json").read_text())
        self.assertEqual(pc.plan_writing_problems(arc["shots"]), [])   # its Keeper holds his scroll: not a scene
        i = next(n for n, s in enumerate(arc["shots"]) if s["kind"] == "scene")
        arc["shots"][i]["prompt"] = arc["shots"][i]["prompt"].replace(". ", ". An old scroll lies open. ", 1)
        self.assertIn("SCENE_WRITING", [x.split()[0] for x in lc.check(arc)["problems"]])

    def test_every_plan_is_free_of_writing_and_genesis_7_s_scroll_shows_none(self):
        for f in sorted((HERE / "plans").glob("*.json")):
            self.assertEqual(pc.plan_writing_problems(json.loads(f.read_text())["shots"]), [], f.name)
        shots = {s["id"]: s for s in json.loads(EXAMPLE.read_text())["shots"]}
        scroll = shots["s-scroll"]
        self.assertEqual(scroll["lines"], [6])
        self.assertIn("goat-hair door flap", scroll["prompt"])
        self.assertIn("clay oil lamp", scroll["prompt"])
        self.assertIn(PERIOD, scroll["prompt"])
        self.assertTrue(scroll["prompt"].startswith(shots["s-well"]["prompt"].split(" Medium shot")[0]))
        self.assertTrue(scroll["prompt"].endswith(f"{PERIOD} No text, no logos."))

# the long's plan (bible-long-plan-v1) and story QA v2/v3 run here too, so pr-checks.yml runs them unchanged
from test_long_plan_check import DraftArc1, Grammar as LongGrammar, NoRendererReadsTheNewQaYet, StoryQa  # noqa: E402,F401,E501

if __name__ == "__main__":
    unittest.main()
