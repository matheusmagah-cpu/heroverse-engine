#!/usr/bin/env python3
"""The uploaded caption track (.srt) of a HeroVerse video: build, validate, frame and verify (E107).

The prayer longs carry their narration as an uploaded English track (publish_video.py, captions.insert), and the
acted Bible long carries an .srt track instead of burned captions (story QA v2/v3), so a broken track is a real
quality and accessibility failure. Before E107 the publisher sent the SRT, saw HTTP 200 and recorded
`captions: true`; nothing ever read whether YouTube served the track. Here:
- srt()            builds the SRT from manifest["sentences"] (byte-identical to the old builder for valid input);
- problems()       validates an SRT strictly (numbering, timing format, blank-line separators, monotonic and
                   non-overlapping times, no cue past the video, no empty cue, UTF-8 without BOM, LF only);
- multipart()      frames captions.insert's body and refuses a boundary that occurs in the SRT;
- tracks()         reads a captions.list answer (status serving/syncing/failed, failureReason, trackKind, isDraft);
- ours()           our standard English track (never the automatic ASR one);
- wait()           polls captions.list until our track is serving or failed, with a bounded number of calls.
No network here: callers pass the listing function.
usage: captions.py MANIFEST_JSON   (prints the SRT's problems; exit 1 when there is any)
"""
import json
from pathlib import Path
import re
import sys
import time

BOUNDARY = "heroverse-caption-boundary"
TRACK_NAME = "English"
TRACK_LANGUAGE = "en"
TIMING = re.compile(r"^(\d{2}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2}):([0-5]\d):([0-5]\d),(\d{3})$")
# captions.list costs 50 units a call; the bound keeps verification inside preflight's LONG_UNITS
WAIT_CALLS = 8
WAIT_SECONDS = 30


def stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def seconds(m, at):
    h, mi, s, ms = (int(x) for x in m.groups()[at:at + 4])
    return h * 3600 + mi * 60 + s + ms / 1000


def text_of(sentence):
    """One line of text: a newline inside a sentence would split the cue, a blank line would end it."""
    return " ".join(str(sentence.get("text") or "").split())


def srt(sentences):
    """The SRT of the narration: one cue per sentence, LF line endings, a blank line between cues and a final
    newline. A sentence with no text is left out (an empty cue is invalid), and the numbering stays continuous."""
    kept = [(s, text_of(s)) for s in sentences]
    kept = [(s, t) for s, t in kept if t]
    return "\n".join(f"{i}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{t}\n" for i, (s, t) in enumerate(kept, 1))


def problems(data, duration=None):
    """Every reason the SRT (str or bytes) is not a clean track; [] when it is."""
    out = []
    if isinstance(data, bytes):
        if data.startswith(b"\xef\xbb\xbf"):
            out.append("SRT_BOM")
            data = data[3:]
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as e:
            return out + [f"SRT_NOT_UTF8 at byte {e.start}"]
    if data.startswith("﻿"):
        out.append("SRT_BOM")
        data = data[1:]
    if "\r" in data:
        out.append("SRT_CR (LF line endings only)")
    if not data.strip():
        return out + ["SRT_EMPTY"]
    if not data.endswith("\n"):
        out.append("SRT_NO_FINAL_NEWLINE")
    if data.endswith("\n\n\n") or data.startswith("\n"):
        out.append("SRT_STRAY_BLANK_LINES")
    bad = sorted({hex(ord(c)) for c in data if (ord(c) < 32 and c not in "\n\r") or 0x7f <= ord(c) < 0xa0})
    if bad:
        out.append("SRT_CONTROL_CHARACTERS " + ",".join(bad))
    blocks = data.replace("\r\n", "\n").strip("\n").split("\n\n")
    prev_end = 0.0
    for n, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if any(not line.strip() for line in lines):
            out.append(f"SRT_CUE_{n}_BLANK_LINE_INSIDE")
            continue
        if len(lines) < 3:
            out.append(f"SRT_CUE_{n}_EMPTY_OR_SHORT ({len(lines)} lines)")
            continue
        if lines[0] != str(n):
            out.append(f"SRT_CUE_{n}_NUMBER {lines[0]!r}")
        m = TIMING.match(lines[1])
        if not m:
            out.append(f"SRT_CUE_{n}_TIMING_FORMAT {lines[1]!r}")
            continue
        start, end = seconds(m, 0), seconds(m, 4)
        if end <= start:
            out.append(f"SRT_CUE_{n}_NOT_POSITIVE {lines[1]}")
        if start < prev_end - 1e-9:
            out.append(f"SRT_CUE_{n}_OVERLAPS_PREVIOUS {lines[1]}")
        if duration is not None and end > round(duration, 3) + 1e-9:   # the stamp is rounded to the ms; so is the end
            out.append(f"SRT_CUE_{n}_PAST_VIDEO_END {end:.3f} > {duration:.3f}")
        if "-->" in "\n".join(lines[2:]):
            out.append(f"SRT_CUE_{n}_ARROW_IN_TEXT")
        prev_end = max(prev_end, end)
    return out


