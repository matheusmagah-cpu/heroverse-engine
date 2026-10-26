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


class GodShotFaces(unittest.TestCase):
    """God's voice-over shot shows no person: one face in any sampled frame flags the clip (calibration 2026-10-26:
    the Genesis 6 storm, sunbeams and tents clips 0 faces; the Keeper's clip 30/44)."""
    def test_any_face_flags_the_clip_and_an_empty_clip_is_not_a_pass(self):
        self.assertEqual(lc.face_verdict("storm.mp4", 40, 0, [])["flags"], [])
        r = lc.face_verdict("keeper.mp4", 44, 1, [12])
        self.assertEqual(r["flags"], ["GOD_SHOT_FACE"])
        self.assertEqual(r["face_frames"], [12])
        self.assertIn("NO_FRAMES", lc.face_verdict("empty.mp4", 0, 0, [])["flags"])

    def test_the_cli_has_a_faces_mode(self):
        text = Path(lc.__file__).read_text()
        self.assertIn('sys.argv[1] == "--faces"', text)
        self.assertGreaterEqual(lc.FACE_SAMPLE_EVERY, 1)


class StillMouth(unittest.TestCase):
    """Plan B (owner, 2026-10-26): a voice-over Keeper clip shows no talking mouth. The inner-lip opening over the
    face height varies over a talking clip (p95 - p5: the 34 Keeper talking clips of 26/10 0.087-0.118, the genesis-06
    narrator 0.056) and stays put with the lips closed (the direct closed-mouth Keeper clips 0.004-0.007)."""

    def test_the_threshold_sits_between_the_closed_and_the_talking_clips(self):
        self.assertGreater(lc.STILL_MOUTH_RANGE_MAX, 0.007 * 2)
        self.assertLess(lc.STILL_MOUTH_RANGE_MAX, 0.056 / 2)

    def test_a_talking_mouth_is_flagged_a_closed_one_passes(self):
        talking = np.abs(np.sin(np.linspace(0, 30, 200))) * 0.11     # opens and closes like the Keeper's lips
        closed = 0.003 + np.random.default_rng(1).normal(0, 0.0008, 200)
        self.assertEqual(lc.still_mouth_verdict(closed, 0.95)["flags"], [])
        self.assertEqual(lc.still_mouth_verdict(talking, 0.95)["flags"], ["MOUTH_TALKING"])
        r = lc.still_mouth_verdict(closed, 0.95)
        self.assertLess(r["opening_range"], lc.STILL_MOUTH_RANGE_MAX)
        self.assertEqual((r["face_frames"], r["frames"]), (0.95, 200))

    def test_the_face_must_be_found_in_80_percent_of_frames_as_for_the_lips(self):
        closed = np.full(100, 0.003)
        self.assertEqual(lc.still_mouth_verdict(closed, 0.79)["flags"], ["FACE_NOT_FOUND"])
        self.assertEqual(lc.FACE_FRAMES_MIN, 0.8)
        empty = lc.still_mouth_verdict(np.array([np.nan] * 10), 0.0)
        self.assertIn("FACE_NOT_FOUND", empty["flags"])
        self.assertIsNone(empty["opening_range"])
        self.assertIn("NO_FRAMES", lc.still_mouth_verdict(np.array([]), 0.0)["flags"])

    def test_nan_frames_are_left_out_not_counted_as_closed(self):
        o = np.full(100, 0.003)
        o[::2] = np.nan
        o[1::4] = 0.12                                                # a talking mouth among missing frames
        self.assertIn("MOUTH_TALKING", lc.still_mouth_verdict(o, 0.5)["flags"])

    def test_the_cli_has_a_still_mouth_mode(self):
        self.assertIn('sys.argv[1] == "--still-mouth"', Path(lc.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
