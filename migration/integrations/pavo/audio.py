"""Local input audio for Flash (our narration), checked against the public capability spec before any request.

Only MP3/WAV files inside this repository are read. Spec (model-capability-spec, agnes-video-new-flash,
2026-10-26): up to 3 audios, audio/mpeg or audio/wav, 15 MiB each, each 2-12 s, total 2-12 s.
WAV duration comes from its header; MP3 duration from ffprobe. An MP3 without a measurable duration is refused.
The web client allows audio only in omni_to_video (references) and never audio alone.
"""
from pathlib import Path
import shutil
import struct
import subprocess

from client import PavoError
import images

MAX_AUDIOS = 3
MAX_AUDIO_BYTES = 15 * 1024 * 1024
DURATION = (2.0, 12.0)
TOTAL = (2.0, 12.0)


def _wav_seconds(data):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise PavoError("INPUT_AUDIO_INVALID")
    i, byte_rate, size = 12, None, None
    while i + 8 <= len(data):
        tag, length = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        body = i + 8
        if tag == b"fmt " and length >= 16:
            byte_rate = struct.unpack("<I", data[body + 8:body + 12])[0]
        elif tag == b"data":
            if length == 0xFFFFFFFF or body + length > len(data):
                raise PavoError("INPUT_AUDIO_INVALID")
            size = length
            break
        i = body + length + (length & 1)
    if not byte_rate or size is None:
        raise PavoError("INPUT_AUDIO_INVALID")
    return size / byte_rate


def _mp3_seconds(path):
    """ffprobe's container duration, or None when it cannot be measured (never estimated)."""
    probe = shutil.which("ffprobe")
    if not probe:
        return None
    try:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                             capture_output=True, text=True, timeout=15, check=False)
        return float(out.stdout.strip()) if out.returncode == 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def audio(path, repo=None):
    """Validated local audio: {"path", "data", "mime", "seconds", "filename"}; no network."""
    if not isinstance(path, str) or not path or len(path) > 512 or "\x00" in path:
        raise PavoError("INPUT_AUDIO_PATH_REFUSED")
    root = Path(repo or images.REPO).resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise PavoError("INPUT_AUDIO_PATH_REFUSED")
    mime = {".mp3": "audio/mpeg", ".wav": "audio/wav"}.get(target.suffix.lower())
    if not mime:
        raise PavoError("INPUT_AUDIO_TYPE_REFUSED")
    size = target.stat().st_size
    if not 0 < size <= MAX_AUDIO_BYTES:
        raise PavoError("INPUT_AUDIO_SIZE_REFUSED")
    data = target.read_bytes()
    if mime == "audio/wav":
        seconds = _wav_seconds(data)
    else:
        if not (data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)):
            raise PavoError("INPUT_AUDIO_INVALID")
        seconds = _mp3_seconds(target)
        if seconds is None or seconds != seconds or seconds <= 0:
            raise PavoError("INPUT_AUDIO_DURATION_UNMEASURABLE")
    if not DURATION[0] <= seconds <= DURATION[1]:
        raise PavoError("INPUT_AUDIO_DURATION_REFUSED")
    return {"path": str(target.relative_to(root)), "data": data, "mime": mime,
            "seconds": round(seconds, 3), "filename": target.name}


def plan(audios=None, mode="frames_to_video", image_count=0, repo=None):
    """Validated audios for a request. Audio needs references (omni_to_video), like the web client."""
    if audios is not None and not isinstance(audios, (list, tuple)):
        raise PavoError("INPUT_AUDIOS_REFUSED")
    audios = list(audios or [])
    if not audios:
        return []
    if not all(isinstance(a, str) for a in audios) or len(audios) > MAX_AUDIOS:
        raise PavoError("INPUT_AUDIOS_REFUSED")
    if mode != "omni_to_video":
        # frames_to_video offers no audio upload; text with audio alone is "audioOnlyUploadNotSupported".
        raise PavoError("AUDIO_NEEDS_REFERENCES" if image_count == 0 else "AUDIO_AND_FRAMES_EXCLUSIVE")
    items = [audio(a, repo) for a in audios]
    total = sum(item["seconds"] for item in items)
    if not TOTAL[0] <= total <= TOTAL[1]:
        raise PavoError("INPUT_AUDIO_TOTAL_DURATION_REFUSED")
    return items
