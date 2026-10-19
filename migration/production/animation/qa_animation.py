#!/usr/bin/env python3
"""QA of an animation render against the frozen animation criteria.

  qa_animation.py OUT_DIR CRITERIA

Exit 2 printing CRITERIA_SHA_MISMATCH (and writing nothing) when the sha256 of
CRITERIA is not the frozen one. Otherwise writes OUT_DIR/qa.json:
  {"criteria_sha256", "render_id",
   "rows": [{"id", "value", "limit", "status"}], "status"}
Row status is PASS, FAIL or UNKNOWN. A row whose evidence is absent is UNKNOWN,
never PASS. The overall status is PASS only if every row passes, FAIL if any
row fails, UNKNOWN otherwise. Exit 0 on PASS, 1 otherwise.

Every leaf of every criteria section becomes a row ("section.key", or
"section.key[output]" for rows checked per output: master, short1, short2...;
the Short names are the keys of `shorts.duration_seconds`). Every limit is read
from CRITERIA. A criteria key with no checker gives an UNKNOWN row. Not rows:
the criteria metadata (version, structure, frozen_*, scope, failure_policy,
not_claimed), `fluidity.rule` (the definition `unique_frame_ratio_min` applies)
and `perceptual_review_required_before_approval` (enforced by the approval
chain after QA, bound to the render_id).

OUT_DIR layout (exact file names):
  master.mp4, short1.mp4, short2.mp4   the outputs (one per Short name)
  master.srt, short1.srt, short2.srt   subtitles, each in its output's own time
  frames.json      master output frame index -> sha256 of its rendered PNG, as an
                   object {"0": "<sha>", "1": ...} or a list; indices 0..N-1
  timing.json      from timing.py (fps, frames_total, scenes[] frame ranges)
  shorts-map.json  from timing.py (per Short: spans[] with master seconds, total_s)
  timeline.json    the voice timeline (pilot_render.py voice): sentence start/end
  script.json      the narration script (segments[].text, voice.engine)
  scenes.json      the scene list (ids, start/end states, holds, cuts)
  manifest.json    render manifest:
    "render_identity": {fields named by criteria render_identity.fields},
    "render_id": sha256 of the canonical JSON of render_identity (render_identity.py),
    "outputs": {"<output>": {"render_width", "render_height", "camera"}}
               (the native render size; camera "master" for the master camera,
               any other value, e.g. "vertical", for a Short's own camera),
    "cards": {"<output>": {"cta": {"text", "start_s", "end_s"},
                           "scripture": {"text", "reference", "translation",
                                         "start_s", "end_s"}}}
               (on-screen card texts and times in that output's time; scripture
               only for outputs that speak the quote),
  and, optional evidence (absent -> the rows that need it are UNKNOWN):
    "asr": {"<output>": "transcript"}, "voice_model_sha256": "<hex>",
    "singing_presence": number, "music": {"generator", "sha256"},
    "music_under_voice_db": number, "burned_phrases": {"<short>": ["phrase", ...]},
    "rerender_check": {"frames": {"<index>": "<sha>"}} (boundary frames re-rendered),
    "rights": {"<criteria rights key>": bool}.

Definitions:
  - unique_frame_ratio = frames that differ from the previous output frame
    (the first frame counts) / frames counted, over master frames.json, excluding
    the declared holds: a scene's `hold.seconds` covers the last round(s*fps)
    frames of that scene's range in timing.json.
  - unique_render_fps = the render identity `fps` (the rate frames are rendered at).
  - media rows use ffprobe; loudness rows use `ffmpeg -af ebur128=peak=true`
    (integrated loudness I, true peak); full decode is `ffmpeg -v error -xerror`.
  - text rows compare exactly: an output's SRT cue texts joined by single spaces
    equal its narration (master: script segments; a Short: the timeline sentences
    inside its spans) joined by single spaces; card texts equal the criteria text.
  - cue offsets: cues are aligned to timeline sentences by text; offset = |cue
    start - sentence start| (first cue of the sentence) and |cue end - sentence
    end| (last cue), with Short times mapped through shorts-map spans.
  - card_only_while_spoken: the scripture card interval lies inside the spoken
    interval of the sentence containing the quote.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_identity import field_names, render_id, sha256_file  # noqa: E402

FROZEN_CRITERIA_SHA256 = "2c97ebfd04951f9016096c1c392c33370cea41a4faf2d72cfe801c18cf202b71"
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
METADATA = {"version", "structure", "frozen_at_utc", "frozen_before_first_render", "scope", "failure_policy",
            "not_claimed", "perceptual_review_required_before_approval"}
DESCRIPTIVE = {("fluidity", "rule")}
EPS = 0.0015
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4}
CHANNELS = {"mono": 1, "stereo": 2}


# ---------------------------------------------------------------- tools

def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    data = json.loads(out.stdout)
    video = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not video:
        return None
    v = video[0]
    num, _, den = v.get("r_frame_rate", "0/1").partition("/")
    return {"width": v.get("width"), "height": v.get("height"), "codec": v.get("codec_name"),
            "pix_fmt": v.get("pix_fmt"), "fps": float(num) / float(den or 1) if float(den or 1) else None,
            "duration": float(data["format"]["duration"]) if "duration" in data.get("format", {}) else None,
            "video_duration": float(v["duration"]) if "duration" in v else None,
            "audio": [{"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate", 0)),
                       "channels": a.get("channels"),
                       "duration": float(a["duration"]) if "duration" in a else None} for a in audio]}


def ebur128(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-map", "0:a:0",
                          "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    summary = out.stderr[out.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp = re.search(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    if not i or not tp:
        return None
    return {"integrated_lufs": float(i.group(1)), "true_peak_dbtp": float(tp.group(1))}


def full_decode(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                         capture_output=True, text=True)
    frames = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                             "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        count = int(frames.stdout.strip().split(",")[0])
    except ValueError:
        count = None
    return {"ok": out.returncode == 0 and not out.stderr.strip(), "frames": count}


def parse_srt(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = block.strip().split("\n")
        idx = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if idx is None:
            continue
        a, _, b = lines[idx].partition("-->")
        cues.append({"start": _srt_time(a), "end": _srt_time(b), "text": " ".join(x.strip() for x in lines[idx + 1:] if x.strip())})
    return cues


def _srt_time(s):
    h, m, rest = s.strip().split(":")
    sec, _, ms = rest.replace(".", ",").partition(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms or 0) / 1000.0


def norm_words(text):
    return re.findall(r"[a-z0-9]+(?:['’-][a-z0-9]+)*", text.lower().replace("’", "'"))


def wer(ref, hyp):
    r, h = norm_words(ref), norm_words(hyp)
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hw in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw))
        prev = cur
    return prev[-1] / max(len(r), 1)


def compare(key, value, limit):
    if value is None:
        return UNKNOWN
    if isinstance(limit, bool) or isinstance(value, bool):
        return PASS if value == limit else FAIL
    if isinstance(value, (int, float)) and isinstance(limit, (int, float)):
        if key.endswith("_max"):
            return PASS if value <= limit else FAIL
        if key.endswith("_min"):
            return PASS if value >= limit else FAIL
        return PASS if math.isclose(value, limit, abs_tol=1e-9) else FAIL
    if isinstance(limit, list) and len(limit) == 2 and isinstance(value, (int, float)):
        return PASS if limit[0] <= value <= limit[1] else FAIL
    return PASS if value == limit else FAIL


def _ok(flag):
    return None if flag is None else (PASS if flag else FAIL)


# ---------------------------------------------------------------- evidence

class Evidence:
    """Everything in OUT_DIR, loaded lazily; absent or unreadable -> None."""

    def __init__(self, out_dir, criteria, criteria_sha, probe=ffprobe, loudness=ebur128, decode=full_decode):
        self.dir, self.criteria, self.criteria_sha = Path(out_dir), criteria, criteria_sha
        self._probe, self._loud, self._decode, self._cache = probe, loudness, decode, {}
        self.shorts = list(criteria["shorts"]["duration_seconds"])
        self.outputs = ["master"] + self.shorts

    def _cached(self, key, fn):
        if key not in self._cache:
            try:
                self._cache[key] = fn()
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                self._cache[key] = None
        return self._cache[key]

    def json(self, name):
        def load():
            p = self.dir / name
            if not p.is_file():
                return None
            dup = []

            def hook(pairs):
                keys = [k for k, _ in pairs]
                if len(set(keys)) != len(keys):
                    dup.append(True)
                return dict(pairs)
            data = json.loads(p.read_text(), object_pairs_hook=hook)
            if dup and name == "frames.json":
                return {"__duplicate__": True}
            return data
        return self._cached(("json", name), load)

    def manifest(self, *path):
        node = self.json("manifest.json")
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def media(self, output):
        def get():
            p = self.dir / f"{output}.mp4"
            return self._probe(p) if p.is_file() else None
        return self._cached(("probe", output), get)

    def loud(self, output):
        def get():
            p = self.dir / f"{output}.mp4"
            return self._loud(p) if p.is_file() else None
        return self._cached(("loud", output), get)

    def decoded(self, output):
        def get():
            p = self.dir / f"{output}.mp4"
            return self._decode(p) if p.is_file() else None
        return self._cached(("decode", output), get)

    def srt(self, output):
        def get():
            p = self.dir / f"{output}.srt"
            return parse_srt(p.read_text(encoding="utf-8")) if p.is_file() else None
        return self._cached(("srt", output), get)

    def frames(self):
        def get():
            data = self.json("frames.json")
            if data is None:
                return None
            if isinstance(data, dict) and data.get("__duplicate__"):
                return {"duplicate": True, "map": {}}
            items = enumerate(data) if isinstance(data, list) else ((int(k), v) for k, v in data.items())
            return {"duplicate": False, "map": dict(items)}
        return self._cached("frames", get)

    def spans(self, short):
        m = self.json("shorts-map.json")
        return m.get(short, {}).get("spans") if isinstance(m, dict) else None

    def sentences(self, output):
        """Timeline sentences spoken in an output, with times in that output's time."""
        def get():
            tl = self.json("timeline.json")
            if tl is None:
                return None
            if output == "master":
                return [dict(s) for s in tl["sentences"]]
            spans = self.spans(output)
            if not spans:
                return None
            out, offset = [], 0.0
            for sp in spans:
                a, b = float(sp["master_start_s"]), float(sp["master_end_s"])
                for s in tl["sentences"]:
                    if s["segment"] == sp["scene"] and s["start"] >= a - EPS and s["end"] <= b + EPS:
                        out.append({"segment": s["segment"], "text": s["text"], "start": offset + s["start"] - a,
                                    "end": offset + s["end"] - a, "master_start": s["start"], "master_end": s["end"]})
                offset += b - a
            return out
        return self._cached(("sentences", output), get)

    def narration(self, output):
        if output == "master":
            script = self.json("script.json")
            return None if script is None else " ".join(" ".join(seg["text"].split()) for seg in script["segments"])
        sents = self.sentences(output)
        return None if sents is None else " ".join(" ".join(s["text"].split()) for s in sents)

    def scripture_outputs(self):
        quote = self.criteria["scripture"]["quote"]
        outs = ["master"]
        for short in self.shorts:
            sents = self.sentences(short) or []
            if any(quote in s["text"] for s in sents):
                outs.append(short)
        return outs


