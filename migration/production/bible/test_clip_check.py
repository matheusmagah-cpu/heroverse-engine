#!/usr/bin/env python3
"""Offline: a clip that opens on black, is low resolution or low frame rate, or carries letterbox bars inside the
frame (E109), is flagged before the compose."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_check as cc  # noqa: E402

EVIDENCE = Path(__file__).resolve().parents[2] / "evidence" / "pavo"
LAMP = EVIDENCE / "20261025" / "genesis-06" / "lamp.mp4"            # a real Pavo night shot: oil lamp in a dark tent
DARKEST = EVIDENCE / "20261026" / "keeper-vo" / "probe-k-insight-1-373107010075637504.mp4"  # mean luma 48, night


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


    def test_a_letterboxed_clip_is_refused_and_a_dark_night_clip_is_not(self):
        # E109: genesis-07 s-well (run 40357197063) was a wide picture with ~22 % black above and below inside the
        # 9:16 frame and passed. The bars are refused; a real night shot, the same shot darkened to near black, and a
        # black sky over a lit camp (one dark edge) are not.
        self.assertFalse(cc.letterboxed({"top": 0.0, "bottom": 0.044, "left": 0.0, "right": 0.0}))   # one edge only
        self.assertTrue(cc.letterboxed({"top": 0.223, "bottom": 0.223, "left": 0.0, "right": 0.0}))   # s-well's 428/1920
        self.assertTrue(cc.letterboxed({"top": 0.0, "bottom": 0.0, "left": 0.05, "right": 0.05}))     # pillarbox
        self.assertFalse(cc.letterboxed(None))                                                       # no picture at all
        with tempfile.TemporaryDirectory() as t:
            boxed, pillar, darker, sky = (str(Path(t, n)) for n in ("boxed.mp4", "pillar.mp4", "darker.mp4", "sky.mp4"))
            ff = ["ffmpeg", "-v", "error", "-y", "-i", str(LAMP), "-an", "-pix_fmt", "yuv420p", "-vf"]
            subprocess.run(ff + ["scale=720:720,pad=720:1280:0:280:black", boxed], check=True)   # s-well's shape
            subprocess.run(ff + ["scale=400:1280,pad=720:1280:160:0:black", pillar], check=True)
            subprocess.run(ff + ["eq=brightness=-0.35", darker], check=True)                   # a deep night
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=720x560:r=30:d=3",
                            "-i", str(LAMP), "-filter_complex", "[1:v]trim=0:3,setpts=PTS-STARTPTS,crop=720:720:0:560"
                            "[g];[0:v][g]vstack", "-an", "-pix_fmt", "yuv420p", sky], check=True)   # black sky, lit camp
            r = cc.check(boxed)
            self.assertIn("LETTERBOX_BARS", r["flags"])
            self.assertGreater(min(r["bars"]["top"], r["bars"]["bottom"]), 0.2)
            self.assertIn("LETTERBOX_BARS", cc.check(pillar)["flags"])
            for clean in (str(LAMP), str(DARKEST), darker, sky):
                self.assertNotIn("LETTERBOX_BARS", cc.check(clean)["flags"], clean)
            self.assertEqual(cc.check(str(LAMP))["flags"], [])
            self.assertEqual(cc.main([boxed]), 1)


if __name__ == "__main__":
    unittest.main()
