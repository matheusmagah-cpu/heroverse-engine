#!/usr/bin/env python3
"""Pre-upload checks of everything YouTube would reject or silently degrade, so a
publication never fails halfway: title, description and tag limits, thumbnail
format/size/aspect, schedule times (future, ordered, Shorts after the long
video), captions buildable from the narration timeline, and the Data API units
the run will spend. Writes nothing; exit 1 with every problem listed.
usage: preflight.py PILOT_DIR THUMBNAIL [PUBLISH_AT]
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captions  # noqa: E402

# videos.insert 1600 + captions.insert 400 + thumbnail, playlist, verify, and the caption check after the insert
# (E107: captions.list at 50 units, at most 1 + captions.WAIT_CALLS times)
LONG_UNITS = 2100 + 50 * (1 + captions.WAIT_CALLS)
SHORT_UNITS = 1650
DAY_UNITS = 10000


def caption_problems(man, base=None):
    """E107: the exact SRT publish_video will upload (captions.manifest_srt: the acted long's short cues when its
    manifest records a caption_track), validated strictly against the video's length, with that track's hash and
    written file (`base`, the manifest's folder)."""
    return [f"CAPTIONS_SRT {p}" for p in captions.manifest_problems(man, base)]


def when(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def image_size(path):
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", struct.unpack(">II", data[16:24]), len(data)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", (w, h), len(data)
            i += 2 + length
    return None, (0, 0), len(data)


def tag_chars(tags):
    # YouTube counts a multi-word tag with its quotes, plus a separator per tag
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


LATE = timedelta(minutes=20)  # same margin as publish.yml: closer than this to the slot, the video goes public now


def effective_publish_at(pilot_dir, now=None):
    """The time publish.yml will use: the schedule's time while at least LATE ahead, else "" (public now). A late
    approval is still a publication the same day, never a block."""
    now = now or datetime.now(timezone.utc)
    p = Path(pilot_dir) / "schedule.json"
    at = json.loads(p.read_text()).get("publish_at") if p.exists() else None
    return at if at and when(at) > now + LATE else ""


def check(pilot_dir, thumbnail, publish_at=None, now=None):
    now = now or datetime.now(timezone.utc)
    d = Path(pilot_dir)
    pkg = json.loads((d / "out" / "package.json").read_text())
    man = json.loads((d / "out" / "manifest.json").read_text())
    problems = []
    title, desc, tags = pkg.get("title", ""), pkg.get("description", ""), pkg.get("tags", [])
    if not 1 <= len(title) <= 100:
        problems.append(f"TITLE_LENGTH {len(title)} (1-100)")
    if len(desc.encode()) > 5000:
        problems.append(f"DESCRIPTION_BYTES {len(desc.encode())} (max 5000)")
    for name, text in (("TITLE", title), ("DESCRIPTION", desc)):
        if "<" in text or ">" in text:
            problems.append(f"{name}_ANGLE_BRACKETS (YouTube rejects < and >)")
    if tag_chars(tags) > 500:
        problems.append(f"TAGS_CHARS {tag_chars(tags)} (max 500)")
    if any(len(t) > 100 or "<" in t or ">" in t or "," in t for t in tags):
        problems.append("TAG_INVALID (over 100 chars, comma or angle bracket)")
    if not str(pkg.get("category_id", "")).isdigit():
        problems.append("CATEGORY_ID")
    if pkg.get("made_for_kids") is not False:
        problems.append("MADE_FOR_KIDS_NOT_FALSE")
    kind, (w, h), size = image_size(thumbnail)
    if kind is None:
        problems.append("THUMBNAIL_NOT_JPEG_OR_PNG")
    else:
        if size > 2 * 1024 * 1024:
            problems.append(f"THUMBNAIL_BYTES {size} (max 2 MB)")
        if w < 1280 or abs(w / h - 16 / 9) > 0.01:
            problems.append(f"THUMBNAIL_SIZE {w}x{h} (1280x720 or larger, 16:9)")
    if kind is not None:   # owner, 27/10: a Bible long uploads only its approved character thumbnail
        import publish_video
        problems += publish_video.bible_thumb_problems(pkg, thumbnail, d)
    sentences = man.get("sentences") or []
    if man.get("version") == "bible-compilation-manifest-v1":
        # E251: the compilation keeps the Shorts' burned captions and uploads no track; it needs valid chapters instead
        rows = man.get("chapters") or []
        if (len(rows) < 3 or rows[0][0] != 0 or any(b[0] - a[0] < 10 for a, b in zip(rows, rows[1:]))
                or man.get("output_seconds", 0) - rows[-1][0] < 10):
            problems.append("CHAPTERS (from 0:00, at least 3, each at least 10 s)")
    elif not sentences or any(not s.get("text") or s["end"] <= s["start"] for s in sentences):
        problems.append("CAPTIONS_TIMELINE (missing or invalid sentences)")
    else:
        problems += caption_problems(man, d / "out")
    sched_path = d / "schedule.json"
    sched = json.loads(sched_path.read_text()) if sched_path.exists() else {}
    if publish_at is None:  # not given: the schedule's time; "" means publish now (a late approval)
        publish_at = sched.get("publish_at")
    t = when(publish_at) if publish_at else now
    if publish_at and t < now + timedelta(minutes=15):
        problems.append(f"PUBLISH_AT_NOT_AHEAD {publish_at} (at least 15 min in the future)")
    shorts_path = d / "shorts" / "shorts.json"
    shorts = [s for s in json.loads(shorts_path.read_text())["shorts"] if s.get("publish")] if shorts_path.exists() else []
    # slots already past are rolled forward by pending_shorts.py (tested); only the ones still ahead must be valid
    slots = [x for x in (when(s) for s in sched.get("shorts_slots", [])) if x > now]
    if shorts and (slots != sorted(slots) or any(s <= t for s in slots)):
        problems.append("SHORTS_SLOTS (must be ordered and after the long video)")
    for s in shorts:
        st = s.get("title") or s.get("hook") or ""
        if not 1 <= len(st) <= 100 or "<" in st or ">" in st:
            problems.append(f"SHORT_TITLE {s['file']}")
    units = LONG_UNITS + SHORT_UNITS * len(shorts)
    if units > DAY_UNITS:
        problems.append(f"DATA_API_UNITS {units} (over the {DAY_UNITS} day)")
    return problems, units


def main(pilot_dir, thumbnail, publish_at=None, now=None):
    # no time given (approve.yml): check the time publish.yml will actually use, so a late approval is not blocked
    if publish_at is None:
        publish_at = effective_publish_at(pilot_dir, now)
    problems, units = check(pilot_dir, thumbnail, publish_at, now)
    print(json.dumps({"preflight": "FAIL" if problems else "PASS", "problems": problems, "estimated_units": units}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
