#!/usr/bin/env python3
"""episode_preflight.py (E106): a build is dispatched only after a local preflight of that exact plan says PASS, and
the preflight names each talking setup that needs a direct 0-credit Pavo probe first."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "integrations" / "pavo"))
import episode_preflight as pf  # noqa: E402

EXAMPLE = HERE / "plans" / "genesis-07-short.json"


class VoiceResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'preflight-example'
        self.prepared = self.root / 'prepared'
        for name in ('source', 'models'):
            (self.prepared / name).mkdir(parents=True)
        self.calls = 0
        self.inputs = {'script': 'fixture', 'renderer': 'fixture', 'runtime': 'fixture'}
        self.plan = json.loads(EXAMPLE.read_text())
        self.layout = {'total': 30, 'keeper_share': .2, 'lesson_share': .8, 'retimed': {}}
        self.addCleanup(patch.stopall)
        patch.object(pf, 'WORK_ROOT', self.root).start()
        # This fixture replaces synthesis/runtime only; cache bytes, lock and receipt are real.
        patch.object(pf, 'voice_inputs', side_effect=lambda *a: (dict(self.inputs), {}), create=True).start()
        patch.object(pf.subprocess, 'run', side_effect=self.fake_voice).start()
        patch.object(pf.eb, 'lines_step', return_value=self.layout).start()
        patch.object(pf.eb, 'compose_prediction', return_value=[]).start()
        patch.object(pf, 'measured_pace', return_value={}).start()

    def fake_voice(self, args, **kwargs):
        if 'voice' not in args:
            return subprocess.CompletedProcess(args, 0, stdout='/fixture', stderr='')
        self.calls += 1
        with wave.open(str(self.work / 'voice.wav'), 'wb') as w:
            w.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            w.writeframes(b'\0\0' * 24000)
        (self.work / 'timeline.json').write_text(json.dumps({
            'voice_seconds': 1, 'sample_rate': 24000,
            'segments': [{'id': 'n00', 'start': 0, 'end': 1}],
            'sentences': [{'segment': 'n00', 'text': 'Fixture.', 'start': 0, 'end': .8}]}))
        return subprocess.CompletedProcess(args, 0, stdout='{}', stderr='')

    def run_voice(self):
        return pf.voice_step(self.plan, sys.executable, self.prepared, self.work)

    def test_e211_completed_voice_is_reused_without_deleting_or_resynthesizing(self):
        first = self.run_voice()
        self.assertTrue(first['ran'])
        before = (self.work / 'voice.wav').read_bytes()
        (self.work / 'preserve.txt').write_text('existing evidence')
        second = self.run_voice()
        self.assertEqual(self.calls, 1)
        self.assertTrue(second['reused'])
        self.assertEqual((self.work / 'voice.wav').read_bytes(), before)
        self.assertTrue((self.work / 'preserve.txt').exists())

    def test_corrupt_missing_or_changed_input_never_replays_voice(self):
        self.run_voice()
        original = (self.work / 'voice.wav').read_bytes()
        for mode in ('corrupt', 'missing', 'binding', 'receipt'):
            with self.subTest(mode=mode):
                receipt_path = self.work / 'voice-checkpoint.json'
                receipt = receipt_path.read_bytes()
                if mode == 'corrupt':
                    (self.work / 'voice.wav').write_bytes(b'broken')
                elif mode == 'missing':
                    (self.work / 'voice.wav').unlink()
                elif mode == 'binding':
                    self.inputs['script'] = 'different'
                else:
                    receipt_path.write_text('[]')
                out = self.run_voice()
                self.assertFalse(out['ran'])
                self.assertTrue(out['problems'][0].startswith('VOICE_CACHE_'), out)
                self.assertEqual(self.calls, 1)
                (self.work / 'voice.wav').write_bytes(original)
                self.inputs['script'] = 'fixture'
                receipt_path.write_bytes(receipt)

    def test_legacy_unreceipted_work_is_preserved_and_not_adopted(self):
        self.work.mkdir()
        (self.work / 'voice.wav').write_bytes(b'previous voice')
        out = self.run_voice()
        self.assertFalse(out['ran'])
        self.assertIn('VOICE_CACHE_UNATTESTED', out['problems'][0])
        self.assertEqual(self.calls, 0)
        self.assertEqual((self.work / 'voice.wav').read_bytes(), b'previous voice')

    def test_failed_layout_does_not_consume_a_previous_layout(self):
        self.run_voice()
        (self.work / 'layout.json').write_text(json.dumps(self.layout))
        with patch.object(pf.eb, 'lines_step', side_effect=SystemExit('NATIVE_SPEECH_OUTSIDE_MEDIA fixture')):
            out = self.run_voice()
        self.assertEqual(self.calls, 1)
        self.assertTrue(out['reused'])
        self.assertIsNone(out['measured'])
        self.assertIn('NATIVE_SPEECH_OUTSIDE_MEDIA', out['problems'][0])

    def test_incomplete_synthesis_is_not_replayed(self):
        def fail(args, **kwargs):
            if 'voice' not in args:
                return subprocess.CompletedProcess(args, 0, stdout='/fixture', stderr='')
            self.calls += 1
            (self.work / 'voice.wav').write_bytes(b'partial')
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='interrupted')
        with patch.object(pf.subprocess, 'run', side_effect=fail):
            first = self.run_voice()
            second = self.run_voice()
        self.assertFalse(first['ran'])
        self.assertFalse(second['ran'])
        self.assertEqual(self.calls, 1)
        self.assertEqual((self.work / 'voice.wav').read_bytes(), b'partial')

    def test_another_owner_or_a_symlink_is_refused_before_synthesis(self):
        import fcntl
        self.work.mkdir()
        with (self.work / '.preflight-voice.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            out = self.run_voice()
            self.assertFalse(out['ran'])
            self.assertIn('VOICE_CACHE_BUSY', out['problems'][0])
        self.assertEqual(self.calls, 0)
        linked = self.root / 'linked'
        linked.symlink_to(self.work, target_is_directory=True)
        out = pf.voice_step(self.plan, sys.executable, self.prepared, linked)
        self.assertFalse(out['ran'])
        self.assertIn('VOICE_CACHE_PATH_REFUSED', out['problems'][0])
        outside = self.root / '..' / 'must-not-create-voice'
        out = pf.voice_step(self.plan, sys.executable, self.prepared, outside)
        self.assertFalse(out['ran'])
        self.assertIn('VOICE_CACHE_PATH_REFUSED', out['problems'][0])

    def test_a_mutating_input_is_not_sealed_as_completed(self):
        self.inputs['models'] = 'before'
        def mutate(args, **kwargs):
            result = self.fake_voice(args, **kwargs)
            if 'voice' in args:
                self.inputs['models'] = 'after'
            return result
        with patch.object(pf.subprocess, 'run', side_effect=mutate):
            out = self.run_voice()
        self.assertFalse(out['ran'])
        self.assertIn('VOICE_CACHE_INPUT_CHANGED_DURING_RUN', out['problems'])
        self.assertFalse((self.work / 'voice-checkpoint.json').exists())
        self.assertTrue((self.work / 'voice.wav').exists())
        self.assertFalse(self.run_voice()['ran'])
        self.assertEqual(self.calls, 1)

    def test_model_source_or_runtime_bytes_change_the_binding(self):
        tree = self.root / 'inputs'
        tree.mkdir()
        item = tree / 'model.bin'
        item.write_bytes(b'first')
        first = pf.voice_tree(tree)
        item.write_bytes(b'second')
        self.assertNotEqual(first, pf.voice_tree(tree))
        item.write_bytes(b'first')
        (tree / '__pycache__').mkdir()
        (tree / '__pycache__' / 'temporary.pyc').write_bytes(b'cache')
        # -B disables writes, not reads: pre-existing bytecode is also an input.
        self.assertNotEqual(first, pf.voice_tree(tree))
        (tree / 'external').symlink_to(item)
        with self.assertRaisesRegex(ValueError, 'VOICE_CACHE_INPUT_SYMLINK'):
            pf.voice_tree(tree)

    def test_invalid_timeline_cannot_get_a_completion_receipt(self):
        def invalid(args, **kwargs):
            result = self.fake_voice(args, **kwargs)
            if 'voice' in args:
                path = self.work / 'timeline.json'
                data = json.loads(path.read_text())
                data['sentences'][0]['end'] = float('inf')
                path.write_text(json.dumps(data))
            return result
        with patch.object(pf.subprocess, 'run', side_effect=invalid):
            out = self.run_voice()
        self.assertFalse(out['ran'])
        self.assertFalse((self.work / 'voice-checkpoint.json').exists())
        self.assertEqual(self.calls, 1)


class Probes(unittest.TestCase):
    def talking_plan(self):
        """genesis-07 as it was before plan B: its three Keeper shots talking, lip-synced, on the same lines."""
        plan = json.loads(EXAMPLE.read_text())
        for s in plan["shots"]:
            if s["kind"] == "keeper":
                s["voiceover"] = False
        return plan

    def test_the_lips_rate_is_the_lines_own_and_genesis_07_talking_is_blocked(self):
        # PR #419: line-01 passed 7 of 14, genesis-07's own Keeper lines 1 of 33 with the same speaker, reference,
        # pose and binding. A probe on one line never vouches for another, and genesis-07 reads its real rates
        plan = self.talking_plan()
        chars = pf.ch.registry()
        probes = pf.load_probes()
        talking = [s["id"] for s in plan["shots"] if pf.plan_check.talking(s)]
        self.assertEqual(talking, ["k-insight", "k-question", "k-close"])
        self.assertEqual(pf.probe_rows(plan, chars, probes=[])[1], talking)
        only_line01 = [p for p in probes if pf.line_words(p.get("line", "")).startswith("genesis five")]
        self.assertEqual(pf.probe_rows(plan, chars, probes=only_line01)[1], talking)   # same setup, other line
        rows, missing, low, chance = pf.probe_rows(plan, chars, probes=probes)
        self.assertEqual(low, ["k-insight", "k-question"])                             # 0 of 15 each
        self.assertEqual(missing, ["k-close"])                                         # 1 of 3: too few to be a rate
        self.assertEqual({r["shot"]: r.get("passed") for r in rows if r.get("kind") == "talk"},
                         {"k-insight": "0 of 15", "k-question": "0 of 15", "k-close": None})
        self.assertIsNone(chance)
        # a new speaking frame is not covered by the old frame's probes
        changed = copy.deepcopy(probes)
        for p in changed:
            p["references"] = {"ch-keeper-talk": "0" * 64}
        self.assertEqual(pf.probe_rows(plan, chars, probes=changed)[1], talking)
        # lines that pass like line-01 are not blocked
        good = [dict(p, passed=7, generations=14) for p in probes]
        _, missing, low, chance = pf.probe_rows(plan, chars, probes=good)
        self.assertEqual((missing, low), ([], []))
        self.assertGreater(chance, 0.9)

    def test_a_voice_over_keeper_needs_its_still_mouth_probe_not_a_talking_one(self):
        # plan B (#423): no talking probe, but the still-mouth probes of its own prompt and talking frame
        plan = json.loads(EXAMPLE.read_text())
        chars = pf.ch.registry()
        probes = pf.load_probes()
        vo = [s["id"] for s in plan["shots"] if pf.plan_check.voiceover(s)]
        self.assertEqual(vo, ["k-insight", "k-question", "k-close"])
        talk_only = [p for p in probes if p.get("kind", "talk") == "talk"]
        self.assertEqual(pf.probe_rows(plan, chars, probes=talk_only)[1], vo)   # a talking probe never covers it
        rows, missing, low, chance = pf.probe_rows(plan, chars, probes=probes)
        self.assertEqual((missing, low), ([], []))
        self.assertEqual({r["shot"]: r["check"] for r in rows if r.get("kind") == "still_mouth"},
                         {k: "lipsync_check --still-mouth" for k in vo})
        self.assertGreater(chance, 0.99)
        # the prompt decides the face (keeper-vo/calibration.json): a changed prompt has no probe yet
        changed = copy.deepcopy(plan)
        changed["shots"][-1]["prompt"] = changed["shots"][-1]["prompt"].replace("faint warm smile", "warm smile")
        self.assertEqual(pf.probe_rows(changed, chars, probes=probes)[1], ["k-close"])
        # a prompt that failed its probes is PROBE_RATE_LOW
        failed = [dict(p, passed=0) if p.get("kind") == "still_mouth" else p for p in probes]
        self.assertEqual(pf.probe_rows(plan, chars, probes=failed)[2], vo)

    def test_the_committed_genesis_07_report_passes_on_its_voice_over_probes(self):
        report = json.loads((pf.REPORTS / "genesis-07-short.json").read_text())
        self.assertEqual((report["status"], report["blockers"]), ("PASS", []))
        self.assertEqual(report["setups"]["probes_required"], [])
        self.assertTrue({r["kind"] for r in report["setups"]["shots"]} <= {"still_mouth", "god_voice_over"})
        # E114 changed the build code it vouches for (stale by design, re-run once after merge): nothing else moved
        changed = pf.stale_parts(report["binding"], pf.binding(EXAMPLE, json.loads(EXAMPLE.read_text())))
        self.assertEqual([p for p in changed if not p.startswith("code:")], [])


class Report(unittest.TestCase):
    def test_pass_needs_every_step_and_binds_the_plan(self):
        r = pf.preflight(EXAMPLE, today_images=0)          # no --voice, no --refs: never a PASS
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(any(b.startswith("VOICE_NOT_MEASURED") for b in r["blockers"]))
        self.assertTrue(any(b.startswith("REQUESTS_NOT_CHECKED") for b in r["blockers"]))
        self.assertEqual(r["plan_check"]["problems"], [])

    def test_verify_refuses_a_missing_stale_or_blocked_report(self):
        saved = pf.REPORTS
        d = Path(tempfile.mkdtemp())
        try:
            pf.REPORTS = d / "reports"
            pf.REPORTS.mkdir()
            plan = d / EXAMPLE.name
            shutil.copyfile(EXAMPLE, plan)
            episode = json.loads(plan.read_text())["episode"]
            self.assertTrue(pf.verify(plan).startswith("PREFLIGHT_MISSING"))
            report = {"binding": pf.binding(plan, json.loads(plan.read_text())), "status": "BLOCKED",
                      "blockers": ["PROBE_REQUIRED s-x"]}
            (pf.REPORTS / f"{episode}.json").write_text(json.dumps(report))
            self.assertTrue(pf.verify(plan).startswith("PREFLIGHT_NOT_PASS PROBE_REQUIRED"))
            ids = [x["id"] for x in json.loads(plan.read_text())["shots"]]
            digests = {i: f"{k:064x}" for k, i in enumerate(ids)}
            needs = {i: 6 for i in ids}
            (pf.REPORTS / f"{episode}.json").write_text(json.dumps(dict(report, status="PASS", blockers=[],
                                                                        requests={"digests": digests, "needs": needs})))
            approvals = {i: {"request_sha256": digests[i], "clip_seconds": 6} for i in ids}
            self.assertIsNone(pf.verify(plan, approvals=approvals))
            plan.write_text(plan.read_text().replace("Genesis", "Genesis "))   # the plan changed after its preflight
            self.assertEqual(pf.verify(plan), "PREFLIGHT_STALE plan changed after the preflight; run it again")
        finally:
            pf.REPORTS = saved
            shutil.rmtree(d)

    def test_verify_refuses_an_unreviewed_shot(self):
        # E114 (genesis-07: 8 builds; genesis-08: 7 of 29 shots rejected after a full build): the build ships only
        # clips Claude reviewed, made from the request the plan sends now; the committed preflight holds its digests
        saved = pf.REPORTS
        d = Path(tempfile.mkdtemp())
        try:
            pf.REPORTS = d / "reports"
            pf.REPORTS.mkdir()
            plan = d / EXAMPLE.name
            shutil.copyfile(EXAMPLE, plan)
            data = json.loads(plan.read_text())
            ids = [x["id"] for x in data["shots"]]
            digests = {i: f"{k:064x}" for k, i in enumerate(ids)}
            needs = {i: 6 for i in ids}
            (pf.REPORTS / f"{data['episode']}.json").write_text(json.dumps(
                {"binding": pf.binding(plan, data), "status": "PASS", "blockers": [],
                 "requests": {"digests": digests, "needs": needs}}))
            approvals = {i: {"request_sha256": digests[i], "clip_seconds": 6} for i in ids[1:]}
            self.assertEqual(pf.verify(plan, approvals={}).split(" (")[0], "SHOT_NOT_REVIEWED " + " ".join(ids))
            self.assertEqual(pf.verify(plan, approvals=approvals).split(" (")[0], f"SHOT_NOT_REVIEWED {ids[0]}")
            approvals[ids[0]] = {"request_sha256": "0" * 64 + "x"}            # approved for another request
            self.assertEqual(pf.verify(plan, approvals=approvals).split(" (")[0], f"SHOT_REQUEST_CHANGED {ids[0]}")
            approvals[ids[0]] = {"request_sha256": digests[ids[0]], "clip_seconds": 6}
            self.assertIsNone(pf.verify(plan, approvals=approvals))
            # E118: a clip shorter than the preflight's measured layout needs is refused before any secret (and one
            # with no recorded clip seconds, or a report with no needs, covers nothing)
            approvals[ids[0]] = dict(approvals[ids[0]], clip_seconds=5)
            self.assertEqual(pf.verify(plan, approvals=approvals).split(" (")[0], f"SHOT_CLIP_TOO_SHORT {ids[0]}(5<6)")
            approvals[ids[0]] = {"request_sha256": digests[ids[0]]}
            self.assertTrue(pf.verify(plan, approvals=approvals).startswith(f"SHOT_CLIP_TOO_SHORT {ids[0]}(None<6)"))
            approvals[ids[0]] = {"request_sha256": digests[ids[0]], "clip_seconds": 7}   # longer covers
            self.assertIsNone(pf.verify(plan, approvals=approvals))
            (pf.REPORTS / f"{data['episode']}.json").write_text(json.dumps(
                {"binding": pf.binding(plan, data), "status": "PASS", "blockers": [], "requests": {"digests": digests}}))
            self.assertTrue(pf.verify(plan, approvals=approvals).startswith("SHOT_CLIP_TOO_SHORT"))
            # a report written before E114 holds no digests: every approved shot is a changed request
            (pf.REPORTS / f"{data['episode']}.json").write_text(json.dumps(
                {"binding": pf.binding(plan, data), "status": "PASS", "blockers": []}))
            self.assertTrue(pf.verify(plan, approvals=approvals).startswith("SHOT_REQUEST_CHANGED"))
        finally:
            pf.REPORTS = saved
            shutil.rmtree(d)

    def test_the_binding_holds_what_the_plan_uses_and_names_what_changed(self):
        # review of #422: approving another character leaves the report valid; a used character, its image
        # records, its probes or the build code each make it stale, by name
        plan = json.loads(EXAMPLE.read_text())
        raw = json.loads(pf.CHARACTERS.read_text())
        base = pf.binding(EXAMPLE, plan, raw)
        other = copy.deepcopy(raw)
        other["characters"]["noah"]["status"] = "APPROVED"            # not in genesis-07
        self.assertEqual(pf.stale_parts(base, pf.binding(EXAMPLE, plan, other)), [])
        used = copy.deepcopy(raw)
        used["characters"]["keeper"]["voice"] = "am_adam"
        self.assertEqual(pf.stale_parts(base, pf.binding(EXAMPLE, plan, used)), ["characters"])
        probes = [dict(p, passed=1) if p.get("kind") == "still_mouth" else p for p in pf.load_probes()]
        self.assertEqual(pf.stale_parts(base, pf.binding(EXAMPLE, plan, raw, probes)), ["setups"])
        old = dict(base, code=dict(base["code"], **{"episode_build.py": "0" * 64}),
                   image_records=dict(base["image_records"], **{"ch-keeper-talk.json": "0" * 64}))
        self.assertEqual(pf.stale_parts(old, base), ["code:episode_build.py", "image_records:ch-keeper-talk.json"])
        self.assertEqual(sorted(base["code"]), sorted(p.name for p in pf.CODE))

    def test_a_crafted_episode_id_is_refused_before_any_path(self):
        # review of #422: preflight built .episode/preflight-<episode> and evidence/preflight/<episode>.json from the
        # plan's own field, and voice_step removed that directory: "x/../../migration" would delete the repository
        d = Path(tempfile.mkdtemp())
        try:
            for bad in ("x/../../migration", "../x", "", "Genesis-07", "a--b"):
                plan = dict(json.loads(EXAMPLE.read_text()), episode=bad)
                path = d / "plan.json"
                path.write_text(json.dumps(plan))
                for call in (lambda: pf.preflight(path, voice=("py", str(d)), today_images=0),
                             lambda: pf.verify(path), lambda: pf.report_path(plan, path)):
                    with self.assertRaises(SystemExit) as err:
                        call()
                    self.assertTrue(str(err.exception).startswith("EPISODE_ID_REFUSED"), bad)
            # a valid id that is not the file's name is refused too
            path = d / "other.json"
            path.write_text(EXAMPLE.read_text())
            with self.assertRaises(SystemExit):
                pf.verify(path)
        finally:
            shutil.rmtree(d)
        # every removal stays inside its root: never the root, never outside it, never through a link
        root = Path(tempfile.mkdtemp(dir=pf.REPO, prefix=".test-rm-"))
        try:
            inside = root / "w"
            inside.mkdir()
            for bad in (root, root / ".." / "migration", pf.REPO):
                with self.assertRaises(SystemExit) as err:
                    pf.eb.safe_rmtree(bad, root)
                self.assertTrue(str(err.exception).startswith("RMTREE_REFUSED"))
            link = root / "link"
            link.symlink_to(pf.REPO / "migration")
            with self.assertRaises(SystemExit):
                pf.eb.safe_rmtree(link, root)
            self.assertTrue((pf.REPO / "migration").is_dir())
            pf.eb.safe_rmtree(inside, root)
            self.assertFalse(inside.exists())
        finally:
            shutil.rmtree(root)

    def test_the_workflow_runs_verify_before_any_secret(self):
        wf = (pf.REPO / ".github" / "workflows" / "episode.yml").read_text()
        verify = wf.index("episode_build.py verify-preflight")
        self.assertNotIn("secrets.", wf)                  # E114: the build holds no Pavo secret at all
        self.assertLess(verify, wf.index("pilot_render.py voice"))
        self.assertLess(verify, wf.index("episode_build.py generate"))

    def test_the_still_mouth_negative_control_requires_mouth_talking(self):
        # review of #422: any nonzero exit counted as "flagged"; only MOUTH_TALKING proves the check sees a mouth
        wf = (pf.REPO / ".github" / "workflows" / "episode.yml").read_text()
        start = wf.index("python3 -I - \"$RUNNER_TEMP/still.json\" <<'PY'")
        end = wf.index("\n", wf.index("          PY", start))
        snippet = "\n".join(line[10:] for line in wf[start - 10:end].splitlines()) + "\n"
        d = Path(tempfile.mkdtemp())
        try:
            (d / "s.sh").write_text(snippet)
            for out, ok in (('{"flags": ["MOUTH_TALKING", "MOUTH_NOT_CLOSED"]}', True),
                            ('{"flags": ["FACE_NOT_FOUND"]}', False), ("Traceback ...", False), ("", False)):
                (d / "still.json").write_text(out + "\n")
                done = subprocess.run(["bash", str(d / "s.sh")], env={"RUNNER_TEMP": str(d), "PATH": "/usr/bin:/bin"},
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode == 0, ok, out)
                if not ok:
                    self.assertIn("STILL_MOUTH_CHECK_BLIND", done.stderr)
        finally:
            shutil.rmtree(d)

    def test_a_committed_report_says_pass_only_with_no_blocker(self):
        for path in sorted(pf.REPORTS.glob("*.json")):
            report = json.loads(path.read_text())
            self.assertIn(report["status"], ("PASS", "BLOCKED"), path.name)
            self.assertEqual(report["status"] == "PASS", report["blockers"] == [], path.name)

    def test_the_command_line_has_a_usage_and_the_pace_never_divides_by_zero(self):
        with self.assertRaises(SystemExit):
            pf.main(["episode_build.py", "preflight"])            # argparse: usage, not an IndexError
        with self.assertRaises(SystemExit):
            pf.main(["episode_build.py", "preflight", str(EXAMPLE), "--voice", "py"])
        d = Path(tempfile.mkdtemp())
        try:
            plan = json.loads(EXAMPLE.read_text())
            items, _ = pf.plan_check.sequence(plan)
            (d / "timeline.json").write_text(json.dumps({"sentences": [
                {"segment": f"n{k:02d}", "start": 1.0, "end": 1.0 if k == 0 else 3.0} for k in range(len(items))]}))
            pace = pf.measured_pace(plan, d)
            self.assertIn(None, [p for v in pace.values() for p in v])
        finally:
            shutil.rmtree(d)


class Messages(unittest.TestCase):
    def test_a_voice_over_probe_required_names_its_own_minimum_and_match(self):
        plan = json.loads(EXAMPLE.read_text())
        rows = pf.probe_rows(plan, pf.ch.registry(), probes=[])[0]
        vo = [r for r in rows if r.get("kind") == "still_mouth"][0]
        message = pf.probe_required(vo)
        self.assertIn(f">= {pf.MIN_VO_PROBE_GENERATIONS} ", message)
        self.assertIn("exact prompt", message)
        self.assertIn("talking reference frame", message)
        self.assertIn("--still-mouth", message)

    def test_a_failing_request_is_a_named_refusal_never_a_crash(self):
        plan = json.loads(EXAMPLE.read_text())

        class Broken:
            def prepare_video(self, *a):
                raise RuntimeError("adapter blew up")

            def _plan(self, *a):
                raise AssertionError("never reached")

        from client import PavoError

        class Empty:
            def prepare_video(self, *a):
                raise PavoError("")

        layout = {"keeper": {}, "speakers": {}}
        for client, word in ((Broken(), "RuntimeError"), (Empty(), "PavoError")):
            one = {"shots": plan["shots"][:1], "aspect_ratio": "9:16", "period": plan["period"]}   # E108: its period
            out = pf.eb.request_problems(one, layout, {"keeper:talk": ["x.jpg"]}, client)
            self.assertEqual(len(out), 1)
            self.assertTrue(out[0].startswith("PAVO_REQUEST_INVALID") and word in out[0], out)


class Allocation(unittest.TestCase):
    def test_today_counts_the_image_records_cf_images_commits(self):
        class Done:
            returncode = 0
            stdout = ("\0Record characters images from Cloudflare Workers AI (flux, run 1)\n\n"
                      "migration/production/characters/images/ch-noah-front.json\n"
                      "migration/production/characters/images/ch-noah-front.png\n"
                      "\0Record pilot-015 images from Cloudflare Workers AI (flux, run 2)\n\n"
                      "migration/production/pilot-015/images/a.json\n"
                      "\0Record pilot-016 images from Cloudflare Workers AI (sdxl, run 3)\n\n"   # E116: FLUX only
                      "migration/production/pilot-016/images/b.json\n")
        self.assertEqual(pf.cf_images_today("2026-10-26", run=lambda *a, **k: Done()), 2)


class Record(unittest.TestCase):
    def test_the_record_is_checked_with_publish_episode_rules_before_dispatch(self):
        rec = json.loads((HERE / "episodes" / "genesis-06-short.json").read_text())
        self.assertEqual(pf.record_problems(rec), [])
        bad = dict(rec, title="x" * 101, description=rec["description"].replace("(public domain)", ""))
        self.assertEqual(pf.record_problems(bad), ["TITLE_LENGTH", "DISCLOSURE_MISSING"])
        # review of #422: it is publish_episode.problems itself, not a copy of its rules
        pe, saved = pf.plan_check.publish_episode, pf.plan_check.publish_episode.problems
        try:
            pe.problems = lambda episode, video=None: ["FROM_PUBLISH_EPISODE", video]
            self.assertEqual(pf.record_problems(rec, "v.mp4"), ["FROM_PUBLISH_EPISODE", "v.mp4"])
        finally:
            pe.problems = saved
        self.assertEqual(pf.record_problems({"narration": rec.get("narration", [])}), ["RECORD_FIELD_MISSING title"])


if __name__ == "__main__":
    unittest.main()
