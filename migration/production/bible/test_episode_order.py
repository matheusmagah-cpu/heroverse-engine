"""E112: a later part is not built while the part before it is planned but not recorded."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import episode_order as eo  # noqa: E402

WORKFLOW = HERE.parents[2] / ".github" / "workflows" / "episode.yml"


class Order(unittest.TestCase):
    def test_a_later_part_waits_until_the_earlier_part_is_recorded(self):
        # E112: genesis-09's build was dispatched while genesis-08 (planned, not recorded) still needed a resume;
        # the one-at-a-time queue then held genesis-08's fix behind genesis-09
        saved = eo.PLANS, eo.EPISODES
        d = Path(tempfile.mkdtemp())
        try:
            eo.PLANS, eo.EPISODES = d / "plans", d / "episodes"
            eo.PLANS.mkdir()
            eo.EPISODES.mkdir()
            later = {"episode": "genesis-09-short", "part": 9}
            self.assertIsNone(eo.earlier_part_open(later))                  # no plan for part 8: nothing to wait on
            (eo.PLANS / "genesis-08-short.json").write_text("{}")
            self.assertEqual(eo.earlier_part_open(later),
                             "EARLIER_PART_NOT_RECORDED genesis-08-short (planned, no episodes/genesis-08-short.json: "
                             "finish, review and record it before building genesis-09-short)")
            (eo.EPISODES / "genesis-08-short.json").write_text("{}")
            self.assertIsNone(eo.earlier_part_open(later))
            self.assertIsNone(eo.earlier_part_open({"episode": "genesis-01-short", "part": 1}))
        finally:
            eo.PLANS, eo.EPISODES = saved
            shutil.rmtree(d)

    def test_the_workflow_checks_the_order_before_the_preflight(self):
        text = WORKFLOW.read_text()
        self.assertIn("migration/production/bible/episode_order.py \"$PLAN\"", text)
        self.assertLess(text.index("episode_order.py"), text.index("verify-preflight"))


if __name__ == "__main__":
    unittest.main()
