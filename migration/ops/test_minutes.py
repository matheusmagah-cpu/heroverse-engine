#!/usr/bin/env python3
"""Offline checks of the Actions minutes report (a speed measure: public repo, standard runners free; E102) and of
the CI speedups found while measuring it."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import minutes as m  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github/workflows"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
CACHE_PIN = "5a3ec84eff668545956fd18022155c47e93e2684"   # actions/cache v4.2.3


def run(name, created, started, updated, conclusion="success"):
    return {"name": name, "created_at": created, "run_started_at": started, "updated_at": updated,
            "status": "completed", "conclusion": conclusion}


def step_script(workflow, step_name):
    """The `run: |` body of one step, unindented, as the runner executes it."""
    text = (WF / workflow).read_text()
    i = text.index(f"- name: {step_name}")
    j = text.index("run: |\n", i) + len("run: |\n")
    k = text.find("\n      - ", j)
    body = text[j:k if k > 0 else None]
    return "\n".join(line[10:] for line in body.splitlines())


class Minutes(unittest.TestCase):
    def test_rounding_windows_and_alerts(self):
        # E21's antidote, kept: each run rounds up to a whole minute and lands in its windows. E102: no alerts any more
        runs = [run("approve", "2026-10-20T08:00:00Z", "2026-10-20T08:00:00Z", "2026-10-20T08:14:10Z"),   # 15 min
                run("heartbeat", "2026-10-20T09:00:00Z", "2026-10-20T09:00:00Z", "2026-10-20T09:00:20Z"),  # 1 min
                run("old", "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", "2026-09-01T02:00:00Z"),        # outside 30 d
                {**run("q", "2026-10-20T10:00:00Z", None, "2026-10-20T10:00:00Z"), "run_started_at": None}]  # never ran
        s = m.summary(runs, NOW)
        self.assertEqual(s["windows"], {"24h": 16, "7d": 16, "30d": 16})
        self.assertEqual(s["top"][0], {"workflow": "approve", "minutes": 15, "runs": 1, "per_run": 15.0})
        self.assertNotIn("alerts", s)

    def test_report_is_a_speed_metric_with_no_budget_alarm(self):
        # E102: the engine is public and standard runners are free for public repos; the report said "private
        # engine; budget 7000 min / 30 days" and raised a spending alarm that did not exist
        heavy = [run("render", "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:00:00Z" % h, "2026-10-20T0%d:59:00Z" % h)
                 for h in range(1, 7)]                                      # 354 min in a day: no alarm
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "runs.json").write_text(json.dumps(heavy))
            m.main(str(Path(d) / "runs.json"), str(Path(d) / "report.md"), NOW.isoformat())
            report = (Path(d) / "report.md").read_text()
        self.assertIn("## Actions minutes (speed only; public repo: standard runners free)", report)
        self.assertIn("| render | 354 | 6 | 59.0 |", report)
        for word in ("budget", "overage", "projection", "\u26a0", "target"):
            self.assertNotIn(word, report.lower())
        source = (ROOT / "migration/ops/minutes.py").read_text()
        self.assertNotRegex(source, r"BUDGET\s*=|7000|overage alert")
        self.assertNotIn("minutes.py check", (WF / "heartbeat.yml").read_text())
        system = (ROOT / "migration/SYSTEM.md").read_text()
        self.assertNotIn("7000 / 30 days", system)
        self.assertIn("standard GitHub-hosted runners are free for public repositories", system)
        self.assertIn("public repo, standard runners free", (WF / "goal-report.yml").read_text())

    def test_ci_does_not_wait_on_idle_setup_or_superseded_runs(self):
        # E102 (speed): the render path spent ~1.5 min deleting SDKs it did not need, ~2 min installing four venvs
        # one after another and ~4 min downloading ~150 assets one at a time on every smoke, preview and render;
        # every push to a PR re-ran its check beside the superseded one
        render = (ROOT / "migration/ci/render_pilot.sh").read_text()
        self.assertIn('if [ "${avail_gb:-0}" -lt "${FREE_DISK_BELOW_GB:-40}" ]; then', render)
        self.assertIn('wait "${job%%:*}" || { echo "SETUP_FAILED', render)
        for venv in ("voice", "qa", "cut", "cine"):
            self.assertIn(f"setup {venv} venv {venv} ", render)
        self.assertIn('fetch_assets.sh" "$FETCH" "$ENGINE_REPO"', render)
        self.assertNotRegex(render, r'download --repo "\$ENGINE_REPO" --pattern "\$asset"')   # no serial fetch left
        pr = (WF / "pr-checks.yml").read_text()
        on = pr[pr.index("on:"):pr.index("permissions:")]
        self.assertNotIn("paths", on)                  # every PR, whatever it changes, runs every check
        self.assertIn("group: heroverse-pr-checks-${{ github.event.pull_request.number }}\n  cancel-in-progress: true", pr)
        for name in ("pilot-preview.yml", "pilot-render-stills.yml", "render-smoke.yml", "pavo-footage.yml"):
            uses = re.findall(r"uses: (actions/cache\S*)", (WF / name).read_text())
            self.assertTrue(uses, name)
            self.assertTrue(all(u.endswith("@" + CACHE_PIN) for u in uses), name)   # pinned, like every action here
        self.assertIn("actions/cache/restore@", (WF / "render-smoke.yml").read_text())   # a PR never saves a cache

    def test_parallel_unit_tests_report_every_result_and_fail_on_any_failure(self):
        script = step_script("pr-checks.yml", "Unit tests (no network, no secrets), ffmpeg and OpenCV installing")
        self.assertIn("migration/ops/test_minutes.py", script)

        def fake(d, tests, video, tools_rc=0):
            """The real step with its test list, its VIDEO list and the apt install replaced (the install writes a
            marker; a VIDEO test fails when it starts before the marker exists)."""
            s = re.sub(r"for t in .*?; do\n", f"for t in {' '.join(str(d / t) for t in tests)}; do\n", script,
                       count=1, flags=re.S)
            s = re.sub(r'VIDEO=" .*?"\n', f'VIDEO=" {" ".join(str(d / t) for t in video)} "\n', s, count=1, flags=re.S)
            s = re.sub(r"video_tools\(\) \{\n.*?\n          \}\n".replace("          ", ""),
                       f"video_tools() {{ sleep 0.5; touch {d}/tools-ready; return {tools_rc}; }}\n", s, count=1, flags=re.S)
            self.assertIn(f"touch {d}/tools-ready", s)
            tmp = Path(tempfile.mkdtemp(dir=d))
            return subprocess.run(["bash", "-e", "-c", s], capture_output=True, text=True,
                                  env={"PATH": "/usr/bin:/bin", "RUNNER_TEMP": str(tmp)})
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a_pass.py").write_text("print('ok')\n")
            (d / "b_fail.py").write_text("import sys; print('boom'); sys.exit(3)\n")
            (d / "c_pass.py").write_text("import time; time.sleep(0.3)\n")
            (d / "d_crash.py").write_text("raise RuntimeError('crash')\n")
            (d / "v_video.py").write_text(f"import os, sys; sys.exit(0 if os.path.exists({str(d / 'tools-ready')!r}) "
                                          "else 'STARTED_BEFORE_TOOLS')\n")
            out = fake(d, ["a_pass.py", "b_fail.py", "v_video.py", "c_pass.py", "d_crash.py"], ["v_video.py"])
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            lines = [l for l in out.stdout.splitlines() if l.startswith(("PASS ", "FAIL "))]
            self.assertEqual(lines, [f"PASS {d}/a_pass.py", f"FAIL {d}/b_fail.py", f"PASS {d}/v_video.py",
                                     f"PASS {d}/c_pass.py", f"FAIL {d}/d_crash.py"])
            self.assertIn("boom", out.stdout)
            self.assertIn("RuntimeError: crash", out.stdout)
            ok = fake(d, ["a_pass.py", "v_video.py", "c_pass.py"], ["v_video.py"])
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            (d / "tools-ready").unlink()
            early = fake(d, ["a_pass.py", "v_video.py"], [])          # a video test left out of VIDEO fails loudly
            self.assertEqual(early.returncode, 1)
            self.assertIn("STARTED_BEFORE_TOOLS", early.stdout)
            broken = fake(d, ["a_pass.py", "v_video.py"], ["v_video.py"], tools_rc=1)
            self.assertEqual(broken.returncode, 1)
            self.assertIn("VIDEO_TOOLS_FAILED", broken.stdout)

    def test_tests_that_can_skip_without_the_video_tools_wait_for_them(self):
        # a test that skips when ffmpeg is missing would pass silently if it ran before the install
        script = step_script("pr-checks.yml", "Unit tests (no network, no secrets), ffmpeg and OpenCV installing")
        video = set(re.search(r'VIDEO=" (.*?)"\n', script, re.S).group(1).replace("\\", " ").split())
        listing = re.search(r"for t in (.*?); do\n", script, re.S).group(1).replace("\\", " ").split()
        tests = {str(p.relative_to(ROOT)) for pat in listing for p in ROOT.glob(pat)}
        self.assertLessEqual(video, tests)
        uses = re.compile(r"@unittest\.skip|\bSkipTest\b|\.skipTest\(|^\s*(?:import (?:cv2|numpy|PIL)|from (?:cv2|numpy|PIL)\b)",
                          re.M)
        for rel in sorted(tests - video):
            hit = uses.search((ROOT / rel).read_text())
            self.assertIsNone(hit, f"{rel} uses {hit and hit.group(0)!r}: list it in VIDEO")
        self.assertIn("timeout 90s sudo apt-get", script)                                  # E55 kept inside the step

    def test_parallel_fetch_checks_every_hash_and_fails_on_any_miss(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            store, dest = d / "store", d / "dest"
            store.mkdir()
            dest.mkdir()
            shas = {}
            for i in range(6):
                (store / f"a{i}.bin").write_bytes(f"asset {i}".encode())
                shas[f"a{i}.bin"] = hashlib.sha256(f"asset {i}".encode()).hexdigest()
            fake = d / "assets.sh"   # stands in for assets.sh: download --repo R --pattern NAME -O FILE --clobber
            fake.write_text('#!/usr/bin/env bash\nset -e\n[ "$1" = download ] && [ "$2" = --repo ] && [ "$4" = --pattern ]\n'
                            f'cp "{store}/$5" "$7"\n')
            env = {"PATH": "/usr/bin:/bin", "ASSETS": str(fake)}

            def fetch(rows):
                lst = d / "list.tsv"
                lst.write_text("".join("\t".join(r) + "\n" for r in rows))
                return subprocess.run(["bash", str(ROOT / "migration/ci/fetch_assets.sh"), str(lst), "owner/repo", "3"],
                                      capture_output=True, text=True, env=env)
            rows = [(n, str(dest / n), s) for n, s in shas.items()]
            out = fetch(rows)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn("FETCHED 6", out.stdout)
            self.assertEqual(sorted(p.name for p in dest.iterdir()), sorted(shas))
            wrong = rows[:2] + [(rows[2][0], rows[2][1], "0" * 64)] + rows[3:]
            out = fetch(wrong)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("FETCH_HASH_MISMATCH a2.bin", out.stdout)
            self.assertNotEqual(fetch(rows + [("missing.bin", str(dest / "m"), "1" * 64)]).returncode, 0)
            self.assertIn("FETCH_LIST_MALFORMED", fetch([("a0.bin", str(dest / "a0.bin"))]).stdout)
            self.assertNotEqual(fetch([("a0.bin", str(dest / "a0.bin"), "not-a-sha")]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
