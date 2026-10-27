#!/usr/bin/env python3
"""long_plan_check.py: a Bible-story long's shot plan (`bible-long-plan-v1`) is refused before any voice or Pavo call
when it misses the registered structure (structures/bible-story-long.json script.gate, the numbers script_check reads
too) or a row of the frozen story QA it will be measured against (qa_criteria_story_v3.json). Also: story QA v2 is v1
with only the caption rows replaced (owner, 2026-10-26: "Nova régua, sem legenda"), v3 is v2 with only the three
acted-long rows replaced ("Sim, régua nova"), and v1 and v2 stay byte-identical.

Runs in pr-checks through test_plan_check.py (which imports these cases), so no workflow changes."""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "migration" / "production"))
import long_plan_check as lc  # noqa: E402

DRAFT_PLAN = HERE / "plans" / "arc-01-long.json"
QA_V1 = ROOT / "migration" / "production" / "qa_criteria_story_v1.json"
QA_V2 = ROOT / "migration" / "production" / "qa_criteria_story_v2.json"
QA_V3 = ROOT / "migration" / "production" / "qa_criteria_story_v3.json"
QA_V1_SHA256 = "5dcf63f92fc716852096cefa8fd48f7498f4733eb1d347f4212a6f31a6c95360"   # main, frozen 2026-10-25
QA_V2_SHA256 = "72a12e231b9daa961f11709eae7004802b66c6cc1c99cf5927f07eb1051099c2"   # frozen 2026-10-26 (#418)


KEEPER_LOOK = "an elderly storyteller with a silver beard"
EVE_LOOK = "a woman of about twenty-five with long black hair"
NOAH_LOOK = "a strong elderly man with a grey beard"
CHARS = {
    "keeper": {"name": "The Keeper (series narrator)", "status": "APPROVED", "look": KEEPER_LOOK, "refs": ["front"],
               "voice": "am_michael", "wardrobe": {"fire": "seated by a small campfire"}},
    "eve": {"name": "Eve", "status": "APPROVED", "look": EVE_LOOK, "refs": ["full"], "voice": "af_heart"},
    "noah": {"name": "Noah", "status": "DRAFT", "look": NOAH_LOOK, "refs": [], "voice": "bm_george"},
}
ARCS = {"arc-x": {"id": "arc-x", "shorts": ["x-01-short", "x-02-short", "x-03-short", "x-04-short"],
                  "long": {"pilot": "pilot-099"}, "next": "arc-y"},
        "arc-y": {"id": "arc-y", "shorts": ["y-01-short"], "long": {"pilot": None}, "next": None}}
STYLE = "Painterly cinematic realism, cinema camera."
# 20 words: 7.27 s at the normal pace; two of them (+ gaps) are a 15.2 s block over three 5.1 s cuts
FILLER = "Ten generations after Eden the earth is full of people and noise, and nobody looks up at the sky."
QUESTION = "How did a very good world come to this, and who would be left standing when it ended?"
QUESTION2 = ("How did a very good world come to this so quickly, and who would still be left standing when it finally "
             "ended?")                                                  # 22 words
OPEN_LINE = "Why do you hide from the voice of the Lord in the garden, where you once walked?"   # 16 words
GOD_LINE = "The end of all flesh is come before me; for the earth is filled with violence"   # 15 words
KEEPER_12 = "This story is older than any city, and it still asks about us."   # 12 words


def keeper(sid, lines, beat):
    return {"id": sid, "kind": "keeper", "beat": beat, "lines": lines,
            "prompt": f"{STYLE} Medium close-up, static camera. The narrator, {KEEPER_LOOK}, seated by a small campfire, "
                      "holds his head level, looks straight into the camera and speaks to the camera. Night in the "
                      "desert, firelight. Warm and grave."}


def scene(sid, lines, beat="chapter", chapter=None, chars=("eve",), seconds=6, **extra):
    who = ", ".join({"eve": f"Eve, {EVE_LOOK}", "noah": f"Noah, {NOAH_LOOK}"}[c] for c in chars) \
        or "a crowd seen from behind"
    s = {"id": sid, "kind": "scene", "beat": beat, "lines": lines, "seconds": seconds, "characters": list(chars),
         "prompt": f"{STYLE} Wide shot, slow tracking shot. {who} walks through the tall grass. Dusk, low gold light. "
                   "Restless and alive."}
    if chapter:
        s["chapter"] = chapter
    if not chars and "establishing" not in extra:
        s["figures"] = "anonymous"
    s.update(extra)
    return s


