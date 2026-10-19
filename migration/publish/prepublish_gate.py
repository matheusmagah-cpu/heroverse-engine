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
- scan    out/scan.json (production/signal_scan.py): ffmpeg black/silence detectors over EVERY frame and
          sample, covering what the 0.5 fps review can miss. Scan rows are not bound to a hash inside the file:
          approve.yml writes it from the hash-verified download in the same job.
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
FROZEN_CRITERIA_SHA256 = {"pilot-qa-criteria-v2": "49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d",
                          # migration/STANDARD.md v1, frozen 2026-10-19 before the first v3 render; v2 is unchanged
                          "pilot-qa-criteria-v3": "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3"}
CRITERIA_V3 = Path(__file__).resolve().parents[1] / "production" / "qa_criteria_v3.json"
PASS_ITEM, PASS_OVERALL = 7, 8  # long_review.py rubric
# the watched review decides only when the designated model answered. Fallback free models score the same file
# very differently (pilot-003: gemini-3.8-flash audio 9 / picture 8.5 / policy 10; gemini-3.6-flash on a near-identical
# render 6.8 / 6.7 / 7.0; flash-lite gave 8-10 to four of five pilot-002 Shorts): their answer is UNKNOWN, retried
REVIEW_MODELS = ("gemini-3.8-flash",)

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
# STANDARD v1 renders (pilot-qa-criteria-v3) are held to its grammar instead of the v2 figure grammar
DIMENSIONS_V3 = {**DIMENSIONS,
                 "captions": {"qa": ["caption_coverage_of_speech", "caption_hold_median", "caption_chars_max",
                                     "caption_words_max", "caption_no_box"], "review": ["captions_readable_and_synced"]},
                 "image": {"qa": ["title_card_seconds", "no_figure", "every_scene_in_motion", "scene_seconds",
                                  "crossfade_seconds_max", "image_repeat_gap", "scripture_card_only_while_read", "cta_count",
                                  "cta_short_and_not_early", "persistent_overlays_only_brand"],
                           "review": ["picture_quality", "figure_and_background_integrity"]}}
# rows measured on our own file and script always block; miner rows block when long_review reports them as hard
# (only once the miner is proven on the holdout) and are then checked like any other hard row
SCORE_HARD = ("minutes", "scripture_per_10_min")


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
        crit = CRITERIA_V3 if qa.get("criteria_version") == "pilot-qa-criteria-v3" else d / "qa_criteria.json"
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
    if w.get("model") not in REVIEW_MODELS:
        return [item("review", n, "UNKNOWN", f"reviewer model {w.get('model')} is not the designated one") for n in names]
    out = []
    for n in names:
        v = w.get(n)
        out.append(item("review", n, "UNKNOWN", "score absent") if not isinstance(v, (int, float)) else
                   item("review", n, "PASS" if v >= PASS_ITEM else "FAIL", v))
    return out


def market_summary(d):
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mining"))
        import market_evidence
        return market_evidence.summary(d / "market" / "vidiq.json")
    except Exception as e:  # informative only: an error here never touches the decision
        return {"status": "UNKNOWN", "detail": f"{type(e).__name__}"}


def decide(states):
    return "FAIL" if "FAIL" in states else ("UNKNOWN" if "UNKNOWN" in states or not states else "PASS")


def evaluate(pilot_dir, video=None, preflight_problems=None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    d = Path(pilot_dir)
    qa, manifest = load(d / "out" / "qa.json"), load(d / "out" / "manifest.json")
    review = load(d / "out" / "review.json")
    sha = (manifest or {}).get("output_sha256")
    dims = {"binding": binding(d, qa, manifest, review, video)}
    spec_by_dim = DIMENSIONS_V3 if (qa or {}).get("criteria_version") == "pilot-qa-criteria-v3" else DIMENSIONS
    for name, spec in spec_by_dim.items():
        dims[name] = qa_items(qa, spec["qa"], sha) + review_items(review, spec["review"], sha)
    # whole-video watched review: its overall score is a gate of its own
    w = (review or {}).get("watched_review") or {}
    if review is None or review.get("output_sha256") != sha or review.get("status") not in ("PASS", "FAIL"):
        overall = [item("review", "overall", "UNKNOWN", "no completed watched review for this file")]
    elif w.get("model") not in REVIEW_MODELS:
        overall = [item("review", "overall", "UNKNOWN", f"reviewer model {w.get('model')} is not the designated one")]
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
    scan = load(d / "out" / "scan.json")
    if scan is None or scan.get("status") not in ("PASS", "FAIL"):
        dims["full_file_scan"] = [item("scan", "signal_scan", "UNKNOWN", (scan or {}).get("error", "out/scan.json missing"))]
    else:
        dims["full_file_scan"] = [item("scan", n, "PASS" if r["pass"] else "FAIL", r["longest_s"])
                                  for n, r in scan["rows"].items() if r.get("blocking")]
    if (qa or {}).get("criteria_version") == "pilot-qa-criteria-v3":
        # owner rule 2026-10-19: approved by the system when it passes STRUCTURE (mined), MODELING (above) and
        # AUTHENTICITY; computed from the pilot's own files (three_stage.py), any error is UNKNOWN, never PASS
        try:
            import three_stage
            for stage, rows in (("structure", three_stage.structure_rows(d)), ("authenticity", three_stage.authenticity_rows(d))):
                dims[stage] = [item(stage, r["name"], r["state"], r["value"]) for r in rows]
        except Exception as e:
            for stage in ("structure", "authenticity"):
                dims[stage] = [item(stage, "three_stage", "UNKNOWN", f"{type(e).__name__}: {str(e)[:120]}")]
    if preflight_problems is None:
        dims["preflight"] = [item("preflight", "preflight", "UNKNOWN", "not run")]
    else:
        dims["preflight"] = [item("preflight", "preflight", "FAIL" if preflight_problems else "PASS", preflight_problems or None)]
    summary = {k: decide([i["state"] for i in v]) for k, v in dims.items()}
    decision = decide(list(summary.values()))
    return {"version": VERSION, "pilot_id": d.name, "output_sha256": sha, "decision": decision,
            "eligible_for_automatic_publication": decision == "PASS", "dimensions": summary, "items": dims,
            "informative_not_deciding": {**(review or {}).get("scorecard_reported", {}),
                                         **{f"scan_{n}": r for n, r in ((scan or {}).get("rows") or {}).items()
                                            if not r.get("blocking")}},
            # market evidence (vidIQ opinion) travels with the package, separate from the decision above
            "market_evidence_not_deciding": market_summary(d),
            "method_notes": {"review_sampling": "watched review samples pictures at 0.5 frames/s, low resolution",
                             "not_claimed": ["perceived quality by viewers", "retention, CTR or revenue",
                                             "originality beyond the rights checks listed"]}}


def main(pilot_dir, video=None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import preflight  # noqa: E402
    d = Path(pilot_dir)
    try:
        # checked against the time publish.yml will really use: a late approval publishes now, it is not a FAIL
        problems, _ = preflight.check(d, d / "inspection" / "thumbnail.jpg", preflight.effective_publish_at(d))
    except Exception as e:  # a preflight that cannot run is missing evidence, not a pass
        problems = None
        print(f"PREFLIGHT_ERROR {type(e).__name__}: {e}"[:300], file=sys.stderr)
    out = evaluate(d, video, problems)
    (d / "out" / "gate.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"decision": out["decision"], "dimensions": out["dimensions"]}))
    return 0 if out["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