# ---------------------------------------------------------------- checkers
# Each returns value or (value, status); status None means compare(value, limit).

def m_decode(ev, limit, out):
    d = ev.decoded(out)
    return None if d is None else d["ok"]


def m_field(name):
    def check(ev, limit, out):
        p = ev.media(out)
        return None if p is None else p.get(name)
    return check


def m_duration(ev, limit, out):
    p = ev.media(out)
    return None if p is None else p.get("duration")


def m_native(ev, limit, out):
    o, p = ev.manifest("outputs", out), ev.media(out)
    if not isinstance(o, dict) or p is None or "render_width" not in o:
        return None
    crit = ev.criteria["master" if out == "master" else "shorts"]
    return [o["render_width"], o["render_height"]] == [p["width"], p["height"]] == [crit["width"], crit["height"]]


def m_upscaled(ev, limit, out):
    o, p = ev.manifest("outputs", out), ev.media(out)
    if not isinstance(o, dict) or p is None or "render_width" not in o:
        return None
    return o["render_width"] < p["width"] or o["render_height"] < p["height"]


def m_cropped(ev, limit, out):
    cam = ev.manifest("outputs", out, "camera")
    return None if cam is None else cam == "master"


def m_audio(ev, limit, out):
    p = ev.media(out)
    m = re.match(r"\s*(\w+) streams?,\s*(\w+)\s+([\d.]+)\s*kHz\s+(\w+)", limit)
    if p is None or not m or m.group(1).lower() not in WORDS or m.group(4).lower() not in CHANNELS:
        return None
    want = (WORDS[m.group(1).lower()], m.group(2).lower(), int(float(m.group(3)) * 1000), CHANNELS[m.group(4).lower()])
    a = p["audio"]
    got = (len(a), a[0]["codec"] if a else None, a[0]["sample_rate"] if a else None, a[0]["channels"] if a else None)
    return "%d stream(s), %s %s Hz %s ch" % got, PASS if got == want else FAIL


