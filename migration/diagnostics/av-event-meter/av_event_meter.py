#!/usr/bin/env python3
"""Blind deterministic AV event meter. Python stdlib + local ffmpeg/ffprobe only.

Input: one media path. Output: discrete audio onsets, visual change onsets and
paired audio-minus-video offsets. It never reads manifests, answers or recipes;
thresholds adapt to each file and are not tuned per stimulus. No model,
network, provider call or approval. An onset is an operational signal event,
not a semantic finding (speech, music, effect) or perceptual approval.
"""
import array
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

VERSION = "av-event-meter-v1"

# Audio: 1 ms RMS windows. Detection is relative to the file's own noise floor
# (20th-percentile window level), never below an absolute -50 dBFS.
AUDIO_WINDOW_SECONDS = 0.001
AUDIO_FLOOR_PERCENTILE = 0.2
AUDIO_DETECT_ABOVE_FLOOR_DB = 20.0
AUDIO_DETECT_MIN_DBFS = -50.0
AUDIO_MERGE_GAP_SECONDS = 0.03
AUDIO_MIN_EVENT_SECONDS = 0.005
DB_FLOOR = -120.0

# Video: mean of the top-decile absolute luma differences between consecutive
# frames on an area-averaged 64x48 gray proxy, so a localized change is not
# diluted by a static background. Threshold = max(floor, median + k * MAD).
VIDEO_PROXY = (64, 48)
VIDEO_TOP_FRACTION = 0.1
VIDEO_MIN_DIFF = 6.0
VIDEO_MAD_K = 8.0
VIDEO_MERGE_GAP_SECONDS = 0.2

PAIR_MAX_SECONDS = 1.0
# ITU-R BT.1359 detectability: sound leading > 45 ms or lagging > 125 ms.
SYNC_LEAD_LIMIT, SYNC_LAG_LIMIT = -0.045, 0.125


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", str(path)]))


def db(value):
    return max(DB_FLOOR, 20 * math.log10(value)) if value > 0 else DB_FLOOR


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def group(indices, max_gap):
    groups = []
    for index in indices:
        if groups and index - groups[-1][-1] <= max_gap:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups


def window_levels_db(samples, channels, window):
    """Per-window RMS in dBFS, maximum over channels (no downmix cancellation)."""
    frames = len(samples) // channels
    levels = []
    for start in range(0, frames, window):
        end = min(frames, start + window)
        best = 0.0
        for channel in range(channels):
            chunk = samples[start * channels + channel:end * channels:channels]
            best = max(best, sum(value * value for value in chunk) / len(chunk))
        levels.append(db(math.sqrt(best)))
    return levels


def detect_audio_events(levels, window_seconds):
    floor = percentile(levels, AUDIO_FLOOR_PERCENTILE)
    threshold = max(AUDIO_DETECT_MIN_DBFS, floor + AUDIO_DETECT_ABOVE_FLOOR_DB)
    gap = round(AUDIO_MERGE_GAP_SECONDS / window_seconds)
    events = []
    for indices in group([i for i, level in enumerate(levels) if level >= threshold], gap):
        start, end = indices[0], indices[-1] + 1
        if (end - start) * window_seconds < AUDIO_MIN_EVENT_SECONDS:
            continue
        events.append({"onset_seconds": round(start * window_seconds, 6),
                       "end_seconds": round(end * window_seconds, 6),
                       "peak_dbfs": round(max(levels[start:end]), 2)})
    return events, {"noise_floor_dbfs": round(floor, 2),
                    "detection_threshold_dbfs": round(threshold, 2)}


def measure_audio(path, stream):
    rate, channels = int(stream["sample_rate"]), int(stream["channels"])
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
               "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"])
    samples = array.array("f")
    samples.frombytes(raw[:len(raw) - len(raw) % 4])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples or len(samples) % channels:
        raise ValueError("AUDIO_DECODE_INCOMPLETE")
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("AUDIO_NONFINITE_SAMPLES")
    window = max(1, round(rate * AUDIO_WINDOW_SECONDS))
    window_seconds = window / rate
    silent = not any(samples)
    if silent:
        events, levels = [], {"noise_floor_dbfs": DB_FLOOR, "detection_threshold_dbfs": None}
    else:
        events, levels = detect_audio_events(window_levels_db(samples, channels, window),
                                             window_seconds)
    return {"present": True, "sample_rate_hz": rate, "channels": channels,
            "decoded_seconds": round(len(samples) / channels / rate, 6),
            "exact_digital_silence": silent, "window_seconds": window_seconds,
            **levels, "onset_count": len(events), "events": events}


