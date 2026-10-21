#!/usr/bin/env python3
"""Closed pilot-006 correction: source pins, real measurements and release barrier.

No provider is imported here. Measurements establish clocks/integrity, not
semantic recognition of captions, phonemes or convincing atmospheric motion.
The unchanged watched review remains necessary. A COMPLETE negative is durable,
not eligible, and the canonical preflight prevents another persisted attempt.
"""
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Only plan-independent primitives: no 005 validators or media measurement path.
from shorts_edit_plan import (EvidenceError, require, exact, number, hash_file,
                              read_json, atomic_json, acoustic_measurements, _run,
                              utc_date, _disable)
from shorts_select import validate_candidate
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "publish"))
import shorts_prerequisite
import owner_quality_policy

CANONICAL_PILOT = Path(__file__).resolve().parent / "pilot-006"
PLAN_SHA256 = "1c52034ce611b8a30c9d92ce22e9b6ce8f7cbff14b803a44ff8e7d1eb4991c57"
HISTORY_SHA256 = "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677"
REJECTED_SHA256 = "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
TARGET_SLOT = "2026-10-21T14:00:00Z"
LEAD_DEADLINE = "2026-10-21T13:15:00Z"
KIND = "pilot-006-correction-v1"
MEDIA_FILE = "correction-media-checks.json"
HASH = re.compile(r"[0-9a-f]{64}\Z")
RUBRIC = ("hook_in_first_2s", "captions_readable_and_synced", "text_clear_of_shorts_ui", "picture_quality",
          "edit_rhythm", "audio_clarity", "stands_alone", "ending_and_loop", "policy_safe")
QA_CHECKS = {"decode_clean", "one_h264_1080x1920", "fps_30", "one_aac_stereo_48k", "duration", "loudness", "true_peak"}
# Independent code-owned schema, not loaded from a mutable production document.
EXPECTED_PLAN = json.loads(r'''{
  "version": "shorts-006-correction-plan-v1",
  "source_pilot": "pilot-006",
  "source_baseline_sha": "582ff607089f9accb91a8a4d1a8c2fe6f4e47408",
  "source_sha256": {
    "script": "1006e8bec3bc8c43dffe6e5ad1d26e257ceaea5fbe0eb12fa414b9c059d10cad",
    "timeline": "73357bd61adf13f004967f0a2b2ef3e16569fb2cd344eb419e3d1fcabf1af7a2",
    "inputs": "07a75a6b6849ed7ada9fc621a573b947689effc458693d6889ce3bc8568f514b",
    "images": "f2e32a9a210ebd3d4f93d1d6fb9254ee2241d416784c9d31343c8f02138bb695",
    "long_manifest": "0d40777f7dd2a84db9615bd148df8c3173e2e46b9f7b32418e7677392e49a2bb",
    "long_review": "e68b0ede86b2837d6070a18f20a17ad097be20d0636c427a4214c0f49324a00f"
  },
  "history": {
    "file": "correction-history.json",
    "sha256": "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677",
    "rejected_output_sha256": "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
  },
  "voice": {
    "asset": "pilot-006-voice-sha256-d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d.flac",
    "sha256": "d417a273a5e694e49c2eba25cb31a4afd175fa9bdf90c756b7e511ea8277861d"
  },
  "music": {
    "asset": "original-rest-music.lossless.flac",
    "sha256": "1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c",
    "source_start": 2511.607
  },
  "candidate": {
    "start": 1311.607,
    "end": 1346.297,
    "hook": "You can let go.",
    "title": "His Peace Stands Watch Over You",
    "reference": "Philippians 4:6-7 (KJV)"
  },
  "audio": {
    "source_start": 1311.607,
    "source_end": 1346.477,
    "source_sample_rate": 24000,
    "source_channels": 1,
    "source_samples": 836880,
    "output_sample_rate": 48000,
    "resampled_source_samples": 1673760,
    "padding_samples": 54240,
    "output_samples": 1728000,
    "fade_start": 34.87,
    "fade_seconds": 1.13
  },
  "tail_seconds": 1.13,
  "narrative_tail_seconds": 1.31,
  "output_seconds": 36.0,
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "transition": {
    "type": "fade",
    "seconds": 0.5
  },
  "scenes": [
    {
      "image_id": "bg-still-water-night",
      "asset": "pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png",
      "sha256": "7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2",
      "nominal_start": 0.0,
      "nominal_end": 18.0,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259006,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1
      }
    },
    {
      "image_id": "bg-healing-garden",
      "asset": "pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png",
      "sha256": "97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070",
      "nominal_start": 18.0,
      "nominal_end": 36.0,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259007,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1
      }
    }
  ],
  "release": {
    "target_slot": "2026-10-21T14:00:00Z",
    "release_deadline": "2026-10-21T13:15:00Z",
    "minimum_overall": 9.0,
    "file": "short-00.mp4"
  }
}
''')


def validate_plan_schema(plan):
    require(exact(plan, EXPECTED_PLAN), "INVALID_CORRECTION_PLAN")
    return deepcopy(plan)


