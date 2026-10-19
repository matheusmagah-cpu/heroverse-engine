import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import structure_mining as sm  # noqa: E402


def narration(start, end, every=5, words=12):
    """A realistic transcript: one sentence every 5 s, 12 words each (144 wpm), stamped inside the window."""
    return [{"start_seconds": t, "text": " ".join([f"sentence{t}"] + ["word"] * (words - 1))} for t in range(start, end, every)]


def window(start, end, cuts):
    edges = [start, *cuts, end]
    return {"video_id": "abcdefghijk", "window_start_seconds": start, "window_end_seconds": end,
            "transcript": narration(start, end),
            "audio_received": True, "visual_received": True,
            "beats": [{"start_seconds": a, "end_seconds": b, "beat": "hook" if a == 0 else "teaching",
                       "opening_words_verbatim": "x", "content": "x", "device": "none", "emotion": "calm"}
                      for a, b in zip(edges, edges[1:])],
            "picture": {"shots_counted": 30}, "sound": {}, "scripture_references": ["John 3:16"]}


class StructureMining(unittest.TestCase):
    # regression cases from the 2026-10-18 accuracy audit (structure-mining/20261017 vs native ASR)
    def test_reviewer_allowance_is_reserved_for_decisions(self):
        # E26: mining and Shorts selection spent gemini-3.8-flash's small free daily allowance before the reviews
        root = Path(__file__).resolve().parents[2]
        reviewers = set()
        for f in ("migration/production/long_review.py", "migration/production/shorts_review.py"):
            reviewers |= set(re.findall(r'REVIEW_MODELS = \(([^)]*)\)', (root / f).read_text())[0].replace('"', "").replace(",", " ").split())
        self.assertEqual(set(sm.DECISION_MODELS), reviewers)
        self.assertFalse(set(sm.SUPPORT_MODELS) & reviewers)
        self.assertTrue(sm.SUPPORT_MODELS)
        for f in ("migration/production/long_review.py", "migration/production/shorts_select.py", "migration/mining/structure_mining.py",
                  "migration/mining/packaging_mining.py"):
            text = (root / f).read_text()
            self.assertNotIn("call(payload, key, list(sm.FREE_MODELS))", text, f)
            self.assertNotIn("call(payload, key, list(FREE_MODELS))", text, f)
            self.assertNotIn('",".join(FREE_MODELS)', text, f)
            self.assertNotIn("sm.FREE_MODELS)", text, f)

    def test_the_last_failure_keeps_the_provider_diagnostic(self):
        # E29: call() re-raised a bare code, so nobody could tell a per-minute from a per-day quota
        real = sm.transport
        def fail(payload, key, model):
            raise sm.ProviderFailure("HTTP_429_RESOURCE_EXHAUSTED:QUOTA", {"quota_ids": ["X-PerMinute"], "message": "m"})
        sm.transport = fail
        try:
            with self.assertRaises(sm.ProviderFailure) as e:
                sm.call({}, "k", ["m"])
        finally:
            sm.transport = real
        self.assertEqual(e.exception.diagnostic["quota_ids"], ["X-PerMinute"])

    def test_every_call_records_its_token_usage(self):
        real, sm.USAGE[:] = sm.transport, []
        sm.transport = lambda payload, key, model: {"candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                                                    "usageMetadata": {"promptTokenCount": 1200, "totalTokenCount": 1300}}
        try:
            sm.call({}, "k", ["m"])
        finally:
            sm.transport = real
        self.assertEqual(sm.USAGE, [{"model": "m", "promptTokenCount": 1200, "totalTokenCount": 1300}])
        sm.USAGE[:] = []

    def test_transcript_stamped_outside_its_window_is_rejected(self):
        w = window(900, 1200, [960])  # e.g. 8YXRtsNnGX0 window 900-1200 stamped 15-19 s
        w["transcript"] = [{"start_seconds": 15 + i * 0.07, "text": f"line{i} " + "word " * 11} for i in range(67)]
        self.assertIn("TRANSCRIPT_TIME_OUTSIDE_WINDOW", sm.transcript_problems(w, 900, 1200))
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 900, 1200))

    def test_rescaled_times_are_rejected(self):
        w = window(300, 600, [400])  # e.g. 6Q98ZRdnzw8 window 300-600 stamped up to 3375 s
        w["transcript"] = [{"start_seconds": 300 + i * 58.0, "text": f"line{i} " + "word " * 11} for i in range(53)]
        self.assertIn("TRANSCRIPT_TIME_OUTSIDE_WINDOW", sm.transcript_problems(w, 300, 600))

    def test_whole_window_in_one_line_is_rejected(self):
        w = window(300, 600, [400])  # e.g. VGv3fbxG7OI window 300-600: one 770-word line
        w["transcript"] = [{"start_seconds": 305, "text": "word " * 770}]
        self.assertIn("TRANSCRIPT_LINE_TOO_LONG", sm.transcript_problems(w, 300, 600))

    def test_truncated_transcript_is_rejected(self):
        w = window(0, 300, [23, 51, 109])  # e.g. 8YXRtsNnGX0 window 0-300: lines stop at 130 s, 207 words
        w["transcript"] = narration(0, 130, every=5, words=8)
        self.assertIn("TRANSCRIPT_INCOMPLETE", sm.transcript_problems(w, 0, 300))

    def test_music_only_window_with_no_words_is_valid(self):
        w = window(0, 300, [20, 140])
        for b in w["beats"]:
            b["beat"] = "music_only"
        w["transcript"] = []
        self.assertEqual(sm.transcript_problems(w, 0, 300), [])

    def test_normal_narration_has_no_problem(self):
        self.assertEqual(sm.transcript_problems(window(0, 300, [20, 140]), 0, 300), [])

    def test_contiguous_window_is_valid(self):
        self.assertTrue(sm.valid_window(window(0, 300, [20, 140]), "abcdefghijk", 0, 300))

    def test_gap_or_foreign_video_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 60
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 300, [20]), "zzzzzzzzzzz", 0, 300))
        self.assertFalse(sm.valid_window(window(0, 250, [20]), "abcdefghijk", 0, 300))

    def test_measured_fields_are_computed_not_asked(self):
        video = {"seconds": 600, "title": "Why Did God Bury Moses Himself?", "description": "0:00 Intro\n2:15 Moses",
                 "likes": 50, "views": 1000, "comments": 5}
        m = sm.measured(video, [window(0, 300, [20, 140]), window(300, 600, [450])])
        self.assertEqual(m["chapters"], 2)
        self.assertEqual(m["beats"], 5)
        self.assertEqual(m["coverage_fraction"], 1.0)
        self.assertEqual(m["shots_per_minute_model_counted"], 6.0)
        self.assertEqual(m["first_spoken_beat"], {"at": 0, "beat": "hook"})

    def test_looping_transcript_is_rejected(self):
        w = window(0, 300, [20, 140])
        w["transcript"] = [{"start_seconds": i, "text": "By divine authority."} for i in range(12)]
        self.assertTrue(sm.degenerate(w))
        self.assertFalse(sm.valid_window(w, "abcdefghijk", 0, 300))

    def test_small_gaps_are_repaired_large_are_not(self):
        w = window(0, 300, [20, 140])
        w["beats"][0]["start_seconds"], w["beats"][1]["start_seconds"] = 5, 30
        self.assertTrue(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))
        w = window(0, 300, [20, 140])
        w["beats"][1]["start_seconds"] = 80
        self.assertFalse(sm.valid_window(sm.repair(w, 0, 300), "abcdefghijk", 0, 300))


if __name__ == "__main__":
    unittest.main()
