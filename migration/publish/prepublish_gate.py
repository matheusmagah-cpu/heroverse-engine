#!/usr/bin/env python3
"""Final pre-publication decision of a rendered long video: PASS, FAIL or UNKNOWN.

Only PASS makes a new render eligible for automatic publication. It adds no new
measurement: it reads the evidence the existing controls already wrote for THIS
file and checks that every dimension is covered.

Evidence and method (each item names where it comes from):
- qa      out/qa.json, frozen criteria (qa_pilot.py): deterministic tools over the
          WHOLE file (ffmpeg decode/loudness, ASR word error vs script, caption
          file vs detected speech, render manifest).
- review  out/review.json (long_review.py): an explicitly designated session review
          of inspection sheets, transcript, thumbnail and QA audio measures.
          Pictures are sampled; whole-file QA and scan remain separate requirements.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import owner_quality_policy  # noqa: E402

VERSION = "prepublish-gate-v1"
FROZEN_CRITERIA_SHA256 = {"pilot-qa-criteria-v2": "49fedd2e5ebf525e38dab1e5135124d31f8ce822f71f3a02c61c702d2da8790d",
                          # migration/STANDARD.md v1, frozen 2026-10-19 before the first v3 render; v2 is unchanged
                          "pilot-qa-criteria-v3": "4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3",
                          # owner, 2026-10-23: real licensed footage, 8-14 s scenes; v3 stays frozen and unchanged
                          "pilot-qa-criteria-v4": "36f2d648d2f37f44781d4ccbee0cd775fd01a5010357cc3bb3478daaafe86b11",
                          # owner, 2026-10-25: Bible-story longs, v4 floors plus Pavo AI video (<= 55 %, >= 40 % real footage)
                          "story-qa-criteria-v1": "5dcf63f92fc716852096cefa8fd48f7498f4733eb1d347f4212a6f31a6c95360",
                          # owner, 2026-10-26 ("Sim, régua nova"): the acted Bible-story long; 2026-10-27 Pavo freed,
                          # no real-footage minimum (v3 has none); v1/v2 stay frozen and unchanged
                          "story-qa-criteria-v3": "746e772d8024a93ef95cbf0f226568cf972e5611b59a430322312605f8e7badc",
                          # owner, 2026-10-27 (R1-R4): v3 + Pavo's speech kept per clip under checks, the pinned
                          # medium.en ASR, free fallbacks for non-spoken shots; v3 stays frozen and unchanged
                          "story-qa-criteria-v4": "99a91e3e75387acea6c6815510baa9a5d0271e46eb0a644e66b8a7e0ab0a272f",
                          # owner exception 2026-10-28 ("tem que ser amanhã"): v4 with only the fallback rows widened,
                          # for the arc-01 long only (long_plan_check CRITERIA_EXCEPTION_PLAN); v4 stays frozen
                          "story-qa-criteria-v4-owner-exception-arc01": "7895818a855f84ee70666f64a9461e4ed1eadf82ddeffbfab97a6ce0a6b7b388",
                          "story-qa-criteria-v5": "d75998f8dffc0e8ad378360d2f897db2d110459beca2097059f32dc6594396ce",
                          # owner, 2026-11-01 (E251): the compilation long of an arc's public Shorts, defect-gated
                          "compilation-qa-criteria-v1": "023e4183247ce3436407dea58e546cbf47bf914569770a9cbc091121df9efe99"}
CRITERIA_V3 = Path(__file__).resolve().parents[1] / "production" / "qa_criteria_v3.json"
CRITERIA_FILES = {"pilot-qa-criteria-v3": CRITERIA_V3,
                  "pilot-qa-criteria-v4": Path(__file__).resolve().parents[1] / "production" / "qa_criteria_v4.json",
                  "story-qa-criteria-v1": Path(__file__).resolve().parents[1] / "production" / "qa_criteria_story_v1.json",
                  "story-qa-criteria-v3": Path(__file__).resolve().parents[1] / "production" / "qa_criteria_story_v3.json",
                  "story-qa-criteria-v4": Path(__file__).resolve().parents[1] / "production" / "qa_criteria_story_v4.json",
                  "story-qa-criteria-v4-owner-exception-arc01": Path(__file__).resolve().parents[1] / "production"
                  / "qa_criteria_story_v4_owner_exception_arc01.json",
                  "story-qa-criteria-v5": Path(__file__).resolve().parents[1] / "production" / "qa_criteria_story_v5.json",
                  "compilation-qa-criteria-v1": Path(__file__).resolve().parents[1] / "production"
                  / "qa_criteria_compilation_v1.json"}
COMPILATION = "compilation-qa-criteria-v1"   # E251: its own track; none of the STANDARD/story rows apply to it
COMPILATION_ARCHETYPE = "bible-compilation-long"
STANDARD_VERSIONS = tuple(v for v in CRITERIA_FILES if v != COMPILATION)  # STANDARD.md renders approved or published
PASS_ITEM, PASS_OVERALL = 7, 8  # long_review.py rubric
# E251: the compilation's dimensions (qa checks of compilation_long.qa; the review is the defect gate below)
COMPILATION_DIMENSIONS = {
    "technical": ["full_decode_without_errors", "video_format_1920x1080_30fps", "duration_is_sum_of_segments", "no_padding"],
    "audio": ["integrated_lufs_band", "true_peak_ceiling"],
    "rights": ["sources_are_the_public_masters_by_sha", "keeper_clips_zero_credit", "music_and_voice_owned"],
    "structure": ["canonical_order"]}
COMPILATION_REVIEW_ITEMS = ("designated_reviewer_bound_to_file", "publish_decision", "no_unresolved_a_b_e")
# the watched review decides only when the designated model answered. Fallback free models score the same file
# very differently (pilot-003: gemini-3.8-flash audio 9 / picture 8.5 / policy 10; gemini-3.6-flash on a near-identical
# render 6.8 / 6.7 / 7.0; flash-lite gave 8-10 to four of five pilot-002 Shorts): their answer is UNKNOWN, retried
REVIEW_MODELS = owner_quality_policy.LONG_REVIEWERS

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
# v4: footage rights replace v3's no-footage rule; the footage share is part of the picture
DIMENSIONS_V4 = {**DIMENSIONS_V3,
                 "image": {"qa": DIMENSIONS_V3["image"]["qa"] + ["footage_picture_share"],
                           "review": DIMENSIONS_V3["image"]["review"]},
                 "rights": {"qa": ["images_open_licence_with_revision", "footage_licensed_vetted_and_credited",
                                   "music_owned", "voice_model_pinned"], "review": []}}
# story v1: the v4 rows plus the Pavo share and its source/licence
DIMENSIONS_STORY_V1 = {**DIMENSIONS_V4,
                       "image": {"qa": DIMENSIONS_V4["image"]["qa"] + ["ai_video_picture_share"],
                                 "review": DIMENSIONS_V4["image"]["review"]},
                       "rights": {"qa": DIMENSIONS_V4["rights"]["qa"] + ["ai_video_source_and_licence"], "review": []}}
STORY_V3 = "story-qa-criteria-v3"
STORY_V4 = "story-qa-criteria-v4"
STORY_V4X = "story-qa-criteria-v4-owner-exception-arc01"   # the owner's arc-01 exception (28/10)
STORY_V5 = "story-qa-criteria-v5"   # the general rule since 28/10
STORY_VERSIONS = (STORY_V3, STORY_V4, STORY_V4X, STORY_V5)


def story_v3_rows(version=STORY_V3):
    """qa_pilot.STORY_ROWS[version]: every row of the frozen story QA (v3, or v4 for a plan that declares it) and the
    qa checks that measure it. Imported here, not at module level (qa_pilot's instruments load only in its main)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
    import qa_pilot
    return qa_pilot.STORY_ROWS[version]


def dimensions_story_v3(version=STORY_V3):
    """story v3 (the acted long): v1's title card, figure, footage-share and burned-caption rows are gone; each
    dimension lists the checks of its v3 rows (STORY_V3_ROWS), so no row is left out. The review items are
    v3's (the watched review, overall >= 9.5 in owner_quality_policy). v4: the same, over v4's rows."""
    rows = story_v3_rows(version)

    def checks(prefixes):
        out = []
        for row, names in rows.items():
            if row.split(".")[0] in prefixes or row in prefixes:
                out += [n for n in names if n not in out]
        return out
    caps = [r for r in rows if r.startswith("grammar.srt_") or r in ("grammar.caption_track", "grammar.burned_captions")]
    image = [r for r in rows if r.startswith("grammar.") and r not in caps]
    return {"technical": {"qa": checks(("technical",)), "review": []},
            "audio": {"qa": ["integrated_lufs", "true_peak", "speech_presence", "no_singing"],
                      "review": ["audio_clarity_and_mix"]},
            "transcript": {"qa": ["wer_vs_script", "words_per_minute", "first_word_onset", "hook_second_person"]
                                 + [n for n in checks(("speech.asr_model",)) if n not in ("wer_vs_script",)],
                           "review": []},
            "captions": {"qa": checks(caps), "review": ["captions_readable_and_synced"]},
            "sync": {"qa": ["srt_coverage_of_speech", "first_word_onset"], "review": ["captions_readable_and_synced"]},
            "image": {"qa": checks(image), "review": ["picture_quality", "figure_and_background_integrity"]},
            "rights": {"qa": checks(("rights",)), "review": []},
            "content_and_policy": DIMENSIONS["content_and_policy"]}


def story_v3_row_items(qa, sha, version=STORY_V3):
    """One item per row of the frozen story QA v3 / v4 (PASS / FAIL / UNKNOWN from its checks; UNKNOWN when the QA is
    not for this file or a check is absent): every row is evaluated, none is skipped."""
    rows = story_v3_rows(version)
    name = "story_qa_" + version.rsplit("-", 1)[-1]
    if qa is None or qa.get("output_sha256") != sha:
        return [item(name, r, "UNKNOWN", "no QA for this file") for r in rows]
    checks = qa.get("checks") or {}
    out = []
    for r, names in rows.items():
        values = [checks.get(n) for n in names]
        state = "FAIL" if any(v is False for v in values) else ("PASS" if all(v is True for v in values) else "UNKNOWN")
        out.append(item(name, r, state, {n: checks.get(n, "absent") for n in names}))
    return out


DIMENSIONS_BY_VERSION = {"pilot-qa-criteria-v3": DIMENSIONS_V3, "pilot-qa-criteria-v4": DIMENSIONS_V4,
                         "story-qa-criteria-v1": DIMENSIONS_STORY_V1}
# rows measured on our own file and script always block; miner rows block when long_review reports them as hard
# (only once the miner is proven on the holdout) and are then checked like any other hard row
SCORE_HARD = ("minutes", "scripture_per_10_min")


def score_hard_keys(version):
    """The acted story's registered structure has a length band, not a prayer's quotation frequency."""
    return ("minutes",) if version in STORY_VERSIONS else SCORE_HARD


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


def story_long(pilot_dir):
    """Owner, 2026-10-26: "stop the prayer videos; the channel is going in another direction." Only a Bible-story
    long (render_queue.story_pilot) may be approved or published. Imported here, not at module level:
    render_queue -> shorts_prerequisite -> publication_binding imports this module."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "production"))
    import render_queue
    return render_queue.story_pilot(pilot_dir) or compilation_long(pilot_dir)


def format_items(pilot_dir):
    ok = story_long(pilot_dir)
    return [item("format", "story_long", "PASS" if ok else "FAIL", "bible-story-long" if ok else "NOT_STORY_LONG")]


def compilation_long(pilot_dir):
    """E251: the pilot holds the compilation of an arc's public Shorts (script archetype bible-compilation-long)."""
    script = load(Path(pilot_dir) / "script.json")
    return isinstance(script, dict) and script.get("archetype") == COMPILATION_ARCHETYPE


def compilation_review_items(review, sha):
    """The defect gate as items: the designated reviewer's file for this master, a publish decision, no unresolved
    [a] [b] [e]. A review that is absent or for another file is UNKNOWN, a refused one FAIL; never a pass by default."""
    if review is None or review.get("output_sha256") != sha or review.get("status") not in ("PASS", "FAIL"):
        why = f"review {None if review is None else review.get('status')}: {(review or {}).get('error', '')}"[:200]
        return [item("review", n, "UNKNOWN", why) for n in COMPILATION_REVIEW_ITEMS]
    w = dict(review.get("watched_review") or {})
    if review.get("status") == "FAIL":
        return [item("review", n, "FAIL", review.get("error")) for n in COMPILATION_REVIEW_ITEMS]
    problems = owner_quality_policy.compilation_problems({**w, "output_sha256": review["output_sha256"]}, sha)
    unresolved = "REVIEW_DEFECT_UNRESOLVED" in problems
    decision = any(p in problems for p in ("REVIEW_DECISION_MISSING",))
    other = [p for p in problems if p not in ("REVIEW_DEFECT_UNRESOLVED", "REVIEW_DECISION_MISSING")]
    return [item("review", COMPILATION_REVIEW_ITEMS[0], "FAIL" if other else "PASS", other or w.get("model")),
            item("review", COMPILATION_REVIEW_ITEMS[1], "FAIL" if decision else "PASS"),
            item("review", COMPILATION_REVIEW_ITEMS[2], "FAIL" if unresolved else "PASS")]


def evaluate_compilation(d, qa, manifest, review, video, preflight_problems):
    sha = (manifest or {}).get("output_sha256")
    dims = {"binding": binding(d, qa, manifest, review, video), "format": format_items(d)}
    dims["format"] = [item("format", "story_long", "PASS" if compilation_long(d) else "FAIL",
                           COMPILATION_ARCHETYPE if compilation_long(d) else "NOT_COMPILATION_LONG")]
    for name, checks in COMPILATION_DIMENSIONS.items():
        dims[name] = qa_items(qa, checks, sha)
    dims["defect_review"] = compilation_review_items(review, sha)
    scan = load(d / "out" / "scan.json")
    if scan is None or scan.get("status") not in ("PASS", "FAIL"):
        dims["full_file_scan"] = [item("scan", "signal_scan", "UNKNOWN", (scan or {}).get("error", "out/scan.json missing"))]
    else:
        dims["full_file_scan"] = [item("scan", n, "PASS" if r["pass"] else "FAIL", r["longest_s"])
                                  for n, r in scan["rows"].items() if r.get("blocking")]
    dims["preflight"] = ([item("preflight", "preflight", "UNKNOWN", "not run")] if preflight_problems is None else
                         [item("preflight", "preflight", "FAIL" if preflight_problems else "PASS", preflight_problems or None)])
    summary = {k: decide([i["state"] for i in v]) for k, v in dims.items()}
    decision = decide(list(summary.values()))
    return {"version": VERSION, "pilot_id": d.name, "output_sha256": sha, "decision": decision,
            "eligible_for_automatic_publication": decision == "PASS", "dimensions": summary, "items": dims,
            "informative_not_deciding": {}, "market_evidence_not_deciding": market_summary(d),
            "method_notes": {"track": "compilation (E251): defect gate, no score floor",
                             "not_claimed": ["perceived quality by viewers", "retention, CTR or revenue"]}}


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
        crit = CRITERIA_FILES.get(qa.get("criteria_version"), d / "qa_criteria.json")
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
    return [item("qa", n, "UNKNOWN", "check absent") if checks.get(n) is None else   # None: evidence absent (v3)
            item("qa", n, "PASS" if checks[n] is True else "FAIL") for n in names]


def review_items(review, names, sha):
    if review is None or review.get("output_sha256") != sha:
        return [item("review", n, "UNKNOWN", "no watched review for this file") for n in names]
    if review.get("status") not in ("PASS", "FAIL"):
        return [item("review", n, "UNKNOWN", f"review {review.get('status')}: {review.get('error', '')}"[:200]) for n in names]
    w = review.get("watched_review") or {}
    if not owner_quality_policy.evidence_valid(w):
        return [item("review", n, "UNKNOWN", "review evidence malformed or absent") for n in names]
    if w.get("model") not in REVIEW_MODELS:
        return [item("review", n, "UNKNOWN", f"reviewer model {w.get('model')} is not the designated one") for n in names]
    out = []
    for n in names:
        v = w.get(n)
        out.append(item("review", n, "UNKNOWN", "score absent or invalid") if not owner_quality_policy.score_valid(v) else
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
    dims = {"binding": binding(d, qa, manifest, review, video), "format": format_items(d)}
    version = (qa or {}).get("criteria_version")
    if version == COMPILATION:
        return evaluate_compilation(d, qa, manifest, review, video, preflight_problems)
    spec_by_dim = (dimensions_story_v3(version) if version in STORY_VERSIONS
                   else DIMENSIONS_BY_VERSION.get(version, DIMENSIONS))
    for name, spec in spec_by_dim.items():
        dims[name] = qa_items(qa, spec["qa"], sha) + review_items(review, spec["review"], sha)
    if version in STORY_VERSIONS:
        dims["story_qa_" + version.rsplit("-", 1)[-1]] = story_v3_row_items(qa, sha, version)
    # whole-video watched review: its overall score is a gate of its own
    w = (review or {}).get("watched_review") or {}
    if not isinstance(w, dict):
        w = {}
    if review is None or review.get("output_sha256") != sha or review.get("status") not in ("PASS", "FAIL"):
        overall = [item("review", "overall", "UNKNOWN", "no completed watched review for this file")]
    elif not owner_quality_policy.evidence_valid(w):
        overall = [item("review", "overall", "UNKNOWN", "review evidence malformed or absent")]
    elif w.get("model") not in REVIEW_MODELS:
        overall = [item("review", "overall", "UNKNOWN", f"reviewer model {w.get('model')} is not the designated one")]
    elif not owner_quality_policy.score_valid(w.get("overall")):
        overall = [item("review", "overall", "UNKNOWN", "score absent or invalid")]
    else:
        overall = [item("review", "overall", "PASS" if w["overall"] >= PASS_OVERALL else "FAIL", w["overall"])]
    dims["content_and_policy"] += overall
    hard = (review or {}).get("scorecard_hard") if review and review.get("output_sha256") == sha else None
    if not hard:
        dims["scorecard"] = [item("score", n, "UNKNOWN", "no scorecard for this file") for n in score_hard_keys(version)]
    else:
        dims["scorecard"] = [item("score", n, "UNKNOWN", "row absent") if n not in hard else
                             item("score", n, "PASS" if hard[n].get("pass") else "FAIL", hard[n].get("value"))
                             for n in sorted(set(score_hard_keys(version)) | set(hard))]
    scan = load(d / "out" / "scan.json")
    if scan is None or scan.get("status") not in ("PASS", "FAIL"):
        dims["full_file_scan"] = [item("scan", "signal_scan", "UNKNOWN", (scan or {}).get("error", "out/scan.json missing"))]
    else:
        dims["full_file_scan"] = [item("scan", n, "PASS" if r["pass"] else "FAIL", r["longest_s"])
                                  for n, r in scan["rows"].items() if r.get("blocking")]
    if (qa or {}).get("criteria_version") in STANDARD_VERSIONS:
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
