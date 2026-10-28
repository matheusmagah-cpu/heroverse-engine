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
sys.path.insert(0, str(HERE.parent / "publish"))   # captions.py: the one SRT builder (the long's .srt track)
CHARACTERS = HERE / "characters" / "characters.json"
KJV_CHECK = HERE / "bible"

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
        # "every image": a footage-only render (E66) shows no generated image, so there is none to license (E68);
        # with any still on screen the models must be recorded
        "images_open_licence_with_revision": (bool(models) or all(h.get("kind") == "footage" for h in holds))
                                             and all(str(m.get("license")).lower() in allowed and m.get("revision") for m in models),
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


def grammar_checks_story_v1(criteria, manifest):
    """story-qa-criteria-v1 (owner, 2026-10-25): the v4 grammar and rights, with Pavo AI video allowed as footage after
    Real-ESRGAN super-resolution and Claude's vetting. The footage share counts real licensed footage only; Pavo clips
    (manifest clip source "pavo", the criteria's ai_video licence) have their own maximum share."""
    g, r = criteria["grammar"], criteria["rights"]
    checks = grammar_checks_v4(criteria, manifest)
    ai = r["ai_video"]
    clips = {c.get("id"): c for c in manifest.get("clips") or []}
    is_ai = {i for i, c in clips.items() if c.get("source") == ai["source"] or c.get("licence") == ai["licence"]}
    scenes = manifest["holds"]
    span = sum(h["end"] - h["start"] for h in scenes)
    shown = [(h["end"] - h["start"], h["image"].partition("#")[0]) for h in scenes if h.get("kind") == "footage"]
    real = sum(t for t, i in shown if i not in is_ai)
    synthetic = sum(t for t, i in shown if i in is_ai)
    checks["footage_picture_share"] = span > 0 and real / span >= g["footage_picture_share_min"]
    checks["ai_video_picture_share"] = span > 0 and synthetic / span <= g["ai_video_picture_share_max"]
    checks["ai_video_source_and_licence"] = all(clips[i].get("source") == ai["source"]
                                                and clips[i].get("licence") == ai["licence"] for i in is_ai)
    return checks