def multipart(meta, srt_text, boundary=BOUNDARY):
    """captions.insert's multipart/related body (bytes). RFC 2046: the CRLF before each delimiter belongs to the
    delimiter, so the media part is exactly the SRT (ending in its own LF); the close delimiter ends in CRLF."""
    if ("--" + boundary) in srt_text or ("--" + boundary) in json.dumps(meta):
        raise ValueError("CAPTIONS_BOUNDARY_IN_CONTENT")
    return (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
            f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n{srt_text}\r\n--{boundary}--\r\n").encode("utf-8")


def parts(body, boundary=BOUNDARY):
    """The parts of a multipart body as (headers, content) bytes, for the framing tests and the audit."""
    delimiter = b"\r\n--" + boundary.encode()
    if not body.startswith(b"--" + boundary.encode() + b"\r\n"):
        raise ValueError("MULTIPART_NO_OPENING_DELIMITER")
    chunks = (b"\r\n" + body).split(delimiter)
    if chunks[0] != b"" or not chunks[-1].startswith(b"--"):
        raise ValueError("MULTIPART_NO_CLOSE_DELIMITER")
    out = []
    for chunk in chunks[1:-1]:
        head, sep, content = chunk[2:].partition(b"\r\n\r\n")
        if not chunk.startswith(b"\r\n") or not sep:
            raise ValueError("MULTIPART_PART_MALFORMED")
        out.append((head.decode(), content))
    return out


def tracks(listing):
    """captions.list (part=snippet) -> one plain record per track; no field of the answer is trusted as present."""
    out = []
    for item in (listing or {}).get("items") or []:
        s = item.get("snippet") or {}
        out.append({"id": item.get("id"), "language": s.get("language"), "name": s.get("name"),
                    "track_kind": s.get("trackKind"), "is_draft": s.get("isDraft"),
                    "status": s.get("status"), "failure_reason": s.get("failureReason"),
                    "audio_track_type": s.get("audioTrackType"), "last_updated": s.get("lastUpdated")})
    return out


def ours(track_list, track_id=None):
    """Our uploaded English track: the one with this id, else the standard English track named TRACK_NAME, else
    any standard English track. The automatic (ASR) track is never ours: before E107 any English track, ASR
    included, counted as 'already inserted'."""
    if track_id:
        return next((t for t in track_list if t["id"] == track_id), None)
    standard = [t for t in track_list if t["track_kind"] in ("standard", "STANDARD")
                and (t["language"] or "").lower().split("-")[0] == TRACK_LANGUAGE]
    return next((t for t in standard if t["name"] == TRACK_NAME), standard[0] if standard else None)


def verdict(track_list):
    """One word for a video's captions: OK, FAILED, SYNCING, DRAFT, NO_UPLOADED_TRACK."""
    mine = ours(track_list)
    if mine is None:
        return "NO_UPLOADED_TRACK"
    if mine["status"] == "failed":
        return "FAILED"
    if mine["is_draft"]:
        return "DRAFT"
    if mine["status"] == "serving":
        return "OK"
    return "SYNCING"


def wait(list_tracks, track_id=None, calls=WAIT_CALLS, pause=WAIT_SECONDS, sleep=None):
    """Poll until our track is serving or failed; at most `calls` listings. Returns the last record seen (None when
    the track is not listed)."""
    seen = None
    for i in range(calls):
        seen = ours(list_tracks(), track_id)
        if seen and seen["status"] in ("serving", "failed"):
            return seen
        if i < calls - 1:
            (sleep or time.sleep)(pause)
    return seen


def main(manifest_path):
    man = json.loads(Path(manifest_path).read_text())
    text = srt(man.get("sentences") or [])
    found = problems(text.encode("utf-8"), man.get("output_seconds"))
    meta = {"snippet": {"videoId": "VIDEO", "language": TRACK_LANGUAGE, "name": TRACK_NAME, "isDraft": False}}
    framed = parts(multipart(meta, text))
    if framed[1][1] != text.encode("utf-8"):
        found.append("MULTIPART_MEDIA_PART_DIFFERS_FROM_SRT")
    print(json.dumps({"manifest": str(manifest_path), "cues": text.count(" --> "), "bytes": len(text.encode()),
                      "duration": man.get("output_seconds"), "problems": found}))
    return 1 if found else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
