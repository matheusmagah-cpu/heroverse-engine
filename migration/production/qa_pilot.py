#!/usr/bin/env python3
"""QA of a rendered pilot against the frozen qa_criteria.json (F5 gates).

Uses the qualified instruments: av-event-meter (cuts), av-semantic (speech,
words, ASR), av-profile (loudness), plus ffprobe/full decode and the render
manifest for rights. Writes qa.json with PASS/FAIL per criterion. A FAIL
blocks approval; nothing here uploads or publishes.
"""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent / "diagnostics"
for sub in ("av-event-meter", "av-semantic", "av-profile"):
    sys.path.insert(0, str(DIAG / sub))
import av_profile  # noqa: E402
import av_semantic  # noqa: E402
from qualify_semantic import wer  # noqa: E402

OWNED_MUSIC_SHA256 = "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c"


def within(value, bounds):
    return value is not None and bounds[0] <= value <= bounds[1]


def grammar_checks(criteria, manifest):
    """Amended-archetype gates read from the render manifest (pilot-manifest-v2)."""
    import statistics
    g, r = criteria["grammar"], criteria["rights"]
    holds = manifest["holds"]
    title = holds[0]["end"] - holds[0]["start"]
    after = [h for h in holds[1:]]
    span = sum(h["end"] - h["start"] for h in after)
    lengths = [h["end"] - h["start"] for h in after[:-1]] or [span]
    caps, sents = manifest["captions"], [s for s in manifest["sentences"] if s["end"] > title]
    covered = sum(max(0.0, min(s["end"], c["end"]) - max(s["start"], c["start"], title)) for s in sents for c in caps)
    spoken = sum(s["end"] - max(s["start"], title) for s in sents)
    allowed = set(r["allowed_model_licences"])
    models = [m for i in manifest["images"].values() for m in i["models"].values()] + list(manifest["figure"]["models"].values())
    return {
        "title_card_seconds": within(title, g["title_card_seconds"]) and not holds[0]["figure"],
        "figure_present_after_title": sum(h["end"] - h["start"] for h in after if h["figure"]) / span >= g["figure_present_fraction_after_title_min"],
        "background_hold_median": within(statistics.median(lengths), g["background_hold_seconds_median"]),
        "background_hold_max": max(lengths) <= g["background_hold_seconds_max"],
        "no_background_repeated_consecutively": all(a["image"] != b["image"] for a, b in zip(after, after[1:])),
        "caption_coverage_of_speech": spoken > 0 and covered / spoken >= g["caption_coverage_of_speech_min"],
        "caption_hold_median": within(statistics.median(c["end"] - c["start"] for c in caps), g["caption_hold_seconds_median"]),
        "caption_chars_max": max(len(c["text"]) for c in caps) <= g["caption_chars_max"],
        "channel_mark_badge_and_amen_prompt": bool(manifest["overlay"]["brand"] and manifest["overlay"]["amen"] and manifest["badges"]),
        "images_open_licence_with_revision": bool(models) and all(str(m.get("license")).lower() in allowed and m.get("revision") for m in models),
        "no_third_party_footage": not manifest["clips"] and not manifest["shots"],
    }


