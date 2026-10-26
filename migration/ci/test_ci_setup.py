#!/usr/bin/env python3
"""Offline checks of the CI setup scripts (E102): the shared bounded apt install (E55), the parallel hash-checked asset
fetch, the render's disk check and bounded setup, the pr-checks runner, the pip cache keys and the job timeouts."""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "migration/ci"
WF = ROOT / ".github/workflows"
CACHE_PIN = "5a3ec84eff668545956fd18022155c47e93e2684"   # actions/cache v4.2.3 (lightweight tag, checked 2026-10-26)
BASE_PATH = "/usr/bin:/bin"


def step_script(workflow, step_name):
    """The `run: |` body of one step, unindented, as the runner executes it."""
    text = (WF / workflow).read_text()
    i = text.index(f"- name: {step_name}")
    j = text.index("run: |\n", i) + len("run: |\n")
    k = text.find("\n      - ", j)
    body = text[j:k if k > 0 else None]
    return "\n".join(line[10:] for line in body.splitlines())


def stage(name):
    """One stage of render_pilot.sh, from its `stage "..."` line to its `end`."""
    text = (CI / "render_pilot.sh").read_text()
    i = text.index(f'stage "{name}')
    return text[i:text.index("\nend\n", i) + len("\nend\n")]


def fake_bin(d, **scripts):
    """A directory of fake commands, first on PATH."""
    b = Path(d) / "bin"
    b.mkdir(exist_ok=True)
    for name, body in scripts.items():
        (b / name).write_text("#!/usr/bin/env bash\n" + body)
        (b / name).chmod(0o755)
    return str(b)


class AptInstall(unittest.TestCase):
    SOURCES = ("Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors.txt\nSuites: noble noble-updates\n\n"
               "Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors-security.txt\nSuites: noble-security\n")

    def run_apt(self, d, *pkgs, hang=False, **env):
        log = Path(d) / "apt.log"
        b = fake_bin(d, sudo='exec "$@"\n',
                     **{"apt-get": f'echo "$*" >> "{log}"\n' + ('[ "${*: -1}" = update ] && sleep 30\n' if hang else "")})
        src = Path(d) / "ubuntu.sources"
        src.write_text(self.SOURCES)
        full = {"PATH": f"{b}:{BASE_PATH}", "RUNNER_TEMP": str(d), "APT_SOURCES": str(src), **env}
        start = time.monotonic()
        out = subprocess.run(["bash", str(CI / "apt_install.sh"), *pkgs], capture_output=True, text=True, env=full)
        return out, (log.read_text() if log.exists() else ""), time.monotonic() - start

    def test_official_origins_and_every_command_bounded(self):
        # E55: runs 39823760082 and 40000227373 hung on the hosted apt mirror; one shared script, one hardening
        with tempfile.TemporaryDirectory() as d:
            out, log, _ = self.run_apt(d, "ffmpeg", "python3-opencv")
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            lines = log.splitlines()
            self.assertEqual(len(lines), 2)
            self.assertTrue(lines[0].endswith(" update -qq"), lines[0])
            self.assertIn("install -y -qq --no-install-recommends ffmpeg python3-opencv", lines[1])
            rewritten = Path(d) / "heroverse-ubuntu.sources"
            for line in lines:
                self.assertIn(f"Dir::Etc::sourcelist={rewritten}", line)
                self.assertIn("Acquire::https::Timeout=20", line)
            text = rewritten.read_text()
            self.assertNotIn("mirror+file", text)
            self.assertIn("https://archive.ubuntu.com/ubuntu/", text)
            self.assertIn("https://security.ubuntu.com/ubuntu/", text)
            script = (CI / "apt_install.sh").read_text()
            for line in re.findall(r".*apt-get .*(?:update|install).*", script):
                self.assertIn("timeout ", line)

    def test_a_hung_mirror_is_cut_off(self):
        with tempfile.TemporaryDirectory() as d:
            out, _, took = self.run_apt(d, "ffmpeg", hang=True, APT_UPDATE_TIMEOUT="1s")
            self.assertNotEqual(out.returncode, 0)
            self.assertLess(took, 10)

    def test_bad_input_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(self.run_apt(d)[0].returncode, 0)                        # no package
            out, log, _ = self.run_apt(d, "ffmpeg; rm -rf /")
            self.assertIn("APT_PACKAGE_REFUSED", out.stdout)
            self.assertEqual(log, "")

    def test_every_engine_apt_install_goes_through_it(self):
        for path in (WF / "pr-checks.yml", WF / "voice-sample.yml", CI / "render_pilot.sh"):
            text = path.read_text()
            self.assertIsNone(re.search(r".*apt-get\s.*", text), path.name)
            self.assertTrue("apt_install.sh" in text, path.name)


class FetchAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.d = Path(self.tmp.name)
        self.store, self.dest = d / "store", d / "dest"
        self.store.mkdir()
        self.dest.mkdir()
        self.shas = {}
        for i in range(6):
            (self.store / f"a{i}.bin").write_bytes(f"asset {i}".encode())
            self.shas[f"a{i}.bin"] = hashlib.sha256(f"asset {i}".encode()).hexdigest()
        self.fake = d / "assets.sh"   # stands in for assets.sh: download --repo R --pattern NAME -O FILE --clobber
        self.fake.write_text('#!/usr/bin/env bash\nset -e\n[ "$1" = download ] && [ "$2" = --repo ] && [ "$4" = --pattern ]\n'
                             f'echo "$5" >> "{d}/calls"\ncp "{self.store}/$5" "$7"\n')
        self.rows = [(n, str(self.dest / n), s) for n, s in self.shas.items()]

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, rows):
        lst = self.d / "list.tsv"
        lst.write_text("".join("\t".join(r) + "\n" for r in rows))
        return subprocess.run(["bash", str(CI / "fetch_assets.sh"), str(lst), "owner/repo", "3"],
                              capture_output=True, text=True, env={"PATH": BASE_PATH, "ASSETS": str(self.fake)})

    def test_every_hash_checked_and_any_miss_fails(self):
        out = self.fetch(self.rows)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("FETCHED 6", out.stdout)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), sorted(self.shas))
        wrong = self.rows[:2] + [(self.rows[2][0], self.rows[2][1], "0" * 64)] + self.rows[3:]
        out = self.fetch(wrong)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("FETCH_HASH_MISMATCH a2.bin", out.stdout)
        self.assertNotEqual(self.fetch(self.rows + [("missing.bin", str(self.dest / "m"), "1" * 64)]).returncode, 0)
        self.assertIn("FETCH_LIST_MALFORMED", self.fetch([("a0.bin", str(self.dest / "a0.bin"))]).stdout)
        self.assertNotEqual(self.fetch([("a0.bin", str(self.dest / "a0.bin"), "not-a-sha")]).returncode, 0)

    def test_identical_lines_are_fetched_once(self):
        # two workers writing and checking the same file at once could pass a torn file or fail a good one
        out = self.fetch(self.rows + self.rows[:3])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("FETCHED 6", out.stdout)
        self.assertEqual(sorted((self.d / "calls").read_text().split()), sorted(self.shas))

    def test_one_destination_with_two_hashes_is_refused(self):
        clash = self.rows + [(self.rows[1][0], self.rows[0][1], self.rows[1][2])]   # a1's bytes into a0's file
        out = self.fetch(clash)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("FETCH_DUPLICATE_DEST", out.stdout)
        self.assertFalse((self.d / "calls").exists())                              # refused before any download


class RenderSetup(unittest.TestCase):
    def disk(self, root_gb, temp_gb):
        """Runs the disk stage with df answering per path; returns whether the SDKs were deleted."""
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "temp"
            t.mkdir()
            b = fake_bin(d, sudo=f'echo "$*" >> "{d}/sudo"\n',
                         df=f'for a in "$@"; do last=$a; done\nif [ "$last" = "{t}" ]; then n={temp_gb}; else n={root_gb}; fi\n'
                            'echo "Avail"; echo " ${n}G"\n')
            script = 'stage() { :; }; end() { :; }\nT="$1"\n' + stage("Free runner disk")
            out = subprocess.run(["bash", "-e", "-c", script, "_", str(t)], capture_output=True, text=True,
                                 env={"PATH": f"{b}:{BASE_PATH}"})
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            return (Path(d) / "sudo").exists() and "rm -rf" in (Path(d) / "sudo").read_text()

    def test_sdks_are_deleted_when_root_or_temp_is_short(self):
        # the SDKs live on /, the render writes to $T: either one short of space frees the disk
        self.assertFalse(self.disk(85, 85))
        self.assertTrue(self.disk(20, 85))
        self.assertTrue(self.disk(85, 20))

    def test_every_setup_command_is_bounded(self):
        # the tools install in the background and the render waits for them: each command must end by itself
        tools = stage("Tools and pinned runtimes")
        self.assertTrue("apt_install.sh" in tools)
        self.assertRegex(tools, r'venv\(\) \{ timeout \S+ python3 -m venv .*&& timeout \S+ "\$T/\$1/bin/pip" install ')
        self.assertIn("curl -fsSL --retry 3 --max-time ", tools)
        self.assertIn('wait "${job%%:*}" || { echo "SETUP_FAILED', tools)
        for venv in ("voice", "qa", "cut", "cine"):
            self.assertIn(f"setup {venv} venv {venv} ", tools)

    def test_assets_are_fetched_in_parallel_with_hashes(self):
        render = (CI / "render_pilot.sh").read_text()
        self.assertIn('fetch_assets.sh" "$FETCH" "$ENGINE_REPO"', render)
        self.assertNotRegex(render, r'download --repo "\$ENGINE_REPO" --pattern "\$asset"')   # no serial fetch left


