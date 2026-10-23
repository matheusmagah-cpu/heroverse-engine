#!/usr/bin/env python3
"""E58 root cause: the designated reviewer does not answer our free key at all (reviewer probe 2026-10-23T22:57:
a 5-token text call timed out on gemini-3.8-flash; gemini-3.6-flash and gemini-3.5-flash-lite answered in < 1 s).

A candidate reviewer is qualified only if, on renders the designated reviewer already judged, it gives
- the same PASS/FAIL on every render,
- a mean absolute difference of the overall score <= 0.6, and
- a mean signed difference <= +0.5 (never more lenient than the reviewer it replaces).
The rule is fixed before the run. Usage: reviewer_calibration.py CANDIDATE OUT_JSON PILOT=VIDEO|youtube:ID [...]
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_review as lr  # noqa: E402

MAX_MEAN_ABS = 0.6
MAX_MEAN_SIGNED = 0.5


def qualify(rows):
    if not rows or any(r.get("error") for r in rows):
        return {"qualified": False, "reason": "INCOMPLETE"}
    same = all(r["candidate_status"] == r["designated_status"] for r in rows)
    diffs = [r["candidate_overall"] - r["designated_overall"] for r in rows]
    mean_abs, mean_signed = sum(abs(d) for d in diffs) / len(diffs), sum(diffs) / len(diffs)
    ok = same and mean_abs <= MAX_MEAN_ABS and mean_signed <= MAX_MEAN_SIGNED
    return {"qualified": ok, "same_verdict_everywhere": same, "mean_abs_diff": round(mean_abs, 2),
            "mean_signed_diff": round(mean_signed, 2), "rule": {"max_mean_abs": MAX_MEAN_ABS, "max_mean_signed": MAX_MEAN_SIGNED}}


def main(candidate, out, *pairs):
    key = os.environ["HERO_GEMINI_API_KEY"]
    rows = []
    for pair in pairs:
        pilot, video = pair.split("=", 1)
        d = Path("migration/production") / pilot
        script = json.loads((d / "script.json").read_text())
        old = json.loads((d / "out" / "review.json").read_text())["watched_review"]
        row = {"pilot": pilot, "designated_model": old["model"], "designated_status": old["status"],
               "designated_overall": old["overall"]}
        try:
            if video.startswith("youtube:"):  # a published render: its public YouTube copy, no upload
                row["source"] = video
                new = lr.watch({"uri": "https://www.youtube.com/watch?v=" + video.split(":", 1)[1]},
                               script["working_title"], key, models=(candidate,))
            else:
                row["source"] = "release"
                file = lr.sr.upload(video, key)
                try:
                    new = lr.watch(file, script["working_title"], key, models=(candidate,))
                finally:
                    try:
                        lr.sr.request(lr.sr.BASE + "/v1beta/" + file["name"], key, method="DELETE")
                    except Exception:  # noqa: BLE001
                        pass
            row.update(candidate_model=new["model"], candidate_status=new["status"], candidate_overall=new["overall"],
                       candidate_items={k: new.get(k) for k in lr.RUBRIC})
        except Exception as e:  # noqa: BLE001
            row["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        rows.append(row)
        print(json.dumps(row))
    result = {"candidate": candidate, "rows": rows, **qualify(rows)}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main(*sys.argv[1:])
