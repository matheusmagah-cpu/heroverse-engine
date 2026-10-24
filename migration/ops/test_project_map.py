#!/usr/bin/env python3
"""Offline: the project map finds what really runs what in this repository."""
from pathlib import Path
import sys
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

    def test_markdown_lists_every_workflow(self):
        m = pm.build(ROOT)
        md = pm.markdown(m)
        for wf in m["workflows"]:
            self.assertIn(f"`{wf}`", md)


if __name__ == "__main__":
    unittest.main()
