#!/usr/bin/env python3
"""Offline: the smoke cut keeps a real shape and the verdict only forgives the length rule."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Smoke(unittest.TestCase):
    def test_cut_keeps_opening_one_scripture_and_the_close(self):
        script = json.loads((ROOT / "production/pilot-011/script.json").read_text())
        ids = [s["id"] for s in smoke.cut(script)["segments"]]
        self.assertEqual(ids[:2], [s["id"] for s in script["segments"][:2]])
        self.assertEqual(ids[-1], script["segments"][-1]["id"])
        self.assertEqual(len(ids), 4)
        self.assertEqual(smoke.cut(script)["footage"], script["footage"])

    def test_verdict_forgives_only_length(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d)
            (w / "package").mkdir()
            for f in ("pilot.mp4", "manifest.json", "package/package.json", "package/thumbnail.jpg"):
                (w / f).write_text("x")
            (w / "package/thumbnail_check.json").write_text(json.dumps({"status": "PASS"}))
            (w / "qa.json").write_text(json.dumps({"checks": {"duration_min": False, "frame": True}}))
            self.assertEqual(smoke.verdict(w), [])
            (w / "qa.json").write_text(json.dumps({"checks": {"duration_min": False,
                                                              "images_open_licence_with_revision": False}}))
            self.assertEqual(smoke.verdict(w), ["QA_FAIL images_open_licence_with_revision"])
            (w / "package/thumbnail.jpg").unlink()
            self.assertIn("MISSING package/thumbnail.jpg", smoke.verdict(w))


if __name__ == "__main__":
    unittest.main()
