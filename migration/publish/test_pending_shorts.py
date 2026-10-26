#!/usr/bin/env python3
"""Offline checks: which approved Shorts are still to publish, and when."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import copy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_shorts as ps  # noqa: E402

SCHED = {"publish_at": "2026-10-18T10:00:00Z", "shorts_slots": ["2026-10-18T14:00:00Z", "2026-10-18T20:00:00Z", "2026-10-18T23:00:00Z"]}


def setup(tmp, approved=2, long_published=True, done=()):
    d = Path(tmp) / "pilot-002"
    (d / "shorts").mkdir(parents=True)
    (d / "out").mkdir()
    (d / "out" / "manifest.json").write_text(json.dumps({"output_sha256": "abc"}))
    (d / "schedule.json").write_text(json.dumps(SCHED))
    shorts = [{"file": f"short-0{i}.mp4", "sha256": f"{i:064x}", "publish": i < approved, "review": {"status": "PASS" if i < approved else "FAIL", "model": "gemini-3.8-flash", "overall": 9.6, "output_sha256": f"{i:064x}"}, "qa": {"status": "PASS"}}
              for i in range(4)]
    (d / "shorts" / "shorts.json").write_text(json.dumps({"source_pilot": "pilot-002", "shorts": shorts}))
    entries = {"pilot-002:abc": {"video_id": "L"}} if long_published else {}
    entries.update({f"short:pilot-002:{s}": {"video_id": "x"} for s in done})
    return Path(tmp), {"entries": entries}


def recovery_setup(tmp):
    import review_recovery as rr
    prod = Path(tmp) / "migration" / "production"
    d = prod / rr.PILOT
    (d / "shorts").mkdir(parents=True)
    (d / "out").mkdir()
    (d / "out/manifest.json").write_text(json.dumps({"output_sha256": "longsha"}))
    (d / "schedule.json").write_text(json.dumps({"publish_at": "2026-10-21T00:00:00Z", "shorts_slots": [rr.TARGET_SLOT]}))
    records = [{"file": f"short-0{i}.mp4", "sha256": rr.OUTPUT_SHA256 if i == 0 else str(i) * 64,
                "publish": i == 0, "hook": "Prayer", "title": "Peace", "qa": {"status": "PASS"},
                "review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.6,
                           "output_sha256": rr.OUTPUT_SHA256 if i == 0 else str(i) * 64}}
               for i in range(3)]
    records[0]["previous_review"] = {"status": rr.ORIGINAL_STATUS}
    spec = {"source_pilot": rr.PILOT, "shorts": records, "review_recovery": rr._expected_binding(),
            "review_recovery_execution": {"reviewed_at": "2026-10-21T01:00:00Z", "github_run_id": "1",
                                          "github_run_attempt": "1", "output_sha256": rr.OUTPUT_SHA256}}
    (d / "shorts/shorts.json").write_text(json.dumps(spec))
    ledger = {"entries": {rr.PILOT + ":longsha": {"video_id": "LONG"}}}
    return prod, d, spec, ledger


class RecoveryPending(unittest.TestCase):
    def setUp(self):
        # Historical recovery's real hash is denied for NEW publication now.
        # Preserve temporal positive coverage using an explicitly synthetic pin.
        import review_recovery as rr
        selection = dict(rr.SELECTION, output_sha256="a" * 64)
        for name, value in (("OUTPUT_SHA256", "a" * 64), ("SELECTION", selection)):
            fixture = patch.object(rr, name, value); fixture.start(); self.addCleanup(fixture.stop)

    def test_exact_boundary_and_no_rollover(self):
        with tempfile.TemporaryDirectory() as t:
            prod, d, spec, ledger = recovery_setup(t)
            boundary = ps.when("2026-10-21T13:15:00Z")
            self.assertEqual(ps.pending(prod, ledger, boundary), ("pilot-006", ["2026-10-21T14:00:00Z"]))
            later = ps.when("2026-10-21T13:15:01Z")
            self.assertIsNone(ps.pending(prod, ledger, later))
            self.assertEqual(ps.states(d, ledger, later)[0]["state"], "temporal_recovery_blocked")
            with patch.object(ps, "datetime") as clock:
                clock.now.return_value = later
                self.assertEqual(ps.todo_files(d, ledger), [])
            ledger["entries"]["short:pilot-006:" + spec["shorts"][0]["sha256"]] = {"video_id": "OLD"}
            self.assertEqual(ps.states(d, ledger, later)[0]["state"], "published")

    def test_missing_binding_wrong_context_other_selected_block(self):
        for change in (lambda s: s.pop("review_recovery"), lambda s: s.update(source_pilot="pilot-009"),
                       lambda s: s["shorts"][1].update(publish=True),
                       lambda s: s["shorts"][0].update(sha256="f" * 64)):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as t:
                prod, d, spec, ledger = recovery_setup(t)
                change(spec)
                (d / "shorts/shorts.json").write_text(json.dumps(spec))
                now = ps.when("2026-10-21T01:00:00Z")
                self.assertIsNone(ps.pending(prod, ledger, now))
                self.assertEqual(ps.states(d, ledger, now)[0]["state"], "temporal_recovery_blocked")

    def test_taken_slot_and_late_long_never_roll(self):
        for mode in ("taken", "late"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as t:
                prod, d, spec, ledger = recovery_setup(t)
                if mode == "taken":
                    ledger["entries"]["other"] = {"slot": "2026-10-21T14:00:00Z", "video_id": "OTHER"}
                else:
                    (d / "schedule.json").write_text(json.dumps({"publish_at": "2026-10-21T13:31:00Z"}))
                self.assertIsNone(ps.pending(prod, ledger, ps.when("2026-10-21T01:00:00Z")))


class Pending(unittest.TestCase):
    def test_policy_block_is_distinct_and_false_cache_cannot_override(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=1)
            path = prod / "pilot-002/shorts/shorts.json"
            spec = json.loads(path.read_text())
            rec = spec["shorts"][0]
            rec["review"]["overall"] = 8.5
            rec["owner_quality_policy"] = {"status": "PASS"}
            path.write_text(json.dumps(spec))
            self.assertIsNone(ps.pending(prod, ledger))
            self.assertEqual(ps.states(prod / "pilot-002", ledger)[0]["state"], "owner_quality_policy_blocked")
            self.assertEqual(ps.todo_files(prod / "pilot-002", ledger), [])
            ledger["entries"]["short:pilot-002:" + rec["sha256"]] = {"video_id": "EXISTING"}
            self.assertEqual(ps.states(prod / "pilot-002", ledger)[0]["state"], "published")

    def test_truthy_publish_or_qa_failure_never_qualifies(self):
        record = {"publish": True, "sha256": "a" * 64, "qa": {"status": "PASS"},
                  "review": {"status": "PASS", "model": "gemini-3.8-flash", "overall": 9.5, "output_sha256": "a" * 64}}
        self.assertTrue(ps.approved(record))
        record["publish"] = 1
        self.assertFalse(ps.approved(record))
        record["publish"] = True
        record["qa"]["status"] = "FAIL"
        self.assertFalse(ps.approved(record))

    def test_uses_schedule_slots_while_ahead(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t)
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 7, 35, tzinfo=timezone.utc)),
                             ("pilot-002", ["2026-10-18T14:00:00Z", "2026-10-18T20:00:00Z"]))

    def test_late_slots_roll_forward(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=3)
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 19, 50, tzinfo=timezone.utc))[1],
                             ["2026-10-18T23:00:00Z", "2026-10-19T14:00:00Z", "2026-10-19T20:00:00Z"])

    def test_late_short_never_takes_another_pilots_slot(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, approved=1)
            other = prod / "pilot-003"; other.mkdir()
            (other / "schedule.json").write_text(json.dumps({"publish_at": "2026-10-18T10:00:00Z",
                                                             "shorts_slots": ["2026-10-18T20:00:00Z"]}))
            ledger["entries"]["short:pilot-001:z"] = {"video_id": "y", "slot": "2026-10-18T23:00:00Z"}
            # missed its 14:00 slot (run at 14:11): 20:00 is pilot-003's, 23:00 is already used -> next free slot
            self.assertEqual(ps.pending(prod, ledger, datetime(2026, 10, 18, 14, 11, tzinfo=timezone.utc))[1],
                             ["2026-10-19T14:00:00Z"])

    def test_nothing_when_long_unpublished_or_all_done(self):
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, long_published=False)
            self.assertIsNone(ps.pending(prod, ledger))
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t, done=(f"{0:064x}", f"{1:064x}"))
            self.assertIsNone(ps.pending(prod, ledger))


class RetiredPrayerLongs(unittest.TestCase):
    def test_no_short_of_a_prayer_long_is_published(self):
        # owner, 2026-10-26: "stop the prayer videos"; a Bible-story long's approved Shorts still go out
        with tempfile.TemporaryDirectory() as t:
            prod, ledger = setup(t)
            script = prod / "pilot-002" / "script.json"
            script.write_text(json.dumps({"archetype": "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md"}))
            self.assertIsNone(ps.pending(prod, ledger, ps.when("2026-10-18T09:00:00Z")))
            script.write_text(json.dumps({"archetype": "bible-story-long"}))
            self.assertEqual(ps.pending(prod, ledger, ps.when("2026-10-18T09:00:00Z"))[0], "pilot-002")


class CorrectionRouting(unittest.TestCase):
    def test_correction_marker_never_falls_back_to_old_binding(self):
        import review_recovery as rr
        with tempfile.TemporaryDirectory() as t:
            prod, d, spec, ledger = recovery_setup(t)
            for mutation in ({"edit_plan": {}}, {"finalization": {}},
                             {"finalization": {"kind": "wrong"}}):
                bad = copy.deepcopy(spec); bad.update(mutation)
                with patch.object(rr, "binding") as old:
                    with self.assertRaises(ValueError):
                        ps.recovery_gate(bad, d, ps.when("2026-10-21T01:00:00Z"))
                    old.assert_not_called()

    def test_correction_missing_canonical_files_blocks_pending(self):
        with tempfile.TemporaryDirectory() as t:
            prod, d, spec, ledger = recovery_setup(t)
            spec["finalization"] = {"kind": "pilot-006-correction-v1"}
            (d / "shorts/shorts.json").write_text(json.dumps(spec))
            self.assertIsNone(ps.pending(prod, ledger, ps.when("2026-10-21T01:00:00Z")))


class MaterialPending(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))

    def test_denied_hashes_before_any_historical_validator(self):
        import shorts_006_plan as v1
        for digest in ps.DENIED_NEW_006:
            with self.subTest(digest=digest), tempfile.TemporaryDirectory() as tmp:
                prod,d,spec,ledger=recovery_setup(tmp)
                spec['shorts'][0]['sha256']=digest
                spec['finalization']={'kind':'pilot-006-correction-v1'}
                with patch.object(v1,'binding') as old:
                    with self.assertRaisesRegex(ValueError,'DENIED_HISTORICAL_OUTPUT'):
                        ps.recovery_gate(spec,d,ps.when('2026-10-21T12:00:00Z'))
                old.assert_not_called()

    def test_v2_marker_renamed_pilot_never_falls_back_to_legacy_slots(self):
        markers={'edit_plan':{'version':'shorts-006-correction-plan-v2'},
                 'finalization':{'kind':'pilot-006-correction-v2'},
                 'correction_material_review_attempt':{'version':'shorts-006-material-review-attempt-v1'}}
        for choice in (*markers,'all'):
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as tmp:
                prod,d,spec,ledger=recovery_setup(tmp)
                renamed=d.with_name('pilot-009');d.rename(renamed)
                spec['source_pilot']='pilot-009';spec.update(markers if choice=='all' else {choice:markers[choice]})
                (renamed/'shorts/shorts.json').write_text(json.dumps(spec))
                ledger['entries']={'pilot-009:longsha':{'video_id':'LONG'}}
                self.assertIsNone(ps.pending(prod,ledger,ps.when('2026-10-21T12:00:00Z')))
                self.assertEqual(ps.states(renamed,ledger,ps.when('2026-10-21T12:00:00Z'))[0]['state'],'temporal_recovery_blocked')

    def test_existing_v2_missing_file_todo_prepass_never_calls_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            prod,d,spec,ledger=recovery_setup(tmp)
            spec['finalization']={'kind':'pilot-006-correction-v2'}
            spec['shorts'][0].pop('file')
            ledger['entries']['short:pilot-006:'+spec['shorts'][0]['sha256']]={'video_id':'OLD'}
            (d/'shorts/shorts.json').write_text(json.dumps(spec))
            with patch.object(ps,'recovery_gate',side_effect=AssertionError('no existing gate')):
                self.assertEqual(ps.todo_files(d,ledger),[])
                self.assertEqual(ps.states(d,ledger)[0]['video_id'],'OLD')

    def test_v2_routes_binding_with_canonical_pilot_and_no_legacy(self):
        import shorts_006_material as material
        import shorts_006_plan as v1
        with tempfile.TemporaryDirectory() as tmp:
            prod,d,spec,ledger=recovery_setup(tmp)
            spec['shorts'][0]['sha256']='a'*64
            spec['finalization']={'kind':'pilot-006-correction-v2'}
            bound={'output_sha256':'a'*64,'target_slot':'2026-10-21T14:00:00Z',
                   'release_deadline':'2026-10-21T13:15:00Z','file':'short-00.mp4',
                   'plan_sha256':'99e0ecbd3a5a0c5736e6ce8eaadc766a346cb789b08203577fa38dde1ade1543','metadata_profile':'rest-v1'}
            with patch.object(material,'binding',return_value=bound) as new, patch.object(v1,'binding') as old:
                self.assertEqual(ps.recovery_gate(spec,d,ps.when('2026-10-21T12:00:00Z')),bound)
            new.assert_called_once_with(spec,pilot_dir=d);old.assert_not_called()


def normalized_shorts_workflow(text):
    allowed = {"Tools, verified inputs (narration, figure, music, images)", "Select (whole video, Gemini), produce (own edit, STANDARD R8), watched review", "Preserve privately and record"}
    output, step, skipping = [], None, False
    for line in text.splitlines(keepends=True):
        if line.startswith("      - name: "):
            step = line.strip().split(": ", 1)[1]
        if skipping and (line.startswith("          ") or not line.strip()):
            continue
        skipping = False
        if step in allowed and line.startswith("        run: |"):
            output.append("        run: AUTHORIZED_BODY\n")
            skipping = True
        else:
            output.append(line)
    return "".join(output)

class CorrectionWorkflow(unittest.TestCase):
    def test_only_three_run_bodies_change_and_history_frames_survive(self):
        import hashlib
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/shorts.yml"
        text = workflow.read_text()
        self.assertEqual(hashlib.sha256(normalized_shorts_workflow(text).encode()).hexdigest(), "c416d6a0b1da6a3b52441e7d571dba2b72b0df08e1b1896537cafcd6443a654a")
        branch = text.split("name: Select (whole video", 1)[1].split('if [ "$PILOT" = "pilot-006" ]; then', 1)[1].split('elif [ -f', 1)[0]
        self.assertIn("--preflight", branch)
        self.assertNotIn("shorts_select.py", branch)
        self.assertLess(branch.index("--preflight"), branch.index("shorts_produce.py"))
        self.assertIn('shorts_006_material.py --review-material "$T/work/shorts/shorts.json" "$T/work/shorts/short-00.mp4"', branch)
        self.assertNotIn("shorts_review.py", branch)
        preserve = text.split('name: Preserve privately and record', 1)[1]
        correction = preserve.split('if [ "$PILOT" = "pilot-006" ]; then', 1)[1].split('          else\n', 1)[0]
        self.assertIn('rm -f "$d/short-00-frame.jpg"', correction)
        self.assertNotIn('*-frame.jpg', correction)
        self.assertIn('cp "$T/work/shorts/correction-media-checks-v2.json"', correction)


    def test_preserve_mismatch_stops_before_upload_or_canonical_change(self):
        import os, subprocess
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/shorts.yml"
        body = workflow.read_text().split('name: Preserve privately and record', 1)[1].split('        run: |\n', 1)[1]
        body = "\n".join(line[10:] if line.startswith("          ") else line for line in body.splitlines())
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); work = root / "temp/work/shorts"; work.mkdir(parents=True)
            canonical = root / "migration/production/pilot-006/shorts"; canonical.mkdir(parents=True)
            (canonical / "shorts.json").write_bytes(b"original")
            (canonical / "short-00-frame.jpg").write_bytes(b"original frame")
            (work / "shorts.json").write_text(json.dumps({"shorts": [{"media_checks_sha256": "0" * 64, "media_checks": {}}]}))
            (work / "correction-media-checks-v2.json").write_bytes(b"{}\n")
            tools = root / "bin"; tools.mkdir(); marker = root / "upload-called"
            (tools / "gh").write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n'); (tools / "gh").chmod(0o755)
            result = subprocess.run(["bash", "-e", "-c", body], cwd=root,
                env={**os.environ, "PILOT": "pilot-006", "RUNNER_TEMP": str(root / "temp"), "PATH": str(tools) + ":" + os.environ["PATH"]}, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CORRECTION_MEASUREMENTS_MISMATCH", result.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual((canonical / "shorts.json").read_bytes(), b"original")
            self.assertEqual((canonical / "short-00-frame.jpg").read_bytes(), b"original frame")


if __name__ == "__main__":
    unittest.main()
