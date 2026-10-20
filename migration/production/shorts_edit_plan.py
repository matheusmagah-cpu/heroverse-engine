#!/usr/bin/env python3
"""One frozen editorial plan and its fail-closed, hash-bound readiness barrier.

Preparation is pure (no provider, renderer or subprocess). Only --check-media
uses local ffmpeg/ffprobe. Energy windows are not phoneme recognition and frame
allocations are the renderer's graph, not independent scene recognition.
"""
from array import array
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shorts_select import validate_candidate  # noqa: E402

TARGET_SLOT = "2026-10-20T20:00:00Z"
LEAD_DEADLINE = "2026-10-20T19:45:00Z"
RUBRIC = ("hook_in_first_2s", "captions_readable_and_synced", "text_clear_of_shorts_ui", "picture_quality",
          "edit_rhythm", "audio_clarity", "stands_alone", "ending_and_loop", "policy_safe")
QA_CHECKS = {"decode_clean", "one_h264_1080x1920", "fps_30", "one_aac_stereo_48k", "duration", "loudness", "true_peak"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
HISTORY_SHA256 = "3e1357fb31d87c5e1b3f6e90fdf86c461b1232a996511a586dce2643e5a58b98"
HISTORY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "shorts-pilot-005-20261020" / "shorts" / "shorts.json"
NEW_REVIEW_CANONICAL_SHA256 = "0d80d5291959b8d718b184f894687caf63862b70bd27fe24461a766cecb6d654"
NEW_FAILED_OUTPUT_SHA256 = "3588afa8468882e7f528d204f41bbb72a8b1b27b4f21b841ab634b20ebbf0dd7"
EXPECTED_PLAN = {'version': 'shorts-editorial-plan-v2',
 'source_pilot': 'pilot-005',
 'source_baseline_sha': '7fb9e9e1fad9396b80c029212f0a3144c1428d51',
 'source_sha256': {'script': 'c0cf3d5fc0747b5f743d9d0189e9deb4326a124a9769a41d4341b14aa347359a',
                   'timeline': '53496f5a82ed391422974e517b5b895059d0040db790c2044030f06bd06245c5',
                   'inputs': '67e393596d74f77e64f5a9de143c99dbc4bc4cb2cb8e898b261900ae69623831'},
 'voice': {'asset': 'pilot-005-voice-sha256-6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc.flac',
           'sha256': '6462b7631c540a56ac4dc6ff30a488e68a21e45dae5be077c27f5e43b30f07dc'},
 'music': {'asset': 'original-rest-music.lossless.flac',
           'sha256': '1a90714dce83ce5919230a420f56cd17d81d82437303b360244d0fe0f22bbd0c'},
 'candidate': {'start': 459.86,
               'end': 499.672,
               'hook': 'Lord, protect my relationships.',
               'title': 'A Prayer for Peace in Your Relationships',
               'reference': None},
 'tail_seconds': 0.5,
 'transition': {'type': 'fade', 'seconds': 0.5},
 'scenes': [{'image_id': 'bg-dawn-lake',
             'asset': 'pilot-003-img-bg-dawn-lake-sha256-74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018.png',
             'sha256': '74d22480484ff2088b82de7d0dd83170be6171711aaeb198f96fc74f40d26018',
             'nominal_start': 0.0,
             'nominal_end': 5.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-sheltered-valley',
             'asset': 'pilot-005-img-bg-sheltered-valley-sha256-1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85.png',
             'sha256': '1d8055fd45c97ae66eead1c19f80dcaf1a9a28644761f31f41f34975bfe34d85',
             'nominal_start': 5.0,
             'nominal_end': 10.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-sunlit-road',
             'asset': 'pilot-005-img-bg-sunlit-road-sha256-79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794.png',
             'sha256': '79591089b067d1e73cc8cb5ad7c5ebcea6754a1b6eb4e1eff039de3d6abb7794',
             'nominal_start': 10.0,
             'nominal_end': 15.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-fortress-dawn',
             'asset': 'pilot-005-img-bg-fortress-dawn-sha256-8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba.png',
             'sha256': '8fe838ae8d71963474991719861e02aaf83651817031e4af59a73858ba043bba',
             'nominal_start': 15.0,
             'nominal_end': 20.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-sunrise-field',
             'asset': 'pilot-003-img-bg-sunrise-field-sha256-8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0.png',
             'sha256': '8083ef5de4d2e1bf8b078a4f8ac0af71cc9992a68c9663528149fe8255aed1e0',
             'nominal_start': 20.0,
             'nominal_end': 25.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-misty-valley',
             'asset': 'pilot-003-img-bg-misty-valley-sha256-a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc.png',
             'sha256': 'a7e0c31b6a3cd366971a604e648ec0728c1227b45ae71dcfaac0a03679f6acdc',
             'nominal_start': 25.0,
             'nominal_end': 30.0,
             'motion_profile': 'phrase_pan_right_v1'},
            {'image_id': 'bg-mountain-sunrise',
             'asset': 'pilot-003-img-bg-mountain-sunrise-sha256-886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5.png',
             'sha256': '886b55ab2de854099a05358f2a8059cd5ad8b42d1a7af482c40e2dde1b84c6c5',
             'nominal_start': 30.0,
             'nominal_end': 35.0,
             'motion_profile': 'phrase_push_in_v1'},
            {'image_id': 'bg-tower-hill',
             'asset': 'pilot-005-img-bg-tower-hill-sha256-0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961.png',
             'sha256': '0a2619e6dbddc3966d31850f2ab74e2e92738d2787ac0dcdd23ad44b7c92f961',
             'nominal_start': 35.0,
             'nominal_end': 40.312,
             'motion_profile': 'phrase_pan_right_v1'}],
 'publish': False,
 'rhythm_exception': {'id': 'pilot-005-20261020-eight-scenes-r3',
                      'target_slot': '2026-10-20T20:00:00Z',
                      'scene_count': 8,
                      'nominal_seconds': [4.0, 6.0],
                      'visible_seconds': [4.0, 6.0]},
 'hook_animation': {'profile': 'cinematic_hook_v1',
                    'start_seconds': 0.0,
                    'end_seconds': 3.0,
                    'caption_policy': 'single_track_no_duplicate'}}


class EvidenceError(ValueError):
    """Only code-owned categorical messages may leave this module."""


def require(predicate, code):
    if not predicate:
        raise EvidenceError(code)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def exact(value, expected):
    """Exact closed schema, rejecting bool-as-number, NaN, and extra keys."""
    if type(expected) is dict:
        return type(value) is dict and value.keys() == expected.keys() and all(exact(value[k], v) for k, v in expected.items())
    if type(expected) is list:
        return type(value) is list and len(value) == len(expected) and all(exact(a, b) for a, b in zip(value, expected))
    if type(expected) in (int, float):
        return number(value) and value == expected
    return type(value) is type(expected) and value == expected


def validate_plan_schema(plan):
    require(exact(plan, EXPECTED_PLAN), "INVALID_EDIT_PLAN")
    return deepcopy(plan)


def hash_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def _constant(_):
    raise EvidenceError("NONFINITE_JSON")


def _float(text):
    value = float(text)
    require(math.isfinite(value), "NONFINITE_JSON")
    return value


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float), hashlib.sha256(raw).hexdigest()