def safe_path(path, *, directory=False):
    path = Path(path)
    require(".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), "UNSAFE_PATH")
    require(path.is_dir() if directory else path.is_file(), "PATH_MISSING")
    return path


def _plan_file(path):
    plan, digest = read_json(safe_path(path))
    require(digest == PLAN_SHA256, "PLAN_RAW_SHA256_MISMATCH")
    return validate_plan_schema(plan)


def historical_failed_hashes(path):
    history, digest = read_json(safe_path(path))
    require(digest == HISTORY_SHA256, "HISTORY_RAW_SHA256_MISMATCH")
    require(type(history) is dict and history.get("source_pilot") == "pilot-006"
            and type(history.get("shorts")) is list and len(history["shorts"]) == 3, "HISTORY_SCHEMA")
    failed = set()
    for record in history["shorts"]:
        require(type(record) is dict and type(record.get("review")) is dict
                and type(record.get("sha256")) is str and HASH.fullmatch(record["sha256"]), "HISTORY_SCHEMA")
        if record["review"].get("status") == "FAIL":
            failed.add(record["sha256"])
    require(REJECTED_SHA256 in failed, "HISTORICAL_FAIL_MISSING")
    return frozenset(failed)


def _sources(pilot_dir):
    pilot = safe_path(pilot_dir, directory=True)
    require(pilot.resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
    paths = {"script": "script.json", "timeline": "out/timeline.json", "inputs": "shorts/inputs.json",
             "images": "images.json", "long_manifest": "out/manifest.json", "long_review": "out/review.json"}
    docs = {}
    for key, relative in paths.items():
        docs[key], digest = read_json(safe_path(pilot / relative))
        require(digest == EXPECTED_PLAN["source_sha256"][key], "SOURCE_PIN_MISMATCH")
    require(not shorts_prerequisite.problems(pilot), "LONG_NOT_QUALIFIED")
    return docs


def _contract():
    plan = _plan_file(CANONICAL_PILOT / "shorts/correction-plan.json")
    failed = historical_failed_hashes(CANONICAL_PILOT / "shorts/correction-history.json")
    docs = _sources(CANONICAL_PILOT)
    return plan, failed, docs


def preflight(pilot_dir, plan_path, history_path):
    """One persisted attempt, not distributed exactly-once after an unknown run."""
    pilot = safe_path(pilot_dir, directory=True)
    require(pilot.resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
    require(safe_path(plan_path).resolve() == (pilot / "shorts/correction-plan.json").resolve(), "PLAN_PATH_MISMATCH")
    require(safe_path(history_path).resolve() == (pilot / "shorts/correction-history.json").resolve(), "HISTORY_PATH_MISMATCH")
    plan = _plan_file(plan_path)
    historical_failed_hashes(history_path)
    require(hash_file(safe_path(pilot / "shorts/shorts.json")) == HISTORY_SHA256, "CANONICAL_ATTEMPT_ALREADY_CHANGED")
    _sources(pilot)
    return plan


def validate_plan(plan, timeline, script, inputs, *, raw_sha256):
    plan = validate_plan_schema(plan)
    require(exact(raw_sha256, {k: plan["source_sha256"][k] for k in ("timeline", "script", "inputs")}), "INPUT_SHA256_MISMATCH")
    require(type(script) is dict and script.get("pilot_id") == "pilot-006", "SOURCE_PILOT_MISMATCH")
    require(type(inputs) is dict and inputs.get("voice_asset") == plan["voice"]["asset"]
            and inputs.get("voice_sha256") == plan["voice"]["sha256"], "VOICE_INPUT_MISMATCH")
    try:
        refs = {s["id"]: s.get("reference") for s in script["segments"]}
        moment, reason = validate_candidate(timeline["sentences"], refs, plan["candidate"])
        require(reason is None, "SOURCE_CANDIDATE_REJECTED")
        require(len(moment["sentences"]) == 7 and moment["sentences"] == timeline["sentences"][314:321], "SOURCE_SENTENCE_MISMATCH")
        require(moment["start"] == 1311.607 and moment["end"] == 1346.297
                and moment["reference"] == plan["candidate"]["reference"], "SOURCE_INTERVAL_MISMATCH")
        require(moment["sentences"][0]["text"] == "You can let go."
                and moment["sentences"][0]["end"] == 1313.228
                and timeline["sentences"][321]["start"] == 1347.677, "SOURCE_BOUNDARY_MISMATCH")
        require(moment["segments"] == ["sleep-reflect-121", "sleep-philippians-4", "sleep-reflect-phil"], "SOURCE_SEGMENT_MISMATCH")
        require(all(s["image_id"] in script["backgrounds"] for s in plan["scenes"]), "IMAGE_MAPPING_MISMATCH")
    except (KeyError, TypeError, IndexError, AttributeError):
        raise EvidenceError("MALFORMED_SOURCE") from None
    return {"chosen": [deepcopy(moment)], "selection_mode": "EDITORIAL_PLAN", "rubric_model": None,
            "input_sha256": deepcopy(raw_sha256), "edit_plan": plan}


def main(plan_path, timeline_path, script_path, inputs_path, out_path):
    preflight(CANONICAL_PILOT, plan_path, CANONICAL_PILOT / "shorts/correction-history.json")
    plan = _plan_file(plan_path)
    timeline, th = read_json(safe_path(timeline_path))
    script, sh = read_json(safe_path(script_path))
    inputs, ih = read_json(safe_path(inputs_path))
    prepared = validate_plan(plan, timeline, script, inputs, raw_sha256={"timeline": th, "script": sh, "inputs": ih})
    atomic_json(out_path, prepared)
    return prepared


def frame_plan(plan):
    validate_plan_schema(plan)
    return {"expected_frame_count": 1080, "fps": 30, "scene_frame_spans": [
        {"image_id": "bg-still-water-night", "start_frame": 0, "end_frame": 548,
         "nominal_start_frame": 0, "nominal_end_frame": 540},
        {"image_id": "bg-healing-garden", "start_frame": 533, "end_frame": 1080,
         "nominal_start_frame": 540, "nominal_end_frame": 1080}]}


def _record(spec):
    require(type(spec) is dict and type(spec.get("shorts")) is list and len(spec["shorts"]) == 1
            and type(spec["shorts"][0]) is dict, "EXACTLY_ONE_SHORT_REQUIRED")
    record = spec["shorts"][0]
    require(record.get("file") == "short-00.mp4", "OUTPUT_FILENAME_MISMATCH")
    return record


def _no_mixed_authority(value):
    if type(value) is dict:
        require(not ({"review_recovery", "review_recovery_execution", "owner_exception"} & value.keys()), "MIXED_AUTHORITY")
        for item in value.values():
            _no_mixed_authority(item)
    elif type(value) is list:
        for item in value:
            _no_mixed_authority(item)


def _bind_record(spec, plan, record, output_hash, docs):
    _no_mixed_authority(spec)
    require(type(output_hash) is str and HASH.fullmatch(output_hash), "INVALID_OUTPUT_SHA256")
    require(spec.get("source_pilot") == "pilot-006" and exact(spec.get("edit_plan"), plan), "PLAN_BINDING_MISMATCH")
    require(record.get("sha256") == output_hash and output_hash != REJECTED_SHA256, "OUTPUT_SHA256_MISMATCH")
    for key, expected in (("source_start", 1311.607), ("source_end", 1346.297), ("seconds", 36.0)):
        require(number(record.get(key)) and abs(record[key] - expected) <= (0.011 if key == "seconds" else 0), "RECORD_INTERVAL_MISMATCH")
    require(record.get("hook_mode") == "caption_only" and record.get("hook_shown") is True, "HOOK_MODE_MISMATCH")
    for key in ("hook", "title", "reference"):
        require(record.get(key) == plan["candidate"][key], "EDITORIAL_IDENTITY_MISMATCH")
    require(exact(record.get("scenes"), [s["image_id"] for s in plan["scenes"]])
            and record.get("figure") is False and record.get("parallax") is False, "RECORD_SCENES_MISMATCH")
    require(exact(record.get("render_plan"), frame_plan(plan)), "RENDER_PLAN_MISMATCH")
    selected = validate_plan(plan, docs["timeline"], docs["script"], docs["inputs"],
                             raw_sha256={k: plan["source_sha256"][k] for k in ("timeline", "script", "inputs")})["chosen"][0]
    require(record.get("text") == selected["text"] and exact(record.get("segments"), selected["segments"]), "SOURCE_TEXT_MISMATCH")


def _probe(path):
    result = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    require(not result.stderr.strip(), "MEDIA_PROBE_FAILED")
    return json.loads(result.stdout)


def source_durations(voice_flac, music, plan):
    """Called by the producer before any encoding, as well as by measurement."""
    validate_plan_schema(plan)
    voice, bed = _probe(safe_path(voice_flac)), _probe(safe_path(music))
    require(len(voice["streams"]) == 1 and voice["streams"][0]["codec_type"] == "audio", "VOICE_STREAM_MISMATCH")
    stream = voice["streams"][0]
    require(int(stream["sample_rate"]) == 24000 and stream["channels"] == 1, "VOICE_FORMAT_MISMATCH")
    vs, ms = float(voice["format"]["duration"]), float(bed["format"]["duration"])
    require(number(vs) and vs >= plan["audio"]["source_end"], "VOICE_SOURCE_TRUNCATED")
    require(number(ms) and ms >= plan["music"]["source_start"] + 36, "MUSIC_SOURCE_TRUNCATED")
    return {"voice_seconds": vs, "music_seconds": ms, "voice_sample_rate": 24000, "voice_channels": 1}


def _black_intervals(path, count):
    # Frame metadata catches a single final black frame, which blackdetect's
    # textual summary alone can miss. Integer frame clocks avoid %.6g rounding.
    result = _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-xerror", "-err_detect", "explode",
                   "-i", str(path), "-map", "0:v:0", "-vf",
                   "blackdetect=d=0.03333333333333333:pix_th=0.02:pic_th=0.99,metadata=mode=print",
                   "-an", "-sn", "-dn", "-f", "null", "-"])
    intervals, start, frame, previous = [], None, None, -1
    for line in result.stderr.decode("utf-8", errors="replace").splitlines():
        header = re.search(r"\bframe:(\d+)\s+pts:\s*-?\d+\s+pts_time:", line)
        if header:
            frame = int(header[1])
            require(previous < frame < count, "BLACKDETECT_PARSE_FAILED")
            previous = frame
        if "lavfi.black_start=" in line or "lavfi.black_end=" in line:
            tag = re.search(r"lavfi.black_(start|end)=([\d.eE+-]+)\s*$", line)
            require(tag is not None and frame is not None, "BLACKDETECT_PARSE_FAILED")
            reported = float(tag[2])
            require(number(reported) and math.floor(reported * 30 + .5) == frame, "BLACKDETECT_PARSE_FAILED")
            if tag[1] == "start":
                require(start is None, "BLACKDETECT_PARSE_FAILED")
                start = frame
            else:
                require(start is not None and frame > start, "BLACKDETECT_PARSE_FAILED")
                intervals.append({"start_frame": start, "end_frame": frame})
                start = None
    if start is not None:
        intervals.append({"start_frame": start, "end_frame": count})
    return intervals


def _audio_packets(path, audio_stream):
    require(Fraction(audio_stream["time_base"]) == Fraction(1, 48000), "AUDIO_TIME_BASE_MISMATCH")
    probed = _run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_packets",
                   "-show_entries", "packet=pts,duration,side_data_list", "-of", "json", str(path)])
    require(not probed.stderr.strip(), "AUDIO_PACKET_PROBE_FAILED")
    packets = json.loads(probed.stdout)["packets"]
    require(len(packets) == 1689, "AUDIO_PACKET_COUNT_FAIL")
    for index, packet in enumerate(packets):
        require(type(packet.get("pts")) is int and packet["pts"] == (index - 1) * 1024
                and type(packet.get("duration")) is int
                and packet["duration"] == (512 if index == len(packets) - 1 else 1024), "AUDIO_PACKET_CLOCK_FAIL")
    side = packets[0].get("side_data_list", [])
    skip = [s for s in side if s.get("side_data_type") == "Skip Samples"]
    require(len(skip) == 1 and type(skip[0].get("skip_samples")) is int and skip[0]["skip_samples"] == 1024
            and skip[0].get("discard_padding") == 0, "AUDIO_PRIMING_MISMATCH")
    require(all(not p.get("side_data_list") for p in packets[1:]), "UNEXPECTED_AUDIO_DISCARD_METADATA")
    return {"packet_count": len(packets), "first_pts_samples": packets[0]["pts"], "skip_samples": 1024,
            "last_pts_samples": packets[-1]["pts"], "last_duration_samples": packets[-1]["duration"],
            "packet_clock_continuous": True, "codec_frame_samples": 1024}


