#!/usr/bin/env python3
"""No provider calls: ready plans reach the existing durable request dispatcher."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("production_handoff", HERE / "production_handoff.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class Handoff(unittest.TestCase):
    def test_active_history_is_complete_or_refused(self):
        row = {"path": ".github/workflows/episode.yml", "status": "queued"}
        self.assertEqual(h.active_pages([{"total_count": 1, "workflow_runs": [row]}]), [row])
        for pages in ([], [{}], [{"total_count": 1, "workflow_runs": []}],
                      [{"total_count": 1, "workflow_runs": [{}]}]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                h.active_pages(pages)

    def fixture(self, folder):
        root = Path(folder)
        for rel in ("migration/requests", h.PLAN_DIR, "migration/publish"):
            (root / rel).mkdir(parents=True, exist_ok=True)
        (root / h.PLAN_DIR / "genesis-09-short.json").write_text(json.dumps({"episode": "genesis-09-short"}))
        (root / "migration/production/bible/arcs.json").write_text('{"arcs": []}')
        (root / "migration/publish/ledger.json").write_text('{"entries": {}}')
        return root

    def test_queue_is_durable_before_dispatcher_output_and_claims_are_not_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            out = root / "outputs"
            env = {"GITHUB_REPOSITORY": h.REPO, "GITHUB_REF": "refs/heads/main", "GITHUB_OUTPUT": str(out)}
            def command(args):
                if args[0] == "gh":
                    return '[[]]' if 'branches?' in args[-1] else '[{"total_count": 0, "workflow_runs": []}]'
                if args[:2] == ["git", "push"]:
                    self.assertFalse(out.exists())
                    self.assertEqual(len(list((root / "migration/requests").glob("*.json"))), 1)
                return ""
            with patch.object(h, "ROOT", root), patch.object(h, "readiness", return_value=None), \
                 patch.object(h, "command", side_effect=command) as cmd, patch.dict(os.environ, env):
                h.main()
                self.assertEqual(out.read_text(), "ready=true\n")
                pending = next((root / "migration/requests").glob("*.json"))
                self.assertEqual(json.loads(pending.read_text())["workflow"], "episode.yml")
                inflight = root / "migration/requests/inflight"
                inflight.mkdir()
                pending.rename(inflight / pending.name)
                out.unlink()
                cmd.reset_mock()
                h.main()
                self.assertFalse(out.exists())
                self.assertFalse(any(c.args[0][:2] == ["git", "push"] for c in cmd.call_args_list))

    def test_refused_plan_never_queries_provider_or_creates_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            env = {"GITHUB_REPOSITORY": h.REPO, "GITHUB_REF": "refs/heads/main"}
            with patch.object(h, "ROOT", root), patch.object(h, "readiness", return_value="STILL_NOT_APPROVED"), \
                 patch.object(h, "command", return_value="") as cmd, patch.dict(os.environ, env):
                h.main()
                self.assertEqual(cmd.call_count, 1)  # read-only git refresh only
                self.assertEqual(list((root / "migration/requests").glob("*.json")), [])

    def test_failed_queue_push_never_invokes_dispatcher(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.fixture(folder)
            out = root / "outputs"
            env = {"GITHUB_REPOSITORY": h.REPO, "GITHUB_REF": "refs/heads/main", "GITHUB_OUTPUT": str(out)}
            def command(args):
                if args[0] == "gh":
                    return '[[]]' if 'branches?' in args[-1] else '[{"total_count": 0, "workflow_runs": []}]'
                if args[:2] == ["git", "push"]:
                    raise subprocess.CalledProcessError(1, args)
                return ""
            with patch.object(h, "ROOT", root), patch.object(h, "readiness", return_value=None), \
                 patch.object(h, "command", side_effect=command), patch.dict(os.environ, env):
                with self.assertRaises(subprocess.CalledProcessError):
                    h.main()
                self.assertFalse(out.exists())

    def test_e213_ready_plan_reaches_existing_build_without_another_chat_command(self):
        p = "migration/production/bible/plans/genesis-09-short.json"
        self.assertEqual(h.decision(p, None, [], [], []), "queue")
        self.assertEqual(h.workflow(p), "episode.yml")
        self.assertEqual(h.workflow(p.replace("genesis-09-short", "arc-01-long")), "long-build.yml")

    def test_blocked_input_never_dispatches(self):
        self.assertEqual(h.decision("p", "PREFLIGHT_STALE", [], [], []), "blocked:PREFLIGHT_STALE")

    def test_any_nonterminal_run_is_not_replaced(self):
        for state in ("queued", "in_progress", "waiting", "future_status"):
            self.assertEqual(h.decision("p", None, [{"status": state}], [], []), "wait:active_build")

    def test_evidence_branch_waits_for_real_review_instead_of_rebuilding(self):
        p = "migration/production/bible/plans/genesis-09-short.json"
        self.assertEqual(h.decision(p, None, [], ["genesis-09-short"], []), "wait:build_evidence")

    def test_claim_and_ack_never_replay_even_if_plan_inputs_changed(self):
        for state in ("inflight", "done"):
            r = {"workflow": "episode.yml", "inputs": {"plan": "p"}, "location": state}
            self.assertEqual(h.decision("p", None, [], [], [r]), "wait:existing_request")

    def test_pending_is_consumed_by_same_dispatcher_not_a_second_post(self):
        r = {"workflow": "episode.yml", "inputs": {"plan": "p"}, "location": "pending"}
        self.assertEqual(h.decision("p", None, [], [], [r]), "submit_pending")
        self.assertEqual(h.decision("p", None, [], [], [r, r]), "wait:duplicate_pending")

    def test_unrelated_request_does_not_block_independent_work(self):
        r = {"workflow": "episode.yml", "inputs": {"plan": "other"}, "location": "done"}
        self.assertEqual(h.decision("p", None, [], [], [r]), "queue")

    def test_live_wiring_uses_only_the_existing_heartbeat_and_claim_dispatcher(self):
        root = HERE.parents[1]
        beat = (root / ".github/workflows/heartbeat.yml").read_text()
        requests = (root / ".github/workflows/requests.yml").read_text()
        self.assertIn("production_handoff.py", beat)
        self.assertIn("uses: ./.github/workflows/requests.yml", beat)
        self.assertIn("  workflow_call:", requests)
        self.assertNotIn("gh workflow run", (HERE / "production_handoff.py").read_text())


if __name__ == "__main__":
    unittest.main()
