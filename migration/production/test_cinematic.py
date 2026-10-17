import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cinematic  # noqa: E402


class Parallax(unittest.TestCase):
    def setUp(self):
        h, w = int(cinematic.H * cinematic.MARGIN), int(cinematic.W * cinematic.MARGIN)
        rng = np.random.default_rng(1)
        self.img = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        self.depth = np.tile(np.linspace(0, 1, h, dtype=np.float32)[:, None], (1, w))

    def test_every_move_yields_full_frames(self):
        for move in cinematic.MOVES:
            out = list(cinematic.frames(self.img, self.depth, move, 3, cinematic.Dust()))
            self.assertEqual(len(out), 3)
            self.assertEqual(out[0].shape, (cinematic.H, cinematic.W, 3))
            self.assertEqual(out[0].dtype, np.uint8)

    def test_focus_plane_stays_and_near_plane_slides(self):
        """Truck move pivots on the median depth: rows at that depth keep still, the near edge slides."""
        img = np.tile(np.arange(self.img.shape[1], dtype=np.float32)[None, :, None] % 256, (self.img.shape[0], 1, 3)).astype(np.uint8)
        a, b = list(cinematic.frames(img, self.depth, "truck_right", 2))
        diff = np.abs(a.astype(int) - b.astype(int)).mean(axis=(1, 2))
        mid = cinematic.H // 2
        self.assertLess(diff[mid - 5:mid + 5].mean(), diff[-40:].mean())


if __name__ == "__main__":
    unittest.main()