def measure_video(path, plan, renderer_plan):
    require(exact(renderer_plan, frame_plan(plan)), "RENDER_PLAN_MISMATCH")
    info = _probe(path)
    video = [s for s in info["streams"] if s["codec_type"] == "video"]
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    require(len(info["streams"]) == 2 and len(video) == len(audio) == 1, "OUTPUT_STREAM_MISMATCH")
    v, a = video[0], audio[0]
    decoded = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries",
                    "frame=best_effort_timestamp_time", "-of", "json", str(path)])
    require(not decoded.stderr.strip(), "FRAME_PROBE_FAILED")
    pts = [float(f["best_effort_timestamp_time"]) for f in json.loads(decoded.stdout)["frames"]]
    require(len(pts) == 1080 and all(number(p) and abs(p - i / 30) <= 1e-6 for i, p in enumerate(pts)), "VIDEO_PTS_FAIL")
    pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0",
                "-vn", "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"])
    require(not pcm.stderr.strip(), "OUTPUT_AUDIO_DECODE_FAILED")
    measured = {"decoded_frame_count": len(pts), "fps": float(Fraction(v["r_frame_rate"])),
                "seconds": float(info["format"]["duration"]), "width": v["width"], "height": v["height"],
                "video_codec": v["codec_name"], "audio_codec": a["codec_name"],
                "audio_sample_rate": int(a["sample_rate"]), "audio_channels": a["channels"],
                "decoded_audio_samples": len(pcm.stdout) // (2 * a["channels"]),
                "presentation_audio_samples": round(int(a["duration_ts"]) * Fraction(a["time_base"]) * 48000),
                "first_pts": pts[0], "last_pts": pts[-1], "pts_uniform": True,
                "audio_packets": _audio_packets(path, a),
                "black_intervals": _black_intervals(path, len(pts)),
                "render_plan": deepcopy(renderer_plan), "status": "PASS"}
    _validate_video(measured, plan)
    return measured