def atomic_json(path, value):
    """Replace a manifest only after a complete, finite JSON serialization."""
    path = Path(path)
    raw = (json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".shorts-", suffix=".tmp", delete=False) as f:
        name = f.name
        try:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            os.unlink(name)
            raise
    try:
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_plan(plan, timeline, script, inputs, *, raw_sha256):
    """Use raw hashes computed by the caller from these exact parsed bytes.

    No JSON reserialization or untrusted candidate text is used as provenance.
    The production entry point and producer both compute their own raw digests.
    """
    plan = validate_plan_schema(plan)
    require(exact(raw_sha256, plan["source_sha256"]), "INPUT_SHA256_MISMATCH")
    require(type(script) is dict and script.get("pilot_id") == plan["source_pilot"], "SOURCE_PILOT_MISMATCH")
    require(type(inputs) is dict and inputs.get("voice_asset") == plan["voice"]["asset"]
            and inputs.get("voice_sha256") == plan["voice"]["sha256"], "VOICE_INPUT_MISMATCH")
    try:
        refs = {s["id"]: s.get("reference") for s in script["segments"]}
        moment, reason = validate_candidate(timeline["sentences"], refs, plan["candidate"])
        require(reason is None, "SOURCE_CANDIDATE_REJECTED")
        require(moment["sentences"] == timeline["sentences"][106:116] and len(moment["sentences"]) == 10,
                "SOURCE_SENTENCE_MISMATCH")
        require(moment["start"] == plan["candidate"]["start"] and moment["end"] == plan["candidate"]["end"]
                and moment["reference"] is None, "SOURCE_INTERVAL_MISMATCH")
        require(moment["sentences"][0]["text"] == plan["candidate"]["hook"], "HOOK_SOURCE_MISMATCH")
        require(moment["segments"] == ["prayer-relationships", "prayer-words"], "SOURCE_SEGMENT_MISMATCH")
        require(all(s["image_id"] in script["backgrounds"] for s in plan["scenes"]), "IMAGE_MAPPING_MISMATCH")
    except (KeyError, TypeError, IndexError, AttributeError):
        raise EvidenceError("MALFORMED_SOURCE") from None
    return {"chosen": [deepcopy(moment)], "selection_mode": "EDITORIAL_PLAN", "rubric_model": None,
            "input_sha256": deepcopy(raw_sha256), "edit_plan": plan}


