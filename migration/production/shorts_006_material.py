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
from shorts_006_plan import (HTTP_AUDIT_KEYS, RECOVERY_ERRORS, _validated_http_client_audit,
    _probe, _black_intervals, _audio_packets, _validate_acoustic, _qa_verdict, _review_verdict)
LEGACY_PLAN_SHA256 = "95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905"
LEGACY_HISTORY_SHA256 = "4c4d178392ee1b13b4a5927ba8a6454b895e85119b247aa038215fb9a58b4677"
REFERENCE_SHA256 = "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e"
JOURNAL = "correction_material_review_attempt"


CANONICAL_PILOT = Path(__file__).resolve().parent / "pilot-006"
PLAN_SHA256 = "99e0ecbd3a5a0c5736e6ce8eaadc766a346cb789b08203577fa38dde1ade1543"
HISTORY_SHA256 = "5b1798377d25f54a813ed8ae1e99fbe17fa7ccab0ea4650454fcb76c5ba1cede"
REJECTED_SHA256 = "9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707"
# Logged run39529000826 failed; its media was not preserved. This deny pin
# does not claim the immutable history archive contains that MP4 or review.
UNPRESERVED_FAIL_SHA256 = "126c2e8335f5135e4d2ec2407c67e6eb636d8ce36ea7d0bd489d8ed34ff9c617"
DENIED_OUTPUTS = frozenset((REJECTED_SHA256, UNPRESERVED_FAIL_SHA256, REFERENCE_SHA256))
TARGET_SLOT = "2026-10-21T14:00:00Z"
LEAD_DEADLINE = "2026-10-21T13:15:00Z"
KIND = "pilot-006-correction-v2"
MEDIA_FILE = "correction-media-checks-v2.json"
HASH = re.compile(r"[0-9a-f]{64}\Z")
RUBRIC = ("hook_in_first_2s", "captions_readable_and_synced", "text_clear_of_shorts_ui", "picture_quality",
          "edit_rhythm", "audio_clarity", "stands_alone", "ending_and_loop", "policy_safe")
QA_CHECKS = {"decode_clean", "one_h264_1080x1920", "fps_30", "one_aac_stereo_48k", "duration", "loudness", "true_peak"}
# Independent code-owned schema, not loaded from a mutable production document.
EXPECTED_PLAN = json.loads(r'''{
  "version": "shorts-006-correction-plan-v2",
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
      "image_id": "bg-healing-stream-night",
      "asset": "pilot-006-img-bg-healing-stream-night-sha256-a7b1f2b1d1e3002f85bbf34250b8db3ff04cba8c5af1d1b3566be33b171e2b01.png",
      "sha256": "a7b1f2b1d1e3002f85bbf34250b8db3ff04cba8c5af1d1b3566be33b171e2b01",
      "metadata_sha256": "0289952b8b7464de1fc51eb5462e10f2db8fa3ef1f83fefc9aa7fcaab84fe385",
      "nominal_start": 0.0,
      "nominal_end": 20.977,
      "visual_profile": "native_stream_hook_v2",
      "camera": {
        "source_width": 2048,
        "source_height": 2048,
        "window_width": 1080,
        "window_height": 1920,
        "y": 64,
        "profile": "two_segment_hermite_v1",
        "knot_seconds": 3.0,
        "x": [
          0.0,
          40.0,
          48.0
        ],
        "velocity": [
          20.0,
          0.5,
          0.3
        ],
        "frames": 637
      },
      "water_light": {
        "profile": "source_texture_flow_v1",
        "coordinates": "source_x_and_source_y_minus_64",
        "polygons": [
          [
            [
              620,
              1530
            ],
            [
              760,
              1515
            ],
            [
              910,
              1530
            ],
            [
              1070,
              1520
            ],
            [
              1070,
              1650
            ],
            [
              930,
              1650
            ],
            [
              780,
              1625
            ],
            [
              620,
              1635
            ]
          ],
          [
            [
              760,
              1290
            ],
            [
              850,
              1280
            ],
            [
              950,
              1300
            ],
            [
              1070,
              1280
            ],
            [
              1070,
              1380
            ],
            [
              940,
              1380
            ],
            [
              850,
              1405
            ],
            [
              760,
              1380
            ]
          ]
        ],
        "inward_feather_pixels": 12,
        "phase_offsets": [
          "zero",
          "pi_over_3"
        ],
        "wavelength_pixels": 96,
        "period_seconds": 4.0,
        "diagonal": 0.15,
        "absolute_amplitude_cap": 0.06,
        "source_amplitude_fraction": 0.16
      }
    },
    {
      "image_id": "bg-still-water-night",
      "asset": "pilot-006-img-bg-still-water-night-sha256-7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2.png",
      "sha256": "7d85453374b1c6920f9312cf19c7719941e594dcbcc96346b67435f1c56084e2",
      "metadata_sha256": "dfe5d78c4c7727369c4b10f31ffa5c5e11e199d5b70a711328b786e8bad527f9",
      "nominal_start": 20.977,
      "nominal_end": 42.0,
      "visual_profile": "native_pond_rest_v2",
      "camera": {
        "source_width": 2048,
        "source_height": 2048,
        "window_width": 1152,
        "window_height": 2048,
        "y": 0,
        "profile": "smoothstep_pan_v1",
        "x": [
          448.0,
          480.0
        ],
        "frames": 638
      }
    }
  ],
  "release": {
    "target_slot": "2026-10-21T14:00:00Z",
    "release_deadline": "2026-10-21T13:15:00Z",
    "minimum_overall": 9.0,
    "file": "short-00.mp4"
  },
  "previous_material": {
    "file": "correction-history-96c8268f.json",
    "sha256": "5b1798377d25f54a813ed8ae1e99fbe17fa7ccab0ea4650454fcb76c5ba1cede",
    "bytes": 17623,
    "rejected_output_sha256": "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e",
    "source_run_id": "39590168285",
    "previous_plan_sha256": "95624da1b4e4e4b256faee29fb37c8bc78fdb5c9747a3be86c69d9ec0e319905"
  },
  "audio_preservation": {
    "mode": "aac_reference_remux_v1",
    "reference_asset": "pilot-006-short-00-sha256-96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e.mp4",
    "reference_sha256": "96c8268fa8b4cd270d0fbafa74bca579d12ae4a38168534b399a4709d0aa7b6e",
    "reference_bytes": 20581582,
    "aac_packets_sha256": "c4f2bade0301d93a2b1ad03335bfceeedb403cb9faff72f673fc6c15de564555",
    "pcm_comparison": "same_ffmpeg_pcm_s32le_exact",
    "sample_rate": 48000,
    "channels": 2,
    "presentation_samples": 2016000,
    "packet_count": 1970,
    "first_pts_samples": -1024,
    "skip_samples": 1024,
    "last_pts_samples": 2015232,
    "last_duration_samples": 768,
    "codec_frame_samples": 1024
  }
}''')


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
    require(digest == HISTORY_SHA256 and Path(path).stat().st_size == 17623, "HISTORY_RAW_SHA256_MISMATCH")
    require(type(history) is dict and history.get("source_pilot") == "pilot-006", "HISTORY_SCHEMA")
    return DENIED_OUTPUTS


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
    plan = _plan_file(CANONICAL_PILOT / "shorts/correction-plan-v2.json")
    failed = historical_failed_hashes(CANONICAL_PILOT / "shorts/correction-history-96c8268f.json")
    require(hash_file(safe_path(CANONICAL_PILOT / "shorts/correction-plan.json")) == LEGACY_PLAN_SHA256,
            "LEGACY_PLAN_CHANGED")
    require(hash_file(safe_path(CANONICAL_PILOT / "shorts/correction-history.json")) == LEGACY_HISTORY_SHA256,
            "LEGACY_HISTORY_CHANGED")
    docs = _sources(CANONICAL_PILOT)
    return plan, failed, docs