def _validate_video(video, plan):
    keys = {"decoded_frame_count", "fps", "seconds", "width", "height", "video_codec", "audio_codec",
            "audio_sample_rate", "audio_channels", "decoded_audio_samples", "presentation_audio_samples",
            "first_pts", "last_pts", "pts_uniform", "audio_packets", "black_intervals", "render_plan", "status"}
    require(type(video) is dict and video.keys() == keys, "VIDEO_SCHEMA")
    for key, expected in (("decoded_frame_count", 1080), ("width", 1080), ("height", 1920),
                          ("audio_sample_rate", 48000), ("audio_channels", 2), ("presentation_audio_samples", 1728000)):
        require(type(video[key]) is int and video[key] == expected, "VIDEO_FORMAT_FAIL")
    require(video["video_codec"] == "h264" and video["audio_codec"] == "aac", "VIDEO_CODEC_FAIL")
    require(number(video["fps"]) and video["fps"] == 30 and number(video["seconds"])
            and abs(video["seconds"] - 36) <= .011, "VIDEO_DURATION_FAIL")
    require(number(video["first_pts"]) and video["first_pts"] == 0
            and number(video["last_pts"]) and abs(video["last_pts"] - 1079 / 30) <= 1e-6
            and video["pts_uniform"] is True, "VIDEO_PTS_FAIL")
    require(exact(video["audio_packets"], {"packet_count": 1689, "first_pts_samples": -1024,
            "skip_samples": 1024, "last_pts_samples": 1727488, "last_duration_samples": 512,
            "packet_clock_continuous": True, "codec_frame_samples": 1024}), "AUDIO_PACKET_CLOCK_FAIL")
    # AAC has a 1024-sample coded frame but the final packet presents only512.
    # Depending on decoder, raw PCM retains or discards that proven final512;
    # never admit arbitrary extra content or silently trim to manufacture PASS.
    require(type(video["decoded_audio_samples"]) is int and video["decoded_audio_samples"] in (1728000, 1728512), "OUTPUT_PCM_COUNT_FAIL")
    require(type(video["black_intervals"]) is list and not video["black_intervals"], "BLACK_FRAME_DETECTED")
    require(exact(video["render_plan"], frame_plan(plan)) and video["status"] == "PASS", "VIDEO_RENDER_PLAN_FAIL")


