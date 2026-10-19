#!/usr/bin/env python3
"""Known-answer native planner tests; no network or provider effects."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_plan as np


def video(vid="v", minutes=10, role="winner"):
    return {"video_id": vid, "minutes": minutes, "role": role}


def claim(start, end=None, status="COMPLETED", vid="v"):
    return {"video_id": vid, "start_seconds": start,
            "end_seconds": start + 60 if end is None else end, "status": status}


def pick(videos=None, claims=None, n=100, stderr=None):
    return np.plan({"claims": claims or []},
                   {"videos": [video()] if videos is None else videos}, n, stderr)


class NativePlan(unittest.TestCase):
    def test_opening_even_grid_and_four_window_cap(self):
        self.assertEqual(pick(), ["v:0:60", "v:180:240", "v:360:420", "v:540:600"])

    def test_n_limits_output_without_changing_grid(self):
        self.assertEqual(pick(n=2), ["v:0:60", "v:180:240"])
        self.assertEqual(pick(n=0), [])
        with self.assertRaises(ValueError):
            pick(n=-1)

    def test_all_statuses_count_and_prevent_repeats(self):
        for status in ("COMPLETED", "FAILED", "RESERVED", "UNKNOWN"):
            with self.subTest(status=status):
                self.assertEqual(pick(claims=[claim(0, status=status)]),
                                 ["v:180:240", "v:360:420", "v:540:600"])
        claims = [claim(s, status=status) for s, status in
                  zip((0, 180, 360, 540), ("COMPLETED", "FAILED", "RESERVED", "UNKNOWN"))]
        self.assertEqual(pick(claims=claims), [])

    def test_unique_ledger_windows_count_once(self):
        self.assertEqual(pick(claims=[claim(0), claim(0, status="FAILED")]),
                         ["v:180:240", "v:360:420", "v:540:600"])

    def test_non_grid_claims_count_toward_four(self):
        self.assertEqual(pick(claims=[claim(130), claim(250), claim(370)]), ["v:0:60"])

    def test_spacing_applies_to_existing_short_or_failed_windows(self):
        self.assertEqual(pick(claims=[claim(0, 40, "FAILED"), claim(150, 190)]),
                         ["v:360:420", "v:540:600"])

    def test_role_order_and_video_id_tie_break(self):
        videos = [video("other", 1, "anything"), {"video_id": "missing", "minutes": 1},
                  video("latest", 1, "latest"), video("weak", 1, "weak_contrast"),
                  video("b", 1), video("a", 1)]
        expected = [f"{vid}:0:60" for vid in ("a", "b", "weak", "latest", "missing", "other")]
        self.assertEqual(pick(videos), expected)
        self.assertEqual(pick(list(reversed(videos))), expected)

    def test_short_video_grid_and_exact_spacing_boundary(self):
        for seconds, starts in ((60, [0]), (179, [0]), (180, [0, 120]),
                                (300, [0, 120, 240]), (420, [0, 120, 240, 360])):
            with self.subTest(seconds=seconds):
                self.assertEqual(pick([video(minutes=seconds / 60)]),
                                 [f"v:{s}:{s + 60}" for s in starts])

    def test_fractional_duration_rounds_down_inside_video(self):
        self.assertEqual(pick([video(minutes=10.025)]),
                         ["v:0:60", "v:180:240", "v:360:420", "v:541:601"])

    def test_missing_null_invalid_and_short_duration_report_reason(self):
        videos = [{"video_id": "missing"}, video("null", None), video("zero", 0),
                  video("negative", -1), video("string", "10"), video("boolean", True),
                  video("infinite", float("inf")), video("nan", float("nan")),
                  video("short", 0.5)]
        errors = io.StringIO()
        self.assertEqual(pick(videos, stderr=errors), [])
        lines = errors.getvalue().splitlines()
        self.assertEqual(len(lines), len(videos))
        for v in videos:
            self.assertTrue(any(line.startswith(f"SKIP {v['video_id']}:") and "duration" in line
                                for line in lines))

    def test_second_batch_skips_first_batch(self):
        first = pick(n=2)
        claims = [claim(int(w.split(":")[1]), status="RESERVED") for w in first]
        self.assertEqual(pick(claims=claims), ["v:360:420", "v:540:600"])

    def test_duplicate_video_records_do_not_repeat_windows(self):
        self.assertEqual(pick([video(), video()]), pick())

    def test_empty_inputs(self):
        self.assertEqual(np.plan({}, {}, 10), [])

    def test_cli_isolated_deterministic_read_only_and_stdout_format(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger, measured = root / "ledger.json", root / "measured.json"
            ledger.write_text(json.dumps({"claims": [claim(0, status="FAILED")]}))
            measured.write_text(json.dumps({"videos": [video("bad", None), video()]}))
            before = (ledger.read_bytes(), measured.read_bytes())
            command = [sys.executable, "-I", "-B", str(Path(np.__file__).resolve()),
                       str(ledger), str(measured), "2"]
            first = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True)
            second = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True)
            self.assertEqual(first.stdout, "v:180:240;v:360:420\n")
            self.assertEqual(second.stdout, first.stdout)
            self.assertIn("SKIP bad:", first.stderr)
            self.assertEqual((ledger.read_bytes(), measured.read_bytes()), before)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["ledger.json", "measured.json"])


if __name__ == "__main__":
    unittest.main()
