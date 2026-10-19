#!/usr/bin/env python3
"""Run a HeroVerse job on a private Kaggle kernel (free GPU) and fetch its output.

The job script and its JSON payload are written into one kernel script, pushed
privately with GPU and internet enabled, polled until it finishes, and its
/kaggle/working output is downloaded. The API token comes only from the
KAGGLE_API_TOKEN environment variable (GitHub secret); it is never written to
disk inside the repository or printed.
usage: kaggle_run.py whoami
       kaggle_run.py run JOB_SCRIPT PAYLOAD_JSON SLUG OUT_DIR [TIMEOUT_MIN] [DATASETS_CSV] [gpu|cpu]
       kaggle_run.py collect SLUG OUT_DIR   (single status check; TIMEOUT_MIN 0 in run = launch only)
       kaggle_run.py dataset DIR SLUG TITLE   (private dataset in the owner's account: create or new version, wait until ready)

Owner authorization 2026-10-17: production code and files may be sent to the
owner's private Kaggle account (private datasets and private kernels only).
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def kaggle(*args, check=True):
    result = subprocess.run(["kaggle", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"KAGGLE_{args[0].upper()}_FAILED: {(result.stderr or result.stdout)[-600:]}")
    return result.stdout


def username():
    """Resolve the Kaggle user through the CLI (token from KAGGLE_API_TOKEN)."""
    out = kaggle("config", "view", check=False)
    for line in out.splitlines():
        if "username" in line.lower() and ":" in line:
            name = line.split(":", 1)[1].strip()
            if name and name.lower() not in ("none", "null"):
                return name
    listed = kaggle("kernels", "list", "--mine", "--page-size", "1", "--csv", check=False)
    rows = [r for r in listed.splitlines()[1:] if "/" in r]
    if rows:
        return rows[0].split(",")[0].split("/")[0]
    raise RuntimeError("KAGGLE_USERNAME_UNRESOLVED: " + (out + listed)[-400:].replace("KGAT_", "KGAT_***"))


def run(job_script, payload_path, slug, out_dir, timeout_min=110, datasets="", accelerator="gpu"):
    user = username()
    payload = json.loads(Path(payload_path).read_text())
    body = Path(job_script).read_text()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "job.py").write_text(f"PAYLOAD = {json.dumps(payload)!r}\n" + body)
        (d / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{user}/{slug}", "title": slug, "code_file": "job.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": accelerator == "gpu", "enable_internet": True,
            "dataset_sources": [f"{user}/{d}" if "/" not in d else d for d in datasets.split(",") if d],
            "competition_sources": [], "kernel_sources": []}))
        print(kaggle("kernels", "push", "-p", str(d)).strip()[-300:])
    if timeout_min in (0, "0"):
        return  # launch only; collect later with `collect`
    deadline = time.time() + float(timeout_min) * 60
    status = ""
    while time.time() < deadline:
        time.sleep(30)
        status = kaggle("kernels", "status", f"{user}/{slug}", check=False).lower()
        if any(s in status for s in ("complete", "error", "cancel")):
            break
    print("STATUS", status.strip()[-200:])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    kaggle("kernels", "output", f"{user}/{slug}", "-p", str(out_dir), check=False)
    for log in Path(out_dir).glob("*.log"):
        try:
            events = json.loads(log.read_text())
            text = "".join(e.get("data", "") for e in events)
        except ValueError:
            text = log.read_text()
        print("KERNEL_LOG_TAIL\n" + text[-3000:].replace("KGAT_", "KGAT_***"))
    if "complete" not in status:
        raise SystemExit("KAGGLE_KERNEL_NOT_COMPLETE")


def collect(slug, out_dir):
    """One status check (no waiting). Prints RUNNING, COMPLETE or ERROR; downloads output when finished."""
    user = username()
    status = kaggle("kernels", "status", f"{user}/{slug}", check=False).lower()
    state = "COMPLETE" if "complete" in status else "ERROR" if ("error" in status or "cancel" in status) else "RUNNING"
    if state != "RUNNING":
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        kaggle("kernels", "output", f"{user}/{slug}", "-p", str(out_dir), check=False)
        for log in Path(out_dir).glob("*.log"):
            try:
                text = "".join(e.get("data", "") for e in json.loads(log.read_text()))
            except ValueError:
                text = log.read_text()
            print("KERNEL_LOG_TAIL\n" + text[-3000:].replace("KGAT_", "KGAT_***"))
    print(state)
    return state


def dataset(directory, slug, title):
    user = username()
    (Path(directory) / "dataset-metadata.json").write_text(json.dumps(
        {"title": title, "id": f"{user}/{slug}", "licenses": [{"name": "other"}]}))
    status = kaggle("datasets", "status", f"{user}/{slug}", check=False).lower()
    if "ready" in status or "pending" in status:
        print(kaggle("datasets", "version", "-p", str(directory), "-m", "heroverse run", "--dir-mode", "tar", "-q").strip()[-300:])
    else:  # new datasets are private unless --public is given
        print(kaggle("datasets", "create", "-p", str(directory), "--dir-mode", "tar", "-q").strip()[-300:])
    for _ in range(60):
        time.sleep(20)
        status = kaggle("datasets", "status", f"{user}/{slug}", check=False).lower()
        if "ready" in status:
            print("DATASET_READY")
            return
        if "error" in status:
            raise SystemExit("KAGGLE_DATASET_ERROR " + status[-200:])
    raise SystemExit("KAGGLE_DATASET_NOT_READY")


if __name__ == "__main__":
    if sys.argv[1] == "whoami":
        print(json.dumps({"kaggle_user": username()}))
    elif sys.argv[1] == "collect":
        collect(*sys.argv[2:4])
    elif sys.argv[1] == "dataset":
        dataset(*sys.argv[2:5])
    elif sys.argv[1] == "run":
        run(*sys.argv[2:9])
    else:
        raise SystemExit(__doc__)
