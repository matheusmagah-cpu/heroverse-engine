#!/usr/bin/env python3
"""The bridge between cloud agents and the ChatGPT runner on the owner's PC (Desktop Commander).

Cloud side (in the repository):
  bridge.py job STILL_RECORD SUBJECT REF_RECORD... [--ref-commit SHA]
      prints a job: the still's prompt behind an identity line for SUBJECT, and each APPROVED reference still by its
      public raw URL at a commit and its sha256 (the runner downloads and checks them). The agent writes it to
      C:\\HeroVerse\\chatgpt-runner\\jobs\\<id>.json (write_file) and starts `runner.py job jobs\\<id>.json`
      (start_process; read_process_output until IMAGE_SAVED or a stop line).

PC side (deployed next to runner.py):
  bridge.py push JOB_ID
      sends out\\<id>\\<id>.<ext> and its record to a new branch claude/chatgpt-image-<id> under
      migration/production/bible/stills/candidates/ through the GitHub API (gh, logged in once by the owner); without
      gh the agent still sees the image with Desktop Commander's read_file and reviews it there.
"""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = "matheusmagah-cpu/heroverse-engine"
RAW = "https://raw.githubusercontent.com/" + REPO + "/{commit}/{path}"
CANDIDATES = "migration/production/bible/stills/candidates/"
IDENTITY = ("The attached images are approved stills of {subject}: keep the face, skin tone, eyes and hair exactly as "
            "in them, and the period wardrobe of the scene below. The scene: ")


def root():
    return Path(__file__).resolve().parents[3]


def make_job(still_record, subject, ref_records, commit="main", base=None):
    base = base or root()
    still = json.loads((base / still_record).read_text())
    refs, problems = [], []
    for r in ref_records:
        rec = json.loads((base / r).read_text())
        if rec.get("status") != "APPROVED":
            problems.append(f"REF_NOT_APPROVED {rec.get('id')}")
            continue
        data = (base / rec["repo_path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != rec["sha256"]:
            problems.append(f"REF_SHA256_MISMATCH {rec.get('id')}")
            continue
        refs.append({"name": Path(rec["repo_path"]).name, "sha256": rec["sha256"],
                     "url": RAW.format(commit=commit, path=rec["repo_path"]), "record": rec["id"]})
    if problems:
        raise SystemExit("; ".join(problems))
    return {"id": f"{still['id']}-chatgpt-1", "still": still["id"], "subject": subject,
            "prompt": IDENTITY.format(subject=subject) + still["prompt"], "refs": refs}


def gh(*args, data=None):
    p = subprocess.run(["gh", *args], input=data, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"GH_FAILED {' '.join(args[:2])}: {(p.stderr or p.stdout)[:300]}")
    return p.stdout


def push(job_id, out_root=None):
    if not shutil.which("gh") or subprocess.run(["gh", "auth", "status"], capture_output=True).returncode:
        raise SystemExit("GH_NOT_LOGGED_IN: the owner runs once: gh auth login --web --git-protocol https")
    out = Path(out_root or HERE / "out") / job_id
    rec = json.loads((out / f"{job_id}.json").read_text(encoding="utf-8"))
    branch = f"claude/chatgpt-image-{job_id}"
    main_sha = gh("api", f"repos/{REPO}/git/ref/heads/main", "--jq", ".object.sha").strip()
    gh("api", "-X", "POST", f"repos/{REPO}/git/refs", "-f", f"ref=refs/heads/{branch}", "-f", f"sha={main_sha}")
    for name in (rec["file"], f"{job_id}.json"):
        body = json.dumps({"message": f"ChatGPT image candidate {job_id} (DRAFT for Claude's still review)",
                           "branch": branch, "content": base64.b64encode((out / name).read_bytes()).decode()})
        gh("api", "-X", "PUT", f"repos/{REPO}/contents/{CANDIDATES}{name}", "--input", "-", data=body)
    print(f"PUSHED {branch}")
    return branch


def main(argv):
    if len(argv) >= 5 and argv[1] == "job":
        commit = "main"
        if "--ref-commit" in argv:
            i = argv.index("--ref-commit")
            commit, argv = argv[i + 1], argv[:i] + argv[i + 2:]
        print(json.dumps(make_job(argv[2], argv[3], argv[4:], commit), indent=1))
        return 0
    if len(argv) == 3 and argv[1] == "push":
        push(argv[2])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
