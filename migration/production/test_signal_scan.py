#!/usr/bin/env python3
"""Synthetic files with known defects: the whole-file scan finds a 1 s black gap and a 4 s silence that a
0.5 frames/s sample could miss, and passes a clean file (ffmpeg lavfi sources, nothing downloaded)."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signal_scan as ss  # noqa: E402


def make(path, black=None, mute=None, d=14):
    v = "[0:v]null[v]" if black is None else f"[0:v]drawbox=enable='between(t,{black[0]},{black[1]})':c=black:t=fill[v]"
    a = "[1:a]anull[a]" if mute is None else f"[1:a]volume=enable='between(t,{mute[0]},{mute[1]})':volume=0[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x240:d={d}", "-f", "lavfi",
                    "-i", f"sine=f=220:d={d}", "-filter_complex", f"{v};{a}", "-map", "[v]", "-map", "[a]",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


class Scan(unittest.TestCase):
    def test_clean_passes(self):
        with tempfile.TemporaryDirectory() as t:
            make(Path(t) / "ok.mp4")
            self.assertEqual(ss.scan(str(Path(t) / "ok.mp4"))["status"], "PASS")

    def test_short_black_gap_fails(self):
        with tempfile.TemporaryDirectory() as t:
            make(Path(t) / "b.mp4", black=(5, 6))
            r = ss.scan(str(Path(t) / "b.mp4"))
            self.assertEqual(r["status"], "FAIL")
            self.assertGreaterEqual(r["rows"]["black_picture"]["longest_s"], 0.9)

    def test_silence_fails_and_edges_are_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            make(Path(t) / "s.mp4", mute=(5, 9))
            self.assertEqual(ss.scan(str(Path(t) / "s.mp4"))["status"], "FAIL")
            make(Path(t) / "e.mp4", black=(0, 1.5), mute=(0, 1.5))  # intended fade-in region
            self.assertEqual(ss.scan(str(Path(t) / "e.mp4"))["status"], "PASS")

    def test_unreadable_file_is_error_not_pass(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "r.json"
            self.assertEqual(ss.main(str(Path(t) / "missing.mp4"), str(out)), 1)
            self.assertIn('"ERROR"', out.read_text())


if __name__ == "__main__":
    unittest.main()
