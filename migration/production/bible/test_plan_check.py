#!/usr/bin/env python3
"""plan_check.py: a Short's plan is refused before any voice or Pavo call when it breaks the Keeper + acted-scenes
rules (DECISIONS.md 2026-10-26) or the part-6 Short rules."""
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
    "keeper": {"status": "APPROVED", "look": KEEPER_LOOK, "refs": ["front"],
               "wardrobe": {"fire": "seated by a small campfire"}},
    "eve": {"status": "APPROVED", "look": EVE_LOOK, "refs": ["full"]},
    "adam": {"status": "DRAFT", "look": "a man of about thirty", "refs": []},
}
STYLE = "Painterly cinematic realism, cinema camera."


def keeper(sid, lines):
    return {"id": sid, "kind": "keeper", "lines": lines,
            "prompt": f"{STYLE} Medium close-up, slow push-in. The narrator, {KEEPER_LOOK}, seated by a small campfire, "
                      "speaks to the camera. Night in the desert, firelight. Warm and grave."}


def scene(sid, lines, chars=(), seconds=8, look=None, **extra):
    who = look if look is not None else ", ".join({"eve": EVE_LOOK}.get(c, c) for c in chars) or "a crowd seen from behind"
    s = {"id": sid, "kind": "scene", "lines": lines, "seconds": seconds, "characters": list(chars),
         "prompt": f"{STYLE} Wide shot, slow tracking shot. {who} walks through the tents. Dusk, torchlight. Restless."}
    if not chars and "establishing" not in extra:
        s["figures"] = "anonymous"
    s.update(extra)
    return s


def plan(shots=None, narration=None):
    narration = narration or [
        {"kind": "story", "text": "There is a verse where God's heart breaks, and it is about us."},
        {"kind": "story", "text": " ".join(["Ten generations after Eden the earth is full of people and noise."] * 3)},
        {"kind": "scripture", "reference": "Genesis 6:5 (KJV)", "text": "And God saw that the wickedness of man was "
         "great in the earth, and that every imagination of the thoughts of his heart was only evil continually."},
        {"kind": "story", "text": " ".join(["Not some thoughts, every one, only evil, all the time, every day."] * 6)},
        {"kind": "insight", "text": "Notice the order. Grief comes before judgment. The flood is not the story of a "
         "cold God, but of a wounded heart."},
        {"kind": "cta", "text": "The full story is in the long video. Part eight tomorrow."},
    ]
    shots = shots or [keeper("k-open", [0]), scene("s-a", [1]), scene("s-b", [1]), scene("s-c", [2]),
                      scene("s-d", [2], ["eve"]), scene("s-e", [3], seconds=10), scene("s-f", [3], seconds=10), scene("s-g", [3], seconds=10),
                      keeper("k-insight", [4]), keeper("k-close", [5])]
    return {"version": "bible-plan-v1", "episode": "genesis-07-short", "part": 7, "aspect_ratio": "9:16",
            "narration": narration, "shots": shots}


def codes(result):
    return [p.split()[0] for p in result["problems"]]


