import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("review_discovery", HERE / "review_discovery.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Discovery(unittest.TestCase):
    def row(self, name, sha="a" * 40):
        return {"name": name, "commit": {"sha": sha}}

    def test_e207_inventory_reaches_branches_not_only_main(self):
        rows = module.discover([[self.row("main"), self.row("claude/long-arc-01-long-12")],
                                [self.row("claude/episode-genesis-09-short-13")]])
        self.assertEqual([r["build_run_id"] for r in rows], ["12", "13"])
        self.assertTrue(all(r["state"] == "DISCOVERED_NOT_VALIDATED" for r in rows))
        self.assertEqual(rows[0]["report"], "migration/evidence/episodes/arc-01-long/report-12.json")

    def test_failure_and_foreign_branch_names_are_not_deliveries(self):
        self.assertEqual(module.discover([[self.row(n) for n in (
            "claude/episode-genesis-09-short-13-failed", "claude/shot-probe-a-1",
            "evil/long-a-12", "claude/long-a-12;echo", "claude/long-a-0")]]), [])

    def test_malformed_or_moving_inventory_never_becomes_empty_success(self):
        for pages in ({}, [None], [[None]], [[self.row("claude/long-a-12", "bad")]],
                      [[self.row("claude/long-a-12"), self.row("claude/long-a-12", "b" * 40)]]):
            with self.assertRaises(ValueError):
                module.discover(pages)

    def test_duplicate_pages_are_deduplicated_not_subjects(self):
        a = self.row("claude/long-a-12")
        self.assertEqual(len(module.discover([[a], [a, self.row("claude/long-a-13")]])), 2)

    def test_existing_heartbeat_exposes_discovery_without_new_clock(self):
        wf = (HERE.parents[1] / ".github/workflows/heartbeat.yml").read_text()
        self.assertIn("migration/ops/review_discovery.py", wf)
        self.assertIn("review-discovery:", wf)
        job = wf.split("  review-discovery:", 1)[1].split("\n  runner-wake:", 1)[0]
        self.assertNotIn("actions: write", job)
        self.assertNotIn("secrets.", job)


if __name__ == "__main__":
    unittest.main()