STORY_V3 = "story-qa-criteria-v3"
# Every row of the frozen story QA v3 (technical, speech, rights, grammar) and the qa.json checks that measure it.
# A row is PASS only when every check it names is True, FAIL when one is False, UNKNOWN when one is absent or None
# (evidence missing): never skipped (prepublish_gate reads the rows through this table; test_qa_pilot holds it equal
# to the frozen file). There is no footage minimum: v3 has no footage_picture_share row (owner, 2026-10-27).
STORY_V3_ROWS = {
    "technical.full_decode_without_errors": ["full_decode_without_errors"],
    "technical.video": ["video_format"],
    "technical.duration_seconds_min": ["duration_min"],
    "technical.integrated_lufs": ["integrated_lufs"],
    "technical.true_peak_dbtp_max": ["true_peak"],
    "technical.frame": ["video_format"],
    "speech.speech_presence_min": ["speech_presence"],
    "speech.singing_presence_max": ["no_singing"],
    "speech.wer_vs_script_max": ["wer_vs_script"],
    "speech.accepted_words_per_minute": ["words_per_minute"],
    "speech.first_word_onset_seconds_max": ["first_word_onset"],
    "speech.hook_second_person_within_seconds": ["hook_second_person"],
    "rights.every_image_generated_by_allowed_open_licence_model_with_revision": ["images_open_licence_with_revision"],
    "rights.allowed_model_licences": ["images_open_licence_with_revision"],
    "rights.music_owned_generator_with_hash": ["music_owned"],
    "rights.voice_model_hash_pinned": ["voice_model_pinned"],
    "rights.script_original_with_public_domain_scripture_only": ["scripture_kjv_exact"],
    "rights.footage_licensed_vetted_and_credited": ["footage_licensed_vetted_and_credited"],
    "rights.allowed_footage_licences": ["footage_licensed_vetted_and_credited"],
    "rights.footage_vetting_required": ["footage_licensed_vetted_and_credited"],
    "rights.ai_video": ["ai_video_source_and_licence"],
    "grammar.first_shot": ["first_shot_cold_open"],
    # figures_allowed measures who is on screen (APPROVED entries, the Keeper in his beats, never God); the "look
    # word for word and approved references" part is enforced at plan time by plan_check.character_problems
    # (CHARACTER_LOOK_CHANGED, CHARACTER_NO_REFS, via long_plan_check) and by the build's reference binding
    "grammar.figures_allowed": ["figures_allowed"],
    "grammar.every_scene_in_motion": ["every_scene_in_motion"],
    "grammar.scene_seconds": ["scene_seconds"],
    "grammar.crossfade_seconds_max": ["crossfade_seconds_max"],
    "grammar.image_repeat_gap_seconds_min": ["image_repeat_gap"],
    "grammar.burned_captions": ["no_burned_captions"],
    "grammar.caption_track": ["caption_track"],
    "grammar.srt_coverage_of_speech_min": ["srt_coverage_of_speech"],
    "grammar.srt_cue_seconds_median": ["srt_cue_seconds_median"],
    "grammar.srt_cue_chars_max": ["srt_cue_chars_max"],
    "grammar.srt_cue_words_max": ["srt_cue_words_max"],
    "grammar.scripture_card_only_while_read": ["scripture_card_only_while_read"],
    "grammar.cta_mid_video_max": ["cta_count"],
    "grammar.cta_seconds_max": ["cta_short_and_not_early"],
    "grammar.cta_first_start_seconds_min": ["cta_short_and_not_early"],
    "grammar.persistent_overlays_allowed": ["persistent_overlays_only_brand"],
    "grammar.ai_video_picture_share_max": ["ai_video_picture_share"],
    "grammar.ai_video_clip_checks": ["ai_video_clip_checks"],
}
KEEPER = "keeper"
# story-qa-criteria-v4 (owner, 2026-10-27, R1-R4): v3's rows, the ai_video row also judging Pavo's kept speech, and the
# rows v4 adds. A plan is measured by v4 only when it declares it (long_plan_check.criteria_version).
STORY_V4 = "story-qa-criteria-v4"
STORY_V4_ROWS = {**STORY_V3_ROWS,
                 "rights.ai_video": ["ai_video_source_and_licence", "pavo_speech_clip_checks"],
                 "speech.asr_model": ["asr_model_pinned"],
                 "rights.fallback_sources": ["fallback_shots"],
                 "grammar.ai_video_speech_checks": ["pavo_speech_clip_checks"],
                 "grammar.spoken_audio_mix": ["spoken_audio_mix"],
                 "grammar.fallback_shots": ["fallback_shots"]}
# the owner's arc-01 exception (28/10): v4's rows; only fallback_shots reads its widened fallback rule
STORY_V4X = "story-qa-criteria-v4-owner-exception-arc01"
STORY_ROWS = {STORY_V3: STORY_V3_ROWS, STORY_V4: STORY_V4_ROWS, STORY_V4X: STORY_V4_ROWS}
KEEPER_BEATS = ("keeper_promise", "keeper_insight", "keeper_close")


def row_states(checks, rows=STORY_V3_ROWS):
    """PASS / FAIL / UNKNOWN for each row from its checks (True / False / absent or None)."""
    out = {}
    for row, names in rows.items():
        values = [checks.get(n) for n in names]
        out[row] = "FAIL" if any(v is False for v in values) else (
            "PASS" if values and all(v is True for v in values) else "UNKNOWN")
    return out


def approved_characters(path=CHARACTERS):
    try:
        reg = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return {k for k, v in (reg.get("characters") or {}).items() if isinstance(v, dict) and v.get("status") == "APPROVED"}


def is_keeper(hold):
    return hold.get("shot_kind") == KEEPER or KEEPER in (hold.get("characters") or [])


def figures_allowed(manifest, approved):
    """grammar.figures_allowed on the manifest's holds: every named figure an APPROVED characters.json entry, the
    Keeper only in his own beats, God never a figure; None (UNKNOWN) when the registry cannot be read or a hold does
    not say who is on screen."""
    if approved is None or any(not isinstance(h.get("characters"), list) for h in manifest["holds"]):
        return None
    for h in manifest["holds"]:
        who = set(h["characters"])
        if "god" in who or not who <= approved:
            return False
        if is_keeper(h) and h.get("beat") not in KEEPER_BEATS:
            return False
    return True


