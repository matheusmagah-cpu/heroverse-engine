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
LONG_PLAN = "migration/production/bible/plans/arc-01-long.json"
PILOT = next(p.parent.name for p in sorted((ROOT / "migration/production").glob("pilot-*/script.json")))


def live_shots(plan, n=2):
    """E133: shot ids of a live plan for a fixture, read from the plan itself (never copied by hand: a plan edit
    removed genesis-09's s-laugh and broke this file). Generated scene shots with no speaker (one probe = at most 3
    generations), in plan order."""
    shots = json.loads((ROOT / plan).read_text())["shots"]
    ids = [s["id"] for s in shots if s.get("kind") == "scene" and s.get("window_of") is None and not s.get("speaker")]
    assert len(ids) >= n, (plan, ids)
    return ids[:n]


S1, S2 = live_shots(PLAN)
L1, L2 = live_shots(LONG_PLAN)
HAND_SHOTS = __import__("re").compile(r'"shots":\s*"([^"]+)"')


def hand_copied_shot_ids(root=ROOT):
    """E133's class antidote: [(test file, line, ids)] where a test line names a live plan (PLAN, LONG_PLAN or a
    plans/<episode>.json path) and passes a hand-written `"shots": "..."` literal holding ids of that plan. An id the
    plan does not have (a refusal test: "s-not-a-shot") is fine; a real id must come from the plan (live_shots)."""
    plans = {p.stem: {s["id"] for s in json.loads(p.read_text())["shots"]}
             for p in (root / "migration/production/bible/plans").glob("*.json")}
    names = {"PLAN": "genesis-09-short", "LONG_PLAN": "arc-01-long"}
    out = []
    for f in sorted(root.glob("migration/**/test_*.py")):
        for no, line in enumerate(f.read_text().splitlines(), 1):
            m = HAND_SHOTS.search(line)
            if not m:
                continue
            eps = [ep for ep in plans if f"plans/{ep}.json" in line]
            eps += [names[k] for k in names if __import__("re").search(rf'"plan":\s*{k}\b', line)]
            for ep in eps:
                hit = [i for i in m.group(1).split(",") if i in plans.get(ep, set())]
                if hit:
                    out.append((str(f.relative_to(root)), no, hit))
    return out
# workflow_dispatch workflows the guard does not cover, each with its reason (a new one must be listed or guarded)
EXEMPT = {
    "heartbeat.yml": "the scheduler itself; it dispatches, it makes nothing",
    "requests.yml": "dispatches committed requests; each dispatched workflow runs its own guard",
    "reconcile.yml": "reconciles ledgers; no generation, render or upload",
    "approve.yml": "the approval gate (prepublish_gate.py); its own gates refuse, the owner's rules forbid loosening it",
    "publish.yml": "publishes a gated, approved render; gated by approve.yml -> prepublish_gate.py",
    "tiktok.yml": "mirrors a published Short (Buffer free plan); idempotent by its ledger",
    "first-comment.yml": "one comment on a published video; idempotent",
    "arc-links.yml": "metadata edits on published videos; idempotent",
    "comment-replies.yml": "replies to viewers' comments, decided by Claude and gated by reply_policy; idempotent by its ledger",
    "channel-config.yml": "channel metadata; no generation",
    "channel-privacy.yml": "privacy flips, dispatched by hand (plan by default); idempotent",
    "goal-report.yml": "a report; reads only",
    "market-panel.yml": "a market report; reads only",
    "thumb-study.yml": "a study of thumbnails; reads only",
    "render-smoke.yml": "the render's CI smoke on fixtures",
    "pavo-mcp.yml": "the Pavo integration's tests; no generation",
    "reviewer-calibration.yml": "reviewer calibration on fixed samples (kept: E59's antidote reads it)",
    "nightly-images.yml": "heartbeat's nightly slot; a used-up allocation defers (E62), never fails",
    "images-upres.yml": "upscales stills already made; no generation",
}


def fake_api(routes):
    """routes: (path prefix, response) pairs, first match wins; anything else is a 404 (None)."""
    def api(path):
        for prefix, resp in routes:
            if path.startswith(prefix):
                return resp(path) if callable(resp) else resp
        return None
    return api


def run_obj(rid, wf, title, conclusion=None, sha="a" * 40):
    return {"id": rid, "path": f".github/workflows/{wf}", "display_title": title, "conclusion": conclusion,
            "head_sha": sha, "status": "completed"}


def jobs(blocks_text):
    """{job name: its text} of a workflow."""
    body = blocks_text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([a-z][a-z0-9-]*):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def render(expr, inputs, subject):
    """A concurrency group expression with the dispatch's inputs (the three forms the guarded workflows use)."""
    out = re.sub(r"\$\{\{ format\('([^']*)', inputs\.(\w+)\) \}\}", lambda m: m.group(1).replace("{0}", inputs[m.group(2)]),
                 expr)
    out = re.sub(r"\$\{\{ inputs\.(\w+) \}\}", lambda m: inputs[m.group(1)], out)
    return out.replace("${{ needs.guard.outputs.subject }}", subject or "")