def m_av_delta(ev, limit, out):
    p = ev.media(out)
    if p is None or not p["audio"] or p.get("video_duration") is None or p["audio"][0]["duration"] is None:
        return None
    return round(abs(p["video_duration"] - p["audio"][0]["duration"]), 4)


def s_count(ev, limit, out):
    m = ev.json("shorts-map.json")
    if m is None:
        return None
    return sum(1 for s in ev.shorts if (ev.dir / f"{s}.mp4").is_file() and s in m)


def s_spans_recorded(ev, limit, out):
    m = ev.json("shorts-map.json")
    if m is None:
        return None
    entry = m.get(out) or {}
    spans = entry.get("spans") or []
    try:
        ok = bool(spans) and all(isinstance(s["scene"], str) and float(s["master_start_s"]) < float(s["master_end_s"])
                                 for s in spans)
        ok = ok and abs(sum(s["master_end_s"] - s["master_start_s"] for s in spans) - float(entry["total_s"])) <= 0.002
    except (KeyError, TypeError, ValueError):
        ok = False
    return ok


def s_speed(ev, limit, out):
    total = (ev.json("shorts-map.json") or {}).get(out, {}).get("total_s")
    p = ev.media(out)
    if total is None or p is None or not p.get("duration"):
        return None
    return round(float(total) / p["duration"], 4)