def main(plan_path, timeline_path, script_path, inputs_path, out_path):
    plan, _ = read_json(plan_path)
    timeline, th = read_json(timeline_path)
    script, sh = read_json(script_path)
    inputs, ih = read_json(inputs_path)
    prepared = validate_plan(plan, timeline, script, inputs, raw_sha256={"timeline": th, "script": sh, "inputs": ih})
    atomic_json(out_path, prepared)
    return prepared


def frame_plan(plan):
    """Shared eight-scene allocation, half-up quantized once (end exclusive).

    Only the exact owner-scoped v2 plan reaches this helper. The no-plan
    renderer has no access to its 4..6 second rhythm exception.
    """
    plan = validate_plan_schema(plan)
    q = lambda s: math.floor(s * 30 + 0.5)
    scenes = plan["scenes"]
    end = q(scenes[-1]["nominal_end"])
    fade_frames = q(plan["transition"]["seconds"])
    starts = [q(s["nominal_end"] - plan["transition"]["seconds"] / 2) for s in scenes[:-1]]
    ends = [start + fade_frames for start in starts]
    spans = [{"image_id": scene["image_id"], "start_frame": starts[i - 1] if i else 0,
              "end_frame": ends[i] if i < len(scenes) - 1 else end,
              "nominal_start_frame": q(scene["nominal_start"]), "nominal_end_frame": q(scene["nominal_end"])}
             for i, scene in enumerate(scenes)]
    return {"expected_frame_count": end, "fps": 30, "scene_frame_spans": spans}


def utc_date(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None and parsed.utcoffset() is not None
                and parsed.utcoffset().total_seconds() == 0, "INVALID_UTC_DATE")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, AttributeError, OverflowError):
        raise EvidenceError("INVALID_UTC_DATE") from None


def _manifest_record(spec):
    require(type(spec) is dict and type(spec.get("shorts")) is list and len(spec["shorts"]) == 1
            and type(spec["shorts"][0]) is dict, "EXACTLY_ONE_SHORT_REQUIRED")
    record = spec["shorts"][0]
    require(record.get("file") == "short-00.mp4", "INVALID_OUTPUT_FILENAME")
    return record


def _disable(spec):
    """Never preserve an inherited publish flag, including malformed records."""
    if type(spec) is not dict:
        return {"shorts": [], "publish": False}
    result = deepcopy(spec)
    result["publish"] = False
    if type(result.get("shorts")) is list:
        for record in result["shorts"]:
            if type(record) is dict:
                record["publish"] = False
    return result


def _bind_record(spec, plan, record, output_hash):
    require(type(output_hash) is str and HASH.fullmatch(output_hash), "INVALID_OUTPUT_SHA256")
    require(spec.get("source_pilot") == plan["source_pilot"] and exact(spec.get("edit_plan"), plan), "PLAN_BINDING_MISMATCH")
    require(record.get("sha256") == output_hash, "OUTPUT_SHA256_MISMATCH")
    require(number(record.get("source_start")) and record["source_start"] == plan["candidate"]["start"]
            and number(record.get("source_end")) and record["source_end"] == plan["candidate"]["end"], "RECORD_INTERVAL_MISMATCH")
    require(record.get("hook_mode") == "caption_only", "RECORD_HOOK_MODE_MISMATCH")
    require(record.get("hook") == plan["candidate"]["hook"] and record.get("hook_shown") is True
            and record.get("title") == plan["candidate"]["title"] and record.get("reference") is None,
            "RECORD_EDITORIAL_MISMATCH")
    require(exact(record.get("scenes"), [s["image_id"] for s in plan["scenes"]])
            and record.get("figure") is False and record.get("parallax") is False, "RECORD_SCENES_MISMATCH")
    require(exact(record.get("render_plan"), frame_plan(plan)), "RENDER_PLAN_MISMATCH")


