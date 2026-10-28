#!/usr/bin/env python3
"""Offline contract fixtures only. They do not assert perceptual quality or create production approvals."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_handoff as h

ROOT = Path(__file__).resolve().parents[3]


def fixture(root):
    root = Path(root)
    plan_path = root / "migration/production/bible/plans/arc-fixture-long.json"
    plan = {"version": "bible-long-plan-v1", "episode": "arc-fixture-long", "pilot": "pilot-999", "arc": "arc-fixture",
            "title": "Creation: The First Word | Genesis Bible Story (KJV)", "criteria": "story-qa-criteria-v5",
            "passage": "Genesis 1:1 (KJV, public domain)", "burned_captions": False,
            "chapters": [{"id": "c1", "title": "Light begins"}, {"id": "c2", "title": "The first question"}],
            "narration": [{"kind": "story", "text": "The story starts with a word, before there was a listener."},
                          {"kind": "cta", "text": "What part of this beginning will you remember?"}],
            "shots": [{"id": "s-open", "kind": "scene", "beat": "cold_open", "speaker": "god", "conflict": True,
                       "line": "In the beginning God created the heaven and the earth.", "reference": "Genesis 1:1 (KJV)"},
                      {"id": "s-light", "kind": "scene", "beat": "chapter", "chapter": "c1", "lines": [0]},
                      {"id": "k-close", "kind": "keeper", "beat": "keeper_close", "chapter": "c2", "lines": [1]}]}
    h.save(plan_path, plan)
    h.save(root / "migration/production/bible/arcs.json", {"arcs": [{"id": "arc-fixture", "long": {
        "pilot": "pilot-999", "slot": "2026-10-28T22:00:00Z"}}]})
    thumb = root / "migration/production/bible/thumbs/arc-fixture-long.jpg"
    thumb.parent.mkdir(parents=True, exist_ok=True)
    thumb.write_bytes(b"offline thumbnail bytes, not perceptual evidence")
    built = root / "built"
    built.mkdir()
    video = built / "arc-fixture-long.mp4"
    video.write_bytes(b"offline opaque master bytes, never QA-passed")
    sha = h.sha256(video)
    items, _ = h.pc.sequence(plan)
    sentences = [{"segment": f"n{k:02d}", "text": item["text"], "start": k * 20 + 0.1, "end": k * 20 + 5.0,
                  **({"speaker": item["speaker"]} if item.get("speaker") else {})} for k, item in enumerate(items)]
    cuts = [{"shot": shot["id"], "source": shot["id"], "kind": "scene", "start": k * 20, "end": (k + 1) * 20,
             "src_start": 0.0, "speed": 1.0} for k, shot in enumerate(plan["shots"])]
    timeline = {"version": "bible-long-timeline-v1", "pilot_id": "pilot-999", "long": "arc-fixture-long",
                "output_sha256": sha, "output_seconds": 60, "voice_seconds": 58.8, "sentences": sentences,
                "cuts": [dict(cut, hold=0.0) for cut in cuts]}
    h.save(built / "timeline.json", timeline)
    text, track = h.captions.track_record(sentences)
    (built / "captions.srt").write_text(text)
    manifest = {"version": "bible-long-manifest-v1", "pilot_id": "pilot-999", "long": "arc-fixture-long",
                "output_sha256": sha, "output_seconds": 60, "criteria_version": "story-qa-criteria-v5",
                "sentences": sentences, "timeline": {"file": "timeline.json", "sha256": h.sha256(built / "timeline.json")},
                "caption_track": track, "clips": [{"id": "s-light", "source": "footage", "source_sha256": "a" * 64,
                    "licence": "CC BY 4.0", "credit": "Fixture creator, clip URL, CC BY 4.0, cropped"}],
                "holds": [dict(cut, chapter=shot.get("chapter"), beat=shot["beat"],
                               shot_kind="keeper" if shot["kind"] == "keeper" else "scene")
                          for cut, shot in zip(cuts, plan["shots"])]}
    h.save(built / "manifest.json", manifest)
    h.save(built / "report.json", {"composed": {"output_sha256": sha, "timeline": cuts}})
    return plan_path, built, plan, manifest, timeline


class Handoff(unittest.TestCase):
    def test_e189_revocation_blocks_inputs_and_already_bound_master_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, built, plan, *_ = fixture(tmp)
            with mock.patch.object(h.thumbs, "publish_problems", return_value=[]):
                d = h.materialize(path, built, tmp)
                binding = (d / "out/handoff.json").read_bytes()
                h.save(Path(tmp) / "migration/production/bible/shots/origin.json", {
                    "shots": {}, "revocations": [{"shot": "old", "clip_sha256": "a" * 64, "score": 9.6,
                        "revocation": {"by": "ChatGPT", "reason": "visible aircraft"}}]})
                # The old manifest's source SHA remains vetoed even if current approvals changed.
                with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                    h.verify(d, root=tmp)
                h.save(Path(tmp) / "migration/production/bible/shots/arc-fixture-long.json", {"shots": {
                    "s-light": {"clip_sha256": "a" * 64, "score": 10, "request_sha256": "c" * 64}}})
                with self.assertRaisesRegex(SystemExit, "SHOT_REVIEW_REVOKED"):
                    h.input_documents(path, root=tmp)
                self.assertEqual((d / "out/handoff.json").read_bytes(), binding)
                self.assertFalse((d / "inspection/APPROVAL.json").exists())

    def test_qa_fail_is_preserved_and_cannot_approve_or_publish(self):
        import publication_binding
        with tempfile.TemporaryDirectory() as tmp:
            path, built, *_ = fixture(tmp)
            with mock.patch.object(h.thumbs, 'publish_problems', return_value=[]):
                d = h.materialize(path, built, tmp)
            manifest = h.load(d / 'out/manifest.json')
            qa = {'status': 'FAIL', 'output_sha256': manifest['output_sha256'], 'criteria_version': 'story-qa-criteria-v5',
                  'criteria_sha256': h.gate.FROZEN_CRITERIA_SHA256['story-qa-criteria-v5'],
                  'checks': {'wer_vs_script': False}}
            h.save(d / 'out/qa.json', qa)
            h.verify(d, root=tmp)  # preservation is not qualification: the failed evidence remains useful to review
            self.assertEqual(h.load(d / 'out/qa.json'), qa)
            self.assertFalse((d / 'inspection/APPROVAL.json').exists())
            gate = h.gate.evaluate(d, preflight_problems=[])
            self.assertEqual(gate['decision'], 'FAIL')
            self.assertFalse(gate['eligible_for_automatic_publication'])
            self.assertIn('QA_NOT_PASS', publication_binding.check(qa, {'approved': False}, manifest, gate))

    def test_live_arc01_title_fits_publication_without_an_unsupported_afternoon_claim(self):
        plan = h.load(ROOT / 'migration/production/bible/plans/arc-01-long.json')
        self.assertLessEqual(len(plan['title']), 100)
        self.assertNotIn('One Afternoon', plan['title'])

    def test_release_capacity_counts_both_aliases_and_every_large_file_part(self):
        self.assertEqual(h.release_uploads(99, part_bytes=100), 3)
        self.assertEqual(h.release_uploads(200, part_bytes=100), 5)
        self.assertEqual(h.release_uploads(201, part_bytes=100), 7)
        self.assertEqual(h.release_uploads(201, pilot=False, part_bytes=100), 4)
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'master.mp4'; video.write_bytes(b'fixture')
            def api(path):
                if path.startswith('releases/tags/'):
                    return {'id': 7}
                page = int(path.rsplit('=', 1)[-1])
                return [{}] * (100 if page < 10 else 99)
            with self.assertRaisesRegex(SystemExit, 'LONG_RELEASE_CAPACITY'):
                h.release_capacity(video, api=api)

    def test_e168_materializes_same_master_words_timing_captions_and_package_without_any_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, built, plan, manifest, timeline = fixture(tmp)
            with mock.patch.object(h.thumbs, "publish_problems", return_value=[]):
                d = h.materialize(path, built, tmp)
            script, package = h.load(d / "script.json"), h.load(d / "out/package.json")
            self.assertEqual(script["archetype"], "bible-story-long")
            self.assertEqual([s["id"] for s in script["segments"]], [s["segment"] for s in timeline["sentences"]])
            self.assertEqual(script["segments"][0]["reference"], "Genesis 1:1 (KJV)")
            self.assertEqual((d / "out/timeline.json").read_bytes(), (built / "timeline.json").read_bytes())
            self.assertEqual((d / "out/captions.srt").read_bytes(), (built / "captions.srt").read_bytes())
            self.assertIn("0:20 Light begins", package["description"])
            self.assertIn("0:40 The first question", package["description"])
            self.assertIn("Fixture creator, clip URL, CC BY 4.0, cropped", package["description"])
            self.assertIn("AI-generated", package["description"])
            self.assertEqual(package["thumb_episode"], plan["episode"])
            self.assertNotIn("morning prayer", json.dumps(package).lower())
            self.assertEqual(h.load(d / "schedule.json")["publish_at"], "2026-10-28T22:00:00Z")
            binding = h.verify(d, built / (plan["episode"] + ".mp4"), tmp)
            self.assertEqual(binding["release_asset"], f"pilot-999-sha256-{manifest['output_sha256']}.mp4")
            for f in ("out/qa.json", "out/review.json", "inspection/claude_review.json", "inspection/APPROVAL.json"):
                self.assertFalse((d / f).exists(), f)

    def test_every_changed_source_witness_is_refused(self):
        for name, mutate in (
                ("manifest.json", lambda x: x.update(output_sha256="b" * 64)),
                ("report.json", lambda x: x["composed"].update(output_sha256="b" * 64)),
                ("timeline.json", lambda x: x["sentences"][0].update(start=2.0)),
                ("manifest.json", lambda x: x.update(criteria_version="story-qa-criteria-v3"))):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path, built, *_ = fixture(tmp)
                doc = h.load(built / name); mutate(doc); h.save(built / name, doc)
                with mock.patch.object(h.thumbs, "publish_problems", return_value=[]), self.assertRaisesRegex(
                        SystemExit, "LONG_HANDOFF_REFUSED"):
                    h.materialize(path, built, tmp)
                self.assertFalse((Path(tmp) / "migration/production/pilot-999").exists())

    def test_changed_words_are_refused_even_if_sidecars_are_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, built, _, manifest, timeline = fixture(tmp)
            timeline["sentences"][0]["text"] = "A fabricated sentence."
            h.save(built / "timeline.json", timeline)
            manifest["sentences"] = timeline["sentences"]
            manifest["timeline"]["sha256"] = h.sha256(built / "timeline.json")
            h.save(built / "manifest.json", manifest)
            with mock.patch.object(h.thumbs, "publish_problems", return_value=[]), self.assertRaisesRegex(
                    SystemExit, "spoken text differs"):
                h.materialize(path, built, tmp)

    def test_unapproved_thumbnail_calendar_and_overlong_title_fail_before_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, _, plan, *_ = fixture(tmp)
            with self.assertRaisesRegex(SystemExit, "THUMB_NOT_APPROVED"):
                h.input_documents(path, tmp)
            with mock.patch.object(h.thumbs, "publish_problems", return_value=[]):
                plan["title"] = "X" * 101; h.save(path, plan)
                with self.assertRaisesRegex(SystemExit, "title"):
                    h.input_documents(path, tmp)
                plan["title"] = "Valid title"; h.save(path, plan)
                h.save(Path(tmp) / "migration/production/bible/arcs.json", {"arcs": []})
                with self.assertRaisesRegex(SystemExit, "calendar"):
                    h.input_documents(path, tmp)

    def test_each_publication_file_and_plan_remain_bound_and_missing_witness_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, built, *_ = fixture(tmp)
            with mock.patch.object(h.thumbs, "publish_problems", return_value=[]):
                d = h.materialize(path, built, tmp)
            binding = h.load(d / "out/handoff.json")
            for name in (*binding["files"], str(path)):
                file = Path(name) if name == str(path) else d / name
                before = file.read_bytes(); file.write_bytes(before + b" ")
                with self.assertRaisesRegex(SystemExit, "LONG_HANDOFF_REFUSED"):
                    h.verify(d, root=tmp)
                file.write_bytes(before)
            binding["files"] = {}
            h.save(d / "out/handoff.json", binding)
            with self.assertRaisesRegex(SystemExit, "incomplete"):
                h.verify(d, root=tmp)

    def test_workflow_runs_real_qa_and_preserves_native_sources_before_existing_approval_route(self):
        text = (ROOT / ".github/workflows/long-build.yml").read_text()
        self.assertLess(text.index("long_handoff.py inputs"), text.index("episode_build.py voice-script"))
        self.assertIn('cp -a "$WORK/clips" "$RUNNER_TEMP/prep/clips"', text)
        self.assertIn("migration/production/qa_pilot.py", text)
        self.assertIn("ai-edge-litert==2.3.0 faster-whisper==1.2.1 av==16.0.1", text)
        self.assertIn("a29b04bd15381511a9af671baec01072039215e3", text)
        self.assertIn("11b220779aea4c6f3ce9d2549c8a95ea869ed84066864b999531ef53e594fe5b", text)
        self.assertIn('release_video.sh put "$mp4" "$PILOT-sha256-$sha.mp4"', text)
        self.assertNotIn('"approved": True', text)
        self.assertNotIn("claude_review.json", text)


if __name__ == "__main__":
    unittest.main()
