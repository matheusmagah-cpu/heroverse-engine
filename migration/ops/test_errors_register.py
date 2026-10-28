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
DIRECTING = {"migration/OPERATIONS.md", "migration/SYSTEM.md", "migration/STANDARD.md", "migration/ops/RUNNER_WAKEUP.md", "migration/ops/CLAUDE_REVIEW.md",
             "migration/strategy/DECISIONS.md", "migration/strategy/MODELING_SPEC.md", "migration/strategy/VIDIQ.md",
             "migration/strategy/BEAT_THE_REFERENCE_RULE.md",
             "migration/strategy/FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md",
             "migration/strategy/MARKET_FORECAST_TIME_TO_YPP_20261017.md"}  # registered forecast (evidence of DECISIONS)
# E115: failure classes (rework audit 2026-10-27). An entry's `class` is one of these, or a list of them
CLASSES = {"cheap-vs-expensive", "env-vs-test", "review-after-build", "random", "no-data", "threshold", "external",
           "order", "drift", "silent", "direction", "pr-late", "capacity", "rerun-without-fix", "recurrence",
           "fragile-input", "instrument"}   # E120 instrument: the instrument cannot measure the property it gates
CLASSED_FROM = 115   # E100-E114 were backfilled with their class; from E115 on every entry is classified


def _num(eid):
    return int(eid[1:]) if eid[1:].isdigit() else 0


def _classes(value):
    return [value] if isinstance(value, str) else list(value or [])


def class_problems(errors):
    """E115: a recurring class names its prior entries and an antidote that covers the class, not the instance."""
    bad, seen = [], {}
    for e in errors:
        cls = _classes(e.get("class"))
        if _num(e["id"]) >= CLASSED_FROM and not cls:
            bad.append(f"{e['id']}: no class (one of test_errors_register.CLASSES)")
        for c in cls:
            if c not in CLASSES:
                bad.append(f"{e['id']}: class {c!r} is not in CLASSES")
        prior = _classes(e.get("prior"))
        for pid in prior:
            if not set(seen.get(pid, ())) & set(cls):
                bad.append(f"{e['id']}: prior {pid} is not an earlier entry of its class")
        if _num(e["id"]) >= CLASSED_FROM:
            covers = _classes(e.get("antidote", {}).get("covers"))
            for c in cls:
                earlier = [eid for eid, ecls in seen.items() if c in ecls]
                missing = [eid for eid in earlier if eid not in prior]
                if missing:
                    bad.append(f"{e['id']}: class {c} recurred: `prior` must name {missing}")
                if c not in covers:
                    bad.append(f"{e['id']}: its antidote must be class-level: antidote.covers names {c!r}")
        seen[e["id"]] = cls
    return bad