def grammar_checks_v3(criteria, manifest):
    """migration/STANDARD.md v1 (R1-R6) read from the render manifest (pilot-qa-criteria-v3)."""
    import statistics
    g, r = criteria["grammar"], criteria["rights"]
    holds = manifest["holds"]
    title = holds[0]["end"] - holds[0]["start"]
    scenes = holds[1:]
    inner = [h["end"] - h["start"] for h in scenes[:-1]] or [scenes[0]["end"] - scenes[0]["start"]]
    last_seen, gaps = {}, []
    for h in scenes:
        if h["image"] in last_seen:
            gaps.append(h["start"] - last_seen[h["image"]])
        last_seen[h["image"]] = h["end"]
    caps, sents = manifest["captions"], [s for s in manifest["sentences"] if s["end"] > title]
    covered = sum(max(0.0, min(s["end"], c["end"]) - max(s["start"], c["start"], title)) for s in sents for c in caps)
    spoken = sum(s["end"] - max(s["start"], title) for s in sents)
    seg_end = {}
    for s in manifest["sentences"]:
        seg_end[s["segment"]] = max(seg_end.get(s["segment"], 0.0), s["end"])
    cta = manifest.get("cta", [])
    style = manifest.get("caption_style", {})
    allowed = set(r["allowed_model_licences"])
    models = [m for i in manifest["images"].values() for m in i["models"].values()]
    return {
        "title_card_seconds": within(title, g["title_card_seconds"]),
        "no_figure": manifest.get("figure") is None and not any(h["figure"] for h in holds),
        "every_scene_in_motion": all(h.get("motion") for h in holds),
        "scene_seconds": all(within(x, g["scene_seconds"]) for x in inner)
                         and scenes[-1]["end"] - scenes[-1]["start"] >= g["scene_seconds"][0],
        "crossfade_seconds_max": manifest.get("crossfade_seconds", 99) <= g["crossfade_seconds_max"],
        "image_repeat_gap": all(x >= g["image_repeat_gap_seconds_min"] for x in gaps),
        "caption_coverage_of_speech": spoken > 0 and covered / spoken >= g["caption_coverage_of_speech_min"],
        "caption_hold_median": within(statistics.median(c["end"] - c["start"] for c in caps), g["caption_hold_seconds_median"]),
        "caption_chars_max": max(len(c["text"]) for c in caps) <= g["caption_chars_max"],
        "caption_words_max": max(len(c["text"].split()) for c in caps) <= g["caption_words_max"],
        "caption_no_box": style.get("box") is g["caption_box"],
        "scripture_card_only_while_read": all(c["end"] <= seg_end.get(c["segment"], -1) + 1e-6 and c["end"] > c["start"]
                                              for c in manifest.get("scripture_cards", [])),
        "cta_count": len(cta) <= g["cta_mid_video_max"],
        "cta_short_and_not_early": all(c["end"] - c["start"] <= g["cta_seconds_max"] and c["start"] >= g["cta_first_start_seconds_min"]
                                       for c in cta),
        "persistent_overlays_only_brand": manifest.get("persistent_overlays") == g["persistent_overlays_allowed"],
        "images_open_licence_with_revision": bool(models) and all(str(m.get("license")).lower() in allowed and m.get("revision") for m in models),
        "no_third_party_footage": not manifest["clips"] and not manifest["shots"],
    }


def grammar_checks_v4(criteria, manifest):
    """pilot-qa-criteria-v4 (owner, 2026-10-23): the v3 grammar with 4-7 s shots, at least a share of the picture
    time in real footage, and footage rights in place of v3's no-footage rule. Footage holds carry kind "footage"
    and the clip id in "image"; every clip used is listed in manifest["clips"] with its licence, vetting and credit."""
    g, r = criteria["grammar"], criteria["rights"]
    checks = grammar_checks_v3(criteria, manifest)
    del checks["no_third_party_footage"]
    scenes = manifest["holds"]   # v4: the opening shot is footage too, so the share counts the whole picture
    span = sum(h["end"] - h["start"] for h in scenes)
    footage = sum(h["end"] - h["start"] for h in scenes if h.get("kind") == "footage")
    clips = manifest.get("clips") or []
    used = {h["image"].partition("#")[0] for h in manifest["holds"] if h.get("kind") == "footage"}
    listed = {c.get("id") for c in clips}
    allowed = set(r["allowed_footage_licences"])
    checks["footage_picture_share"] = span > 0 and footage / span >= g["footage_picture_share_min"]
    checks["footage_licensed_vetted_and_credited"] = bool(clips) and used <= listed and all(
        c.get("licence") in allowed and c.get("vetting") == r["footage_vetting_required"] and c.get("credit")
        and c.get("sha256") for c in clips)
    return checks