class PrChecks(unittest.TestCase):
    def test_every_pr_runs_every_check_and_only_the_superseded_run_is_cancelled(self):
        pr = (WF / "pr-checks.yml").read_text()
        on = pr[pr.index("on:"):pr.index("permissions:")]
        self.assertNotIn("paths", on)
        self.assertIn("group: heroverse-pr-checks-${{ github.event.pull_request.number }}\n  cancel-in-progress: true", pr)
        self.assertTrue("migration/ci/test_ci_setup.py" in pr)

    def test_job_timeout_covers_its_steps(self):
        pr = (WF / "pr-checks.yml").read_text()
        job = int(re.search(r"\n    timeout-minutes: (\d+)", pr).group(1))
        steps = [int(x) for x in re.findall(r"\n        timeout-minutes: (\d+)", pr)]
        self.assertTrue(steps)
        self.assertGreater(job, sum(steps))

    def test_tests_start_after_the_video_tools(self):
        # a test that probes ffmpeg or cv2 (directly or through a module) must never run before the install
        pr = (WF / "pr-checks.yml").read_text()
        self.assertLess(pr.index("- name: ffmpeg and OpenCV for the video tests"), pr.index("- name: Unit tests"))
        self.assertNotIn("VIDEO=", pr)
        self.assertNotIn("video_tools", pr)

    def test_parallel_runner_reports_every_result_and_fails_on_any_failure(self):
        script = step_script("pr-checks.yml", "Unit tests (no network, no secrets)")
        self.assertTrue("jobs -rp" in script)
        self.assertIn("wait -n", script)
        self.assertNotIn("kill -0", script)
        self.assertNotIn("sleep", script)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a_pass.py").write_text("print('ok')\n")
            (d / "b_fail.py").write_text("import sys; print('boom'); sys.exit(3)\n")
            (d / "c_pass.py").write_text("import time; time.sleep(0.3)\n")
            (d / "d_crash.py").write_text("raise RuntimeError('crash')\n")

            def run(names):
                s = re.sub(r"for t in .*?; do\n", f"for t in {' '.join(str(d / n) for n in names)}; do\n", script,
                           count=1, flags=re.S)
                tmp = tempfile.mkdtemp(dir=d)
                return subprocess.run(["bash", "-e", "-c", s], capture_output=True, text=True,
                                      env={"PATH": BASE_PATH, "RUNNER_TEMP": tmp})
            out = run(["a_pass.py", "b_fail.py", "c_pass.py", "d_crash.py"])
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            lines = [l for l in out.stdout.splitlines() if l.startswith(("PASS ", "FAIL "))]
            self.assertEqual(lines, [f"PASS {d}/a_pass.py", f"FAIL {d}/b_fail.py", f"PASS {d}/c_pass.py",
                                     f"FAIL {d}/d_crash.py"])
            self.assertIn("boom", out.stdout)
            self.assertIn("RuntimeError: crash", out.stdout)
            self.assertEqual(run(["a_pass.py", "c_pass.py"]).returncode, 0)


class PipCache(unittest.TestCase):
    def test_keys_on_the_pin_lines_only_without_a_fallback(self):
        # a restore-keys fallback restores an older cache under a new key and saves it again, growing stale caches
        for name, source in (("pilot-preview.yml", "migration/ci/render_pilot.sh"),
                             ("pilot-render-stills.yml", "migration/ci/render_pilot.sh"),
                             ("render-smoke.yml", "migration/ci/render_pilot.sh"),
                             ("pavo-footage.yml", ".github/workflows/pavo-footage.yml")):
            text = (WF / name).read_text()
            uses = re.findall(r"uses: (actions/cache\S*)", text)
            self.assertTrue(uses, name)
            self.assertTrue(all(u.endswith("@" + CACHE_PIN) for u in uses), name)
            self.assertNotIn("restore-keys", text, name)
            self.assertIn("steps.pins.outputs.hash", text, name)
            self.assertIn(source, text[text.index("id: pins"):text.index("steps.pins.outputs.hash")], name)
        self.assertIn("actions/cache/restore@", (WF / "render-smoke.yml").read_text())   # a PR never saves a cache
        render_pins = re.findall(r"^setup [a-z]+ venv .*$", (CI / "render_pilot.sh").read_text(), re.M)
        self.assertEqual(len(render_pins), 4)
        upres_pins = re.findall(r'^.*/bin/pip" install .*$', (WF / "pavo-footage.yml").read_text(), re.M)
        self.assertEqual(len(upres_pins), 2)


if __name__ == "__main__":
    unittest.main()
