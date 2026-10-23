#!/usr/bin/env python3
"""Offline: thumbnail measures and the within channel-month test behave."""
from pathlib import Path
import sys
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thumb_study as ts  # noqa: E402


class ThumbStudy(unittest.TestCase):
    def test_letterbox_is_cropped_to_16_9(self):
        self.assertEqual(ts.crop_letterbox(Image.new("RGB", (480, 360))).size, (480, 270))

    def test_measures_tell_dark_from_bright_and_warm(self):
        dark, warm = ts.measure(Image.new("RGB", (480, 270), (10, 10, 30))), ts.measure(Image.new("RGB", (480, 270), (250, 160, 40)))
        self.assertLess(dark["brightness"], 0.1)
        self.assertGreater(warm["brightness"], 0.5)
        self.assertGreater(warm["warm_share"], 0.9)
        self.assertGreater(dark["dark_share"], 0.9)

    def test_feature_that_marks_every_hit_has_a_high_odds_ratio(self):
        rows, metrics = [], {}
        for ch in ("a", "b", "c", "d"):
            for i in range(6):
                hit = i < 2
                rows.append({"id": f"{ch}{i}", "ch": ch, "pub": "2026-09-01", "ratio": 5.0 if hit else 0.3})
                metrics[f"{ch}{i}"] = {"brightness": 0.6 if hit else 0.2, "contrast": 0, "saturation": 0, "colourfulness": 0,
                                       "edge_density": 0, "warm_share": 0, "blue_share": 0, "yellow_text_like": 0}
        res = {f["feature"]: f for f in ts.mh_perm(rows, metrics, n=200)["features"]}
        bright = res["bright (mean luminance > 0.45)"]
        self.assertIsNone(bright["or_hit"])   # infinite: no bright video failed
        self.assertLess(bright["p_hit"], 0.05)


if __name__ == "__main__":
    unittest.main()
