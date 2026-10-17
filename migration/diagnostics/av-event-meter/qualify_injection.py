#!/usr/bin/env python3
"""Injection qualification of av_event_meter on real media. Offline, no model.

Real references have no human-labelled event list, so ground truth is created
by construction: known tone bursts and full-frame flashes are inserted into the
real audio/video at seeded times away from the file's natural events, with a
known audio-minus-video offset. The meter then measures the injected file
blind. Reported: recall and timing error of injected events, offset error, and
spurious events (neither injected nor present in the original measurement).
Natural-event correctness is NOT measured by this method.
"""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

import numpy as np

import av_event_meter as meter

INJECTED_EVENTS = 6
INJECTED_OFFSET_SECONDS = 0.04
BURST_SECONDS, BURST_HZ = 0.05, 2500
BURST_ABOVE_LOCAL_DB = 18.0
MIN_SEPARATION_SECONDS = 0.4
FLASH_FRAMES = 2
AUDIO_TOL, FRAME_SLACK = 0.015, 1.01


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def choose_times(duration, natural, rng, fps):
    """Seeded times on frame boundaries, away from natural events and each other."""
    times, attempts = [], 0
    while len(times) < INJECTED_EVENTS and attempts < 10000:
        attempts += 1
        t = round(rng.uniform(1.0, duration - 1.0) * fps) / fps
        if all(abs(t - x) >= MIN_SEPARATION_SECONDS for x in natural + times):
            times.append(t)
    return sorted(times)


def inject(source, out, video_times, offset, rate, channels, fps, tmp):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:a:0",
                          "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"],
                         check=True, capture_output=True).stdout
    audio = np.frombuffer(raw, "<f4").reshape(-1, channels).astype(np.float64).copy()
    length, ramp = round(BURST_SECONDS * rate), round(0.002 * rate)
    envelope = np.minimum(1, np.minimum(np.arange(length) / ramp, (length - 1 - np.arange(length)) / ramp))
    burst = envelope * np.sin(2 * np.pi * BURST_HZ * np.arange(length) / rate)
    levels = []
    for t in video_times:
        start = round((t + offset) * rate)
        context = audio[max(0, start - round(.2 * rate)):start]
        local = float(np.sqrt((context ** 2).mean())) if len(context) else 0.0
        amplitude = min(0.89, max(10 ** (-30 / 20), local * 10 ** (BURST_ABOVE_LOCAL_DB / 20)) * np.sqrt(2))
        audio[start:start + length] += amplitude * burst[:, None]
        levels.append(round(20 * np.log10(amplitude / np.sqrt(2)), 2))
    np.clip(audio, -1, 1, out=audio)
    wav = tmp / "injected.f32"
    wav.write_bytes(audio.astype("<f4").tobytes())
    enable = "+".join(f"between(t,{t - 1e-4:.6f},{t + (FLASH_FRAMES - .5) / fps:.6f})"
                      for t in video_times)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source),
                    "-f", "f32le", "-ar", str(rate), "-ac", str(channels), "-i", str(wav),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", f"drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='{enable}'",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-bf", "0",
                    "-c:a", "aac", "-b:a", "256k", str(out)], check=True, capture_output=True)
    return levels


def match(observed, expected, tolerance):
    hits, used = [], set()
    for want in expected:
        best = min((i for i in range(len(observed)) if i not in used), default=None,
                   key=lambda i: abs(observed[i] - want))
        if best is not None and abs(observed[best] - want) <= tolerance:
            used.add(best)
            hits.append(observed[best] - want)
        else:
            hits.append(None)
    return hits, used


def spurious(observed, used, natural, tolerance):
    return [t for i, t in enumerate(observed)
            if i not in used and all(abs(t - n) > tolerance for n in natural)]


