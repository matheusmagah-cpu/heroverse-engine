#!/usr/bin/env python3
"""Offline checks of the three-stage approval rows (structure, authenticity)."""
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import three_stage as ts  # noqa: E402

TEXT = ("Good evening. You keep carrying today; tonight, thank God and rest. " +
        " ".join(f"Thank you Lord for mercy number {i}, for the quiet gift of this hour {i}." for i in range(40)))


def pilot(root, name, backgrounds=("bg-a", "bg-b"), opening=TEXT, title="Night Prayer of Thanks | Rest in His Care",
          motion=True, at="2026-10-20T00:30:00Z", chapters=True):
    d = Path(root) / name
    (d / "out").mkdir(parents=True)
    script = {"working_title": title, "backgrounds": list(backgrounds),
              "segments": [{"id": "hook", "text": opening},
                           {"id": "cta", "text": "If this prayer helped you, you may write Amen."}]}
    (d / "script.json").write_text(json.dumps(script))
    (d / "schedule.json").write_text(json.dumps({"publish_at": at}))
    (d / "out" / "manifest.json").write_text(json.dumps({"grammar": "standard-v1:fullframe-moving+captions",
                                                         "holds": [{"motion": "push_in" if motion else None}]}))
    (d / "out" / "timeline.json").write_text(json.dumps({"sentences": [{"start": 0.4, "text": "Good evening."},
                                                                       {"start": 1.6, "text": "You keep carrying today."}]}))
    (d / "out" / "qa.json").write_text(json.dumps({"checks": {"voice_model_pinned": True, "music_owned": True}}))
    desc = "Promise.\n0:00 Opening\n1:10 Thanks\n5:20 Rest\n" if chapters else "Promise only."
    (d / "out" / "package.json").write_text(json.dumps({"title": title, "description": desc}))
    return d


class Structure(unittest.TestCase):
    def test_story_routes_to_bound_measured_story_rules_never_prayer_hygiene(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'production/bible'))
        import test_long_handoff as fixture
        h = fixture.h
        with tempfile.TemporaryDirectory() as t:
            path, built, *_ = fixture.fixture(t)
            with mock.patch.object(h.thumbs, 'publish_problems', return_value=[]):
                d = h.materialize(path, built, t)
            h.save(d / 'out/qa.json', {'criteria_version': 'story-qa-criteria-v5',
                'criteria_sha256': h.gate.FROZEN_CRITERIA_SHA256['story-qa-criteria-v5'],
                'output_sha256': h.load(d / 'out/manifest.json')['output_sha256'], 'checks': {
                    'voice_model_pinned': True, 'music_owned': True, 'every_scene_in_motion': True,
                    'first_shot_cold_open': True, 'caption_track': True, 'no_burned_captions': True}})
            structure = Path(t) / 'migration/structures/bible-story-long.json'
            structure.parent.mkdir(parents=True)
            structure.write_bytes((ts.ROOT / 'structures/bible-story-long.json').read_bytes())
            with mock.patch.object(ts, 'ROOT', Path(t) / 'migration'):
                rows = {r['name']: r['state'] for r in ts.structure_rows(d)}
                self.assertEqual(rows['story_inputs_bound'], 'PASS')
                self.assertEqual(rows['package_chapters'], 'PASS')
                self.assertEqual(rows['package_arc_schedule'], 'PASS')
                # A 60-second test fixture is not a qualifying long, and the story checks correctly reject it.
                self.assertEqual(rows['story_measured_length'], 'FAIL')
                self.assertEqual(rows['story_rehooks'], 'FAIL')
                for name in ('driver_viewer_hook_5s', 'hygiene_spoken_amen_cta', 'hygiene_recurring_refrain',
                             'hygiene_gratitude_block'):
                    self.assertNotIn(name, rows)
                (d / 'out/handoff.json').unlink()
                self.assertEqual(ts.structure_rows(d)[0]['state'], 'UNKNOWN')

    def test_conforming_pilot_passes_every_row(self):
        with tempfile.TemporaryDirectory() as t:
            rows = ts.structure_rows(pilot(t, "pilot-012"))
            self.assertEqual({r["name"]: r["state"] for r in rows if r["state"] != "PASS"}, {})

    def test_static_picture_and_missing_chapters_and_wrong_hour_fail(self):
        with tempfile.TemporaryDirectory() as t:
            rows = {r["name"]: r["state"] for r in ts.structure_rows(
                pilot(t, "pilot-012", motion=False, chapters=False, at="2026-10-20T15:00:00Z"))}
            self.assertEqual(rows["driver_continuous_motion"], "FAIL")
            self.assertEqual(rows["package_chapters"], "FAIL")
            self.assertEqual(rows["package_publish_window"], "FAIL")


    def test_v4_footage_grammar_counts_as_continuous_motion(self):
        # E56: the first v4 render (pilot-010, 178 holds all in motion) failed because only standard-v1 was accepted
        def state(grammar, motions):
            with tempfile.TemporaryDirectory() as t:
                d = pilot(t, "pilot-012")
                (d / "out" / "manifest.json").write_text(json.dumps({"grammar": grammar,
                                                                     "holds": [{"motion": m} for m in motions]}))
                return {r["name"]: r["state"] for r in ts.structure_rows(d)}["driver_continuous_motion"]
        v4 = "standard-v4:licensed-footage+depth-parallax+film-look+captions"
        self.assertEqual(state(v4, ["footage", "push_in"]), "PASS")
        self.assertEqual(state(v4, ["footage", None]), "FAIL")
        self.assertEqual(state("figure-v0:static", ["footage"]), "FAIL")


