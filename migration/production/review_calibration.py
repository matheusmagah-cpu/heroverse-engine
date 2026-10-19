#!/usr/bin/env python3
"""Calibration of the automatic review with cases whose answer is known before they are reviewed.

From a QA-PASS render, a 180 s excerpt (the control) and copies with one deliberate defect each are made with
ffmpeg. Every case goes through the two signals the final decision uses: the whole-file scan (signal_scan.py)
and the watched review (long_review.watch, the same prompt, rubric and free models). The control is reviewed
twice (consistency). Expected answers are fixed in CASES before any review runs.

Measured: false rejections (control fails), false approvals (a defective case passes every signal), which
signal caught which defect, score spread between the two control runs. A defect only the frame-by-frame scan
catches is evidence that the review's 0.5 fps sampling misses it.
usage: review_calibration.py RENDER_MP4 WORK_DIR OUT_JSON [TITLE] [MODEL]
       review_calibration.py qualify OUT_JSON CALIBRATION_JSON...   (backup reviewer verdicts, see qualification())
A backup reviewer is QUALIFIED only when, on the renders of at least two different pilots, every defect case is FAIL,
every control is PASS, and its watched-review status equals the designated reviewer's on every case of the same
render. Any error, missing case or single miss is NOT_QUALIFIED. Qualification never changes the gate by itself.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import long_review as lr  # noqa: E402
import shorts_review as sr  # noqa: E402
import signal_scan as ss  # noqa: E402

VERSION = "review-calibration-v1"
EXCERPT = (30, 210)  # seconds of the render: after the title, voice, captions, figure and backgrounds present
# case -> (ffmpeg filters on the excerpt, expected verdict, rubric items expected to drop)
CASES = {
    "control": ([], "PASS", []),
    "control_repeat": ([], "PASS", []),
    "av_desync_1500ms": (["-af", "adelay=1500|1500,atrim=0:180"], "FAIL", ["captions_readable_and_synced", "audio_clarity_and_mix"]),
    "audio_dropouts": (["-af", "volume=enable='between(t,40,44)+between(t,95,99)+between(t,150,154)':volume=0"], "FAIL",
                       ["audio_clarity_and_mix"]),
    "degraded_picture": (["-vf", "scale=320:-2,boxblur=2:1,scale=1920:1080:flags=neighbor"], "FAIL", ["picture_quality"]),
    "black_flash_800ms": (["-vf", "drawbox=enable='between(t,61,61.8)':c=black:t=fill"], "FAIL", ["picture_quality"]),
    "frozen_60s": (["-vf", "trim=0:60,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=60,trim=0:120,"
                    "setpts=PTS-STARTPTS[a];[0:v]trim=120:180,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0"],
                   "FAIL", ["pacing_and_visual_variety"]),
}
GAP_S = 40  # free-tier tokens per minute between whole-video reviews


def make(render, work, name, filters):
    out = Path(work) / f"{name}.mp4"
    base = Path(work) / "excerpt.mp4"
    if not base.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(EXCERPT[0]), "-i", render, "-t", str(EXCERPT[1] - EXCERPT[0]),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(base)], check=True)
    if not filters:
        return base
    if filters[0] == "-vf" and "concat" in filters[1]:
        args = ["-filter_complex", "[0:v]" + filters[1] + "[v]", "-map", "[v]", "-map", "0:a"]
    else:
        args = filters
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *args, "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    return out


def review(path, title, key, model=None):
    f = sr.upload(str(path), key)
    try:
        return lr.watch(f, title, key, (model,) if model else lr.REVIEW_MODELS)
    finally:
        try:
            sr.request(sr.BASE + "/v1beta/" + f["name"], key, method="DELETE")
        except Exception:
            pass


def main(render, work, out_json, title="Morning Prayer", model=None):
    key = os.environ["HERO_GEMINI_API_KEY"]
    Path(work).mkdir(parents=True, exist_ok=True)
    rows = {}
    for i, (name, (filters, expected, items)) in enumerate(CASES.items()):
        path = make(render, work, name, filters)
        scan = ss.scan(str(path))
        if i:
            time.sleep(GAP_S)
        try:
            r = review(path, title, key, model)
            rev = {"status": r["status"], **{k: r.get(k) for k in (*lr.RUBRIC, "overall")}, "issues": r.get("issues", [])[:6],
                   "model": r.get("model")}
        except Exception as e:
            rev = {"status": "ERROR", "error": f"{type(e).__name__}: {e}"[:200]}
        scan_fail = scan["status"] == "FAIL"
        review_fail = rev["status"] == "FAIL"
        if rev["status"] == "ERROR":
            verdict = "FAIL" if scan_fail else "UNKNOWN"
        else:
            verdict = "FAIL" if scan_fail or review_fail else "PASS"
        rows[name] = {"expected": expected, "verdict": verdict, "correct": verdict == expected,
                      "caught_by": [s for s, f in (("scan", scan_fail), ("review", review_fail)) if f],
                      "expected_items_dropped": {k: rev.get(k) for k in items},
                      "scan": {k: v["longest_s"] for k, v in scan["rows"].items()}, "review": rev}
        print(name, expected, verdict, rows[name]["caught_by"], flush=True)
    defects = [r for n, r in rows.items() if r["expected"] == "FAIL"]
    controls = [r for n, r in rows.items() if r["expected"] == "PASS"]
    c = [r["review"] for r in controls if r["review"]["status"] != "ERROR"]
    spread = (max(abs(c[0][k] - c[1][k]) for k in (*lr.RUBRIC, "overall") if isinstance(c[0].get(k), (int, float))
                  and isinstance(c[1].get(k), (int, float))) if len(c) == 2 else None)
    summary = {"false_rejections": sum(r["verdict"] == "FAIL" for r in controls),
               "false_approvals": sum(r["verdict"] == "PASS" for r in defects),
               "unknown": sum(r["verdict"] == "UNKNOWN" for r in rows.values()),
               "defects_caught_by_review": sum("review" in r["caught_by"] for r in defects),
               "defects_caught_only_by_scan": sum(r["caught_by"] == ["scan"] for r in defects),
               "defects": len(defects), "controls": len(controls), "control_max_score_spread": spread}
    out = {"version": VERSION, "at": datetime.now(timezone.utc).isoformat(), "excerpt_s": EXCERPT,
           "render": Path(render).name, "model": model or lr.REVIEW_MODELS[0], "summary": summary, "cases": rows,
           "limits": "one excerpt of one render; small n; synthetic defects stand for, not equal, real render faults"}
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)  # first run of a model: the evidence folder may not exist
    Path(out_json).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(summary))


def qualification(runs, reference=None):
    """runs: calibration outputs (any models, any renders). reference: the designated reviewer.
    Returns {model: {"verdict": "QUALIFIED" | "NOT_QUALIFIED", "renders": [...], "reasons": [...]}} for every other model."""
    reference = reference or lr.REVIEW_MODELS[0]
    ref = {r["render"]: r for r in runs if r.get("model") == reference}
    out = {}
    for model in sorted({r.get("model") for r in runs} - {reference, None}):
        reasons, renders = [], []
        for run in (r for r in runs if r.get("model") == model):
            render = run["render"]
            renders.append(render)
            base = ref.get(render)
            if base is None:
                reasons.append(f"{render}: NO_REFERENCE_RUN")
                continue
            for name in CASES:
                case, rcase = run["cases"].get(name), base["cases"].get(name)
                if case is None or rcase is None:
                    reasons.append(f"{render}/{name}: MISSING_CASE")
                    continue
                status, rstatus = case["review"].get("status"), rcase["review"].get("status")
                if status not in ("PASS", "FAIL") or rstatus not in ("PASS", "FAIL"):
                    reasons.append(f"{render}/{name}: REVIEW_{status}_REFERENCE_{rstatus}")
                    continue
                if case["expected"] == "FAIL" and case["verdict"] != "FAIL":
                    reasons.append(f"{render}/{name}: FALSE_APPROVAL")
                if case["expected"] == "PASS" and case["verdict"] != "PASS":
                    reasons.append(f"{render}/{name}: FALSE_REJECTION")
                if status != rstatus:
                    reasons.append(f"{render}/{name}: DIFFERS_FROM_REFERENCE {status} != {rstatus}")
        if len(set(renders)) < 2:
            reasons.append(f"FEW_RENDERS {len(set(renders))} (two different pilots required)")
        out[model] = {"verdict": "NOT_QUALIFIED" if reasons else "QUALIFIED", "renders": sorted(set(renders)), "reasons": reasons}
    return out


if __name__ == "__main__":
    if sys.argv[1] == "qualify":
        result = qualification([json.loads(Path(f).read_text()) for f in sys.argv[3:]])
        Path(sys.argv[2]).write_text(json.dumps(result, indent=1) + "\n")
        print(json.dumps({m: v["verdict"] for m, v in result.items()}))
    else:
        main(*sys.argv[1:6])
