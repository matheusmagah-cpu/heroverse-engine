#!/usr/bin/env python3
"""Final pre-publication decision of a rendered long video: PASS, FAIL or UNKNOWN.

Only PASS makes a new render eligible for automatic publication. It adds no new
measurement: it reads the evidence the existing controls already wrote for THIS
file and checks that every dimension is covered.

Evidence and method (each item names where it comes from):
- qa      out/qa.json, frozen criteria (qa_pilot.py): deterministic tools over the
          WHOLE file (ffmpeg decode/loudness, ASR word error vs script, caption
          file vs detected speech, render manifest).
- review  out/review.json (long_review.py): a free Gemini model watching the file
          with audio. Pictures are SAMPLED at 0.5 frames/s, low resolution: it can
          miss a defect shorter than ~2 s. Independent of qa (different instrument).
- score   out/review.json scorecard hard rows (same miner as the reference winners).
- preflight  publish/preflight.py (YouTube limits, thumbnail, schedule, captions).
- binding qa, manifest and review name the same output_sha256; the QA criteria file
          is the frozen one; when the video file is given, its hash is recomputed.

Rules: an item that failed -> FAIL. An item whose evidence is missing, errored
(timeout, quota, provider error) or belongs to another file -> UNKNOWN, never a
pass. Informative rows (winners' bands, "beat the reference") are reported and
never decide.

usage: prepublish_gate.py PILOT_DIR [VIDEO_MP4]   (writes out/gate.json, exit 0 only on PASS)
"""
import hashlib
import json
from pathlib import Path
import sys

VERSION = "prepublish-gate-v1"
FROZEN_CRITERIA_SHA256 = {"pilot-qa-criteria-v2": "49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d"}
PASS_ITEM, PASS_OVERALL = 7, 8  # long_review.py rubric

# dimension -> qa checks (whole file, deterministic) and review rubric items (sampled, model)
DIMENSIONS = {
    "technical": {"qa": ["full_decode_without_errors", "video_format", "duration_min"], "review": []},
    "audio": {"qa": ["integrated_lufs", "true_peak", "speech_presence", "no_singing"], "review": ["audio_clarity_and_mix"]},
    "transcript": {"qa": ["wer_vs_script", "words_per_minute", "first_word_onset", "hook_second_person"], "review": []},
    "captions": {"qa": ["caption_coverage_of_speech", "caption_hold_median", "caption_chars_max"],
                 "review": ["captions_readable_and_synced"]},
    "sync": {"qa": ["caption_coverage_of_speech", "first_word_onset"], "review": ["captions_readable_and_synced"]},
    "image": {"qa": ["title_card_seconds", "figure_present_after_title", "background_hold_median", "background_hold_max",
                     "no_background_repeated_consecutively", "channel_mark_badge_and_amen_prompt"],
              "review": ["picture_quality", "figure_and_background_integrity"]},
    "rights": {"qa": ["images_open_licence_with_revision", "no_third_party_footage", "music_owned", "voice_model_pinned"],
               "review": []},
    "content_and_policy": {"qa": [], "review": ["opening_and_promise", "pacing_and_visual_variety", "scripture_on_screen",
                                                "policy_safe"]},
}
SCORE_HARD = ("minutes", "words_per_minute", "first_spoken_at", "scripture_per_10_min", "coverage")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def item(source, name, state, detail=None):
    return {"source": source, "item": name, "state": state, **({"detail": detail} if detail is not None else {})}


def binding(d, qa, manifest, review, video):
    out = []
    sha = (manifest or {}).get("output_sha256")
    out.append(item("binding", "manifest", "PASS" if sha else "UNKNOWN", sha))
    if qa is None:
        out.append(item("binding", "qa_for_this_file", "UNKNOWN", "out/qa.json missing"))
    else:
        out.append(item("binding", "qa_for_this_file", "PASS" if qa.get("output_sha256") == sha else "UNKNOWN",
                        qa.get("output_sha256")))
        frozen = FROZEN_CRITERIA_SHA256.get(qa.get("criteria_version"))
        crit = d / "qa_criteria.json"
        real = sha256_file(crit) if crit.exists() else None
        ok = frozen is not None and qa.get("criteria_sha256") == frozen == real
        out.append(item("binding", "qa_criteria_frozen", "PASS" if ok else "FAIL",
                        {"version": qa.get("criteria_version"), "recorded": qa.get("criteria_sha256"), "file": real}))
    if review is not None:
        out.append(item("binding", "review_for_this_file", "PASS" if review.get("output_sha256") == sha else "UNKNOWN",
                        review.get("output_sha256")))
    if video is not None:
        real = sha256_file(video) if Path(video).exists() else None
        out.append(item("binding", "video_file_hash", "PASS" if real and real == sha else ("UNKNOWN" if real is None else "FAIL"),
                        real))
    return out


