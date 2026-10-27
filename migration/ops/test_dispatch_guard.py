#!/usr/bin/env python3
"""E116: one dispatch guard runs first in every expensive workflow (inputs, capacity, one run per subject, no re-run
of failed inputs without a fix, imports in the job's environment)."""
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dispatch_guard as g  # noqa: E402
sys.path.insert(0, str(g.ROOT / "migration" / "production" / "bible"))

ROOT = g.ROOT
PLAN = "migration/production/bible/plans/genesis-09-short.json"
PILOT = next(p.parent.name for p in sorted((ROOT / "migration/production").glob("pilot-*/script.json")))
# workflow_dispatch workflows the guard does not cover, each with its reason (a new one must be listed or guarded)
EXEMPT = {
    "heartbeat.yml": "the scheduler itself; it dispatches, it makes nothing",
    "requests.yml": "dispatches committed requests; each dispatched workflow runs its own guard",
    "reconcile.yml": "reconciles ledgers; no generation, render or upload",
    "approve.yml": "the approval gate (prepublish_gate.py); its own gates refuse, the owner's rules forbid loosening it",
    "publish.yml": "publishes a gated, approved render; gated by approve.yml -> prepublish_gate.py",
    "publish-shorts.yml": "publishes gated Shorts on heartbeat; idempotent by its ledger",
    "shorts.yml": "byte-frozen (test_shorts_produce)",
    "shorts-review.yml": "review artefacts of a made Short; no generation",
    "tiktok.yml": "mirrors a published Short (Buffer free plan); idempotent by its ledger",
    "first-comment.yml": "one comment on a published video; idempotent",
    "arc-links.yml": "metadata edits on published videos; idempotent",
    "channel-config.yml": "channel metadata; no generation",
    "channel-privacy.yml": "privacy flips on heartbeat; idempotent",
    "description-refresh.yml": "description edits; idempotent",
    "goal-report.yml": "a report; reads only",
    "market-panel.yml": "a market report; reads only",
    "thumb-study.yml": "a study of thumbnails; reads only",
    "render-smoke.yml": "the render's CI smoke on fixtures",
    "pavo-mcp.yml": "the Pavo integration's tests; no generation",
    "reviewer-probe.yml": "a reviewer probe on a fixed sample",
    "reviewer-calibration.yml": "reviewer calibration on fixed samples",
    "voice-sample.yml": "a short voice sample; minutes only",
    "nightly-images.yml": "heartbeat's nightly slot; a used-up allocation defers (E62), never fails",
    "images-upres.yml": "upscales stills already made; no generation",
}


def fake_api(routes):
    """routes: (path prefix, response) pairs, first match wins; anything else is a 404 (None)."""
    calls = []

    def api(path):
        calls.append(path)
        for prefix, resp in routes:
            if path.startswith(prefix):
                return resp(path) if callable(resp) else resp
        return None
    api.calls = calls
    return api


def run_obj(rid, wf, title, conclusion=None, sha="a" * 40, status="completed"):
    return {"id": rid, "path": f".github/workflows/{wf}", "display_title": title, "conclusion": conclusion,
            "head_sha": sha, "status": status}


