#!/usr/bin/env python3
"""Scene timing and Shorts spans from the voice timeline (stdlib only).

  timing.py TIMELINE SCENES OUT_DIR [CRITERIA]

TIMELINE is the `timeline.json` written by `pilot_render.py voice`
(`segments[].id/start/end`, `sentences[] {segment, text, start, end}`,
`voice_seconds`). SCENES is the project's `scenes.json`. CRITERIA defaults to
`migration/production/animation/qa_criteria_animation_v1.json` (frozen).

Writes OUT_DIR/timing.json:
  {"fps": 24, "frames_total": N,
   "scenes": [{"id", "start_s", "end_s", "first_frame", "end_frame"}]}
  - the timeline segment ids must equal the scene ids, in order;
  - S01 (the first scene) starts at 0 s, every other scene at its segment's start,
    and each scene ends where the next one starts (pauses belong to the preceding
    scene); the last scene ends at `voice_seconds` (the master end);
  - frame = round(seconds * fps), half up; end_frame is exclusive and equals the
    next scene's first_frame, so scenes are contiguous with no gap or overlap.

Writes OUT_DIR/shorts-map.json (only when every Short fits its frozen range):
  {"short1": {"spans": [{"scene", "master_start_s", "master_end_s"}], "speed": 1.0,
              "total_s": T}, "short2": {...}}
  - spans are the scenes listed in scenes.json `shorts.<name>.scenes`, in order;
    a span starts at the start of a sentence of that scene and ends at the end of
    a sentence of that scene (never mid-sentence); speed 1.0, so total_s is the
    sum of the span lengths;
  - rule: whole scenes first. If the total is above the frozen maximum, whole
    sentences are dropped from the start of the scene marked trimmable (the
    Short's `trimmable` field, or a note "<scene> trimmed ...") until the total
    is inside the range; its last sentence is always kept;
  - a note "<scene> first sentence opens on '<text>'" is checked: that span must
    open on exactly that sentence.
  Exit 1 printing `SHORT_DURATION <name> <seconds>` when a total stays outside
  the frozen `shorts.duration_seconds` range.
"""
import json
import math
from pathlib import Path
import re
import sys

FPS = 24
DEFAULT_CRITERIA = Path(__file__).resolve().parent / "qa_criteria_animation_v1.json"


class TimingError(Exception):
    pass


def frame(seconds, fps=FPS):
    """Frame index for a time: round(seconds * fps), half up (deterministic)."""
    return int(math.floor(seconds * fps + 0.5))


def scene_timing(timeline, scenes, fps=FPS):
    ids = [s["id"] for s in scenes["scenes"]]
    segments = timeline["segments"]
    if [s["id"] for s in segments] != ids:
        raise TimingError("SEGMENTS_NOT_SCENES %s != %s" % ([s["id"] for s in segments], ids))
    master_end = float(timeline["voice_seconds"])
    starts = [0.0] + [float(s["start"]) for s in segments[1:]]
    ends = starts[1:] + [master_end]
    out = []
    for sid, start, end in zip(ids, starts, ends):
        if end <= start:
            raise TimingError("SCENE_NOT_INCREASING %s %.3f %.3f" % (sid, start, end))
        out.append({"id": sid, "start_s": round(start, 3), "end_s": round(end, 3),
                    "first_frame": frame(start, fps), "end_frame": frame(end, fps)})
    for a, b in zip(out, out[1:]):
        if a["end_frame"] != b["first_frame"] or b["first_frame"] <= a["first_frame"]:
            raise TimingError("SCENE_FRAMES_NOT_CONTIGUOUS %s %s" % (a["id"], b["id"]))
    return {"fps": fps, "frames_total": frame(master_end, fps), "scenes": out}


def _trimmable(short):
    if short.get("trimmable"):
        return short["trimmable"]
    m = re.search(r"\b(S\d+) trimmed\b", short.get("note", ""))
    return m.group(1) if m else None


def _opens_on(short):
    m = re.search(r"\b(S\d+) first sentence opens on '([^']+)'", short.get("note", ""))
    return (m.group(1), m.group(2)) if m else None


def _total(spans):
    return round(sum(s["master_end_s"] - s["master_start_s"] for s in spans), 3)


def short_spans(name, short, timeline, limits):
    """Spans for one Short; returns (spans, total) or raises TimingError carrying the total."""
    by_scene = {}
    for s in timeline["sentences"]:
        by_scene.setdefault(s["segment"], []).append(s)
    chosen = {}
    for sid in short["scenes"]:
        if not by_scene.get(sid):
            raise TimingError("SHORT_SCENE_WITHOUT_SENTENCES %s %s" % (name, sid))
        chosen[sid] = list(by_scene[sid])
    opens = _opens_on(short)
    if opens and opens[0] in chosen and chosen[opens[0]][0]["text"] != opens[1]:
        raise TimingError("SHORT_OPENING_SENTENCE %s %s" % (name, opens[0]))

    def build():
        return [{"scene": sid, "master_start_s": round(float(chosen[sid][0]["start"]), 3),
                 "master_end_s": round(float(chosen[sid][-1]["end"]), 3)} for sid in short["scenes"]]
    low, high = limits
    spans = build()
    trim = _trimmable(short)
    while _total(spans) > high and trim in chosen and len(chosen[trim]) > 1:
        chosen[trim].pop(0)
        spans = build()
    total = _total(spans)
    if not low <= total <= high:
        err = TimingError("SHORT_DURATION %s %s" % (name, total))
        err.total = total
        raise err
    return spans, total


def shorts_map(timeline, scenes, criteria):
    ranges = criteria["shorts"]["duration_seconds"]
    out = {}
    for name, limits in ranges.items():
        short = scenes["shorts"].get(name)
        if short is None:
            raise TimingError("SHORT_MISSING %s" % name)
        spans, total = short_spans(name, short, timeline, limits)
        out[name] = {"spans": spans, "speed": 1.0, "total_s": total}
    return out


def main(argv):
    if len(argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        return 2
    timeline = json.loads(Path(argv[1]).read_text())
    scenes = json.loads(Path(argv[2]).read_text())
    out_dir = Path(argv[3])
    criteria = json.loads(Path(argv[4] if len(argv) == 5 else DEFAULT_CRITERIA).read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        timing = scene_timing(timeline, scenes)
        (out_dir / "timing.json").write_text(json.dumps(timing, indent=1) + "\n")
        shorts = shorts_map(timeline, scenes, criteria)
    except TimingError as e:
        print(str(e))
        return 1
    (out_dir / "shorts-map.json").write_text(json.dumps(shorts, indent=1) + "\n")
    print(json.dumps({"frames_total": timing["frames_total"],
                      "shorts": {k: v["total_s"] for k, v in shorts.items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