def preflight(pilot_dir, plan_path, history_path):
    """One persisted attempt, not distributed exactly-once after an unknown run."""
    pilot = safe_path(pilot_dir, directory=True)
    require(pilot.resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
    require(safe_path(plan_path).resolve() == (pilot / "shorts/correction-plan-v2.json").resolve(), "PLAN_PATH_MISMATCH")
    require(safe_path(history_path).resolve() == (pilot / "shorts/correction-history-96c8268f.json").resolve(), "HISTORY_PATH_MISMATCH")
    plan = _plan_file(plan_path)
    historical_failed_hashes(history_path)
    require(hash_file(safe_path(pilot / "shorts/shorts.json")) == HISTORY_SHA256, "CANONICAL_ATTEMPT_ALREADY_CHANGED")
    _contract()
    require(datetime.now(timezone.utc) <= utc_date(LEAD_DEADLINE), "TARGET_SLOT_LEAD_MISSED")
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
    preflight(CANONICAL_PILOT, plan_path, CANONICAL_PILOT / "shorts/correction-history-96c8268f.json")
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
        {"image_id": "bg-healing-stream-night", "start_frame": 0, "end_frame": 637,
         "nominal_start_frame": 0, "nominal_end_frame": 629},
        {"image_id": "bg-still-water-night", "start_frame": 622, "end_frame": 1260,
         "nominal_start_frame": 629, "nominal_end_frame": 1260}]}


def _record(spec):
    require(type(spec) is dict and type(spec.get("shorts")) is list and len(spec["shorts"]) == 1
            and type(spec["shorts"][0]) is dict, "EXACTLY_ONE_SHORT_REQUIRED")
    record = spec["shorts"][0]
    require(record.get("file") == "short-00.mp4", "OUTPUT_FILENAME_MISMATCH")
    return record


def _no_mixed_authority(value):
    if type(value) is dict:
        require(not ({"review_recovery", "review_recovery_execution", "owner_exception", "correction_review_attempt", "correction_http_recovery_attempt"} & value.keys()), "MIXED_AUTHORITY")
        for item in value.values():
            _no_mixed_authority(item)
    elif type(value) is list:
        for item in value:
            _no_mixed_authority(item)


def _bind_record(spec, plan, record, output_hash, docs):
    _no_mixed_authority(spec)
    require(type(output_hash) is str and HASH.fullmatch(output_hash), "INVALID_OUTPUT_SHA256")
    require(spec.get("source_pilot") == "pilot-006" and exact(spec.get("edit_plan"), plan), "PLAN_BINDING_MISMATCH")
    require(record.get("sha256") == output_hash and output_hash not in DENIED_OUTPUTS, "OUTPUT_SHA256_MISMATCH")
    for key, expected in (("source_start", 813.728), ("source_end", 854.417), ("seconds", 42.0)):
        require(number(record.get(key)) and abs(record[key] - expected) <= (0.011 if key == "seconds" else 0), "RECORD_INTERVAL_MISMATCH")
    require(record.get("hook_mode") == "caption_only" and record.get("hook_shown") is True, "HOOK_MODE_MISMATCH")
    for key in ("hook", "title", "reference"):
        require(key in record and record[key] == plan["candidate"][key], "EDITORIAL_IDENTITY_MISMATCH")
    require(exact(record.get("scenes"), [s["image_id"] for s in plan["scenes"]])
            and record.get("figure") is False and record.get("parallax") is False, "RECORD_SCENES_MISMATCH")
    require(exact(record.get("render_plan"), frame_plan(plan)), "RENDER_PLAN_MISMATCH")
    selected = validate_plan(plan, docs["timeline"], docs["script"], docs["inputs"],
                             raw_sha256={k: plan["source_sha256"][k] for k in ("timeline", "script", "inputs")})["chosen"][0]
    require(record.get("text") == selected["text"] and exact(record.get("segments"), selected["segments"]), "SOURCE_TEXT_MISMATCH")




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
    require(bool(pts) and all(number(p) for p in pts), "VIDEO_PTS_MALFORMED")
    pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0",
                "-vn", "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"])
    require(not pcm.stderr.strip(), "OUTPUT_AUDIO_DECODE_FAILED")
    measured = {"decoded_frame_count": len(pts), "fps": float(Fraction(v["r_frame_rate"])),
                "seconds": float(info["format"]["duration"]), "width": v["width"], "height": v["height"],
                "video_codec": v["codec_name"], "audio_codec": a["codec_name"],
                "audio_sample_rate": int(a["sample_rate"]), "audio_channels": a["channels"],
                "decoded_audio_samples": len(pcm.stdout) // (2 * a["channels"]),
                "presentation_audio_samples": round(int(a["duration_ts"]) * Fraction(a["time_base"]) * 48000),
                "first_pts": pts[0], "last_pts": pts[-1], "pts_uniform": len(pts) == 1260 and all(abs(p - i / 30) <= 1e-6 for i, p in enumerate(pts)),
                "audio_packets": _audio_packets(path, a),
                "black_intervals": _black_intervals(path, len(pts)),
                "render_plan": deepcopy(renderer_plan), "status": "PASS"}
    measured["status"] = _video_state(measured, plan, measuring=True)
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




