"""Generalization tests: synthetic media unlike the five controls. Offline only.

Each case encodes H.264/AAC with local ffmpeg in a temporary directory, then
measures it blind. Counts, times, levels, noise, frame/sample rates and channel
layouts differ from c01-c05; tolerances are the frozen criteria.json values.
"""
import array
import json
import math
from pathlib import Path
import random
import shutil
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

import av_event_meter as meter

CRITERIA = json.loads((Path(__file__).with_name("criteria.json")).read_text())["rules"]
AUDIO_TOL = CRITERIA["audio_onset_tolerance_seconds"]
VIDEO_TOL = CRITERIA["visual_onset_tolerance_seconds"]
OFFSET_TOL = CRITERIA["offset_tolerance_seconds"]
W, H = 320, 240


def write_video(path, fps, seconds, flashes=(), fade=False):
    """flashes: (start_seconds, frames, (x, y, w, h), level) on a gray-60 background."""
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pixel_format", "yuv420p", "-video_size", f"{W}x{H}", "-framerate", str(fps),
               "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-bf", "0", "-g", str(fps), "-pix_fmt", "yuv420p", str(path)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in range(round(fps * seconds)):
        base = 60 + (round(120 * index / (fps * seconds)) if fade else 0)
        y = bytearray([base]) * (W * H)
        for start, frames, (x, top, width, height), level in flashes:
            first = round(start * fps)
            if first <= index < first + frames:
                for row in range(top, top + height):
                    y[row * W + x:row * W + x + width] = bytes([level]) * width
        process.stdin.write(bytes(y) + bytes([128]) * (W * H // 2))
    process.stdin.close()
    stderr = process.stderr.read()
    process.stderr.close()
    if process.wait():
        raise RuntimeError(stderr.decode())


def write_audio(path, rate, channels, seconds, tones=(), noise_dbfs=None, seed=7):
    """tones: (onset, duration, hz, rms_dbfs, mode); mode in mono/right/antiphase."""
    rng = random.Random(seed)
    frames = round(rate * seconds)
    data = [[0.0] * frames for _ in range(channels)]
    if noise_dbfs is not None:
        sigma = 10 ** (noise_dbfs / 20)
        for channel in data:
            for i in range(frames):
                channel[i] = rng.gauss(0, sigma)
    ramp = round(.005 * rate)
    for onset, duration, hz, rms_dbfs, mode in tones:
        amplitude = math.sqrt(2) * 10 ** (rms_dbfs / 20)
        start, length = round(onset * rate), round(duration * rate)
        for i in range(length):
            value = amplitude * min(1.0, i / ramp, (length - 1 - i) / ramp) * math.sin(2 * math.pi * hz * i / rate)
            for c in range(channels):
                if mode == "right" and c == 0:
                    continue
                data[c][start + i] += -value if mode == "antiphase" and c == 1 else value
    pcm = array.array("h", (max(-32768, min(32767, round(data[c][i] * 32767)))
                            for i in range(frames) for c in range(channels)))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())


def mux(out, video=None, audio=None):
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for source in (video, audio):
        if source:
            args += ["-i", str(source)]
    if video:
        args += ["-map", "0:v:0", "-c:v", "copy"]
    if audio:
        args += ["-map", f"{1 if video else 0}:a:0", "-c:a", "aac", "-b:a", "160k"]
    subprocess.run(args + [str(out)], check=True, capture_output=True)


class GeneralizationTests(unittest.TestCase):
    def setUp(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Meter test attempted network access")
        for guard in (patch.object(socket, "socket", forbidden),
                      patch.object(socket, "create_connection", forbidden)):
            guard.start()
            self.addCleanup(guard.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="av_meter_test_"))
        self.addCleanup(shutil.rmtree, self.tmp)

    def build(self, name, fps=None, rate=None, channels=1, seconds=6, flashes=(),
              tones=(), noise_dbfs=None, fade=False):
        video = audio = None
        if fps:
            video = self.tmp / f"{name}.v.mp4"
            write_video(video, fps, seconds, flashes, fade)
        if rate:
            audio = self.tmp / f"{name}.wav"
            write_audio(audio, rate, channels, seconds, tones, noise_dbfs)
        out = self.tmp / f"{name}.mp4"
        mux(out, video, audio)
        return meter.measure(out)

    def assert_onsets(self, events, expected, tolerance):
        observed = [event["onset_seconds"] for event in events]
        self.assertEqual(len(observed), len(expected), observed)
        for got, want in zip(observed, expected):
            self.assertLessEqual(abs(got - want), tolerance, (observed, expected))

    def test_irregular_counts_levels_noise_and_frame_rate(self):
        for count, fps, rate, offset in ((1, 25, 44100, 0.08), (4, 25, 48000, -0.12),
                                         (7, 30, 44100, 0.3), (0, 30, 48000, 0)):
            with self.subTest(count=count, fps=fps, rate=rate, offset=offset):
                starts = [0.6 + 1.13 * k for k in range(count)]
                # Flash starts on frame boundaries; positions and levels vary.
                starts = [round(s * fps) / fps for s in starts]
                flashes = [(s, 2 + k % 3, (20 + 30 * k, 20 + 15 * k, 60, 60), 220 if k % 2 else 10)
                           for k, s in enumerate(starts)]
                tones = [(s + offset, .06 + .03 * k, 500 + 300 * k, -6 - 3 * k, "mono")
                         for k, s in enumerate(starts)]
                result = self.build(f"irregular{count}", fps=fps, rate=rate, seconds=9,
                                    flashes=flashes, tones=tones, noise_dbfs=-50)
                self.assert_onsets(result["video"]["events"], starts, VIDEO_TOL)
                self.assert_onsets(result["audio"]["events"], [s + offset for s in starts], AUDIO_TOL)
                self.assertFalse(result["audio"]["exact_digital_silence"])
                if count:
                    self.assertLessEqual(abs(result["sync"]["median_offset_seconds"] - offset), OFFSET_TOL)
                    in_sync = -0.045 <= offset <= 0.125  # frozen ITU-R BT.1359 window
                    self.assertEqual(result["sync"]["verdict"], "IN_SYNC" if in_sync else "OUT_OF_SYNC")
                else:
                    self.assertEqual(result["sync"]["verdict"], "NOT_MEASURABLE")

    def test_stereo_right_only_and_antiphase_are_not_lost(self):
        tones = [(1.0, .1, 800, -12, "right"), (2.5, .1, 800, -12, "antiphase")]
        result = self.build("stereo", rate=48000, channels=2, seconds=4, tones=tones)
        self.assertFalse(result["video"]["present"])
        self.assert_onsets(result["audio"]["events"], [1.0, 2.5], AUDIO_TOL)
        self.assertEqual(result["sync"]["verdict"], "NOT_MEASURABLE")

    def test_close_events_stay_separate(self):
        tones = [(1.0, .05, 1000, -10, "mono"), (1.11, .05, 1000, -10, "mono")]
        flashes = [(1.0, 2, (100, 80, 80, 80), 235), (1.4, 2, (100, 80, 80, 80), 235)]
        result = self.build("close", fps=30, rate=48000, seconds=3, flashes=flashes, tones=tones)
        self.assert_onsets(result["audio"]["events"], [1.0, 1.11], AUDIO_TOL)
        self.assert_onsets(result["video"]["events"], [1.0, 1.4], VIDEO_TOL)

    def test_gradual_fade_and_steady_noise_are_not_events(self):
        result = self.build("fade", fps=30, rate=48000, seconds=4, fade=True, noise_dbfs=-30)
        self.assertEqual(result["video"]["onset_count"], 0)
        self.assertEqual(result["audio"]["onset_count"], 0)
        self.assertFalse(result["audio"]["exact_digital_silence"])

    def test_documented_limit_event_below_20db_snr_is_not_counted(self):
        tones = [(1.0, .1, 1000, -40, "mono"), (2.0, .1, 1000, -10, "mono")]
        result = self.build("snr", rate=48000, seconds=3, tones=tones, noise_dbfs=-50)
        self.assert_onsets(result["audio"]["events"], [2.0], AUDIO_TOL)

    def test_video_only_file(self):
        flashes = [(0.5, 3, (0, 0, 320, 240), 200)]
        result = self.build("videoonly", fps=24, seconds=2, flashes=flashes)
        self.assertFalse(result["audio"]["present"])
        self.assert_onsets(result["video"]["events"], [0.5], VIDEO_TOL)
        self.assertEqual(result["video"]["events"][0]["direction"], "brighter")


if __name__ == "__main__":
    unittest.main()
