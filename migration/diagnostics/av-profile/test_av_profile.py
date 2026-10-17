"""Known-truth tests for av_profile: tempo, cut rate, cut-on-onset, loudness, colour."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "av-event-meter"))
import test_av_event_meter as synth  # noqa: E402
import av_profile  # noqa: E402


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="av_profile_test_"))
        self.addCleanup(shutil.rmtree, self.tmp)

    def clip(self, name, bpm, seconds, cut_every_beats, cut_shift=0.0, level=-12):
        beat = 60 / bpm
        beats = [0.5 + k * beat for k in range(int((seconds - 1) / beat))]
        tones = [(t, .03, 1800, level, "mono") for t in beats]
        cuts = [round((t + cut_shift) * 30) / 30 for t in beats[::cut_every_beats]]
        flashes = [(t, 2, (0, 0, 320, 240), 230) for t in cuts if t < seconds - .2]
        video, audio, out = self.tmp / f"{name}.v.mp4", self.tmp / f"{name}.wav", self.tmp / f"{name}.mp4"
        synth.write_video(video, 30, seconds, flashes)
        synth.write_audio(audio, 48000, 1, seconds, tones)
        synth.mux(out, video, audio)
        return av_profile.profile(out), len(flashes)

    def test_tempo_cut_rate_and_cuts_on_beat(self):
        for bpm in (90, 120, 140):
            with self.subTest(bpm=bpm):
                result, flashes = self.clip(f"bpm{bpm}", bpm, 20, 2)
                self.assertLessEqual(abs(result["rhythm"]["tempo"]["bpm"] - bpm), 1.5, result["rhythm"])
                self.assertEqual(result["editing"]["picture_changes"], flashes)
                relation = result["image_sound"]["cut_on_audio_onset"]
                self.assertEqual(relation["fraction"], 1.0)
                self.assertGreater(relation["lift"], 3)

    def test_cuts_off_beat_are_not_on_onset(self):
        result, _ = self.clip("offbeat", 120, 16, 2, cut_shift=0.25)
        self.assertEqual(result["image_sound"]["cut_on_audio_onset"]["fraction"], 0.0)

    def test_loudness_tracks_level_difference(self):
        quiet, _ = self.clip("quiet", 120, 8, 4, level=-24)
        loud, _ = self.clip("loud", 120, 8, 4, level=-18)
        delta = loud["loudness"]["integrated_lufs"] - quiet["loudness"]["integrated_lufs"]
        self.assertLessEqual(abs(delta - 6), 0.5, (quiet["loudness"], loud["loudness"]))
        self.assertLess(loud["loudness"]["true_peak_dbtp"], 0)

    def test_colour_saturation(self):
        out = self.tmp / "red.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x240:r=30",
                        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
        grey = self.tmp / "grey.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=30",
                        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(grey)], check=True)
        self.assertGreater(av_profile.profile(out)["colour"]["mean_saturation"], 0.8)
        self.assertLess(av_profile.profile(grey)["colour"]["mean_saturation"], 0.05)


if __name__ == "__main__":
    unittest.main()