def _editorial_metadata(plan, docs):
    # This is source/renderer metadata, not an OCR or motion-quality claim.
    sentences = docs["timeline"]["sentences"][191:203]
    return {"caption_source_intervals": [{"text": s["text"], "start": round(s["start"] - 813.728, 3),
                                           "end": round(s["end"] - 813.728, 3)} for s in sentences],
            "caption_mode": "caption_only", "reference": plan["candidate"]["reference"],
            "scenes": deepcopy(plan["scenes"])}


def validate_media_checks(checks, plan, output_hash, *, docs, now_utc=None):
    keys = {"version", "plan_sha256", "history_sha256", "source_sha256", "output_sha256", "source_voice_sha256",
            "source_music_sha256", "source_image_sha256", "source_durations", "measured_at", "acoustic", "video", "editorial_metadata", "status", "audio_preservation"}
    require(type(checks) is dict and checks.keys() == keys, "MEDIA_CHECKS_SCHEMA")
    require(checks["version"] == "shorts-006-media-checks-v2" and checks["plan_sha256"] == PLAN_SHA256
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
    _validate_audio_preservation(checks["audio_preservation"], plan)
    acoustic_state = _acoustic_state(checks["acoustic"], plan)
    video_state = _video_state(checks["video"], plan)
    require(exact(checks["editorial_metadata"], _editorial_metadata(plan, docs)), "EDITORIAL_METADATA_MISMATCH")
    state = "PASS" if acoustic_state == video_state == "PASS" else "FAIL"
    require(checks["status"] == state, "MEDIA_FALSE_STATUS")
    return state


def check_media(work, plan, manifest, voice_flac, music, images_dir, history_path, reference_mp4):
    spec, original_hash = read_json(safe_path(manifest))
    require(JOURNAL not in spec and "finalization" not in spec
        and "review" not in _record(spec), "MATERIAL_PREVIOUS_ATTEMPT_EVIDENCE")
    _no_mixed_authority(spec)
    spec = _disable(spec)
    expected_hash = hashlib.sha256((json.dumps(spec, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")).hexdigest()
    require(hash_file(safe_path(manifest)) == original_hash, "INPUT_CHANGED")
    atomic_json(manifest, spec)
    require(hash_file(safe_path(manifest)) == expected_hash, "INPUT_CHANGED")
    checks = {"version": "shorts-006-media-checks-v2", "status": "FAIL"}
    reason = None
    try:
        record = _record(spec)
        preflight(CANONICAL_PILOT, CANONICAL_PILOT / "shorts/correction-plan-v2.json",
                  CANONICAL_PILOT / "shorts/correction-history-96c8268f.json")
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
            meta, meta_hash = read_json(safe_path(Path(images_dir) / (ident + ".json")))
            require(meta_hash == scene["metadata_sha256"], "IMAGE_METADATA_HASH_MISMATCH")
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
        checks = {"version": "shorts-006-media-checks-v2", "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256,
                  "source_sha256": deepcopy(contract["source_sha256"]), "output_sha256": output_hash,
                  "source_voice_sha256": sources["voice"], "source_music_sha256": sources["music"],
                  "source_image_sha256": images, "source_durations": durations,
                  "measured_at": datetime.now(timezone.utc).isoformat(), "acoustic": acoustic_measurements(pcm.stdout),
                  "video": measure_video(output, contract, record["render_plan"]),
                  "editorial_metadata": _editorial_metadata(contract, docs), "status": "PASS",
                  "audio_preservation": verify_audio_remux(reference_mp4, output, contract)}
        checks["status"] = "PASS" if _acoustic_state(checks["acoustic"], contract) == _video_state(checks["video"], contract) == "PASS" else "FAIL"
        validate_media_checks(checks, contract, output_hash, docs=docs)
        require(hash_file(output) == output_hash and hash_file(voice_flac) == sources["voice"]
                and hash_file(music) == sources["music"], "MEDIA_CHANGED_DURING_MEASUREMENT")
        for ident, digest in images.items():
            require(hash_file(Path(images_dir) / (ident + ".png")) == digest, "IMAGE_CHANGED_DURING_MEASUREMENT")
        preflight(CANONICAL_PILOT, CANONICAL_PILOT / "shorts/correction-plan-v2.json",
                  CANONICAL_PILOT / "shorts/correction-history-96c8268f.json")
    except EvidenceError as error:
        reason = str(error)
    except Exception:
        reason = "MEDIA_MEASUREMENT_ERROR"
    if reason:
        checks["status"] = "FAIL"
    require(hash_file(safe_path(manifest)) == expected_hash, "INPUT_CHANGED")
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
    require(hash_file(safe_path(manifest)) == expected_hash, "INPUT_CHANGED")
    atomic_json(manifest, spec)
    if reason is not None:
        raise EvidenceError(reason)
    return checks







def _evaluate(spec, actual_output_sha256, now, media, media_hash, contract):
    plan, failed, docs = contract
    record = _record(spec)
    http_release = _validate_material_attempt(spec, actual_output_sha256, media_hash, now)
    _bind_record(spec, plan, record, actual_output_sha256, docs)
    require(actual_output_sha256 not in failed, "HISTORICAL_EDITORIAL_FAIL_BYTES")
    require(type(media_hash) is str and HASH.fullmatch(media_hash)
            and record.get("media_checks_sha256") == media_hash and exact(record.get("media_checks"), media), "MEDIA_FILE_BINDING_MISMATCH")
    media_state = validate_media_checks(media, plan, actual_output_sha256, docs=docs, now_utc=now)
    require(record.get("qa_output_sha256") == actual_output_sha256, "QA_OUTPUT_HASH_MISMATCH")
    qa = _qa_verdict(record.get("qa"), 42.0)
    review = _review_verdict(record.get("review"), actual_output_sha256)
    require(exact(spec.get("review_rubric"), {"items": list(RUBRIC), "pass_item": 7, "pass_overall": 8}), "REVIEW_RUBRIC_MISMATCH")
    previous = record.get("previous_editorial_review")
    require(not (type(previous) is dict and previous.get("status") == "FAIL"
                 and previous.get("output_sha256") in (None, actual_output_sha256)), "PREVIOUS_FAILED_BYTES")
    if media_state != "PASS":
        return "MEDIA_CHECKS_FAIL"
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
    """Pure eligibility followed by last-clock, source/media/output and CAS checks."""
    path = safe_path(manifest)
    spec, original_hash = read_json(path)
    actual = None
    try:
        record = _record(spec)
        output = safe_path(mp4)
        require(output.resolve() == (path.parent / record["file"]).resolve(), "OUTPUT_PATH_MISMATCH")
        actual = hash_file(output)
        contract = _contract()
        media, mh = read_json(safe_path(path.parent / MEDIA_FILE))
        data = {"path": path, "output": output, "output_hash": actual, "contract": contract,
            "media": media, "media_hash": mh}
        return _install_finalized(data, spec, original_hash)
    except Exception as error:
        require(hash_file(safe_path(path)) == original_hash, "INPUT_CHANGED")
        guarded = _disable(spec)
        reason = str(error) if isinstance(error, EvidenceError) else "MALFORMED_EVIDENCE"
        now = datetime.now(timezone.utc)
        guarded["release_status"] = reason
        guarded["finalization"] = {"kind": KIND, "status": "ERROR", "source_pilot": "pilot-006",
            "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256, "output_sha256": actual,
            "target_slot": TARGET_SLOT, "release_deadline": LEAD_DEADLINE,
            "validated_at": now.isoformat(), "release_status": reason}
        require(hash_file(safe_path(path)) == original_hash, "INPUT_CHANGED")
        atomic_json(path, guarded)
        return guarded


def binding(spec, *, pilot_dir):
    """Publication eligibility from complete gates and actual canonical files.

    The caller supplies freshly calculated raw digests, then this routine
    independently reopens the pinned documents. MP4 rehash is the publisher's
    responsibility; it is unavailable after normal local-media cleanup.
    """
    require(safe_path(pilot_dir, directory=True).resolve() == CANONICAL_PILOT.resolve(), "PILOT_PATH_MISMATCH")
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
    require(now <= datetime.now(timezone.utc), "FINALIZATION_IN_FUTURE")
    require(now <= utc_date(LEAD_DEADLINE), "TARGET_SLOT_LEAD_MISSED")
    media, mh = read_json(safe_path(CANONICAL_PILOT / "shorts" / MEDIA_FILE))
    release = _evaluate(spec, final["output_sha256"], now, media, mh, contract)
    record = _record(spec)
    require(release == "READY" and record.get("publish") is True and record.get("release_status") == "READY"
            and spec.get("release_status") == "READY", "CORRECTION_NOT_ELIGIBLE")
    require(now <= datetime.now(timezone.utc) <= utc_date(LEAD_DEADLINE), "TARGET_SLOT_LEAD_MISSED")
    return {"output_sha256": final["output_sha256"], "target_slot": TARGET_SLOT,
            "release_deadline": LEAD_DEADLINE, "file": "short-00.mp4",
            "plan_sha256": PLAN_SHA256, "metadata_profile": "rest-v1"}




def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _digest_value(value):
    require(type(value) is str and re.fullmatch(r"SHA256:[0-9a-fA-F]{64}", value), "AUDIO_DIGEST_SCHEMA")
    return value.split(":", 1)[1].lower()


def _packet_manifest(packets):
    require(type(packets) is list and len(packets) == 1970, "AUDIO_PACKET_COUNT_FAIL")
    normalized = []
    side_keys = {"side_data_type", "skip_samples", "discard_padding", "skip_reason", "discard_reason"}
    for i, p in enumerate(packets):
        require(type(p) is dict, "AUDIO_PACKET_SCHEMA")
        size = p.get("size")
        require(type(size) is int or type(size) is str and re.fullmatch(r"[0-9]+", size), "AUDIO_PACKET_SCHEMA")
        size = int(size)
        require(size > 0 and all(type(p.get(k)) is int for k in ("pts", "dts", "duration")), "AUDIO_PACKET_SCHEMA")
        require(p["pts"] == p["dts"] == (i - 1) * 1024
                and p["duration"] == (768 if i == 1969 else 1024), "AUDIO_PACKET_CLOCK_FAIL")
        side = p.get("side_data_list", [])
        require(type(side) is list, "AUDIO_SIDE_DATA_SCHEMA")
        for entry in side:
            require(type(entry) is dict and entry.keys() == side_keys and entry["side_data_type"] == "Skip Samples"
                    and all(type(entry[k]) is int and entry[k] >= 0 for k in side_keys - {"side_data_type"}),
                    "AUDIO_SIDE_DATA_SCHEMA")
        require(side == ([{"side_data_type": "Skip Samples", "skip_samples": 1024,
                "discard_padding": 0, "skip_reason": 0, "discard_reason": 0}] if i == 0 else []), "AUDIO_PRIMING_MISMATCH")
        normalized.append({"data_hash": _digest_value(p.get("data_hash")), "size": size,
            "pts": p["pts"], "dts": p["dts"], "duration": p["duration"], "side_data_list": deepcopy(side)})
    return normalized


def _audio_snapshot(path):
    probed = _run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_streams",
        "-show_packets", "-show_data_hash", "sha256", "-of", "json", str(path)])
    require(not probed.stderr.strip(), "AUDIO_PACKET_PROBE_FAILED")
    data = json.loads(probed.stdout)
    require(type(data.get("streams")) is list and len(data["streams"]) == 1, "AUDIO_STREAM_MISMATCH")
    stream = data["streams"][0]
    require(stream.get("codec_name") == "aac" and stream.get("sample_rate") == "48000"
            and type(stream.get("channels")) is int and stream["channels"] == 2
            and stream.get("time_base") == "1/48000" and type(stream.get("start_pts")) is int
            and stream["start_pts"] == 0 and type(stream.get("duration_ts")) is int
            and stream["duration_ts"] == 2016000, "AUDIO_PRESENTATION_MISMATCH")
    packets = _packet_manifest(data.get("packets"))
    payload = _run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:a:0",
        "-vn", "-sn", "-dn", "-c:a", "copy", "-f", "hash", "-hash", "sha256", "-"])
    require(not payload.stderr.strip(), "AUDIO_PACKET_HASH_FAILED")
    match = re.fullmatch(rb"SHA256=([0-9a-f]{64})\s*", payload.stdout)
    require(match is not None, "AUDIO_PACKET_HASH_FAILED")
    pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0",
        "-vn", "-sn", "-dn", "-acodec", "pcm_s32le", "-f", "s32le", "pipe:1"])
    require(not pcm.stderr.strip() and len(pcm.stdout) % 8 == 0, "AUDIO_PCM_DECODE_FAILED")
    count = len(pcm.stdout) // 8
    require(count in (2016000, 2016256), "OUTPUT_PCM_COUNT_FAIL")
    return {"aac_packets_sha256": match.group(1).decode("ascii"),
        "packet_manifest_sha256": _canonical_hash(packets), "extradata_sha256": _digest_value(stream.get("extradata_hash")),
        "pcm_sha256": hashlib.sha256(pcm.stdout).hexdigest(), "pcm_samples": count}


