#!/usr/bin/env python3
"""Offline: the smoke cut keeps a real shape and the verdict only forgives the length rule."""
import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Smoke(unittest.TestCase):
    def make_work(self, directory):
        w = Path(directory)
        (w / "package").mkdir()
        for f in ("pilot.mp4", "manifest.json", "package/package.json", "package/thumbnail.jpg"):
            (w / f).write_text("x")
        (w / "package/thumbnail_check.json").write_text(json.dumps({"status": "PASS"}))
        # A real renderer report, including its complete non-length checks. The smoke cut is allowed to fail
        # only the two measured length-dependent rows; FAIL alone therefore cannot reject a valid cut.
        report = json.loads((ROOT / "production/pilot-011/out/qa.json").read_text())
        report["checks"]["duration_min"] = False
        report["checks"]["speech_presence"] = False
        report["status"] = "FAIL"
        (w / "qa.json").write_text(json.dumps(report))
        return w, report

    def test_cut_keeps_opening_one_scripture_and_the_close(self):
        script = json.loads((ROOT / "production/pilot-011/script.json").read_text())
        ids = [s["id"] for s in smoke.cut(script)["segments"]]
        self.assertEqual(ids[:2], [s["id"] for s in script["segments"][:2]])
        self.assertEqual(ids[-1], script["segments"][-1]["id"])
        self.assertEqual(len(ids), 4)
        self.assertEqual(smoke.cut(script)["footage"], script["footage"])

    def test_verdict_forgives_only_length(self):
        with tempfile.TemporaryDirectory() as d:
            w, report = self.make_work(d)
            self.assertEqual(smoke.verdict(w), [])
            report["checks"]["images_open_licence_with_revision"] = False
            (w / "qa.json").write_text(json.dumps(report))
            self.assertEqual(smoke.verdict(w), ["QA_FAIL images_open_licence_with_revision"])
            (w / "package/thumbnail.jpg").unlink()
            self.assertIn("MISSING package/thumbnail.jpg", smoke.verdict(w))

    def test_e205_missing_malformed_or_unknown_measurements_never_pass(self):
        with tempfile.TemporaryDirectory() as d:
            w, real = self.make_work(d)
            cases = [{}, {"status": "FAIL"}, [],
                     dict(real, checks={}), dict(real, checks=[]),
                     dict(real, checks={"duration_min": False}),
                     dict(real, version="unrecognized"), dict(real, status="ERROR"),
                     dict(real, status="PASS")]
            for key, value in (("video_format", "false"), ("video_format", 1),
                               ("full_decode_without_errors", None), ("duration_min", None),
                               ("speech_presence", "")):
                broken = copy.deepcopy(real)
                broken["checks"][key] = value
                cases.append(broken)
            for report in cases:
                with self.subTest(report=report):
                    (w / "qa.json").write_text(json.dumps(report))
                    self.assertTrue(smoke.verdict(w))
            (w / "qa.json").write_text("{broken")
            self.assertTrue(smoke.verdict(w))
            # The exception is for measured failures of the short cut, never absent or malformed measurements.
            (w / "qa.json").write_text(json.dumps(real))
            self.assertEqual(smoke.verdict(w), [])


if __name__ == "__main__":
    unittest.main()