class Builder:
    """A plan that passes at the real gate numbers: 4 chapters of 15.2 s blocks (two lines, three cuts)."""

    def __init__(self, blocks_per_chapter=14):
        self.narration, self.shots = [], []
        self.blocks_per_chapter = blocks_per_chapter

    def line(self, kind, text, **extra):
        self.narration.append(dict({"kind": kind, "text": text}, **extra))
        return len(self.narration) - 1

    def block(self, prefix, beat, chapter=None, last=FILLER, rehook=False, cuts=3, **extra):
        a = self.line("story", FILLER)
        b = self.line("story", last, **({"rehook": True} if rehook else {}))
        for k in range(cuts):
            self.shots.append(scene(f"{prefix}-{k}", [a, b], beat, chapter, **(extra if k == 0 else {})))

    def build(self):
        self.shots.append({"id": "s-open", "kind": "scene", "beat": "cold_open", "speaker": "eve", "line": OPEN_LINE,
                           "conflict": True, "characters": ["eve"],
                           "prompt": f"{STYLE} Medium close-up, slow push-in. Eve, {EVE_LOOK}, turns and speaks to him, "
                                     "her lips moving clearly with every word. A garden at dusk, low gold light. Tense."})
        self.block("s-cold", "cold_open")                                  # the cold open ends at ~28 s
        q = self.line("story", QUESTION2, rehook=True)
        self.shots += [scene(f"s-cold2-{k}", [q], "cold_open") for k in range(2)]
        self.shots.append(keeper("k-promise-1", [self.line("promise", KEEPER_12)], "keeper_promise"))
        self.shots.append(keeper("k-promise-2", [self.line("promise", KEEPER_12)], "keeper_promise"))
        for c, chap in enumerate(("c1", "c2", "c3", "c4")):
            for k in range(self.blocks_per_chapter):
                end = k == self.blocks_per_chapter - 1
                mid = k == self.blocks_per_chapter // 2
                if chap == "c4" and k == 3:
                    self.shots.append({"id": "s-god", "kind": "scene", "beat": "chapter", "chapter": "c4",
                                       "speaker": "god", "line": GOD_LINE, "reference": "Genesis 6:13 (KJV)",
                                       "seconds": 8, "characters": [],
                                       "prompt": f"{STYLE} Extreme wide shot, slow push-in. Black storm clouds roll "
                                                 "over the plain, lightning inside them. Dusk, a hard wind. Ominous. "
                                                 "No people, no text, no logos."})
                    self.block(f"s-{chap}-{k}", "chapter", chap, climax=True)
                    continue
                beat = "payoff" if chap == "c4" and end else "chapter"
                self.block(f"s-{chap}-{k}", beat, chap, last=QUESTION if (end and chap != "c4") or mid else FILLER,
                           rehook=(end and chap != "c4") or mid)
        insight = ("Notice the order. Grief comes before judgment, and grace before the flood.",   # 12 words
                   "This story is older than any city, and it still asks about us.")
        for k in range(6):
            self.shots.append(keeper(f"k-insight-{k}", [self.line("insight", insight[k % 2] if k else KEEPER_12)],
                                     "keeper_insight"))
        self.shots.append(keeper("k-close-1", [self.line("cta", "Would you have walked against the crowd? Tell me "
                                                         "in the comments.")], "keeper_close"))
        self.shots.append(keeper("k-close-2", [self.line("cta", "Next on the channel, the full story of Noah and the "
                                                         "flood.")], "keeper_close"))
        return {"version": "bible-long-plan-v1", "long": "arc-x-long", "arc": "arc-x", "pilot": "pilot-099",
                "aspect_ratio": "16:9", "burned_captions": False,
                "chapters": [{"id": f"c{k + 1}", "short": s, "title": f"Chapter {k + 1}"}
                             for k, s in enumerate(ARCS["arc-x"]["shorts"])],
                "narration": self.narration, "shots": self.shots}


# E108 (review of #426): the long's scene prompts state their period too (plan_check.plan_period_problems)
PERIOD = f"{lc.pc.PERIODS['eden']['setting']} {lc.pc.PERIODS['eden']['exclude']}"


def with_period(p):
    p["period"] = "eden"
    for s in p["shots"]:
        if s.get("kind") == "scene" and isinstance(s.get("prompt"), str) and PERIOD not in s["prompt"]:
            s["prompt"] = f"{s['prompt'].rstrip()} {PERIOD}"
    return p


def plan(**kw):
    return with_period(Builder(**kw).build())


def check(p, **kw):
    kw.setdefault("chars", CHARS)
    kw.setdefault("arc_table", ARCS)
    return lc.check(p, **kw)


def codes(result, key="problems"):
    return [x.split()[0] for x in result[key]]


def insert_line(p, at, line):
    """Insert a narration line at index `at`, every shot's later line indices shifted: the new line's index."""
    p["narration"].insert(at, line)
    for s in p["shots"]:
        if s.get("lines"):
            s["lines"] = [k + 1 if k >= at else k for k in s["lines"]]
    return at


