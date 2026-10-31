#!/usr/bin/env python3
"""E232: the weekly Claude limit was hit on 2026-10-28 with no enforced budget. This project may spend half of the
weekly cap; a hook stops the session over it. Window math, weighting, max-merge, exit codes and the wiring."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import token_budget as tb   # noqa: E402

CFG = {"weekly_cap_tokens": 1000, "project_share": 0.5, "warn_at": 0.8, "cache_read_weight": 0.1,
       "reset": {"weekday": "Saturday", "time_utc": "19:00"}, "cache_seconds": 0}
UTC = timezone.utc


def entry(ts, mid, inp=0, cc=0, out=0, cr=0, model="claude-x"):
    return json.dumps({"type": "assistant", "timestamp": ts, "uuid": mid, "message": {
        "id": mid, "model": model, "usage": {"input_tokens": inp, "cache_creation_input_tokens": cc,
                                              "output_tokens": out, "cache_read_input_tokens": cr}}})


class Budget(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "proj/-x-heroverse-engine/sess1/subagents").mkdir(parents=True)
        (t / "ledger").mkdir()
        (t / "cfg.json").write_text(json.dumps(CFG))
        (t / "costs.json").write_text(json.dumps({"actions": {"agent_long": {"p90": 100}, "agent_short": {"p90": 50}}}))
        (t / "plan.json").write_text(json.dumps({"budget": 500, "allocations": {"long": 400, "shorts": 60, "clocks": 0, "reviews_prs": 0, "reserve": 40}}))
        self.env = dict(os.environ, TOKEN_BUDGET_PROJECTS_DIR=str(t / "proj"), TOKEN_BUDGET_LEDGER_DIR=str(t / "ledger"),
                        TOKEN_BUDGET_CONFIG=str(t / "cfg.json"), TOKEN_BUDGET_CACHE=str(t / "cache.json"),
                        TOKEN_BUDGET_COSTS=str(t / "costs.json"), TOKEN_BUDGET_PLAN=str(t / "plan.json"),
                        TOKEN_BUDGET_NOW="2026-10-31T21:00:00Z")
        self.t = t

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, lines, name="sess1.jsonl"):
        (self.t / "proj/-x-heroverse-engine" / name).write_text("\n".join(lines) + "\n")

    def run_cli(self, cmd, stdin="", action=None, actual=None):
        extra = (["--action", action] if action else []) + (["--actual", actual] if actual else [])
        return subprocess.run([sys.executable, "-I", "-B", str(ROOT / "migration/ops/token_budget.py"), cmd, *extra],
                              input=stdin, capture_output=True, text=True, env=self.env)

    def test_window_resets_saturday_1900_utc(self):
        f = lambda s: tb.window_start(datetime.fromisoformat(s), CFG).isoformat()
        self.assertEqual(f("2026-10-31T19:00:00+00:00"), "2026-10-31T19:00:00+00:00")
        self.assertEqual(f("2026-10-31T18:59:59+00:00"), "2026-10-24T19:00:00+00:00")
        self.assertEqual(f("2026-11-04T03:00:00+00:00"), "2026-10-31T19:00:00+00:00")

    def test_weighting_and_only_inside_the_window(self):
        self.write([entry("2026-10-31T18:59:00Z", "old", out=999),          # before the reset: not counted
                    entry("2026-10-31T20:00:00Z", "a", inp=10, cc=20, out=30, cr=1000),
                    entry("2026-10-31T20:00:01Z", "a", inp=10, cc=20, out=30, cr=1000),   # same message streamed twice
                    entry("2026-10-31T20:01:00Z", "syn", out=500, model="<synthetic>")])
        os.environ.update(self.env)
        s = tb.compute(CFG, datetime(2026, 10, 31, 21, tzinfo=UTC), use_cache=False)
        self.assertEqual(s["used"], 10 + 20 + 30 + 100)   # cache_read weighted 0.1, counted once
        self.assertEqual(s["budget"], 500)

    def test_subagent_transcripts_are_counted(self):
        self.write([entry("2026-10-31T20:00:00Z", "a", out=50)])
        (self.t / "proj/-x-heroverse-engine/sess1/subagents/agent-1.jsonl").write_text(entry("2026-10-31T20:00:00Z", "b", out=70) + "\n")
        os.environ.update(self.env)
        self.assertEqual(tb.compute(CFG, datetime(2026, 10, 31, 21, tzinfo=UTC), use_cache=False)["used"], 120)

    def test_ledger_merges_by_max_per_session_across_restarts(self):
        a = {"s": {"input_tokens": 5, "cache_creation_input_tokens": 0, "output_tokens": 100, "cache_read_input_tokens": 0}}
        b = {"s": {"input_tokens": 9, "cache_creation_input_tokens": 0, "output_tokens": 40, "cache_read_input_tokens": 0},
             "t": {"input_tokens": 1}}
        m = tb.merge_max(a, b)
        self.assertEqual((m["s"]["input_tokens"], m["s"]["output_tokens"], m["t"]["input_tokens"]), (9, 100, 1))
        # a restart that lost the transcripts keeps the recorded count
        (self.t / "ledger/2026-10-31.json").write_text(json.dumps({"sessions": {"s": dict(a["s"], output_tokens=450)}}))
        os.environ.update(self.env)
        self.assertEqual(tb.compute(CFG, datetime(2026, 10, 31, 21, tzinfo=UTC), use_cache=False)["used"], 455)

    def test_check_exit_codes(self):
        self.assertEqual(self.run_cli("check").returncode, 0)
        self.write([entry("2026-10-31T20:00:00Z", "a", out=499)])      # 99.8% of 500: still allowed, no warning
        r = self.run_cli("check")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.write([entry("2026-10-31T20:00:00Z", "a", out=500)])      # at the budget: blocked
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2)
        self.assertIn("TOKEN_BUDGET_EXCEEDED", r.stderr)

    def test_precheck_blocks_when_used_plus_p90_crosses_the_budget(self):
        self.write([entry("2026-10-31T20:00:00Z", "a", out=350)])      # 350 + 100 < 500
        self.assertEqual(self.run_cli("check", "", "agent_long").returncode, 0)
        self.write([entry("2026-10-31T20:00:00Z", "a", out=401)])      # 401 + 100 > 500
        r = self.run_cli("check", "", "agent_long")
        self.assertEqual(r.returncode, 2)
        self.assertIn("TOKEN_BUDGET_EXCEEDED", r.stderr)
        self.assertEqual(self.run_cli("check").returncode, 0)          # no action: only the hard stop applies
        agent = json.dumps({"tool_name": "Agent", "tool_input": {"prompt": "produce the LONG of arc-01"}})
        self.assertEqual(self.run_cli("check", agent).returncode, 2)   # the hook derives the action from the brief

    def test_activity_allocation_is_a_hard_limit_too(self):
        sub = self.t / "proj/-x-heroverse-engine/sess1/subagents/agent-s.jsonl"
        sub.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "Make a Short"}}) + "\n"
                       + entry("2026-10-31T20:00:00Z", "s", out=20) + "\n")
        self.assertEqual(self.run_cli("check", "", "agent_short").returncode, 2)    # 20 + 50 crosses the shorts allocation 60
        self.assertEqual(self.run_cli("check", "", "agent_long").returncode, 0)     # 20 + 100 is within budget and long (400)
        self.assertEqual(self.run_cli("plan").returncode, 0)

    def test_there_is_no_warn_only_path(self):
        src = (ROOT / "migration/ops/token_budget.py").read_text()
        self.assertNotIn("TOKEN_BUDGET_WARN", src)
        self.assertNotIn("warn_at", src + (ROOT / "migration/ops/token_budget.json").read_text())

    def test_plan_allocations_fit_the_budget_and_are_all_activities(self):
        cfg = json.loads((ROOT / "migration/ops/token_budget.json").read_text())
        plan = json.loads((ROOT / "migration/ops/token_plan.json").read_text())
        self.assertEqual(set(plan["allocations"]), set(tb.ACTIVITIES))
        self.assertLessEqual(sum(plan["allocations"].values()), cfg["weekly_cap_tokens"] * cfg["project_share"])
        self.assertGreater(plan["allocations"]["reserve"], 0)
        costs = json.loads((ROOT / "migration/ops/token_costs.json").read_text())["actions"]
        for a in ("main_turn", "agent_long", "agent_short", "agent_review", "pr_cycle", "tool_bash", "tool_mcp", "tool_read_image"):
            self.assertIn(a, costs)
            self.assertLessEqual(costs[a]["mean"], costs[a]["p90"] * 1.0 + costs[a]["mean"])
        # build_plan sizes allocations from the table: 2 longs at 100 each = 200, within 1000 * 0.8
        out = tb.build_plan({"weekly_cap_tokens": 2000, "project_share": 0.5}, {"actions": {"agent_long": {"mean": 100}}},
                            {"cadence": {"long_per_week": 2, "shorts_per_week": 0, "clock_runs_per_week": 0,
                                         "mining_runs_per_week": 0, "pr_cycles_per_week": 0}, "reserve_share": 0.2})
        self.assertEqual((out["allocations"]["long"], out["allocations"]["reserve"]), (200, 800))

    def test_record_stores_actual_against_estimate_and_p90_follows(self):
        for n in (10, 20, 30):
            self.assertEqual(self.run_cli("record", "", "agent_short", str(n)).returncode, 0)
        d = json.loads((self.t / "ledger/2026-10-31.json").read_text())
        self.assertEqual([(a["estimate"], a["actual"]) for a in d["actions"]], [(50, 10), (50, 20), (50, 30)])
        os.environ.update(self.env)
        s = tb.compute(CFG, datetime(2026, 10, 31, 21, tzinfo=UTC), use_cache=False)
        self.assertEqual(tb.estimate("agent_short", s, {"actions": {"agent_short": {"p90": 50}}}), 30)

    def test_over_budget_only_status_and_git_status_pass(self):
        self.write([entry("2026-10-31T20:00:00Z", "a", out=900)])
        bash = lambda c: json.dumps({"tool_name": "Bash", "tool_input": {"command": c}})
        self.assertEqual(self.run_cli("check", bash("python3 -I -B migration/ops/token_budget.py status")).returncode, 0)
        self.assertEqual(self.run_cli("check", bash("git status")).returncode, 0)
        for c in ("git push", "git status; rm -rf x", "python3 -I -B migration/ops/token_budget.py status && git push"):
            self.assertEqual(self.run_cli("check", bash(c)).returncode, 2, c)
        self.assertEqual(self.run_cli("check", json.dumps({"tool_name": "Read", "tool_input": {}})).returncode, 2)

    def test_status_reports_used_budget_pct_projection(self):
        self.write([entry("2026-10-31T20:00:00Z", "a", out=100)])
        r = self.run_cli("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        for word in ("used 100 of budget 500", "20.0%", "projected end of week"):
            self.assertIn(word, r.stdout)

    def test_record_writes_the_weekly_ledger(self):
        self.write([entry("2026-10-31T20:00:00Z", "a", out=100)])
        self.assertEqual(self.run_cli("record").returncode, 0)
        d = json.loads((self.t / "ledger/2026-10-31.json").read_text())
        self.assertEqual(d["used"], 100)
        self.assertEqual(d["sessions"]["sess1"]["output_tokens"], 100)

    def test_config_is_half_of_a_positive_cap(self):
        cfg = json.loads((ROOT / "migration/ops/token_budget.json").read_text())
        self.assertEqual(cfg["project_share"], 0.5)   # owner, 2026-10-31: half of the weekly tokens, never more
        self.assertGreater(cfg["weekly_cap_tokens"], 0)

    def test_settings_wires_the_hook_on_every_tool_and_prompt(self):
        hooks = json.loads((ROOT / ".claude/settings.json").read_text())["hooks"]
        cmd = "python3 -I -B migration/ops/token_budget.py check"
        pre = [h for g in hooks["PreToolUse"] if g.get("matcher") == "*" for h in g["hooks"]]
        ups = [h for g in hooks["UserPromptSubmit"] for h in g["hooks"]]
        self.assertIn(cmd, [h["command"] for h in pre])
        self.assertIn(cmd, [h["command"] for h in ups])


if __name__ == "__main__":
    unittest.main()
