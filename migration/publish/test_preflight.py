#!/usr/bin/env python3
"""Offline checks of the pre-upload preflight."""
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight as pf  # noqa: E402

NOW = datetime(2026, 10, 18, 0, 0, tzinfo=timezone.utc)


def png(path, w, h):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", w, h) + b"\x00" * 20)


def pilot(tmp, title="Morning Prayer | God Goes Before You", tags=("morning prayer",), publish_at="2026-10-18T10:00:00Z",
          slots=("2026-10-18T14:00:00Z",)):
    d = Path(tmp)
    (d / "out").mkdir()
    (d / "out" / "package.json").write_text(json.dumps({"title": title, "description": "Pray with me.", "tags": list(tags),
                                                        "category_id": "29", "made_for_kids": False}))
    (d / "out" / "manifest.json").write_text(json.dumps({"sentences": [{"text": "Good morning.", "start": 0.1, "end": 1.2}]}))
    (d / "schedule.json").write_text(json.dumps({"publish_at": publish_at, "shorts_slots": list(slots)}))
    png(d / "thumb.png", 1280, 720)
    return d


class Preflight(unittest.TestCase):
    def test_clean(self):
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t)
            self.assertEqual(pf.check(d, d / "thumb.png", now=NOW), ([], pf.LONG_UNITS))

    def test_catches_everything_youtube_rejects(self):
        with tempfile.TemporaryDirectory() as t:
            d = pilot(t, title="x" * 101 + " <b>", tags=["a very long tag " * 4] * 10, publish_at="2026-10-17T23:00:00Z",
                      slots=("2026-10-17T22:00:00Z",))
            png(d / "thumb.png", 1280, 1280)
            (d / "shorts").mkdir()
            (d / "shorts" / "shorts.json").write_text(json.dumps({"shorts": [{"file": "short-00.mp4", "publish": True, "title": "Pray"}]}))
            problems = " ".join(pf.check(d, d / "thumb.png", now=NOW)[0])
            for code in ("TITLE_LENGTH", "TITLE_ANGLE_BRACKETS", "TAGS_CHARS", "THUMBNAIL_SIZE", "PUBLISH_AT_NOT_AHEAD", "SHORTS_SLOTS"):
                self.assertIn(code, problems)

    def test_tag_chars_counts_quotes(self):
        self.assertEqual(pf.tag_chars(["morning prayer", "faith"]), 16 + 5 + 1)


if __name__ == "__main__":
    unittest.main()
