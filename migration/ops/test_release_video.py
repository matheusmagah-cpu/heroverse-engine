#!/usr/bin/env python3
"""Offline: E60 long renders larger than a release asset are stored in parts and rejoined, hash-verified."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "migration/ci/release_video.sh"
FAKE_GH = r'''#!/usr/bin/env python3
import fnmatch, os, shutil, sys
store = os.environ["FAKE_RELEASE"]; a = sys.argv[1:]
if a[:2] == ["release", "upload"]:
    for f in [x for x in a[3:] if not x.startswith("--") and x not in (os.environ.get("REPO"),)]:
        if os.path.isfile(f): shutil.copy(f, store)
elif a[:2] == ["release", "download"]:
    pat = a[a.index("--pattern") + 1]; dest = a[a.index("-D") + 1]
    hits = [n for n in os.listdir(store) if fnmatch.fnmatch(n, pat)]
    if not hits: print("no assets match the file pattern", file=sys.stderr); sys.exit(1)
    for n in hits: shutil.copy(os.path.join(store, n), dest)
elif a[:2] == ["release", "view"]:
    print("\n".join(sorted(os.listdir(store))))
elif a[0] == "api" and "/releases/tags/" in a[1]:   # assets.sh asset_names (E91): the REST release object
    print("\n".join(sorted(os.listdir(store))))
elif a[:2] == ["release", "delete-asset"]:
    os.remove(os.path.join(store, a[3]))
'''


class ReleaseVideo(unittest.TestCase):
    def run_script(self, env, *args):
        return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True)

    def test_large_render_is_split_rejoined_verified_and_deleted(self):
        # E60: pilot-009's 2.1 GB render was refused by the release (assets must be < 2 GiB)
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "bin").mkdir(); (t / "store").mkdir()
            gh = t / "bin" / "gh"; gh.write_text(FAKE_GH); gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{t / 'bin'}:{os.environ['PATH']}", "FAKE_RELEASE": str(t / "store"),
                   "TAG": "v", "REPO": "o/r", "RELEASE_PART_BYTES": "1000"}
            video = t / "pilot.mp4"; video.write_bytes(os.urandom(2500))
            sha = hashlib.sha256(video.read_bytes()).hexdigest()
            name = f"pilot-009-sha256-{sha}.mp4"
            self.assertEqual(self.run_script(env, "put", str(video), name).returncode, 0)
            self.assertEqual(sorted(os.listdir(t / "store")), [f"{name}.part0{i}" for i in (1, 2, 3)])
            out = t / "back.mp4"
            r = self.run_script(env, "get", name, sha, str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_bytes(), video.read_bytes())
            self.assertNotEqual(self.run_script(env, "get", name, "0" * 64, str(out)).returncode, 0)  # wrong hash fails
            self.assertEqual(self.run_script(env, "del", name).returncode, 0)
            self.assertEqual(os.listdir(t / "store"), [])
            small = t / "small.mp4"; small.write_bytes(b"x" * 10)
            self.run_script(env, "put", str(small), "s.mp4")
            self.assertEqual(os.listdir(t / "store"), ["s.mp4"])          # a small render stays one asset

    def test_every_long_render_consumer_uses_the_helper(self):
        for wf in ("approve.yml", "publish.yml", "reviewer-calibration.yml"):
            text = (ROOT / ".github/workflows" / wf).read_text()
            self.assertNotRegex(text, r'--pattern "\$P(ILOT)?-sha256-\$sha\.mp4"', wf)
            self.assertIn("migration/ci/release_video.sh", text, wf)
        self.assertIn("release_video.sh put", (ROOT / "migration/ci/render_pilot.sh").read_text())


if __name__ == "__main__":
    unittest.main()