def _span_bounds(ev, out, field):
    spans, tl = ev.spans(out), ev.json("timeline.json")
    if not spans or tl is None:
        return None
    key = "start" if field == "master_start_s" else "end"
    return all(any(s["segment"] == sp["scene"] and abs(s[key] - sp[field]) <= EPS for s in tl["sentences"])
               for sp in spans)


def s_starts(ev, limit, out):
    return _span_bounds(ev, out, "master_start_s")


def s_ends(ev, limit, out):
    return _span_bounds(ev, out, "master_end_s")


def s_cta(ev, limit, out):
    sents = ev.sentences(out)
    if not sents:
        return None
    return sents[-1]["text"] == ev.criteria["cta"]["text"]


def f_render_fps(ev, limit, out):
    return ev.manifest("render_identity", "fps")


def _holds(ev):
    """Exempt master frame indices: the last hold.seconds of each scene declaring a hold."""
    timing, scenes = ev.json("timing.json"), ev.json("scenes.json")
    if timing is None or scenes is None:
        return None
    ranges = {s["id"]: s for s in timing["scenes"]}
    exempt = set()
    for sc in scenes["scenes"]:
        hold = sc.get("hold")
        if hold and sc["id"] in ranges:
            r = ranges[sc["id"]]
            n = int(math.floor(float(hold["seconds"]) * timing["fps"] + 0.5))
            exempt.update(range(max(r["first_frame"], r["end_frame"] - n), r["end_frame"]))
    return exempt


