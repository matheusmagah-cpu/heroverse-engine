#!/usr/bin/env python3
"""E244: the bytes of a Buzzy clip reach the engine's release only through buzzy-ingest.yml (this session cannot upload
binaries). Everything here is decided from the committed ledger, never from the caller's words:

  buzzy_ingest.py asset EPISODE SHOT TASK_ID URL   prints "<asset name> <sha256>" for pinned_asset.sh mirror, or refuses

Refused: a URL that is not https on the Buzzy file service (BUZZY_URL_REFUSED), a task id with no ledger call or whose
`episode_shot` is not "<EPISODE> <SHOT>" (BUZZY_NOT_FOR_SHOT), a call with no output_sha256 (BUZZY_LEDGER_INCOMPLETE).
The download itself is accepted only when it hashes to that ledger sha256 (pinned_asset.sh mirror, fail closed)."""
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[3]
LEDGER = REPO / "migration" / "evidence" / "buzzy" / "ledger.json"
URL = re.compile(r"https://res-prod\.buzzy\.now/file-service/[0-9a-f-]{36}\.mp4")


def asset(episode, shot, task_id, url, ledger=None):
    if not URL.fullmatch(str(url)):
        raise SystemExit(f"BUZZY_URL_REFUSED {url!r}")
    calls = json.loads(Path(ledger or LEDGER).read_text()).get("calls") or []
    call = next((c for c in calls if isinstance(c, dict) and c.get("task_id") == task_id), None)
    if call is None or call.get("episode_shot") != f"{episode} {shot}":
        raise SystemExit(f"BUZZY_NOT_FOR_SHOT {task_id} ({episode} {shot})")
    sha = call.get("output_sha256")
    if not (isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)):
        raise SystemExit(f"BUZZY_LEDGER_INCOMPLETE {task_id} (output_sha256)")
    return f"shot-{episode}-{shot}-sha256-{sha}.mp4", sha


if __name__ == "__main__":
    if len(sys.argv) != 6 or sys.argv[1] != "asset":
        raise SystemExit(__doc__)
    print(*asset(*sys.argv[2:]))