def acoustic_measurements(pcm):
    """RMS of mono signed little-endian 16-bit PCM; last sample is exclusive."""
    require(type(pcm) is bytes and len(pcm) > 0 and len(pcm) % 2 == 0, "INVALID_PCM")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    active = []
    threshold_squared = 32768 ** 2 * 10 ** (-40.0 / 10)
    for start in range(0, len(samples), 480):
        window = samples[start:start + 480]
        if sum(x * x for x in window) / len(window) >= threshold_squared:
            active.append((start, min(start + 480, len(samples))))
    first, last = (active[0][0], active[-1][1]) if active else (None, None)
    result = {"pcm_sample_rate": 48000, "window_samples": 480, "active_threshold_dbfs": -40.0,
              "leading_inactive_seconds": first / 48000 if first is not None else None,
              "trailing_inactive_seconds": (len(samples) - last) / 48000 if last is not None else None,
              "first_active_sample": first, "last_active_sample": last, "narration_samples": len(samples), "status": "FAIL"}
    if first is not None and first / 48000 <= 0.3 and (len(samples) - last) / 48000 <= 0.3:
        result["status"] = "PASS"
    return result


def _run(command):
    try:
        result = subprocess.run(command, capture_output=True, check=False, timeout=600)
    except (OSError, subprocess.SubprocessError):
        raise EvidenceError("MEDIA_TOOL_FAILED") from None
    require(result.returncode == 0, "MEDIA_DECODE_FAILED")
    return result


def measure_video(path, plan, renderer_plan):
    require(exact(renderer_plan, frame_plan(plan)), "RENDER_PLAN_MISMATCH")
    probe = _run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                  "stream=nb_read_frames,r_frame_rate:format=duration", "-of", "json", str(path)])
    require(not probe.stderr.strip(), "VIDEO_PROBE_FAILED")
    try:
        info = json.loads(probe.stdout)
        require(len(info["streams"]) == 1, "VIDEO_STREAM_MISMATCH")
        stream = info["streams"][0]
        count = int(stream["nb_read_frames"])
        fps = float(Fraction(stream["r_frame_rate"]))
        seconds = float(info["format"]["duration"])
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        raise EvidenceError("VIDEO_PROBE_MALFORMED") from None
    decoded = _run(["ffmpeg", "-hide_banner", "-nostdin", "-v", "info", "-xerror", "-err_detect", "explode",
                    "-i", str(path), "-map", "0:v:0", "-vf",
                    "blackdetect=d=0.03333333333333333:pix_th=0.02:pic_th=0.99,metadata=mode=print", "-an", "-sn", "-dn", "-f", "null", "-"])
    log = decoded.stderr.decode("utf-8", errors="replace")
    require(type(count) is int and count > 0 and number(fps) and fps > 0, "VIDEO_PROBE_MALFORMED")
    intervals, start, metadata_frame = [], None, None
    saw_summary = False
    for line in log.splitlines():
        header = re.search(r"\bframe:(\d+)\s+pts:\s*-?\d+\s+pts_time:", line)
        if header:
            frame = int(header.group(1))
            require(0 <= frame < count and (metadata_frame is None or frame > metadata_frame), "BLACKDETECT_PARSE_FAILED")
            metadata_frame = frame
        # Validate any blackdetect summaries, but use its frame metadata below.
        # A black final frame has a start tag and no summary/end tag: the normal
        # d=1/30 log alone silently misses it. The decoded frame clock closes it.
        if any(tag in line for tag in ("black_start:", "black_end:", "black_duration:")):
            match = re.search(r"black_start:([\d.eE+-]+)\s+black_end:([\d.eE+-]+)\s+black_duration:([\d.eE+-]+)", line)
            require(match is not None, "BLACKDETECT_PARSE_FAILED")
            a, b, d = map(float, match.groups())
            require(all(number(x) for x in (a, b, d)) and 0 <= a <= b and d >= 0
                    and abs((b - a) - d) <= 1e-4, "BLACKDETECT_PARSE_FAILED")
            saw_summary = True
        if "lavfi.black_start=" in line or "lavfi.black_end=" in line:
            match = re.search(r"lavfi.black_(start|end)=([\d.eE+-]+)\s*$", line)
            require(match is not None, "BLACKDETECT_PARSE_FAILED")
            kind, reported = match.group(1), float(match.group(2))
            require(number(reported) and reported >= 0 and metadata_frame is not None
                    and math.floor(reported * fps + 0.5) == metadata_frame, "BLACKDETECT_PARSE_FAILED")
            # FFmpeg 6.1 prints times with %.6g: 40.266667 becomes 40.2667.
            # Subtraction then makes a genuine one-frame interval only .0333s.
            # Use the filter's integer frame counter, not rounded prose, for
            # durations. This changes no pixel/duration acceptance threshold.
            if kind == "start":
                require(start is None, "BLACKDETECT_PARSE_FAILED")
                start = metadata_frame
            else:
                require(start is not None and metadata_frame > start, "BLACKDETECT_PARSE_FAILED")
                intervals.append({"start": start / fps, "end": metadata_frame / fps,
                                  "duration": (metadata_frame - start) / fps})
                start = None
    if start is not None:
        require(count > start, "BLACKDETECT_PARSE_FAILED")
        intervals.append({"start": start / fps, "end": count / fps, "duration": (count - start) / fps})
    require(not saw_summary or bool(intervals), "BLACKDETECT_PARSE_FAILED")
    video = {"decoded_frame_count": count, "fps": fps, "seconds": seconds,
             "expected_frame_count": renderer_plan["expected_frame_count"], "black_intervals": intervals,
             "scene_frame_spans": deepcopy(renderer_plan["scene_frame_spans"]), "status": "PASS"}
    try:
        _validate_video(video, plan)
    except EvidenceError:
        video["status"] = "FAIL"
    return video