def f_ratio(ev, limit, out):
    fr, exempt = ev.frames(), _holds(ev)
    if fr is None or exempt is None or fr["duplicate"] or not fr["map"]:
        return None
    frames = fr["map"]
    counted = [i for i in sorted(frames) if i not in exempt]
    if not counted:
        return None
    distinct = sum(1 for i in counted if i - 1 not in frames or frames[i] != frames[i - 1])
    return round(distinct / len(counted), 4)


def f_hold(ev, limit, out):
    scenes = ev.json("scenes.json")
    if scenes is None:
        return None
    return max([float(s["hold"]["seconds"]) for s in scenes["scenes"] if s.get("hold")] or [0.0])


def c_every_scene(ev, limit, out):
    timing, scenes, fr = ev.json("timing.json"), ev.json("scenes.json"), ev.frames()
    if timing is None or scenes is None or fr is None:
        return None
    ranges = {s["id"]: s for s in timing["scenes"]}
    missing = [s["id"] for s in scenes["scenes"] if s["id"] not in ranges
               or not all(i in fr["map"] for i in range(ranges[s["id"]]["first_frame"], ranges[s["id"]]["end_frame"]))]
    return missing, PASS if not missing else FAIL


def c_contiguous(ev, limit, out):
    timing, fr = ev.json("timing.json"), ev.frames()
    if timing is None or fr is None:
        return None
    hexok = all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in fr["map"].values())
    return (not fr["duplicate"]) and hexok and set(fr["map"]) == set(range(timing["frames_total"]))


def c_joins(ev, limit, out):
    d, fr = ev.decoded("master"), ev.frames()
    if d is None or fr is None or d["frames"] is None:
        return None
    return d["ok"] and d["frames"] == len(fr["map"])


def c_rerender(ev, limit, out):
    check, fr = ev.manifest("rerender_check", "frames"), ev.frames()
    if not isinstance(check, dict) or not check or fr is None:
        return None
    return all(fr["map"].get(int(k)) == v for k, v in check.items())


def c_states(ev, limit, out):
    scenes = ev.json("scenes.json")
    if scenes is None:
        return None
    bad = [f"{a['id']}->{b['id']}" for a, b in zip(scenes["scenes"], scenes["scenes"][1:])
           if a.get("end_state") != b.get("start_state") and not (b.get("cut") or {}).get("reason")]
    return bad, PASS if not bad else FAIL


def a_loud(name):
    def check(ev, limit, out):
        lo = ev.loud(out)
        return None if lo is None else lo[name]
    return check


def a_engine(ev, limit, out):
    script = ev.json("script.json")
    return None if script is None else script.get("voice", {}).get("engine")


def a_pinned(ev, limit, out):
    h = ev.manifest("voice_model_sha256")
    return None if h is None else bool(re.fullmatch(r"[0-9a-f]{64}", str(h)))


def a_direct(ev, limit, out):
    engine = a_engine(ev, limit, out)
    return None if engine is None else any(w in engine.lower() for w in ("flite", "espeak"))


def a_wpm(ev, limit, out):
    text, tl = ev.narration("master"), ev.json("timeline.json")
    if text is None or tl is None or not tl.get("voice_seconds"):
        return None
    return round(len(norm_words(text)) / (float(tl["voice_seconds"]) / 60.0), 2)


def a_wer(ev, limit, out):
    text, asr = ev.narration("master"), ev.manifest("asr", "master")
    return None if text is None or asr is None else round(wer(text, asr), 4)


def a_manifest_number(name):
    def check(ev, limit, out):
        v = ev.manifest(name)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return check


def a_music(ev, limit, out):
    music, ident = ev.manifest("music"), ev.manifest("render_identity", "music_sha256")
    if not isinstance(music, dict) or not music.get("generator") or not music.get("sha256") or ident is None:
        return None
    return music["sha256"] == ident


def t_present(ev, limit, out):
    return all(ev.srt(o) for o in ev.outputs)


def t_text(ev, limit, out):
    cues, text = ev.srt(out), ev.narration(out)
    if cues is None or text is None:
        return None
    return " ".join(" ".join(c["text"] for c in cues).split()) == text


