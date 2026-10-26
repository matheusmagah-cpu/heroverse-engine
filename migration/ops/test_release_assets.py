#!/usr/bin/env python3
"""Offline: E85 a GitHub release holds at most 1000 assets. New assets go to the newest release, reads try newest first."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "migration/ci/assets.sh"
NEW, OLD = "v0.0.0-cloud-assets-20261025", "v0.0.0-cloud-assets-20261013"
FAKE_GH = r'''#!/usr/bin/env python3
import fnmatch, os, shutil, sys
root = os.environ["FAKE_RELEASES"]; a = sys.argv[1:]
def store(tag):
    d = os.path.join(root, tag)
    if not os.path.isdir(d): print("release not found", file=sys.stderr); sys.exit(1)
    return d
def opt(name): return a[a.index(name) + 1] if name in a else None
if a[:2] == ["release", "create"]:
    os.makedirs(os.path.join(root, a[2]))
elif a[:2] == ["release", "upload"]:
    d = store(a[2])
    files = [x for x in a[3:] if os.path.isfile(x.split("#")[0])]
    if len(os.listdir(d)) + len(files) > int(os.environ.get("FAKE_CAP", "1000")):
        print("HTTP 422: Validation Failed\nfile_count limited to 1000 assets per release", file=sys.stderr); sys.exit(1)
    for f in files: shutil.copy(f.split("#")[0], d)
elif a[:2] == ["release", "download"]:
    d = store(a[2]); pat = opt("--pattern")
    hits = [n for n in sorted(os.listdir(d)) if fnmatch.fnmatch(n, pat)]
    if not hits: print("no assets match the file pattern", file=sys.stderr); sys.exit(1)
    if opt("-O"): shutil.copy(os.path.join(d, hits[0]), opt("-O"))
    else:
        for n in hits: shutil.copy(os.path.join(d, n), opt("-D") or ".")
elif a[:2] == ["release", "view"]:   # like the runner on 2026-10-26 (E91): lists only part of a big release
    d = store(a[2])
    if "--jq" in a and "length" in opt("--jq"): print(min(len(os.listdir(d)), 100))
    else: print("\n".join(sorted(os.listdir(d))[:100]))
elif a[0] == "api" and "/releases/tags/" in a[1]:   # the REST release object: every asset
    d = os.path.join(root, a[1].rsplit("/", 1)[1])
    if not os.path.isdir(d): print("gh: Not Found (HTTP 404)", file=sys.stderr); sys.exit(1)
    print("\n".join(sorted(os.listdir(d))))
elif a[:2] == ["release", "delete-asset"]:
    p = os.path.join(store(a[2]), a[3])
    if not os.path.exists(p): print("asset not found", file=sys.stderr); sys.exit(1)
    os.remove(p)
else:
    print("unexpected gh call", a, file=sys.stderr); sys.exit(3)
'''


class ReleaseAssets(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp())
        (self.t / "bin").mkdir(); (self.t / "rel" / OLD).mkdir(parents=True)
        gh = self.t / "bin" / "gh"; gh.write_text(FAKE_GH); gh.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.t / 'bin'}:{os.environ['PATH']}", "FAKE_RELEASES": str(self.t / "rel"),
                    "GITHUB_REPOSITORY": "o/r"}

    def run_script(self, *args, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], env={**self.env, **env}, capture_output=True, text=True)

    def put_old(self, name, data):
        (self.t / "rel" / OLD / name).write_bytes(data)

    def test_full_release_upload_goes_to_the_newest_release_created_once(self):
        # E85: footage run 40218507819 died at asset 1001 of v0.0.0-cloud-assets-20261013 (HTTP 422 file_count)
        f = self.t / "clip.mp4"; f.write_bytes(b"new")
        r = self.run_script("upload", str(f), "--repo", "o/r", "--clobber", FAKE_CAP="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.t / "rel" / NEW), ["clip.mp4"])
        self.assertEqual(os.listdir(self.t / "rel" / OLD), [])
        self.assertEqual(self.run_script("upload", str(f), "--repo", "o/r").returncode, 0)  # release exists: no 2nd create

    def test_download_tries_newest_first_and_falls_back(self):
        self.put_old("a.mp4", b"old-a"); self.put_old("b.mp4", b"old-b")
        (self.t / "rel" / NEW).mkdir(); (self.t / "rel" / NEW / "b.mp4").write_bytes(b"new-b")
        out = self.t / "out"
        r = self.run_script("download", "--repo", "o/r", "--pattern", "a.mp4", "-O", str(out))
        self.assertEqual((r.returncode, out.read_bytes()), (0, b"old-a"), r.stderr)
        self.run_script("download", "--repo", "o/r", "--pattern", "b.mp4", "-O", str(out))
        self.assertEqual(out.read_bytes(), b"new-b")
        r = self.run_script("download", "--repo", "o/r", "--pattern", "missing.mp4", "-O", str(out))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no assets match", r.stderr)

    def test_download_works_before_the_new_release_exists(self):
        self.put_old("a.mp4", b"old-a")
        d = self.t / "d"; d.mkdir()
        r = self.run_script("download", "--repo", "o/r", "--pattern", "a.mp4", "-D", str(d))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(d), ["a.mp4"])

    def test_names_which_and_delete_cover_every_release(self):
        self.put_old("a.mp4", b"1"); self.put_old("b.mp4", b"1")
        (self.t / "rel" / NEW).mkdir(); (self.t / "rel" / NEW / "b.mp4").write_bytes(b"2")
        r = self.run_script("names", "--repo", "o/r")
        self.assertEqual(sorted(r.stdout.split()), ["a.mp4", "b.mp4", "b.mp4"])
        self.assertEqual(self.run_script("which", "a.mp4", "--repo", "o/r").stdout.strip(), OLD)
        self.assertEqual(self.run_script("which", "b.mp4", "--repo", "o/r").stdout.strip(), NEW)
        self.assertNotEqual(self.run_script("which", "zz.mp4", "--repo", "o/r").returncode, 0)
        self.assertEqual(self.run_script("delete", "b.mp4", "--repo", "o/r", "-y").returncode, 0)
        self.assertEqual(os.listdir(self.t / "rel" / NEW), [])
        self.assertEqual(sorted(os.listdir(self.t / "rel" / OLD)), ["a.mp4"])
        self.assertNotEqual(self.run_script("delete", "zz.mp4", "--repo", "o/r", "-y").returncode, 0)

    def test_which_finds_an_asset_past_the_first_hundred_of_a_full_release(self):
        # E91: the TikTok mirror of Genesis 4 failed ASSET_NOT_FOUND although `release download` found the file in the
        # 1000-asset release; `which` must read every asset name, and a real API error must not read as "absent"
        for i in range(150):
            self.put_old(f"a{i:03d}.mp4", b"x")
        self.put_old("zz-genesis-04.mp4", b"x")
        r = self.run_script("which", "zz-genesis-04.mp4", "--repo", "o/r")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, OLD), r.stderr)
        self.assertEqual(len(self.run_script("names", "--repo", "o/r").stdout.split()), 151)

    def test_no_caller_reads_or_writes_one_release_directly(self):
        bad = re.compile(r'gh release (download|upload|view|delete-asset) "?\$\{?TAG|releases/download/v0\.0\.0-cloud-assets')
        files = list((ROOT / ".github/workflows").glob("*.yml")) + list((ROOT / "migration/ci").glob("*.sh"))
        # shorts.yml and shorts-review.yml are frozen byte for byte (test_pending_shorts, test_review_recovery,
        # test_shorts_006_plan): they still read and write the 2026-10-13 release only, until their freeze is lifted
        frozen = {"shorts.yml", "shorts-review.yml"}
        offenders = [str(p.relative_to(ROOT)) for p in files
                     if p.name != "assets.sh" and p.name not in frozen and bad.search(p.read_text())]
        self.assertEqual(offenders, [])
        self.assertIn("ASSET_RELEASE_TAG", (ROOT / "migration/publish/tiktok_publish.py").read_text())
        self.assertIn('"release_tag"', (ROOT / "migration/production/characters/characters.py").read_text())
        for wf in ("cf-images.yml", "footage.yml"):   # records say which release holds their asset
            self.assertIn("release_tag", (ROOT / ".github/workflows" / wf).read_text(), wf)

    def test_cf_images_refuses_a_bad_input_by_name(self):
        # E96: pilot=migration/production/characters exited 1 with no message; the refusal must say why
        wf = (ROOT / ".github/workflows/cf-images.yml").read_text().splitlines()
        checks = "\n".join(l.strip() for l in wf if l.strip().startswith(('case "$PILOT"', 'case "$ENGINE"')))
        def run(pilot, engine="flux"):
            return subprocess.run(["bash", "-ec", checks], env={"PILOT": pilot, "ENGINE": engine, "PATH": os.environ["PATH"]},
                                  capture_output=True, text=True)
        for pilot, engine, code in (("migration/production/characters", "flux", "PILOT_INVALID"),
                                    ("characters", "dalle", "ENGINE_INVALID")):
            r = run(pilot, engine)
            self.assertEqual(r.returncode, 1)
            self.assertIn(code, r.stdout)
        for pilot in ("characters", "pilot-015"):
            self.assertEqual(run(pilot).returncode, 0)

    def test_public_urls_name_the_release_that_holds_the_file(self):
        import importlib, json, sys
        for d in ("migration/publish", "migration/production/characters"):
            sys.path.insert(0, str(ROOT / d))
        tp, ch = importlib.import_module("tiktok_publish"), importlib.import_module("characters")
        ep = {"id": "genesis-06-short", "output_sha256": "f" * 64}
        base = "https://github.com/matheusmagah-cpu/heroverse-engine/releases/download/"
        os.environ.pop("ASSET_RELEASE_TAG", None)
        self.assertEqual(tp.video_url(ep), f"{base}{OLD}/bible-genesis-06-short-sha256-{'f' * 64}.mp4")
        try:
            os.environ["ASSET_RELEASE_TAG"] = NEW
            self.assertTrue(tp.video_url(ep).startswith(f"{base}{NEW}/bible-genesis-06-short-"))
            os.environ["ASSET_RELEASE_TAG"] = "../evil"
            with self.assertRaises(SystemExit):
                tp.video_url(ep)
        finally:
            os.environ.pop("ASSET_RELEASE_TAG", None)
        img = self.t / "img"; img.mkdir()
        (img / "ch-eve-front.json").write_text(json.dumps({"release_asset": "eve.png"}))
        (img / "ch-adam-front.json").write_text(json.dumps({"release_asset": "adam.png", "release_tag": NEW}))
        chars = {"eve": {"refs": ["front"]}, "adam": {"refs": ["front"]}}
        self.assertEqual(ch.reference_urls(["eve", "adam"], img, chars), [f"{base}{OLD}/eve.png", f"{base}{NEW}/adam.png"])


if __name__ == "__main__":
    unittest.main()