def first_shot(criteria, manifest, first_word):
    """grammar.first_shot: the first hold is the acted cold open (beat cold_open, no title card, never the Keeper),
    and the first voiced sentence is a character's or God's (never the Keeper or the narrator), heard within
    first_word_onset_seconds_max."""
    holds, sents = manifest["holds"], manifest.get("sentences") or []
    if not holds or not sents:
        return False
    h, s = holds[0], min(sents, key=lambda x: x["start"])
    speaker = s.get("speaker")
    return (h.get("beat") == "cold_open" and not h.get("title_card") and not is_keeper(h) and h["start"] <= 1e-6
            and bool(speaker) and speaker != KEEPER
            and first_word is not None and first_word <= criteria["speech"]["first_word_onset_seconds_max"])


def overlays_allowed(recorded, allowed):
    """grammar.persistent_overlays_allowed (story v3): True when every recorded overlay is in the allowed list (an
    empty list included), False on any other overlay or a value that is not a list, None (UNKNOWN) when the manifest
    does not record its overlays."""
    if recorded is None:
        return None
    return isinstance(recorded, list) and all(o in allowed for o in recorded)


def ai_clip_checks(manifest, ai):
    """grammar.ai_video_clip_checks: every Pavo clip records clip_check PASS, every talking clip lipsync_check
    PASS, every God voice-over clip face_check PASS (lipsync_check --faces, no face). None when no clip is listed."""
    clips = [c for c in manifest.get("clips") or [] if c.get("source") == ai["source"]]
    if not clips:
        return None
    return all(c.get("clip_check") == "PASS"
               and (not c.get("talking") or c.get("lipsync_check") == "PASS")
               and (c.get("voiceover") != "god" or c.get("face_check") == "PASS") for c in clips)


def repeat_gaps(manifest):
    """The seconds between two holds of one picture (story QA image_repeat_gap_seconds_min). A hold's `image` is
    `<source shot>#<src_start>` (long_build); E139: a fallback is keyed by what it shows, its sha256, not by its shot,
    so one still or library clip approved for two shots is a repeat: a still is one picture whatever part is shown,
    a footage clip one picture per part. A Pavo clip keeps its shot key (a window shows another part of it)."""
    pic = {}
    for c in manifest.get("clips") or []:
        if c.get("source") == "footage" and c.get("source_sha256"):
            pic[c.get("id")] = (f"footage:{c['source_sha256']}", True)
    for sid, im in (manifest.get("images") or {}).items():
        if isinstance(im, dict) and im.get("sha256"):
            pic[sid] = (f"still:{im['sha256']}", False)

    def key(h):
        src, _, part = str(h["image"]).partition("#")
        if src not in pic:
            return h["image"]
        k, by_part = pic[src]
        return f"{k}#{part}" if by_part else k

    last_seen, gaps = {}, []
    for h in manifest["holds"]:
        k = key(h)
        if k in last_seen:
            gaps.append(h["start"] - last_seen[k])
        last_seen[k] = h["end"]
    return gaps