SAMPLES = {
    "episode.yml": {"plan": PLAN, "resume_run": ""},
    "shot-probe.yml": {"plan": PLAN, "shots": S1, "attempts": "2", "adopt_run": ""},
    "publish-episode.yml": {"episode": "genesis-09-short", "source_url": "", "publish_at": ""},
    "cf-images.yml": {"pilot": PILOT, "engine": "flux", "only": ""},
    "pilot-render-stills.yml": {"pilot": PILOT},
    "pilot-preview.yml": {"pilot": PILOT},
    "footage.yml": {"queries": f"migration/production/{PILOT}/beats.json", "per_theme": "3"},
    "scene-stills.yml": {"plan": PLAN, "shots": S1, "candidates": "2"},
    "long-build.yml": {"plan": LONG_PLAN, "resume_run": ""},
}


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
            # the run-name holds the inputs (the first names the subject), so a later dispatch finds its failures
            name = re.search(r"^run-name: \"(.*)\"$", text, re.M)
            self.assertIsNotNone(name, wf)
            self.assertEqual(name.group(1), g.run_name(wf, {k: "${{ inputs.%s }}" % k for k in keys}), wf)

    def test_every_job_that_holds_a_secret_or_does_the_work_runs_the_guard_first(self):
        # review of #445: "Re-run failed jobs" skips a separate guard job that passed, so each such job starts with
        # the guard (or its attempt rule) after the checkout, and its job-level env holds no secret
        for wf in g.WORKFLOWS:
            for name, body in jobs((g.WF_DIR / wf).read_text()).items():
                head = body.split("    steps:\n", 1)[0]
                self.assertNotIn("secrets.", head, f"{wf} {name}: a secret in the job's env reaches the guard step")
                if "secrets." not in body and int(re.search(r"timeout-minutes: (\d+)", head).group(1)) < 30:
                    continue          # light jobs with no secret (record, failure evidence, plan)
                steps = body.split("    steps:\n", 1)[1].split("\n      - ")
                self.assertIn("actions/checkout@", steps[0], f"{wf} {name}")
                self.assertRegex(steps[1], rf"dispatch_guard\.py (run|attempt) {re.escape(wf)}", f"{wf} {name}")
                self.assertTrue(steps[1].startswith("name: " + g.GUARD_STEP), f"{wf} {name}")
                self.assertNotIn("secrets.", steps[1], f"{wf} {name}")

    def test_one_run_per_subject_is_a_shared_concurrency_group(self):
        # review of #445: GitHub's own concurrency, not a scan of in-flight runs; the group renders subject_of
        for wf, job in g.SUBJECT_JOBS.items():
            head = jobs((g.WF_DIR / wf).read_text())[job].split("    steps:\n", 1)[0]
            m = re.search(r"    concurrency:.*\n      group: (.+)\n      cancel-in-progress: false\n", head)
            self.assertIsNotNone(m, f"{wf} {job}: no subject concurrency group")
            subject = g.subject_of(wf, SAMPLES[wf])
            self.assertEqual(render(m.group(1), SAMPLES[wf], subject), f"heroverse-subject-{subject}", wf)
        # the episode's build, its probes and its publication share one group; a pilot's images, render and preview
        self.assertEqual(len({g.subject_of(w, SAMPLES[w]) for w in ("episode.yml", "shot-probe.yml",
                                                                     "publish-episode.yml", "scene-stills.yml")}), 1)
        self.assertEqual(len({g.subject_of(w, SAMPLES[w]) for w in ("cf-images.yml", "pilot-render-stills.yml",
                                                                     "pilot-preview.yml", "footage.yml")}), 1)
        footage = (g.WF_DIR / "footage.yml").read_text()
        self.assertIn("subject: ${{ steps.guard.outputs.subject }}", footage)

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

    def test_imports_resolve_from_the_importing_folder_first_and_same_names_stay_apart(self):
        # review of #445: two modules with one stem are two modules; a script's own folder and its sys.path
        # inserts decide which one it imports
        d = Path(tempfile.mkdtemp())
        try:
            (d / "a").mkdir()
            (d / "b").mkdir()
            (d / "a" / "client.py").write_text("import numpy\n")
            (d / "b" / "client.py").write_text("import json\n")
            (d / "b" / "entry.py").write_text("import client\n")
            (d / "a" / "far.py").write_text("import sys\nfrom pathlib import Path\n"
                                            "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'b'))\n")
            self.assertEqual(g._resolve("client", d / "b" / "entry.py", []), [(d / "b" / "client.py").resolve()])
            far = d / "a" / "far.py"
            dirs = g._sys_path_dirs(g.ast.parse(far.read_text()), far)
            self.assertEqual([p.resolve() for p in dirs], [(d / "b").resolve()])
            with mock.patch.object(g, "_module_index", return_value={"x": [d / "a" / "client.py", d / "b" / "client.py"]}):
                self.assertEqual(len(g._resolve("x", d / "z.py", [])), 2)          # never collapsed into one
        finally:
            shutil.rmtree(d)

    def test_a_sibling_import_that_fails_under_isolation_is_refused(self):
        # E73: python3 -I leaves the script's own folder off sys.path; one process checks every script, and what
        # one script put on sys.path does not rescue the next
        d = Path(tempfile.mkdtemp())
        try:
            (d / "helper_e116.py").write_text("X = 1\n")
            (d / "fixed_e116.py").write_text("import sys\nfrom pathlib import Path\n"
                                             "sys.path.insert(0, str(Path(__file__).parent))\nimport helper_e116\n")
            (d / "entry_e116.py").write_text("import helper_e116\n")
            with mock.patch.object(g, "scripts", return_value=(str(d / "fixed_e116.py"), str(d / "entry_e116.py"))):
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
        self.refused("shot-probe.yml", {"plan": PLAN, "shots": S1, "attempts": "7"}, "GUARD_INPUT_INVALID")
        self.refused("cf-images.yml", {"pilot": "migration/production/pilot-010", "engine": "flux"}, "GUARD_INPUT_INVALID")
        self.refused("footage.yml", {"queries": "/etc/passwd", "per_theme": "3"}, "GUARD_INPUT_INVALID")
        # owner 28/10: a Short's own queries file (footage/queries-<name>.json) feeds the same library
        self.refused("footage.yml", {"queries": "migration/production/footage/queries-../x.json"}, "GUARD_INPUT_INVALID")
        self.refused("footage.yml", {"queries": "migration/production/footage/queries-nope-99.json"}, "GUARD_INPUT_MISSING")
        named = {"queries": "migration/production/footage/queries-shorts-g09.json", "per_theme": "2"}
        self.assertEqual(g.WORKFLOWS["footage.yml"][1](named)["uploads"], 2 * 17)
        self.assertEqual(g.subject_of("footage.yml", named), "footage-library-shorts-g09")
        wf = (g.WF_DIR / "footage.yml").read_text()
        self.assertIn("footage/queries(-[a-z0-9]+)*|", wf)   # the workflow's own path check agrees
        self.refused("publish-episode.yml", {"episode": "genesis-01-short", "publish_at": "tomorrow"}, "GUARD_INPUT_INVALID")
        self.refused("pilot-render-stills.yml", {"pilot": "pilot-999"}, "GUARD_INPUT_MISSING")
        # LONG_DESIGN slice 3: the long's build takes a long plan only
        self.refused("long-build.yml", {"plan": PLAN}, "GUARD_INPUT_INVALID")
        self.refused("long-build.yml", {"plan": LONG_PLAN, "resume_run": "x"}, "GUARD_INPUT_INVALID")
        self.assertEqual(g.WORKFLOWS["long-build.yml"][1]({"plan": LONG_PLAN})["uploads"], 2)

    def test_no_test_copies_a_live_plans_shot_ids_by_hand(self):
        """E133: a fixture that copies a live plan's shot ids breaks when the plan is edited (genesis-09's redesign
        removed s-laugh: GUARD_INPUT_INVALID in two tests). Every test reads them from the plan (live_shots)."""
        self.assertEqual(hand_copied_shot_ids(), [])
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "migration/production/bible/plans").mkdir(parents=True)
            (d / "migration/production/bible/plans/ep-01-short.json").write_text(json.dumps(
                {"shots": [{"id": "s-a", "kind": "scene"}]}))
            (d / "migration/ops").mkdir(parents=True)
            (d / "migration/ops/test_x.py").write_text(
                'PLAN = "migration/production/bible/plans/ep-01-short.json"\n'
                'a = {"plan": "migration/production/bible/plans/ep-01-short.json", "shots": "s-a"}\n'
                'b = {"plan": "migration/production/bible/plans/ep-01-short.json", "shots": "s-not-a-shot"}\n')
            self.assertEqual(hand_copied_shot_ids(d), [("migration/ops/test_x.py", 2, ["s-a"])])

    def test_e135_a_probe_whose_plan_fails_its_strict_check_is_refused_before_the_run(self):
        """E135: run 40626005505 passed the guard and stopped in shot-probe's next step (plan_check --strict: 11
        STILL_NOT_APPROVED). The guard runs that same check first."""
        import subprocess as sp

        def ran(code, out):
            return lambda cmd, **kw: sp.CompletedProcess(cmd, code, out, "")
        bad = ran(1, json.dumps({"problems": ["STILL_NOT_APPROVED shot 4 s-pairs (...)"]}))
        self.assertEqual(g.plan_strict_problems(PLAN, run=bad), ["STILL_NOT_APPROVED shot 4 s-pairs (...)"])
        self.assertEqual(g.plan_strict_problems(PLAN, run=ran(0, "{}")), [])
        self.assertTrue(g.plan_strict_problems(PLAN, run=ran(2, "Traceback")))    # a crash is never a pass
        seen = []
        with mock.patch.object(g, "plan_strict_problems", lambda p: seen.append(p) or ["STILL_NOT_APPROVED x"]):
            with self.assertRaises(g.Refusal) as c:
                g.check_local("shot-probe.yml", {"plan": PLAN, "shots": S1, "attempts": "1", "adopt_run": ""})
            self.assertTrue(str(c.exception).startswith("GUARD_PLAN_NOT_STRICT"), str(c.exception))
            g.check_local("scene-stills.yml", {"plan": PLAN, "shots": S1, "candidates": "1"})   # stills come first
        self.assertEqual(seen, [PLAN])
        long_cmd = []
        g.plan_strict_problems(LONG_PLAN, run=lambda cmd, **kw: long_cmd.append(cmd) or sp.CompletedProcess(cmd, 0, "", ""))
        self.assertTrue(long_cmd[0][3].endswith("long_plan_check.py"))

    def test_parallel_footage_runs_retry_their_record_push(self):
        """After E144 footage runs of different queries run at once; each pulls and pushes its records to main, so a
        push that loses the race pulls again (bounded) and a run that never lands fails loudly, never silently."""
        wf = (g.WF_DIR / "footage.yml").read_text()
        loop = re.search(r"for i in 1 2 3 4 5 6; do\n\s+git pull --rebase -q origin main && git push -q origin HEAD:main "
                         r"&& \{ pushed=1; break; \}\n\s+git rebase --abort 2>/dev/null \|\| true; sleep \$\(\(i \* 7\)\)\n"
                         r"\s+done\n\s+\[ \"\$pushed\" = 1 \] \|\| \{ echo \"FOOTAGE_RECORDS_NOT_PUSHED\"; exit 1; \}", wf)
        self.assertIsNotNone(loop)
        self.assertEqual(wf.count("git push"), 1)

    def test_e144_footage_runs_of_different_queries_never_share_a_pending_slot(self):
        """E144 (28/10): GitHub keeps one PENDING run per concurrency group and cancels the older one; every
        footage.yml run shared `heroverse-footage` and the subject `footage-library`/the pilot, so the long's beats-6
        cancelled genesis-09's pending run (40678588023) and genesis-10/11's cancelled beats-6 (40680841788). Each
        queries file is now its own workflow-level group, and a named library queries file its own subject (job
        group); a pilot's beats keep the pilot's subject on purpose (its footage, images, render and preview in order)."""
        subjects = {g.subject_of("footage.yml", {"queries": q}) for q in (
            "migration/production/footage/queries.json", "migration/production/footage/queries-shorts-g09.json",
            "migration/production/footage/queries-shorts-g10-g11.json", f"migration/production/{PILOT}/beats-5.json")}
        self.assertEqual(len(subjects), 4)
        wf = (g.WF_DIR / "footage.yml").read_text()
        top = re.search(r"^concurrency:.*?\n  group: (.+)", wf, re.M | re.S).group(1)
        self.assertIn("inputs.queries", top)
        self.assertEqual(g.subject_of("pavo-footage.yml", {"list": f"migration/production/{PILOT}/pavo-1.json"}), PILOT)

    def test_valid_inputs_name_their_subject_and_uploads(self):
        f = g.WORKFLOWS["shot-probe.yml"][1]({"plan": PLAN, "shots": f"{S1},{S2}", "attempts": "3"})
        self.assertEqual(f["uploads"], 6)
        self.assertEqual(g.subject_of("shot-probe.yml", {"plan": PLAN}), PLAN)
        self.assertEqual(g.subject_of("pavo-footage.yml", {"list": f"migration/production/{PILOT}/pavo-1.json"}), PILOT)
        self.assertEqual(g.subject_of("footage.yml", {"queries": "migration/production/footage/queries.json"}),
                         "footage-library")

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

    def test_the_run_name_names_its_subject(self):
        title = g.run_name("shot-probe.yml", {"plan": PLAN, "shots": S1, "attempts": "2"})
        self.assertEqual(g.run_subject("shot-probe.yml", title), PLAN)
        self.assertEqual(g.run_subject("publish-episode.yml", g.run_name("publish-episode.yml",
                                                                         {"episode": "genesis-09-short"})), PLAN)
        self.assertIsNone(g.run_subject("episode.yml", title))


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

    def test_a_used_up_flux_allocation_refuses_a_flux_run_only(self):
        # review of #445: FLUX records only, by episode_preflight's own predicate (cf_allocation.flux_record), on
        # main; E134: scene-stills.yml's images from its runs, so a squash-merged, deleted review branch still counts
        cap = g.cf_daily_images()
        half = cap // 2

        def commit(msg, files, date="2026-10-27T10:00:00Z"):
            return {"commit": {"message": msg, "committer": {"date": date}},
                    "files": [{"status": "added", "filename": f} for f in files]}
        flux = commit("Record pilot-010 images from Cloudflare Workers AI (flux, run 1)",
                      [f"migration/production/pilot-010/images/i{k}.json" for k in range(half)])
        sdxl = commit("Record pilot-011 images from Cloudflare Workers AI (sdxl, run 2)",
                      [f"migration/production/pilot-011/images/i{k}.json" for k in range(cap)])
        rest = cap - half
        runs = [dict(run_obj(3, "scene-stills.yml", f"scene-stills: plan={PLAN} shots={','.join(['a'] * rest)} "
                                                    f"candidates=1", "success"), created_at="2026-10-27T09:00:00Z"),
                dict(run_obj(4, "scene-stills.yml", f"scene-stills: plan={PLAN} shots=a,b candidates=3", "success"),
                     created_at="2026-10-26T09:00:00Z")]                       # yesterday
        api = fake_api([("commits?", [{"sha": "c1", "commit": flux["commit"]}, {"sha": "c2", "commit": sdxl["commit"]}]),
                        ("actions/workflows/scene-stills.yml/runs", {"workflow_runs": runs}),
                        ("commits/c1", flux), ("commits/c2", sdxl)])
        self.assertEqual(g.cf_images_today(api, "2026-10-27"), cap)        # no sdxl, nothing from yesterday
        self.assertEqual(g.cf_images_today(api, "2026-10-27", run_id=3), half)   # a run is not counted twice
        with self.assertRaises(g.Refusal) as c:
            g.capacity("scene-stills.yml", {"uploads": 0, "flux": True}, api, "2026-10-27")
        self.assertTrue(str(c.exception).startswith("GUARD_CF_ALLOCATION_USED"))
        g.capacity("cf-images.yml", {"uploads": 0, "flux": False}, api, "2026-10-27")   # an sdxl run
        sys.path.insert(0, str(ROOT / "migration/production/bible"))
        import episode_preflight
        self.assertIs(episode_preflight.cf_allocation, sys.modules["cf_allocation"])   # one predicate for both

    def test_e134_a_stills_run_counts_after_its_branch_is_gone_and_its_own_images_must_fit(self):
        """E134 (28/10): genesis-09 run 40615150859 made 30 FLUX images; #487 squash-merged its review branch and
        deleted it, the guard counted 0 and passed run 40623485981 (18 images) into a used-up allocation."""
        cap = g.cf_daily_images()
        done = dict(run_obj(40615150859, "scene-stills.yml",
                            f"scene-stills: plan={PLAN} shots={','.join(['s'] * 15)} candidates=2", "success"),
                    created_at="2026-10-28T01:28:00Z")
        api = fake_api([("commits?", []), ("branches?", []),           # no review branch, no marked commit left
                        ("actions/workflows/scene-stills.yml/runs", {"workflow_runs": [done]})])
        self.assertEqual(g.cf_images_today(api, "2026-10-28"), 30)
        facts = g.scene_stills({"plan": PLAN, "shots": f"{S1},{S2}", "candidates": "2"})
        self.assertEqual(facts["flux_images"], 4)
        over = dict(facts, flux=True, uploads=0, flux_images=cap - 30 + 1)
        with self.assertRaises(g.Refusal) as c:
            g.capacity("scene-stills.yml", over, api, "2026-10-28")
        self.assertTrue(str(c.exception).startswith("GUARD_CF_ALLOCATION_USED"))
        g.capacity("scene-stills.yml", dict(over, flux_images=cap - 30), api, "2026-10-28")   # exactly fits
        refused = dict(done, id=7, conclusion="failure")
        api2 = fake_api([("commits?", []), ("actions/workflows/scene-stills.yml/runs", {"workflow_runs": [refused]}),
                         ("actions/runs/7/jobs", {"jobs": [{"steps": [{"name": g.GUARD_STEP + " (inputs)",
                                                                       "conclusion": "failure"}]}]})])
        self.assertEqual(g.cf_images_today(api2, "2026-10-28"), 0)   # refused by the guard: no image made


