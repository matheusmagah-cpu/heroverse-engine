#!/usr/bin/env python3
"""Offline checks of the nightly queue (images, then renders)."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_queue as rq  # noqa: E402

NOW = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)


def pilot(root, name, publish_at, images_done=True, rendered=False):
    d = Path(root) / name
    (d / "images").mkdir(parents=True)
    script = {"backgrounds": ["bg-a", "bg-b"], "figure": "figure-a", "overlay": {"title_image": "bg-a"}}
    (d / "script.json").write_text(json.dumps(script))
    (d / "schedule.json").write_text(json.dumps({"publish_at": publish_at}))
    (d / "images.json").write_text(json.dumps({"images": [{"id": "bg-b"}]}))
    for i in (("figure-a", "bg-a", "bg-b") if images_done else ("figure-a", "bg-a")):
        (d / "images" / f"{i}.json").write_text("{}")
    if rendered:
        (d / "out").mkdir()
        sha = hashlib.sha256((d / "script.json").read_bytes()).hexdigest()
        (d / "out" / "manifest.json").write_text(json.dumps({"script_sha256": sha, "output_sha256": "x"}))


class Queue(unittest.TestCase):
    def test_images_then_render_by_publish_time(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-003", "2026-10-19T10:00:00Z", images_done=False)
            pilot(t, "pilot-004", "2026-10-19T23:00:00Z")
            pilot(t, "pilot-009", "2026-10-25T10:00:00Z")  # outside the horizon
            rows = rq.due(t, {}, NOW, 48)
            self.assertEqual([r["pilot"] for r in rows], ["pilot-003", "pilot-004"])
            self.assertEqual(rows[0]["missing_images"], ["bg-b"])
            nxt = next(r for r in rows if not r["missing_images"] and not r["rendered"])
            self.assertEqual(nxt["pilot"], "pilot-004")

    def test_rendered_or_published_is_not_queued(self):
        with tempfile.TemporaryDirectory() as t:
            pilot(t, "pilot-003", "2026-10-19T10:00:00Z", rendered=True)
            self.assertTrue(rq.due(t, {}, NOW, 48)[0]["rendered"])
            self.assertEqual(rq.due(t, {"entries": {"pilot-003:x": {"video_id": "v"}}}, NOW, 48), [])


if __name__ == "__main__":
    unittest.main()
