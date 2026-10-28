"""E152: source media timing measured from bytes, never the requested generation duration.

Historical approvals are immutable. A hash-bound media sidecar can add measurements without manufacturing a
new review; new probe seals carry this record directly. It says nothing about spoken words or visual quality.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

VERSION = "clip-media-v1"
RECORDS = Path(__file__).resolve().parents[2] / "evidence" / "shots"
SHA = re.compile(r"^[0-9a-f]{64}$")
EPISODE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def finite_positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def measure(path):
    path = Path(path)
    try:
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                          "stream=codec_type,duration", "-of", "json", str(path)],
                                         capture_output=True, text=True, check=True).stdout)
        videos = [s for s in info["streams"] if s.get("codec_type") == "video"]
        audios = [s for s in info["streams"] if s.get("codec_type") == "audio"]
        video = float(videos[0]["duration"]) if len(videos) == 1 else None
        audio = float(audios[0]["duration"]) if len(audios) == 1 else None
        if not finite_positive(video) or len(audios) > 1 or (audios and not finite_positive(audio)):
            raise ValueError("one measured video stream and at most one measured audio stream")
        return {"version": VERSION, "clip_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "video_seconds": video, "audio_seconds": audio, "instrument": "ffprobe stream durations"}
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"SHOT_MEDIA_UNMEASURED {path.name} ({type(exc).__name__}; no nominal-duration fallback)") from None


def valid(record, sha):
    return (isinstance(record, dict) and record.get("version") == VERSION and isinstance(sha, str)
            and bool(SHA.fullmatch(sha)) and record.get("clip_sha256") == sha
            and finite_positive(record.get("video_seconds"))
            and (record.get("audio_seconds") is None or finite_positive(record.get("audio_seconds"))))


def evidence(approval, episode=None):
    """Inline record first; else a content-addressed sidecar. A present bad binding is never a legacy fallback."""
    sha = approval.get("clip_sha256")
    rec = approval.get("media")
    explicit = "media" in approval
    if not explicit and isinstance(sha, str) and SHA.fullmatch(sha) and EPISODE.fullmatch(episode or ""):
        path = RECORDS / episode / "media" / f"{sha}.json"
        if path.is_file():
            explicit = True
            try:
                rec = json.loads(path.read_text())
            except (OSError, ValueError):
                rec = None
    if explicit and not valid(rec, sha):
        raise SystemExit(f"SHOT_MEDIA_UNMEASURED {sha} (measurement missing, invalid or bound to different bytes)")
    return rec


def seconds(approval, episode=None):
    rec = evidence(approval, episode)
    return rec["video_seconds"] if rec else approval.get("clip_seconds")


def speech_problem(shot_id, speech, media):
    """No clamp, tail padding or inferred words: the claimed native speech must exist in both source streams."""
    start, end = speech.get("onset"), speech.get("end")
    audio = media.get("audio_seconds")
    if (not isinstance(start, (int, float)) or isinstance(start, bool) or not math.isfinite(start) or start < 0
            or not finite_positive(end) or end <= start or not finite_positive(audio)
            or end > min(media["video_seconds"], audio) + 0.001):
        return f"NATIVE_SPEECH_OUTSIDE_MEDIA {shot_id} (speech {start}..{end}; video {media.get('video_seconds')}; audio {audio})"
    return None