def _ffmpeg_version():
    result = _run(["ffmpeg", "-version"])
    first = result.stdout.decode("utf-8", errors="strict").splitlines()[0]
    require(0 < len(first) <= 512, "FFMPEG_VERSION_INVALID")
    return first


def _validate_audio_preservation(proof, plan):
    require(type(proof) is dict and proof.keys() == {"version", "reference_sha256", "reference_bytes",
        "ffmpeg_version", "reference", "output"}, "AUDIO_PRESERVATION_SCHEMA")
    expected = plan["audio_preservation"]
    require(proof["version"] == "aac-remux-proof-v1" and proof["reference_sha256"] == expected["reference_sha256"]
        and type(proof["reference_bytes"]) is int and proof["reference_bytes"] == expected["reference_bytes"], "AUDIO_REFERENCE_BINDING")
    require(type(proof["ffmpeg_version"]) is str and 0 < len(proof["ffmpeg_version"]) <= 512, "FFMPEG_VERSION_INVALID")
    fields = {"aac_packets_sha256", "packet_manifest_sha256", "extradata_sha256", "pcm_sha256", "pcm_samples"}
    for snapshot in (proof["reference"], proof["output"]):
        require(type(snapshot) is dict and snapshot.keys() == fields, "AUDIO_SNAPSHOT_SCHEMA")
        require(all(type(snapshot[k]) is str and HASH.fullmatch(snapshot[k]) for k in fields - {"pcm_samples"}), "AUDIO_SNAPSHOT_HASH")
        require(type(snapshot["pcm_samples"]) is int and snapshot["pcm_samples"] in (2016000, 2016256), "OUTPUT_PCM_COUNT_FAIL")
        require(snapshot["aac_packets_sha256"] == expected["aac_packets_sha256"], "AUDIO_PAYLOAD_CHANGED")
    require(exact(proof["reference"], proof["output"]), "AUDIO_REMUX_CHANGED")
    return proof


