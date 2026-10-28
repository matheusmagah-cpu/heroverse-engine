#!/usr/bin/env python3
"""Bridge qualified Bible plans to the existing request/claim dispatcher. No generation or approval.

Called only by the existing heartbeat. Reuses migration/requests; no second ledger or scheduler.
Completed/uncertain requests and evidence branches require reconciliation, never an automatic replay.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_discovery import discover

ROOT = Path(__file__).resolve().parents[2]
REPO = "matheusmagah-cpu/heroverse-engine"
PLAN_DIR = "migration/production/bible/plans"


def workflow(path):
    return "long-build.yml" if path.endswith("-long.json") else "episode.yml"


def decision(path, refusal, runs, subjects, requests):
    if refusal:
        return "blocked:" + refusal
    if any(r["status"] != "completed" for r in runs):
        return "wait:active_build"
    if Path(path).stem in subjects:
        return "wait:build_evidence"
    matching = [r for r in requests if r.get("workflow") == workflow(path)
                and (r.get("inputs") or {}).get("plan") == path]
    if any(r["location"] != "pending" for r in matching):
        return "wait:existing_request"
    if len(matching) > 1:
        return "wait:duplicate_pending"
    return "submit_pending" if matching else "queue"


def command(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=100, check=True).stdout


def active_pages(pages):
    if not isinstance(pages, list) or not pages:
        raise ValueError("active run inventory missing")
    rows = []
    totals = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list):
            raise ValueError("active run page malformed")
        total = page.get("total_count")
        if type(total) is not int or total < 0:
            raise ValueError("active run count malformed")
        totals.add(total)
        for row in page["workflow_runs"]:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("status"), str):
                raise ValueError("active run row malformed")
            rows.append(row)
    if len(totals) != 1 or len(rows) != next(iter(totals)):
        raise ValueError("active run inventory incomplete or moved")
    return rows


def readiness(path):
    long = workflow(path) == "long-build.yml"
    commands = [[sys.executable, "-I", "-B", f"migration/production/bible/{'long_plan_check' if long else 'plan_check'}.py", path, "--strict"],
                [sys.executable, "-I", "-B", "migration/production/bible/episode_build.py", "verify-preflight", path]]
    if long:
        commands += [[sys.executable, "-I", "-B", "migration/production/bible/long_handoff.py", "inputs", path]]
    else:
        commands += [[sys.executable, "-I", "-B", "migration/production/bible/episode_order.py", path]]
    for args in commands:
        r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=100)
        if r.returncode:
            # Preserve the real refusal, not PASS inferred from missing output.
            return (r.stdout + r.stderr).strip()[:2000] or f"check exit {r.returncode}"
    return None


def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("production bridge requires the owner repository main")
    command(["git", "pull", "--rebase", "-q", "origin", "main"])
    if (ROOT / "migration/ops/RENDER_HOLD").exists():
        print("Render hold preserved")
        return
    reqs = []
    for p in sorted((ROOT / "migration/requests").rglob("*.json")):
        if p.is_symlink():
            raise ValueError("request symlink refused")
        r = json.loads(p.read_text())
        r["location"] = "pending" if p.parent.name == "requests" else p.parent.name
        reqs.append(r)
    ledger = json.loads((ROOT / "migration/publish/ledger.json").read_text())["entries"]
    arcs = json.loads((ROOT / "migration/production/bible/arcs.json").read_text())["arcs"]
    pilots = {a["id"] + "-long": (a.get("long") or {}).get("pilot") for a in arcs}
    paths = sorted((ROOT / PLAN_DIR).glob("*.json"), key=lambda p: (not p.stem.endswith("-long"), p.name))
    rows, selected = [], None
    remote = None
    for p in paths:
        if p.is_symlink() or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", p.stem):
            raise ValueError("plan path refused")
        plan = json.loads(p.read_text())
        if plan.get("episode") != p.stem:
            raise ValueError("plan identity mismatch")
        prefix = (pilots.get(p.stem) or "") + ":" if p.stem.endswith("-long") else f"bible:{p.stem}:"
        if prefix != ":" and any(k.startswith(prefix) and v.get("video_id") for k, v in ledger.items()):
            continue  # Existing identity is reconciled by publication, never rebuilt here.
        if (ROOT / "migration/production/bible/episodes" / p.name).exists():
            rows.append({"subject": p.stem, "state": "wait:episode_record"})
            continue
        path = str(p.relative_to(ROOT))
        refusal = readiness(path)
        if refusal:
            rows.append({"subject": p.stem, "state": "blocked", "reason": refusal})
            continue
        if remote is None:
            runs = []
            for state in ("queued", "in_progress", "waiting", "pending", "requested"):
                pages = json.loads(command(["gh", "api", "--method", "GET", "--paginate", "--slurp",
                                            f"repos/{REPO}/actions/runs?per_page=100&status={state}"]))
                runs += active_pages(pages)
            # Evidence inventory is read in full; malformed responses fail, never become an empty queue.
            pages = json.loads(command(["gh", "api", "--method", "GET", "--paginate", "--slurp",
                                        f"repos/{REPO}/branches?per_page=100"]))
            subjects = [b["subject"] for b in discover(pages)]
            remote = (runs, subjects)
        active = [r for r in remote[0] if r["path"] in (".github/workflows/episode.yml", ".github/workflows/long-build.yml",
                                                       ".github/workflows/shot-probe.yml")]
        state = decision(path, None, active, remote[1], reqs)
        rows.append({"subject": p.stem, "state": state})
        if state in ("queue", "submit_pending"):
            selected = (p, path, state)
            break  # One durable handoff, not a fan-out of builds.
    print(json.dumps({"handoffs": rows, "approval": False}, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## Qualified production handoff\n\n```json\n" + json.dumps(rows, indent=2) + "\n```\n")
    if not selected:
        return
    p, path, state = selected
    if state == "queue":
        name = f"production-build-{p.stem}-{hashlib.sha256(p.read_bytes()).hexdigest()[:16]}.json"
        target = ROOT / "migration/requests" / name
        # Exclusive creation. No overwrite or replay if another operation has already reserved this identity.
        with target.open("x") as f:
            json.dump({"workflow": workflow(path), "inputs": {"plan": path}}, f, indent=1)
            f.write("\n")
        command(["git", "add", "--", str(target.relative_to(ROOT))])
        command(["git", "commit", "-qm", f"Queue qualified production handoff {p.stem}"])
        command(["git", "push", "-q", "origin", "HEAD:main"])
    # The caller now invokes requests.yml, whose durable claim must precede the actual provider POST.
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("ready=true\n")


if __name__ == "__main__":
    main()
