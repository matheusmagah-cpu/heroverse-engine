#!/usr/bin/env python3
"""Offline: R16 thumbnail style (breakout layout, warmest still) and its ruler."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import thumb_check  # noqa: E402

spec = importlib.util.spec_from_file_location("package_pilot", HERE / "package_pilot.py")
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


class ThumbCheck(unittest.TestCase):
    def test_ruler(self):
        self.assertEqual(thumb_check.verdict({"saturation": 0.6, "blue_share": 0.1}), [])
        self.assertIn("THUMB_NOT_SATURATED", " ".join(thumb_check.verdict({"saturation": 0.3, "blue_share": 0.1})))
        self.assertIn("THUMB_BLUE_DOMINANT", " ".join(thumb_check.verdict({"saturation": 0.6, "blue_share": 0.7})))

    def test_breakout_layout_spans_the_frame_and_fits(self):
        rows = pkg.thumbnail_lines({"lines": ["LAY DOWN", "YOUR CARES"], "sub": "Night Prayer"})
        self.assertEqual(rows[0][0], "NIGHT PRAYER")                   # the search phrase on top
        for text, size, _, y in rows:
            self.assertLessEqual(size * pkg.THUMB_CHAR_EM * len(text), pkg.THUMB_WIDTH)
        text_height = sum(int(size * 1.05) for _, size, _, _ in rows)
        self.assertGreater(text_height, 0.5 * 720)                     # the text fills at least half the frame
        self.assertLessEqual(rows[-1][3] + rows[-1][1], 720)

    def test_warmest_still_and_the_ruler_on_a_real_render(self):
        with tempfile.TemporaryDirectory() as d:
            blue, gold = Path(d, "001.png"), Path(d, "002.png")
            for f, colour in ((blue, "0x1a3a8a"), (gold, "0xd9902b")):
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=640x360",
                                "-frames:v", "1", str(f)], check=True)
            self.assertEqual(pkg.warmest([blue, gold]), gold)
            thumb = Path(d, "t.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(gold), "-frames:v", "1", "-vf",
                            pkg.thumbnail_filter({"lines": ["WAIT ON", "THE LORD"], "sub": "Morning Prayer"}), str(thumb)],
                           check=True)
            self.assertEqual(thumb_check.main(thumb, Path(d, "c.json")), 0)


if __name__ == "__main__":
    unittest.main()