class Rerun(unittest.TestCase):
    INPUTS = {"pilot": PILOT}
    WF = "pilot-preview.yml"

    def api(self, conclusion="failure", compare=None, guard_failed=False, older=None, title=None):
        title = title or g.run_name(self.WF, self.INPUTS)
        runs = [run_obj(5, self.WF, g.run_name(self.WF, {"pilot": "pilot-000"}), "failure"),
                run_obj(4, self.WF, title, conclusion, sha="f" * 40)] + (older or [])
        step = g.GUARD_STEP + " (...)" if guard_failed else "Render"
        return fake_api([(f"actions/workflows/{self.WF}/runs", {"workflow_runs": runs}),
                         ("actions/runs/4/jobs", {"jobs": [{"steps": [{"name": step, "conclusion": "failure"}]}]}),
                         ("actions/runs/3/jobs", {"jobs": [{"steps": [{"name": "Render", "conclusion": "failure"}]}]}),
                         ("compare/", compare or {"status": "identical", "files": []})])

    def facts(self, wf=None, inputs=None):
        wf, inputs = wf or self.WF, inputs or self.INPUTS
        f = g.WORKFLOWS[wf][1](inputs)
        f["subject"], f["files"] = g.subject_of(wf, inputs), g.static_import_problems(wf)[1]
        return f

    def assert_refused(self, api, attempt=1, wf=None, inputs=None):
        with self.assertRaises(g.Refusal) as c:
            g.rerun(wf or self.WF, self.facts(wf, inputs), inputs or self.INPUTS, api, 9, attempt, "e" * 40)
        self.assertTrue(str(c.exception).startswith("GUARD_RERUN_WITHOUT_FIX"), str(c.exception))

    def test_failed_inputs_need_a_new_commit_touching_what_the_run_depends_on(self):
        self.assert_refused(self.api())                                         # main has not moved
        self.assert_refused(self.api(compare={"status": "ahead", "files": [{"filename": "README.md"}]}))
        for touched in (f"migration/production/{PILOT}/x.json", "migration/production/still_render.py"):
            g.rerun(self.WF, self.facts(), self.INPUTS,
                    self.api(compare={"status": "ahead", "files": [{"filename": touched}]}), 9, 1, "e" * 40)
        g.rerun(self.WF, self.facts(), self.INPUTS, self.api(conclusion="success"), 9, 1, "e" * 40)
        g.rerun(self.WF, self.facts(), self.INPUTS, self.api(conclusion="cancelled"), 9, 1, "e" * 40)

    def test_the_failure_history_is_keyed_on_the_subject_not_the_other_inputs(self):
        # review of #445: a new resume_run / attempts / adopt_run is not a fix
        wf = "shot-probe.yml"
        old = g.run_name(wf, {"plan": PLAN, "shots": S1, "attempts": "2", "adopt_run": ""})
        new = {"plan": PLAN, "shots": S2, "attempts": "3", "adopt_run": ""}
        api = fake_api([(f"actions/workflows/{wf}/runs", {"workflow_runs": [run_obj(4, wf, old, "failure")]}),
                        ("actions/runs/4/jobs", {"jobs": []}), ("compare/", {"status": "identical", "files": []})])
        self.assert_refused(api, wf=wf, inputs=new)

    def test_a_new_pass_preflight_counts_as_a_fix_for_the_episode_build(self):
        # review of #445: the dependency is the report file evidence/preflight/<episode>.json
        wf, inputs = "episode.yml", {"plan": PLAN, "resume_run": ""}
        with mock.patch("episode_order.earlier_part_open", return_value=None):
            facts = self.facts(wf, inputs)
        ep = PLAN.rsplit("/", 1)[1][:-5]
        self.assertIn(f"migration/evidence/preflight/{ep}.json", g.depends_on(wf, facts))

        def api(report):
            return fake_api([(f"actions/workflows/{wf}/runs", {"workflow_runs": [
                                run_obj(4, wf, g.run_name(wf, {"plan": PLAN, "resume_run": "123456"}), "failure")]}),
                             ("actions/runs/4/jobs", {"jobs": []}),
                             ("compare/", {"status": "ahead", "files": [{"filename": report}]})])
        g.rerun(wf, facts, inputs, api(f"migration/evidence/preflight/{ep}.json"), 9, 1, "e" * 40)
        with self.assertRaises(g.Refusal):
            g.rerun(wf, facts, inputs, api(f"migration/evidence/preflight/{ep}-old.md"), 9, 1, "e" * 40)

    def test_a_run_the_guard_refused_is_not_a_failure_of_its_subject(self):
        g.rerun(self.WF, self.facts(), self.INPUTS, self.api(guard_failed=True), 9, 1, "e" * 40)
        older = [run_obj(3, self.WF, g.run_name(self.WF, self.INPUTS), "failure")]
        self.assert_refused(self.api(guard_failed=True, older=older))        # the failure before it still counts

    def test_an_external_failure_recorded_by_pr_may_run_again(self):
        with mock.patch.object(g, "recorded_retry", side_effect=lambda rid: str(rid) == "4"):
            g.rerun(self.WF, self.facts(), self.INPUTS, self.api(), 9, 1, "e" * 40)
        self.assertIn("retries", json.loads(g.RETRIES.read_text()))

    def test_a_re_run_attempt_is_refused_only_after_a_failed_attempt(self):
        # review of #445: a re-run after a cancelled or successful attempt, or one the guard refused, is allowed
        def api(conclusion, step="Render"):
            return fake_api([("actions/runs/9/attempts/1/jobs", {"jobs": [{"steps": [{"name": step,
                                                                                      "conclusion": "failure"}]}]}),
                             ("actions/runs/9/attempts/1", {"conclusion": conclusion})])
        with self.assertRaises(g.Refusal) as c:
            g.attempt_check(api("failure"), 9, 2, "e" * 40)
        self.assertIn("attempt 1 failed", str(c.exception))
        g.attempt_check(api("cancelled"), 9, 2, "e" * 40)
        g.attempt_check(api("success"), 9, 2, "e" * 40)
        g.attempt_check(api("failure", step=g.GUARD_STEP + " (...)"), 9, 2, "e" * 40)
        g.attempt_check(api("failure"), 9, 1, "e" * 40)