def _validate_acoustic(acoustic, plan):
    keys = {"pcm_sample_rate", "window_samples", "active_threshold_dbfs", "leading_inactive_seconds",
            "trailing_inactive_seconds", "first_active_sample", "last_active_sample", "narration_samples", "status"}
    require(type(acoustic) is dict and acoustic.keys() == keys, "ACOUSTIC_SCHEMA")
    require(type(acoustic["pcm_sample_rate"]) is int and acoustic["pcm_sample_rate"] == 48000
            and type(acoustic["window_samples"]) is int and acoustic["window_samples"] == 480
            and number(acoustic["active_threshold_dbfs"]) and acoustic["active_threshold_dbfs"] == -40, "ACOUSTIC_METHOD_MISMATCH")
    first, last, count = (acoustic[k] for k in ("first_active_sample", "last_active_sample", "narration_samples"))
    require(all(type(x) is int for x in (first, last, count)) and count == plan["audio"]["resampled_source_samples"]
            and 0 <= first < last <= count and first % 480 == 0 and (last % 480 == 0 or last == count), "ACOUSTIC_SAMPLE_MISMATCH")
    lead, tail = acoustic["leading_inactive_seconds"], acoustic["trailing_inactive_seconds"]
    require(number(lead) and number(tail) and abs(lead - first / 48000) < 1e-12
            and abs(tail - (count - last) / 48000) < 1e-12 and 0 <= lead <= .3 and 0 <= tail <= .3,
            "ACOUSTIC_ONSET_OR_ENDING_FAIL")
    require(acoustic["status"] == "PASS", "ACOUSTIC_NOT_PASS")


def _editorial_metadata(plan, docs):
    # This is source/renderer metadata, not an OCR or motion-quality claim.
    sentences = docs["timeline"]["sentences"][314:321]
    return {"caption_source_intervals": [{"text": s["text"], "start": round(s["start"] - 1311.607, 3),
                                           "end": round(s["end"] - 1311.607, 3)} for s in sentences],
            "caption_mode": "caption_only", "reference": plan["candidate"]["reference"],
            "motion_profiles": [s["motion_profile"] for s in plan["scenes"]],
            "atmosphere_profiles": [deepcopy(s["atmosphere"]) for s in plan["scenes"]]}


def validate_media_checks(checks, plan, output_hash, *, docs, now_utc=None):
    keys = {"version", "plan_sha256", "history_sha256", "source_sha256", "output_sha256", "source_voice_sha256",
            "source_music_sha256", "source_image_sha256", "source_durations", "measured_at", "acoustic", "video", "editorial_metadata", "status"}
    require(type(checks) is dict and checks.keys() == keys, "MEDIA_CHECKS_SCHEMA")
    require(checks["version"] == "shorts-006-media-checks-v1" and checks["plan_sha256"] == PLAN_SHA256
            and checks["history_sha256"] == HISTORY_SHA256 and checks["output_sha256"] == output_hash, "MEDIA_BINDING_MISMATCH")
    require(exact(checks["source_sha256"], plan["source_sha256"])
            and checks["source_voice_sha256"] == plan["voice"]["sha256"]
            and checks["source_music_sha256"] == plan["music"]["sha256"]
            and exact(checks["source_image_sha256"], {s["image_id"]: s["sha256"] for s in plan["scenes"]}), "MEDIA_SOURCE_HASH_MISMATCH")
    durations = checks["source_durations"]
    require(type(durations) is dict and durations.keys() == {"voice_seconds", "music_seconds", "voice_sample_rate", "voice_channels"}, "SOURCE_DURATION_SCHEMA")
    require(number(durations["voice_seconds"]) and durations["voice_seconds"] >= 1346.477
            and number(durations["music_seconds"]) and durations["music_seconds"] >= 2547.607
            and type(durations["voice_sample_rate"]) is int and durations["voice_sample_rate"] == 24000
            and type(durations["voice_channels"]) is int and durations["voice_channels"] == 1, "SOURCE_DURATION_FAIL")
    measured = utc_date(checks["measured_at"])
    if now_utc is not None:
        now = utc_date(now_utc)
        require(measured <= now and measured.date() == now.date(), "MEDIA_MEASUREMENT_STALE")
    _validate_acoustic(checks["acoustic"], plan)
    _validate_video(checks["video"], plan)
    require(exact(checks["editorial_metadata"], _editorial_metadata(plan, docs)), "EDITORIAL_METADATA_MISMATCH")
    require(checks["status"] == "PASS", "MEDIA_CHECKS_NOT_PASS")


