#!/usr/bin/env python3
"""Offline: a clip that opens on black, or is low resolution or low frame rate, is flagged before the compose."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_check as cc  # noqa: E402


def clip(path, fade_in=False, size="1080x1920", fps=30):
    vf = "fade=t=in:st=0:d=1" if fade_in else "null"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x3a7a3a:s={size}:r={fps}:d=3",
                    "-vf", vf, "-pix_fmt", "yuvj420p", path], check=True)


class ClipCheck(unittest.TestCase):
    def test_pure_rules(self):
        ok = {"width": 1080, "height": 1920, "fps": 30}
        self.assertEqual(cc.flags(ok, [90, 92], [91]), [])
        self.assertEqual(cc.flags(ok, [2.6, 20, 43], [91]), ["BLACK_START"])  # the Genesis 4 forest clip at 8.4 s
        self.assertEqual(cc.flags(dict(ok, width=360, height=640, fps=16), [90], [90]), ["LOW_RES", "LOW_FPS"])

    def test_real_files(self):
        with tempfile.TemporaryDirectory() as t:
            good, dark = str(Path(t, "good.mp4")), str(Path(t, "dark.mp4"))
            clip(good)
            clip(dark, fade_in=True)
            self.assertEqual(cc.check(good)["flags"], [])
            self.assertEqual(cc.check(dark)["flags"], ["BLACK_START"])
            self.assertEqual(cc.main([good, dark]), 1)

    def test_composed_black_only_at_intended_dips(self):
        self.assertEqual(cc.unexpected([8.43, 32.43, 46.5], [32.4], end=46.6), [8.43])  # Genesis 4's faded cut at 8.4 s
        with tempfile.TemporaryDirectory() as t:
            a, b, out = (str(Path(t, n)) for n in ("a.mp4", "b.mp4", "out.mp4"))
            clip(a)
            clip(b, fade_in=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a, "-i", b, "-filter_complex", "concat=n=2:v=1:a=0",
                            out], check=True)
            self.assertEqual(cc.main(["--composed", out]), 1)          # a fade from black between scenes is a flash
            self.assertEqual(cc.main(["--composed", out, "3.0"]), 0)   # unless it is an intended dip_to_black


if __name__ == "__main__":
    unittest.main()
