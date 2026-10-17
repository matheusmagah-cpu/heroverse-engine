#!/usr/bin/env python3
"""Blind deterministic AV event meter. Python + numpy + local ffmpeg/ffprobe only.

Input: one media path. Output: discrete audio onsets, visual change onsets and
paired audio-minus-video offsets, each with its timing resolution. It never
reads manifests, answers or recipes; thresholds adapt to each file and are not
tuned per stimulus. Media is streamed in bounded chunks, so memory does not
grow with raw duration. No model, network, provider call or approval. An onset
is an operational signal event, not a semantic finding or perceptual approval.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

VERSION = "av-event-meter-v2"

# Audio: 1 ms RMS windows (maximum over channels, no downmix). A window is an
# onset candidate when it is at least NOVELTY_DB above the median of 10 ms block
# levels in the trailing 20-210 ms (local baseline) and at least ABS_MIN_DBFS.
# Candidates closer than MERGE_GAP form one event. The onset is then refined to
# the first sample whose magnitude reaches the peak of a sine at the threshold.
AUDIO_WINDOW_SECONDS = 0.001
AUDIO_BLOCK_WINDOWS = 10
AUDIO_BASELINE_BLOCKS = (21, 2)
AUDIO_NOVELTY_DB = 12.0
AUDIO_ABS_MIN_DBFS = -50.0
AUDIO_MERGE_GAP_SECONDS = 0.03
DB_FLOOR = -120.0
CHUNK_SECONDS = 10

# Video: mean of the top-decile absolute luma differences between consecutive
# frames on an area-averaged 64x48 gray proxy, so a localized change is not
# diluted by a static background. Threshold = max(floor, median + k * MAD).
VIDEO_PROXY = (64, 48)
VIDEO_TOP_FRACTION = 0.1
VIDEO_MIN_DIFF = 6.0
VIDEO_MAD_K = 8.0
VIDEO_MERGE_GAP_SECONDS = 0.2
VIDEO_CHUNK_FRAMES = 300

PAIR_MAX_SECONDS = 1.0
MIN_CONSENSUS = 3
# ITU-R BT.1359 detectability: sound leading > 45 ms or lagging > 125 ms.
SYNC_LEAD_LIMIT, SYNC_LAG_LIMIT = -0.045, 0.125


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout


def stream(args, chunk_bytes):
    """Yield chunks of exactly chunk_bytes (the last may be short) from ffmpeg."""
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while True:
            data = process.stdout.read(chunk_bytes)
            if not data:
                break
            yield data
    finally:
        process.stdout.close()
        if process.wait():
            raise RuntimeError("FFMPEG_DECODE_FAILED")


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                           "-of", "json", str(path)]))


def to_db(power):
    with np.errstate(divide="ignore"):
        return np.maximum(DB_FLOOR, 10 * np.log10(power))


def group(indices, max_gap):
    if not len(indices):
        return []
    return np.split(indices, np.flatnonzero(np.diff(indices) > max_gap) + 1)


def audio_chunks(path, channels, window):
    frames = window * round(CHUNK_SECONDS / AUDIO_WINDOW_SECONDS)
    args = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"]
    for data in stream(args, 4 * channels * frames):
        usable = len(data) - len(data) % (4 * channels)
        yield np.frombuffer(data[:usable], "<f4").reshape(-1, channels)


def audio_levels(path, channels, window):
    """Pass 1: per-window maximum-channel power, frame count and exact-zero flag."""
    powers, frames, nonzero = [], 0, False
    for samples in audio_chunks(path, channels, window):
        if not np.isfinite(samples).all():
            raise ValueError("AUDIO_NONFINITE_SAMPLES")
        nonzero = nonzero or bool(samples.any())
        squared = samples.astype(np.float64) ** 2
        whole = len(squared) // window * window
        if whole:
            powers.append(squared[:whole].reshape(-1, window, channels).mean(1).max(1))
        if len(squared) > whole:
            powers.append(squared[whole:].mean(0).max(keepdims=True))
        frames += len(samples)
    if not frames:
        raise ValueError("AUDIO_DECODE_EMPTY")
    return np.concatenate(powers), frames, not nonzero


def local_baseline(levels):
    """Median 10 ms block level over the trailing 20-210 ms, per 1 ms window."""
    blocks = -(-len(levels) // AUDIO_BLOCK_WINDOWS)
    padded_levels = np.full(blocks * AUDIO_BLOCK_WINDOWS, DB_FLOOR)
    padded_levels[:len(levels)] = levels
    block_db = to_db((10 ** (padded_levels / 10)).reshape(blocks, -1).mean(1))
    far, near = AUDIO_BASELINE_BLOCKS
    # Before the first sample the level is taken as the first block's level, so a
    # background present from t=0 is not an onset (events in the first 10 ms are
    # not detectable).
    history = np.concatenate([np.full(far, block_db[0]), block_db])
    # Row j covers blocks j-far .. j-near: strictly before block j.
    medians = np.median(np.lib.stride_tricks.sliding_window_view(history, far - near + 1),
                        axis=1)[:blocks]
    return medians[np.arange(len(levels)) // AUDIO_BLOCK_WINDOWS]


def refine_onsets(path, channels, window, starts, thresholds_db):
    """Pass 2: first sample in [start - 1 window, start + 1 window) whose absolute
    value reaches sqrt(2) * threshold amplitude; window start if none does."""
    targets = [((max(0, s - 1)) * window, (s + 1) * window) for s in starts]
    limits = [np.sqrt(2) * 10 ** (t / 20) for t in thresholds_db]
    refined, carry, carry_start, offset, k = [], np.zeros(0), 0, 0, 0
    for samples in audio_chunks(path, channels, window):
        peak = np.concatenate([carry, np.abs(samples).max(1)])
        end = offset + len(samples)
        while k < len(targets) and targets[k][1] <= end:
            lo, hi = targets[k]
            hits = np.flatnonzero(peak[lo - carry_start:hi - carry_start] >= limits[k])
            refined.append(lo + int(hits[0]) if len(hits) else starts[k] * window)
            k += 1
        keep = min(len(peak), 2 * window)
        carry, carry_start, offset = peak[len(peak) - keep:], end - keep, end
    while k < len(targets):
        refined.append(starts[k] * window)
        k += 1
    return refined


def measure_audio(path, info):
    rate, channels = int(info["sample_rate"]), int(info["channels"])
    window = max(1, round(rate * AUDIO_WINDOW_SECONDS))
    powers, frames, silent = audio_levels(path, channels, window)
    result = {"present": True, "sample_rate_hz": rate, "channels": channels,
              "decoded_seconds": round(frames / rate, 6), "exact_digital_silence": silent,
              "window_seconds": window / rate,
              "rule": f"level >= {AUDIO_ABS_MIN_DBFS} dBFS and >= trailing local median + {AUDIO_NOVELTY_DB} dB"}
    if silent:
        return {**result, "onset_count": 0, "events": []}
    levels = to_db(powers)
    baseline = local_baseline(levels)
    novelty = levels - baseline
    candidates = np.flatnonzero((levels >= AUDIO_ABS_MIN_DBFS) & (novelty >= AUDIO_NOVELTY_DB))
    starts = [int(g[0]) for g in group(candidates, round(AUDIO_MERGE_GAP_SECONDS / AUDIO_WINDOW_SECONDS))]
    thresholds = [max(AUDIO_ABS_MIN_DBFS, float(baseline[s]) + AUDIO_NOVELTY_DB) for s in starts]
    samples = refine_onsets(path, channels, window, starts, thresholds) if starts else []
    span = round(0.05 / AUDIO_WINDOW_SECONDS)
    events = [{"onset_seconds": round(sample / rate, 6), "resolution_seconds": round(1 / rate, 9),
               "peak_dbfs": round(float(levels[s:s + span].max()), 2),
               "novelty_db": round(float(novelty[s]), 2)}
              for s, sample in zip(starts, samples)]
    return {**result, "onset_count": len(events), "events": events}


def frame_times(path, expected):
    lines = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "packet=pts_time", "-of", "csv=p=0", str(path)]).decode().split()
    values = [x.strip(",") for x in lines]
    times = np.sort(np.array([float(x) for x in values if x not in ("", "N/A")]))
    if len(times) != expected:
        raise ValueError("VIDEO_PTS_FRAME_COUNT_MISMATCH")
    return times


def measure_video(path):
    width, height = VIDEO_PROXY
    size = width * height
    top = max(1, round(size * VIDEO_TOP_FRACTION))
    args = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-fps_mode", "passthrough",
            "-vf", f"scale={width}:{height}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    diffs, luma, previous = [np.zeros(1)], [], None
    for data in stream(args, size * VIDEO_CHUNK_FRAMES):
        if len(data) % size:
            raise ValueError("VIDEO_DECODE_INCOMPLETE")
        frames = np.frombuffer(data, np.uint8).reshape(-1, size).astype(np.int16)
        luma.append(frames.mean(1))
        joined = frames if previous is None else np.vstack([previous, frames])
        if len(joined) > 1:
            delta = np.abs(np.diff(joined, axis=0))
            diffs.append(np.partition(delta, size - top, axis=1)[:, size - top:].mean(1))
        previous = frames[-1:]
    if previous is None:
        raise ValueError("VIDEO_DECODE_EMPTY")
    diffs, luma = np.concatenate(diffs), np.concatenate(luma)
    count = len(luma)
    times = frame_times(path, count)
    body = diffs[1:]
    median = float(np.median(body)) if len(body) else 0.0
    mad = float(np.median(np.abs(body - median))) if len(body) else 0.0
    threshold = max(VIDEO_MIN_DIFF, median + VIDEO_MAD_K * mad)
    interval = float(np.median(np.diff(times))) if count > 1 else 1.0
    events = []
    for indices in group(np.flatnonzero(diffs >= threshold), max(1, round(VIDEO_MERGE_GAP_SECONDS / interval))):
        first = int(indices[0])
        events.append({"onset_seconds": round(float(times[first]), 6), "onset_frame": first,
                       "resolution_seconds": round(float(times[first] - times[first - 1]), 6),
                       "last_change_frame": int(indices[-1]),
                       "direction": "brighter" if luma[first] > luma[first - 1] else "darker",
                       "peak_top_decile_diff": round(float(diffs[indices].max()), 3)})
    return {"present": True, "frames": count, "proxy_resolution": [width, height],
            "diff_median": round(median, 3), "diff_mad": round(mad, 3),
            "detection_threshold": round(threshold, 3),
            "onset_note": "the change happened after the previous frame and at or before onset_seconds",
            "onset_count": len(events), "events": events}


def pair(audio_events, video_events):
    """Consensus offset: among all audio-minus-video differences within +/-1 s,
    choose the one that the most visual events support one-to-one (an audio
    onset within that event's frame resolution of video + offset). Nearest
    neighbour pairing is not used: in real content many audio onsets (music
    notes) lie near each picture change. With fewer than MIN_CONSENSUS pairs the
    verdict is given only if every supported visual event has exactly one audio
    onset within +/-1 s. If a clearly different offset (more than two pairing
    tolerances away) has equal support, the verdict is AMBIGUOUS as well."""
    audio = np.array(sorted(e["onset_seconds"] for e in audio_events))
    audio_resolution = max((e["resolution_seconds"] for e in audio_events), default=0.0)
    if not len(audio) or not video_events:
        return {"pairs": [], "median_offset_seconds": None, "verdict": "NOT_MEASURABLE"}

    def support(offset):
        used, pairs = set(), []
        for event in video_events:
            target = event["onset_seconds"] + offset
            tolerance = event["resolution_seconds"] + audio_resolution
            lo, hi = np.searchsorted(audio, [target - tolerance, target + tolerance], side="left")
            choices = [i for i in range(lo, min(hi + 1, len(audio)))
                       if i not in used and abs(audio[i] - target) <= tolerance]
            if choices:
                best = min(choices, key=lambda i: abs(audio[i] - target))
                used.add(best)
                pairs.append((event, float(audio[best])))
        return pairs

    candidates = sorted({round(float(a - v["onset_seconds"]), 6) for v in video_events
                         for a in audio[np.abs(audio - v["onset_seconds"]) <= PAIR_MAX_SECONDS]})
    if not candidates:
        return {"pairs": [], "median_offset_seconds": None, "verdict": "NOT_MEASURABLE"}
    scored = []
    for candidate in candidates:
        pairs = support(candidate)
        residual = sum(abs(a - v["onset_seconds"] - candidate) for v, a in pairs)
        scored.append((-len(pairs), residual, abs(candidate), candidate, pairs))
    best = min(scored, key=lambda item: item[:3])
    pairs = best[4]
    separation = 2 * (max(v["resolution_seconds"] for v in video_events) + audio_resolution)
    rival = any(item[0] == best[0] and abs(item[3] - best[3]) > separation for item in scored)
    offsets = [a - v["onset_seconds"] for v, a in pairs]
    offset = float(np.median(offsets))
    nearby = [int(np.sum(np.abs(audio - v["onset_seconds"]) <= PAIR_MAX_SECONDS)) for v, _ in pairs]
    ambiguous = rival or (len(pairs) < MIN_CONSENSUS and any(n > 1 for n in nearby))
    rows = [{"audio_onset_seconds": a, "video_onset_seconds": v["onset_seconds"],
             "audio_minus_video_seconds": round(a - v["onset_seconds"], 6),
             "resolution_seconds": round(v["resolution_seconds"] + audio_resolution, 6)}
            for v, a in pairs]
    if ambiguous:
        return {"pairs": rows, "median_offset_seconds": None, "verdict": "AMBIGUOUS",
                "consensus_pairs": len(pairs), "visual_events": len(video_events)}
    verdict = "IN_SYNC" if SYNC_LEAD_LIMIT <= offset <= SYNC_LAG_LIMIT else "OUT_OF_SYNC"
    return {"pairs": rows, "median_offset_seconds": round(offset, 6), "verdict": verdict,
            "consensus_pairs": len(pairs), "visual_events": len(video_events),
            "sign": "positive means sound lags picture",
            "window_seconds": [SYNC_LEAD_LIMIT, SYNC_LAG_LIMIT]}


def measure(path):
    path = Path(path)
    streams = probe(path)["streams"]
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    # Audio and video decode in parallel; both are ffmpeg/numpy bound.
    with ThreadPoolExecutor(max_workers=2) as pool:
        audio_job = pool.submit(measure_audio, path, audio) if audio else None
        video_job = pool.submit(measure_video, path) if video else None
        audio_result = audio_job.result() if audio_job else {"present": False}
        video_result = video_job.result() if video_job else {"present": False}
    sync = pair(audio_result.get("events", []), video_result.get("events", []))
    return {"version": VERSION, "media_file": path.name, "audio": audio_result,
            "video": video_result, "sync": sync,
            "scope": "DISCRETE_SIGNAL_EVENTS_ONLY_NOT_SEMANTIC_OR_PERCEPTUAL_APPROVAL",
            "model_inferences": 0, "network_calls": 0}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: av_event_meter.py MEDIA")
    print(json.dumps(measure(sys.argv[1]), indent=2))