def check_media(work, plan, manifest, voice_flac, music, images_dir, history_path):
    spec, _ = read_json(safe_path(manifest))
    spec = _disable(spec)
    atomic_json(manifest, spec)
    checks = {"version": "shorts-006-media-checks-v1", "status": "FAIL"}
    reason = None
    try:
        record = _record(spec)
        preflight(CANONICAL_PILOT, CANONICAL_PILOT / "shorts/correction-plan.json",
                  CANONICAL_PILOT / "shorts/correction-history.json")
        contract, failed, docs = _contract()
        supplied = validate_plan_schema(plan) if type(plan) is dict else _plan_file(plan)
        require(exact(contract, supplied), "PLAN_BINDING_MISMATCH")
        require(historical_failed_hashes(history_path) == failed, "HISTORY_MISMATCH")
        output = safe_path(Path(manifest).parent / record["file"])
        output_hash = hash_file(output)
        require(output_hash not in failed, "HISTORICAL_EDITORIAL_FAIL_BYTES")
        _bind_record(spec, contract, record, output_hash, docs)
        require(hash_file(safe_path(Path(work) / "timeline.json")) == contract["source_sha256"]["timeline"], "TIMELINE_HASH_MISMATCH")
        sources = {"voice": hash_file(safe_path(voice_flac)), "music": hash_file(safe_path(music))}
        require(sources["voice"] == contract["voice"]["sha256"] and sources["music"] == contract["music"]["sha256"], "AUDIO_SOURCE_HASH_MISMATCH")
        images = {}
        for scene in contract["scenes"]:
            ident = scene["image_id"]
            meta, _ = read_json(safe_path(Path(images_dir) / (ident + ".json")))
            require(meta.get("id") == ident and meta.get("release_asset") == scene["asset"]
                    and meta.get("sha256") == scene["sha256"], "IMAGE_MAPPING_MISMATCH")
            require(type(meta.get("models")) is dict and meta["models"]
                    and all(type(m) is dict and m.get("license") for m in meta["models"].values()), "IMAGE_LICENSE_MISSING")
            images[ident] = hash_file(safe_path(Path(images_dir) / (ident + ".png")))
            require(images[ident] == scene["sha256"], "IMAGE_HASH_MISMATCH")
        durations = source_durations(voice_flac, music, contract)
        pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-ss", "1311.607", "-i", str(voice_flac),
                    "-t", "34.870", "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "48000",
                    "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"])
        require(not pcm.stderr.strip(), "AUDIO_DECODE_FAILED")
        checks = {"version": "shorts-006-media-checks-v1", "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256,
                  "source_sha256": deepcopy(contract["source_sha256"]), "output_sha256": output_hash,
                  "source_voice_sha256": sources["voice"], "source_music_sha256": sources["music"],
                  "source_image_sha256": images, "source_durations": durations,
                  "measured_at": datetime.now(timezone.utc).isoformat(), "acoustic": acoustic_measurements(pcm.stdout),
                  "video": measure_video(output, contract, record["render_plan"]),
                  "editorial_metadata": _editorial_metadata(contract, docs), "status": "PASS"}
        validate_media_checks(checks, contract, output_hash, docs=docs)
        require(hash_file(output) == output_hash and hash_file(voice_flac) == sources["voice"]
                and hash_file(music) == sources["music"], "MEDIA_CHANGED_DURING_MEASUREMENT")
        for ident, digest in images.items():
            require(hash_file(Path(images_dir) / (ident + ".png")) == digest, "IMAGE_CHANGED_DURING_MEASUREMENT")
        preflight(CANONICAL_PILOT, CANONICAL_PILOT / "shorts/correction-plan.json",
                  CANONICAL_PILOT / "shorts/correction-history.json")
    except EvidenceError as error:
        reason = str(error)
    except Exception:
        reason = "MEDIA_MEASUREMENT_ERROR"
    if reason:
        checks["status"] = "FAIL"
    media_file = Path(manifest).parent / MEDIA_FILE
    atomic_json(media_file, checks)
    if type(spec.get("shorts")) is list:
        for rec in spec["shorts"]:
            if type(rec) is dict:
                rec["media_checks"] = deepcopy(checks)
                rec["media_checks_sha256"] = hash_file(media_file)
                rec["media_checks_reason"] = reason
                rec["publish"] = False
    spec["release_status"] = reason or "MEDIA_CHECKS_PASS_PENDING_REVIEW"
    atomic_json(manifest, spec)
    return checks