def _validate_acoustic(acoustic, plan):
    keys = {"pcm_sample_rate", "window_samples", "active_threshold_dbfs", "leading_inactive_seconds",
            "trailing_inactive_seconds", "first_active_sample", "last_active_sample", "narration_samples", "status"}
    require(type(acoustic) is dict and acoustic.keys() == keys, "ACOUSTIC_SCHEMA")
    require(type(acoustic["pcm_sample_rate"]) is int and acoustic["pcm_sample_rate"] == 48000
            and type(acoustic["window_samples"]) is int and acoustic["window_samples"] == 480
            and number(acoustic["active_threshold_dbfs"]) and acoustic["active_threshold_dbfs"] == -40.0,
            "ACOUSTIC_METHOD_MISMATCH")
    first, last, n = (acoustic[k] for k in ("first_active_sample", "last_active_sample", "narration_samples"))
    expected = round((plan["candidate"]["end"] - plan["candidate"]["start"]) * 48000)
    require(all(type(x) is int for x in (first, last, n)) and n == expected and 0 <= first < last <= n
            and first % 480 == 0 and (last % 480 == 0 or last == n), "ACOUSTIC_SAMPLE_MISMATCH")
    lead, tail = acoustic["leading_inactive_seconds"], acoustic["trailing_inactive_seconds"]
    require(number(lead) and number(tail) and abs(lead - first / 48000) <= 1e-12
            and abs(tail - (n - last) / 48000) <= 1e-12 and 0 <= lead <= 0.3 and 0 <= tail <= 0.3,
            "ACOUSTIC_ONSET_OR_ENDING_FAIL")
    require(acoustic["status"] == "PASS", "ACOUSTIC_NOT_PASS")


def _validate_video(video, plan):
    keys = {"decoded_frame_count", "fps", "seconds", "expected_frame_count", "black_intervals", "scene_frame_spans", "status"}
    require(type(video) is dict and video.keys() == keys, "VIDEO_SCHEMA")
    expected = frame_plan(plan)
    require(type(video["decoded_frame_count"]) is int and abs(video["decoded_frame_count"] - expected["expected_frame_count"]) <= 1
            and type(video["expected_frame_count"]) is int and video["expected_frame_count"] == expected["expected_frame_count"],
            "VIDEO_FRAME_COUNT_FAIL")
    require(number(video["fps"]) and video["fps"] == 30 and number(video["seconds"])
            and abs(video["seconds"] - plan["scenes"][-1]["nominal_end"]) <= 1 / 30 + 1e-9,
            "VIDEO_CLOCK_FAIL")
    require(exact(video["scene_frame_spans"], expected["scene_frame_spans"]), "VIDEO_SCENE_SPANS_FAIL")
    for scene in video["scene_frame_spans"]:
        require(all(type(scene[k]) is int for k in ("start_frame", "end_frame", "nominal_start_frame", "nominal_end_frame"))
                and 120 <= scene["nominal_end_frame"] - scene["nominal_start_frame"] <= 180
                and 120 <= scene["end_frame"] - scene["start_frame"] <= 180, "VIDEO_SCENE_DURATION_FAIL")
    require(type(video["black_intervals"]) is list, "BLACKDETECT_SCHEMA")
    for interval in video["black_intervals"]:
        require(type(interval) is dict and interval.keys() == {"start", "end", "duration"}
                and all(number(interval[k]) for k in interval), "BLACKDETECT_SCHEMA")
        a, b, d = (interval[k] for k in ("start", "end", "duration"))
        require(0 <= a <= b <= video["seconds"] + 1 / 30 and d >= 0 and abs(b - a - d) <= 1e-4,
                "BLACKDETECT_SCHEMA")
        require(d < 1 / 30 - 1e-6, "BLACK_FRAME_DETECTED")
    require(video["status"] == "PASS", "VIDEO_NOT_PASS")


