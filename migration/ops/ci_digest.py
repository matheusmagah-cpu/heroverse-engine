#!/usr/bin/env python3
"""E263: ci_digest.py RUN_ID prints run status/conclusion, each job's conclusion and, for failed jobs only,
the last 40 log lines. Uses `gh api` (REST) with gh's own auth. Avoids reading full CI logs."""
import json
import subprocess
import sys

REPO = "matheusmagah-cpu/heroverse-engine"
TAIL = 40


def gh(path, raw=False):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"gh api {path}: {p.stderr.strip()[:300]}")
    return p.stdout if raw else json.loads(p.stdout)


def digest(run_id, api=gh):
    run = api(f"repos/{REPO}/actions/runs/{run_id}")
    lines = [f"run {run_id}: status={run.get('status')} conclusion={run.get('conclusion')}"]
    jobs = api(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100").get("jobs", [])
    for j in jobs:
        lines.append(f"  job {j['name']}: {j.get('conclusion') or j.get('status')}")
    for j in jobs:
        if j.get("conclusion") == "failure":
            log = api(f"repos/{REPO}/actions/jobs/{j['id']}/logs", raw=True).splitlines()
            lines.append(f"--- last {TAIL} lines of {j['name']} ---")
            lines.extend(log[-TAIL:])
    return "\n".join(lines)


def main(argv):
    if len(argv) != 1 or not argv[0].isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    try:
        print(digest(argv[0]))
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