def _reference_identity(reference, plan):
    path = safe_path(reference)
    expected = plan["audio_preservation"]
    require(path.stat().st_size == expected["reference_bytes"] and hash_file(path) == expected["reference_sha256"],
        "AUDIO_REFERENCE_CHANGED")
    return path


def verify_audio_reference(reference_mp4, plan):
    validate_plan_schema(plan)
    path = _reference_identity(reference_mp4, plan)
    version = _ffmpeg_version()
    snapshot = _audio_snapshot(path)
    _reference_identity(path, plan)
    require(_ffmpeg_version() == version, "FFMPEG_BINARY_CHANGED")
    proof = {"version": "aac-remux-proof-v1", "reference_sha256": plan["audio_preservation"]["reference_sha256"],
        "reference_bytes": plan["audio_preservation"]["reference_bytes"], "ffmpeg_version": version,
        "reference": snapshot, "output": deepcopy(snapshot)}
    return deepcopy(_validate_audio_preservation(proof, plan))


def verify_audio_remux(reference_mp4, output_mp4, plan):
    output = safe_path(output_mp4)
    before = hash_file(output)
    require(before not in DENIED_OUTPUTS, "HISTORICAL_EDITORIAL_FAIL_BYTES")
    proof = verify_audio_reference(reference_mp4, plan)
    proof["output"] = _audio_snapshot(output)
    _reference_identity(reference_mp4, plan)
    require(hash_file(output) == before and _ffmpeg_version() == proof["ffmpeg_version"], "MEDIA_CHANGED_DURING_MEASUREMENT")
    return deepcopy(_validate_audio_preservation(proof, plan))


