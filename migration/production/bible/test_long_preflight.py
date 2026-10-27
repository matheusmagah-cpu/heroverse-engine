#!/usr/bin/env python3
"""E127: the Bible-story long gets the Shorts' no-rework contract. A long preflight (long_plan_check --strict, the
frozen story QA, the plan, characters, references, voices and probes bound by sha256, and no review row open) is
required before its build; its shots are probed by shot-probe.yml (16:9, its own shot ids, windows excluded) and
approved into shots/<long>.json; the build ships approved clips only; the riskiest shots go first and the queue
resumes where the approvals stop."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "integrations" / "pavo"))
sys.path.insert(0, str(ROOT / "migration" / "ops"))
import episode_build as eb  # noqa: E402
import episode_preflight as pf  # noqa: E402
import long_plan_check as lpc  # noqa: E402
import long_preflight as lp  # noqa: E402

LONG = HERE / "plans" / "arc-01-long.json"
REAL_REGISTRY = lp.REGISTRY
WORKFLOWS = ROOT / ".github" / "workflows"


def registry(open_names=()):
    """ops/refusal_registry.json with every long review row closed but `open_names`."""
    data = json.loads(REAL_REGISTRY.read_text())
    for k, v in data["review"]["story_qa_v3"].items():
        v["class"] = "open" if f"story_qa_v3.{k}" in open_names else "plan"
    for k, v in data["review"]["rubric"].items():
        if isinstance(v.get("long"), dict):
            v["long"]["class"] = "open" if f"rubric.{k}.long" in open_names else "plan"
    return data


def estimate_durations(plan):
    items, _ = eb.plan_check.sequence(plan)
    return [eb.plan_check.words(x["text"]) / lpc.pace(x) for x in items]


class Scratch(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.saved = (pf.REPORTS, lp.REGISTRY)
        pf.REPORTS = self.dir / "reports"
        pf.REPORTS.mkdir()
        lp.REGISTRY = self.dir / "registry.json"
        lp.REGISTRY.write_text(json.dumps(registry()))
        self.plan_path = self.dir / LONG.name
        shutil.copyfile(LONG, self.plan_path)
        self.plan = json.loads(LONG.read_text())

    def tearDown(self):
        pf.REPORTS, lp.REGISTRY = self.saved
        shutil.rmtree(self.dir)

    def generated(self):
        return [s["id"] for s in self.plan["shots"] if not eb.is_window(s)]


class Preflight(Scratch):
    def test_the_long_preflight_refuses_while_a_review_row_is_open(self):
        # the rework E106 forbids: a story QA v3 row with no earlier check is met first at the review, after the build
        lp.REGISTRY.write_text(json.dumps(registry({"story_qa_v3.grammar.caption_track", "rubric.audio_clarity_and_mix.long"})))
        r = pf.preflight(self.plan_path, setups=[], today_images=0)
        rows = [b for b in r["blockers"] if b.startswith("LONG_REVIEW_OPEN")]
        self.assertEqual(len(rows), 1, r["blockers"])
        self.assertIn("story_qa_v3.grammar.caption_track", rows[0])
        self.assertIn("rubric.audio_clarity_and_mix.long", rows[0])
        self.assertEqual(r["review_rows"]["open"], ["rubric.audio_clarity_and_mix.long",
                                                    "story_qa_v3.grammar.caption_track"])
        lp.REGISTRY.write_text(json.dumps(registry()))
        r = pf.preflight(self.plan_path, setups=[], today_images=0)
        self.assertFalse([b for b in r["blockers"] if b.startswith("LONG_REVIEW_OPEN")])
        # #469 (E126) closed every long review row: on main the long is no longer blocked by them
        self.assertEqual(lp.open_rows(json.loads(self.saved[1].read_text())), [])

    def test_the_long_plan_is_checked_by_long_plan_check_strict_and_the_frozen_qa(self):
        r = pf.preflight(LONG, setups=[], today_images=0)
        self.assertEqual((r["plan_check"]["problems"], r["plan_check"]["pending"]), ([], []))
        self.assertIn("LONG_LENGTH", json.dumps(lpc.check(dict(self.plan, shots=self.plan["shots"][:60]))))
        broken = dict(self.plan, aspect_ratio="9:16")
        self.plan_path.write_text(json.dumps(broken))
        r = pf.preflight(self.plan_path, setups=[], today_images=0)
        self.assertTrue(any(b.startswith("PLAN ASPECT_RATIO") for b in r["blockers"]), r["blockers"])
        unnamed = {k: v for k, v in self.plan.items() if k != "episode"}
        self.assertIn("LONG_EPISODE_ID", " ".join(eb.check_plan(unnamed)["problems"]))
        self.assertEqual(eb.LONG_VERSION, lpc.VERSION)

    def test_the_report_binds_the_plan_characters_voices_refs_probes_and_review_rows(self):
        base = pf.binding(self.plan_path, self.plan)
        self.assertIn("review", base)
        self.assertIn("long_preflight.py", base["long_code"])
        chars = json.loads(pf.CHARACTERS.read_text())
        changed = copy.deepcopy(chars)
        changed["characters"]["eve"]["voice"] = {"voice_id": "af_bella", "speed": 1.0}   # another voice for Eve
        self.assertEqual(pf.stale_parts(base, pf.binding(self.plan_path, self.plan, chars_raw=changed)),
                         ["characters"])
        lp.REGISTRY.write_text(json.dumps(registry({"story_qa_v3.technical.video"})))
        self.assertEqual(pf.stale_parts(base, pf.binding(self.plan_path, self.plan)), ["review"])
        self.assertTrue(base["image_records"])   # the references of every character it uses, by record sha256

    def test_verify_requires_a_pass_report_no_open_row_and_an_approved_clip_for_every_generated_shot(self):
        self.assertTrue(pf.verify(self.plan_path).startswith("PREFLIGHT_MISSING"))
        ids = self.generated()
        digests = {i: f"{k:064x}" for k, i in enumerate(ids)}
        needs = {i: 6 for i in ids}
        report = {"binding": pf.binding(self.plan_path, self.plan), "status": "PASS", "blockers": [],
                  "requests": {"digests": digests, "needs": needs}}
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(report))
        approvals = {i: {"request_sha256": digests[i], "clip_seconds": 6} for i in ids}
        self.assertIsNone(pf.verify(self.plan_path, approvals=approvals))   # windows need no clip of their own
        missing = pf.verify(self.plan_path, approvals={k: v for k, v in approvals.items() if k != "s-open"})
        self.assertEqual(missing.split(" (")[0], "SHOT_NOT_REVIEWED s-open")
        self.assertFalse(any(eb.is_window(s) and s["id"] in missing for s in self.plan["shots"]))
        # a review row reopened after a PASS report: stale, and refused by name
        lp.REGISTRY.write_text(json.dumps(registry({"story_qa_v3.technical.video"})))
        self.assertTrue(pf.verify(self.plan_path, approvals=approvals).startswith("PREFLIGHT_STALE review"))
        report["binding"] = pf.binding(self.plan_path, self.plan)
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(report))
        self.assertTrue(pf.verify(self.plan_path, approvals=approvals).startswith("LONG_REVIEW_OPEN 1 rows"))


class ApprovedShots(Scratch):
    def layout_and_refs(self):
        _, layout = eb.predict(self.plan, estimate_durations(self.plan))
        for folder in ("keeper", "speakers"):
            for sid, rec in layout[folder].items():
                rec["wav"] = f".episode/test/{folder}/{sid}.wav"
        return layout, eb.ref_paths(self.plan, ROOT / ".episode" / "test")

    def test_the_long_layout_is_measured_at_its_own_gap_and_gate(self):
        durations = estimate_durations(self.plan)
        problems, layout = eb.predict(self.plan, durations)
        self.assertEqual(problems, [])
        self.assertAlmostEqual(layout["lines"][1]["start"] - layout["lines"][0]["end"], lpc.LONG_LINE_GAP, places=3)
        self.assertIsNone(layout["lesson_share"])
        problems, _ = eb.predict(self.plan, [d * 1.3 for d in durations])   # ~18.9 min: over the gate
        self.assertTrue(any(p.startswith("LONG_LENGTH") for p in problems), problems)

    def test_every_generated_shot_has_a_16x9_request_digest_and_windows_have_none(self):
        layout, refs = self.layout_and_refs()
        digests = eb.request_digests(self.plan, layout, refs)
        self.assertEqual(sorted(digests), sorted(self.generated()))
        self.assertEqual(len(digests), 164)
        i, shot = next((i, s) for i, s in enumerate(self.plan["shots"]) if s["id"] == "s-c1-light")
        self.assertEqual(eb.request_identity(shot, i, self.plan, layout, refs)[1]["aspect_ratio"], "16:9")
        self.assertEqual(sorted(eb.clip_needs(self.plan, layout)), sorted(self.generated()))
        self.assertEqual(eb.request_problems(self.plan, layout, refs, client=type("C", (), {
            "prepare_video": lambda *a: None, "_plan": lambda *a: None})()), [])
        self.assertEqual(eb.shots_path(self.plan).name, "arc-01-long.json")   # approve-shot writes here

    def test_the_build_ships_approved_clips_only(self):
        layout, refs = self.layout_and_refs()
        work = ROOT / ".episode" / f"test-long-{os.getpid()}"
        try:
            work.mkdir(parents=True)
            eb.save(work / "layout.json", layout)
            eb.save(work / "refs.json", refs)
            with self.assertRaises(SystemExit) as c:   # no approval: nothing is generated, the build stops first
                eb.generate_step(self.plan, work, "python", "face.task", approvals={})
            self.assertTrue(str(c.exception).startswith("SHOT_NOT_REVIEWED s-"), str(c.exception)[:80])
            self.assertNotIn("s-c3-window", str(c.exception))
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_shot_probe_takes_the_long_plan_and_refuses_windows_and_an_unclean_preflight(self):
        wf = (WORKFLOWS / "shot-probe.yml").read_text()
        step = wf.split("- id: plan", 1)[1].split("\n      - ", 1)[0]
        self.assertIn("long_plan_check.py \"$PLAN\" --strict", step)
        self.assertLess(step.index("long_plan_check.py"), step.index("episode_build.py check-probe"))
        self.assertEqual(int(re.search(r"timeout-minutes: (\d+)", wf.split("  probe:", 1)[1]).group(1)),
                         lp.PROBE_JOB_MINUTES)
        window = next(s["id"] for s in self.plan["shots"] if eb.is_window(s))
        with self.assertRaises(SystemExit) as c:
            eb.probe_ids(self.plan, f"s-open,{window}", 2)
        self.assertTrue(str(c.exception).startswith("PROBE_WINDOW_SHOT"))
        self.assertEqual(eb.probe_ids(self.plan, "s-open", 2), (["s-open"], 2))
        import dispatch_guard as g
        with self.assertRaises(g.Refusal):
            g.WORKFLOWS["shot-probe.yml"][1]({"plan": "migration/production/bible/plans/arc-01-long.json",
                                              "shots": window, "attempts": "2"})
        # the probe gate: no report, a stale one, a blocked one; open review rows and talking probes do not block it
        self.assertTrue(lp.probe_gate(self.plan_path).startswith("LONG_PROBE_PREFLIGHT arc-01-long.json missing"))
        report = {"binding": pf.binding(self.plan_path, self.plan), "status": "BLOCKED",
                  "blockers": ["PROBE_REQUIRED s-open (...)", "LONG_REVIEW_OPEN 25 rows: ..."],
                  "requests": {"digests": {"s-open": "0" * 64}}}
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(report))
        self.assertIsNone(lp.probe_gate(self.plan_path))
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(dict(report, blockers=["VOICE_NOT_MEASURED (...)"])))
        self.assertTrue(lp.probe_gate(self.plan_path).startswith("LONG_PROBE_PREFLIGHT blocked: VOICE_NOT_MEASURED"))
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(report))
        self.plan_path.write_text(self.plan_path.read_text().replace("Genesis", "Genesis "))
        self.assertTrue(lp.probe_gate(self.plan_path).startswith("LONG_PROBE_PREFLIGHT stale: plan"))


class RiskAndResume(Scratch):
    def test_the_riskiest_shots_go_first_talking_characters_then_the_keeper_then_wide_shots(self):
        order = eb.risk_order(self.plan["shots"])
        ranks = [eb.risk_rank(s) for _, s in order]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual([s["id"] for _, s in order[:6]],
                         ["s-open", "s-c2-adam", "s-c3-eve", "s-c4-adam", "s-c4-blame", "s-c4-eve"])
        self.assertTrue(all(s["kind"] == "keeper" for _, s in order[6:20]))
        self.assertTrue(all(eb.plan_check.speaking(s) for _, s in order[20:29]))   # God's voice-over
        wide = [s for _, s in order if eb.risk_rank(s) == 3]
        self.assertTrue(wide and all(s.get("establishing") or "wide shot" in s["prompt"].lower()
                                     or "aerial" in s["prompt"].lower() for s in wide))
        self.assertFalse([s for _, s in order if eb.is_window(s)])
        self.assertEqual(sorted(i for i, _ in order), [i for i, s in enumerate(self.plan["shots"])
                                                         if not eb.is_window(s)])

    def test_the_queue_resumes_where_the_approvals_stop_in_batches_that_fit_one_run(self):
        ids = self.generated()
        digests = {i: f"{k:064x}" for k, i in enumerate(ids)}
        q = lp.queue(self.plan, digests, {})
        self.assertEqual(q["to_probe"], 164)
        self.assertEqual(q["batches"][0]["shots"].split(",")[0], "s-open")
        for b in q["batches"]:
            self.assertLessEqual(b["minutes_est"], lp.PROBE_JOB_MINUTES - lp.PROBE_SETUP_MINUTES)
            self.assertEqual(len({eb.risk_rank(s) for s in self.plan["shots"] if s["id"] in b["shots"].split(",")}), 1)
        self.assertEqual(sum(len(b["shots"].split(",")) for b in q["batches"]), 164)
        approvals = {i: {"request_sha256": digests[i], "clip_seconds": 6} for i in ids[:100]}
        approvals["s-open"] = {"request_sha256": "f" * 64, "clip_seconds": 6}   # approved for another request
        q = lp.queue(self.plan, digests, approvals)
        left = [x for b in q["batches"] for x in b["shots"].split(",")]
        self.assertEqual(q["approved"], 99)
        self.assertEqual(left[0], "s-open")
        self.assertEqual(sorted(left), sorted(set(ids[100:]) | {"s-open"}))

    def test_the_production_estimate_accounts_for_every_generated_shot(self):
        e = lp.estimate(self.plan)
        s = e["shots"]
        self.assertEqual(s["generated"] + s["windows"], s["holds"])
        parts = (s["talking_character_reference_video"]["n"] + s["talking_keeper_reference_video"]["n"]
                 + s["god_voice_over_text_to_video"]["n"] + s["character_reference_video"]["n"]
                 + s["image_first_still_needed"]["n"] + s["direct_text_to_video"]["n"])
        self.assertEqual(parts, s["generated"])
        self.assertEqual(s["prop_guided"]["n"], 0)   # Eden: no prop of props.json
        self.assertEqual(e["time"]["shot_probe_runs"], len(lp.queue(self.plan, {}, {})["batches"]))
        written = ROOT / "migration" / "evidence" / "long" / "20261027" / "arc-01-long-production-estimate.json"
        self.assertEqual(json.loads(written.read_text())["shots"], s)   # the committed estimate is this plan's


class ReviewOf468(Scratch):
    def run_cli(self, *args, env=None):
        import subprocess
        return subprocess.run([sys.executable, "-I", "-B", str(HERE / "episode_build.py"), *args],
                              capture_output=True, text=True, env=dict(os.environ, **(env or {})), cwd=str(ROOT))

    def test_only_a_long_probe_depends_on_its_preflight_report(self):
        # a Short's new preflight report is no fix that lifts GUARD_RERUN_WITHOUT_FIX for its probes
        import dispatch_guard as g
        probe = g.WORKFLOWS["shot-probe.yml"][1]
        short = probe({"plan": "migration/production/bible/plans/genesis-09-short.json", "shots": "s-voice",
                       "attempts": "2"})
        self.assertFalse([d for d in short["deps"] if "evidence/preflight" in d])
        long_ = probe({"plan": "migration/production/bible/plans/arc-01-long.json", "shots": "s-open", "attempts": "2"})
        self.assertIn("migration/evidence/preflight/arc-01-long.json", long_["deps"])

    def test_a_batch_is_packed_to_seventy_percent_of_the_probe_timeout(self):
        self.assertLessEqual(lp.batch_budget(), 0.7 * lp.PROBE_JOB_MINUTES - lp.PROBE_SETUP_MINUTES)
        q = lp.queue(self.plan, {}, {})
        self.assertTrue(all(b["minutes_est"] <= lp.batch_budget() for b in q["batches"]), q["batches"])
        # a batch whose shots all regenerate 1.4x the mean still ends inside the job's timeout
        self.assertTrue(all(b["minutes_est"] * 1.4 + lp.PROBE_SETUP_MINUTES <= lp.PROBE_JOB_MINUTES
                            for b in q["batches"]))

    def test_a_clip_of_another_shape_than_the_plan_asks_is_refused(self):
        import clip_check
        info = {"width": 720, "height": 1280, "fps": 24.0}
        self.assertIn("CLIP_ASPECT_MISMATCH", clip_check.flags(info, [80], [80], aspect="16:9"))
        self.assertNotIn("CLIP_ASPECT_MISMATCH", clip_check.flags(info, [80], [80], aspect="9:16"))
        self.assertNotIn("CLIP_ASPECT_MISMATCH", clip_check.flags(dict(info, width=1280, height=720), [80], [80],
                                                                  aspect="16:9"))
        self.assertNotIn("CLIP_ASPECT_MISMATCH", clip_check.flags(info, [80], [80]))
        # the build's own check (probe, adopt, ship) asks for the plan's aspect
        seen = []
        saved = eb.clip_flags
        eb.clip_flags = lambda path, aspect=None: seen.append(aspect) or []
        try:
            i, shot = next((i, s) for i, s in enumerate(self.plan["shots"]) if s["id"] == "s-c1-light")
            check = eb.shot_runner(shot, i, self.plan, {}, {}, ROOT / ".episode" / "unused", None, None, "py",
                                   "face")[2]
            self.assertEqual(check("clip.mp4"), ([], None))
        finally:
            eb.clip_flags = saved
            shutil.rmtree(ROOT / ".episode" / "unused", ignore_errors=True)
        self.assertEqual(seen, ["16:9"])

    def test_the_estimate_is_dated_today_by_default(self):
        from datetime import datetime, timezone
        self.assertEqual(lp.estimate(self.plan)["date"], datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        self.assertEqual(lp.estimate(self.plan, "2026-10-27")["date"], "2026-10-27")

    def test_estimate_write_refuses_an_episode_id_that_is_not_a_file_name(self):
        bad = dict(self.plan, episode="../../escape")
        self.plan_path.write_text(json.dumps(bad))
        with self.assertRaises(SystemExit) as c:
            lp.main(["long_preflight.py", "estimate", str(self.plan_path), "--write"])
        self.assertTrue(str(c.exception).startswith("EPISODE_ID_REFUSED"))
        self.assertFalse((lp.ESTIMATES.parent / "escape-production-estimate.json").exists())

    def test_the_probe_gate_refuses_a_report_without_request_digests(self):
        report = {"binding": pf.binding(self.plan_path, self.plan), "status": "BLOCKED",
                  "blockers": ["LONG_REVIEW_OPEN 25 rows: ..."], "requests": {"ran": False}}
        (pf.REPORTS / "arc-01-long.json").write_text(json.dumps(report))
        self.assertTrue(lp.probe_gate(self.plan_path).startswith("LONG_PROBE_PREFLIGHT no request digests"))

    def test_the_long_layout_refuses_a_keeper_share_over_its_gate(self):
        saved = lpc.gate
        lpc.gate = lambda: dict(saved(), keeper_share_max=0.01)
        try:
            problems, _ = eb.predict(self.plan, estimate_durations(self.plan))
        finally:
            lpc.gate = saved
        self.assertTrue(any(p.startswith("KEEPER_SHARE") and p.endswith("(measured)") for p in problems), problems)

    def test_an_unfrozen_story_qa_blocks_the_long_preflight(self):
        saved = lpc.QA_SHA256
        lpc.QA_SHA256 = "0" * 64
        try:
            r = pf.preflight(LONG, setups=[], today_images=0)
        finally:
            lpc.QA_SHA256 = saved
        self.assertTrue(any(b.startswith("PLAN QA_NOT_FROZEN") for b in r["blockers"]), r["blockers"])

    def test_check_probe_and_probe_queue_are_wired_for_the_long(self):
        plan = "migration/production/bible/plans/arc-01-long.json"
        if (ROOT / "migration" / "evidence" / "preflight" / "arc-01-long.json").exists():
            self.skipTest("a committed long preflight exists: the refusals below need none")
        done = self.run_cli("check-probe", plan, env={"SHOTS": "s-open", "ATTEMPTS": "2"})
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("LONG_PROBE_PREFLIGHT", done.stderr)
        done = self.run_cli("check-probe", plan, env={"SHOTS": "s-ki-trees", "ATTEMPTS": "2"})   # a window
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("PROBE_WINDOW_SHOT", done.stderr)
        done = self.run_cli("probe-queue", plan)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("PREFLIGHT_MISSING", done.stderr)


class Contract(unittest.TestCase):
    def test_every_plan_kind_in_plans_has_the_preflight_and_approved_shot_contract(self):
        # E127 (class review-after-build, cheap-vs-expensive): the long existed beside the Shorts with none of their
        # no-rework contract (E106 preflight, E114 approved shots, E99 risk order). Every kind of plan in plans/ must
        # be one the engine's plan check, preflight, verify-preflight, shot-probe.yml and approve-shot all take.
        contract = {"bible-plan-v2": "plan_check.py", eb.LONG_VERSION: "long_plan_check.py"}
        wf = (WORKFLOWS / "shot-probe.yml").read_text()
        for path in sorted((HERE / "plans").glob("*.json")):
            plan = json.loads(path.read_text())
            self.assertIn(plan.get("version"), contract, f"{path.name}: a plan kind with no preflight contract")
            self.assertIn(contract[plan["version"]], wf, path.name)
            self.assertEqual(plan.get("episode"), path.stem, path.name)          # shot-probe, the guard, shots/
            self.assertIsInstance(eb.check_plan(plan), dict, path.name)
            self.assertTrue(pf.binding(path, plan)["plan"], path.name)          # preflight binds it
            self.assertEqual(eb.shots_path(plan).name, path.name)               # approve-shot's file
            for _, s in eb.risk_order(plan["shots"]):
                self.assertFalse(eb.is_window(s), path.name)
        # a build that ships clips runs verify-preflight first and holds no Pavo secret (episode.yml; the long's
        # build, LONG_DESIGN slice 3, must do the same)
        for w in sorted(WORKFLOWS.glob("*.yml")):
            text = w.read_text()
            if "episode_build.py generate" in text or "bible/long_build.py " in text:
                self.assertIn("verify-preflight", text, w.name)
                self.assertLess(text.index("verify-preflight"), text.index("episode_build.py generate"), w.name)
                self.assertNotIn("PAVO_TOKEN", text, w.name)


class PavoBudgetQueue(Scratch):
    """E128: probe-queue cut batches by minutes only; a batch could plan more Pavo generations than the free-model
    quota left that day (run 40592173923 burned 24 submissions on a spent quota). Each batch now names its expected
    units, none is larger than a day's cap, and the queue says whether the next one fits today's budget."""
    def test_every_batch_names_its_units_and_fits_a_day(self):
        import quota
        q = lp.queue(self.plan, {}, {})
        cap = quota.QuotaGuard(actions=None).cap()
        for b in q["batches"]:
            shots = [s for s in self.plan["shots"] if s["id"] in b["shots"].split(",")]
            self.assertEqual(b["pavo_units_est"], lp.planned_units(shots, b["attempts"]))
            self.assertLessEqual(b["pavo_units_est"], cap)
        small = lp.queue(self.plan, {}, {}, max_units=10)
        self.assertTrue(all(b["pavo_units_est"] <= 10 for b in small["batches"]), small["batches"])
        self.assertEqual(sum(len(b["shots"].split(",")) for b in small["batches"]), q["to_probe"])

    def test_the_queue_says_when_the_next_batch_does_not_fit_today(self):
        import quota
        from datetime import datetime, timezone
        ledger = self.dir / "ledger.json"
        ledger.write_text(json.dumps({"days": {"2026-10-27": {"generated": 251}}}))
        now = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)
        guard = quota.QuotaGuard(ledger, now=lambda: now, actions=lambda day: quota.NO_ACTIONS)
        got = lp.budget_today([{"pavo_units_est": 10}], guard)
        self.assertEqual(got["next_batch"], "refused")
        self.assertTrue(got["refusal"].startswith("PAVO_BUDGET_SHORT"), got)
        ledger.write_text(json.dumps({"days": {"2026-10-27": {"generated": 100}}}))
        self.assertEqual(lp.budget_today([{"pavo_units_est": 10}], guard)["remaining"], 10)


if __name__ == "__main__":
    unittest.main()