class PavoBudget(unittest.TestCase):
    """E128: shot-probe run 40592173923 started on a day whose free Pavo quota was already spent (~187 stills, ~32
    MCP video probes) and burned 24 submissions; nothing before the dispatch counted Pavo at all. The guard now
    refuses a batch whose expected units do not fit what is left today of the one budget (main's ledger + today's
    shot-probe records), or that runs into a suspected quota stop, and hands the count to the probe."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name) / "image-ledger.json"
        sys.path.insert(0, str(ROOT / "migration" / "integrations" / "pavo"))
        import quota
        self.quota = quota
        self.patch = mock.patch.object(quota, "LEDGER", self.ledger)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def api(self, failed=0, ok=3, date="2026-10-27T22:41:42Z"):
        import base64
        gens = [{"conversation_id": str(373595250617019904 + k), "flags": []} for k in range(ok)]
        gens += [{"conversation_id": str(373599328776227520 + k), "flags": ["NO_VIDEO"]} for k in range(failed)]
        record = {"episode": "arc-01-long", "shots": {"g-c1-lights": {"clips": [{"round": 1, "generations": gens}]}}}
        content = base64.b64encode(json.dumps(record).encode()).decode()
        return fake_api([
            ("branches?", [{"name": "claude/shot-probe-arc-01-long-40592173923", "commit": {"sha": "p1"}},
                           {"name": "claude/shot-probe-genesis-08-short-40477936323", "commit": {"sha": "p0"}},
                           {"name": "main", "commit": {"sha": "m"}}]),
            ("commits/p1", {"commit": {"committer": {"date": date}}}),
            ("commits/p0", {"commit": {"committer": {"date": "2026-10-26T09:35:04Z"}}}),   # yesterday: not counted
            ("contents/migration/evidence/shots/arc-01-long/40592173923.json?ref=p1", {"content": content})])

    def test_a_probe_batch_names_its_expected_units_and_an_adopt_run_none(self):
        probe = g.WORKFLOWS["shot-probe.yml"][1]
        f = probe({"plan": LONG_PLAN, "shots": f"{L1},{L2}", "attempts": "2", "adopt_run": ""})
        # review of #475: the worst case, 2 shots x 2 rounds x 3 generations (make_shot's ATTEMPTS) x 2 units, so a
        # batch that starts can finish; the mean (1.2 a round: 10 units) is only probe-queue's estimate
        self.assertEqual(f["pavo_units"], 24)
        f = probe({"plan": LONG_PLAN, "shots": L1, "attempts": "2", "adopt_run": "40592173923"})
        self.assertEqual(f["pavo_units"], 0)

    def test_todays_probe_records_count_from_their_branches(self):
        usage = g.pavo_actions_usage(self.api(failed=24), "2026-10-27")
        self.assertEqual((usage["units"], usage["failed_tail"]), (27 * self.quota.VIDEO_UNITS, 24))

    def test_a_batch_that_cannot_finish_today_is_refused_before_it_starts(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc)
        self.ledger.write_text(json.dumps({"days": {"2026-10-28": {"generated": 100}}}))
        api = self.api(ok=4, date="2026-10-28T00:30:00Z")                 # 8 units on Actions today
        facts = {"uploads": 0, "pavo_units": 13}
        # E138: 108 used today no longer refuses (a rolling quota); a batch larger than one window does
        self.assertEqual(g.pavo_budget(facts, api, "2026-10-28", now=now), 108)
        with self.assertRaises(g.Refusal) as c:
            g.pavo_budget(dict(facts, pavo_units=self.quota.DAILY_CAP + 1), api, "2026-10-28", now=now)
        self.assertTrue(str(c.exception).startswith("PAVO_BUDGET_SHORT"), c.exception)
        api = self.api(failed=2, date="2026-10-28T00:30:00Z")              # the last run ended on 2 failed read-backs
        with self.assertRaises(g.Refusal) as c:
            g.pavo_budget(dict(facts, pavo_units=2), api, "2026-10-28", now=now)
        self.assertTrue(str(c.exception).startswith("PAVO_FREE_QUOTA_SUSPECTED"), c.exception)

    def test_e138_the_shorts_take_at_most_their_share_and_the_long_the_rest(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc)
        usage = {"units": 60, "failed_tail": 0, "last_at": None, "short_units": 2 * 20}   # 20 Short jobs today
        with mock.patch.object(g, "pavo_actions_usage", return_value=usage):
            with self.assertRaises(g.Refusal) as c:
                g.pavo_budget({"uploads": 0, "pavo_units": 12, "short": True}, None, "2026-10-28", now=now)
            self.assertTrue(str(c.exception).startswith("PAVO_SHORTS_SHARE"), c.exception)
            g.pavo_budget({"uploads": 0, "pavo_units": 10, "short": True}, None, "2026-10-28", now=now)   # 25 of 25
            g.pavo_budget({"uploads": 0, "pavo_units": 100, "short": False}, None, "2026-10-28", now=now)  # the long
        self.assertTrue(g.shot_probe({"plan": PLAN, "shots": S1, "attempts": "1", "adopt_run": ""})["short"])
        self.assertFalse(g.shot_probe({"plan": LONG_PLAN, "shots": L1, "attempts": "1", "adopt_run": ""})["short"])
        api = self.api(ok=4, date="2026-10-28T00:30:00Z")
        self.assertEqual(g.pavo_actions_usage(api, "2026-10-28", now)["short_units"], 0)   # an arc-01-long record

    def test_capacity_checks_the_budget_and_the_probe_gets_the_count(self):
        with mock.patch.object(g, "pavo_budget", return_value=57) as budget:
            facts = {"uploads": 0, "pavo_units": 10}
            g.capacity("shot-probe.yml", facts, fake_api([]), "2026-10-27")
            self.assertEqual(facts["pavo_used"], 57)
            g.capacity("shot-probe.yml", {"uploads": 0, "pavo_units": 0}, fake_api([]), "2026-10-27")
            self.assertEqual(budget.call_count, 1)                          # an adopt run spends nothing
        src = (HERE / "dispatch_guard.py").read_text()
        self.assertIn('out.write(f"pavo_used={facts[\'pavo_used\']}\\n")', src)


class PavoBudgetReview475(unittest.TestCase):
    """Review of #475: the REST count never passes what it could not read (an unreadable record, more branches than it
    scans), and a stop shortly before 00:00 UTC still holds after it."""
    setUp, tearDown, api = PavoBudget.setUp, PavoBudget.tearDown, PavoBudget.api

    def test_an_unreadable_record_or_too_many_branches_refuses(self):
        bad = fake_api([("branches?", [{"name": "claude/shot-probe-arc-01-long-40592173923", "commit": {"sha": "p1"}}]),
                        ("commits/p1", {"commit": {"committer": {"date": "2026-10-27T22:41:42Z"}}}),
                        ("contents/", {"content": "not base64 json"})])
        with self.assertRaises(g.Refusal) as c:
            g.pavo_actions_usage(bad, "2026-10-27")
        self.assertTrue(str(c.exception).startswith("PAVO_BUDGET_UNREADABLE"), c.exception)
        full = [{"name": f"claude/other-{k}", "commit": {"sha": "x"}} for k in range(100)]
        many = fake_api([("branches?", full)])                  # every page full: more remain after the last scanned
        with self.assertRaises(g.Refusal) as c:
            g.pavo_actions_usage(many, "2026-10-27")
        self.assertTrue(str(c.exception).startswith("PAVO_BUDGET_UNREADABLE"), c.exception)

    def test_a_stop_just_before_midnight_holds_after_it(self):
        from datetime import datetime, timezone
        after = datetime(2026, 10, 28, 0, 30, tzinfo=timezone.utc)
        api = self.api(failed=3, date="2026-10-27T23:30:00Z")
        usage = g.pavo_actions_usage(api, "2026-10-28", after)
        self.assertEqual((usage["units"], usage["failed_tail"]), (0, 3))   # yesterday's units, the stop still on
        with self.assertRaises(g.Refusal) as c:
            g.pavo_budget({"uploads": 0, "pavo_units": 2}, api, "2026-10-28", now=after)
        self.assertTrue(str(c.exception).startswith("PAVO_FREE_QUOTA_SUSPECTED"), c.exception)


if __name__ == "__main__":
    unittest.main()