def _qa_verdict(qa, seconds):
    require(type(qa) is dict and qa.keys() == {"file", "seconds", "lufs", "true_peak_dbtp", "checks", "status"}, "QA_SCHEMA")
    require(type(qa["file"]) is str and Path(qa["file"]).name == "short-00.mp4", "QA_FILE_MISMATCH")
    require(number(qa["seconds"]) and abs(qa["seconds"] - seconds) <= 0.011, "QA_DURATION_MISMATCH")
    checks = qa["checks"]
    require(type(checks) is dict and checks.keys() == QA_CHECKS and all(type(v) is bool for v in checks.values()), "QA_CHECKS_SCHEMA")
    require(qa["status"] in ("PASS", "FAIL"), "QA_STATUS_MALFORMED")
    require(qa["lufs"] is None or number(qa["lufs"]), "QA_LOUDNESS_MALFORMED")
    require(qa["true_peak_dbtp"] is None or number(qa["true_peak_dbtp"]), "QA_PEAK_MALFORMED")
    require(checks["duration"] == (15 <= qa["seconds"] <= 60)
            and checks["loudness"] == (qa["lufs"] is not None and -16 <= qa["lufs"] <= -12)
            and checks["true_peak"] == (qa["true_peak_dbtp"] is not None and qa["true_peak_dbtp"] <= -1), "QA_NUMERIC_MISMATCH")
    require((qa["status"] == "PASS") == all(checks.values()), "QA_FALSE_STATUS")
    return qa["status"]


def _review_verdict(review, output_hash):
    require(type(review) is dict and type(review.get("status")) is str, "REVIEW_SCHEMA")
    status = review["status"]
    if status.startswith("NOT_REVIEWED_"):
        require(re.fullmatch(r"NOT_REVIEWED_[A-Za-z][A-Za-z0-9_]*", status) is not None, "REVIEW_STATUS_MALFORMED")
        if "output_sha256" in review:
            require(review["output_sha256"] == output_hash, "REVIEW_OUTPUT_HASH_MISMATCH")
        return "NOT_REVIEWED"
    require(status in ("PASS", "FAIL"), "REVIEW_STATUS_MALFORMED")
    require(review.get("model") == "gemini-3.8-flash", "UNDESIGNATED_REVIEW_MODEL")
    require(all(number(review.get(k)) and 0 <= review[k] <= 10 for k in (*RUBRIC, "overall")), "REVIEW_SCORE_MALFORMED")
    require(type(review.get("issues")) is list and all(type(i) is str for i in review["issues"])
            and type(review.get("strongest_moment")) is str, "REVIEW_REPORT_MALFORMED")
    calculated = all(review[k] >= 7 for k in RUBRIC) and review["overall"] >= 8
    require((status == "PASS") == calculated, "REVIEW_FALSE_STATUS")
    require(review.get("output_sha256") == output_hash, "REVIEW_OUTPUT_HASH_MISMATCH")
    return status



def _evaluate(spec, actual_output_sha256, now, media, media_hash, contract):
    plan, failed, docs = contract
    record = _record(spec)
    _bind_record(spec, plan, record, actual_output_sha256, docs)
    require(actual_output_sha256 not in failed, "HISTORICAL_EDITORIAL_FAIL_BYTES")
    require(type(media_hash) is str and HASH.fullmatch(media_hash)
            and record.get("media_checks_sha256") == media_hash and exact(record.get("media_checks"), media), "MEDIA_FILE_BINDING_MISMATCH")
    validate_media_checks(media, plan, actual_output_sha256, docs=docs, now_utc=now)
    require(record.get("qa_output_sha256") == actual_output_sha256, "QA_OUTPUT_HASH_MISMATCH")
    qa = _qa_verdict(record.get("qa"), 36.0)
    review = _review_verdict(record.get("review"), actual_output_sha256)
    require(exact(spec.get("review_rubric"), {"items": list(RUBRIC), "pass_item": 7, "pass_overall": 8}), "REVIEW_RUBRIC_MISMATCH")
    previous = record.get("previous_editorial_review")
    require(not (type(previous) is dict and previous.get("status") == "FAIL"
                 and previous.get("output_sha256") in (None, actual_output_sha256)), "PREVIOUS_FAILED_BYTES")
    if qa != "PASS":
        return "QA_FAIL"
    if review != "PASS":
        return "REVIEW_" + review
    if owner_quality_policy.check(record["review"], actual_output_sha256):
        return "OWNER_QUALITY_POLICY_BLOCKED"
    if now > utc_date(LEAD_DEADLINE):
        return "TARGET_SLOT_LEAD_MISSED"
    return "READY"


def finalize_manifest(spec, *, actual_output_sha256, now_utc, media_checks, media_sha256, contract):
    """Internal object validator shared by file finalization and publication binding."""
    guarded = _disable(spec)
    now = utc_date(now_utc)
    final = {"kind": KIND, "status": "ERROR", "source_pilot": "pilot-006", "plan_sha256": PLAN_SHA256,
             "history_sha256": HISTORY_SHA256, "output_sha256": actual_output_sha256,
             "target_slot": TARGET_SLOT, "release_deadline": LEAD_DEADLINE,
             "validated_at": now.isoformat(), "release_status": "MALFORMED_EVIDENCE"}
    guarded["finalization"] = final
    try:
        _no_mixed_authority(spec)
        release = _evaluate(guarded, actual_output_sha256, now, media_checks, media_sha256, contract)
        final["status"] = "COMPLETE"
        final["release_status"] = release
        record = _record(guarded)
        record["publish"] = release == "READY"
        record["release_status"] = release
    except EvidenceError as error:
        final["release_status"] = str(error)
    except Exception:
        final["release_status"] = "MALFORMED_EVIDENCE"
    guarded["release_status"] = final["release_status"]
    return guarded


