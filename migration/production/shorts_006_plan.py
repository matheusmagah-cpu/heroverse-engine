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
import os
import tempfile
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
PLAN_SHA256 = "95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905"
HISTORY_SHA256 = "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677"
REJECTED_SHA256 = "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
# Logged run39529000826 failed; its media was not preserved. This deny pin
# does not claim the immutable history archive contains that MP4 or review.
UNPRESERVED_FAIL_SHA256 = "126c2e8335f5135e4d2ec2407c67e6eb636d8ce36ea7d0bd489d8ed34ff9c617"
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
    "source_start": 2013.728
  },
  "candidate": {
    "start": 813.728,
    "end": 854.417,
    "hook": "Let your face soften.",
    "title": "Rest in God's Care",
    "reference": null
  },
  "audio": {
    "source_start": 813.728,
    "source_end": 854.418,
    "source_sample_rate": 24000,
    "source_channels": 1,
    "source_samples": 976560,
    "output_sample_rate": 48000,
    "resampled_source_samples": 1953120,
    "padding_samples": 62880,
    "output_samples": 2016000,
    "fade_start": 40.69,
    "fade_seconds": 1.31
  },
  "tail_seconds": 1.31,
  "narrative_tail_seconds": 1.311,
  "output_seconds": 42.0,
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
      "nominal_end": 20.977,
      "motion_profile": "phrase_push_in_v1",
      "atmosphere": {
        "profile": "source_atmosphere_continuous_v1",
        "seed": 259006,
        "envelope": 1.0,
        "alpha_cap": 0.18,
        "fog_alpha_max": 0.09,
        "light_alpha_max": 0.06,
        "dust_alpha_max": 0.1,
        "opening_profile": "source_atmosphere_hook_v1"
      }
    },
    {
      "image_id": "bg-healing-garden",
      "asset": "pilot-006-img-bg-healing-garden-sha256-97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070.png",
      "sha256": "97fc90684ebd51dcf615f1c42ec86ea5f473b3025ea49ef8bb9ecebcfc7a4070",
      "nominal_start": 20.977,
      "nominal_end": 42.0,
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
        require(len(moment["sentences"]) == 12 and moment["sentences"] == timeline["sentences"][191:203], "SOURCE_SENTENCE_MISMATCH")
        require(moment["start"] == 813.728 and moment["end"] == 854.417
                and moment["reference"] == plan["candidate"]["reference"], "SOURCE_INTERVAL_MISMATCH")
        require(moment["sentences"][0]["text"] == "Let your face soften."
                and moment["sentences"][0]["end"] == 815.669
                and timeline["sentences"][203]["start"] == 855.797, "SOURCE_BOUNDARY_MISMATCH")
        require(moment["segments"] == ["sleep-relax-1", "sleep-relax-2", "sleep-relax-3"], "SOURCE_SEGMENT_MISMATCH")
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
    return {"expected_frame_count": 1260, "fps": 30, "scene_frame_spans": [
        {"image_id": "bg-still-water-night", "start_frame": 0, "end_frame": 637,
         "nominal_start_frame": 0, "nominal_end_frame": 629},
        {"image_id": "bg-healing-garden", "start_frame": 622, "end_frame": 1260,
         "nominal_start_frame": 629, "nominal_end_frame": 1260}]}


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
    require(record.get("sha256") == output_hash and output_hash not in (REJECTED_SHA256, UNPRESERVED_FAIL_SHA256), "OUTPUT_SHA256_MISMATCH")
    for key, expected in (("source_start", 813.728), ("source_end", 854.417), ("seconds", 42.0)):
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
    require(number(ms) and ms >= plan["music"]["source_start"] + plan["output_seconds"], "MUSIC_SOURCE_TRUNCATED")
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
    require(len(packets) == 1970, "AUDIO_PACKET_COUNT_FAIL")
    for index, packet in enumerate(packets):
        require(type(packet.get("pts")) is int and packet["pts"] == (index - 1) * 1024
                and type(packet.get("duration")) is int
                and packet["duration"] == (768 if index == len(packets) - 1 else 1024), "AUDIO_PACKET_CLOCK_FAIL")
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
    require(len(pts) == 1260 and all(number(p) and abs(p - i / 30) <= 1e-6 for i, p in enumerate(pts)), "VIDEO_PTS_FAIL")
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
    for key, expected in (("decoded_frame_count", 1260), ("width", 1080), ("height", 1920),
                          ("audio_sample_rate", 48000), ("audio_channels", 2), ("presentation_audio_samples", 2016000)):
        require(type(video[key]) is int and video[key] == expected, "VIDEO_FORMAT_FAIL")
    require(video["video_codec"] == "h264" and video["audio_codec"] == "aac", "VIDEO_CODEC_FAIL")
    require(number(video["fps"]) and video["fps"] == 30 and number(video["seconds"])
            and abs(video["seconds"] - 42) <= .011, "VIDEO_DURATION_FAIL")
    require(number(video["first_pts"]) and video["first_pts"] == 0
            and number(video["last_pts"]) and abs(video["last_pts"] - 1259 / 30) <= 1e-6
            and video["pts_uniform"] is True, "VIDEO_PTS_FAIL")
    require(exact(video["audio_packets"], {"packet_count": 1970, "first_pts_samples": -1024,
            "skip_samples": 1024, "last_pts_samples": 2015232, "last_duration_samples": 768,
            "packet_clock_continuous": True, "codec_frame_samples": 1024}), "AUDIO_PACKET_CLOCK_FAIL")
    # AAC has a 1024-sample coded frame but the final packet presents only 768.
    # Depending on decoder, raw PCM retains or discards the proven final 256 padding samples;
    # never admit arbitrary extra content or silently trim to manufacture PASS.
    require(type(video["decoded_audio_samples"]) is int and video["decoded_audio_samples"] in (2016000, 2016256), "OUTPUT_PCM_COUNT_FAIL")
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
    sentences = docs["timeline"]["sentences"][191:203]
    return {"caption_source_intervals": [{"text": s["text"], "start": round(s["start"] - 813.728, 3),
                                           "end": round(s["end"] - 813.728, 3)} for s in sentences],
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
    require(number(durations["voice_seconds"]) and durations["voice_seconds"] >= 854.418
            and number(durations["music_seconds"]) and durations["music_seconds"] >= 2055.728
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
        pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-ss", "813.728", "-i", str(voice_flac),
                    "-t", "40.690", "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "48000",
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
    _validate_attempt(spec, actual_output_sha256, now)
    http_release = _validate_http_attempt(spec, actual_output_sha256, now)
    _bind_record(spec, plan, record, actual_output_sha256, docs)
    require(actual_output_sha256 not in failed, "HISTORICAL_EDITORIAL_FAIL_BYTES")
    require(type(media_hash) is str and HASH.fullmatch(media_hash)
            and record.get("media_checks_sha256") == media_hash and exact(record.get("media_checks"), media), "MEDIA_FILE_BINDING_MISMATCH")
    validate_media_checks(media, plan, actual_output_sha256, docs=docs, now_utc=now)
    require(record.get("qa_output_sha256") == actual_output_sha256, "QA_OUTPUT_HASH_MISMATCH")
    qa = _qa_verdict(record.get("qa"), 42.0)
    review = _review_verdict(record.get("review"), actual_output_sha256)
    require(exact(spec.get("review_rubric"), {"items": list(RUBRIC), "pass_item": 7, "pass_overall": 8}), "REVIEW_RUBRIC_MISMATCH")
    previous = record.get("previous_editorial_review")
    require(not (type(previous) is dict and previous.get("status") == "FAIL"
                 and previous.get("output_sha256") in (None, actual_output_sha256)), "PREVIOUS_FAILED_BYTES")
    if qa != "PASS":
        return "QA_FAIL"
    if review != "PASS":
        return "REVIEW_" + review
    if http_release is not None:
        return http_release
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


# Review-only recovery of one preserved, unreviewed correction. These pins do
# not change production preflight or authorize a second render/provider attempt.
RECOVERY_SOURCE_RUN = "39569442793"
RECOVERY_MANIFEST_SHA256 = "a33d46db02ee419c357ae4ecefeee615b3d6ac32af143e85814cfbcb82bd1418"
RECOVERY_MEDIA_SHA256 = "6d3f0199f1ea9b0b22a87dbb29b9abfa7a3632f74488d6f1be990a9b46e00200"
RECOVERY_OUTPUT_SHA256 = "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e"
RECOVERY_OUTPUT_BYTES = 20581582
RECOVERY_NOT_BEFORE = "2026-10-21T08:51:45Z"
RECOVERY_PREVIOUS_REVIEW = {
    "status": "NOT_REVIEWED_ProviderFailure", "error_code": "HTTP_503_UNAVAILABLE",
    "failed_at": "2026-10-21T08:41:45.362893+00:00", "output_sha256": RECOVERY_OUTPUT_SHA256,
    "provider_diagnostic": {"http_status": 503, "provider_status": "UNAVAILABLE",
        "body_truncated": False, "raw_body_retained": False, "sanitized": True,
        "body_parse_status": "JSON_ERROR_OBJECT", "body_bytes_read": 198}}
RECOVERY_ERRORS = {"INPUT_CHANGED", "OUTPUT_CHANGED", "FINALIZATION_ERROR",
                   "OUTPUT_WHITELIST_VIOLATION", "OPERATION_ERROR"}


def _attempt_constants():
    return {"version": "shorts-006-review-attempt-v1", "source_run_id": RECOVERY_SOURCE_RUN,
            "source_manifest_sha256": RECOVERY_MANIFEST_SHA256, "media_sha256": RECOVERY_MEDIA_SHA256,
            "output_sha256": RECOVERY_OUTPUT_SHA256, "not_before": RECOVERY_NOT_BEFORE,
            "cutoff": LEAD_DEADLINE, "target_slot": TARGET_SLOT}


def _validate_attempt(spec, output_hash, now):
    audit = spec.get("correction_review_attempt")
    if audit is None:
        require("correction_review_attempt" not in spec, "CORRECTION_ATTEMPT_SCHEMA")
        if output_hash == RECOVERY_OUTPUT_SHA256:
            require(exact(_record(spec).get("review"), RECOVERY_PREVIOUS_REVIEW), "CORRECTION_ATTEMPT_REQUIRED")
        return
    constants = _attempt_constants()
    keys = set(constants) | {"run_id", "run_attempt", "started_at", "completed_at", "state",
                             "previous_review", "fresh_qa", "reason"}
    require(type(audit) is dict and audit.keys() == keys, "CORRECTION_ATTEMPT_SCHEMA")
    require(output_hash == RECOVERY_OUTPUT_SHA256 and all(exact(audit[k], v) for k, v in constants.items()),
            "CORRECTION_ATTEMPT_PINS")
    require(type(audit["run_id"]) is str and re.fullmatch(r"[1-9][0-9]*", audit["run_id"])
            and audit["run_id"] != RECOVERY_SOURCE_RUN and type(audit["run_attempt"]) is int
            and audit["run_attempt"] == 1, "CORRECTION_ATTEMPT_RUN")
    require(exact(audit["previous_review"], RECOVERY_PREVIOUS_REVIEW), "CORRECTION_PREVIOUS_REVIEW")
    require(_qa_verdict(audit["fresh_qa"], 42.0) == "PASS", "CORRECTION_FRESH_QA_FAIL")
    require(type(audit["started_at"]) is str, "CORRECTION_ATTEMPT_CLOCK")
    start = utc_date(audit["started_at"])
    require(utc_date(RECOVERY_NOT_BEFORE) <= start <= utc_date(LEAD_DEADLINE)
            and start <= now, "CORRECTION_ATTEMPT_CLOCK")
    state = audit["state"]
    require(type(state) is str and state in {"STARTED", "COMPLETE", "ERROR"}, "CORRECTION_ATTEMPT_STATE")
    if state == "STARTED":
        require(audit["completed_at"] is None and audit["reason"] is None, "CORRECTION_ATTEMPT_CLOCK")
    else:
        require(type(audit["completed_at"]) is str and start <= utc_date(audit["completed_at"]) <= now,
                "CORRECTION_ATTEMPT_CLOCK")
        require(audit["reason"] is None if state == "COMPLETE" else
                type(audit["reason"]) is str and audit["reason"] in RECOVERY_ERRORS, "CORRECTION_ATTEMPT_REASON")
    require(state == "COMPLETE", "CORRECTION_ATTEMPT_NOT_COMPLETE")


def recovery_preflight(pilot_dir, *, now_utc):
    """Document-only preflight; release download has not necessarily happened."""
    now = utc_date(now_utc)
    require(utc_date(RECOVERY_NOT_BEFORE) <= now <= utc_date(LEAD_DEADLINE), "RECOVERY_OUTSIDE_WINDOW")
    pilot = safe_path(pilot_dir, directory=True)
    require(pilot.resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
    path = safe_path(pilot / "shorts/shorts.json")
    spec, digest = read_json(path)
    require(digest == RECOVERY_MANIFEST_SHA256, "RECOVERY_SOURCE_CHANGED")
    media, mh = read_json(safe_path(path.parent / MEDIA_FILE))
    require(mh == RECOVERY_MEDIA_SHA256, "RECOVERY_MEDIA_CHANGED")
    require("correction_review_attempt" not in spec, "RECOVERY_ALREADY_ATTEMPTED")
    record = _record(spec)
    require(exact(record.get("review"), RECOVERY_PREVIOUS_REVIEW), "RECOVERY_NOT_ORIGINAL_503")
    require(record.get("publish") is False and spec.get("publish") is False, "RECOVERY_SOURCE_ELIGIBLE")
    final = spec.get("finalization")
    expected = {"kind": KIND, "status": "COMPLETE", "source_pilot": "pilot-006",
                "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256,
                "output_sha256": RECOVERY_OUTPUT_SHA256, "target_slot": TARGET_SLOT,
                "release_deadline": LEAD_DEADLINE, "release_status": "REVIEW_NOT_REVIEWED"}
    require(type(final) is dict and final.keys() == set(expected) | {"validated_at"}
            and all(exact(final[k], v) for k, v in expected.items()), "RECOVERY_FINALIZATION_INVALID")
    require(type(final["validated_at"]) is str and utc_date(final["validated_at"]) <= now, "RECOVERY_FINALIZATION_CLOCK")
    require(spec.get("release_status") == record.get("release_status") == "REVIEW_NOT_REVIEWED",
            "RECOVERY_SOURCE_STATUS")
    contract = _contract()
    require(_qa_verdict(record.get("qa"), 42.0) == "PASS", "RECOVERY_ORIGINAL_QA_FAIL")
    require(_evaluate(spec, RECOVERY_OUTPUT_SHA256, now, media, mh, contract) == "REVIEW_NOT_REVIEWED",
            "RECOVERY_NOT_UNREVIEWED")
    return {"pilot": pilot, "path": path, "spec": spec, "media": media, "media_hash": mh, "contract": contract}


def recovery_list(pilot_dir):
    recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    print("short-00.mp4", RECOVERY_OUTPUT_SHA256)


def _recovery_output(path):
    require(safe_path(path).stat().st_size == RECOVERY_OUTPUT_BYTES
            and hash_file(path) == RECOVERY_OUTPUT_SHA256, "OUTPUT_CHANGED")


def _recovery_stable(data, started_hash, mp4):
    require(hash_file(safe_path(data["path"])) == started_hash, "INPUT_CHANGED")
    _recovery_output(mp4)
    try:
        _contract()
        require(hash_file(safe_path(data["path"].parent / MEDIA_FILE)) == RECOVERY_MEDIA_SHA256, "INPUT_CHANGED")
    except Exception:
        raise EvidenceError("INPUT_CHANGED") from None
    _recovery_output(mp4)
    require(hash_file(safe_path(data["path"])) == started_hash, "INPUT_CHANGED")


def _recovery_whitelist(original, result, *, attempt_key="correction_review_attempt"):
    top = {attempt_key, "finalization", "release_status", "publish", "shorts"}
    fields = {"review", "owner_quality_policy", "release_status", "publish"}
    require(type(result) is dict and exact({k: v for k, v in original.items() if k not in top},
            {k: v for k, v in result.items() if k not in top}), "OUTPUT_WHITELIST_VIOLATION")
    before, after = _record(original), _record(result)
    require(exact({k: v for k, v in before.items() if k not in fields},
                  {k: v for k, v in after.items() if k not in fields}), "OUTPUT_WHITELIST_VIOLATION")


def recover_review(pilot_dir):
    """One invocation after operational idle reconciliation; no retries here."""
    data = recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    run_id, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]*", run_id)
            and run_id != RECOVERY_SOURCE_RUN and attempt == "1", "RECOVERY_RUN_INVALID")
    key = os.environ.get("HERO_GEMINI_API_KEY", "")
    require(bool(key.strip()), "RECOVERY_KEY_MISSING")
    mp4 = data["path"].parent / "short-00.mp4"
    _recovery_output(mp4)
    import shorts_qa  # local technical check; no provider initialization
    fresh = shorts_qa.check(mp4)
    _recovery_output(mp4)
    require(_qa_verdict(fresh, 42.0) == "PASS", "RECOVERY_FRESH_QA_FAIL")
    # Recheck every source and the clock after potentially slow local QA.
    data = recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    _recovery_output(mp4)
    import shorts_review  # lazy, only after all prechecks passed
    start = datetime.now(timezone.utc)
    require(utc_date(RECOVERY_NOT_BEFORE) <= start <= utc_date(LEAD_DEADLINE), "RECOVERY_OUTSIDE_WINDOW")
    original = deepcopy(data["spec"])
    started = _disable(original)
    started["correction_review_attempt"] = _attempt_constants() | {
        "run_id": run_id, "run_attempt": 1, "started_at": start.isoformat(), "completed_at": None,
        "state": "STARTED", "previous_review": deepcopy(RECOVERY_PREVIOUS_REVIEW),
        "fresh_qa": deepcopy(fresh), "reason": None}
    started_raw = (json.dumps(started, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    started_hash = hashlib.sha256(started_raw).hexdigest()
    require(hash_file(safe_path(data["path"])) == RECOVERY_MANIFEST_SHA256, "INPUT_CHANGED")
    atomic_json(data["path"], started)
    require(hash_file(safe_path(data["path"])) == started_hash, "INPUT_CHANGED")
    candidate = None
    try:
        # The second clock/read is immediately before the sole provider call.
        _recovery_stable(data, started_hash, mp4)
        require(utc_date(RECOVERY_NOT_BEFORE) <= datetime.now(timezone.utc) <= utc_date(LEAD_DEADLINE), "OPERATION_ERROR")
        try:
            review = shorts_review.review(mp4, deepcopy(_record(original)), key)
        except Exception as error:
            review = shorts_review.failure_record(error, mp4)
        _recovery_stable(data, started_hash, mp4)
        result = deepcopy(started)
        rec = _record(result)
        rec["review"] = deepcopy(review)
        problems = owner_quality_policy.check(review, RECOVERY_OUTPUT_SHA256)
        rec["owner_quality_policy"] = {"minimum_overall": 9.0, "status": "FAIL" if problems else "PASS", "problems": problems}
        result["correction_review_attempt"].update(state="COMPLETE", completed_at=datetime.now(timezone.utc).isoformat())
        fd, name = tempfile.mkstemp(prefix=".correction-review-", suffix=".json", dir=data["path"].parent)
        os.close(fd)
        candidate = Path(name)
        atomic_json(candidate, result)
        finalized = finalize_file(candidate, mp4)
        require(finalized.get("finalization", {}).get("status") == "COMPLETE", "FINALIZATION_ERROR")
        _recovery_whitelist(original, finalized)
        _recovery_stable(data, started_hash, mp4)
        # All slow external checks precede this fresh, final clock. Pure
        # finalization catches cutoff crossing without another provider call.
        install_at = datetime.now(timezone.utc)
        while True:
            finalized = finalize_manifest(finalized, actual_output_sha256=RECOVERY_OUTPUT_SHA256,
                now_utc=install_at, media_checks=data["media"], media_sha256=data["media_hash"], contract=data["contract"])
            require(finalized.get("finalization", {}).get("status") == "COMPLETE", "FINALIZATION_ERROR")
            _recovery_whitelist(original, finalized)
            _recovery_stable(data, started_hash, mp4)
            after_checks = datetime.now(timezone.utc)
            if install_at <= utc_date(LEAD_DEADLINE) < after_checks:
                # The cutoff crosses only once; repeat pure finalization, never
                # the provider. Rehash again even after this negative result.
                install_at = after_checks
                continue
            require(after_checks.date() == install_at.date(), "FINALIZATION_ERROR")
            break
        atomic_json(data["path"], finalized)
        return finalized
    except Exception as error:
        reason = str(error) if isinstance(error, EvidenceError) and str(error) in RECOVERY_ERRORS else "OPERATION_ERROR"
        # Never overwrite another actor's bytes, or a possibly successful install.
        if hash_file(safe_path(data["path"])) == started_hash:
            failed = _disable(started)
            failed["correction_review_attempt"].update(state="ERROR", reason=reason,
                completed_at=datetime.now(timezone.utc).isoformat())
            failed["release_status"] = reason
            _record(failed)["release_status"] = reason
            failed["finalization"].update(status="ERROR", release_status=reason,
                validated_at=datetime.now(timezone.utc).isoformat())
            atomic_json(data["path"], failed)
        raise EvidenceError(reason) from None
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)


# Separate execution authority; historical recovery pins/CLI remain consumed.
# The second alias deliberately scopes the new eligibility guard to these bytes,
# without retroactively changing unrelated correction/legacy synthetic fixtures.
HTTP_RECOVERY_SOURCE_RUN = "39575597092"
HTTP_RECOVERY_MANIFEST_SHA256 = "856f2765f104a1a98a54ec322784302066b545882595290020cf672183ebf9f8"
HTTP_RECOVERY_OUTPUT_SHA256 = "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e"
HTTP_RECOVERY_NOT_BEFORE = "2026-10-21T10:00:00Z"
HTTP_PREVIOUS_ATTEMPT_SHA256 = "c9c707beb0b6cfbfd6f8512ec4a705482a267d0be15c12a1e9dbcefed289c3e3"
HTTP_PREVIOUS_REVIEW = {
    "status": "NOT_REVIEWED_ProviderFailure", "error_code": "HTTP_503_UNAVAILABLE",
    "failed_at": "2026-10-21T09:17:47.236719+00:00", "output_sha256": HTTP_RECOVERY_OUTPUT_SHA256,
    "provider_diagnostic": {"http_status": 503, "provider_status": "UNAVAILABLE",
        "body_truncated": False, "raw_body_retained": False, "sanitized": True,
        "body_parse_status": "JSON_ERROR_OBJECT", "body_bytes_read": 198}}
HTTP_PREVIOUS_ATTEMPT = {
    "version": "shorts-006-review-attempt-v1", "source_run_id": "39569442793",
    "source_manifest_sha256": "a33d46db02ee419c357ae4ecefeee615b3d6ac32af143e85814cfbcb82bd1418",
    "media_sha256": "6d3f0199f1ea9b0b22a87dbb29b9abfa7a3632f74488d6f1be990a9b46e00200",
    "output_sha256": HTTP_RECOVERY_OUTPUT_SHA256, "not_before": "2026-10-21T08:51:45Z",
    "cutoff": LEAD_DEADLINE, "target_slot": TARGET_SLOT, "run_id": HTTP_RECOVERY_SOURCE_RUN,
    "run_attempt": 1, "started_at": "2026-10-21T09:16:23.550574+00:00",
    "completed_at": "2026-10-21T09:17:47.289630+00:00", "state": "COMPLETE",
    "previous_review": deepcopy(RECOVERY_PREVIOUS_REVIEW),
    "fresh_qa": {"file": "migration/production/pilot-006/shorts/short-00.mp4", "seconds": 42.0,
        "lufs": -15.0, "true_peak_dbtp": -2.4, "checks": {key: True for key in QA_CHECKS}, "status": "PASS"},
    "reason": None}
HTTP_AUDIT_KEYS = {"transport_attempts", "http_completion", "terminal_stage", "cleanup_status", "http_elapsed_seconds"}
HTTP_TRACE_KEYS = {"attempt", "started_at", "elapsed_start_seconds", "elapsed_end_seconds", "outcome",
                   "http_status", "provider_status", "retry_after_seconds", "retry_info_seconds",
                   "selected_delay_seconds", "slept_seconds", "decision"}
HTTP_COMPLETIONS = {"COMPLETED", "BUDGET_EXHAUSTED", "DEADLINE_EXCEEDED", "UPLOAD_FAILED"}
HTTP_STAGES = {"NONE", "UPLOAD_START", "UPLOAD_FINALIZE", "FILE_POLL", "GENERATE_CONTENT"}
HTTP_PROVIDER_STATUSES = {"INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED",
                          "NOT_FOUND", "RESOURCE_EXHAUSTED", "UNAVAILABLE"}


def _canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _http_attempt_constants():
    return {"version": "shorts-006-http-review-attempt-v1", "source_run_id": HTTP_RECOVERY_SOURCE_RUN,
            "source_manifest_sha256": HTTP_RECOVERY_MANIFEST_SHA256, "media_sha256": RECOVERY_MEDIA_SHA256,
            "output_sha256": HTTP_RECOVERY_OUTPUT_SHA256, "not_before": HTTP_RECOVERY_NOT_BEFORE,
            "cutoff": LEAD_DEADLINE, "target_slot": TARGET_SLOT,
            "previous_attempt_sha256": HTTP_PREVIOUS_ATTEMPT_SHA256, "http_policy": "designated-review-http-v1"}


def _http_previous_attempt(spec):
    previous = spec.get("correction_review_attempt")
    require(exact(previous, HTTP_PREVIOUS_ATTEMPT)
            and _canonical_sha256(previous) == HTTP_PREVIOUS_ATTEMPT_SHA256, "HTTP_PREVIOUS_ATTEMPT_CHANGED")


def _validate_http_trace(audit):
    """Pure closed-schema validation, never trusts fields returned by a model."""
    trace, elapsed = audit["transport_attempts"], audit["http_elapsed_seconds"]
    require(type(trace) is list and len(trace) <= 2 and number(elapsed) and elapsed >= 0, "HTTP_TRACE_SCHEMA")
    previous_end = 0.0
    for index, entry in enumerate(trace):
        require(type(entry) is dict and entry.keys() == HTTP_TRACE_KEYS, "HTTP_TRACE_SCHEMA")
        require(type(entry["attempt"]) is int and entry["attempt"] == index + 1, "HTTP_TRACE_ATTEMPT")
        require(type(entry["started_at"]) is str, "HTTP_TRACE_CLOCK")
        utc_date(entry["started_at"])
        start, end, slept = entry["elapsed_start_seconds"], entry["elapsed_end_seconds"], entry["slept_seconds"]
        require(number(start) and number(end) and number(slept)
                and previous_end <= start <= end <= elapsed and 0 <= slept <= elapsed - end, "HTTP_TRACE_CLOCK")
        status = entry["http_status"]
        require(status is None or type(status) is int and 100 <= status <= 599, "HTTP_TRACE_STATUS")
        require(entry["provider_status"] is None or type(entry["provider_status"]) is str
                and entry["provider_status"] in HTTP_PROVIDER_STATUSES, "HTTP_TRACE_STATUS")
        for field in ("retry_after_seconds", "retry_info_seconds", "selected_delay_seconds"):
            require(entry[field] is None or type(entry[field]) is int and entry[field] >= 0, "HTTP_TRACE_HINT")
        outcome, decision = entry["outcome"], entry["decision"]
        require(type(outcome) is str and outcome in {"HTTP_ERROR", "SUCCESS", "UNPARSEABLE_MODEL_OUTPUT", "TRANSPORT_ERROR"}
                and type(decision) is str and decision in {"RETURN", "RETRY", "STOP_FINAL", "STOP_NONRETRYABLE",
                    "STOP_HINT_INVALID", "STOP_BUDGET", "STOP_DEADLINE"}, "HTTP_TRACE_OUTCOME")
        if outcome in {"SUCCESS", "UNPARSEABLE_MODEL_OUTPUT"}:
            require(status == 200 and entry["provider_status"] is None, "HTTP_TRACE_STATUS")
        elif outcome == "TRANSPORT_ERROR":
            # A response may have supplied a factual status before body reading
            # failed. Preserve that observation without treating it as success.
            require(entry["provider_status"] is None, "HTTP_TRACE_STATUS")
        else:
            require(status is not None, "HTTP_TRACE_STATUS")
        if outcome != "HTTP_ERROR":
            require(all(entry[k] is None for k in ("retry_after_seconds", "retry_info_seconds", "selected_delay_seconds"))
                    and slept == 0, "HTTP_TRACE_HINT")
        selected = entry["selected_delay_seconds"]
        if selected is not None:
            require(outcome == "HTTP_ERROR" and status == 503
                    and selected == max(20, entry["retry_after_seconds"] or 0, entry["retry_info_seconds"] or 0),
                    "HTTP_TRACE_HINT")
        if slept > 0:
            require(index == 0 and selected is not None, "HTTP_TRACE_SLEEP")
        if decision == "RETURN":
            require(outcome == "SUCCESS" and index == len(trace) - 1, "HTTP_TRACE_DECISION")
        if decision == "STOP_FINAL":
            require(index == 1 and outcome == "HTTP_ERROR" and status == 503, "HTTP_TRACE_DECISION")
        if decision == "STOP_HINT_INVALID":
            require(outcome == "HTTP_ERROR" and status == 503 and selected is None and slept == 0,
                    "HTTP_TRACE_DECISION")
        if index < len(trace) - 1:
            require(outcome == "HTTP_ERROR" and status == 503 and decision == "RETRY"
                    and selected is not None and slept >= selected, "HTTP_TRACE_RETRY")
        else:
            require(decision != "RETRY", "HTTP_TRACE_RETRY")
        previous_end = end + slept
    require(not trace or audit["terminal_stage"] == "GENERATE_CONTENT", "HTTP_TRACE_STAGE")
    return trace


def _validated_http_client_audit(audit):
    """Only closed, sanitized client evidence may survive an integrity ERROR."""
    require(type(audit) is dict and audit.keys() == HTTP_AUDIT_KEYS, "HTTP_AUDIT_SCHEMA")
    require(type(audit["http_completion"]) is str and audit["http_completion"] in HTTP_COMPLETIONS
            and type(audit["terminal_stage"]) is str and audit["terminal_stage"] in HTTP_STAGES
            and type(audit["cleanup_status"]) is str and audit["cleanup_status"] in {"NOT_ATTEMPTED", "SUCCESS", "FAILED"},
            "HTTP_COMPLETION_SCHEMA")
    _validate_http_trace(audit)
    return deepcopy(audit)


def _validate_http_attempt(spec, output_hash, now):
    audit = spec.get("correction_http_recovery_attempt")
    if audit is None:
        require("correction_http_recovery_attempt" not in spec, "HTTP_ATTEMPT_SCHEMA")
        if output_hash == HTTP_RECOVERY_OUTPUT_SHA256:
            if "correction_review_attempt" in spec:
                _http_previous_attempt(spec)
                require(exact(_record(spec).get("review"), HTTP_PREVIOUS_REVIEW), "HTTP_ATTEMPT_REQUIRED")
            else:
                require(exact(_record(spec).get("review"), RECOVERY_PREVIOUS_REVIEW), "HTTP_ATTEMPT_REQUIRED")
        return None
    constants = _http_attempt_constants()
    keys = set(constants) | HTTP_AUDIT_KEYS | {"run_id", "run_attempt", "started_at", "completed_at", "state",
                                             "previous_review", "fresh_qa", "reason"}
    require(type(audit) is dict and audit.keys() == keys, "HTTP_ATTEMPT_SCHEMA")
    require(output_hash == HTTP_RECOVERY_OUTPUT_SHA256 and all(exact(audit[k], v) for k, v in constants.items()),
            "HTTP_ATTEMPT_PINS")
    _http_previous_attempt(spec)
    require(type(audit["run_id"]) is str and re.fullmatch(r"[1-9][0-9]*", audit["run_id"])
            and audit["run_id"] not in {RECOVERY_SOURCE_RUN, HTTP_RECOVERY_SOURCE_RUN}
            and type(audit["run_attempt"]) is int and audit["run_attempt"] == 1, "HTTP_ATTEMPT_RUN")
    require(exact(audit["previous_review"], HTTP_PREVIOUS_REVIEW), "HTTP_PREVIOUS_REVIEW_CHANGED")
    require(_qa_verdict(audit["fresh_qa"], 42.0) == "PASS", "HTTP_FRESH_QA_FAIL")
    require(type(audit["started_at"]) is str, "HTTP_ATTEMPT_CLOCK")
    start = utc_date(audit["started_at"])
    require(utc_date(HTTP_RECOVERY_NOT_BEFORE) <= start <= utc_date(LEAD_DEADLINE) and start <= now,
            "HTTP_ATTEMPT_CLOCK")
    state = audit["state"]
    require(type(state) is str and state in {"STARTED", "COMPLETE", "ERROR"}, "HTTP_ATTEMPT_STATE")
    if state == "STARTED":
        require(all(audit[k] is None for k in ("completed_at", "reason", "http_completion", "http_elapsed_seconds"))
                and audit["transport_attempts"] == [] and audit["terminal_stage"] == "NONE"
                and audit["cleanup_status"] == "NOT_ATTEMPTED", "HTTP_ATTEMPT_STARTED")
    else:
        require(type(audit["completed_at"]) is str and start <= utc_date(audit["completed_at"]) <= now,
                "HTTP_ATTEMPT_CLOCK")
        require(audit["reason"] is None if state == "COMPLETE" else
                type(audit["reason"]) is str and audit["reason"] in RECOVERY_ERRORS, "HTTP_ATTEMPT_REASON")
    require(state == "COMPLETE", "HTTP_ATTEMPT_NOT_COMPLETE")
    client_audit = _validated_http_client_audit({k: audit[k] for k in HTTP_AUDIT_KEYS})
    trace = client_audit["transport_attempts"]
    if audit["http_completion"] != "COMPLETED":
        return "HTTP_" + audit["http_completion"]
    if audit["http_elapsed_seconds"] > 600:
        return "HTTP_BUDGET_EXHAUSTED"
    if _record(spec)["review"].get("status") in {"PASS", "FAIL"}:
        require(len(trace) in (1, 2) and trace[-1]["outcome"] == "SUCCESS"
                and trace[-1]["decision"] == "RETURN" and trace[-1]["http_status"] == 200, "HTTP_SUCCESS_TRACE_REQUIRED")
        require(all(start <= utc_date(t["started_at"]) <= utc_date(audit["completed_at"])
                    and utc_date(t["started_at"]) <= utc_date(LEAD_DEADLINE) for t in trace), "HTTP_TRACE_CLOCK")
    return None


def http_recovery_preflight(pilot_dir, *, now_utc):
    """Document-only check of the consumed v1 evidence; no download/provider."""
    now = utc_date(now_utc)
    require(utc_date(HTTP_RECOVERY_NOT_BEFORE) <= now <= utc_date(LEAD_DEADLINE), "HTTP_RECOVERY_OUTSIDE_WINDOW")
    pilot = safe_path(pilot_dir, directory=True)
    require(pilot.resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
    path = safe_path(pilot / "shorts/shorts.json")
    spec, digest = read_json(path)
    require(digest == HTTP_RECOVERY_MANIFEST_SHA256, "HTTP_RECOVERY_SOURCE_CHANGED")
    media, mh = read_json(safe_path(path.parent / MEDIA_FILE))
    require(mh == RECOVERY_MEDIA_SHA256, "RECOVERY_MEDIA_CHANGED")
    require("correction_http_recovery_attempt" not in spec, "HTTP_RECOVERY_ALREADY_ATTEMPTED")
    _http_previous_attempt(spec)
    record = _record(spec)
    require(exact(record.get("review"), HTTP_PREVIOUS_REVIEW), "HTTP_RECOVERY_NOT_SECOND_503")
    require(record.get("publish") is False and spec.get("publish") is False, "RECOVERY_SOURCE_ELIGIBLE")
    final = spec.get("finalization")
    expected = {"kind": KIND, "status": "COMPLETE", "source_pilot": "pilot-006",
                "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256,
                "output_sha256": HTTP_RECOVERY_OUTPUT_SHA256, "target_slot": TARGET_SLOT,
                "release_deadline": LEAD_DEADLINE, "release_status": "REVIEW_NOT_REVIEWED"}
    require(type(final) is dict and final.keys() == set(expected) | {"validated_at"}
            and all(exact(final[k], v) for k, v in expected.items()), "RECOVERY_FINALIZATION_INVALID")
    require(type(final["validated_at"]) is str and utc_date(final["validated_at"]) <= now, "RECOVERY_FINALIZATION_CLOCK")
    require(spec.get("release_status") == record.get("release_status") == "REVIEW_NOT_REVIEWED", "RECOVERY_SOURCE_STATUS")
    contract = _contract()
    require(_qa_verdict(record.get("qa"), 42.0) == "PASS", "RECOVERY_ORIGINAL_QA_FAIL")
    require(_evaluate(spec, HTTP_RECOVERY_OUTPUT_SHA256, now, media, mh, contract) == "REVIEW_NOT_REVIEWED",
            "RECOVERY_NOT_UNREVIEWED")
    return {"pilot": pilot, "path": path, "spec": spec, "media": media, "media_hash": mh, "contract": contract}


def http_recovery_list(pilot_dir):
    http_recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    print("short-00.mp4", HTTP_RECOVERY_OUTPUT_SHA256)


def recover_http_review(pilot_dir):
    """One invocation after operational idle reconciliation; no retries here."""
    data = http_recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    run_id, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]*", run_id)
            and run_id not in {RECOVERY_SOURCE_RUN, HTTP_RECOVERY_SOURCE_RUN} and attempt == "1", "RECOVERY_RUN_INVALID")
    key = os.environ.get("HERO_GEMINI_API_KEY", "")
    require(bool(key.strip()), "RECOVERY_KEY_MISSING")
    mp4 = data["path"].parent / "short-00.mp4"
    _recovery_output(mp4)
    import shorts_qa  # local technical check; no provider initialization
    fresh = shorts_qa.check(mp4)
    _recovery_output(mp4)
    require(_qa_verdict(fresh, 42.0) == "PASS", "RECOVERY_FRESH_QA_FAIL")
    # Recheck every source and the clock after potentially slow local QA.
    data = http_recovery_preflight(pilot_dir, now_utc=datetime.now(timezone.utc))
    _recovery_output(mp4)
    import shorts_review  # lazy, only after all prechecks passed
    start = datetime.now(timezone.utc)
    require(utc_date(HTTP_RECOVERY_NOT_BEFORE) <= start <= utc_date(LEAD_DEADLINE), "RECOVERY_OUTSIDE_WINDOW")
    original = deepcopy(data["spec"])
    started = _disable(original)
    started["correction_http_recovery_attempt"] = _http_attempt_constants() | {
        "run_id": run_id, "run_attempt": 1, "started_at": start.isoformat(), "completed_at": None,
        "state": "STARTED", "previous_review": deepcopy(HTTP_PREVIOUS_REVIEW),
        "fresh_qa": deepcopy(fresh), "reason": None, "transport_attempts": [],
        "http_completion": None, "terminal_stage": "NONE", "cleanup_status": "NOT_ATTEMPTED", "http_elapsed_seconds": None}
    started_raw = (json.dumps(started, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    started_hash = hashlib.sha256(started_raw).hexdigest()
    require(hash_file(safe_path(data["path"])) == HTTP_RECOVERY_MANIFEST_SHA256, "INPUT_CHANGED")
    atomic_json(data["path"], started)
    require(hash_file(safe_path(data["path"])) == started_hash, "INPUT_CHANGED")
    candidate = None
    client_audit = None
    try:
        # The second clock/read is immediately before the sole provider call.
        _recovery_stable(data, started_hash, mp4)
        require(utc_date(HTTP_RECOVERY_NOT_BEFORE) <= datetime.now(timezone.utc) <= utc_date(LEAD_DEADLINE), "OPERATION_ERROR")
        policy = shorts_review.ReviewHTTPPolicy(cutoff_utc=LEAD_DEADLINE)
        try:
            review = shorts_review.review(mp4, deepcopy(_record(original)), key, http_policy=policy)
        except Exception as error:
            review = shorts_review.failure_record(error, mp4)
        client_audit = _validated_http_client_audit(policy.audit())
        _recovery_stable(data, started_hash, mp4)
        result = deepcopy(started)
        rec = _record(result)
        rec["review"] = deepcopy(review)
        problems = owner_quality_policy.check(review, RECOVERY_OUTPUT_SHA256)
        rec["owner_quality_policy"] = {"minimum_overall": 9.0, "status": "FAIL" if problems else "PASS", "problems": problems}
        result["correction_http_recovery_attempt"].update(deepcopy(client_audit))
        result["correction_http_recovery_attempt"].update(state="COMPLETE", completed_at=datetime.now(timezone.utc).isoformat())
        fd, name = tempfile.mkstemp(prefix=".correction-http-review-", suffix=".json", dir=data["path"].parent)
        os.close(fd)
        candidate = Path(name)
        atomic_json(candidate, result)
        finalized = finalize_file(candidate, mp4)
        require(finalized.get("finalization", {}).get("status") == "COMPLETE", "FINALIZATION_ERROR")
        _recovery_whitelist(original, finalized, attempt_key="correction_http_recovery_attempt")
        _recovery_stable(data, started_hash, mp4)
        # All slow external checks precede this fresh, final clock. Pure
        # finalization catches cutoff crossing without another provider call.
        install_at = datetime.now(timezone.utc)
        while True:
            finalized = finalize_manifest(finalized, actual_output_sha256=RECOVERY_OUTPUT_SHA256,
                now_utc=install_at, media_checks=data["media"], media_sha256=data["media_hash"], contract=data["contract"])
            require(finalized.get("finalization", {}).get("status") == "COMPLETE", "FINALIZATION_ERROR")
            _recovery_whitelist(original, finalized, attempt_key="correction_http_recovery_attempt")
            _recovery_stable(data, started_hash, mp4)
            after_checks = datetime.now(timezone.utc)
            if install_at <= utc_date(LEAD_DEADLINE) < after_checks:
                # The cutoff crosses only once; repeat pure finalization, never
                # the provider. Rehash again even after this negative result.
                install_at = after_checks
                continue
            require(after_checks.date() == install_at.date(), "FINALIZATION_ERROR")
            break
        atomic_json(data["path"], finalized)
        return finalized
    except Exception as error:
        reason = str(error) if isinstance(error, EvidenceError) and str(error) in RECOVERY_ERRORS else "OPERATION_ERROR"
        # Never overwrite another actor's bytes, or a possibly successful install.
        if hash_file(safe_path(data["path"])) == started_hash:
            failed = _disable(started)
            if client_audit is not None:
                failed["correction_http_recovery_attempt"].update(deepcopy(client_audit))
            failed["correction_http_recovery_attempt"].update(state="ERROR", reason=reason,
                completed_at=datetime.now(timezone.utc).isoformat())
            failed["release_status"] = reason
            _record(failed)["release_status"] = reason
            failed["finalization"].update(status="ERROR", release_status=reason,
                validated_at=datetime.now(timezone.utc).isoformat())
            atomic_json(data["path"], failed)
        raise EvidenceError(reason) from None
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)


def cli(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args[:1] == ["--http-recovery-list"] and len(args) == 2:
            http_recovery_list(args[1])
            return 0
        if args[:1] == ["--recover-http-review"] and len(args) == 2:
            result = recover_http_review(args[1])
            print(json.dumps({"status": result["finalization"]["status"], "release_status": result["release_status"],
                              "publish": _record(result)["publish"]}))
            return 0 if result["finalization"]["status"] == "COMPLETE" else 1
        if args[:1] == ["--recovery-list"] and len(args) == 2:
            recovery_list(args[1])
            return 0
        if args[:1] == ["--recover-review"] and len(args) == 2:
            result = recover_review(args[1])
            print(json.dumps({"status": result["finalization"]["status"], "release_status": result["release_status"],
                              "publish": _record(result)["publish"]}))
            return 0 if result["finalization"]["status"] == "COMPLETE" else 1
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