class Authenticity(unittest.TestCase):
    def setup(self, t, **other):
        d = pilot(t, "pilot-012")
        pilot(t, "pilot-002", **other)
        ledger = Path(t) / "ledger.json"
        ledger.write_text(json.dumps({"entries": {"pilot-002:abc": {"video_id": "V2"}, "pilot-004:def": {"video_id": "V4"}}}))
        receipts = Path(t) / "receipts"
        receipts.mkdir()
        (receipts / "unschedule-receipt-1.json").write_text(json.dumps({"changes": [{"video_id": "V4", "result": "UNSCHEDULED"}]}))
        refs = Path(t) / "refs"
        refs.mkdir()
        return d, dict(production=t, ledger=ledger, references=(refs, "*.json"), receipts=(receipts, "*.json")), refs

    def rows(self, d, kw):
        return {r["name"]: r["state"] for r in ts.authenticity_rows(d, **kw)}

    def test_template_copy_of_a_visible_video_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d, kw, refs = self.setup(t)                      # pilot-002 is visible and has the same script, images, title
            (refs / "r.json").write_text(json.dumps({"hashes": []}))
            got = self.rows(d, kw)
            for name in ("no_template_script_overlap", "no_template_image_set", "no_template_title", "no_template_opening_line"):
                self.assertEqual(got[name], "FAIL", name)
            self.assertEqual(got["critique_policy_and_ypp"], "UNKNOWN")          # missing evidence is never a pass

    def test_distinct_video_passes_and_hidden_videos_do_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            d, kw, refs = self.setup(t, backgrounds=("bg-x", "bg-y"), title="Morning Prayer for Courage | Walk With God",
                                     opening="Good morning. Before your feet touch the floor, breathe and pray with me today.")
            pilot(t, "pilot-004")                            # identical copy, but private (unscheduled): not visible
            (refs / "r.json").write_text(json.dumps({"hashes": []}))
            (d / "out" / "critique.json").write_text(json.dumps({"status": "PASS", "findings": []}))
            got = self.rows(d, kw)
            self.assertEqual({k: v for k, v in got.items() if v != "PASS"}, {})

    def test_reference_reuse_fails(self):
        with tempfile.TemporaryDirectory() as t:
            d, kw, refs = self.setup(t, backgrounds=("bg-x",), title="Other | Words", opening="Good morning. Something else entirely here now.")
            ws = re.findall(r"[a-z']+", TEXT.lower())
            hashes = [hashlib.sha256(" ".join(ws[i:i + 8]).encode()).hexdigest()[:16] for i in range(len(ws) - 7)]
            (refs / "r.json").write_text(json.dumps({"hashes": hashes}))
            self.assertEqual(self.rows(d, kw)["not_reused_reference_overlap"], "FAIL")

    def test_scripture_heavy_script_fails_narrative_share(self):
        with tempfile.TemporaryDirectory() as t:
            d, kw, _ = self.setup(t, backgrounds=("bg-x",), title="Other | Words")
            s = json.loads((d / "script.json").read_text())
            s["segments"] = [{"id": "s", "text": " ".join("The LORD is my shepherd; I shall not want." for _ in range(50))}]
            (d / "script.json").write_text(json.dumps(s))
            self.assertEqual(self.rows(d, kw)["original_words_share"], "FAIL")

    def test_story_counts_explicit_kjv_quotations_without_archaic_word_heuristics(self):
        with tempfile.TemporaryDirectory() as t:
            d, kw, _ = self.setup(t, backgrounds=("bg-x",), title="Other | Words")
            s = json.loads((d / "script.json").read_text())
            s.update(version="bible-long-publication-script-v1", segments=[{
                "id": "n00", "text": "In the beginning God created the heaven and the earth.",
                "reference": "Genesis 1:1 (KJV)", "kind": "scripture"},
                {"id": "n01", "text": "The story begins.", "kind": "story"}])
            (d / "script.json").write_text(json.dumps(s))
            self.assertEqual(self.rows(d, kw)["original_words_share"], "FAIL")


if __name__ == "__main__":
    unittest.main()