def validate_media_checks(checks, plan, output_hash, *, now_utc=None):
    keys = {"version", "output_sha256", "source_voice_sha256", "source_music_sha256", "source_image_sha256",
            "measured_at", "acoustic", "video", "status"}
    require(type(checks) is dict and checks.keys() == keys, "MEDIA_CHECKS_SCHEMA")
    require(checks["version"] == "shorts-media-checks-v1" and checks["output_sha256"] == output_hash, "MEDIA_OUTPUT_HASH_MISMATCH")
    require(checks["source_voice_sha256"] == plan["voice"]["sha256"]
            and checks["source_music_sha256"] == plan["music"]["sha256"]
            and exact(checks["source_image_sha256"], {s["image_id"]: s["sha256"] for s in plan["scenes"]}),
            "MEDIA_SOURCE_HASH_MISMATCH")
    measured = utc_date(checks["measured_at"])
    if now_utc is not None:
        now = utc_date(now_utc)
        require(measured <= now and measured.date() == now.date(), "MEDIA_MEASUREMENT_STALE")
    _validate_acoustic(checks["acoustic"], plan)
    _validate_video(checks["video"], plan)
    require(checks["status"] == "PASS", "MEDIA_CHECKS_NOT_PASS")


def historical_failed_hashes(history_path):
    """Read-only guard against shopping another score for pinned failed bytes."""
    try:
        fixture, fixture_hash = read_json(HISTORY_FIXTURE)
    except Exception:
        raise EvidenceError("HISTORICAL_FIXTURE_UNREADABLE_OR_MALFORMED") from None
    require(fixture_hash == HISTORY_SHA256, "HISTORICAL_FIXTURE_SHA256_MISMATCH")
    try:
        history, _ = read_json(history_path)
    except Exception:
        raise EvidenceError("HISTORICAL_ARCHIVE_UNREADABLE_OR_MALFORMED") from None
    require(type(history) is dict and history.get("source_baseline_sha") == EXPECTED_PLAN["source_baseline_sha"]
            and history.get("source_sha256") == HISTORY_SHA256
            and exact(history.get("historical_records"), fixture), "HISTORICAL_ARCHIVE_MISMATCH")
    require(type(fixture) is dict and type(fixture.get("shorts")) is list, "HISTORICAL_FIXTURE_MALFORMED")
    failed = set()
    for record in fixture["shorts"]:
        require(type(record) is dict and type(record.get("review")) is dict
                and type(record.get("sha256")) is str and HASH.fullmatch(record["sha256"]), "HISTORICAL_FIXTURE_MALFORMED")
        if record["review"].get("status") == "FAIL":
            failed.add(record["sha256"])
    new_reviews = history.get("new_reviews")
    require(type(new_reviews) is list and len(new_reviews) == 1 and type(new_reviews[0]) is dict,
            "NEW_REVIEW_HISTORY_MISSING_OR_MALFORMED")
    try:
        canonical = json.dumps(new_reviews[0], sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                               allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise EvidenceError("NEW_REVIEW_HISTORY_MALFORMED") from None
    require(hashlib.sha256(canonical).hexdigest() == NEW_REVIEW_CANONICAL_SHA256, "NEW_REVIEW_HISTORY_SHA256_MISMATCH")
    reviewed = new_reviews[0]
    rec = _manifest_record(reviewed)
    require(reviewed.get("source_pilot") == "pilot-005" and rec.get("sha256") == NEW_FAILED_OUTPUT_SHA256
            and rec.get("qa_output_sha256") == NEW_FAILED_OUTPUT_SHA256
            and type(rec.get("review")) is dict and rec["review"].get("status") == "FAIL"
            and rec["review"].get("output_sha256") == NEW_FAILED_OUTPUT_SHA256
            and type(rec.get("media_checks")) is dict and rec["media_checks"].get("output_sha256") == NEW_FAILED_OUTPUT_SHA256
            and rec.get("publish") is False, "NEW_REVIEW_HISTORY_BINDING_MISMATCH")
    failed.add(rec["sha256"])
    return frozenset(failed)


def check_media(work, plan, manifest, voice_flac, music, images_dir, history_path):
    """Measure verified local bytes; any error returns sanitized FAIL evidence.

    The manifest stays in the fresh work directory and publish is always false.
    CLI emits evidence and MP4_UNPRESERVED on failure before frozen preserve.
    """
    spec, _ = read_json(manifest)
    spec = _disable(spec)
    atomic_json(manifest, spec)
    checks = {"version": "shorts-media-checks-v1", "output_sha256": None, "source_voice_sha256": None,
              "source_music_sha256": None, "source_image_sha256": {},
              "measured_at": datetime.now(timezone.utc).isoformat(),
              "acoustic": {"pcm_sample_rate": 48000, "window_samples": 480, "active_threshold_dbfs": -40.0,
                           "leading_inactive_seconds": None, "trailing_inactive_seconds": None,
                           "first_active_sample": None, "last_active_sample": None, "narration_samples": None, "status": "FAIL"},
              "video": {"decoded_frame_count": None, "fps": None, "seconds": None, "expected_frame_count": None,
                        "black_intervals": [], "scene_frame_spans": [], "status": "FAIL"}, "status": "FAIL"}
    reason = None
    record = None
    try:
        record = _manifest_record(spec)
        output = Path(manifest).parent / record["file"]
        checks["output_sha256"] = hash_file(output)
        if not isinstance(plan, dict):
            plan, _ = read_json(plan)
        plan = validate_plan_schema(plan)
        _bind_record(spec, plan, record, checks["output_sha256"])
        require(checks["output_sha256"] not in historical_failed_hashes(history_path), "HISTORICAL_EDITORIAL_FAIL_BYTES")
        _, timeline_hash = read_json(Path(work) / "timeline.json")
        require(timeline_hash == plan["source_sha256"]["timeline"], "INPUT_SHA256_MISMATCH")
        checks["source_voice_sha256"] = hash_file(voice_flac)
        checks["source_music_sha256"] = hash_file(music)
        for scene in plan["scenes"]:
            image_id = scene["image_id"]
            meta, _ = read_json(Path(images_dir) / (image_id + ".json"))
            require(type(meta) is dict and meta.get("id") == image_id and meta.get("release_asset") == scene["asset"]
                    and meta.get("sha256") == scene["sha256"], "IMAGE_MAPPING_MISMATCH")
            checks["source_image_sha256"][image_id] = hash_file(Path(images_dir) / (image_id + ".png"))
        require(checks["source_voice_sha256"] == plan["voice"]["sha256"]
                and checks["source_music_sha256"] == plan["music"]["sha256"]
                and exact(checks["source_image_sha256"], {s["image_id"]: s["sha256"] for s in plan["scenes"]}),
                "MEDIA_SOURCE_HASH_MISMATCH")
        voice = plan["candidate"]
        pcm = _run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-ss", f"{voice['start']:.3f}", "-i", str(voice_flac),
                    "-t", f"{voice['end'] - voice['start']:.3f}", "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "48000",
                    "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"])
        require(not pcm.stderr.strip(), "AUDIO_DECODE_FAILED")
        checks["acoustic"] = acoustic_measurements(pcm.stdout)
        checks["video"] = measure_video(output, plan, record["render_plan"])
        try:
            _validate_acoustic(checks["acoustic"], plan)
        except EvidenceError:
            checks["acoustic"]["status"] = "FAIL"
            raise
        checks["status"] = "PASS"
        validate_media_checks(checks, plan, checks["output_sha256"])
        require(hash_file(output) == checks["output_sha256"], "OUTPUT_CHANGED_DURING_MEASUREMENT")
    except EvidenceError as error:
        reason = str(error)
    except Exception:
        reason = "MEDIA_MEASUREMENT_ERROR"
    if reason:
        checks["status"] = "FAIL"
    if record is not None:
        record["media_checks"] = checks
        record["media_checks_reason"] = reason
        record["publish"] = False
    spec["release_status"] = "MEDIA_CHECKS_PASS_PENDING_REVIEW" if not reason else reason
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


