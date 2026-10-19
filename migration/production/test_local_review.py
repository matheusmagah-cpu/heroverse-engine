#!/usr/bin/env python3
"""Synthetic adapter tests only. No model, ASR weights, network or real qualification."""
import copy
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import local_review as local
import review_calibration as rc
import long_review as lr


class Adapter(unittest.TestCase):
    def run_cases(self, root, pilot="pilot-005", seconds=1, bad=None, frame_count=90, words=None, clock=None):
        calls = []
        names = iter(rc.CASES)
        self.prompt_seen = []

        def make(render, work, name, filters):
            calls.append((name, filters))
            return Path(work) / (name + ".mp4")

        def infer(frames, transcript, prompt):
            name = next(names)
            self.prompt_seen.append(prompt)
            self.assertEqual(len(frames), 90)
            self.assertEqual(transcript[0]["word"], "Hello")
            if name == bad:
                raise RuntimeError("must not leak arbitrary error text")
            scores = {k: 9 for k in (*lr.RUBRIC, "overall")}
            for key in rc.CASES[name][2]:
                scores[key] = 3
            return scores, {"truncated": False}

        tick = iter(n * seconds for n in range(2 * len(rc.CASES)))
        out = local.calibrate(pilot + ".mp4", Path(root) / pilot, Path(root) / (pilot + ".json"),
                              "Known title", local.MODEL_ID, local.REVISION, infer=infer,
                              asr=lambda path: words if words is not None else [{"word": "Hello", "start": 0.0, "end": 1.0}],
                              make=make, frames=lambda *args: [Path("frame.png")] * frame_count,
                              clock=clock or (lambda: next(tick)))
        self.assertEqual(calls, [(name, values[0]) for name, values in rc.CASES.items()])
        self.assertEqual(json.loads((Path(root) / (pilot + ".json")).read_text()), out)
        return out

    def references(self, runs):
        refs = copy.deepcopy(runs)
        for run in refs:
            run["model"] = lr.REVIEW_MODELS[0]
            run.pop("timing", None)
        return refs

    def test_shape_prompt_and_known_answers(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.run_cases(root)
        self.assertEqual(out["model"], local.MODEL_ID)
        self.assertEqual(out["render"], "pilot-005.mp4")
        self.assertEqual(out["revision"], local.REVISION)
        self.assertEqual(out["sample_fps"], 0.5)
        self.assertTrue(out["test_stub"])
        self.assertEqual(self.prompt_seen, [lr.review_prompt("Known title")] * len(rc.CASES))
        for name, row in out["cases"].items():
            self.assertEqual(row["verdict"], rc.CASES[name][1])
            self.assertEqual(row["review"]["status"], row["verdict"])
            self.assertTrue(set((*lr.RUBRIC, "overall")).issubset(row["review"]))

    def test_measured_mean_and_projection(self):
        with tempfile.TemporaryDirectory() as root:
            ticks = iter([0, 1, 2, 4, 5, 8, 9, 13, 14, 19, 20, 26, 27, 34])
            out = self.run_cases(root, clock=lambda: next(ticks))
        self.assertEqual(out["timing"]["seconds_per_180s_case"], 4)
        self.assertIsNone(rc.timing_status(out))
        self.assertEqual([x["wall_seconds"] for x in out["cases"].values()], list(range(1, 8)))

    def test_slow_stub_is_not_qualified(self):
        with tempfile.TemporaryDirectory() as root:
            runs = [self.run_cases(root, pilot=pilot, seconds=2000) for pilot in ("pilot-005", "pilot-006")]
        result = rc.qualification(self.references(runs) + runs)[local.MODEL_ID]
        self.assertEqual(result["verdict"], "NOT_QUALIFIED")
        self.assertTrue(any("TOO_SLOW" in reason for reason in result["reasons"]))
        self.assertTrue(all(run["timing_status"] == "TOO_SLOW" for run in runs))

    def test_two_synthetic_runs_only_exercise_qualification_contract(self):
        with tempfile.TemporaryDirectory() as root:
            runs = [self.run_cases(root, pilot=pilot) for pilot in ("pilot-005", "pilot-006")]
        self.assertEqual(rc.qualification(self.references(runs) + runs)[local.MODEL_ID]["verdict"], "QUALIFIED")
        self.assertEqual(rc.qualification(runs)[local.MODEL_ID]["verdict"], "NOT_QUALIFIED")
        one = [runs[0]]
        self.assertEqual(rc.qualification(self.references(one) + one)[local.MODEL_ID]["verdict"], "NOT_QUALIFIED")

    def test_error_is_error_and_remaining_cases_continue(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.run_cases(root, bad="control")
        self.assertEqual(out["cases"]["control"]["review"], {"status": "ERROR", "error": "RuntimeError"})
        self.assertEqual(out["cases"]["control"]["verdict"], "ERROR")
        self.assertEqual(out["cases"]["control_repeat"]["verdict"], "PASS")

    def test_incomplete_frames_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.run_cases(root, frame_count=89)
        self.assertTrue(all(r["review"]["error"] == "FRAME_COVERAGE_INCOMPLETE" for r in out["cases"].values()))
        self.assertEqual(self.prompt_seen, [])

    def test_missing_asr_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.run_cases(root, words=[])
        self.assertTrue(all(r["review"]["error"] == "ASR_WORD_TIMESTAMPS_MISSING" for r in out["cases"].values()))

    def test_invalid_clock_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.run_cases(root, seconds=0)
        self.assertIsNone(out["timing"]["seconds_per_180s_case"])
        self.assertEqual(rc.timing_status(out), "TIMING_INVALID")
        self.assertTrue(all(r["review"]["status"] == "ERROR" for r in out["cases"].values()))

    def test_setup_failure_preserves_all_error_rows(self):
        with tempfile.TemporaryDirectory() as root:
            def loader(*args):
                raise RuntimeError("private details")
            path = Path(root) / "nested/result.json"
            out = local.calibrate("pilot-005.mp4", Path(root) / "work", path, "title", local.MODEL_ID,
                                  local.REVISION, loader=loader)
            self.assertEqual(json.loads(path.read_text()), out)
        self.assertEqual(out["setup_error"], "RuntimeError")
        self.assertEqual(set(out["cases"]), set(rc.CASES))
        self.assertTrue(all(r["review"]["status"] == "ERROR" for r in out["cases"].values()))

    def test_snapshot_keeps_unfinished_cases_error(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "o.json"
            def interrupted(*args):
                raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                local.calibrate("pilot-005.mp4", root, output, "title", local.MODEL_ID, local.REVISION,
                                infer=interrupted, asr=lambda p: [{"word": "hello", "start": 0, "end": 1}],
                                make=lambda *a: Path("case.mp4"), frames=lambda *a: [Path("f")] * 90)
            out = json.loads(output.read_text())
        self.assertTrue(all(r["review"]["status"] == "ERROR" for r in out["cases"].values()))
        self.assertIsNone(out["timing"]["seconds_per_180s_case"])


class Validation(unittest.TestCase):
    def test_scores_thresholds_and_invalid_values(self):
        good = {k: 7 for k in lr.RUBRIC} | {"overall": 8}
        self.assertEqual(local.score_report(good)["status"], "PASS")
        for key in (*lr.RUBRIC, "overall"):
            scores = good | {key: good[key] - .01}
            self.assertEqual(local.score_report(scores)["status"], "FAIL")
            for invalid in (None, True, float("nan"), float("inf"), -1, 11, "9"):
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    local.score_report(good | {key: invalid})
        with self.assertRaises(ValueError):
            local.score_report({})

    def test_parser_does_not_guess_missing_or_duplicate_scores(self):
        good = {k: 9 for k in (*lr.RUBRIC, "overall")}
        self.assertEqual(local.parse_report(json.dumps(good))["status"], "PASS")
        text = "\n".join(f"{k}: {v}/10" for k, v in good.items())
        self.assertEqual(local.parse_report(text)["status"], "PASS")
        for bad in ("All good!", text + "\noverall: 2", text + "\noverall: unknown",
                    text + "\noverall: -1", text + "\noverall: 0/100", text.replace("overall: 9/10", "overall: 100/10"),
                    text.replace("9/10", "9/100"), text.replace("9/10", "9/20"), text.replace("9/10", "9.5.3"),
                    json.dumps(good)[:-1] + ", \"overall\": 1}"):
            with self.assertRaises(ValueError):
                local.parse_report(bad)

    def test_word_timestamps_are_required_and_ordered(self):
        for value in ([], [{"word": "x"}], [{"word": "x", "start": 4, "end": 3}],
                      [{"word": "x", "start": 0, "end": float("nan")}],
                      [{"word": "x", "start": 2, "end": 3}, {"word": "y", "start": 1, "end": 2}]):
            with self.assertRaises(ValueError):
                local.validate_words(value)

    def test_context_overflow_never_truncates(self):
        local.context_guard(7000, 8192, 90)
        with self.assertRaises(local.ContextLimit) as caught:
            local.context_guard(8192, 8192, 90)
        self.assertFalse(caught.exception.details["truncated"])
        self.assertEqual(caught.exception.details["input_tokens"], 8192)
        with self.assertRaises(ValueError):
            local.context_guard(7000, 8192, 64)

    def test_unverified_models_or_revisions_rejected(self):
        for model, revision in ((local.MODEL_ID, "main"), ("other/model", local.REVISION)):
            with self.assertRaises(ValueError):
                local.validate_model(model, revision)

    def test_frame_extraction_full_rate_and_no_stale_frames(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "frames"
            calls = []
            def run(command, **kwargs):
                calls.append(command)
                if command[0] == "ffprobe":
                    return subprocess.CompletedProcess(command, 0, "180.0\n")
                for i in range(90):
                    (directory / f"{i+1:04d}.png").write_bytes(b"stub")
                return subprocess.CompletedProcess(command, 0)
            with patch.object(local.subprocess, "run", side_effect=run):
                self.assertEqual(len(local.frame_paths("case.mp4", directory)), 90)
                self.assertIn(local.FRAME_FILTER, calls[1])
                with self.assertRaisesRegex(ValueError, "FRAME_DIRECTORY_NOT_EMPTY"):
                    local.frame_paths("case.mp4", directory)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_sampled_pixels_match_zero_anchored_timestamps(self):
        # Frame-dependent pixels distinguish 0,2,4s from default fps rounding's 0.9,2.9,4.9s.
        source = "nullsrc=s=16x16:r=10:d=6,geq=lum='N*3':cb=128:cr=128"
        def pixels(filter_text):
            return subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", source,
                                   "-vf", filter_text + ",scale=1:1,format=gray", "-fps_mode", "passthrough",
                                   "-f", "rawvideo", "pipe:1"], check=True, capture_output=True).stdout
        expected = pixels("select='eq(n,0)+eq(n,20)+eq(n,40)'")
        self.assertEqual(len(expected), 3)
        self.assertEqual(pixels(local.FRAME_FILTER), expected)
        self.assertNotEqual(pixels("fps=0.5:start_time=0"), expected)

    def test_workflow_never_relabels_stale_evidence(self):
        workflow = HERE.parent.parent / ".github/workflows/local-review-calibration.yml"
        text = workflow.read_text()
        tail = text.split("      - name: Record evidence, including ERROR cases\n", 1)[1]
        script = tail.split("        run: |\n", 1)[1]
        script = "\n".join(line[10:] for line in script.splitlines())
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            old = root / "migration/evidence/review-calibration/pilot-005-HuggingFaceTB--SmolVLM2-2.2B-Instruct.json"
            old.parent.mkdir(parents=True)
            old.write_text('{"old": true}')
            fresh = root / "runner-temp"
            fresh.mkdir()
            env = dict(os.environ, PILOT="pilot-005", CANDIDATE=local.MODEL_ID + "@" + local.REVISION,
                       RUNNER_TEMP=str(fresh))
            result = subprocess.run(["bash", "-e", "-c", script], cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NO_CURRENT_RUN_CALIBRATION_EVIDENCE", result.stdout)
            self.assertEqual(old.read_text(), '{"old": true}')

    def test_imports_do_not_load_ml_packages(self):
        code = ("import sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parent))
                + ");import local_review;assert not any(x in sys.modules for x in ('torch','transformers','whisper','PIL'))")
        subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True)


if __name__ == "__main__":
    unittest.main()
