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
DIRECTING = {"migration/OPERATIONS.md", "migration/SYSTEM.md", "migration/STANDARD.md", "migration/ops/RUNNER_WAKEUP.md",
             "migration/strategy/DECISIONS.md", "migration/strategy/MODELING_SPEC.md", "migration/strategy/VIDIQ.md",
             "migration/strategy/BEAT_THE_REFERENCE_RULE.md", "migration/strategy/FORMAT_OPINION_AND_CRITIQUE.md",
             "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md",
             "migration/strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md"}  # registered forecast (evidence of DECISIONS)


class Register(unittest.TestCase):
    def test_production_entry_points_exist(self):
        for path in ['.github/workflows/requests.yml', 'migration/ci/render_pilot.sh',
                     'migration/second_opening_asr.py', 'migration/verify_public_voice_asset.py',
                     'HeroVerse_Linux_Source_Ready_20261013_v2.zip']:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_push_triggers_ignore_deleted_files(self):
        # E50: deleting pilot-001 (out/qa.json) fired approve.yml, which then looked for the deleted render
        for name in ('approve.yml', 'publish.yml'):  # shorts.yml is byte-frozen (test_shorts_produce)
            text = (ROOT / '.github/workflows' / name).read_text()
            diffs = re.findall(r'git diff [^|]*HEAD~1 HEAD', text)
            self.assertTrue(diffs, name)
            for d in diffs:
                self.assertIn('--diff-filter=AM', d, name)

    def test_heartbeat_dispatches_only_existing_workflows(self):
        scheduler = (ROOT / 'migration/ops/heartbeat.py').read_text()
        for name in set(re.findall(r'"workflow":\s*"([a-z0-9-]+\.yml)"', scheduler)):
            self.assertTrue((ROOT / '.github/workflows' / name).is_file(), name)

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
        found = {str(p.relative_to(ROOT)) for d in ("migration", "migration/strategy", "migration/ops")
                 for p in (ROOT / d).glob("*.md")}
        self.assertEqual(found - DIRECTING, set(), "new directing document: list it in OPERATIONS.md and here, or delete it")
        ops = (ROOT / "migration/OPERATIONS.md").read_text()
        for doc in ("RUNNER_WAKEUP.md", "DECISIONS.md", "MODELING_SPEC.md", "VIDIQ.md"):
            self.assertIn(doc, ops)


if __name__ == "__main__":
    unittest.main()
