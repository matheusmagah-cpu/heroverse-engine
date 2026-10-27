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
The acted Bible long (story QA v3, `grammar.caption_track`: an uploaded .srt, the script's words on their voice
timings, never burned in):
- cues()           cuts each voiced sentence into short cues (<= srt_cue_words_max words, <= srt_cue_chars_max
                   characters), the sentence's own words unchanged (KJV text exact), timed inside its voice span;
- track_record()   the SRT and the `caption_track` record the long's build writes into its manifest;
- manifest_srt()   the one SRT a manifest uploads (publish_video, preflight and qa_pilot all call it);
- long_track()     v3's caption rows measured on that SRT (qa_pilot.py).
No network here: callers pass the listing function.
usage: captions.py MANIFEST_JSON   (prints the SRT's problems; exit 1 when there is any)
       captions.py long TIMELINE_JSON OUT_SRT   (writes the long's SRT from the compose timeline's sentences at
                                                 story QA v3's cue limits; prints its caption_track record)
"""
import hashlib
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


# ---------- the acted Bible long's track (story QA v3: an uploaded .srt, never burned captions) ----------
QA_V3 = Path(__file__).resolve().parents[1] / "production" / "qa_criteria_story_v3.json"


def cues(sentences, words_max, chars_max):
    """Short cues for the acted long: each sentence is cut into the fewest balanced runs of its own words with at
    most `words_max` words and `chars_max` characters each, timed inside that sentence's voice span in proportion to
    their characters. The words are the sentence's words, unchanged (KJV text exact): only the whitespace between
    cues differs. A single word longer than chars_max is a cue of its own (long_track names it) and the words around
    it are cut as usual (review of #469). No cue is shorter than CUE_MIN_SECONDS: a cue the voice span leaves shorter
    is merged into its shorter neighbour (the merged cue may then exceed a limit, which long_track measures)."""
    out = []
    for s in sentences:
        words = text_of(s).split()
        if not words:
            continue
        runs, group = [], []
        for w in words + [None]:
            if w is None or len(w) > chars_max:
                runs += balanced(group, words_max, chars_max)
                group = []
                if w is not None:
                    runs.append([w])
            else:
                group.append(w)
        start, span = float(s["start"]), float(s["end"]) - float(s["start"])
        runs = merge_short(runs, start, span)
        for r, (a, b) in zip(runs, spans_of(runs, start, span)):
            out.append({"start": a, "end": b, "text": " ".join(r)})
    return out


CUE_MIN_SECONDS = 0.5


def balanced(words, words_max, chars_max):
    """The fewest balanced runs of `words` (each word <= chars_max) with <= words_max words and <= chars_max chars."""
    n = len(words)
    if not n:
        return []
    k = max(1, -(-n // words_max))
    while True:
        bounds = [round(i * n / k) for i in range(k + 1)]
        runs = [words[a:b] for a, b in zip(bounds, bounds[1:])]
        if k >= n or all(len(" ".join(r)) <= chars_max for r in runs):
            return runs
        k += 1


def spans_of(runs, start, span):
    """Each run's [start, end] inside the voice span, in proportion to its characters, rounded to the ms."""
    weights = [len(" ".join(r)) + 1 for r in runs]
    total, acc, out = sum(weights), 0, []
    for w in weights:
        a = start + span * acc / total
        acc += w
        out.append((round(a, 3), round(start + span * acc / total, 3)))
    return out


def merge_short(runs, start, span):
    """Merge the shortest cue under CUE_MIN_SECONDS into its shorter neighbour until none is left (or one cue)."""
    runs = [list(r) for r in runs]
    while len(runs) > 1:
        spans = spans_of(runs, start, span)
        short = [i for i, (a, b) in enumerate(spans) if b - a < CUE_MIN_SECONDS - 1e-9]
        if not short:
            break
        i = min(short, key=lambda j: spans[j][1] - spans[j][0])
        if i == 0:
            j = 1
        elif i == len(runs) - 1:
            j = i - 1
        else:
            j = i - 1 if len(" ".join(runs[i - 1])) <= len(" ".join(runs[i + 1])) else i + 1
        a, b = min(i, j), max(i, j)
        runs[a:b + 1] = [runs[a] + runs[b]]
    return runs


def track_srt(sentences, track=None):
    """The SRT a video uploads: one cue per sentence (prayer longs, unchanged), or, when the manifest records a
    `caption_track` (the acted long), the short cues of cues() at the frozen story QA v3's limits. The record's own
    words_max / chars_max are never used to build (review of #469): manifest_problems refuses a record whose limits
    are not the frozen ones (CAPTION_TRACK_LIMITS)."""
    if isinstance(track, dict):
        words_max, chars_max = v3_limits()
        return srt(cues(sentences, words_max, chars_max))
    return srt(sentences)


def manifest_srt(manifest):
    """The one SRT this manifest uploads (publish_video, preflight, captions-audit and qa_pilot all read it)."""
    return track_srt(manifest.get("sentences") or [], manifest.get("caption_track"))


def v3_limits():
    g = json.loads(QA_V3.read_text())["grammar"]
    return g["srt_cue_words_max"], g["srt_cue_chars_max"]


def track_record(sentences, words_max=None, chars_max=None, file="captions.srt"):
    """The long's SRT and the `caption_track` record its build writes beside it and into its manifest. The limits
    default to the frozen story QA v3's (srt_cue_words_max, srt_cue_chars_max)."""
    if words_max is None or chars_max is None:
        words_max, chars_max = v3_limits()
    text = track_srt(sentences, {"words_max": words_max, "chars_max": chars_max})
    return text, {"file": file, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                  "words_max": words_max, "chars_max": chars_max, "cues": text.count(" --> "), "burned": False}


def manifest_problems(manifest, base=None):
    """Every reason the track this manifest uploads is not clean: the strict SRT problems and, for a recorded
    `caption_track`, its hash and (with `base`, the manifest's folder) the written file."""
    text = manifest_srt(manifest)
    out = problems(text.encode("utf-8"), manifest.get("output_seconds"))
    track = manifest.get("caption_track")
    if track is not None and not isinstance(track, dict):
        return out + ["CAPTION_TRACK_INVALID (caption_track is a record)"]
    if isinstance(track, dict):
        if (track.get("words_max"), track.get("chars_max")) != v3_limits():
            out.append(f"CAPTION_TRACK_LIMITS {track.get('words_max')}/{track.get('chars_max')} (story QA v3: "
                       f"{'/'.join(str(x) for x in v3_limits())})")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != track.get("sha256"):
            out.append("CAPTION_TRACK_SHA256 (the recorded track is not the one the manifest builds)")
        if base is not None:
            name = str(track.get("file") or "")
            f = Path(base) / name
            # a bare file name beside the manifest: never a path out of the pilot (sweep H1)
            if not name or Path(name).name != name or name in (".", "..") or not f.is_file():
                out.append(f"CAPTION_TRACK_FILE_MISSING {track.get('file')} (a file beside the manifest)")
            elif f.read_bytes() != text.encode("utf-8"):
                out.append(f"CAPTION_TRACK_FILE_DIFFERS {track.get('file')}")
    return out


def parse(text):
    """The cues of a valid SRT: [{"start", "end", "text"}]."""
    out = []
    for block in text.replace("\r\n", "\n").strip("\n").split("\n\n"):
        lines = block.split("\n")
        m = TIMING.match(lines[1]) if len(lines) >= 3 else None
        if m:
            out.append({"start": seconds(m, 0), "end": seconds(m, 4), "text": " ".join(lines[2:])})
    return out


def long_track(text, sentences, script_text, grammar, asr_words=None, duration=None):
    """Story QA v3's caption rows measured on the SRT the long uploads: {row: (ok, value)} for caption_track,
    srt_coverage_of_speech_min, srt_cue_seconds_median, srt_cue_chars_max and srt_cue_words_max.
    caption_track: a valid SRT whose words are the script's words in order (KJV exact) and whose cues sit, in order,
    inside the voice span of the sentence they come from. Coverage: the share of the voice timeline under a cue and,
    with `asr_words` (the words heard in the audio), the share whose onset falls under a cue (0.25 s slack); the
    lower one counts."""
    import statistics
    bad = problems(text.encode("utf-8"), duration)
    got = parse(text) if not bad else []
    spoken = [s for s in sentences if text_of(s)]
    joined = " ".join(c["text"] for c in got).split()
    script_ok = bool(got) and joined == " ".join(text_of(s) for s in spoken).split() == str(script_text).split()
    on_line, i = bool(got), 0
    for s in spoken:
        want, have = text_of(s).split(), []
        while i < len(got) and len(have) < len(want):
            c = got[i]
            if c["start"] < s["start"] - 0.002 or c["end"] > s["end"] + 0.002:
                on_line = False
            have += c["text"].split()
            i += 1
        on_line = on_line and have == want
    on_line = on_line and i == len(got)
    total = sum(s["end"] - s["start"] for s in spoken)
    covered = sum(max(0.0, min(s["end"], c["end"]) - max(s["start"], c["start"])) for s in spoken for c in got)
    cover = covered / total if total > 0 and got else 0.0
    if asr_words:
        heard = [w for w in asr_words if any(c["start"] - 0.25 <= w["start_seconds"] <= c["end"] + 0.25 for c in got)]
        cover = min(cover, len(heard) / len(asr_words))
    med = statistics.median(c["end"] - c["start"] for c in got) if got else None
    chars = max((len(c["text"]) for c in got), default=None)
    words = max((len(c["text"].split()) for c in got), default=None)
    lo, hi = grammar["srt_cue_seconds_median"]
    return {"caption_track": (not bad and script_ok and on_line,
                              {"problems": bad[:5], "script_words_exact": script_ok, "on_timeline": on_line}),
            "srt_coverage_of_speech_min": (bool(got) and cover >= grammar["srt_coverage_of_speech_min"],
                                           round(cover, 4)),
            "srt_cue_seconds_median": (med is not None and lo <= med <= hi, None if med is None else round(med, 3)),
            "srt_cue_chars_max": (chars is not None and chars <= grammar["srt_cue_chars_max"], chars),
            "srt_cue_words_max": (words is not None and words <= grammar["srt_cue_words_max"], words)}


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
    text = manifest_srt(man)
    found = manifest_problems(man, Path(manifest_path).parent)
    meta = {"snippet": {"videoId": "VIDEO", "language": TRACK_LANGUAGE, "name": TRACK_NAME, "isDraft": False}}
    framed = parts(multipart(meta, text))
    if framed[1][1] != text.encode("utf-8"):
        found.append("MULTIPART_MEDIA_PART_DIFFERS_FROM_SRT")
    print(json.dumps({"manifest": str(manifest_path), "cues": text.count(" --> "), "bytes": len(text.encode()),
                      "duration": man.get("output_seconds"), "problems": found}))
    return 1 if found else 0


def write_long(timeline_path, out_srt):
    """The acted long's SRT from its compose timeline (episode_build's compose-timeline.json `sentences`), at story
    QA v3's limits; the caption_track record goes into the long's manifest. Exit 1 when the track has a problem."""
    sentences = json.loads(Path(timeline_path).read_text()).get("sentences") or []
    text, record = track_record(sentences, file=Path(out_srt).name)
    found = problems(text.encode("utf-8"))
    if not found:
        Path(out_srt).write_bytes(text.encode("utf-8"))
    print(json.dumps({"caption_track": record, "problems": found}))
    return 1 if found else 0


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "long":
        sys.exit(write_long(sys.argv[2], sys.argv[3]))
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