def _attempt_constants(output_hash, media_hash):
    return {"version": "shorts-006-material-review-attempt-v1", "source_run_id": "39590168285",
        "source_manifest_sha256": HISTORY_SHA256, "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256,
        "media_sha256": media_hash, "output_sha256": output_hash, "target_slot": TARGET_SLOT,
        "cutoff": LEAD_DEADLINE, "http_policy": "designated-review-http-v1"}


def _validate_material_attempt(spec, output_hash, media_hash, now):
    audit = spec.get(JOURNAL)
    review = _record(spec).get("review", {})
    if JOURNAL not in spec:
        require(type(review) is dict and review.get("status", "").startswith("NOT_REVIEWED_"), "MATERIAL_ATTEMPT_REQUIRED")
        return None
    constants = _attempt_constants(output_hash, media_hash)
    keys = set(constants) | HTTP_AUDIT_KEYS | {"run_id", "run_attempt", "started_at", "completed_at", "state", "reason", "fresh_qa"}
    require(type(audit) is dict and audit.keys() == keys, "MATERIAL_ATTEMPT_SCHEMA")
    require(all(exact(audit[k], v) for k, v in constants.items()), "MATERIAL_ATTEMPT_PINS")
    require(type(audit["run_id"]) is str and re.fullmatch(r"[1-9][0-9]*", audit["run_id"])
        and audit["run_id"] not in {"39569442793", "39575597092", "39590168285"}
        and type(audit["run_attempt"]) is int and audit["run_attempt"] == 1, "MATERIAL_ATTEMPT_RUN")
    require(_qa_verdict(audit["fresh_qa"], 42.) == "PASS", "MATERIAL_FRESH_QA_FAIL")
    require(exact(audit["fresh_qa"], _record(spec).get("qa")), "MATERIAL_FRESH_QA_MISMATCH")
    start = utc_date(audit["started_at"])
    require(start.date() == utc_date(LEAD_DEADLINE).date() and start <= now and start <= utc_date(LEAD_DEADLINE), "MATERIAL_ATTEMPT_CLOCK")
    state = audit["state"]
    require(type(state) is str and state in {"STARTED", "COMPLETE", "ERROR"}, "MATERIAL_ATTEMPT_STATE")
    if state == "STARTED":
        require(all(audit[k] is None for k in ("completed_at", "reason", "http_completion", "http_elapsed_seconds"))
            and audit["transport_attempts"] == [] and audit["terminal_stage"] == "NONE"
            and audit["cleanup_status"] == "NOT_ATTEMPTED", "MATERIAL_ATTEMPT_STARTED")
    else:
        require(start <= utc_date(audit["completed_at"]) <= now, "MATERIAL_ATTEMPT_CLOCK")
        require(audit["reason"] is None if state == "COMPLETE" else
            type(audit["reason"]) is str and audit["reason"] in RECOVERY_ERRORS, "MATERIAL_ATTEMPT_REASON")
    require(state == "COMPLETE", "MATERIAL_ATTEMPT_NOT_COMPLETE")
    client = _validated_http_client_audit({k: audit[k] for k in HTTP_AUDIT_KEYS})
    trace = client["transport_attempts"]
    require(all(start <= utc_date(t["started_at"]) <= utc_date(audit["completed_at"])
        and utc_date(t["started_at"]) <= utc_date(LEAD_DEADLINE) for t in trace), "HTTP_TRACE_CLOCK")
    if review.get("status") in {"PASS", "FAIL"}:
        require(len(trace) in (1, 2) and trace[-1]["outcome"] == "SUCCESS" and trace[-1]["http_status"] == 200
            and trace[-1]["decision"] in {"RETURN", "STOP_BUDGET", "STOP_DEADLINE"}, "HTTP_SUCCESS_TRACE_REQUIRED")
    if audit["http_completion"] != "COMPLETED":
        return "HTTP_" + audit["http_completion"]
    if audit["http_elapsed_seconds"] > 600:
        return "HTTP_BUDGET_EXHAUSTED"
    if review.get("status") in {"PASS", "FAIL"}:
        require(trace[-1]["decision"] == "RETURN", "HTTP_SUCCESS_TRACE_REQUIRED")
    return None


def _material_stable(data, expected_manifest_hash):
    path, output = data["path"], data["output"]
    require(hash_file(safe_path(path)) == expected_manifest_hash, "INPUT_CHANGED")
    require(hash_file(safe_path(output)) == data["output_hash"], "OUTPUT_CHANGED")
    _contract()
    if "canonical_hash" in data:
        require(hash_file(safe_path(CANONICAL_PILOT / "shorts/shorts.json")) == data["canonical_hash"], "INPUT_CHANGED")
    require(hash_file(safe_path(path.parent / MEDIA_FILE)) == data["media_hash"], "INPUT_CHANGED")
    require(hash_file(safe_path(output)) == data["output_hash"], "OUTPUT_CHANGED")
    require(hash_file(safe_path(path)) == expected_manifest_hash, "INPUT_CHANGED")



