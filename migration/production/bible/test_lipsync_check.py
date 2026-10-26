#!/usr/bin/env python3
"""lipsync_check.py: thresholds calibrated on the 2026-10-26 Keeper test (no model needed for these cases)."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lipsync_check as lc


class Measures(unittest.TestCase):
    def test_best_lag_finds_the_shift(self):
        a = np.sin(np.linspace(0, 20, 200)) + np.linspace(0, 1, 200)
        b = np.roll(a, 3)
        corr, lag = lc.best_lag(a, b, 6)
        self.assertGreater(corr, 0.95)
        self.assertEqual(lag, -3)

    def test_envelope_hops(self):
        self.assertEqual(len(lc.envelope(np.ones(16000, dtype=np.float32), 16000)), 25)


class Verdict(unittest.TestCase):
    GOOD_AUDIO = {"corr": 0.886, "lag_ms": 0}
    GOOD_MOUTH = {"corr": 0.521, "lag_ms": 0, "speak_to_pause": 1.98, "face_frames": 0.9}

    def test_calibration_clip_passes(self):
        self.assertEqual(lc.verdict(self.GOOD_AUDIO, self.GOOD_MOUTH), [])

    def test_pavo_own_voice_fails(self):
        # the clip with Pavo's own voice: not our line, lips 208 ms late
        flags = lc.verdict({"corr": 0.113, "lag_ms": 40},
                           {"corr": 0.516, "lag_ms": 208, "speak_to_pause": 2.23, "face_frames": 0.99})
        self.assertEqual(flags, ["AUDIO_NOT_OUR_LINE", "MOUTH_NOT_IN_SYNC"])

    def test_each_rule(self):
        self.assertIn("AUDIO_OFFSET", lc.verdict({"corr": 0.9, "lag_ms": 120}, self.GOOD_MOUTH))
        self.assertIn("FACE_NOT_FOUND", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, face_frames=0.5)))
        self.assertIn("MOUTH_OPEN_IN_PAUSES", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, speak_to_pause=1.1)))
        self.assertIn("MOUTH_NOT_IN_SYNC", lc.verdict(self.GOOD_AUDIO, dict(self.GOOD_MOUTH, corr=0.3)))


if __name__ == "__main__":
    unittest.main()
