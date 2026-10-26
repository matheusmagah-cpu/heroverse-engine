#!/usr/bin/env python3
"""episode_preflight.py (E106): a build is dispatched only after a local preflight of that exact plan says PASS, and
the preflight names each talking setup that needs a direct 0-credit Pavo probe first."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import episode_preflight as pf  # noqa: E402

EXAMPLE = HERE / "plans" / "genesis-07-short.json"


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
        self.assertIsNone(pf.verify(EXAMPLE))


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
            pf.REPORTS = d
            plan = d / "p.json"
            shutil.copyfile(EXAMPLE, plan)
            episode = json.loads(plan.read_text())["episode"]
            self.assertTrue(pf.verify(plan).startswith("PREFLIGHT_MISSING"))
            report = {"plan_sha256": pf.sha256(plan), "characters_sha256": pf.sha256(pf.CHARACTERS), "status": "BLOCKED",
                      "blockers": ["PROBE_REQUIRED s-x"]}
            (d / f"{episode}.json").write_text(json.dumps(report))
            self.assertTrue(pf.verify(plan).startswith("PREFLIGHT_NOT_PASS PROBE_REQUIRED"))
            (d / f"{episode}.json").write_text(json.dumps(dict(report, status="PASS", blockers=[])))
            self.assertIsNone(pf.verify(plan))
            plan.write_text(plan.read_text().replace("Genesis", "Genesis "))   # the plan changed after its preflight
            self.assertTrue(pf.verify(plan).startswith("PREFLIGHT_STALE"))
        finally:
            pf.REPORTS = saved
            shutil.rmtree(d)

    def test_the_workflow_runs_verify_before_any_secret(self):
        wf = (pf.REPO / ".github" / "workflows" / "episode.yml").read_text()
        verify = wf.index("episode_build.py verify-preflight")
        self.assertLess(verify, wf.index("secrets.PAVO_TOKEN"))
        self.assertLess(verify, wf.index("pilot_render.py voice"))

    def test_a_committed_report_says_pass_only_with_no_blocker(self):
        for path in sorted(pf.REPORTS.glob("*.json")):
            report = json.loads(path.read_text())
            self.assertIn(report["status"], ("PASS", "BLOCKED"), path.name)
            self.assertEqual(report["status"] == "PASS", report["blockers"] == [], path.name)


class Allocation(unittest.TestCase):
    def test_today_counts_the_image_records_cf_images_commits(self):
        class Done:
            returncode = 0
            stdout = ("migration/production/characters/images/ch-noah-front.json\n"
                      "migration/production/characters/images/ch-noah-front.png\n"
                      "migration/production/pilot-015/images/a.json\n")
        self.assertEqual(pf.cf_images_today("2026-10-26", run=lambda *a, **k: Done()), 2)


class Record(unittest.TestCase):
    def test_the_record_is_checked_with_publish_episode_rules_before_dispatch(self):
        rec = json.loads((HERE / "episodes" / "genesis-06-short.json").read_text())
        self.assertEqual(pf.record_problems(rec), [])
        bad = dict(rec, title="x" * 101, description=rec["description"].replace("(public domain)", ""))
        self.assertEqual(pf.record_problems(bad), ["TITLE_LENGTH", "DISCLOSURE_MISSING"])


if __name__ == "__main__":
    unittest.main()