def finalize_manifest(spec, *, actual_output_sha256, now_utc, target_slot):
    """Pure guard. ERROR is nonzero at the CLI; valid FAIL remains preservable."""
    guarded = _disable(spec)
    # Invalid clocks/slots are programmer errors as well as fail-closed CLI errors.
    now = utc_date(now_utc)
    require(type(target_slot) is str and target_slot == TARGET_SLOT, "TARGET_SLOT_MISMATCH")
    final = {"status": "ERROR", "output_sha256": actual_output_sha256 if type(actual_output_sha256) is str and HASH.fullmatch(actual_output_sha256) else None,
             "finalized_at": now.isoformat(), "target_slot": TARGET_SLOT}
    guarded["finalization"] = final
    try:
        record = _manifest_record(guarded)
        plan = validate_plan_schema(guarded.get("edit_plan"))
        _bind_record(guarded, plan, record, actual_output_sha256)
        checks = record.get("media_checks")
        validate_media_checks(checks, plan, actual_output_sha256, now_utc=now)
        require(number(record.get("seconds")) and abs(record["seconds"] - checks["video"]["seconds"]) <= 0.011, "RECORD_DURATION_MISMATCH")
        require(record.get("qa_output_sha256") == actual_output_sha256, "QA_OUTPUT_HASH_MISMATCH")
        qa = _qa_verdict(record.get("qa"), checks["video"]["seconds"])
        review = _review_verdict(record.get("review"), actual_output_sha256)
        require(exact(guarded.get("review_rubric"), {"items": list(RUBRIC), "pass_item": 7, "pass_overall": 8}), "REVIEW_RUBRIC_MISMATCH")
        previous = record.get("previous_editorial_review")
        require(not (type(previous) is dict and previous.get("status") == "FAIL" and review == "PASS"
                     and previous.get("output_sha256") in (None, actual_output_sha256)), "PREVIOUS_FAILED_BYTES")
        if qa != "PASS":
            release = "QA_FAIL"
        elif review != "PASS":
            release = "REVIEW_" + review
        elif now > utc_date(LEAD_DEADLINE):
            release = "TARGET_SLOT_LEAD_MISSED"
        else:
            release = "READY_FOR_TARGET_SLOT"
            record["publish"] = True
        guarded["release_status"] = release
        record["release_status"] = release
        final["status"] = "COMPLETE"
    except EvidenceError as error:
        guarded["release_status"] = str(error)
    except Exception:
        guarded["release_status"] = "MALFORMED_EVIDENCE"
    return guarded


