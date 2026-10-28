#!/usr/bin/env python3
"""Read-only inventory of build evidence outside main; never a review or approval.

The existing supervisor consumes these branch/commit/run identities and validates
the report, current plan, QA and actual media before any review. Retained branches
may already be reviewed: discovery deliberately does not call them pending.
"""
import json
import os
import re
import subprocess
import sys

REPO = "matheusmagah-cpu/heroverse-engine"
BRANCH = re.compile(r"claude/(long|episode)-([a-z0-9]+(?:-[a-z0-9]+)*)-([1-9][0-9]*)$")
SHA = re.compile(r"[0-9a-f]{40}$")


def discover(pages):
    if not isinstance(pages, list) or any(not isinstance(p, list) for p in pages):
        raise ValueError("BRANCH_PAGES_INVALID")
    found = {}
    for page in pages:
        for item in page:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ValueError("BRANCH_ROW_INVALID")
            match = BRANCH.fullmatch(item["name"])
            if not match:
                continue
            sha = (item.get("commit") or {}).get("sha")
            if not isinstance(sha, str) or not SHA.fullmatch(sha):
                raise ValueError("BRANCH_SHA_INVALID")
            if item["name"] in found and found[item["name"]]["commit"] != sha:
                raise ValueError("BRANCH_MOVED_DURING_DISCOVERY")
            kind, subject, run = match.groups()
            found[item["name"]] = {
                "branch": item["name"], "commit": sha, "kind": kind,
                "subject": subject, "build_run_id": run,
                "report": f"migration/evidence/episodes/{subject}/report-{run}.json",
                "state": "DISCOVERED_NOT_VALIDATED",
            }
    return sorted(found.values(), key=lambda r: (int(r["build_run_id"]), r["branch"]))


def main():
    if os.environ.get("GITHUB_REPOSITORY", REPO) != REPO:
        raise ValueError("REPOSITORY_REFUSED")
    # Explicit GET, pagination and bounded execution; no dispatch or credentials in output.
    result = subprocess.run(
        ["gh", "api", "--method", "GET", "--paginate", "--slurp",
         f"repos/{REPO}/branches?per_page=100"],
        capture_output=True, text=True, timeout=90, check=True,
    )
    rows = discover(json.loads(result.stdout))
    print(json.dumps({"state": "INVENTORY_ONLY", "branches": rows}, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Build evidence discovery\n\n")
            f.write("Inventory only, not pending status, QA, review or approval. "
                    "The designated supervisor must reconcile existing reviews and current inputs.\n\n")
            for row in rows:
                f.write(f"- `{row['branch']}` at `{row['commit']}`; build `{row['build_run_id']}`\n")
            if not rows:
                f.write("No matching build evidence branches found.\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, TypeError, AttributeError, OSError, subprocess.SubprocessError):
        print("REVIEW_DISCOVERY_FAILED: inventory unknown; do not infer an empty queue", file=sys.stderr)
        sys.exit(1)