def qualify(path):
    path = Path(path)
    started = time.monotonic()
    original = meter.measure(path)
    elapsed = time.monotonic() - started
    info = meter.probe(path)
    audio_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
    video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in video_stream["avg_frame_rate"].split("/"))
    fps = num / den
    duration = float(info["format"]["duration"])
    natural_audio = [e["onset_seconds"] for e in original["audio"]["events"]]
    natural_video = [e["onset_seconds"] for e in original["video"]["events"]]
    digest = sha256(path)
    rng = random.Random(int(digest[:16], 16))
    natural = natural_video + [t - INJECTED_OFFSET_SECONDS for t in natural_audio]
    times = choose_times(duration, natural, rng, fps)
    with tempfile.TemporaryDirectory(prefix="av_inject_") as tmp:
        tmp = Path(tmp)
        out = tmp / "injected.mp4"
        levels = inject(path, out, times, INJECTED_OFFSET_SECONDS, int(audio_stream["sample_rate"]),
                        int(audio_stream["channels"]), fps, tmp)
        result = meter.measure(out)
    frame = 1 / fps
    audio_obs = [e["onset_seconds"] for e in result["audio"]["events"]]
    video_obs = [e["onset_seconds"] for e in result["video"]["events"]]
    audio_err, audio_used = match(audio_obs, [t + INJECTED_OFFSET_SECONDS for t in times], AUDIO_TOL)
    video_err, video_used = match(video_obs, times, frame * FRAME_SLACK)
    pairs = [p for p in result["sync"]["pairs"]
             if any(abs(p["video_onset_seconds"] - t) <= frame * FRAME_SLACK for t in times)]
    offsets = [p["audio_minus_video_seconds"] for p in pairs]
    found_audio = [e for e in audio_err if e is not None]
    found_video = [e for e in video_err if e is not None]
    return {
        "media_file": path.name, "sha256": digest, "duration_seconds": duration, "fps": round(fps, 3),
        "meter_seconds_original": round(elapsed, 2),
        "natural_audio_onsets": len(natural_audio), "natural_video_onsets": len(natural_video),
        "original_sync_verdict": original["sync"]["verdict"],
        "injected_times_video_seconds": times, "injected_offset_seconds": INJECTED_OFFSET_SECONDS,
        "injected_burst_rms_dbfs": levels,
        "audio_recall": f"{len(found_audio)}/{len(times)}",
        "audio_abs_error_max_seconds": round(max(map(abs, found_audio)), 6) if found_audio else None,
        "video_recall": f"{len(found_video)}/{len(times)}",
        "video_abs_error_max_seconds": round(max(map(abs, found_video)), 6) if found_video else None,
        "injected_pair_offsets_seconds": offsets,
        "offset_abs_error_max_seconds": round(max(abs(o - INJECTED_OFFSET_SECONDS) for o in offsets), 6) if offsets else None,
        "spurious_audio_onsets": spurious(audio_obs, audio_used, natural_audio, AUDIO_TOL),
        "spurious_video_onsets": spurious(video_obs, video_used, natural_video, frame * FRAME_SLACK),
        # Frozen before any real-media run: full recall on both modalities, offset
        # within one frame, and no spurious event anywhere in the file.
        "pass": (len(found_audio) == len(times) == len(found_video) == INJECTED_EVENTS
                 and bool(offsets) and max(abs(o - INJECTED_OFFSET_SECONDS) for o in offsets) <= frame * FRAME_SLACK
                 and not spurious(audio_obs, audio_used, natural_audio, AUDIO_TOL)
                 and not spurious(video_obs, video_used, natural_video, frame * FRAME_SLACK)),
    }


def main(output, paths):
    results = [qualify(p) for p in paths]
    record = {"version": "av-event-meter-injection-qualification-v1",
              "status": "PASS" if results and all(r["pass"] for r in results) else "FAIL",
              "meter_version": meter.VERSION,
              "meter_sha256": sha256(Path(meter.__file__)),
              "method": __doc__.strip().splitlines()[2:10],
              "results": results, "model_inferences": 0, "provider_calls": 0,
              "natural_event_accuracy_measured": False,
              "production_authorized": False, "publication_authorized": False}
    Path(output).write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"status": record["status"], "files": [
        (r["media_file"][:24], r["audio_recall"], r["video_recall"], r["offset_abs_error_max_seconds"],
         len(r["spurious_audio_onsets"]), len(r["spurious_video_onsets"]), r["meter_seconds_original"])
        for r in results]}, indent=1))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: qualify_injection.py OUT.json MEDIA [MEDIA ...]")
    sys.exit(main(sys.argv[1], sys.argv[2:]))
