#!/usr/bin/env python3
"""Regression tests of the mining-accuracy comparator (2026-10-18 audit defects)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accuracy_check as ac  # noqa: E402

TEXT = ("the almond was called the wakeful tree because it is the first tree to wake up after winter "
        "that is not poetry invented later it is in the standard hebrew lexicons and the prophet uses it")


def win(start, end, lines, beats=None):
    return {"window_start_seconds": start, "window_end_seconds": end, "transcript": lines,
            "beats": beats or [{"start_seconds": start, "end_seconds": end, "beat": "teaching", "opening_words_verbatim": "UNKNOWN"}]}


def narration(start, end, text=TEXT):
    w = text.split()
    return [{"start_seconds": t, "text": " ".join(w[i % len(w):i % len(w) + 12])} for i, t in enumerate(range(start, end, 5))]


class Classify(unittest.TestCase):
    def test_lines_are_never_borrowed_from_another_window(self):
        # 8YXRtsNnGX0: lines of window 900-1200 stamped 15-19 s used to land in the 0-30 s comparison
        good = win(0, 300, narration(0, 300))
        bad = win(900, 1200, [{"start_seconds": 15 + i * 0.07, "text": f"x{i} " * 12} for i in range(67)])
        r = ac.classify([good, bad], 0, 30, ac.words(" ".join(t["text"] for t in good["transcript"] if t["start_seconds"] < 30)))
        self.assertEqual(r["status"], "COMPARED")
        self.assertLess(r["mined_words"], 100)
        self.assertGreater(r["transcript_agreement"], 0.95)

    def test_defective_window_is_an_error_not_no_speech(self):
        # 9iVoAk5NZAM / VGv3fbxG7OI: ASR has 65-71 words, the covering mined window is defective
        bad = win(300, 600, [{"start_seconds": 305, "text": "word " * 770}])
        r = ac.classify([bad], 429, 459, ac.words(TEXT))
        self.assertEqual(r["status"], "MINED_WINDOW_INVALID")
        self.assertIn("TRANSCRIPT_LINE_TOO_LONG", r["problems"])

    def test_omission_and_conflict_and_silence(self):
        music = win(0, 300, [], [{"start_seconds": 0, "end_seconds": 300, "beat": "music_only"}])
        self.assertEqual(ac.classify([music], 0, 30, ac.words(TEXT))["status"], "MINED_OMISSION")
        self.assertEqual(ac.classify([music], 0, 30, [])["status"], "NO_SPEECH")
        spoken = win(0, 300, narration(0, 300))
        self.assertEqual(ac.classify([spoken], 0, 30, [])["status"], "ASR_SILENT_MINED_SPEECH")

    def test_errors_count_against_the_verdict(self):
        rows = [{"status": "COMPARED", "transcript_agreement": 0.95, "openings_checked": 1, "openings_found": 1}] * 3 + \
               [{"status": "MINED_WINDOW_INVALID"}] * 2
        s = ac.summarise(rows)
        self.assertEqual(s["window_pass_rate"], 0.6)
        self.assertEqual(s["verdict"], "FAIL")
        self.assertEqual(ac.summarise([])["verdict"], "UNKNOWN")
        no_openings = [{"status": "COMPARED", "transcript_agreement": 0.95, "openings_checked": 0, "openings_found": 0}] * 3
        self.assertEqual(ac.summarise(no_openings)["verdict"], "UNKNOWN")

    def test_holdout_is_separate_from_tuning(self):
        with tempfile.TemporaryDirectory() as t:
            sd, pd = Path(t) / "s", Path(t) / "p"
            sd.mkdir(); pd.mkdir()
            beats = [{"start_seconds": 60, "end_seconds": 300, "beat": "teaching", "opening_words_verbatim": " ".join(TEXT.split()[12:18])},
                     {"start_seconds": 0, "end_seconds": 60, "beat": "hook", "opening_words_verbatim": " ".join(TEXT.split()[:6])}]
            rec = {"video": {"video_id": "AAAAAAAAAAA", "title": "x", "description": ""}, "windows": [win(0, 300, narration(0, 300), beats)]}
            (sd / "structure-AAAAAAAAAAA.json").write_text(json.dumps(rec))
            asr = " ".join(t["text"] for t in rec["windows"][0]["transcript"] if t["start_seconds"] < 30)
            for a, b in ((0, 30), (60, 90)):
                txt = " ".join(t["text"] for t in rec["windows"][0]["transcript"] if a <= t["start_seconds"] < b)
                (pd / f"acq-AAAAAAAAAAA-{a}-{b}-v1.json").write_text(json.dumps({"profiles": [{"sound_classes": {"transcript": txt}}]}))
            reg = Path(t) / "holdout.json"
            reg.write_text(json.dumps({"tuning_windows": ["AAAAAAAAAAA:0:30"]}))
            ac.check(sd, pd, reg)
            out = json.loads((sd / "accuracy.json").read_text())
            self.assertEqual(out["tuning"]["windows"], 1)
            self.assertEqual(out["holdout"]["windows"], 1)
            self.assertEqual(out["holdout"]["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