def grammar_checks_story_v3(criteria, manifest, script=None, words=None, first_word=None, duration=None,
                            base=None, approved=None):
    """story-qa-criteria-v3 (owner, 2026-10-26; Pavo freed, no real-footage minimum, 2026-10-27): the acted
    Bible-story long. v1's title card, figure ban and footage share are gone; the v3 rows are the acted cold open,
    approved figures, AI share up to 1.0 with each clip's checks, and the uploaded .srt track (no burned captions).
    The manifest (the long's build, LONG_DESIGN.md slice 3) carries, beside v4's fields: holds[].beat,
    holds[].characters, holds[].shot_kind; sentences[].speaker on spoken lines; clips[] with source, licence, model,
    upscaler, audio, vetting, credit, sha256, clip_check, talking, lipsync_check, voiceover, face_check;
    burned_captions false; caption_track (captions.track_record). A value None is UNKNOWN (evidence absent)."""
    import captions
    g, r = criteria["grammar"], criteria["rights"]
    ai = r["ai_video"]
    holds = manifest["holds"]
    inner = [h["end"] - h["start"] for h in holds[:-1]] or [holds[0]["end"] - holds[0]["start"]]
    gaps = repeat_gaps(manifest)
    seg_end = {}
    for s in manifest.get("sentences") or []:
        seg_end[s.get("segment")] = max(seg_end.get(s.get("segment"), 0.0), s["end"])
    cta = manifest.get("cta", [])
    allowed = set(r["allowed_model_licences"])
    models = [m for i in (manifest.get("images") or {}).values() for m in i["models"].values()]
    clips = {c.get("id"): c for c in manifest.get("clips") or []}
    span = sum(h["end"] - h["start"] for h in holds)
    shown = [(h["end"] - h["start"], h["image"].partition("#")[0]) for h in holds if h.get("kind") == "footage"]
    is_ai = {i for i, c in clips.items() if c.get("source") == ai["source"] or c.get("licence") == ai["licence"]}
    used = {i for _, i in shown}
    flicences = set(r["allowed_footage_licences"])
    checks = {
        "first_shot_cold_open": first_shot(criteria, manifest, first_word),
        "figures_allowed": figures_allowed(manifest, approved),
        "every_scene_in_motion": all(h.get("motion") for h in holds),
        "scene_seconds": all(within(x, g["scene_seconds"]) for x in inner)
                         and holds[-1]["end"] - holds[-1]["start"] >= g["scene_seconds"][0],
        "crossfade_seconds_max": manifest.get("crossfade_seconds", 99) <= g["crossfade_seconds_max"],
        "image_repeat_gap": all(x >= g["image_repeat_gap_seconds_min"] for x in gaps),
        "no_burned_captions": manifest.get("burned_captions") is g["burned_captions"] and not manifest.get("captions"),
        "scripture_card_only_while_read": all(c["end"] <= seg_end.get(c["segment"], -1) + 1e-6 and c["end"] > c["start"]
                                              for c in manifest.get("scripture_cards", [])),
        "cta_count": len(cta) <= g["cta_mid_video_max"],
        "cta_short_and_not_early": all(c["end"] - c["start"] <= g["cta_seconds_max"]
                                       and c["start"] >= g["cta_first_start_seconds_min"] for c in cta),
        # v3's key is an allowed list: every overlay recorded must be in it ([] passes); not recorded is UNKNOWN
        "persistent_overlays_only_brand": overlays_allowed(manifest.get("persistent_overlays"),
                                                           g["persistent_overlays_allowed"]),
        "images_open_licence_with_revision": (bool(models) or all(h.get("kind") == "footage" for h in holds))
                                             and all(str(m.get("license")).lower() in allowed and m.get("revision")
                                                     for m in models),
        "footage_licensed_vetted_and_credited": bool(clips) and used <= set(clips) and all(
            c.get("licence") in flicences and c.get("vetting") == r["footage_vetting_required"] and c.get("credit")
            and c.get("sha256") for c in clips.values()),
        "ai_video_source_and_licence": all(clips[i].get("source") == ai["source"] and clips[i].get("licence") == ai["licence"]
                                           and clips[i].get("model") == ai["model"]
                                           and clips[i].get("upscaler") == ai["upscaler"]
                                           and clips[i].get("audio") == ai["audio"]
                                           and clips[i].get("vetting") == ai["vetting_required"] for i in is_ai),
        "ai_video_picture_share": span > 0 and sum(t for t, i in shown if i in is_ai) / span <= g["ai_video_picture_share_max"],
        "ai_video_clip_checks": ai_clip_checks(manifest, ai),
    }
    # the .srt track: the one publish_video uploads (captions.manifest_srt), its record, file and v3's caption rows
    track = manifest.get("caption_track")
    if not isinstance(track, dict) or not manifest.get("sentences"):
        for k in ("caption_track", "srt_coverage_of_speech", "srt_cue_seconds_median", "srt_cue_chars_max",
                  "srt_cue_words_max"):
            checks[k] = False
        return checks, {"caption_track": "CAPTION_TRACK_MISSING"}
    text = captions.manifest_srt(manifest)
    script_text = " ".join(s["text"] for s in (script or {}).get("segments", []))
    rows = captions.long_track(text, manifest["sentences"], script_text, g, words, duration)
    recorded = captions.manifest_problems(manifest, base)
    checks["caption_track"] = rows["caption_track"][0] and not recorded and track.get("burned") is False
    checks["srt_coverage_of_speech"] = rows["srt_coverage_of_speech_min"][0]
    checks["srt_cue_seconds_median"] = rows["srt_cue_seconds_median"][0]
    checks["srt_cue_chars_max"] = rows["srt_cue_chars_max"][0]
    checks["srt_cue_words_max"] = rows["srt_cue_words_max"][0]
    return checks, {"caption_track": {**rows["caption_track"][1], "recorded_problems": recorded[:5]},
                    **{k: v[1] for k, v in rows.items() if k != "caption_track"}}