class Register(unittest.TestCase):
    def test_production_entry_points_exist(self):
        for path in ['.github/workflows/requests.yml', 'migration/ci/render_pilot.sh',
                     'migration/second_opening_asr.py', 'migration/verify_public_voice_asset.py',
                     'HeroVerse_Linux_Source_Ready_20261013_v2.zip']:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_push_triggers_ignore_deleted_files(self):
        # E50: deleting pilot-001 (out/qa.json) fired approve.yml, which then looked for the deleted render
        for name in ('approve.yml', 'publish.yml'):
            text = (ROOT / '.github/workflows' / name).read_text()
            diffs = re.findall(r'git diff [^|]*HEAD~1 HEAD', text)
            self.assertTrue(diffs, name)
            for d in diffs:
                self.assertIn('--diff-filter=AM', d, name)

    def test_a_piped_step_fails_when_its_command_fails(self):
        # E54: the voice judge crashed inside "judge | tee" and the run still showed success
        for wf in sorted((ROOT / '.github/workflows').glob('*.yml')):
            for step in re.split(r'\n      - ', wf.read_text()):
                if re.search(r'\|\s*tee\b', step):
                    self.assertIn('pipefail', step, wf.name)

    def test_apt_installs_cannot_hang(self):
        # E55: voice-sample.yml hung 30 min on the hosted apt mirror; these workflows bound apt with timeouts
        # E102: they and render_pilot.sh install through migration/ci/apt_install.sh, which bounds every command
        shared = (ROOT / 'migration/ci/apt_install.sh').read_text()
        self.assertIn('mirror+file:/etc/apt/apt-mirrors.txt#https://archive.ubuntu.com/ubuntu/', shared)
        self.assertEqual(len(re.findall(r'.*apt-get .*(?:update|install).*', shared)), 2)
        # voice-sample.yml (the workflow of E55) was retired with the closed voice A/B (slim audit 2026-10-28); every
        # workflow that installs with apt_install.sh is held to the same bound
        users = sorted(str(p.relative_to(ROOT)) for p in (ROOT / '.github/workflows').glob('*.yml')
                       if 'apt_install.sh' in p.read_text())
        for path in sorted({'.github/workflows/pr-checks.yml', 'migration/ci/render_pilot.sh', *users}):
            text = (ROOT / path).read_text()
            self.assertIn('apt_install.sh', text, path)
            for line in re.findall(r'.*apt-get .*(?:update|install).*', text) + re.findall(r'.*apt-get .*(?:update|install).*', shared):
                self.assertIn('timeout ', line, f'{path}: {line.strip()}')

    def test_approval_checks_the_owner_floor(self):
        # E65: a 9.0 review would be approved and then refused at publication, again and again
        wf = (ROOT / '.github/workflows/approve.yml').read_text()
        i, j = wf.index('oq.check(w, r["output_sha256"], oq.LONG_REVIEWER)'), wf.index('"approved": True')
        self.assertLess(i, j)
        self.assertIn('status="BELOW_OWNER_FLOOR"', wf)

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

    def test_a_recurring_class_names_its_prior_and_a_class_level_antidote(self):
        # E115: E08 -> E86 -> E90, E10 -> E63 -> E112, E54 -> E73 -> E81 -> E89 ... each antidote fixed the instance;
        # a classified entry whose class already has one names it (`prior`) and its antidote states the class it covers
        reg = json.loads((ROOT / "migration/ops/ERRORS.json").read_text())
        self.assertEqual(class_problems(reg["errors"]), [])
        a = {"id": "E200", "class": "order", "antidote": {"covers": "order"}}
        b = {"id": "E201", "class": "order", "antidote": {"covers": "order"}}
        self.assertEqual(class_problems([a]), [])
        self.assertTrue(any("prior` must name ['E200']" in x for x in class_problems([a, b])))
        self.assertEqual(class_problems([a, dict(b, prior=["E200"])]), [])
        self.assertTrue(any("class-level" in x for x in class_problems([a, dict(b, prior="E200", antidote={})])))
        self.assertTrue(any("not an earlier entry" in x for x in class_problems([a, dict(b, prior="E999")])))
        self.assertTrue(any("no class" in x for x in class_problems([{"id": "E202", "antidote": {}}])))
        self.assertTrue(any("not in CLASSES" in x for x in class_problems([dict(a, **{"class": "oops"})])))
        old = [{"id": "E100", "class": "drift"}, {"id": "E102", "class": "drift"}]   # backfilled history stays as is
        self.assertEqual(class_problems(old), [])

    def test_validated_structures_count_only_winners_above_the_breakout_bar(self):
        # E88: Steelshort (breakout 6.2) and two prayer Shorts (46.41, 13.34) were counted as winners; SYSTEM.md 1.1
        # sets the bar at 50, so a validated structure needs >= 6 counted winners from its evidence, each >= 50
        for f in sorted((ROOT / "migration/structures").glob("*.json")):
            s = json.loads(f.read_text())
            if s.get("status") not in ("validated", "active"):
                continue
            ev = s.get("validation", {}).get("evidence", [])
            winners = []
            for rel in [ev] if isinstance(ev, str) else ev:
                path = ROOT / "migration" / rel
                if path.suffix == ".json":
                    winners += [w for w in json.loads(path.read_text()).get("winners", []) if "breakout" in w]
            below = [w.get("videoId") or w.get("video") for w in winners if (w["breakout"] or 0) < 50]
            self.assertEqual(below, [], f"{f.name}: winners below breakout 50")
            if winners:
                self.assertGreaterEqual(len(winners), 6, f"{f.name}: fewer than 6 counted winners")

    def test_preview_footage_sheets_hold_at_most_twelve_clips(self):
        # E72: one sheet of every clip made modern objects too small to see; the preview splits them 12 a sheet
        self.assertIn("PER_SHEET=12", (ROOT / "migration/ci/render_pilot.sh").read_text())

    def test_every_antidote_is_a_test_that_runs_on_every_pr(self):
        # owner, 2026-10-26: "an error must never repeat": its antidote is a test, and that test runs on every PR
        # (pr-checks.yml, or pavo-mcp.yml for the Pavo integration), so a change that brings the error back fails CI
        wf = (ROOT / ".github/workflows/pr-checks.yml").read_text() + (ROOT / ".github/workflows/pavo-mcp.yml").read_text()
        listed = set(re.findall(r"migration/[\w/-]+/test_[\w*]+\.py", wf))

        def runs(rel):
            return rel in listed or any(l.endswith("test_*.py") and rel.startswith(l[:-len("test_*.py")])
                                        and "/" not in rel[len(l) - len("test_*.py"):] for l in listed)
        reg = json.loads((ROOT / "migration/ops/ERRORS.json").read_text())
        for e in reg["errors"]:
            f = e["antidote"]["file"]
            self.assertTrue(Path(f).name.startswith("test_"), f"{e['id']}: antidote {f} is not a test")
            self.assertTrue(runs(f), f"{e['id']}: antidote {f} does not run on every PR")

    def test_every_active_test_runs_in_pr_checks(self):
        wf = (ROOT / ".github/workflows/pr-checks.yml").read_text()
        listed = set(re.findall(r"migration/[\w/-]+/test_[\w*]+\.py", wf))
        for d in ACTIVE:
            for t in sorted((ROOT / d).glob("test_*.py")):
                rel = str(t.relative_to(ROOT))
                self.assertTrue(rel in listed or f"{d}/test_*.py" in listed, f"{rel} is not run by pr-checks.yml")

    def test_only_listed_documents_direct(self):
        found = {str(p.relative_to(ROOT)) for d in ("migration", "migration/strategy", "migration/ops")
                 for p in (ROOT / d).glob("*.md")}
        self.assertEqual(found - DIRECTING, set(), "new directing document: list it in OPERATIONS.md and here, or delete it")
        ops = (ROOT / "migration/OPERATIONS.md").read_text()
        for doc in ("RUNNER_WAKEUP.md", "DECISIONS.md", "MODELING_SPEC.md", "VIDIQ.md", "CLAUDE_REVIEW.md"):
            self.assertIn(doc, ops)


if __name__ == "__main__":
    unittest.main()
