import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import av_picture_change as apc  # noqa: E402


def clip(change):
    rng = np.random.default_rng(1)
    a = rng.uniform(0, 255, (54, 96)).astype(np.float32)
    b = change(a.copy())
    return np.stack([a] * 30 + [b] * 30), 30.0


class Classify(unittest.TestCase):
    def test_band_change_is_local_with_region(self):
        def band(img):
            img[36:45, 16:80] = 255 - img[36:45, 16:80]
            return img
        frames, fps = clip(band)
        r = apc.classify_at(frames, fps, 1.0)
        self.assertEqual(r["kind"], "LOCAL")
        self.assertEqual(r["region"]["rows"], [4, 4])

    def test_full_replacement_is_scene(self):
        frames, fps = clip(lambda img: 255 - img)
        r = apc.classify_at(frames, fps, 1.0)
        self.assertEqual(r["kind"], "SCENE")
        self.assertFalse(r["centre_kept"])

    def test_background_change_keeping_centre(self):
        def bg(img):
            out = 255 - img
            out[9:45, 32:64] = img[9:45, 32:64]
            return out
        frames, fps = clip(bg)
        r = apc.classify_at(frames, fps, 1.0)
        self.assertEqual(r["kind"], "SCENE")
        self.assertTrue(r["centre_kept"])

    def test_change_too_close_to_edge(self):
        frames, fps = clip(lambda img: 255 - img)
        self.assertEqual(apc.classify_at(frames, fps, 0.1)["kind"], "EDGE")

    def test_summary_rates(self):
        changes = [{"time": 10.0, "kind": "SCENE", "changed_fraction": 0.9, "centre_kept": False},
                   {"time": 20.0, "kind": "LOCAL", "changed_fraction": 0.1, "region": {"rows": [4, 5], "cols": [2, 9]}}]
        s = apc.summarize(changes, 60.0)
        self.assertEqual((s["scene_changes_per_minute"], s["local_changes_per_minute"]), (1.0, 1.0))
        self.assertEqual(s["local_region_rows_median"], [4, 5])


if __name__ == "__main__":
    unittest.main()
