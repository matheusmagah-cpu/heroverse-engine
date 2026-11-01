#!/usr/bin/env python3
"""E244: the Buzzy clip ingest decides the asset name and sha256 from the committed ledger only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import buzzy_ingest as bi  # noqa: E402

URL = "https://res-prod.buzzy.now/file-service/0fcabdc3-03c2-32ed-ba80-506e0d58c019.mp4"
SHA = "a" * 64


class Ingest(unittest.TestCase):
    def ledger(self, **over):
        d = tempfile.mkdtemp()
        call = dict({"task_id": "gt_1", "episode_shot": "ep-short s-a", "output_sha256": SHA}, **over)
        path = Path(d, "ledger.json")
        path.write_text(json.dumps({"calls": [call]}))
        return path

    def test_name_and_sha_come_from_the_ledger_for_that_shot(self):
        self.assertEqual(bi.asset("ep-short", "s-a", "gt_1", URL, self.ledger()),
                         (f"shot-ep-short-s-a-sha256-{SHA}.mp4", SHA))

    def test_refused_url_shot_or_incomplete_ledger(self):
        for url in ("http://res-prod.buzzy.now/file-service/0fcabdc3-03c2-32ed-ba80-506e0d58c019.mp4",
                    "https://example.com/x.mp4", URL + "?x=1"):
            with self.assertRaisesRegex(SystemExit, "BUZZY_URL_REFUSED"):
                bi.asset("ep-short", "s-a", "gt_1", url, self.ledger())
        with self.assertRaisesRegex(SystemExit, "BUZZY_NOT_FOR_SHOT"):
            bi.asset("ep-short", "s-b", "gt_1", URL, self.ledger())
        with self.assertRaisesRegex(SystemExit, "BUZZY_NOT_FOR_SHOT"):
            bi.asset("ep-short", "s-a", "gt_other", URL, self.ledger())
        with self.assertRaisesRegex(SystemExit, "BUZZY_LEDGER_INCOMPLETE"):
            bi.asset("ep-short", "s-a", "gt_1", URL, self.ledger(output_sha256="nothex"))

    def test_the_workflow_mirrors_only_through_the_sha_checked_script(self):
        text = (HERE.parents[2] / ".github/workflows/buzzy-ingest.yml").read_text()
        self.assertIn('pinned_asset.sh mirror "$name" "$sha" "$CLIP_URL"', text)
        self.assertIn("buzzy_ingest.py asset", text)


if __name__ == "__main__":
    unittest.main()