class Wiring(unittest.TestCase):
    def test_every_expensive_workflow_runs_the_guard_before_any_secret(self):
        for wf, (keys, _) in g.WORKFLOWS.items():
            text = (g.WF_DIR / wf).read_text()
            call = f"python3 -I -B migration/ops/dispatch_guard.py run {wf}"
            self.assertIn(call, text, wf)
            secret = text.find("secrets.")
            self.assertTrue(secret == -1 or text.index(call) < secret, f"{wf}: a secret comes before the guard")
            step = text[:text.index(call)].rsplit("      - name: ", 1)[1]
            self.assertTrue(step.startswith(g.GUARD_STEP), wf)
            self.assertIn("GUARD_INPUTS: ${{ toJSON(inputs) }}", step, wf)
            self.assertRegex(text, r"actions: (read|write)", f"{wf}: the guard reads runs")
            # the guard is the first step after the checkout of its job, and a guard job gates every other job
            job = text[:text.index(call)].rsplit("    steps:\n", 1)[1]
            self.assertEqual(job.count("      - "), 2, f"{wf}: the guard is not the step after the checkout")
            if "\n  guard:\n" in text:
                jobs = re.findall(r"^  ([a-z-]+):\n", text.split("\njobs:\n", 1)[1], re.M)
                for other in jobs[1:]:
                    body = text.split(f"\n  {other}:\n", 1)[1]
                    self.assertTrue(body.startswith("    needs: guard") or "needs: [guard" in body.split("\n  ")[0]
                                    or re.match(r"    needs: \[?[\w, -]*guard", body), f"{wf}: {other} skips the guard")
            # the run-name holds the inputs, so a later dispatch can find the failed run of the same inputs
            name = re.search(r"^run-name: \"(.*)\"$", text, re.M)
            self.assertIsNotNone(name, wf)
            self.assertEqual(name.group(1), g.run_name(wf, {k: "${{ inputs.%s }}" % k for k in keys}), wf)

    def test_every_dispatch_workflow_is_guarded_or_exempt(self):
        for wf in sorted(g.WF_DIR.glob("*.yml")):
            if "workflow_dispatch" in wf.read_text():
                self.assertTrue(wf.name in g.WORKFLOWS or wf.name in EXEMPT,
                                f"{wf.name}: guard it (dispatch_guard.WORKFLOWS) or exempt it here with its reason")
        self.assertEqual(sorted(set(EXEMPT) & set(g.WORKFLOWS)), [])

    def test_every_guarded_workflow_resolves_its_imports(self):
        # E73 / E81 / E89 class: the scripts a workflow calls import in the environment it builds
        for wf in g.WORKFLOWS:
            self.assertEqual(g.import_problems(wf), [], wf)


class Imports(unittest.TestCase):
    def test_a_package_the_workflow_does_not_install_is_refused(self):
        # E81: footage.py's vetting reaches cinematic, which imports numpy; footage.yml must install it
        have = g.installed("footage.yml")
        self.assertIn("numpy", have)
        with mock.patch.object(g, "installed", return_value=have - {"numpy"}):
            bad, _ = g.static_import_problems("footage.yml")
        self.assertTrue(any("cinematic.py imports numpy" in b for b in bad), bad)

    def test_a_sibling_import_that_fails_under_isolation_is_refused(self):
        # E73: python3 -I leaves the script's own folder off sys.path
        d = Path(tempfile.mkdtemp())
        try:
            (d / "helper_e116.py").write_text("X = 1\n")
            (d / "entry_e116.py").write_text("import helper_e116\n")
            (d / "fixed_e116.py").write_text("import sys\nfrom pathlib import Path\n"
                                             "sys.path.insert(0, str(Path(__file__).parent))\nimport helper_e116\n")
            with mock.patch.object(g, "scripts", return_value=[str(d / "entry_e116.py"), str(d / "fixed_e116.py")]):
                bad = g.runtime_import_problems("footage.yml")
            self.assertEqual(len(bad), 1, bad)
            self.assertIn("entry_e116.py", bad[0])
            self.assertIn("helper_e116", bad[0])
        finally:
            shutil.rmtree(d)


