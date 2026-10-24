#!/usr/bin/env python3
"""Offline: an episode is refused unless the file matches its hash and the KJV and AI disclosures are stated."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_episode as pe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class Episode(unittest.TestCase):
    def test_every_episode_record_is_publishable_metadata(self):
        for f in sorted((ROOT / "production/bible/episodes").glob("*.json")):
            ep = json.loads(f.read_text())
            self.assertLessEqual(len(ep["title"]), pe.TITLE_MAX, f.name)
            self.assertIn("(public domain)", ep["description"], f.name)
            self.assertIn("AI", ep["description"], f.name)
            self.assertRegex(ep["output_sha256"], r"^[0-9a-f]{64}$")

    def test_hash_mismatch_and_missing_disclosure_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d, "v.mp4")
            v.write_bytes(b"video")
            ep = {"output_sha256": pe.sha256_file(v), "title": "T", "description": "KJV (public domain). AI voice."}
            self.assertEqual(pe.problems(ep, v), [])
            self.assertIn("OUTPUT_SHA256_MISMATCH", pe.problems(dict(ep, output_sha256="0" * 64), v))
            self.assertIn("DISCLOSURE_MISSING", pe.problems(dict(ep, description="no source"), v))


if __name__ == "__main__":
    unittest.main()