def _aligned(ev, out):
    cues, sents = ev.srt(out), ev.sentences(out)
    if not cues or not sents:
        return None
    pairs, i = [], 0
    for s in sents:
        target, got, first = " ".join(s["text"].split()), "", i
        while i < len(cues) and len(got) < len(target):
            got = (got + " " + cues[i]["text"]).strip()
            i += 1
        if " ".join(got.split()) != target:
            return None
        pairs.append((s, cues[first], cues[i - 1]))
    return pairs if i == len(cues) else None


def t_start(ev, limit, out):
    pairs = _aligned(ev, out)
    return None if pairs is None else round(max(abs(a["start"] - s["start"]) for s, a, _ in pairs), 3)


def t_end(ev, limit, out):
    pairs = _aligned(ev, out)
    return None if pairs is None else round(max(abs(b["end"] - s["end"]) for s, _, b in pairs), 3)


def t_source(ev, limit, out):
    return None if ev.json("timeline.json") is None else ("timeline.json", PASS)


def t_burned(ev, limit, out):
    phrases = ev.manifest("burned_phrases", out)
    if not isinstance(phrases, list) or not phrases:
        return None
    counts = [len(str(p).split()) for p in phrases]
    value = [min(counts), max(counts)]
    return value, PASS if limit[0] <= value[0] and value[1] <= limit[1] else FAIL


def sc_quote(ev, limit, out):
    text = ev.narration("master")
    return None if text is None else (limit in text, _ok(limit in text))


def sc_card(field):
    def check(ev, limit, out):
        return ev.manifest("cards", out, "scripture", field)
    return check


def sc_card_text(ev, limit, out):
    text = ev.manifest("cards", out, "scripture", "text")
    return None if text is None else text == ev.criteria["scripture"]["quote"]


def sc_spoken(ev, limit, out):
    asr = ev.manifest("asr", out)
    if asr is None:
        return None
    q, a = norm_words(ev.criteria["scripture"]["quote"]), norm_words(asr)
    return any(a[i:i + len(q)] == q for i in range(len(a) - len(q) + 1))


def sc_while(ev, limit, out):
    card, sents = ev.manifest("cards", out, "scripture"), ev.sentences(out)
    if not isinstance(card, dict) or "start_s" not in card or not sents:
        return None
    quote = ev.criteria["scripture"]["quote"]
    spoken = [s for s in sents if quote in s["text"]]
    if not spoken:
        return False
    s = spoken[0]
    return s["start"] - EPS <= float(card["start_s"]) < float(card["end_s"]) <= s["end"] + EPS


def cta_text(ev, limit, out):
    sents = ev.sentences("master")
    if not sents:
        return None
    return sents[-1]["text"], _ok(sents[-1]["text"] == limit)


def cta_spoken(ev, limit, out):
    asr = ev.manifest("asr", out)
    if asr is None:
        return None
    c = norm_words(ev.criteria["cta"]["text"])
    return norm_words(asr)[-len(c):] == c


def cta_screen(ev, limit, out):
    text = ev.manifest("cards", out, "cta", "text")
    return None if text is None else text == ev.criteria["cta"]["text"]


def cta_position(ev, limit, out):
    tl, p = ev.json("timeline.json"), ev.media("master")
    m = re.search(r"within ([\d.]+) s", limit)
    if tl is None or p is None or not m or not tl["segments"] or not tl["sentences"]:
        return None
    last_seg = tl["segments"][-1]["id"]
    in_last = [s for s in tl["sentences"] if s["segment"] == last_seg]
    is_cta = [s["text"] for s in in_last] == [ev.criteria["cta"]["text"]] and tl["sentences"][-1] is in_last[-1]
    gap = round(p["duration"] - in_last[-1]["end"], 3)
    return gap, PASS if is_cta and 0 <= gap <= float(m.group(1)) else FAIL