def _install_finalized(data, spec, expected_hash, *, original=None, require_complete=False):
    _material_stable(data, expected_hash)
    install_at = datetime.now(timezone.utc)
    while True:
        finalized = finalize_manifest(spec, actual_output_sha256=data["output_hash"], now_utc=install_at,
            media_checks=data["media"], media_sha256=data["media_hash"], contract=data["contract"])
        if require_complete:
            require(finalized.get("finalization", {}).get("status") == "COMPLETE", "FINALIZATION_ERROR")
        if original is not None:
            _material_whitelist(original, finalized)
        _material_stable(data, expected_hash)
        after_checks = datetime.now(timezone.utc)
        if install_at <= utc_date(LEAD_DEADLINE) < after_checks:
            install_at = after_checks
            continue
        require(after_checks.date() == install_at.date(), "FINALIZATION_ERROR")
        require(hash_file(safe_path(data["path"])) == expected_hash, "INPUT_CHANGED")
        break
    atomic_json(data["path"], finalized)
    return finalized


def _material_whitelist(original, result):
    top = {JOURNAL, "finalization", "release_status", "publish", "shorts", "review_rubric"}
    fields = {"review", "qa", "qa_output_sha256", "owner_quality_policy", "release_status", "publish"}
    require(exact({k: v for k, v in original.items() if k not in top},
        {k: v for k, v in result.items() if k not in top}), "OUTPUT_WHITELIST_VIOLATION")
    require(exact({k: v for k, v in _record(original).items() if k not in fields},
        {k: v for k, v in _record(result).items() if k not in fields}), "OUTPUT_WHITELIST_VIOLATION")


def _review_input(manifest, output):
    path = safe_path(manifest)
    spec, raw = read_json(path)
    require(JOURNAL not in spec, "MATERIAL_ATTEMPT_ALREADY_STARTED")
    _no_mixed_authority(spec)
    record = _record(spec)
    require(not ({"finalization", "review_rubric"} & spec.keys())
        and not ({"review", "previous_editorial_review", "owner_quality_policy", "qa", "qa_output_sha256",
                  "provider_diagnostic"} & record.keys())
        and record.get("publish") is False, "MATERIAL_PREVIOUS_ATTEMPT_EVIDENCE")
    output = safe_path(output)
    require(output.resolve() == (path.parent / record["file"]).resolve(), "OUTPUT_PATH_MISMATCH")
    actual = hash_file(output)
    contract = _contract()
    _bind_record(spec, contract[0], record, actual, contract[2])
    require(hash_file(safe_path(CANONICAL_PILOT / "shorts/shorts.json")) == HISTORY_SHA256, "CANONICAL_ATTEMPT_ALREADY_CHANGED")
    media, mh = read_json(safe_path(path.parent / MEDIA_FILE))
    require(exact(record.get("media_checks"), media) and record.get("media_checks_sha256") == mh, "MEDIA_FILE_BINDING_MISMATCH")
    validate_media_checks(media, contract[0], actual, docs=contract[2], now_utc=datetime.now(timezone.utc))
    return {"canonical_hash": HISTORY_SHA256, "path": path, "spec": spec, "raw": raw, "output": output, "output_hash": actual,
        "contract": contract, "media": media, "media_hash": mh}