def grammar_checks_story_v4(criteria, manifest, script=None, words=None, first_word=None, duration=None,
                            base=None, approved=None, asr_sha256=None):
    """story-qa-criteria-v4 (owner, 2026-10-27): every v3 row unchanged, with
    - rights.ai_video: a Pavo clip keeps its speech (audio = the kept value) only with its speech checks PASS, and a
      non-spoken one has its audio removed (audio_silent_shots); source, licence, model, upscaler and vetting as v3;
    - speech.asr_model: the ASR that measured the words is the pinned medium.en (its model.bin sha256);
    - fallback_sources / fallback_shots: every licensed-footage or still clip sits on a shot with no character and no
      speech, APPROVED; a footage clip under the frozen licence list and credited, a still's model licence recorded;
    - spoken_audio_mix: with any kept speech, one gain per speech clip within clip_gain_db_max, fades within
      audio_crossfade_seconds_max, a continuous ambience bed and the owned music."""
    g, r = criteria["grammar"], criteria["rights"]
    ai = r["ai_video"]
    checks, measures = grammar_checks_story_v3(criteria, manifest, script, words, first_word, duration, base, approved)
    clips = manifest.get("clips") or []
    pavo = [c for c in clips if c.get("source") == ai["source"]]
    kept = [c for c in pavo if c.get("audio") == ai["audio"]]
    checks["ai_video_source_and_licence"] = all(
        c.get("licence") == ai["licence"] and c.get("model") == ai["model"] and c.get("upscaler") == ai["upscaler"]
        and c.get("vetting") == ai["vetting_required"] and c.get("audio") in (ai["audio"], ai["audio_silent_shots"])
        for c in pavo)
    checks["pavo_speech_clip_checks"] = all(c.get("speech_checks") == "PASS" for c in kept)
    fallbacks = [c for c in clips if c.get("source") in ("footage", "still")]
    holds = {h.get("shot"): h for h in manifest.get("holds") or []}
    spoken = {s.get("shot") for s in manifest.get("spoken_shots") or []}
    flic, mlic = set(r["allowed_footage_licences"]), {x.lower() for x in r["allowed_model_licences"]}
    exception = criteria.get("version") == STORY_V4X

    def person_or_voice_ok(c):
        """v4: a fallback shows no character and speaks no line. The owner's arc-01 exception: a still made by Pavo
        with the characters' approved references (the build records character_refs from the approval it checked)
        may show them, and a spoken shot may carry the Kokoro voice over such a still."""
        if exception and c["source"] == "still" and c.get("character_refs") is True:
            return c.get("id") not in spoken or c.get("voice") == "kokoro"
        return not (holds.get(c.get("id")) or {}).get("characters") and c.get("id") not in spoken

    def licence_ok(c):
        if c["source"] == "footage":
            return c.get("licence") in flic and bool(c.get("credit"))
        return str(c.get("licence")).lower() in mlic or (
            exception and c.get("character_refs") is True and c.get("licence") == ai["licence"])

    checks["fallback_shots"] = all(
        c.get("vetting") == "APPROVED" and c.get("sha256") and person_or_voice_ok(c) and c.get("audio") == "removed"
        and licence_ok(c) for c in fallbacks)
    if exception:   # a Pavo character still is owner-owned output, judged by fallback_shots, not the open-model row
        models = [m for i in (manifest.get("images") or {}).values() if not i.get("pavo_still")
                  for m in i["models"].values()]
        checks["images_open_licence_with_revision"] = bool(manifest.get("images")) and all(
            str(m.get("license")).lower() in mlic and m.get("revision") for m in models) and all(
            m.get("revision") for i in (manifest.get("images") or {}).values() if i.get("pavo_still")
            for m in i["models"].values())
    # v3's footage row reads every clip as footage; a still is an image (images_open_licence_with_revision)
    used = {h["image"].partition("#")[0] for h in manifest.get("holds") or [] if h.get("kind") == "footage"}
    movie = [c for c in clips if c.get("source") != "still"]
    checks["footage_licensed_vetted_and_credited"] = bool(movie) and used <= {c.get("id") for c in clips} and all(
        c.get("licence") in flic and c.get("vetting") == r["footage_vetting_required"] and c.get("credit")
        and c.get("sha256") for c in movie)
    mix = manifest.get("spoken_audio_mix") or {}
    sm, sc = g["spoken_audio_mix"], ai["speech_checks"]
    gains = mix.get("per_clip_gain_db") or {}
    checks["spoken_audio_mix"] = not kept or (
        set(gains) >= {c.get("id") for c in kept}
        and all(isinstance(v, (int, float)) and v <= sc["clip_gain_db_max"] for v in gains.values())
        and isinstance(mix.get("audio_crossfade_seconds"), (int, float))
        and mix["audio_crossfade_seconds"] <= sm["audio_crossfade_seconds_max"]
        and bool(mix.get("ambience_bed")) and bool(mix.get("music")))
    asr = criteria["speech"]["asr_model"]["model_bin_sha256"]
    checks["asr_model_pinned"] = None if asr_sha256 is None else asr_sha256 == asr
    return checks, measures