def r_fields(ev, limit, out):
    ident = ev.manifest("render_identity")
    if not isinstance(ident, dict):
        return None
    problems = ["missing " + n for n in field_names(ev.criteria) if n not in ident]
    if ident.get("criteria_sha256") != ev.criteria_sha:
        problems.append("criteria_sha256")
    for key, name in (("script_sha256", "script.json"), ("scenes_sha256", "scenes.json")):
        p = ev.dir / name
        if not p.is_file() or ident.get(key) != sha256_file(p):
            problems.append(key)
    srt = ident.get("srt_sha256")
    srts = srt if isinstance(srt, dict) else {"master.srt": srt}
    for name in [f"{o}.srt" for o in ev.outputs]:
        p = ev.dir / name
        if not p.is_file() or srts.get(name) != sha256_file(p):
            problems.append("srt_sha256 " + name)
    timing = ev.json("timing.json")
    if timing is None or ident.get("fps") != timing.get("fps"):
        problems.append("fps")
    return problems, PASS if not problems else FAIL


def r_rule(ev, limit, out):
    ident, rid = ev.manifest("render_identity"), ev.manifest("render_id")
    if not isinstance(ident, dict) or rid is None:
        return None
    value = render_id(ident)
    return value, _ok(value == rid)


def _right(key):
    def check(ev, limit, out):
        v = ev.manifest("rights", key)
        return v if isinstance(v, bool) else None
    return check


ALL, MASTER, SHORTS, SCRIPTURE = "all", "master", "shorts", "scripture"
CHECKS = {
    ("master", "full_decode_without_errors"): (MASTER, m_decode),
    ("master", "width"): (MASTER, m_field("width")),
    ("master", "height"): (MASTER, m_field("height")),
    ("master", "native_render"): (MASTER, m_native),
    ("master", "upscaled"): (MASTER, m_upscaled),
    ("master", "codec"): (MASTER, m_field("codec")),
    ("master", "pix_fmt"): (MASTER, m_field("pix_fmt")),
    ("master", "fps"): (MASTER, m_field("fps")),
    ("master", "duration_seconds"): (MASTER, m_duration),
    ("master", "audio"): (MASTER, m_audio),
    ("master", "av_duration_delta_seconds_max"): (MASTER, m_av_delta),
    ("shorts", "count"): (None, s_count),
    ("shorts", "width"): (SHORTS, m_field("width")),
    ("shorts", "height"): (SHORTS, m_field("height")),
    ("shorts", "native_render"): (SHORTS, m_native),
    ("shorts", "upscaled"): (SHORTS, m_upscaled),
    ("shorts", "cropped_from_master"): (SHORTS, m_cropped),
    ("shorts", "codec"): (SHORTS, m_field("codec")),
    ("shorts", "pix_fmt"): (SHORTS, m_field("pix_fmt")),
    ("shorts", "fps"): (SHORTS, m_field("fps")),
    ("shorts", "duration_seconds"): (SHORTS, m_duration),
    ("shorts", "source_spans_recorded"): (SHORTS, s_spans_recorded),
    ("shorts", "source_speed"): (SHORTS, s_speed),
    ("shorts", "starts_on_sentence_start"): (SHORTS, s_starts),
    ("shorts", "ends_on_sentence_end_or_cta"): (SHORTS, s_ends),
    ("shorts", "self_contained_cta"): (SHORTS, s_cta),
    ("fluidity", "unique_render_fps_min"): (None, f_render_fps),
    ("fluidity", "unique_frame_ratio_min"): (None, f_ratio),
    ("fluidity", "hold_seconds_max"): (None, f_hold),
    ("continuity", "every_scene_in_scenes_json_rendered"): (None, c_every_scene),
    ("continuity", "frame_set_contiguous_no_missing_no_duplicate_index"): (None, c_contiguous),
    ("continuity", "chunk_joins_decoded_end_to_end"): (None, c_joins),
    ("continuity", "chunk_boundary_frames_identical_on_rerender"): (None, c_rerender),
    ("continuity", "scene_end_state_equals_next_start_state"): (None, c_states),
    ("audio", "integrated_lufs"): (ALL, a_loud("integrated_lufs")),
    ("audio", "true_peak_dbtp_max"): (ALL, a_loud("true_peak_dbtp")),
    ("audio", "voice_engine"): (None, a_engine),
    ("audio", "voice_model_hash_pinned"): (None, a_pinned),
    ("audio", "flite_or_espeak_direct_voice"): (None, a_direct),
    ("audio", "accepted_words_per_minute"): (None, a_wpm),
    ("audio", "wer_vs_script_max"): (None, a_wer),
    ("audio", "singing_presence_max"): (None, a_manifest_number("singing_presence")),
    ("audio", "music_owned_generator_with_hash"): (None, a_music),
    ("audio", "music_under_voice_db_min"): (None, a_manifest_number("music_under_voice_db")),
    ("subtitles", "srt_present_for_master_and_each_short"): (None, t_present),
    ("subtitles", "text_equals_narration_exactly"): (ALL, t_text),
    ("subtitles", "cue_start_offset_seconds_max"): (ALL, t_start),
    ("subtitles", "cue_end_offset_seconds_max"): (ALL, t_end),
    ("subtitles", "timing_source"): (None, t_source),
    ("subtitles", "shorts_burned_phrase_words"): (SHORTS, t_burned),
    ("scripture", "quote"): (None, sc_quote),
    ("scripture", "reference"): (SCRIPTURE, sc_card("reference")),
    ("scripture", "translation"): (SCRIPTURE, sc_card("translation")),
    ("scripture", "spoken_exactly"): (SCRIPTURE, sc_spoken),
    ("scripture", "card_text_exactly"): (SCRIPTURE, sc_card_text),
    ("scripture", "card_only_while_spoken"): (SCRIPTURE, sc_while),
    ("cta", "text"): (None, cta_text),
    ("cta", "spoken_exactly_in_master_and_each_short"): (ALL, cta_spoken),
    ("cta", "on_screen_exactly_in_master_and_each_short"): (ALL, cta_screen),
    ("cta", "position"): (None, cta_position),
    ("render_identity", "fields"): (None, r_fields),
    ("render_identity", "rule"): (None, r_rule),
}


