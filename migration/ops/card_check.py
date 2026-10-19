#!/usr/bin/env python3
"""Lint of a Dot script card (issue body) before Claude sends it and on every Dot PR: the card must be executable
as written and consistent with the engine's rules.
  - an ```allowed block;
  - publish_at at a slot (night 00:00, morning 10:00 UTC);
  - exactly one Short slot: night pilot of day D at D 14:00, morning pilot at D 20:00 (OPERATIONS.md);
  - DEADLINE no later than publish_at - 72 h (the content runway alerts a slot without a script < 72 h before);
  - the frozen QA criteria SHA-256 of the current pilots.
Code cards: every line of the ```interfaces block ("path/to/file.py: exact text") must appear verbatim in that file of
the repository, so a card never names a function, signature or data value that does not exist as written.
usage: card_check.py ISSUE_BODY_FILE [REPO_ROOT]   (prints problems; exit 0 when the card is clean)
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys

FROZEN_QA = "49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d"
RUNWAY = timedelta(hours=72)


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def interfaces(body, root="."):
    m = re.search(r"```interfaces\s*\n(.*?)```", body, re.S)
    if not m:
        return []
    p = []
    for line in (l.strip() for l in m.group(1).splitlines()):
        if not line or line.startswith("#"):
            continue
        path, _, text = line.partition(": ")
        f = Path(root) / path
        if not f.exists():
            p.append(f"INTERFACE_FILE_MISSING {path}")
        elif text not in f.read_text():
            p.append(f"INTERFACE_NOT_IN_FILE {path}: {text}")
    return p


def check(body, root="."):
    code = interfaces(body, root)
    pub = re.search(r"`publish_at`\s*`(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)`", body)
    if not pub:
        return code  # not a script card
    p, at = [], ts(pub.group(1))
    if not re.search(r"```allowed\s*\n.*?```", body, re.S):
        p.append("NO_ALLOWED_BLOCK")
    if (at.hour, at.minute) not in ((0, 0), (10, 0)):
        p.append(f"PUBLISH_AT_NOT_A_SLOT {pub.group(1)}")
    slots = re.search(r"`shorts_slots`\s*`\[(.*?)\]`", body)
    want = at.replace(hour=14 if at.hour == 0 else 20, minute=0)
    got = re.findall(r'"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"', slots.group(1)) if slots else []
    if [ts(g) for g in got] != [want]:
        p.append(f"SHORT_SLOT {got} (must be exactly [\"{want:%Y-%m-%dT%H:%M:%SZ}\"])")
    dl = re.search(r"\*\*DEADLINE \(UTC\)\*\*\s*[—-]\s*(\d{4}-\d\d-\d\d) (\d\d:\d\d)", body)
    if not dl:
        p.append("NO_DEADLINE")
    else:
        d = datetime.fromisoformat(f"{dl.group(1)}T{dl.group(2)}:00+00:00")
        if d > at - RUNWAY:
            p.append(f"DEADLINE_AFTER_RUNWAY {d:%Y-%m-%d %H:%M} (latest {at - RUNWAY:%Y-%m-%d %H:%M}: publish_at - 72 h)")
    if FROZEN_QA not in body:
        p.append("FROZEN_QA_SHA_MISSING")
    return p + code


if __name__ == "__main__":
    problems = check(open(sys.argv[1]).read(), sys.argv[2] if len(sys.argv) > 2 else ".")
    print("\n".join(problems) or "CARD_OK")
    sys.exit(1 if problems else 0)
