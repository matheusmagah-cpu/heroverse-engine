#!/usr/bin/env python3
"""lipsync_check.py: thresholds calibrated on the 2026-10-26 Keeper test (no model needed for these cases)."""
import json
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


SERIES = Path(__file__).resolve().parents[2] / "evidence/pavo/20261026/keeper-vo/opening-series.json"
FPS = 24.0


def closed(seconds, level=0.002, noise=0.0004, seed=1):
    return level + np.random.default_rng(seed).normal(0, noise, int(seconds * FPS))


def talk(seconds, amplitude=0.11):
    return np.abs(np.sin(np.linspace(0, 1.5 * np.pi * seconds, int(seconds * FPS)))) * amplitude + 0.002


class StillMouth(unittest.TestCase):
    """Plan B (owner, 2026-10-26): a voice-over Keeper clip shows no talking mouth (MOUTH_TALKING: the fastest ~1 s of
    lip motion anywhere in the clip, or the old whole-clip rule) and a mouth confirmed closed after a settle window
    (MOUTH_NOT_CLOSED: the most open ~1 s after STILL_MOUTH_SETTLE_S). Calibrated on the 42 talking and 14 closed
    clips of 26/10, whose per-frame series are kept and replayed here."""

    def test_the_thresholds_sit_between_the_closed_and_the_talking_clips(self):
        # calibration.json: window motion talking >= 0.0091, closed <= 0.0043; open after the settle talking >= 0.0389,
        # closed <= 0.0046
        self.assertTrue(0.0043 * 1.3 < lc.STILL_MOUTH_WINDOW_MOTION_MAX < 0.0091 / 1.3)
        self.assertTrue(0.0046 * 2 < lc.STILL_MOUTH_CLOSED_MAX < 0.0389 / 2)
        self.assertEqual(lc.STILL_MOUTH_SETTLE_S, 2.5)          # clip 5 settles closed within ~2.5 s
        self.assertEqual(lc.STILL_MOUTH_WINDOW_S, 1.0)

    def test_every_recorded_talking_clip_is_flagged_every_closed_clip_with_a_face_passes(self):
        data = json.loads(SERIES.read_text())
        self.assertEqual((len(data["talking"]), len(data["closed"])), (42, 14))
        for name, s in data["talking"].items():
            o = np.array([np.nan if x is None else x for x in s["opening"]])
            self.assertIn("MOUTH_TALKING", lc.still_mouth_verdict(o, s["share"], s["fps"])["flags"], name)
        passed = []
        for name, s in data["closed"].items():
            o = np.array([np.nan if x is None else x for x in s["opening"]])
            r = lc.still_mouth_verdict(o, s["share"], s["fps"])
            self.assertNotIn("MOUTH_TALKING", r["flags"], name)
            if s["share"] >= lc.FACE_FRAMES_MIN:
                self.assertEqual(r["flags"], [], (name, r))
                passed.append(name)
        # clip 5 and the 6 build probes of genesis-07's own prompts (k-insight revised, k-question, k-close)
        self.assertEqual(len(passed), 7, passed)

    def test_a_talking_mouth_is_flagged_a_closed_one_passes(self):
        r = lc.still_mouth_verdict(closed(8), 0.95, FPS)
        self.assertEqual(r["flags"], [])
        self.assertLess(r["window_motion"], lc.STILL_MOUTH_WINDOW_MOTION_MAX)
        self.assertLess(r["closed_opening"], lc.STILL_MOUTH_CLOSED_MAX)
        self.assertEqual((r["face_frames"], r["frames"]), (0.95, 192))
        self.assertIn("MOUTH_TALKING", lc.still_mouth_verdict(talk(8), 0.95, FPS)["flags"])

    def test_two_and_a_half_seconds_of_talking_inside_twelve_is_not_averaged_away(self):
        o = np.concatenate([closed(5, noise=0.0002), talk(2.5), closed(4.5, noise=0.0002, seed=2)])
        r = lc.still_mouth_verdict(o, 1.0, FPS)
        self.assertLess(r["opening_motion"], lc.STILL_MOUTH_MOTION_MAX)   # the whole-clip mean would pass it
        self.assertIn("MOUTH_TALKING", r["flags"])

    def test_an_open_still_mouth_is_not_confirmed_closed(self):
        r = lc.still_mouth_verdict(closed(8, level=0.05), 1.0, FPS)
        self.assertNotIn("MOUTH_TALKING", r["flags"])
        self.assertEqual(r["flags"], ["MOUTH_NOT_CLOSED"])
        # open for 1.5 s at the end, after it had closed: refused too
        late = np.concatenate([closed(6), closed(1.5, level=0.05)])
        self.assertEqual(lc.still_mouth_verdict(late, 1.0, FPS)["flags"], ["MOUTH_NOT_CLOSED"])

    def test_the_mouth_may_settle_closed_within_the_settle_window_not_later(self):
        # clip 5 (conversation 373100393016087168): the talking reference's open mouth closes over ~2.5 s, then stays
        settle = np.concatenate([np.linspace(0.061, 0.002, int(2.4 * FPS)), closed(5.6)])
        self.assertEqual(lc.still_mouth_verdict(settle, 1.0, FPS)["flags"], [])
        slow = np.concatenate([np.linspace(0.061, 0.002, int(5 * FPS)), closed(3)])
        self.assertIn("MOUTH_NOT_CLOSED", lc.still_mouth_verdict(slow, 1.0, FPS)["flags"])

    def test_the_face_must_be_found_in_80_percent_of_frames_as_for_the_lips(self):
        self.assertEqual(lc.still_mouth_verdict(closed(5), 0.79, FPS)["flags"], ["FACE_NOT_FOUND"])
        self.assertEqual(lc.FACE_FRAMES_MIN, 0.8)
        empty = lc.still_mouth_verdict(np.array([np.nan] * 100), 0.0, FPS)
        self.assertIn("FACE_NOT_FOUND", empty["flags"])
        self.assertIn("MOUTH_NOT_CLOSED", empty["flags"])     # nothing measured is never a confirmed closed mouth
        self.assertIn("MOUTH_UNMEASURED", empty["flags"])
        self.assertIsNone(empty["opening_range"])
        self.assertIn("NO_FRAMES", lc.still_mouth_verdict(np.array([]), 0.0, FPS)["flags"])

    def test_frames_without_a_face_are_left_out_not_counted_as_closed(self):
        o = talk(8)
        o[40:80] = np.nan                                            # the face lost for a while: still talking
        r = lc.still_mouth_verdict(o, 0.8, FPS)
        self.assertIn("MOUTH_TALKING", r["flags"])
        self.assertEqual(r["frames"], 192)

    def test_the_cli_has_a_still_mouth_mode(self):
        self.assertIn('sys.argv[1] == "--still-mouth"', Path(lc.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