def check_row(ev, section, key, limit, out=None):
    """One row; also used by the tests with injected evidence."""
    entry = CHECKS.get((section, key))
    if section == "rights":
        entry = (None, _right(key))
    rid = f"{section}.{key}" + (f"[{out}]" if out else "")
    if isinstance(limit, dict) and out in limit:
        limit = limit[out]
    if entry is None:
        return {"id": rid, "value": "no checker", "limit": limit, "status": UNKNOWN}
    result = entry[1](ev, limit, out)
    value, status = result if isinstance(result, tuple) else (result, None)
    if value is None:
        status = UNKNOWN
    return {"id": rid, "value": value, "limit": limit, "status": status or compare(key, value, limit)}


def evaluate(ev):
    rows = []
    for section, body in ev.criteria.items():
        if section in METADATA:
            continue
        if not isinstance(body, dict):
            rows.append({"id": section, "value": "no checker", "limit": body, "status": UNKNOWN})
            continue
        for key, limit in body.items():
            if (section, key) in DESCRIPTIVE:
                continue
            scope = CHECKS.get((section, key), (None,))[0]
            outs = {None: [None], MASTER: ["master"], SHORTS: ev.shorts, ALL: ev.outputs,
                    SCRIPTURE: None}[scope]
            if outs is None:
                outs = ev.scripture_outputs()
            for out in outs:
                rows.append(check_row(ev, section, key, limit, out))
    statuses = {r["status"] for r in rows}
    overall = FAIL if FAIL in statuses else UNKNOWN if UNKNOWN in statuses else PASS
    return {"criteria_sha256": ev.criteria_sha, "render_id": ev.manifest("render_id"), "rows": rows, "status": overall}


def main(argv, **tools):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir, criteria_path = Path(argv[1]), Path(argv[2])
    raw = criteria_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != FROZEN_CRITERIA_SHA256:
        print("CRITERIA_SHA_MISMATCH %s" % sha)
        return 2
    ev = Evidence(out_dir, json.loads(raw), sha, **tools)
    report = evaluate(ev)
    (out_dir / "qa.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    bad = [r["id"] + " " + r["status"] for r in sorted(report["rows"], key=lambda r: r["status"] != FAIL)
           if r["status"] != PASS]
    print(json.dumps({"status": report["status"], "rows": len(report["rows"]), "not_pass": bad[:20]}, ensure_ascii=False))
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
