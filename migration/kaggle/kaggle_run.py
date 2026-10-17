#!/usr/bin/env python3
"""Run a HeroVerse job on a private Kaggle kernel (free GPU) and fetch its output.

The job script and its JSON payload are written into one kernel script, pushed
privately with GPU and internet enabled, polled until it finishes, and its
/kaggle/working output is downloaded. The API token comes only from the
KAGGLE_API_TOKEN environment variable (GitHub secret); it is never written to
disk inside the repository or printed.
usage: kaggle_run.py whoami
       kaggle_run.py run JOB_SCRIPT PAYLOAD_JSON SLUG OUT_DIR [TIMEOUT_MIN]
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
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    name = api.get_config_value("username") or getattr(api, "config_values", {}).get("username")
    if not name:
        listed = kaggle("kernels", "list", "--mine", "--page-size", "1", "--csv")
        rows = [r for r in listed.splitlines()[1:] if r]
        name = rows[0].split(",")[0].split("/")[0] if rows else None
    if not name:
        raise RuntimeError("KAGGLE_USERNAME_UNRESOLVED")
    return name


def run(job_script, payload_path, slug, out_dir, timeout_min=110):
    user = username()
    payload = json.loads(Path(payload_path).read_text())
    body = Path(job_script).read_text()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "job.py").write_text(f"PAYLOAD = {json.dumps(payload)!r}\n" + body)
        (d / "kernel-metadata.json").write_text(json.dumps({
            "id": f"{user}/{slug}", "title": slug, "code_file": "job.py", "language": "python",
            "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
            "dataset_sources": [], "competition_sources": [], "kernel_sources": []}))
        print(kaggle("kernels", "push", "-p", str(d)).strip()[-300:])
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
    if "complete" not in status:
        raise SystemExit("KAGGLE_KERNEL_NOT_COMPLETE")


if __name__ == "__main__":
    if sys.argv[1] == "whoami":
        print(json.dumps({"kaggle_user": username()}))
    elif sys.argv[1] == "run":
        run(*sys.argv[2:7])
    else:
        raise SystemExit(__doc__)