def qa_items(qa, names, sha):
    if qa is None or qa.get("output_sha256") != sha:
        return [item("qa", n, "UNKNOWN", "no QA for this file") for n in names]
    checks = qa.get("checks") or {}
    return [item("qa", n, "UNKNOWN", "check absent") if n not in checks else
            item("qa", n, "PASS" if checks[n] is True else "FAIL") for n in names]


def review_items(review, names, sha):
    if review is None or review.get("output_sha256") != sha:
        return [item("review", n, "UNKNOWN", "no watched review for this file") for n in names]
    if review.get("status") not in ("PASS", "FAIL"):
        return [item("review", n, "UNKNOWN", f"review {review.get('status')}: {review.get('error', '')}"[:200]) for n in names]
    w = review.get("watched_review") or {}
    out = []
    for n in names:
        v = w.get(n)
        out.append(item("review", n, "UNKNOWN", "score absent") if not isinstance(v, (int, float)) else
                   item("review", n, "PASS" if v >= PASS_ITEM else "FAIL", v))
    return out


def decide(states):
    return "FAIL" if "FAIL" in states else ("UNKNOWN" if "UNKNOWN" in states or not states else "PASS")


def evaluate(pilot_dir, video=None, preflight_problems=None):
    d = Path(pilot_dir)
    qa, manifest = load(d / "out" / "qa.json"), load(d / "out" / "manifest.json")
    review = load(d / "out" / "review.json")
    sha = (manifest or {}).get("output_sha256")
    dims = {"binding": binding(d, qa, manifest, review, video)}
    for name, spec in DIMENSIONS.items():
        dims[name] = qa_items(qa, spec["qa"], sha) + review_items(review, spec["review"], sha)
    # whole-video watched review: its overall score is a gate of its own
    w = (review or {}).get("watched_review") or {}
    if review is None or review.get("output_sha256") != sha or review.get("status") not in ("PASS", "FAIL"):
        overall = [item("review", "overall", "UNKNOWN", "no completed watched review for this file")]
    elif not isinstance(w.get("overall"), (int, float)):
        overall = [item("review", "overall", "UNKNOWN", "score absent")]
    else:
        overall = [item("review", "overall", "PASS" if w["overall"] >= PASS_OVERALL else "FAIL", w["overall"])]
    dims["content_and_policy"] += overall
    hard = (review or {}).get("scorecard_hard") if review and review.get("output_sha256") == sha else None
    if not hard:
        dims["scorecard"] = [item("score", n, "UNKNOWN", "no scorecard for this file") for n in SCORE_HARD]
    else:
        dims["scorecard"] = [item("score", n, "UNKNOWN", "row absent") if n not in hard else
                             item("score", n, "PASS" if hard[n].get("pass") else "FAIL", hard[n].get("value"))
                             for n in sorted(set(SCORE_HARD) | set(hard))]
    if preflight_problems is None:
        dims["preflight"] = [item("preflight", "preflight", "UNKNOWN", "not run")]
    else:
        dims["preflight"] = [item("preflight", "preflight", "FAIL" if preflight_problems else "PASS", preflight_problems or None)]
    summary = {k: decide([i["state"] for i in v]) for k, v in dims.items()}
    decision = decide(list(summary.values()))
    return {"version": VERSION, "pilot_id": d.name, "output_sha256": sha, "decision": decision,
            "eligible_for_automatic_publication": decision == "PASS", "dimensions": summary, "items": dims,
            "informative_not_deciding": (review or {}).get("scorecard_reported", {}),
            "method_notes": {"review_sampling": "watched review samples pictures at 0.5 frames/s, low resolution",
                             "not_claimed": ["perceived quality by viewers", "retention, CTR or revenue",
                                             "originality beyond the rights checks listed"]}}


def main(pilot_dir, video=None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import preflight  # noqa: E402
    d = Path(pilot_dir)
    try:
        problems, _ = preflight.check(d, d / "inspection" / "thumbnail.jpg")
    except Exception as e:  # a preflight that cannot run is missing evidence, not a pass
        problems = None
        print(f"PREFLIGHT_ERROR {type(e).__name__}: {e}"[:300], file=sys.stderr)
    out = evaluate(d, video, problems)
    (d / "out" / "gate.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"decision": out["decision"], "dimensions": out["dimensions"]}))
    return 0 if out["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