def scripture_kjv_exact(script):
    """rights.script_original_with_public_domain_scripture_only, read again on the script that was voiced: every
    referenced quotation is the KJV word for word (bible/kjv_check.py, the same check script_check runs)."""
    if str(KJV_CHECK) not in sys.path:
        sys.path.insert(0, str(KJV_CHECK))
    import kjv_check
    return not kjv_check.script_problems(script or {})


def main(video, manifest_path, script_path, criteria_path, yamnet, whisper, out):
    import av_profile
    import av_semantic
    from qualify_semantic import wer
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
    elif criteria["version"] in (STORY_V4, STORY_V4X):
        # owner 27/10: v3's rows plus Pavo's kept speech, the pinned ASR, the fallback shots and the spoken mix
        model_bin = Path(whisper) / "model.bin"
        v3, srt_measures = grammar_checks_story_v4(criteria, manifest, script, words, first, duration,
                                                   Path(manifest_path).parent, approved_characters(),
                                                   av_semantic.sha256(model_bin) if model_bin.is_file() else None)
        checks.update(v3)
        checks["scripture_kjv_exact"] = scripture_kjv_exact(script)
    elif criteria["version"] == STORY_V3:
        # the acted Bible-story long: every v3 row through STORY_V3_ROWS, the .srt track measured against the
        # script and the words heard in the audio
        v3, srt_measures = grammar_checks_story_v3(criteria, manifest, script, words, first, duration,
                                                   Path(manifest_path).parent, approved_characters())
        checks.update(v3)
        checks["scripture_kjv_exact"] = scripture_kjv_exact(script)
    else:
        grammar = {"pilot-qa-criteria-v3": grammar_checks_v3, "pilot-qa-criteria-v4": grammar_checks_v4,
                   "story-qa-criteria-v1": grammar_checks_story_v1}
        checks.update(grammar.get(criteria["version"], grammar_checks)(criteria, manifest))
    checks["music_owned"] = manifest["music"]["sha256"] == OWNED_MUSIC_SHA256
    checks["voice_model_pinned"] = manifest["voice"]["voice_id"] == "am_michael"
    # numpy bools are not JSON serializable; under v3 None stays None (UNKNOWN: evidence absent, never a pass)
    checks = {k: (None if v is None and criteria["version"] in STORY_ROWS else bool(v)) for k, v in checks.items()}
    result = {"version": "pilot-qa-v1", "pilot_id": manifest["pilot_id"], "output_sha256": manifest["output_sha256"],
              "status": "PASS" if all(v is True for v in checks.values()) else "FAIL", "checks": checks,
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
    if criteria["version"] in STORY_ROWS:
        result["rows"] = row_states(checks, STORY_ROWS[criteria["version"]])
        result["measurements"]["srt"] = srt_measures
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"status": result["status"], "failed": [k for k, ok in checks.items() if not ok],
                      **{k: result["measurements"][k] for k in ("duration_seconds", "wer_vs_script",
                                                                "accepted_words_per_minute", "speech_presence")}}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:8]))
