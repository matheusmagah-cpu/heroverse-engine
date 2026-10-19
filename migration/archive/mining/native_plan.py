#!/usr/bin/env python3
"""Plan native acquisitions without changing the ledger or making provider calls.

usage: native_plan.py LEDGER MEASURED_JSON N
Print up to N semicolon-separated VIDEO:START:END windows (60 seconds each).
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

WINDOW_SECONDS = 60
MIN_START_SPACING = 120
MAX_WINDOWS = 4
ROLE_ORDER = {"winner": 0, "weak_contrast": 1, "latest": 2}


def candidate_starts(seconds):
    """Fixed grid including the opening and last full window, rounded down.

    Use at most four starts; shorter videos get fewer so starts stay at least
    120 seconds apart. The grid is independent of the requested batch size.
    """
    last = seconds - WINDOW_SECONDS
    if last < 0:
        return []
    count = min(MAX_WINDOWS, last // MIN_START_SPACING + 1)
    if count == 1:
        return [0]
    return [i * last // (count - 1) for i in range(count)]


def plan(ledger, measured, n, stderr=None):
    """Return fresh windows in role/video order, then ascending start order.

    Count distinct (start, end) ledger windows, regardless of status. Fixed-grid
    candidates must be >=120 seconds start-to-start from every existing or
    newly planned window. Existing non-grid windows consume the four-window
    allowance too; we never move the grid to fill gaps. Unknown roles rank
    after latest. Missing/null/invalid durations are skipped with a reason.
    """
    if stderr is None:
        stderr = sys.stderr
    if n < 0:
        raise ValueError("N must be nonnegative")
    if n == 0:
        return []
    used = {}
    for claim in ledger.get("claims", []):
        used.setdefault(claim["video_id"], set()).add(
            (claim["start_seconds"], claim["end_seconds"]))
    videos = sorted(measured.get("videos", []),
                    key=lambda v: (ROLE_ORDER.get(v.get("role"), 3), v["video_id"]))
    picks = []
    for video in videos:
        vid = video["video_id"]
        windows = used.setdefault(vid, set())
        if len(windows) >= MAX_WINDOWS:
            continue
        minutes = video.get("minutes")
        if (isinstance(minutes, bool) or not isinstance(minutes, (int, float))
                or not math.isfinite(minutes) or minutes <= 0
                or not math.isfinite(minutes * 60)):
            print(f"SKIP {vid}: missing/null or invalid minutes duration", file=stderr)
            continue
        seconds = math.floor(minutes * 60)
        if seconds < WINDOW_SECONDS:
            print(f"SKIP {vid}: duration is shorter than 60 seconds", file=stderr)
            continue
        for start in candidate_starts(seconds):
            end = start + WINDOW_SECONDS
            if any(abs(start - previous_start) < MIN_START_SPACING
                   for previous_start, _ in windows):
                continue
            windows.add((start, end))
            picks.append(f"{vid}:{start}:{end}")
            if len(picks) == n:
                return picks
            if len(windows) >= MAX_WINDOWS:
                break
    return picks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("measured_json", type=Path)
    parser.add_argument("n", type=int)
    args = parser.parse_args(argv)
    if args.n < 0:
        parser.error("N must be nonnegative")
    ledger = json.loads(args.ledger.read_text())
    measured = json.loads(args.measured_json.read_text())
    print(";".join(plan(ledger, measured, args.n)))


if __name__ == "__main__":
    main()