def review_material(manifest_path, output_path):
    """One new material review; journal before effects, never retry a persisted run."""
    data = _review_input(manifest_path, output_path)
    import shorts_qa
    fresh = shorts_qa.check(data["output"])
    _material_stable(data, data["raw"])
    verdict = _qa_verdict(fresh, 42.)
    original = deepcopy(data["spec"])
    started = _disable(original)
    rec = _record(started)
    rec.update(qa=deepcopy(fresh), qa_output_sha256=data["output_hash"],
        review={"status": "NOT_REVIEWED_MATERIAL_PENDING", "output_sha256": data["output_hash"]})
    started["review_rubric"] = {"items": list(RUBRIC), "pass_item": 7, "pass_overall": 8}
    if verdict != "PASS" or data["media"]["status"] != "PASS" or datetime.now(timezone.utc) > utc_date(LEAD_DEADLINE):
        return _install_finalized(data, started, data["raw"])
    run_id, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]*", run_id)
        and run_id not in {"39569442793", "39575597092", "39590168285"} and attempt == "1", "RECOVERY_RUN_INVALID")
    key = os.environ.get("HERO_GEMINI_API_KEY", "")
    require(bool(key.strip()), "RECOVERY_KEY_MISSING")
    _material_stable(data, data["raw"])
    start = datetime.now(timezone.utc)
    if start > utc_date(LEAD_DEADLINE):
        return _install_finalized(data, started, data["raw"])
    started[JOURNAL] = _attempt_constants(data["output_hash"], data["media_hash"]) | {
        "run_id": run_id, "run_attempt": 1, "started_at": start.isoformat(), "completed_at": None,
        "state": "STARTED", "fresh_qa": deepcopy(fresh), "reason": None,
        "transport_attempts": [], "http_completion": None, "terminal_stage": "NONE",
        "cleanup_status": "NOT_ATTEMPTED", "http_elapsed_seconds": None}
    raw = (json.dumps(started, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    started_hash = hashlib.sha256(raw).hexdigest()
    require(hash_file(safe_path(data["path"])) == data["raw"], "INPUT_CHANGED")
    atomic_json(data["path"], started)
    require(hash_file(safe_path(data["path"])) == started_hash, "INPUT_CHANGED")
    client_audit = None
    try:
        import shorts_review
        _material_stable(data, started_hash)
        # Policy.begin/check rechecks UTC before upload, including cutoff crossing
        # after STARTED. Its real empty negative audit is retained, never invented.
        policy = shorts_review.ReviewHTTPPolicy(cutoff_utc=LEAD_DEADLINE)
        try:
            review = shorts_review.review(data["output"], deepcopy(rec), key, http_policy=policy)
        except Exception as error:
            review = shorts_review.failure_record(error, data["output"])
        client_audit = _validated_http_client_audit(policy.audit())
        _material_stable(data, started_hash)
        result = deepcopy(started)
        record = _record(result)
        record["review"] = deepcopy(review)
        problems = owner_quality_policy.check(review, data["output_hash"])
        record["owner_quality_policy"] = {"minimum_overall": 9., "status": "FAIL" if problems else "PASS", "problems": problems}
        result[JOURNAL].update(client_audit)
        result[JOURNAL].update(state="COMPLETE", completed_at=datetime.now(timezone.utc).isoformat())
        return _install_finalized(data, result, started_hash, original=original, require_complete=True)
    except Exception as error:
        reason = str(error) if isinstance(error, EvidenceError) and str(error) in RECOVERY_ERRORS else "OPERATION_ERROR"
        if hash_file(safe_path(data["path"])) == started_hash:
            failed = _disable(started)
            if client_audit is not None:
                failed[JOURNAL].update(client_audit)
            failed[JOURNAL].update(state="ERROR", reason=reason, completed_at=datetime.now(timezone.utc).isoformat())
            failed["release_status"] = reason
            _record(failed)["release_status"] = reason
            failed["finalization"] = {"kind": KIND, "status": "ERROR", "source_pilot": "pilot-006",
                "plan_sha256": PLAN_SHA256, "history_sha256": HISTORY_SHA256, "output_sha256": data["output_hash"],
                "target_slot": TARGET_SLOT, "release_deadline": LEAD_DEADLINE,
                "validated_at": datetime.now(timezone.utc).isoformat(), "release_status": reason}
            atomic_json(data["path"], failed)
        raise EvidenceError(reason) from None



def _acoustic_state(value, plan):
    keys = {"pcm_sample_rate", "window_samples", "active_threshold_dbfs", "leading_inactive_seconds",
        "trailing_inactive_seconds", "first_active_sample", "last_active_sample", "narration_samples", "status"}
    require(type(value) is dict and value.keys() == keys, "ACOUSTIC_SCHEMA")
    require(type(value["pcm_sample_rate"]) is int and value["pcm_sample_rate"] == 48000
        and type(value["window_samples"]) is int and value["window_samples"] == 480
        and number(value["active_threshold_dbfs"]) and value["active_threshold_dbfs"] == -40, "ACOUSTIC_METHOD_MISMATCH")
    first, last, count = (value[k] for k in ("first_active_sample", "last_active_sample", "narration_samples"))
    require(all(type(x) is int for x in (first, last, count)) and count == plan["audio"]["resampled_source_samples"]
        and 0 <= first < last <= count and first % 480 == 0 and (last % 480 == 0 or last == count), "ACOUSTIC_SAMPLE_MISMATCH")
    lead, tail = value["leading_inactive_seconds"], value["trailing_inactive_seconds"]
    require(number(lead) and number(tail) and lead >= 0 and tail >= 0
        and abs(lead-first/48000) < 1e-12 and abs(tail-(count-last)/48000) < 1e-12, "ACOUSTIC_SAMPLE_MISMATCH")
    state = "PASS" if lead <= .3 and tail <= .3 else "FAIL"
    require(value["status"] == state, "ACOUSTIC_FALSE_STATUS")
    return state


def _video_state(value, plan, *, measuring=False):
    keys = {"decoded_frame_count", "fps", "seconds", "width", "height", "video_codec", "audio_codec",
        "audio_sample_rate", "audio_channels", "decoded_audio_samples", "presentation_audio_samples",
        "first_pts", "last_pts", "pts_uniform", "audio_packets", "black_intervals", "render_plan", "status"}
    require(type(value) is dict and value.keys() == keys, "VIDEO_SCHEMA")
    ints = {"decoded_frame_count", "width", "height", "audio_sample_rate", "audio_channels", "decoded_audio_samples", "presentation_audio_samples"}
    require(all(type(value[k]) is int and value[k] > 0 for k in ints)
        and all(number(value[k]) for k in ("fps", "seconds", "first_pts", "last_pts"))
        and all(type(value[k]) is str for k in ("video_codec", "audio_codec"))
        and type(value["pts_uniform"]) is bool and type(value["black_intervals"]) is list, "VIDEO_SCHEMA")
    for interval in value["black_intervals"]:
        require(type(interval) is dict and interval.keys() == {"start_frame", "end_frame"}
            and all(type(v) is int and v >= 0 for v in interval.values()) and interval["end_frame"] > interval["start_frame"], "BLACK_INTERVAL_SCHEMA")
    require(exact(value["render_plan"], frame_plan(plan)), "VIDEO_RENDER_PLAN_FAIL")
    checked = deepcopy(value)
    checked["status"] = "PASS"
    try:
        _validate_video(checked, plan)
        state = "PASS"
    except EvidenceError as error:
        require(str(error) in {"VIDEO_FORMAT_FAIL", "VIDEO_CODEC_FAIL", "VIDEO_DURATION_FAIL", "VIDEO_PTS_FAIL", "BLACK_FRAME_DETECTED"}, str(error))
        state = "FAIL"
    if not measuring:
        require(value["status"] == state, "VIDEO_FALSE_STATUS")
    return state


def cli(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args[:1] == ["--preflight"] and len(args) == 4:
            preflight(*args[1:])
            print(json.dumps({"status": "PREFLIGHT_PASS"}))
            return 0
        if args[:1] == ["--check-media"] and len(args) == 9:
            checks = check_media(*args[1:])
            print(json.dumps({"media_checks": checks}, allow_nan=False))
            return 0 if checks["status"] in {"PASS", "FAIL"} and len(checks) == 15 else 1
        if args[:1] in (["--finalize"], ["--review-material"]) and len(args) == 3:
            result = (review_material if args[0] == "--review-material" else finalize_file)(*args[1:])
            print(json.dumps({"finalization": result["finalization"], "publish": _record(result).get("publish", False)}, allow_nan=False))
            return 0 if result["finalization"]["status"] == "COMPLETE" else 1
        require(len(args) == 5 and not args[0].startswith("--"), "INVALID_ARGUMENTS")
        main(*args)
        return 0
    except Exception as error:
        print(json.dumps({"reason": str(error) if isinstance(error, EvidenceError) else "CORRECTION_OPERATION_FAILED", "publish": False}))
        return 1


if __name__ == "__main__":
    sys.exit(cli())