def finalize_file(manifest, mp4):
    """Clear inherited reviewer eligibility before any operation that can fail."""
    spec, _ = read_json(manifest)
    spec = _disable(spec)
    atomic_json(manifest, spec)
    try:
        record = _manifest_record(spec)
        require(Path(mp4).resolve() == (Path(manifest).parent / record["file"]).resolve(), "OUTPUT_PATH_MISMATCH")
        output_hash = hash_file(mp4)
        guarded = finalize_manifest(spec, actual_output_sha256=output_hash,
                                    now_utc=datetime.now(timezone.utc), target_slot=TARGET_SLOT)
        require(hash_file(mp4) == output_hash, "OUTPUT_CHANGED_DURING_FINALIZATION")
        atomic_json(manifest, guarded)
        return guarded
    except Exception:
        # The already written manifest is nonpublishable, including a TOCTOU failure.
        raise


def cli(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    manifest = args[1] if args[:1] == ["--finalize"] and len(args) >= 2 else None
    if args[:1] == ["--check-media"] and len(args) >= 4:
        manifest = args[3]
    try:
        if args[:1] == ["--check-media"] and len(args) == 8:
            checks = check_media(*args[1:])
            spec, _ = read_json(manifest)
            if checks["status"] != "PASS":
                print(json.dumps({"media_checks": checks, "reason": spec.get("release_status", "MEDIA_MEASUREMENT_ERROR"),
                                  "artifact_status": "MP4_UNPRESERVED"}, allow_nan=False))
                return 1
            print(json.dumps({"media_checks": checks}, allow_nan=False))
            return 0
        if args[:1] == ["--finalize"] and len(args) == 3:
            manifest = args[1]
            spec = finalize_file(*args[1:])
            print(json.dumps({"output_sha256": spec["finalization"]["output_sha256"], "release_status": spec["release_status"],
                              "publish": spec["shorts"][0]["publish"] if spec.get("shorts") else False}))
            return 0 if spec["finalization"]["status"] == "COMPLETE" else 1
        require(len(args) == 5 and not args[0].startswith("--"), "INVALID_ARGUMENTS")
        main(*args)
        return 0
    except Exception as error:
        # A malformed JSON file is not preservable. If it can be parsed, revoke all flags.
        if manifest is not None:
            try:
                try:
                    spec, _ = read_json(manifest)
                    revoked = _disable(spec)
                except Exception:
                    revoked = {"shorts": [], "publish": False, "release_status": "MALFORMED_EVIDENCE"}
                atomic_json(manifest, revoked)
            except Exception:
                # No preserve follows the nonzero exit, even if the file is unwritable.
                pass
        reason = str(error) if isinstance(error, EvidenceError) else "EDIT_PLAN_OPERATION_FAILED"
        print(json.dumps({"reason": reason, "publish": False, "artifact_status": "MP4_UNPRESERVED"}))
        return 1


if __name__ == "__main__":
    sys.exit(cli())
