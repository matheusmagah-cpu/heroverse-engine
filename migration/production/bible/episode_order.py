#!/usr/bin/env python3
"""E112: one episode in flight. episode.yml runs one build at a time (concurrency group heroverse-episode), so a
later part dispatched while the part before it still needs a resume or regeneration queues that fix behind a whole
build. A part is built only when the part before it, if it was planned, is recorded in episodes/ (built, reviewed
at >= 9.5 and recorded by PR).

  episode_order.py PLAN     exit 0 when the plan may build now; else prints EARLIER_PART_NOT_RECORDED and exits 1

Kept out of episode_preflight.CODE on purpose: the order of the series is not something a preflight report vouches
for, and a change here must not make every committed preflight stale.
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PLANS = HERE / "plans"
EPISODES = HERE / "episodes"


def earlier_part_open(plan):
    """The refusal when the part before this plan's has a plan but no record; None when it may build."""
    part = plan.get("part")
    if not isinstance(part, int) or part < 2:
        return None
    prev = plan["episode"].replace(f"-{part:02d}-", f"-{part - 1:02d}-", 1)
    if prev == plan["episode"] or not (PLANS / f"{prev}.json").exists() or (EPISODES / f"{prev}.json").exists():
        return None
    return (f"EARLIER_PART_NOT_RECORDED {prev} (planned, no episodes/{prev}.json: finish, review and record it "
            f"before building {plan['episode']})")


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__)
    bad = earlier_part_open(json.loads(Path(argv[1]).read_text()))
    print(bad or "ORDER_OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