def main(video, manifest_path, script_path, criteria_path, yamnet, whisper, out):
    criteria = json.loads(Path(criteria_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    script = json.loads(Path(script_path).read_text())
    checks = {}
    decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", video, "-f", "null", "-"],
                            capture_output=True, text=True)
    checks["full_decode_without_errors"] = decode.returncode == 0 and not decode.stderr.strip()
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", video],
                                     check=True, capture_output=True, text=True).stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    fw, fh = criteria["technical"].get("frame", [1920, 1080])  # v4: 2560x1440 (owner, 2026-10-23: >= 1440p)
    checks["video_format"] = (len(v) == 1 and v[0]["codec_name"] == "h264" and v[0]["width"] == fw
                              and v[0]["height"] == fh and v[0]["avg_frame_rate"] in ("30/1", "30000/1000")
                              and len(a) == 1 and a[0]["codec_name"] == "aac" and a[0]["sample_rate"] == "48000"
                              and a[0]["channels"] == 2)
    duration = float(info["format"]["duration"])
    checks["duration_min"] = duration >= criteria["technical"]["duration_seconds_min"]
    semantic = av_semantic.analyze(video, yamnet, whisper)
    profile = av_profile.profile(video, semantic)
    loud = profile["loudness"]
    checks["integrated_lufs"] = within(loud["integrated_lufs"], criteria["technical"]["integrated_lufs"])
    checks["true_peak"] = loud["true_peak_dbtp"] is not None and loud["true_peak_dbtp"] <= criteria["technical"]["true_peak_dbtp_max"]
    sp = criteria["speech"]
    presence = semantic["presence_fraction"]
    checks["speech_presence"] = presence["speech"] >= sp["speech_presence_min"]
    checks["no_singing"] = presence["singing"] <= sp["singing_presence_max"]
    text = " ".join(s["text"] for s in script["segments"])
    error = wer(text, semantic["transcript"])
    checks["wer_vs_script"] = error <= sp["wer_vs_script_max"]
    words = semantic["words"]
    wpm = len(words) / (duration / 60)
    checks["words_per_minute"] = within(wpm, sp["accepted_words_per_minute"])
    first = words[0]["start_seconds"] if words else None
    checks["first_word_onset"] = first is not None and first <= sp["first_word_onset_seconds_max"]
    checks["hook_second_person"] = any(w["word"].lower().strip(".,!?") in ("you", "your", "you're")
                                       and w["start_seconds"] <= sp["hook_second_person_within_seconds"] for w in words)
    if "editing" in criteria:
        ed = criteria["editing"]
        checks["picture_changes_per_minute"] = within(profile["editing"]["picture_changes_per_minute"], ed["picture_changes_per_minute"])
        checks["median_shot_seconds"] = within(profile["editing"]["median_shot_seconds"], ed["median_shot_seconds"])
        spans = {}
        for shot in manifest["shots"]:
            spans.setdefault(shot["video_id"], []).append((shot["source_start"], shot["source_start"] + shot["duration"]))
        checks["no_source_second_reused"] = all(b0 >= a1 - 1e-6 for s in spans.values()
                                                for (a0, a1), (b0, b1) in zip(sorted(s), sorted(s)[1:]))
        clips = manifest["clips"]
        checks["clips_creative_commons_with_attribution"] = bool(clips) and all(
            c["license"] == "creativeCommon" and c["attribution"] and c["picture_only"] for c in clips)
    else:
        grammar = {"pilot-qa-criteria-v3": grammar_checks_v3, "pilot-qa-criteria-v4": grammar_checks_v4}
        checks.update(grammar.get(criteria["version"], grammar_checks)(criteria, manifest))
    checks["music_owned"] = manifest["music"]["sha256"] == OWNED_MUSIC_SHA256
    checks["voice_model_pinned"] = manifest["voice"]["voice_id"] == "am_michael"
    checks = {k: bool(v) for k, v in checks.items()}  # numpy bools are not JSON serializable
    result = {"version": "pilot-qa-v1", "pilot_id": manifest["pilot_id"], "output_sha256": manifest["output_sha256"],
              "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "criteria_version": criteria["version"],
              "measurements": {"duration_seconds": round(duration, 2), "loudness": loud,
                               "speech_presence": presence["speech"], "music_presence": presence["music"],
                               "wer_vs_script": round(error, 4), "accepted_words_per_minute": round(wpm, 1),
                               "caption_lines": len(manifest.get("captions", [])), "holds": len(manifest.get("holds", [])),
                               "first_word_seconds": first, "editing": profile["editing"],
                               "colour": profile["colour"], "rhythm": profile["rhythm"]},
              "transcript_head": semantic["transcript"][:400],
              "criteria_sha256": av_semantic.sha256(criteria_path),
              "human_review": "PENDING (D-076 calibration by sampling)",
              "upload_performed": False, "publication_performed": False}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"status": result["status"], "failed": [k for k, ok in checks.items() if not ok],
                      **{k: result["measurements"][k] for k in ("duration_seconds", "wer_vs_script",
                                                                "accepted_words_per_minute", "speech_presence")}}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:8]))