def remove_line(p, at):
    """Remove narration line `at`, every shot's later line indices shifted down."""
    del p["narration"][at]
    for s in p["shots"]:
        if s.get("lines"):
            s["lines"] = [k - 1 if k > at else k for k in s["lines"]]


def shot(p, sid):
    return next(s for s in p["shots"] if s["id"] == sid)


class Grammar(unittest.TestCase):
    def test_the_builder_plan_passes_at_the_real_gate(self):
        r = check(plan())
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["pending"], [])
        e = r["estimate"]
        self.assertTrue(14 <= e["minutes"] <= 18, e)
        self.assertTrue(0.6 <= e["climax_at"] <= 0.85, e)
        self.assertGreaterEqual(e["rehooks"], 6)
        self.assertLessEqual(e["keeper_share"], 0.25)

    def test_against_v2_the_acted_long_rows_are_pending_owner_rows_and_v3_checks_them(self):
        # story v2 = v1 apart from captions: no figure on screen, >= 40 % real licensed footage, <= 55 % Pavo, and a
        # 4-7 s title card first; an acted long meets none of them, so they are the owner's (pending), never decided
        r = check(plan(), criteria=lc.qa(QA_V2))
        self.assertEqual(r["problems"], [])
        found = codes(r, "pending")
        for row in ("QA_CONFLICT_FIGURES", "QA_CONFLICT_REAL_FOOTAGE", "QA_CONFLICT_AI_SHARE", "QA_CONFLICT_TITLE_CARD"):
            self.assertIn(row, found)
        # owner, 2026-10-26 "Sim, régua nova": v3 replaces those rows with the structure's, and checks them
        r = check(plan())
        self.assertEqual((r["problems"], r["pending"]), ([], []))

    def test_each_line_is_timed_at_its_own_voices_measured_pace(self):
        # measured 2026-10-26 (arc-1 voiced locally): Eve 3.73 words/s, Adam 3.98, the narrator 2.87; at the Short's
        # single 2.75 a 12-word line of Eve's looked like 4.4 s, and it is 3.2 s: under the 4 s a talking clip fills
        self.assertGreater(lc.VOICE_PACE["eve"], lc.VOICE_PACE["keeper"] * 1.25)
        self.assertGreater(lc.VOICE_PACE["adam"], lc.VOICE_PACE["keeper"] * 1.25)
        p = plan()
        p["shots"][0]["line"] = "Why do you hide from the voice of the Lord in the garden?"   # 12 words
        found = codes(check(p))
        self.assertTrue({"TALK_LINE_UNREACHABLE", "HOLD_UNDER_QA", "SPEAKER_LINE_TOO_SHORT"} & set(found), found)
        # and the long breathes 0.6 s between lines (the QA's 165 words a minute ceiling)
        self.assertEqual(lc.LONG_LINE_GAP, 0.6)

    def test_v3_every_talking_clip_is_judged_on_a_human_face(self):
        # lipsync_check reads a human face and lips: a talking serpent fails every generation (FACE_NOT_FOUND)
        chars = dict(CHARS, serpent={"name": "The serpent", "status": "APPROVED", "look": "a slender green serpent",
                                     "refs": ["full"], "voice": "bm_fable", "pronoun": "its"})
        p = plan()
        s = p["shots"][0]
        s.update(speaker="serpent", characters=["serpent"],
                 prompt=s["prompt"].replace(f"Eve, {EVE_LOOK}", "The serpent, a slender green serpent"))
        self.assertIn("TALKING_WITHOUT_A_FACE", codes(check(p, chars=chars)))

    # ---- review of #418 (2026-10-26)
    def test_review_1_the_cold_open_is_at_most_30_s_on_its_own(self):
        self.assertLessEqual(check(plan())["estimate"]["beats_s"]["cold_open"], 30.0)
        # a ~43 s cold open with a short promise (over by 50 s), and one with no promise at all, are refused
        p = plan()
        k2 = shot(p, "k-promise-2")
        remove_line(p, k2["lines"][0])
        p["shots"].remove(k2)
        i = next(k for k, s in enumerate(p["shots"]) if s["beat"] == "keeper_promise")
        a = insert_line(p, p["shots"][i]["lines"][0], {"kind": "story", "text": FILLER})
        insert_line(p, a + 1, {"kind": "story", "text": FILLER})
        p["shots"][i:i] = [scene(f"s-late-{k}", [a, a + 1], "cold_open") for k in range(3)]
        r = check(p)
        self.assertLessEqual(r["estimate"]["beats_s"]["keeper_promise"] + 30, 50)
        self.assertIn("COLD_OPEN_LENGTH", codes(r))
        k1 = shot(p, "k-promise-1")
        remove_line(p, k1["lines"][0])
        p["shots"].remove(k1)
        self.assertIn("COLD_OPEN_LENGTH", codes(check(p)))

    def test_review_1_the_keeper_starts_at_30_s_after_a_shorter_cold_open(self):
        # the build holds the cold open's last frame (under the music) until 30 s: the Keeper never starts before it
        r = check(plan())
        self.assertNotIn("KEEPER_IN_COLD_OPEN", codes(r))
        self.assertLess(r["estimate"]["cold_open_voice_s"], 30.0)
        self.assertGreaterEqual(r["estimate"]["beats_s"]["cold_open"], 30.0 - 1e-6)
        # but a cold open that leaves more than COLD_OPEN_HOLD_MAX of held frame before the Keeper is too short
        p = plan()
        for k in shot(p, "s-cold-0")["lines"]:
            p["narration"][k]["text"] = "It was quiet."
        self.assertIn("COLD_OPEN_SHORT", codes(check(p)))

    def test_a_voiceover_keeper_is_refused_in_the_long_until_it_has_its_own_path(self):
        p = plan()
        k = next(s for s in p["shots"] if s["kind"] == "keeper")
        k["voiceover"] = True
        self.assertIn("LONG_VOICEOVER_UNSUPPORTED", codes(check(p)))
        self.assertNotIn("LONG_VOICEOVER_UNSUPPORTED", codes(check(plan())))

    def test_review_2_keeper_prompts_pass_the_prompt_rules_too(self):
        p = plan()
        s = shot(p, "k-insight-1")
        s["prompt"] = s["prompt"].replace("Medium close-up, static camera. ", "")
        found = codes(check(p))
        self.assertIn("PROMPT_NO_CINEMATOGRAPHY", found)
        p = plan()
        s = shot(p, "k-insight-1")
        s["prompt"] += " Behind him God stands with open hands."
        self.assertIn("GOD_AS_A_FIGURE", codes(check(p)))
        p = plan()
        shot(p, "k-insight-1")["prompt"] = "Static camera. The narrator speaks."
        self.assertIn("PROMPT_LENGTH", codes(check(p)))

    def test_review_5_a_faceless_speaker_is_refused_under_any_qa(self):
        chars = dict(CHARS, serpent={"name": "The serpent", "status": "APPROVED", "look": "a slender green serpent",
                                     "refs": ["full"], "voice": "bm_fable", "pronoun": "its"})
        p = plan()
        s = p["shots"][0]
        s.update(speaker="serpent", characters=["serpent"],
                 prompt=s["prompt"].replace(f"Eve, {EVE_LOOK}", "The serpent, a slender green serpent"))
        self.assertIn("TALKING_WITHOUT_A_FACE", codes(check(p, chars=chars, criteria=lc.qa(QA_V2))))

    def test_review_6_character_entries_without_refs_or_look_are_refused_not_crashed(self):
        chars = dict(CHARS, keeper=dict(CHARS["keeper"], refs=[]))
        r = check(plan(), chars=chars)
        self.assertIn("KEEPER_NO_REFS", codes(r))
        self.assertNotIn("CHARACTER_PENDING", codes(r, "pending"))
        chars = dict(CHARS, eve={k: v for k, v in CHARS["eve"].items() if k != "look"})
        self.assertIn("CHARACTER_NO_LOOK", codes(check(plan(), chars=chars)))
        chars = dict(CHARS, keeper={k: v for k, v in CHARS["keeper"].items() if k != "look"})
        self.assertIn("CHARACTER_NO_LOOK", codes(check(plan(), chars=chars)))
        chars = dict(CHARS, eve=dict(CHARS["eve"], refs=[]))
        self.assertIn("CHARACTER_NO_REFS", codes(check(plan(), chars=chars)))

    def test_review_7_a_rehook_on_a_silent_shot_is_refused(self):
        p = plan()
        shot(p, "s-c1-2-1")["rehook"] = True
        self.assertIn("REHOOK_ON_SILENT_SHOT", codes(check(p)))

    def test_review_8_words_only_over_landscape_are_refused(self):
        p = plan()
        for s in p["shots"]:
            if s["id"].startswith("s-c2-4-"):
                s.update(characters=[], establishing=True)
                s.pop("figures", None)
                s["prompt"] = (f"{STYLE} Extreme wide establishing shot, slow crane down. A dry plain under heavy "
                               "clouds. Dusk. Vast and empty. No people, no text, no logos.")
        self.assertIn("ESTABLISHING_ONLY", codes(check(p)))

    def test_review_9_the_long_id_is_its_arc(self):
        p = plan()
        p["long"] = "arc-y-long"
        self.assertIn("LONG_ID", codes(check(p)))

    def test_the_numbers_are_the_structure_gate_that_script_check_reads(self):
        import script_check
        self.assertEqual(lc.gate(), script_check.story_gate())
        p = plan()
        g = dict(lc.gate(), length_min=[20, 30])
        self.assertIn("LONG_LENGTH", codes(check(p, gate_values=g)))

    def test_the_gate_and_the_beat_map_agree(self):
        s = json.loads(lc.STRUCTURE.read_text())["script"]
        beats = {b["beat"]: b for b in s["beats"]}
        g = s["gate"]
        self.assertEqual(g["length_min"], s["length_min"])
        self.assertEqual(g["cold_open_s"], beats["cold_open"]["at_s"][1])
        self.assertEqual(g["keeper_promise_max_s"], beats["keeper_promise"]["at_s"][1] - beats["keeper_promise"]["at_s"][0])
        self.assertEqual(g["keeper_insight_max_s"], beats["keeper_insight"]["max_s"])
        self.assertEqual(g["keeper_close_max_s"], beats["keeper_close"]["max_s"])
        self.assertEqual(g["climax_at"], beats["climax"]["at"])
        self.assertIn("longer than 20 s", " ".join(s["retention"]))
        self.assertEqual(g["slow_stretch_max_s"], 20)

    def test_a_long_is_16_9_with_no_burned_captions(self):
        p = plan()
        p["aspect_ratio"] = "9:16"
        p["burned_captions"] = True
        found = codes(check(p))
        self.assertIn("ASPECT_RATIO", found)
        self.assertIn("BURNED_CAPTIONS", found)

    def test_the_cold_open_is_acted_and_spoken_never_the_keeper(self):
        p = plan()
        p["shots"][0]["conflict"] = False
        self.assertIn("COLD_OPEN_CONFLICT", codes(check(p)))
        p = plan()
        k = keeper("k-early", [p["shots"][1]["lines"][0]], "cold_open")
        p["shots"][1] = k
        found = codes(check(p))
        self.assertIn("KEEPER_IN_COLD_OPEN", found)
        # a cold open over 30 s: three more cuts of a 15.2 s block before the promise
        p = plan()
        i = next(k for k, s in enumerate(p["shots"]) if s["beat"] == "keeper_promise")
        a = insert_line(p, p["shots"][i]["lines"][0], {"kind": "story", "text": FILLER})
        insert_line(p, a + 1, {"kind": "story", "text": FILLER})
        p["shots"][i:i] = [scene(f"s-late-{k}", [a, a + 1], "cold_open") for k in range(3)]
        self.assertIn("COLD_OPEN_LENGTH", codes(check(p)))

    def test_the_cold_open_ends_on_an_open_question(self):
        p = plan()
        last = [s for s in p["shots"] if s["beat"] == "cold_open"][-1]
        p["narration"][last["lines"][-1]]["text"] = FILLER
        self.assertIn("COLD_OPEN_NO_QUESTION", codes(check(p)))

    def test_the_keeper_promise_is_on_screen_and_at_most_20_s(self):
        p = plan()
        i = next(k for k, s in enumerate(p["shots"]) if s["beat"] == "keeper_promise")
        for k in range(3):
            n = insert_line(p, p["shots"][i]["lines"][0], {"kind": "promise", "text": KEEPER_12})
            p["shots"].insert(i, keeper(f"k-promise-x{k}", [n], "keeper_promise"))
        found = codes(check(p))
        self.assertIn("KEEPER_PROMISE_LENGTH", found)

    def test_re_hooks_count_spacing_and_every_chapter_end(self):
        p = plan()
        for x in p["narration"]:
            x.pop("rehook", None)
        found = codes(check(p))
        self.assertIn("REHOOKS", found)
        self.assertIn("CHAPTER_END_NO_REHOOK", found)
        self.assertIn("REHOOK_GAP", found)

    def test_one_acted_climax_at_0_6_to_0_85_on_a_kjv_line(self):
        p = plan()
        shot(p, "s-c2-3-0")["climax"] = True
        self.assertIn("CLIMAX_COUNT", codes(check(p)))
        p = plan()
        shot(p, "s-c4-3-0").pop("climax")
        shot(p, "s-c1-3-0")["climax"] = True
        self.assertIn("CLIMAX_POSITION", codes(check(p)))
        p = plan()
        p["shots"].remove(shot(p, "s-god"))
        self.assertIn("CLIMAX_NO_KJV_LINE", codes(check(p)))
        p = plan()
        shot(p, "s-c4-3-0").pop("climax")
        shot(p, "s-god")["climax"] = True
        self.assertIn("CLIMAX_NOT_ACTED", codes(check(p)))

    def test_the_payoff_follows_the_climax(self):
        p = plan()
        for s in p["shots"]:
            if s.get("beat") == "payoff":
                s["beat"] = "chapter"
        self.assertIn("PAYOFF_MISSING", codes(check(p)))

    def test_the_keeper_insight_and_close_limits(self):
        p = plan()
        i = next(k for k, s in enumerate(p["shots"]) if s["beat"] == "keeper_close")
        for k in range(23):
            n = insert_line(p, p["shots"][i + k]["lines"][0], {"kind": "insight", "text": KEEPER_12})
            p["shots"].insert(i + k, keeper(f"k-more-{k}", [n], "keeper_insight"))
        found = codes(check(p))
        self.assertIn("KEEPER_INSIGHT_LENGTH", found)
        p = plan()
        for k in range(6):
            p["narration"].append({"kind": "cta", "text": KEEPER_12})
            p["shots"].append(keeper(f"k-close-x{k}", [len(p["narration"]) - 1], "keeper_close"))
        self.assertIn("KEEPER_CLOSE_LENGTH", codes(check(p)))
        p = plan()
        p["narration"][shot(p, "k-close-1")["lines"][0]]["text"] = "Walk against the crowd, and tell me about it in the comments."
        self.assertIn("CLOSE_NO_QUESTION", codes(check(p)))

    def test_the_keeper_share_is_at_most_a_quarter(self):
        g = dict(lc.gate(), keeper_share_max=0.05)
        self.assertIn("KEEPER_SHARE", codes(check(plan(), gate_values=g)))

    def test_no_stretch_without_people_over_20_s(self):
        p = plan()
        for s in p["shots"]:
            if s["id"].startswith(("s-c2-4-", "s-c2-5-")):
                s.update(characters=[], establishing=True)
                s.pop("figures", None)
                s["prompt"] = (f"{STYLE} Extreme wide establishing shot, slow crane down. A dry plain under heavy "
                               "clouds. Dusk. Vast and empty. No people, no text, no logos.")
        self.assertIn("SLOW_STRETCH", codes(check(p)))

    def test_every_cut_is_a_4_to_7_s_hold_of_the_frozen_qa(self):
        p = plan()
        s = shot(p, "s-c1-0-0")
        p["shots"].insert(p["shots"].index(s), dict(copy.deepcopy(s), id="s-c1-0-x"))
        self.assertIn("HOLD_UNDER_QA", codes(check(p)))   # four cuts of 3.8 s
        p = plan()
        p["shots"].remove(shot(p, "s-c1-0-2"))
        self.assertIn("HOLD_OVER_QA", codes(check(p)))    # two cuts of 7.6 s

    def test_draft_characters_are_pending_with_their_look_word_for_word(self):
        p = plan()
        s = shot(p, "s-c4-12-1")
        s["characters"] = ["noah"]
        s["prompt"] = s["prompt"].replace(f"Eve, {EVE_LOOK}", f"Noah, {NOAH_LOOK}")
        r = check(p)
        self.assertEqual(r["problems"], [])
        self.assertEqual(codes(r, "pending"), ["CHARACTER_PENDING"])
        s["prompt"] = s["prompt"].replace(NOAH_LOOK, "an old man")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(check(p)))
        s["characters"] = ["cain"]
        self.assertIn("CHARACTER_UNKNOWN", codes(check(p)))

    def test_a_named_character_is_listed_so_the_references_go_in(self):
        p = plan()
        s = shot(p, "s-c2-1-1")
        s["prompt"] = s["prompt"].replace("walks through the tall grass", "walks toward Noah through the tall grass")
        self.assertIn("CHARACTER_NOT_LISTED", codes(check(p)))

    def test_a_window_reuses_a_clip_never_next_to_it(self):
        p = plan()
        base = shot(p, "s-c1-1-0")
        w = shot(p, "s-c1-1-2")
        for k in ("prompt", "seconds", "characters"):
            w.pop(k)
        w["window_of"] = base["id"]
        base["seconds"] = 8                       # two ~5.1 s holds of one 8 s clip (slowed 1.3 at most)
        r = check(p)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["estimate"]["generations"]["windows"], 1)
        w["window_of"] = "s-c1-1-1"
        self.assertIn("WINDOW_ADJACENT", codes(check(p)))
        w["window_of"] = base["id"]
        base["seconds"] = 4
        self.assertIn("FOOTAGE_SHORT", codes(check(p)))

    def test_the_second_person_hook_of_the_frozen_qa(self):
        p = plan()
        p["shots"][0]["line"] = "Why do they hide from the voice of the Lord in the garden?"
        self.assertIn("HOOK_SECOND_PERSON", codes(check(p)))

    def test_chapters_are_the_arcs_shorts_or_an_owner_row(self):
        p = plan()
        p["chapters"][3]["short"] = "z-09-short"
        r = check(p)
        self.assertEqual(r["problems"], [])
        self.assertIn("ARC_SHORTS", codes(r, "pending"))
        p["arc"] = "arc-q"
        self.assertIn("ARC_UNKNOWN", codes(check(p)))

    def test_strict_cli_fails_on_a_pending_row(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(json.dumps(plan()))
            cli = [sys.executable, str(HERE / "long_plan_check.py"), str(f)]
            # the builder's cast is not the real character bible: CHARACTER_UNKNOWN etc. are problems (exit 1)
            run = subprocess.run(cli, capture_output=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn(b'"problems"', run.stdout)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(DRAFT_PLAN.read_text())
            # the arc-1 draft: no problem and no pending row, so it passes even --strict (what the build runs)
            self.assertEqual(subprocess.run([sys.executable, str(HERE / "long_plan_check.py"), str(f), "--strict"],
                                            capture_output=True).returncode, 0)
            p = json.loads(DRAFT_PLAN.read_text())
            p["shots"][1]["characters"] = ["noah"]          # a DRAFT character: a pending row, so --strict fails
            f.write_text(json.dumps(p))
            self.assertEqual(subprocess.run([sys.executable, str(HERE / "long_plan_check.py"), str(f), "--strict"],
                                            capture_output=True).returncode, 1)


class DraftArc1(unittest.TestCase):
    def test_the_arc_1_draft_is_arcs_json_arc_01_and_passes_strict(self):
        # owner, 2026-10-26: the long follows arcs.json, arc-01 = Genesis 1-3 = Shorts 1-4, one complete story, with
        # Adam, Eve, the serpent (silent: the Keeper narrates its lines) and God; no Cain or Abel
        p = json.loads(DRAFT_PLAN.read_text())
        r = lc.check(p)
        self.assertEqual((r["problems"], r["pending"]), ([], []))
        self.assertTrue(14 <= r["estimate"]["minutes"] <= 18, r["estimate"])
        arc = lc.arcs()["arc-01"]
        self.assertEqual([c["short"] for c in p["chapters"]], arc["shorts"])
        self.assertEqual((p["arc"], p["pilot"]), ("arc-01", arc["long"]["pilot"]))
        cast = {c for s in p["shots"] for c in s.get("characters", [])}
        self.assertEqual(cast, {"adam", "eve", "serpent"})
        speakers = {s["speaker"] for s in p["shots"] if s.get("speaker")}
        self.assertEqual(speakers, {"adam", "eve", "god"})


class StoryQa(unittest.TestCase):
    def test_v1_stays_byte_identical_to_main(self):
        self.assertEqual(hashlib.sha256(QA_V1.read_bytes()).hexdigest(), QA_V1_SHA256)

    def test_v2_stays_byte_identical(self):
        self.assertEqual(hashlib.sha256(QA_V2.read_bytes()).hexdigest(), QA_V2_SHA256)

    def test_v3_is_the_file_the_long_is_checked_against(self):
        self.assertEqual(hashlib.sha256(QA_V3.read_bytes()).hexdigest(), lc.QA_SHA256)
        self.assertEqual(lc.QA, QA_V3)
        self.assertIsNone(lc.frozen_qa_problem())

    def test_v3_points_to_the_owners_decision_which_quotes_the_rows(self):
        # review of #418, point 4: v3 relaxes three v2 rows by the owner's explicit decision of 2026-10-26
        entry = "Owner decision: story QA v3 for the acted Bible long; the long follows arcs.json (2026-10-26)"
        self.assertIn(entry, json.loads(QA_V3.read_text())["basis"])
        decisions = (ROOT / "migration" / "strategy" / "DECISIONS.md").read_text()
        section = decisions.split("## " + entry, 1)[1].split("\n## ", 1)[0]
        self.assertIn('"Sim, régua nova"', section)
        for row in ("title_card_seconds", "figure_present_fraction_max", "footage_picture_share_min",
                    "footage_picture_share_counts", "ai_video_picture_share_max", "first_shot", "figures_allowed",
                    "ai_video_clip_checks"):
            self.assertIn(f"`{row}`", section, row)

    def test_v3_differs_from_v2_only_in_the_three_acted_long_rows(self):
        v2, v3 = json.loads(QA_V2.read_text()), json.loads(QA_V3.read_text())
        meta = {"version", "frozen_at_utc", "basis"}
        self.assertEqual(set(v2) - meta, set(v3) - meta)
        for k in set(v2) - meta - {"grammar"}:
            self.assertEqual(v2[k], v3[k], k)        # audio, loudness, pace, rights, the review: unchanged
        old = {"title_card_seconds", "figure_present_fraction_max", "footage_picture_share_min",
               "footage_picture_share_counts", "ai_video_picture_share_max"}
        new = {"first_shot", "figures_allowed", "ai_video_picture_share_max", "ai_video_clip_checks"}
        g2, g3 = v2["grammar"], v3["grammar"]
        self.assertEqual(set(g2) - old, set(g3) - new)
        for k in set(g2) - old:
            self.assertEqual(g2[k], g3[k], k)        # 4-7 s holds, the .srt track, ... unchanged
        self.assertEqual(g3["ai_video_picture_share_max"], 1.0)
        self.assertIn("lipsync_check", g3["ai_video_clip_checks"])
        self.assertIn("clip_check", g3["ai_video_clip_checks"])
        self.assertIn("APPROVED", g3["figures_allowed"])
        self.assertIn("cold-open", g3["first_shot"])
        self.assertEqual((v2["version"], v3["version"]), ("story-qa-criteria-v2", "story-qa-criteria-v3"))
        self.assertEqual(v3["perceptual_review_required_before_approval"], v2["perceptual_review_required_before_approval"])
        self.assertTrue(v3["frozen_before_first_story_render"])

    def test_v2_differs_from_v1_only_in_the_caption_rows(self):
        v1, v2 = json.loads(QA_V1.read_text()), json.loads(QA_V2.read_text())
        meta = {"version", "frozen_at_utc", "basis"}
        self.assertEqual(set(v1) - meta, set(v2) - meta)
        for k in set(v1) - meta - {"grammar"}:
            self.assertEqual(v1[k], v2[k], k)
        old = {"caption_coverage_of_speech_min", "caption_hold_seconds_median", "caption_chars_max",
               "caption_words_max", "caption_box"}
        new = {"burned_captions", "caption_track", "srt_coverage_of_speech_min", "srt_cue_seconds_median",
               "srt_cue_chars_max", "srt_cue_words_max"}
        g1, g2 = v1["grammar"], v2["grammar"]
        self.assertEqual(set(g1) - old, set(g2) - new)
        for k in set(g1) - old:
            self.assertEqual(g1[k], g2[k], k)
        # the same numbers, now on the .srt track: nothing loosened
        self.assertEqual(g2["srt_coverage_of_speech_min"], g1["caption_coverage_of_speech_min"])
        self.assertEqual(g2["srt_cue_seconds_median"], g1["caption_hold_seconds_median"])
        self.assertEqual(g2["srt_cue_chars_max"], g1["caption_chars_max"])
        self.assertEqual(g2["srt_cue_words_max"], g1["caption_words_max"])
        self.assertIs(g2["burned_captions"], False)
        self.assertEqual((v1["version"], v2["version"]), ("story-qa-criteria-v1", "story-qa-criteria-v2"))
        self.assertTrue(v2["frozen_before_first_story_render"])


class NoRendererReadsTheNewQaYet(unittest.TestCase):
    """Review of #418, point 3: story QA v2/v3 rename keys that qa_pilot.py and prepublish_gate.py index directly
    (caption_coverage_of_speech_min, figure_present_fraction_max, footage_picture_share_min, title_card_seconds), and
    prepublish_gate knows only story-qa-criteria-v1. Until a reader handles the new keys (slice 3), nothing that
    renders, measures or gates a video may point at v2 or v3: this fails the PR that wires one in too early."""
    NEW = re.compile(r"story-qa-criteria-v[23]|qa_criteria_story_v[23]")
    # test_refusal_parity reads v3's row names only to require each one mapped to its earlier check (E106); it
    # measures and gates nothing
    ALLOWED = {"migration/production/bible/long_plan_check.py", "migration/production/bible/test_long_plan_check.py",
               "migration/ops/test_refusal_parity.py"}

    def readers(self):
        for pattern in ("migration/**/*.py", "migration/**/*.sh", ".github/workflows/*.yml"):
            for path in ROOT.glob(pattern):
                rel = path.relative_to(ROOT).as_posix()
                if "/evidence/" in rel or rel in self.ALLOWED:
                    continue
                yield rel, path.read_text(errors="replace")

    def test_no_renderer_or_gate_points_at_story_qa_v2_or_v3_before_it_reads_their_keys(self):
        qa_pilot = (ROOT / "migration" / "production" / "qa_pilot.py").read_text()
        gate = (ROOT / "migration" / "publish" / "prepublish_gate.py").read_text()
        ready = all(k in qa_pilot for k in ("srt_coverage_of_speech_min", "figures_allowed", "first_shot")) and \
            "story-qa-criteria-v3" in gate
        early = [rel for rel, text in self.readers() if self.NEW.search(text)]
        if not ready:
            self.assertEqual(early, [], "story QA v2/v3 referenced before qa_pilot/prepublish_gate can read them "
                                        "(LONG_DESIGN.md, build blocker)")

    def test_the_readers_still_index_the_v1_keys(self):
        # the gap this guards: the keys v2/v3 removed are read directly today
        qa_pilot = (ROOT / "migration" / "production" / "qa_pilot.py").read_text()
        self.assertIn('g["caption_coverage_of_speech_min"]', qa_pilot)
        self.assertIn('g["footage_picture_share_min"]', qa_pilot)
        self.assertNotIn("story-qa-criteria-v3", (ROOT / "migration" / "publish" / "prepublish_gate.py").read_text())


if __name__ == "__main__":
    unittest.main()
