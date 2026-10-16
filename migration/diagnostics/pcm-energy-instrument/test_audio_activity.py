"""Self-contained synthetic PCM16 qualification. No files, models or media I/O."""
from decimal import localcontext
import hashlib
import json
import socket
import struct
import subprocess
import unittest
from unittest.mock import patch

from audio_activity import VERSION, measure_pcm16_activity


def pcm(frames):
    channels = len(frames[0])
    return b"".join(struct.pack("<" + "h" * channels, *frame) for frame in frames)


def measure(frames, *, sample_rate=8000, window_frames=8, rms_threshold="0.02"):
    return measure_pcm16_activity(pcm(frames), channels=len(frames[0]), sample_rate=sample_rate,
                                  window_frames=window_frames, rms_threshold=rms_threshold)


class PCM16EnergyTests(unittest.TestCase):
    def setUp(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Synthetic energy test attempted an external effect")
        for guard in (patch.object(socket, "socket", forbidden),
                      patch.object(socket, "create_connection", forbidden),
                      patch.object(subprocess, "Popen", forbidden)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_zero_one_four_independent_pulses(self):
        for intervals in ([], [[8, 16]], [[0, 8], [24, 40], [56, 64], [80, 96]]):
            with self.subTest(intervals=intervals):
                frames = [(8192 if any(a <= i < b for a, b in intervals) else 0,) for i in range(112)]
                result = measure(frames)["any_channel"]
                self.assertEqual(result["active_intervals_frames"], intervals)
                self.assertEqual(result["active_interval_count"], len(intervals))
                self.assertEqual(result["active_frames"], sum(b - a for a, b in intervals))

    def test_stereo_antiphase_does_not_cancel(self):
        result = measure([(8192, -8192)] * 8 + [(0, 0)] * 8)
        for channel in result["per_channel"]:
            self.assertEqual(channel["active_intervals_frames"], [[0, 8]])
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[0, 8]])

    def test_channel_intervals_and_any_channel_union_remain_distinct(self):
        result = measure([(8192, 0)] * 8 + [(0, 8192)] * 8 + [(0, 0)] * 8)
        self.assertEqual(result["per_channel"][0]["active_intervals_frames"], [[0, 8]])
        self.assertEqual(result["per_channel"][1]["active_intervals_frames"], [[8, 16]])
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[0, 16]])

    def test_nonzero_below_threshold_does_not_claim_silence(self):
        frames = [(1,)] * 8
        self.assertTrue(any(pcm(frames)))
        result = measure(frames)
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [])
        for absent in ("digital_silence", "speech_absence", "quality_approved", "production_authorized"):
            self.assertNotIn(absent, result)

    def test_exact_threshold_equality_and_signed_full_scale(self):
        result = measure([(16383,)] * 8 + [(16384,)] * 8 + [(-16384,)] * 8, rms_threshold="0.5")
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[8, 24]])
        result = measure([(32767,)] * 8 + [(-32768,)] * 8, rms_threshold="1")
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[8, 16]])

    def test_partial_final_window_has_no_silent_padding(self):
        result = measure([(0,)] * 8 + [(6554,)] * 2, sample_rate=1000, rms_threshold="0.15")
        self.assertEqual(result["frames"], 10)
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[8, 10]])
        self.assertEqual(result["any_channel"]["active_frames"], 2)

    def test_sample_rate_preserved_and_frames_not_assumed_milliseconds(self):
        result = measure([(8192,)] * 44 + [(0,)] * 397, sample_rate=44100, window_frames=44)
        self.assertEqual(result["sample_rate_hz"], 44100)
        self.assertEqual(result["frames"], 441)
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[0, 44]])
        self.assertEqual(result["parameters"]["time_basis"],
                         "HALF_OPEN_PCM_FRAME_INDICES_FROM_ARTIFACT_START")

    def test_repeat_is_deterministic_and_parameters_are_explicit(self):
        frames = [(8192,)] * 16
        first = measure(frames)
        second = measure(frames, rms_threshold="0.0200")
        self.assertEqual(first, second)
        serialize = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(serialize(first)).hexdigest(),
                         hashlib.sha256(serialize(second)).hexdigest())
        self.assertEqual(first["version"], VERSION)
        self.assertEqual(first["parameters"]["rms_threshold_full_scale"], "0.02")
        self.assertEqual(first["parameters"]["window_frames"], 8)
        self.assertEqual(first["parameters"]["hop_frames"], 8)
        self.assertEqual(first["parameters"]["sample_scale"], 32768)
        self.assertNotEqual(first, measure(frames, window_frames=4))
        self.assertNotEqual(first, measure(frames, rms_threshold="0.03"))

    def test_decimal_context_does_not_change_threshold_or_result(self):
        frames = [(8192,)] * 8
        first = measure(frames, rms_threshold="0.123456789012345678")
        with localcontext() as context:
            context.prec = 2
            second = measure(frames, rms_threshold="0.123456789012345678")
        self.assertEqual(first, second)

    def test_invalid_window_and_threshold_fail_closed(self):
        raw = b"\0\0" * 8
        cases = ({"window_frames": 0}, {"window_frames": -1}, {"window_frames": True},
                 {"window_frames": 1.5}, {"rms_threshold": "0"}, {"rms_threshold": "-0.01"},
                 {"rms_threshold": "1.1"}, {"rms_threshold": "NaN"}, {"rms_threshold": "Infinity"},
                 {"rms_threshold": "broken"}, {"rms_threshold": "1e-100000"}, {"rms_threshold": .02})
        for params in cases:
            with self.subTest(params=params), self.assertRaises(ValueError):
                measure_pcm16_activity(raw, channels=1, sample_rate=8000, **params)

    def test_empty_incomplete_pcm_and_invalid_channel_rate_fail_closed(self):
        raw = b"\0\0" * 8
        cases = ((b"", 1, 8000), (b"\0", 1, 8000), (b"\0\0", 2, 8000),
                 (raw, True, 8000), (raw, 3, 8000), (raw, 1, 0),
                 (raw, 1, True), (raw, 1, 8000.0), (bytearray(raw), 1, 8000))
        for data, channels, rate in cases:
            with self.subTest(channels=channels, rate=rate), self.assertRaises(ValueError):
                measure_pcm16_activity(data, channels=channels, sample_rate=rate)

    def test_multiple_impulses_in_one_window_are_not_perceptual_event_count(self):
        # Two nonzero impulses become one active energy window by definition.
        result = measure([(16384,), (0,), (0,), (16384,), (0,), (0,), (0,), (0,)])
        self.assertEqual(result["any_channel"]["active_intervals_frames"], [[0, 8]])
        self.assertEqual(result["any_channel"]["active_interval_count"], 1)
        self.assertNotIn("perceptual_event_count", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
