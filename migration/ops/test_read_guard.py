#!/usr/bin/env python3
"""E263: whole-file reads of ERRORS.json and binary evidence, and full CI logs, burned tens of thousands of
tokens per session. Read guard, errors_query, ci_digest and the settings wiring."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_digest   # noqa: E402
import errors_query   # noqa: E402

GUARD = str(ROOT / "migration/ops/read_guard.py")


def guard(tool_input, tool="Read"):
    p = subprocess.run([sys.executable, "-I", "-B", GUARD], input=json.dumps(
        {"tool_name": tool, "tool_input": tool_input}), capture_output=True, text=True)
    return p.returncode, p.stderr


class ReadGuard(unittest.TestCase):
    def test_errors_json_needs_limit(self):
        p = str(ROOT / "migration/ops/ERRORS.json")
        code, err = guard({"file_path": p})
        self.assertEqual(code, 2)
        self.assertIn("errors_query.py", err)
        self.assertEqual(guard({"file_path": p, "limit": 20})[0], 0)

    def test_media_is_denied(self):
        for name in ("a.mp4", "b.MOV", "c.wav"):
            self.assertEqual(guard({"file_path": f"/x/{name}"})[0], 2, name)

    def test_large_image_and_json_denied_small_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            for name, size, want in (("big.png", 2 * 1024 * 1024 + 1, 2), ("big.json", 2 * 1024 * 1024 + 1, 2),
                                     ("ok.png", 100, 0), ("ok.json", 100, 0)):
                f = Path(d) / name
                f.write_bytes(b"0" * size)
                self.assertEqual(guard({"file_path": str(f)})[0], want, name)

    def test_other_reads_and_tools_pass(self):
        self.assertEqual(guard({"file_path": str(ROOT / "CLAUDE.md")})[0], 0)
        self.assertEqual(guard({"file_path": "/x/a.mp4"}, tool="Bash")[0], 0)

    def test_bad_input_does_not_block(self):
        p = subprocess.run([sys.executable, "-I", "-B", GUARD], input="not json", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)

    def test_settings_wiring_keeps_existing_hooks(self):
        s = json.loads((ROOT / ".claude/settings.json").read_text())
        pre = s["hooks"]["PreToolUse"]
        self.assertTrue(any(h["matcher"] == "*" and "token_budget.py" in h["hooks"][0]["command"] for h in pre))
        read = [h for h in pre if h["matcher"] == "Read"]
        self.assertEqual(len(read), 1)
        self.assertEqual(read[0]["hooks"][0]["command"],
                         'python3 -I -B "$CLAUDE_PROJECT_DIR/migration/ops/read_guard.py"')
        self.assertIn("token_budget.py", json.dumps(s["hooks"]["UserPromptSubmit"]))


class Query(unittest.TestCase):
    ERRS = [{"id": "E1", "class": "instrument", "error": "alpha thing"},
            {"id": "E2", "class": ["instrument", "drift"], "error": "beta"}]

    def test_modes(self):
        self.assertEqual(errors_query.run(["--class", "instrument"], self.ERRS), ["E1", "E2"])
        self.assertEqual(errors_query.run(["--class", "drift"], self.ERRS), ["E2"])
        self.assertEqual(errors_query.run(["--grep", "ALPHA"], self.ERRS), ["E1: alpha thing"])
        self.assertEqual(json.loads(errors_query.run(["e2"], self.ERRS)[0])["id"], "E2")

    def test_real_register_has_this_entry(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(errors_query.main(["E263"]), 0)
        self.assertIn("read_guard", buf.getvalue())


class Digest(unittest.TestCase):
    def test_only_failed_jobs_get_log_tail(self):
        calls = []

        def api(path, raw=False):
            calls.append(path)
            if path.endswith("/runs/7"):
                return {"status": "completed", "conclusion": "failure"}
            if "/jobs?" in path:
                return {"jobs": [{"id": 1, "name": "ok", "conclusion": "success"},
                                 {"id": 2, "name": "bad", "conclusion": "failure"}]}
            if path.endswith("/jobs/2/logs"):
                return "\n".join(f"line{i}" for i in range(100))
            raise AssertionError(path)

        out = ci_digest.digest("7", api=api)
        self.assertIn("status=completed conclusion=failure", out)
        self.assertIn("job ok: success", out)
        self.assertIn("job bad: failure", out)
        self.assertIn("line99", out)
        self.assertIn("line60", out)
        self.assertNotIn("line59", out)
        self.assertFalse(any("/jobs/1/logs" in c for c in calls))

    def test_gh_is_called_via_rest_api(self):
        from unittest import mock
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout='{"a": 1}', stderr="")
            self.assertEqual(ci_digest.gh("repos/x"), {"a": 1})
            self.assertEqual(run.call_args[0][0], ["gh", "api", "repos/x"])

    def test_bad_args(self):
        self.assertEqual(ci_digest.main(["abc"]), 2)


if __name__ == "__main__":
    unittest.main()