def finalize_file(manifest, mp4):
    """Revoke first, record ERROR on integrity failure, COMPLETE on real negatives."""
    safe_path(manifest)
    try:
        spec, _ = read_json(manifest)
    except (ValueError, UnicodeError):
        spec = {"shorts": [], "publish": False}
    spec = _disable(spec)
    atomic_json(manifest, spec)
    now = datetime.now(timezone.utc)
    actual = None
    try:
        record = _record(spec)
        require(safe_path(mp4).resolve() == (Path(manifest).parent / record["file"]).resolve(), "OUTPUT_PATH_MISMATCH")
        actual = hash_file(mp4)
        contract = _contract()
        media, mh = read_json(safe_path(Path(manifest).parent / MEDIA_FILE))
        guarded = finalize_manifest(spec, actual_output_sha256=actual, now_utc=now,
                                    media_checks=media, media_sha256=mh, contract=contract)
        require(hash_file(mp4) == actual, "OUTPUT_CHANGED_DURING_FINALIZATION")
        _contract()
    except Exception as error:
        guarded = _disable(spec)
        reason = str(error) if isinstance(error, EvidenceError) else "MALFORMED_EVIDENCE"
        guarded["release_status"] = reason
        guarded["finalization"] = {"kind": KIND, "status": "ERROR", "source_pilot": "pilot-006",
            "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256, "output_sha256": actual,
            "target_slot": TARGET_SLOT, "release_deadline": LEAD_DEADLINE,
            "validated_at": now.isoformat(), "release_status": reason}
    atomic_json(manifest, guarded)
    return guarded


def binding(spec, *, plan_sha256, history_sha256):
    """Publication eligibility from complete gates and actual canonical files.

    The caller supplies freshly calculated raw digests, then this routine
    independently reopens the pinned documents. MP4 rehash is the publisher's
    responsibility; it is unavailable after normal local-media cleanup.
    """
    require(plan_sha256 == PLAN_SHA256 and history_sha256 == HISTORY_SHA256, "CONTRACT_SHA256_MISMATCH")
    contract = _contract()
    _no_mixed_authority(spec)
    final = spec.get("finalization") if type(spec) is dict else None
    keys = {"kind", "status", "source_pilot", "plan_sha256", "history_sha256", "output_sha256",
            "target_slot", "release_deadline", "validated_at", "release_status"}
    require(type(final) is dict and final.keys() == keys, "FINALIZATION_SCHEMA")
    for key, expected in (("kind", KIND), ("status", "COMPLETE"), ("source_pilot", "pilot-006"),
                          ("plan_sha256", PLAN_SHA256), ("history_sha256", HISTORY_SHA256),
                          ("target_slot", TARGET_SLOT), ("release_deadline", LEAD_DEADLINE), ("release_status", "READY")):
        require(final[key] == expected, "FINALIZATION_BINDING_MISMATCH")
    now = utc_date(final["validated_at"])
    require(now <= utc_date(LEAD_DEADLINE), "TARGET_SLOT_LEAD_MISSED")
    media, mh = read_json(safe_path(CANONICAL_PILOT / "shorts" / MEDIA_FILE))
    release = _evaluate(spec, final["output_sha256"], now, media, mh, contract)
    record = _record(spec)
    require(release == "READY" and record.get("publish") is True and record.get("release_status") == "READY"
            and spec.get("release_status") == "READY", "CORRECTION_NOT_ELIGIBLE")
    return {"output_sha256": final["output_sha256"], "target_slot": TARGET_SLOT,
            "release_deadline": LEAD_DEADLINE, "file": "short-00.mp4"}


def cli(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args[:1] == ["--preflight"] and len(args) == 4:
            preflight(*args[1:])
            print(json.dumps({"status": "PREFLIGHT_PASS"}))
            return 0
        if args[:1] == ["--check-media"] and len(args) == 8:
            checks = check_media(*args[1:])
            print(json.dumps({"media_checks": checks}, allow_nan=False))
            return 0 if checks["status"] == "PASS" else 1
        if args[:1] == ["--finalize"] and len(args) == 3:
            result = finalize_file(*args[1:])
            print(json.dumps({"finalization": result["finalization"],
                              "publish": result["shorts"][0].get("publish", False) if result.get("shorts") else False}, allow_nan=False))
            return 0 if result["finalization"]["status"] == "COMPLETE" else 1
        require(len(args) == 5 and not args[0].startswith("--"), "INVALID_ARGUMENTS")
        main(*args)
        return 0
    except Exception as error:
        print(json.dumps({"reason": str(error) if isinstance(error, EvidenceError) else "CORRECTION_OPERATION_FAILED", "publish": False}))
        return 1


if __name__ == "__main__":
    sys.exit(cli())