class Inputs(unittest.TestCase):
    def refused(self, wf, inputs, code):
        with self.assertRaises(g.Refusal) as c:
            g.WORKFLOWS[wf][1](inputs)
        self.assertTrue(str(c.exception).startswith(code), str(c.exception))

    def test_each_workflow_refuses_inputs_outside_its_rules(self):
        self.refused("episode.yml", {"plan": "plans/x.json"}, "GUARD_INPUT_INVALID")
        self.refused("episode.yml", {"plan": "migration/production/bible/plans/nope-99-short.json"}, "GUARD_INPUT_MISSING")
        self.refused("shot-probe.yml", {"plan": PLAN, "shots": "s-not-a-shot", "attempts": "2"}, "GUARD_INPUT_INVALID")
        self.refused("shot-probe.yml", {"plan": PLAN, "shots": "s-voice", "attempts": "7"}, "GUARD_INPUT_INVALID")
        self.refused("cf-images.yml", {"pilot": "migration/production/pilot-010", "engine": "flux"}, "GUARD_INPUT_INVALID")
        self.refused("agnes-clip.yml", {"prompt": "x", "seconds": "13", "aspect": "9:16"}, "GUARD_INPUT_INVALID")
        self.refused("footage.yml", {"queries": "/etc/passwd", "per_theme": "3"}, "GUARD_INPUT_INVALID")
        self.refused("publish-episode.yml", {"episode": "genesis-01-short", "publish_at": "tomorrow"}, "GUARD_INPUT_INVALID")
        self.refused("pilot-render-stills.yml", {"pilot": "pilot-999"}, "GUARD_INPUT_MISSING")

    def test_valid_inputs_name_their_subject_and_uploads(self):
        f = g.WORKFLOWS["shot-probe.yml"][1]({"plan": PLAN, "shots": "s-voice,s-laugh", "attempts": "3"})
        self.assertEqual(f["subject"], ("episode", "genesis-09-short"))
        self.assertEqual(f["uploads"], 6)
        self.assertEqual(g.WORKFLOWS["pilot-preview.yml"][1]({"pilot": PILOT})["subject"], ("pilot", PILOT))
        self.assertIsNone(g.WORKFLOWS["agnes-clip.yml"][1]({"prompt": "a", "seconds": "6", "aspect": "9:16"})["subject"])

    def test_a_later_episode_part_waits_for_the_earlier_one(self):
        # E112's order, reused: the guard refuses with episode_order's own refusal
        import episode_order
        with mock.patch.object(episode_order, "earlier_part_open", return_value="EARLIER_PART_NOT_RECORDED x"):
            self.refused("episode.yml", {"plan": PLAN}, "EARLIER_PART_NOT_RECORDED")

    def test_a_publish_record_over_the_platform_limits_is_refused(self):
        rec = json.loads((ROOT / "migration/production/bible/episodes/genesis-01-short.json").read_text())
        rec["description"] = "x" * (g.DESCRIPTION_MAX + 1)
        with mock.patch.object(g, "load", return_value=rec):
            self.refused("publish-episode.yml", {"episode": "genesis-01-short"}, "GUARD_RECORD_OVER_LIMIT")

    def test_the_run_name_reads_back_into_its_inputs(self):
        inputs = {"seconds": "6", "aspect": "9:16", "characters": "", "first_frame": "", "prompt": "a man walks, slow"}
        title = g.run_name("agnes-clip.yml", inputs)
        self.assertEqual(g.parse_run_name("agnes-clip.yml", title), inputs)
        self.assertIsNone(g.parse_run_name("episode.yml", title))


class Capacity(unittest.TestCase):
    def test_a_release_without_room_for_the_uploads_is_refused(self):
        tag = g.newest_tag()
        assets = [{"name": f"a{i}"} for i in range(100)]
        last = [{"name": f"b{i}"} for i in range(95)]
        api = fake_api([(f"releases/tags/{tag}", {"id": 7}),
                        ("releases/7/assets?per_page=100&page=10", last),
                        ("releases/7/assets", assets)])
        self.assertEqual(g.asset_count(api, tag), 995)
        with self.assertRaises(g.Refusal) as c:
            g.capacity("pilot-render-stills.yml", {"uploads": 12}, api, "2026-10-27")
        self.assertTrue(str(c.exception).startswith("GUARD_ASSETS_FULL"))
        g.capacity("pilot-render-stills.yml", {"uploads": 5}, api, "2026-10-27")
        g.capacity("pilot-render-stills.yml", {"uploads": 12}, fake_api([]), "2026-10-27")  # no release yet: 0

    def test_a_used_up_image_allocation_is_refused(self):
        cap = g.cf_daily_images()
        files = [{"status": "added", "filename": f"migration/production/pilot-010/images/i{k}.json"} for k in range(cap)]
        api = fake_api([("commits?", [{"sha": "c1", "commit": {"message": "Record 44 images from Cloudflare Workers AI"}},
                                      {"sha": "c2", "commit": {"message": "other"}}]),
                        ("commits/c1", {"files": files})])
        with self.assertRaises(g.Refusal) as c:
            g.capacity("cf-images.yml", {"uploads": 0}, api, "2026-10-27")
        self.assertTrue(str(c.exception).startswith("GUARD_CF_ALLOCATION_USED"))
        g.capacity("pilot-preview.yml", {"uploads": 0}, api, "2026-10-27")   # it makes no image


