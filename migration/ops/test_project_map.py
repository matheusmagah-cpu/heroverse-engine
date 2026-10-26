#!/usr/bin/env python3
"""Offline: the project map finds what really runs what in this repository."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_map as pm  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class Map(unittest.TestCase):
    def test_known_edges_of_the_engine(self):
        m = pm.build(ROOT)
        rq = m["modules"]["migration/production/render_queue.py"]
        self.assertIn("migration/production/preview_gate.py", rq["local_imports"])
        self.assertIn("heartbeat.yml", rq["called_by_workflows"])
        self.assertIn("migration/ci/render_pilot.sh", m["workflows"]["pilot-preview.yml"]["calls"])
        # a script run only through render_pilot.sh still counts as run by the render workflow
        self.assertIn("pilot-render-stills.yml", m["modules"]["migration/production/qa_pilot.py"]["called_by_workflows"])
        self.assertIn("approve.yml", m["workflows"]["pilot-render-stills.yml"]["dispatches"])

    def test_a_checkout_under_a_dot_claude_folder_keeps_its_shell_edges(self):
        # E105: an agent worktree lives in .claude/worktrees/<name>; the shell exclusion compared the absolute path's
        # parts, so every shell file was dropped there and test_known_edges_of_the_engine failed
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".claude" / "worktrees" / "agent-x"
            for rel, text in (("migration/ci/run.sh", "python3 migration/production/step.py\n"),
                              ("migration/production/step.py", '"""A step."""\n'),
                              ("migration/archive/old.sh", "python3 migration/production/old.py\n"),
                              ("migration/.claude/hook.sh", "python3 migration/production/hook.py\n"),
                              (".github/workflows/w.yml", "name: W\non:\n  push:\njobs:\n  a:\n    steps:\n"
                                                          "      - run: bash migration/ci/run.sh\n")):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text)
            m = pm.build(root)
            self.assertEqual(sorted(m["shell"]), ["migration/ci/run.sh"])   # archive and .claude inside: skipped
            self.assertEqual(m["shell"]["migration/ci/run.sh"], ["migration/production/step.py"])
            self.assertEqual(m["modules"]["migration/production/step.py"]["called_by_workflows"], ["w.yml"])

    def test_markdown_lists_every_workflow(self):
        m = pm.build(ROOT)
        md = pm.markdown(m)
        for wf in m["workflows"]:
            self.assertIn(f"`{wf}`", md)


if __name__ == "__main__":
    unittest.main()