def frame_times(path, expected):
    packets = json.loads(run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "packet=pts_time", "-of", "json",
                              str(path)]))["packets"]
    times = sorted(float(packet["pts_time"]) for packet in packets
                   if packet.get("pts_time") not in (None, "N/A"))
    if len(times) != expected:
        raise ValueError("VIDEO_PTS_FRAME_COUNT_MISMATCH")
    return times


def measure_video(path):
    width, height = VIDEO_PROXY
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
               "-fps_mode", "passthrough", "-vf",
               f"scale={width}:{height}:flags=area,format=gray",
               "-f", "rawvideo", "pipe:1"])
    size = width * height
    if not raw or len(raw) % size:
        raise ValueError("VIDEO_DECODE_INCOMPLETE")
    count = len(raw) // size
    times = frame_times(path, count)
    luma = [sum(raw[i * size:(i + 1) * size]) / size for i in range(count)]
    top = max(1, round(size * VIDEO_TOP_FRACTION))
    diffs = [0.0] + [sum(sorted((abs(a - b) for a, b in zip(raw[i * size:(i + 1) * size],
                                                            raw[(i - 1) * size:i * size])),
                                reverse=True)[:top]) / top
                     for i in range(1, count)]
    median = statistics.median(diffs[1:]) if count > 1 else 0.0
    mad = statistics.median(abs(d - median) for d in diffs[1:]) if count > 1 else 0.0
    threshold = max(VIDEO_MIN_DIFF, median + VIDEO_MAD_K * mad)
    events = []
    changed = [i for i in range(1, count) if diffs[i] >= threshold]
    interval = statistics.median(b - a for a, b in zip(times, times[1:])) if count > 1 else 1.0
    for indices in group(changed, max(1, round(VIDEO_MERGE_GAP_SECONDS / interval))):
        first = indices[0]
        events.append({"onset_seconds": round(times[first], 6), "onset_frame": first,
                       "last_change_frame": indices[-1],
                       "direction": "brighter" if luma[first] > luma[first - 1] else "darker",
                       "peak_top_decile_diff": round(max(diffs[i] for i in indices), 3)})
    return {"present": True, "frames": count, "proxy_resolution": [width, height],
            "diff_median": round(median, 3), "diff_mad": round(mad, 3),
            "detection_threshold": round(threshold, 3),
            "onset_count": len(events), "events": events}


def pair(audio_events, video_events):
    pairs = []
    for event in audio_events:
        nearest = min(video_events, default=None,
                      key=lambda v: abs(event["onset_seconds"] - v["onset_seconds"]))
        if nearest and abs(event["onset_seconds"] - nearest["onset_seconds"]) <= PAIR_MAX_SECONDS:
            pairs.append({"audio_onset_seconds": event["onset_seconds"],
                          "video_onset_seconds": nearest["onset_seconds"],
                          "audio_minus_video_seconds":
                              round(event["onset_seconds"] - nearest["onset_seconds"], 6)})
    if not pairs:
        return {"pairs": [], "median_offset_seconds": None, "verdict": "NOT_MEASURABLE"}
    offset = statistics.median(p["audio_minus_video_seconds"] for p in pairs)
    verdict = "IN_SYNC" if SYNC_LEAD_LIMIT <= offset <= SYNC_LAG_LIMIT else "OUT_OF_SYNC"
    return {"pairs": pairs, "median_offset_seconds": round(offset, 6), "verdict": verdict,
            "sign": "positive means sound lags picture",
            "window_seconds": [SYNC_LEAD_LIMIT, SYNC_LAG_LIMIT]}


def measure(path):
    path = Path(path)
    streams = probe(path)["streams"]
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    audio_result = measure_audio(path, audio) if audio else {"present": False}
    video_result = measure_video(path) if video else {"present": False}
    sync = pair(audio_result.get("events", []), video_result.get("events", []))
    return {"version": VERSION, "media_file": path.name, "audio": audio_result,
            "video": video_result, "sync": sync,
            "scope": "DISCRETE_SIGNAL_EVENTS_ONLY_NOT_SEMANTIC_OR_PERCEPTUAL_APPROVAL",
            "model_inferences": 0, "network_calls": 0}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: av_event_meter.py MEDIA")
    print(json.dumps(measure(sys.argv[1]), indent=2))
