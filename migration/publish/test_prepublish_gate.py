#!/usr/bin/env python3
"""Offline checks of the final pre-publication decision: good, bad and missing-evidence cases."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepublish_gate as g  # noqa: E402

PROD = Path(__file__).resolve().parent.parent / "production"
CRITERIA = (PROD / "pilot-002" / "qa_criteria.json").read_bytes()
SHA = "f" * 64
CHECKS = sorted({c for spec in g.DIMENSIONS.values() for c in spec["qa"]})
RUBRIC = sorted({c for spec in g.DIMENSIONS.values() for c in spec["review"]})


def good():
    qa = {"output_sha256": SHA, "status": "PASS", "criteria_version": "pilot-qa-criteria-v2",
          "criteria_sha256": hashlib.sha256(CRITERIA).hexdigest(), "checks": {c: True for c in CHECKS}}
    review = {"output_sha256": SHA, "status": "PASS", "watched_review": {**{c: 9 for c in RUBRIC}, "overall": 9, "model": "claude-session-reviewer"},
              "scorecard_hard": {n: {"pass": True, "value": 1} for n in g.SCORE_HARD},
              "scorecard_reported": {"beats_per_minute": {"value": 1.0, "inside": False}}}
    review["watched_review"].update(evidence=["inspection/review-sheet.jpg", "out/qa.json"], issues=[])
    return qa, {"output_sha256": SHA}, review


SCAN = {"status": "PASS", "rows": {"black_picture": {"longest_s": 0, "pass": True, "blocking": True},
                                   "digital_silence": {"longest_s": 0, "pass": True, "blocking": True},
                                   "frozen_picture": {"longest_s": 9, "inside": False, "blocking": False}}}


def run(qa, manifest, review, preflight=(), video_bytes=None, criteria=CRITERIA, scan=SCAN, archetype="bible-story-long"):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "pilot-009"
        (d / "out").mkdir(parents=True)
        (d / "qa_criteria.json").write_bytes(criteria)
        if archetype is not None:
            (d / "script.json").write_text(json.dumps({"archetype": archetype}))
        for name, obj in (("qa", qa), ("manifest", manifest), ("review", review), ("scan", scan)):
            if obj is not None:
                (d / "out" / f"{name}.json").write_text(json.dumps(obj))
        video = None
        if video_bytes is not None:
            video = d / "v.mp4"
            video.write_bytes(video_bytes)
        return g.evaluate(d, video, None if preflight is None else list(preflight))


class Gate(unittest.TestCase):
    def test_e208_review_schema_and_finite_scores_are_required_at_consumption(self):
        for field, values in {
                "evidence": (None, [], "viewed", True, {"file": "x"}, [None], [" "]),
                "issues": (None, "none", [True], [{}], [" "]),
                "picture_quality": (True, float("inf"), float("nan"), 11, -1),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    qa, man, rev = good()
                    rev["watched_review"][field] = value
                    self.assertNotEqual(run(qa, man, rev)["decision"], "PASS")

    def test_explicit_gpt_reviewer_passes_but_nearby_model_names_do_not(self):
        qa, man, rev = good()
        rev["watched_review"].update(model="gpt-6-astra-session-reviewer", overall=9.5)
        self.assertEqual(run(qa, man, rev)["decision"], "PASS")
        for model in ("gpt-6-astra", "gpt-6-astra-session-reviewer-other"):
            with self.subTest(model=model):
                rev["watched_review"]["model"] = model
                self.assertEqual(run(qa, man, rev)["decision"], "UNKNOWN")

    def test_gpt_reviewer_does_not_bypass_binding_missing_scores_or_frozen_qa(self):
        qa, man, rev = good()
        rev["watched_review"].update(model="gpt-6-astra-session-reviewer", overall=9.5)
        other = copy.deepcopy(rev); other["output_sha256"] = "0" * 64
        self.assertEqual(run(qa, man, other)["decision"], "UNKNOWN")
        missing = copy.deepcopy(rev); del missing["watched_review"]["policy_safe"]
        self.assertEqual(run(qa, man, missing)["decision"], "UNKNOWN")
        self.assertEqual(run(qa, man, rev, criteria=CRITERIA + b" ")["dimensions"]["binding"], "FAIL")
        failed = copy.deepcopy(rev); failed["watched_review"]["picture_quality"] = 6.5
        self.assertEqual(run(qa, man, failed)["decision"], "FAIL")

    def test_good_case_passes_and_informative_rows_do_not_decide(self):
        r = run(*good())
        self.assertEqual(r["decision"], "PASS")
        self.assertTrue(r["eligible_for_automatic_publication"])
        self.assertIn("beats_per_minute", r["informative_not_deciding"])  # outside its band, still PASS
        self.assertIn("scan_frozen_picture", r["informative_not_deciding"])  # reported until calibrated

    def test_a_prayer_long_never_passes(self):
        # owner, 2026-10-26: "stop the prayer videos"; only a Bible-story long may be approved or published
        for archetype in ("migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md", None):
            r = run(*good(), archetype=archetype)
            self.assertEqual((r["decision"], r["dimensions"]["format"]), ("FAIL", "FAIL"), archetype)
            self.assertEqual(r["items"]["format"][0]["detail"], "NOT_STORY_LONG")
        self.assertEqual(run(*good())["dimensions"]["format"], "PASS")

    def test_bad_cases_fail(self):
        qa, man, rev = good()
        bad_qa = copy.deepcopy(qa); bad_qa["checks"]["true_peak"] = False
        self.assertEqual(run(bad_qa, man, rev)["dimensions"]["audio"], "FAIL")
        bad_rev = copy.deepcopy(rev); bad_rev["watched_review"]["figure_and_background_integrity"] = 5
        r = run(qa, man, bad_rev)
        self.assertEqual((r["decision"], r["dimensions"]["image"]), ("FAIL", "FAIL"))
        low = copy.deepcopy(rev); low["watched_review"]["overall"] = 7.5
        self.assertEqual(run(qa, man, low)["decision"], "FAIL")
        hard = copy.deepcopy(rev); hard["scorecard_hard"]["minutes"]["pass"] = False
        self.assertEqual(run(qa, man, hard)["decision"], "FAIL")
        miner = copy.deepcopy(rev); miner["scorecard_hard"]["coverage"] = {"pass": False, "value": 0.69}  # proven miner row
        self.assertEqual(run(qa, man, miner)["decision"], "FAIL")
        self.assertEqual(run(qa, man, rev, preflight=["THUMBNAIL_SIZE"])["decision"], "FAIL")
        gap = copy.deepcopy(SCAN); gap["status"] = "FAIL"; gap["rows"]["black_picture"].update(longest_s=1.0, **{"pass": False})
        self.assertEqual(run(qa, man, rev, scan=gap)["dimensions"]["full_file_scan"], "FAIL")   # 1 s black gap
        # a render whose QA criteria were edited after the freeze never passes
        self.assertEqual(run(qa, man, rev, criteria=CRITERIA + b" ")["dimensions"]["binding"], "FAIL")
        # the file given is not the approved one
        self.assertEqual(run(qa, man, rev, video_bytes=b"other")["dimensions"]["binding"], "FAIL")

    def test_missing_or_errored_evidence_is_unknown_never_pass(self):
        qa, man, rev = good()
        self.assertEqual(run(qa, man, None)["decision"], "UNKNOWN")                      # no watched review
        self.assertEqual(run(None, man, rev)["decision"], "UNKNOWN")                     # no QA
        err = {"output_sha256": SHA, "status": "ERROR", "error": "HTTPError 429 quota"}
        self.assertEqual(run(qa, man, err)["decision"], "UNKNOWN")                       # quota / provider error
        timeout = {"output_sha256": SHA, "status": "ERROR", "error": "TimeoutError"}
        self.assertFalse(run(qa, man, timeout)["eligible_for_automatic_publication"])
        other = copy.deepcopy(rev); other["output_sha256"] = "0" * 64
        self.assertEqual(run(qa, man, other)["decision"], "UNKNOWN")                     # review of another file
        gap = copy.deepcopy(qa); del gap["checks"]["wer_vs_script"]
        self.assertEqual(run(gap, man, rev)["dimensions"]["transcript"], "UNKNOWN")     # check absent
        miss = copy.deepcopy(rev); del miss["watched_review"]["policy_safe"]
        self.assertEqual(run(qa, man, miss)["decision"], "UNKNOWN")                      # score absent
        self.assertEqual(run(qa, man, rev, preflight=None)["decision"], "UNKNOWN")       # preflight could not run
        fallback = copy.deepcopy(rev); fallback["watched_review"].update({"model": "gemini-3.6-flash", "policy_safe": 6})
        self.assertEqual(run(qa, man, fallback)["decision"], "UNKNOWN")                  # uncalibrated reviewer: no verdict
        lite = copy.deepcopy(rev); lite["watched_review"]["model"] = "gemini-3.5-flash-lite"
        self.assertFalse(run(qa, man, lite)["eligible_for_automatic_publication"])     # not even when it says 9
        self.assertEqual(run(qa, {}, rev)["decision"], "UNKNOWN")                        # no manifest hash
        self.assertEqual(run(qa, man, rev, scan=None)["decision"], "UNKNOWN")            # whole-file scan missing
        self.assertEqual(run(qa, man, rev, scan={"status": "ERROR", "error": "x"})["decision"], "UNKNOWN")

    def test_market_evidence_never_decides(self):
        r = run(*good())
        self.assertEqual(r["decision"], "PASS")
        self.assertEqual(r["market_evidence_not_deciding"]["status"], "UNKNOWN")   # no opinion: shown, not blocking

    def test_fail_outranks_unknown(self):
        qa, man, _ = good()
        qa["checks"]["no_third_party_footage"] = False
        self.assertEqual(run(qa, man, None)["decision"], "FAIL")

    def test_matching_video_file_passes(self):
        data = b"video bytes"
        qa, man, rev = good()
        sha = hashlib.sha256(data).hexdigest()
        for o in (qa, man, rev):
            o["output_sha256"] = sha
        self.assertEqual(run(qa, man, rev, video_bytes=data)["decision"], "PASS")


class StandardV3(unittest.TestCase):
    def test_v3_render_is_held_to_the_standard_grammar(self):
        crit = (PROD / "qa_criteria_v3.json").read_bytes()
        checks = sorted({c for spec in g.DIMENSIONS_V3.values() for c in spec["qa"]})
        qa, man, rev = good()
        qa.update({"criteria_version": "pilot-qa-criteria-v3", "criteria_sha256": hashlib.sha256(crit).hexdigest(),
                   "checks": {c: True for c in checks}})
        r = run(qa, man, rev, criteria=b"not the v3 file")       # v3 binds to the shared frozen file, not the pilot copy
        self.assertEqual(r["dimensions"]["binding"], "PASS")
        self.assertEqual(r["dimensions"]["image"], "PASS")
        figure = copy.deepcopy(qa); figure["checks"]["no_figure"] = False
        self.assertEqual(run(figure, man, rev)["dimensions"]["image"], "FAIL")
        box = copy.deepcopy(qa); box["checks"]["caption_no_box"] = False
        self.assertEqual(run(box, man, rev)["dimensions"]["captions"], "FAIL")
        # the v2 figure grammar is not what a v3 render is judged by
        self.assertNotIn("figure_present_after_title", {c for spec in g.DIMENSIONS_V3.values() for c in spec["qa"]})

    def test_v3_criteria_frozen_hash(self):
        self.assertEqual(hashlib.sha256((PROD / "qa_criteria_v3.json").read_bytes()).hexdigest(),
                         g.FROZEN_CRITERIA_SHA256["pilot-qa-criteria-v3"])



class StandardV4(unittest.TestCase):
    """Owner, 2026-10-23: licensed real footage (pilot-qa-criteria-v4); v3 stays frozen and judged as before."""

    def test_v4_render_needs_licensed_vetted_footage_and_its_share(self):
        crit = (PROD / "qa_criteria_v4.json").read_bytes()
        checks = sorted({c for spec in g.DIMENSIONS_V4.values() for c in spec["qa"]})
        self.assertIn("footage_licensed_vetted_and_credited", checks)
        self.assertIn("footage_picture_share", checks)
        self.assertNotIn("no_third_party_footage", checks)
        qa, man, rev = good()
        qa.update({"criteria_version": "pilot-qa-criteria-v4", "criteria_sha256": hashlib.sha256(crit).hexdigest(),
                   "checks": {c: True for c in checks}})
        r = run(qa, man, rev, criteria=b"not the v4 file")
        self.assertEqual(r["dimensions"]["binding"], "PASS")
        self.assertEqual(r["dimensions"]["rights"], "PASS")
        unvetted = copy.deepcopy(qa); unvetted["checks"]["footage_licensed_vetted_and_credited"] = False
        self.assertEqual(run(unvetted, man, rev)["dimensions"]["rights"], "FAIL")
        stills = copy.deepcopy(qa); stills["checks"]["footage_picture_share"] = False
        self.assertEqual(run(stills, man, rev)["dimensions"]["image"], "FAIL")

    def test_v4_criteria_frozen_hash_and_v3_untouched(self):
        self.assertEqual(hashlib.sha256((PROD / "qa_criteria_v4.json").read_bytes()).hexdigest(),
                         g.FROZEN_CRITERIA_SHA256["pilot-qa-criteria-v4"])
        self.assertEqual(g.FROZEN_CRITERIA_SHA256["pilot-qa-criteria-v3"],
                         "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3")


class StoryV1(unittest.TestCase):
    """Owner, 2026-10-25: Bible-story longs mix Pavo AI video (upscaled to 1440p) with licensed footage."""

    def test_story_criteria_frozen_and_v4_floors_unchanged(self):
        crit = PROD / "qa_criteria_story_v1.json"
        self.assertEqual(hashlib.sha256(crit.read_bytes()).hexdigest(), g.FROZEN_CRITERIA_SHA256["story-qa-criteria-v1"])
        story, v4 = json.loads(crit.read_text()), json.loads((PROD / "qa_criteria_v4.json").read_text())
        self.assertEqual(story["technical"], v4["technical"])
        self.assertEqual(story["speech"], v4["speech"])
        for k, v in v4["grammar"].items():
            if k != "footage_picture_share_min":
                self.assertEqual(story["grammar"][k], v, k)
        self.assertIn("story-qa-criteria-v1", g.STANDARD_VERSIONS)

    def test_story_render_needs_ai_share_and_source(self):
        crit = (PROD / "qa_criteria_story_v1.json").read_bytes()
        checks = sorted({c for spec in g.DIMENSIONS_STORY_V1.values() for c in spec["qa"]})
        for c in ("footage_picture_share", "ai_video_picture_share", "ai_video_source_and_licence",
                  "footage_licensed_vetted_and_credited"):
            self.assertIn(c, checks)
        qa, man, rev = good()
        qa.update({"criteria_version": "story-qa-criteria-v1", "criteria_sha256": hashlib.sha256(crit).hexdigest(),
                   "checks": {c: True for c in checks}})
        r = run(qa, man, rev)
        self.assertEqual(r["dimensions"]["binding"], "PASS")
        too_much_ai = copy.deepcopy(qa); too_much_ai["checks"]["ai_video_picture_share"] = False
        self.assertEqual(run(too_much_ai, man, rev)["dimensions"]["image"], "FAIL")
        wrong = copy.deepcopy(qa); wrong["checks"]["ai_video_source_and_licence"] = False
        self.assertEqual(run(wrong, man, rev)["dimensions"]["rights"], "FAIL")


class StoryV4(unittest.TestCase):
    """Owner 27/10 (R1-R4): a long that declares story QA v4 is gated by every v4 row; v4 is pinned like v3."""
    CRIT = (PROD / "qa_criteria_story_v4.json").read_bytes()

    def v4(self):
        rows = g.story_v3_rows("story-qa-criteria-v4")
        qa, man, rev = good()
        qa.update({"criteria_version": "story-qa-criteria-v4", "criteria_sha256": hashlib.sha256(self.CRIT).hexdigest(),
                   "checks": {c: True for names in rows.values() for c in names}})
        return qa, man, rev

    def test_v4_is_pinned_and_every_row_is_an_item(self):
        self.assertEqual(hashlib.sha256(self.CRIT).hexdigest(), g.FROZEN_CRITERIA_SHA256["story-qa-criteria-v4"])
        self.assertEqual(g.CRITERIA_FILES["story-qa-criteria-v4"].read_bytes(), self.CRIT)
        crit = json.loads(self.CRIT)
        rows = sorted(f"{s}.{k}" for s in ("technical", "speech", "rights", "grammar") for k in crit[s])
        r = run(*self.v4())
        self.assertEqual(sorted(i["item"] for i in r["items"]["story_qa_v4"]), rows)
        self.assertEqual(r["dimensions"]["story_qa_v4"], "PASS")
        named = {n for names in g.story_v3_rows("story-qa-criteria-v4").values() for n in names}
        read = {n for spec in g.dimensions_story_v3("story-qa-criteria-v4").values() for n in spec["qa"]}
        self.assertEqual(named - read, set())

    def test_failed_speech_checks_or_an_unpinned_asr_never_pass(self):
        for check in ("pavo_speech_clip_checks", "asr_model_pinned", "fallback_shots", "spoken_audio_mix"):
            qa, man, rev = self.v4()
            qa["checks"][check] = False
            self.assertEqual(run(qa, man, rev)["dimensions"]["story_qa_v4"], "FAIL", check)
            qa["checks"][check] = None
            self.assertEqual(run(qa, man, rev)["decision"], "UNKNOWN", check)


class StoryV3(unittest.TestCase):
    """E126: the acted Bible-story long is measured by the frozen story QA v3 (no footage minimum: owner,
    2026-10-27), and every v3 row is an item of the gate: PASS, FAIL or UNKNOWN, never skipped."""
    CRIT = (PROD / "qa_criteria_story_v3.json").read_bytes()

    def v3(self):
        rows = g.story_v3_rows()
        checks = sorted({n for names in rows.values() for n in names})
        qa, man, rev = good()
        qa.update({"criteria_version": "story-qa-criteria-v3", "criteria_sha256": hashlib.sha256(self.CRIT).hexdigest(),
                   "checks": {c: True for c in checks}})
        return qa, man, rev

    def test_v3_is_pinned_and_its_file_is_the_frozen_one(self):
        self.assertEqual(hashlib.sha256(self.CRIT).hexdigest(), g.FROZEN_CRITERIA_SHA256["story-qa-criteria-v3"])
        self.assertIn("story-qa-criteria-v3", g.STANDARD_VERSIONS)
        self.assertEqual(g.CRITERIA_FILES["story-qa-criteria-v3"].read_bytes(), self.CRIT)

    def test_every_v3_row_is_an_item_and_a_full_qa_passes(self):
        crit = json.loads(self.CRIT)
        rows = sorted(f"{s}.{k}" for s in ("technical", "speech", "rights", "grammar") for k in crit[s])
        r = run(*self.v3())
        self.assertEqual(sorted(i["item"] for i in r["items"]["story_qa_v3"]), rows)
        self.assertEqual(r["dimensions"]["story_qa_v3"], "PASS")
        for dim in ("binding", "technical", "audio", "transcript", "captions", "sync", "image", "rights"):
            self.assertEqual(r["dimensions"][dim], "PASS", dim)
        # every qa check a v3 row names is read by a dimension too
        named = {n for names in g.story_v3_rows().values() for n in names}
        read = {n for spec in g.dimensions_story_v3().values() for n in spec["qa"]}
        self.assertEqual(named - read, set())

    def test_no_footage_minimum_and_no_v1_row(self):
        read = {n for spec in g.dimensions_story_v3().values() for n in spec["qa"]}
        for gone in ("footage_picture_share", "title_card_seconds", "no_figure", "caption_hold_median",
                     "caption_coverage_of_speech", "caption_chars_max"):
            self.assertNotIn(gone, read)
        qa, man, rev = self.v3()
        self.assertNotIn("footage_picture_share", qa["checks"])
        self.assertEqual(run(qa, man, rev)["dimensions"]["image"], "PASS")

    def test_a_failed_absent_or_unknown_check_never_passes_its_row(self):
        qa, man, rev = self.v3()
        bad = copy.deepcopy(qa); bad["checks"]["srt_cue_words_max"] = False
        r = run(bad, man, rev)
        state = {i["item"]: i["state"] for i in r["items"]["story_qa_v3"]}
        self.assertEqual((state["grammar.srt_cue_words_max"], r["dimensions"]["captions"]), ("FAIL", "FAIL"))
        gone = copy.deepcopy(qa); del gone["checks"]["first_shot_cold_open"]
        r = run(gone, man, rev)
        state = {i["item"]: i["state"] for i in r["items"]["story_qa_v3"]}
        self.assertEqual((state["grammar.first_shot"], r["decision"]), ("UNKNOWN", "UNKNOWN"))
        unknown = copy.deepcopy(qa); unknown["checks"]["ai_video_clip_checks"] = None
        r = run(unknown, man, rev)
        state = {i["item"]: i["state"] for i in r["items"]["story_qa_v3"]}
        self.assertEqual((state["grammar.ai_video_clip_checks"], r["dimensions"]["image"]), ("UNKNOWN", "UNKNOWN"))
        other = copy.deepcopy(qa); other["output_sha256"] = "0" * 64
        r = run(other, man, rev)
        self.assertEqual({i["state"] for i in r["items"]["story_qa_v3"]}, {"UNKNOWN"})


if __name__ == "__main__":
    unittest.main()
