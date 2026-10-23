#!/usr/bin/env python3
"""Offline checks of the pilot acceptance used on the executor's work: a real pilot passes; copies, fear-bait
packaging, promises, wrong length, edited QA criteria and a taken slot fail."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import script_check as sc  # noqa: E402

HERE = Path(__file__).resolve().parent


def make(t, mutate=None, name="pilot-099", at="2099-01-01T10:00:00Z"):
    prod = Path(t)
    shutil.copytree(HERE / "pilot-005", prod / name, ignore=shutil.ignore_patterns("out", "market", "shorts", "inspection"))
    shutil.copytree(HERE / "pilot-003", prod / "pilot-003", ignore=shutil.ignore_patterns("out", "market", "shorts", "inspection"))
    s = json.loads((prod / name / "script.json").read_text())
    s["pilot_id"] = name
    # pilot-005 has 14 backgrounds, below BACKGROUNDS_MIN (E48): add hydrated fixture-only records to reach the floor
    for i in range(sc.BACKGROUNDS_MIN - len(set(s["backgrounds"]))):
        s["backgrounds"].append(f"bg-fixture-extra-{i}")
        (prod / name / "images" / f"bg-fixture-extra-{i}.json").write_text("{}")
    if mutate:
        mutate(s, prod / name)
    (prod / name / "script.json").write_text(json.dumps(s))
    sch = json.loads((prod / name / "schedule.json").read_text()); sch["publish_at"] = at
    (prod / name / "schedule.json").write_text(json.dumps(sch))
    return prod / name


class Check(unittest.TestCase):
    def run_check(self, mutate=None, **kw):
        with tempfile.TemporaryDirectory() as t:
            return sc.check(make(t, mutate, **kw))[0]

    def overlap_fixture(self, mine, others):
        """Known background sets; other pilots need only script.json, not publication."""
        with tempfile.TemporaryDirectory() as t:
            pilot = make(t, name="pilot-008")
            # Remove the unrelated source fixture; isolate the known-answer sets.
            shutil.rmtree(Path(t) / "pilot-003")
            script = json.loads((pilot / "script.json").read_text())
            script["backgrounds"] = mine
            script["figure"] = None
            (pilot / "script.json").write_text(json.dumps(script))
            (pilot / "images.json").write_text(json.dumps({"images": [{"id": x} for x in set(mine)]}))
            for name, backgrounds in others.items():
                other = Path(t) / name
                other.mkdir()
                (other / "script.json").write_text(json.dumps({"backgrounds": backgrounds, "segments": []}))
            problems, stats = sc.check(pilot, Path(t))
            # the known-answer sets are deliberately small; the background floor has its own test
            return [x for x in problems if not x.startswith("TOO_FEW_BACKGROUNDS")], stats

    def test_image_set_overlap_identical_008_012(self):
        problems, stats = self.overlap_fixture(["a", "b"], {"pilot-012": ["a", "b"]})
        self.assertEqual(problems, ["image_set_overlap vs pilot-012: 1.000000 > 0.5"])
        self.assertEqual(stats["image_set_overlap"]["status"], "FAIL")
        print("KNOWN ANSWER identical 008=012: FAIL Jaccard=1")

    def test_image_set_overlap_0529_fails(self):
        mine = [f"bg-{i}" for i in range(12)]
        other = mine[:9] + [f"other-{i}" for i in range(5)]
        problems, stats = self.overlap_fixture(mine, {"pilot-012": other})
        self.assertEqual(problems, ["image_set_overlap vs pilot-012: 0.529412 > 0.5"])
        self.assertAlmostEqual(stats["image_set_overlap"]["comparisons"][0]["jaccard"], 9 / 17)
        print("KNOWN ANSWER overlap 9/17=0.529412: FAIL")

    def test_image_set_overlap_low_passes(self):
        problems, stats = self.overlap_fixture(["a", "b"], {"pilot-012": ["a", "c"]})
        self.assertEqual(problems, [])
        self.assertEqual(stats["image_set_overlap"]["status"], "PASS")
        self.assertAlmostEqual(stats["image_set_overlap"]["comparisons"][0]["jaccard"], 1 / 3)
        print("KNOWN ANSWER overlap 1/3<=0.35: PASS")

    def test_image_set_overlap_boundary_all_pilots_and_duplicates(self):
        problems, stats = self.overlap_fixture(["a", "a", "b"], {
            "pilot-002": ["a"], "pilot-012": ["a", "b"], "pilot-099": ["z"]})
        self.assertEqual(problems, ["image_set_overlap vs pilot-012: 1.000000 > 0.5"])
        self.assertEqual([r["jaccard"] for r in stats["image_set_overlap"]["comparisons"]], [0.5, 1.0, 0.0])
        self.assertEqual([r["pilot"] for r in stats["image_set_overlap"]["comparisons"]],
                         ["pilot-002", "pilot-012", "pilot-099"])
        print("KNOWN ANSWER boundary0.5 PASS; unpublished identical FAIL; duplicate IDs deduplicated")

    def test_image_set_overlap_uses_approval_limit_and_excludes_self(self):
        original = sc.three_stage.IMAGE_SHARE_MAX
        try:
            sc.three_stage.IMAGE_SHARE_MAX = 0.25
            problems, stats = self.overlap_fixture(["a", "b"], {"pilot-012": ["a", "c"]})
            self.assertEqual(problems, ["image_set_overlap vs pilot-012: 0.333333 > 0.25"])
            self.assertEqual(stats["image_set_overlap"]["limit"], 0.25)
        finally:
            sc.three_stage.IMAGE_SHARE_MAX = original
        problems, stats = self.overlap_fixture(["a", "b"], {})
        self.assertEqual(problems, [])
        self.assertEqual(stats["image_set_overlap"]["comparisons"], [])
        self.assertEqual(sc.three_stage.IMAGE_SHARE_MAX, 0.5)

    def test_real_pilot_passes(self):
        self.assertEqual(self.run_check(), [])

    def test_footage_must_be_vetted_licensed_library_clips(self):
        def footage(n, vetting="APPROVED", licence="CC BY 4.0"):
            def mutate(s, d):
                lib = d.parent / "footage" / "library"
                lib.mkdir(parents=True, exist_ok=True)
                s["footage"] = [f"clip-x-{i}" for i in range(n)]
                for c in s["footage"]:
                    (lib / f"{c}.json").write_text(json.dumps({"id": c, "vetting": vetting, "licence": licence,
                                                               "release_asset": "a.mp4", "frame": [2560, 1440]}))
            return mutate
        footage_rows = lambda problems: [p for p in problems if "FOOTAGE" in p]   # v4 hook/length have their own tests
        self.assertEqual(footage_rows(self.run_check(footage(20))), [])
        self.assertIn("TOO_FEW_FOOTAGE 12 < 20", self.run_check(footage(12)))
        self.assertTrue(any(p.startswith("FOOTAGE_NOT_VETTED") for p in self.run_check(footage(20, vetting="PENDING"))))
        self.assertTrue(any(p.startswith("FOOTAGE_RIGHTS") for p in self.run_check(footage(20, licence="CC BY-SA 4.0"))))

    def test_title_rules_r14(self):
        ok = "Before You Sleep, Thank God for Everything 🙏 | Night Prayer for Gratitude & Rest"
        self.assertEqual(sc.title_problems(ok), [])
        self.assertIn("TITLE_HAS_DATE", " ".join(sc.title_problems("Friday July 24 🙏 | Morning Prayer for Breakthrough")))
        self.assertIn("TITLE_HAS_DATE", " ".join(sc.title_problems("Powerful October Morning Prayer 🙏 | Morning Prayer")))
        self.assertIn("TITLE_NOT_HOOK_PIPE", " ".join(sc.title_problems("Let God Do The Math Today 🙏")))
        self.assertIn("TITLE_TAIL_NOT_A_SEARCH_PHRASE", " ".join(sc.title_problems("Rest 🙏 | Let God Do The Math")))
        self.assertIn("TITLE_NO_EMOJI (R14)", sc.title_problems("Before You Sleep | Night Prayer for Peace"))

    def test_speech_presence_counts_the_v4_sentence_gap(self):
        # E53: pilot-010 measured 0.844 with a 0.45 s gap; the estimate must see the gap the renderer really uses
        import re as _re
        render = (Path(sc.__file__).parent / "pilot_render.py").read_text()
        self.assertEqual(float(_re.search(r"^SENTENCE_GAP_V4 = ([0-9.]+)", render, _re.M).group(1)), sc.SENTENCE_GAP_V4)
        self.assertEqual(float(_re.search(r"^SENTENCE_GAP = ([0-9.]+)", render, _re.M).group(1)), sc.SENTENCE_GAP)

    def test_continuity_rules_r13(self):
        def seg(i, n_words, pause=0.5):
            return {"id": i, "text": " ".join(["word"] * n_words), "pause_after": pause}
        good = [seg("hook", 15), seg("roadmap", 25), seg("prayer-1", 300), seg("rehook-1", 10), seg("prayer-2", 300),
                seg("payoff", 40), {"id": "cta", "text": "Write amen, or leave a prayer request in the comments.", "pause_after": 1}]
        self.assertEqual(sc.continuity_problems(good), [])
        late = [good[0], seg("invitation", 80), good[1]] + good[2:]
        self.assertIn("ROADMAP_MISSING", " ".join(sc.continuity_problems(late)))
        gap = [s for s in good if s["id"] != "rehook-1"]   # 600 words = 257 s without a preview
        self.assertTrue(any(p.startswith("REHOOK_GAP") for p in sc.continuity_problems(gap)))
        amen_only = good[:-1] + [{"id": "cta", "text": "Write amen.", "pause_after": 1}]
        self.assertIn("PRAYER_REQUEST_INVITE_MISSING (R13)", sc.continuity_problems(amen_only))

    def test_hook_rules_r12(self):
        self.assertEqual(sc.hook_problems("Before you sleep tonight, give God the worry you cannot fix. Pray with me now."), [])
        self.assertEqual(sc.hook_problems("The world tells you to carry it all. But God says rest, so pray this with me."), [])
        self.assertIn("HOOK_OPENS_ON_GREETING", sc.hook_problems("Good morning. If you woke tired, pray with me for strength."))
        self.assertIn("HOOK_NO_PRAYER_PROMISE", sc.hook_problems("Before you sleep tonight, let your shoulders drop."))
        self.assertIn("HOOK_NOT_SECOND_PERSON", sc.hook_problems("Tonight the Lord is near. Pray with me."))
        self.assertTrue(any(p.startswith("HOOK_FIRST_SENTENCE_LONG") for p in sc.hook_problems(
            "If you have been carrying the same heavy worry through every single hour of this long day, pray with me.")))

    def test_too_few_backgrounds_fail_pilot_008(self):
        # E48: 12 backgrounds for 28 minutes scored pacing 6.5 ("a small loop of recurring images")
        def twelve(s, d):
            s["backgrounds"] = s["backgrounds"][:12]
        self.assertIn("TOO_FEW_BACKGROUNDS 12 < 18", self.run_check(twelve))

    def test_copied_prayer_fails(self):
        other = json.loads((HERE / "pilot-003" / "script.json").read_text())["segments"]
        prayer = next(x for x in other if x["id"].startswith("prayer") and not x.get("reference"))
        def copy(s, d):
            s["segments"][3]["text"] += " " + prayer["text"]
        self.assertTrue(any(p.startswith("NOT_ORIGINAL") for p in self.run_check(copy)))

    def test_fear_bait_title_and_promises_fail(self):
        def bait(s, d):
            s["working_title"] = "WARNING: Morning Prayer They Don't Want You To Hear"
        self.assertTrue(any(p.startswith("POLICY_WORDING") for p in self.run_check(bait)))
        def promise(s, d):
            s["segments"][2]["text"] += " Pray this and you will be healed."
        self.assertTrue(any(p.startswith("POLICY_WORDING") for p in self.run_check(promise)))

    def test_length_and_speech(self):
        def short(s, d):
            s["segments"] = s["segments"][:20]
        self.assertTrue(any(p.startswith("LENGTH") for p in self.run_check(short)))
        def silent(s, d):
            for x in s["segments"]:
                x["pause_after"] = 4.0
        self.assertTrue(any(p.startswith("SPEECH_PRESENCE_EST") for p in self.run_check(silent)))

    def test_modeling_beat_order(self):
        def long_hook(s, d):
            s["segments"][0]["text"] = "Good morning. " + "Stay with me for a few minutes and breathe slowly, " * 3
        self.assertTrue(any(p.startswith("HOOK_TOO_LONG") for p in self.run_check(long_hook)))
        def late_prayer(s, d):
            first = next(i for i, x in enumerate(s["segments"]) if x["id"].startswith("prayer"))
            s["segments"].insert(first, {"id": "reflection-extra", "beat": "x", "pause_after": 1.0, "text": "word " * 300})
        self.assertTrue(any(p.startswith("FIRST_PRAYER_LATE") for p in self.run_check(late_prayer)))
        def cta_first(s, d):
            ids = [x["id"] for x in s["segments"]]
            i, j = ids.index("payoff"), ids.index("cta")
            s["segments"][i]["id"], s["segments"][j]["id"] = "cta", "payoff"
        self.assertIn("CTA_BEFORE_PAYOFF", self.run_check(cta_first))

    def test_reused_images_must_be_hydrated(self):
        def unhydrated(s, d):
            (d / "images" / "figure-a.json").unlink()
        self.assertTrue(any(p.startswith("REUSED_NOT_HYDRATED") for p in self.run_check(unhydrated)))

    def test_frozen_criteria_and_slot(self):
        def edit(s, d):
            (d / "qa_criteria.json").write_text((d / "qa_criteria.json").read_text() + " ")
        self.assertIn("QA_CRITERIA_NOT_THE_FROZEN_FILE", self.run_check(edit))
        taken = json.loads((HERE / "pilot-003" / "schedule.json").read_text())["publish_at"]
        probs = self.run_check(at=taken)
        self.assertTrue(any(p.startswith("SLOT_TAKEN") or p == "PUBLISH_AT_IN_THE_PAST" for p in probs))

    def test_shorts_slot_taken(self):
        def same(s, d):
            sch = json.loads((d / "schedule.json").read_text())
            sch["shorts_slots"] = json.loads((HERE / "pilot-003" / "schedule.json").read_text())["shorts_slots"][:1]
            (d / "schedule.json").write_text(json.dumps(sch))
        self.assertTrue(any(p.startswith("SHORTS_SLOT_TAKEN") for p in self.run_check(same)))


if __name__ == "__main__":
    unittest.main()