class Plan(unittest.TestCase):
    def test_the_fixture_plan_passes(self):
        r = pc.check(plan(), CHARS)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["pending"], [])
        self.assertTrue(62 <= r["estimate"]["seconds"] <= 90, r["estimate"])

    def test_the_genesis_7_example_passes_against_the_real_character_bible(self):
        r = pc.check(json.loads(EXAMPLE.read_text()))
        self.assertEqual(r["problems"], [])
        keeper_status = pc.ch.registry()["keeper"]["status"]
        self.assertEqual(r["pending"], [] if keeper_status == "APPROVED" else r["pending"][:1])

    def test_an_unapproved_character_is_refused(self):
        p = plan()
        p["shots"][4] = scene("s-d", [2], ["adam"], look="a man of about thirty")
        self.assertIn("CHARACTER_NOT_APPROVED", codes(pc.check(p, CHARS)))

    def test_a_look_that_is_not_word_for_word_is_refused(self):
        p = plan()
        p["shots"][4] = scene("s-d", [2], ["eve"], look="a woman with long dark hair")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0]["prompt"] = p["shots"][0]["prompt"].replace("silver beard", "white beard")
        self.assertIn("CHARACTER_LOOK_CHANGED", codes(pc.check(p, CHARS)))

    def test_a_keeper_line_over_12_seconds_is_refused(self):
        p = plan()
        p["narration"][4]["text"] = " ".join(["Notice the order, grief comes before judgment."] * 4)   # 28 words
        self.assertIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))
        # the closing clip also holds the tail: 10.2 s at most
        p = plan()
        p["narration"][5]["text"] = ("The full story is in the long video on the channel, and part eight comes tomorrow. "
                                     "Noah builds the ark, so come and see it there.")   # 26 words: ~11.6 s
        self.assertLess(26 / pc.WPS_SLOWEST, pc.KEEPER_AUDIO[1])
        self.assertIn("KEEPER_LINE_TOO_LONG", codes(pc.check(p, CHARS)))

    def test_the_keeper_share_over_25_percent_is_refused(self):
        p = plan()
        p["shots"][1:3] = [keeper("k-more", [1])]
        self.assertIn("KEEPER_SHARE", codes(pc.check(p, CHARS)))

    def test_establishing_shots_are_held_short_and_at_most_15_percent(self):
        p = plan()
        for i in (1, 2):
            p["shots"][i] = scene(p["shots"][i]["id"], p["shots"][i]["lines"], establishing=True,
                                  look="a vast city of tents")
        p["shots"][8:8] = [scene(f"s-x{k}", [3], establishing=True, look="a vast city of tents") for k in range(4)]
        found = codes(pc.check(p, CHARS))
        self.assertIn("ESTABLISHING_SHARE", found)
        self.assertIn("ESTABLISHING_ONLY", found)   # line 1 over landscape alone

    def test_a_scene_without_people_must_be_marked(self):
        p = plan()
        p["shots"][1] = scene("s-a", [1], look="a vast city of tents", figures=None)
        del p["shots"][1]["figures"]
        self.assertIn("SCENE_WITHOUT_CHARACTERS", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][1] = scene("s-a", [1], look="a crowd of men")
        self.assertIn("FIGURES_NOT_ANONYMOUS", codes(pc.check(p, CHARS)))

    def test_god_is_never_a_visible_figure(self):
        for prompt in ("God stands on a cloud above the tents", "the Lord appears as an old man with a beard",
                       "the hands of God reach down", "God watches the earth"):
            self.assertTrue(pc.god_problem(prompt), prompt)
        for prompt in ("the presence of God as a warm golden light breaking through storm clouds",
                       "the voice of the Lord carried by a strong wind over the plain", "a crowd of men walking"):
            self.assertIsNone(pc.god_problem(prompt), prompt)
        p = plan()
        p["shots"][3]["prompt"] += " God stands above the city."
        self.assertIn("GOD_AS_A_FIGURE", codes(pc.check(p, CHARS)))

    def test_the_keeper_opens_and_closes_and_never_acts(self):
        p = plan()
        p["shots"] = p["shots"][1:2] + [keeper("k-open", [0])] + p["shots"][2:]
        self.assertIn("LINES_OUT_OF_ORDER", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][0] = scene("s-open", [0])
        self.assertIn("KEEPER_MUST_OPEN", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][-1] = scene("s-close", [5])
        self.assertIn("KEEPER_MUST_CLOSE", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][3] = scene("s-c", [2], ["keeper"], look=KEEPER_LOOK)
        self.assertIn("KEEPER_IN_SCENE", codes(pc.check(p, CHARS)))

    def test_every_line_is_carried_in_order(self):
        p = plan()
        del p["shots"][5:8]
        self.assertIn("LINES_OUT_OF_ORDER", codes(pc.check(p, CHARS)))
        p = plan()
        p["shots"][1]["lines"] = [1, 3]
        self.assertIn("SHOT_LINES", codes(pc.check(p, CHARS)))

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
        p["narration"][2]["text"] = p["narration"][2]["text"].replace("continually", "always")
        p["narration"][5]["text"] = "Part eight tomorrow, see you there."
        found = " ".join(pc.check(p, CHARS)["problems"])
        self.assertIn("KJV line 2", found)
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
            p["shots"][0]["kind"] = "scene"
            bad.write_text(json.dumps(p))
            run = lambda *a: subprocess.run([sys.executable, "-I", "-B", str(HERE / "plan_check.py"), *a],
                                            capture_output=True, text=True).returncode
            self.assertEqual(run(str(ok)), 0)
            self.assertEqual(run(str(bad)), 1)


if __name__ == "__main__":
    unittest.main()