class InFlight(unittest.TestCase):
    def test_one_run_per_subject_across_workflows(self):
        probe = run_obj(11, "shot-probe.yml", g.run_name("shot-probe.yml", {"plan": PLAN, "shots": "s-voice",
                                                                            "attempts": "2"}), status="in_progress")
        api = fake_api([("actions/runs?status=in_progress", {"workflow_runs": [probe]})])
        facts = {"subject": ("episode", "genesis-09-short")}
        with self.assertRaises(g.Refusal) as c:
            g.in_flight("episode.yml", facts, api, run_id=99)
        self.assertTrue(str(c.exception).startswith("GUARD_SUBJECT_IN_FLIGHT"))
        g.in_flight("episode.yml", facts, api, run_id=11)                       # its own run
        g.in_flight("episode.yml", {"subject": ("episode", "genesis-08-short")}, api, run_id=99)
        g.in_flight("agnes-clip.yml", {"subject": None}, api, run_id=99)


class Rerun(unittest.TestCase):
    INPUTS = {"pilot": PILOT}
    WF = "pilot-preview.yml"

    def api(self, conclusion="failure", compare=None, guard_failed=False, older=None):
        title = g.run_name(self.WF, self.INPUTS)
        runs = [run_obj(5, self.WF, g.run_name(self.WF, {"pilot": "pilot-000"}), "failure"),
                run_obj(4, self.WF, title, conclusion, sha="f" * 40)] + (older or [])
        step = g.GUARD_STEP + " (...)" if guard_failed else "Render"
        return fake_api([(f"actions/workflows/{self.WF}/runs", {"workflow_runs": runs}),
                         ("actions/runs/4/jobs", {"jobs": [{"steps": [{"name": step, "conclusion": "failure"}]}]}),
                         ("actions/runs/3/jobs", {"jobs": [{"steps": [{"name": "Render", "conclusion": "failure"}]}]}),
                         ("compare/", compare or {"status": "identical", "files": []})])

    def facts(self):
        return g.WORKFLOWS[self.WF][1](self.INPUTS)

    def assert_refused(self, api, attempt=1):
        with self.assertRaises(g.Refusal) as c:
            g.rerun(self.WF, self.facts(), self.INPUTS, api, 9, attempt, "e" * 40)
        self.assertTrue(str(c.exception).startswith("GUARD_RERUN_WITHOUT_FIX"), str(c.exception))

    def test_failed_inputs_need_a_new_commit_touching_what_the_run_depends_on(self):
        self.assert_refused(self.api())                                         # main has not moved
        self.assert_refused(self.api(compare={"status": "ahead", "files": [{"filename": "README.md"}]}))
        g.rerun(self.WF, self.facts(), self.INPUTS,
                self.api(compare={"status": "ahead", "files": [{"filename": f"migration/production/{PILOT}/x.json"}]}),
                9, 1, "e" * 40)
        g.rerun(self.WF, self.facts(), self.INPUTS,
                self.api(compare={"status": "ahead", "files": [{"filename": "migration/production/still_render.py"}]}),
                9, 1, "e" * 40)
        g.rerun(self.WF, self.facts(), self.INPUTS, self.api(conclusion="success"), 9, 1, "e" * 40)

    def test_a_run_the_guard_refused_is_not_a_failure_of_its_inputs(self):
        g.rerun(self.WF, self.facts(), self.INPUTS, self.api(guard_failed=True), 9, 1, "e" * 40)
        older = [run_obj(3, self.WF, g.run_name(self.WF, self.INPUTS), "failure")]
        self.assert_refused(self.api(guard_failed=True, older=older))        # the failure before it still counts

    def test_an_external_failure_recorded_by_pr_may_run_again(self):
        with mock.patch.object(g, "recorded_retry", side_effect=lambda rid: str(rid) == "4"):
            g.rerun(self.WF, self.facts(), self.INPUTS, self.api(), 9, 1, "e" * 40)
        retries = json.loads(g.RETRIES.read_text())
        self.assertIn("retries", retries)

    def test_a_re_run_attempt_of_a_failed_run_is_refused(self):
        api = fake_api([("actions/runs/9/attempts/1/jobs", {"jobs": [{"steps": [{"name": "Render",
                                                                                   "conclusion": "failure"}]}]})])
        self.assert_refused(api, attempt=2)


if __name__ == "__main__":
    unittest.main()
