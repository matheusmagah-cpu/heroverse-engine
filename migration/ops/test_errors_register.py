#!/usr/bin/env python3
"""The error register is real: every error names an antidote that exists, every active test runs on every PR,
and only the documents OPERATIONS.md lists give direction."""
import json
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ("migration/production", "migration/publish", "migration/ops", "migration/mining")
DIRECTING = {"migration/OPERATIONS.md", "migration/SYSTEM.md", "migration/STANDARD.md", "migration/ops/DOT_PROTOCOL.md", "migration/ops/RUNNER_WAKEUP.md",
             "migration/HANDOFF_NEXT_CHAT_20261023.md",  # transfer checkpoint registered in OPERATIONS
             "migration/strategy/DECISIONS.md", "migration/strategy/MODELING_SPEC.md", "migration/strategy/VIDIQ.md",
             "migration/strategy/BEAT_THE_REFERENCE_RULE.md", "migration/strategy/FORMAT_OPINION_AND_CRITIQUE.md",
             "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md",
             "migration/strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md",  # registered forecast (evidence of DECISIONS)
             "migration/kaggle/STATUS.md"}  # decision record: Kaggle not used


class Register(unittest.TestCase):
    def test_retirement_manifest_is_complete_and_reversible(self):
        plan = json.loads((ROOT / 'migration/archive/ARCHIVE_PLAN.json').read_text())
        paths = [p for group in plan['classified_paths'].values() for p in group]
        self.assertEqual(len(paths), plan['engine']['tracked_files'])
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(plan['group_counts'], {k: len(v) for k, v in plan['classified_paths'].items()})
        for source, item in plan['moves'].items():
            self.assertIn(source, paths)
            self.assertFalse((ROOT / source).exists(), 'retired path reactivated: ' + source)
            destination = ROOT / item['destination']
            self.assertTrue(destination.is_file(), item['destination'])
            self.assertEqual(hashlib.sha256(destination.read_bytes()).hexdigest(), item['sha256'])
        for source in plan['deletions']:
            self.assertTrue(source.endswith('.pyc') and '__pycache__' in source)
            self.assertFalse((ROOT / source).exists())

    def test_retired_workflows_cannot_reenter_the_scheduler(self):
        plan = json.loads((ROOT / 'migration/archive/ARCHIVE_PLAN.json').read_text())
        names = set(plan['retired_workflow_reasons'])
        for name in names:
            self.assertFalse((ROOT / '.github/workflows' / name).exists(), name)
        scheduler = (ROOT / 'migration/ops/heartbeat.py').read_text()
        dispatched = set(re.findall(r'"workflow":\s*"([a-z0-9-]+\.yml)"', scheduler))
        self.assertFalse(dispatched & names)
        # Existing recovery/production entry points must not be mistaken for clutter.
        for path in ['.github/workflows/requests.yml', 'migration/ci/render_pilot.sh',
                     'migration/second_opening_asr.py', 'migration/verify_public_voice_asset.py',
                     'HeroVerse_Linux_Source_Ready_20261013_v2.zip']:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_every_error_has_an_existing_antidote(self):
        reg = json.loads((ROOT / "migration/ops/ERRORS.json").read_text())
        ids = [e["id"] for e in reg["errors"]]
        self.assertEqual(len(ids), len(set(ids)))
        for e in reg["errors"]:
            for k in ("id", "date", "error", "fix", "antidote"):
                self.assertTrue(e.get(k), f"{e.get('id')} lacks {k}")
            f = ROOT / e["antidote"]["file"]
            self.assertTrue(f.exists(), f"{e['id']}: {f} missing")
            self.assertIn(e["antidote"]["contains"], f.read_text(), f"{e['id']}: antidote not found")

    def test_every_active_test_runs_in_pr_checks(self):
        wf = (ROOT / ".github/workflows/pr-checks.yml").read_text()
        listed = set(re.findall(r"migration/[\w/]+/test_[\w*]+\.py", wf))
        for d in ACTIVE:
            for t in sorted((ROOT / d).glob("test_*.py")):
                rel = str(t.relative_to(ROOT))
                self.assertTrue(rel in listed or f"{d}/test_*.py" in listed, f"{rel} is not run by pr-checks.yml")

    def test_only_listed_documents_direct(self):
        found = {str(p.relative_to(ROOT)) for d in ("migration", "migration/strategy", "migration/ops", "migration/kaggle")
                 for p in (ROOT / d).glob("*.md")}
        self.assertEqual(found - DIRECTING, set(), "new directing document: list it in OPERATIONS.md and here, or delete it")
        ops = (ROOT / "migration/OPERATIONS.md").read_text()
        for doc in ("DOT_PROTOCOL.md", "RUNNER_WAKEUP.md", "DECISIONS.md", "MODELING_SPEC.md", "VIDIQ.md"):
            self.assertIn(doc, ops)


if __name__ == "__main__":
    unittest.main()
