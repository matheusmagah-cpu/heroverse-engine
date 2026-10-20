#!/usr/bin/env python3
"""Produce each chosen Short as its own edit (not a crop of the long video), to STANDARD R8.

Input: the moments chosen by shorts_select.py (analysis of the whole video) and the long video's
sentence clock (WORK/timeline.json). Per Short, 1080x1920, from the long video's own sources:
  * window: snapped inward to whole timeline sentences: it starts exactly at a sentence start (the
    first word is spoken at the cut) and ends exactly at a sentence end; a moment whose snapped
    window is outside WINDOW_S or opens on a word that leans on earlier context is dropped;
  * picture: full-frame scenery only (R1, no figure), one continuous slow zoom 1.00 -> 1.06 over the
    whole Short, a new background at most every SCENE_MIN_S seconds, cross-fades of FADE_S;
  * text inside the Shorts safe area: phrase captions of 1-5 words, white bold with a dark outline,
    no box, centred at y=CAPTION_Y, timed to the sentence clock; the scripture reference only while
    a KJV sentence is spoken; the hook line only if it is the first spoken line's own words (<= 2.5 s);
    no CTA of any kind;
  * film finish (halation, vignette, grain) under the text;
  * sound: the exact narration of the window, music ducked under the voice, loudness -14 LUFS.
usage: shorts_produce.py WORK SELECTION_JSON SCRIPT IMAGES_DIR FIGURE MUSIC OUT_DIR [DEPTH_MODEL]
FIGURE and DEPTH_MODEL are accepted for interface compatibility and are not used (R1, R8).
The source-bound editorial v2 plan has its own scoped eight-scene exception:
caption-only hook, local three-second atmosphere and sample-continuous audio.
That exception never changes the legacy no-plan constants or behavior.
"""
import json
import math
import random
import subprocess
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import RATE_OUT, MUSIC_OFFSET, run, sha256, probe_duration  # noqa: E402
from still_render import ts, ass_text, chunks, KJV  # noqa: E402
from shorts_select import CONTEXT_START, FULL_STOP, NOT_IN_SHORTS, validate_candidate  # noqa: E402

VW, VH = 1080, 1920
FPS = 30
WINDOW_S = (30.0, 55.0)   # R8: snapped window length
SNAP_EPS = 0.05           # a sentence counts as inside the moment within this tolerance
FIRST_WORD_MAX = 0.3      # first spoken word at most this long after the cut
TAIL_S = 0.5              # picture and music only, after the last word
SCENE_MIN_S = 15.0        # a new background at most every 15 s
SCENE_TARGET_S = 18.0
FADE_S = 0.5              # cross-fade between backgrounds (<= 0.6 s)
ZOOM = (1.00, 1.06)       # one continuous slow zoom over the whole Short
CAPTION_WORDS = 5
CAPTION_CHARS = 24
CAPTION_Y = 1150
HOOK_S = 2.5
REF_MERGE_GAP = 0.5       # consecutive verse sentences closer than this share one reference line
LEAN = {"the", "a", "an", "to", "of", "and", "or", "in", "on", "at", "for", "with", "your", "my", "his", "that", "is", "be"}

HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VW}
PlayResY: {VH}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,74,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,2,5,90,90,0,1
Style: Hook,DejaVu Sans,70,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,6,2,8,90,170,400,1
Style: Ref,DejaVu Serif,50,&H00A3E7FF,&H00FFFFFF,&H00000000,&H64000000,1,1,0,0,100,100,0,0,1,4,2,8,90,170,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def words_of(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace("’", "'"))


# --- window (R8: whole sentences) -------------------------------------------------------------------

def snap(moment, sentences):
    """Snap a proposed moment inward to whole timeline sentences. Returns (moment, None) or (None, reason)."""
    inside = [s for s in sentences
              if s["start"] >= moment["start"] - SNAP_EPS and s["end"] <= moment["end"] + SNAP_EPS]
    while inside and not FULL_STOP.search(inside[-1]["text"].strip()):
        inside.pop()  # never end on a comma, colon or semicolon: the window ends on a completed sentence
    if not inside:
        return None, "NO_WHOLE_SENTENCE"
    if CONTEXT_START.match(inside[0]["text"].strip()):
        return None, "CONTEXT_OPENER"
    if {s["segment"] for s in inside} & NOT_IN_SHORTS:
        return None, "CTA_OR_TRANSITION_SEGMENT"
    length = inside[-1]["end"] - inside[0]["start"]
    if not WINDOW_S[0] <= length <= WINDOW_S[1]:
        return None, f"LENGTH_{length:.1f}S"
    segs = [s["segment"] for s in inside]
    out = dict(moment, start=inside[0]["start"], end=inside[-1]["end"], sentences=inside,
               segments=sorted(set(segs), key=segs.index))
    return out, None


# --- captions, hook, reference -----------------------------------------------------------------------

def split_phrase(words):
    """Split one phrase into balanced lines of at most CAPTION_WORDS words / CAPTION_CHARS characters,
    never ending a line on a function word when avoidable."""
    if len(words) <= CAPTION_WORDS and len(" ".join(words)) <= CAPTION_CHARS:
        return [words]
    best = None
    for cut in range(1, len(words)):
        head, tail = words[:cut], words[cut:]
        if len(head) > CAPTION_WORDS or (cut > 1 and len(" ".join(head)) > CAPTION_CHARS):
            break
        cost = abs(len(" ".join(head)) - len(" ".join(tail))) + (20 if head[-1].lower().strip(",.;:!?") in LEAN else 0)
        if best is None or cost < best[0]:
            best = (cost, cut)
    cut = best[1] if best else 1
    return [words[:cut]] + split_phrase(words[cut:])


def phrases(sentence):
    """Caption lines of 1-5 words: the long video's phrase chunks, split further."""
    return [" ".join(w) for line in chunks(sentence) for w in split_phrase(line.split())]


def caption_events(moment):
    """(start, end, text) relative to the cut, timed within each sentence by characters."""
    t0, out = moment["start"], []
    for s in moment["sentences"]:
        lines = phrases(s["text"])
        total = sum(len(x) for x in lines)
        t = s["start"] - t0
        for line in lines:
            span = (s["end"] - s["start"]) * len(line) / total
            out.append((t, t + span, line))
            t += span
    return out


def verse_sentences(sentences, refs):
    """Sentences that are KJV text of a referenced Scripture segment: from the first to the last sentence
    with KJV wording (an introduction such as 'The prophet Jeremiah prayed...' is not verse); a referenced
    segment with no KJV marker word at all is the verse alone."""
    verse = []
    for seg in dict.fromkeys(s["segment"] for s in sentences):
        if not refs.get(seg):
            continue
        own = [s for s in sentences if s["segment"] == seg]
        marked = [i for i, s in enumerate(own) if KJV.search(s["text"])]
        if not marked:
            verse += own
            continue
        a, b = marked[0], marked[-1]
        # a clause the timeline split at ';' or ':' belongs to the same verse ('I laid me down and slept;')
        while a > 0 and own[a - 1]["text"].rstrip().endswith((";", ":", ",")):
            a -= 1
        while b < len(own) - 1 and own[b]["text"].rstrip().endswith((";", ":", ",")):
            b += 1
        verse += own[a:b + 1]
    return verse


def reference_events(moment, refs, timeline_sentences=None):
    """(start, end, reference) relative to the cut, only while KJV sentences are spoken.
    timeline_sentences (the whole video) decides which sentences are verse; without it, the moment's own."""
    verse = {(s["start"], s["end"]) for s in verse_sentences(timeline_sentences or moment["sentences"], refs)}
    spans = []
    for s in moment["sentences"]:
        if (s["start"], s["end"]) not in verse:
            continue
        ref = refs[s["segment"]]
        if spans and spans[-1][3] == s["segment"] and s["start"] - spans[-1][1] <= REF_MERGE_GAP:
            spans[-1][1] = s["end"]
        else:
            spans.append([s["start"], s["end"], ref, s["segment"]])
    t0 = moment["start"]
    return [(a - t0, b - t0, ref) for a, b, ref, _ in spans]


def hook_shown(moment, hook):
    """The hook may be shown only when it is the first spoken line's own words."""
    if not hook:
        return False
    h, first = words_of(hook), words_of(moment["sentences"][0]["text"])
    return bool(h) and first[:len(h)] == h


def ass(moment, hook, refs, dur, timeline_sentences=None, *, hook_mode="overlay"):
    """The Short's subtitles: captions, the reference while a verse is read, the hook only when it is the
    first line's own words; no CTA. caption_only avoids duplicating the first caption.
    refs maps segment id -> reference."""
    if hook_mode not in ("overlay", "caption_only"):
        raise ValueError("INVALID_HOOK_MODE")
    lines = []
    hook_end = 0.0
    if hook_mode == "overlay" and hook_shown(moment, hook):
        first = moment["sentences"][0]
        hook_end = min(HOOK_S, first["end"] - moment["start"], dur)
        lines.append(f"Dialogue: 5,{ts(0)},{ts(hook_end)},Hook,,0,0,0,,{{\\fad(0,200)}}{ass_text(hook)}")
    for a, b, ref in reference_events(moment, refs, timeline_sentences):
        a = max(a, hook_end)  # the reference slot sits under the hook: never both at once
        if b > a:
            lines.append(f"Dialogue: 3,{ts(a)},{ts(b)},Ref,,0,0,0,,{{\\fad(200,200)}}{ass_text(ref)}")
    for a, b, text in caption_events(moment):
        lines.append(f"Dialogue: 4,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\an5\\pos({VW // 2},{CAPTION_Y})\\fad(60,40)}}"
                     f"{ass_text(text)}")
    return HEAD + "\n".join(lines) + "\n"


# --- picture and sound -------------------------------------------------------------------------------

def scene_plan(dur):
    """Number of backgrounds and the length of each: every scene at least SCENE_MIN_S."""
    n = max(1, min(round(dur / SCENE_TARGET_S), int(dur // SCENE_MIN_S)))
    return n, dur / n


def vertical_still(src, out):
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf",
         f"scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},eq=brightness=-0.05:saturation=1.05",
         "-frames:v", "1", str(out)])


def motion_progress(t, boundaries):
    """C1 monotonic camera progress, on the scene's own source clock."""
    if len(boundaries) < 2 or any(not math.isfinite(x) for x in boundaries + [t]):
        raise ValueError("INVALID_MOTION_CLOCK")
    if any(a >= b for a, b in zip(boundaries, boundaries[1:])) or not boundaries[0] <= t <= boundaries[-1]:
        raise ValueError("INVALID_MOTION_CLOCK")
    total = boundaries[-1] - boundaries[0]
    for a, b in zip(boundaries, boundaries[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            g = u - 0.35 * math.sin(2 * math.pi * u) / (2 * math.pi)
            return (a - boundaries[0] + (b - a) * g) / total
    return 1.0


def scene_frame_plan(edit_plan):
    from shorts_edit_plan import frame_plan
    canonical = frame_plan(edit_plan)
    spans = canonical["scene_frame_spans"]
    return {"fps": canonical["fps"], "output_frames": canonical["expected_frame_count"],
            "boundary_frames": [x["nominal_end_frame"] for x in spans[:-1]],
            "fade_start_frames": [x["start_frame"] for x in spans[1:]],
            "fade_end_frames": [x["end_frame"] for x in spans[:-1]],
            "fade_frames": spans[0]["end_frame"] - spans[1]["start_frame"],
            "scene_frames": [x["end_frame"] - x["start_frame"] for x in spans],
            "nominal_scene_frames": [x["nominal_end_frame"] - x["nominal_start_frame"] for x in spans],
            "scene_spans": [[x["start_frame"], x["end_frame"]] for x in spans]}


def opening_envelope(frame_index):
    """Zero outside the approved three-second hook; smooth entry and exit."""
    if type(frame_index) is not int:
        raise ValueError("INVALID_HOOK_FRAME")
    t = frame_index / FPS
    if not 0 <= t < 3:
        return 0.0
    def smooth(u):
        u = min(1.0, max(0.0, u))
        return u * u * (3 - 2 * u)
    return smooth(t / 0.35) * smooth((3 - t) / 0.45)


def opening_particles(frame_index, width, height, seed=231005):
    """Deterministic dust paths in source coordinates, never in the caption zone."""
    if any(type(x) is not int for x in (width, height, seed)) or min(width, height) <= 0:
        raise ValueError("INVALID_HOOK_GEOMETRY")
    envelope = opening_envelope(frame_index)
    t, rng = frame_index / FPS, random.Random(seed)
    particles = []
    for _ in range(24):
        x, y = rng.uniform(50, 1030), rng.uniform(100, 900)
        radius, vx, vy = rng.uniform(1, 2.5), rng.uniform(6, 12), rng.uniform(-18, -10)
        particles.append({"x": (x + vx * t) * width / 1080,
                          "y": (y + vy * t) * height / 1920,
                          "radius": radius * width / 1080, "alpha": 0.10 * envelope})
    return particles


def opening_atmosphere(base_rgb, frame_index, seed=231005):
    """Source-bound fog, warm highlights and dust; no camera, grain or generated asset.

    RGB and diagnostic alpha are floats in [0,1]. Input uint8 is also accepted;
    the caller's source is never mutated. The helper is deterministic and local.
    """
    import cv2
    import numpy as np
    base = np.asarray(base_rgb)
    if base.ndim != 3 or base.shape[2] != 3 or min(base.shape[:2]) <= 0:
        raise ValueError("INVALID_HOOK_IMAGE")
    base = base.astype(np.float32) / (255 if base.dtype == np.uint8 else 1)
    if not np.isfinite(base).all() or np.any(base < 0) or np.any(base > 1):
        raise ValueError("INVALID_HOOK_IMAGE")
    envelope = opening_envelope(frame_index)
    h, w = base.shape[:2]
    particles = opening_particles(frame_index, w, h, seed)
    if not envelope:
        return base.copy(), np.zeros((h, w), dtype=np.float32)
    t = frame_index / FPS
    y, x = np.mgrid[:h, :w].astype(np.float32)
    fog = (np.exp(-((y / h - 0.72) / 0.22) ** 2) *
           (0.50 + 0.25 * np.sin(2 * np.pi * (x / w - 0.035 * t)) +
            0.25 * np.sin(2 * np.pi * (1.7 * x / w + 0.7 * y / h - 0.05 * t))))
    fog_alpha = 0.09 * envelope * fog
    luma = base @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    highlights = cv2.GaussianBlur(np.clip((luma - 0.65) / 0.35, 0, 1),
                                  (0, 0), sigmaX=0.025 * w)
    light_alpha = 0.06 * envelope * highlights
    dust_alpha = np.zeros((h, w), dtype=np.float32)
    subsamples = (np.arange(8, dtype=np.float32) + 0.5) / 8 - 0.5
    for p in particles:
        # A compact C1 disk has the declared physical radius. Subpixel area
        # integration avoids blinking when the dust is smaller than one pixel.
        radius = p["radius"]
        x0, x1 = max(0, math.floor(p["x"] - radius - 0.5)), min(w, math.ceil(p["x"] + radius + 0.5))
        y0, y1 = max(0, math.floor(p["y"] - radius - 0.5)), min(h, math.ceil(p["y"] + radius + 0.5))
        if x0 < x1 and y0 < y1:
            dx2 = (np.arange(x0, x1)[:, None] + subsamples - p["x"]) ** 2
            dy2 = (np.arange(y0, y1)[:, None] + subsamples - p["y"]) ** 2
            disk = np.maximum(0, 1 - (dy2[:, :, None, None] + dx2[None, None, :, :]) / radius ** 2) ** 2
            dust_alpha[y0:y1, x0:x1] += p["alpha"] * disk.mean(axis=(1, 3))
    dust_alpha = np.minimum(dust_alpha, 0.10 * envelope)
    total = fog_alpha + light_alpha + dust_alpha
    factor = np.minimum(1, 0.18 / np.maximum(total, 1e-20))
    alpha = total * factor
    light = (fog_alpha[..., None] * np.array([0.92, 0.94, 1.0], np.float32) +
             light_alpha[..., None] * np.array([1.0, 0.92, 0.75], np.float32) +
             dust_alpha[..., None] * np.array([1.0, 0.96, 0.84], np.float32)) * factor[..., None]
    composed = base * (1 - alpha[..., None]) + light
    return np.clip(composed, 0, 1).astype(np.float32), alpha.astype(np.float32)


def write_opening_video(still_path, out_path):
    """Lossless local hook input, including its transparent endpoint frame 90."""
    import cv2
    import numpy as np
    bgr = cv2.imread(str(still_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("HOOK_SOURCE_UNREADABLE")
    base = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = base.shape[:2]
    command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{w}x{h}", "-framerate", str(FPS), "-i", "pipe:0", "-an",
               "-c:v", "ffv1", "-level", "3", "-pix_fmt", "bgr0", str(out_path)]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        try:
            for frame in range(91):
                rgb, _ = opening_atmosphere(base, frame)
                process.stdin.write(np.rint(rgb * 255).astype(np.uint8).tobytes())
            process.stdin.close()
            error = process.stderr.read()
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, command, stderr=error)
        except BaseException:
            process.kill()
            process.wait()
            raise
    return Path(out_path)


def motion_boundaries(moment, start, end):
    points = [s[k] - moment["start"] for s in moment["sentences"] for k in ("start", "end")]
    return sorted({start, end, *(x for x in points if start < x < end)})


def motion_expression(boundaries, clock):
    """Code-owned expression; no JSON-supplied FFmpeg expression is accepted."""
    total = boundaries[-1] - boundaries[0]
    expression = "1"
    for a, b in reversed(list(zip(boundaries, boundaries[1:]))):
        u = f"(({clock})-{a:.12f})/{b - a:.12f}"
        g = f"(({u})-0.35*sin(2*PI*({u}))/(2*PI))"
        value = f"({a - boundaries[0]:.12f}+{b - a:.12f}*{g})/{total:.12f}"
        expression = f"if(lte({clock},{b:.12f}),{value},{expression})"
    return expression


def portrait_crop(width, height):
    if type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError("INVALID_IMAGE_DIMENSIONS")
    scale = max(VW / width, VH / height)
    sw, sh = math.ceil(width * scale), math.ceil(height * scale)
    return {"source_width": width, "source_height": height, "scaled_width": sw, "scaled_height": sh,
            "crop_width": VW, "crop_height": VH, "crop_x": (sw - VW) / 2, "crop_y": (sh - VH) / 2,
            "native_portrait_width": min(width, height * VW / VH),
            "native_portrait_height": min(height, width * VH / VW)}


def editorial_picture(stills, moment, edit_plan, *, hook_video=None):
    from shorts_edit_plan import validate_plan_schema
    validate_plan_schema(edit_plan)
    if len(stills) != len(edit_plan["scenes"]):
        raise ValueError("EDITORIAL_PLAN_IMAGE_COUNT")
    if hook_video is None:
        raise ValueError("EDITORIAL_HOOK_VIDEO_REQUIRED")
    plan = scene_frame_plan(edit_plan)
    inputs, graph = [], []
    for i, (path, frames, span) in enumerate(zip(stills, plan["scene_frames"], plan["scene_spans"])):
        if i == 0:
            inputs += ["-threads", "1", "-i", str(hook_video)]
        else:
            inputs += ["-threads", "1", "-loop", "1", "-framerate", str(FPS),
                       "-t", f"{frames / FPS:.12f}", "-i", str(path)]
        a, b = span[0] / FPS, span[1] / FPS
        boundaries = motion_boundaries(moment, a, b)
        progress = motion_expression(boundaries, f"on/{frames - 1}*{b - a:.12f}+{a:.12f}")
        if edit_plan["scenes"][i]["motion_profile"] == "phrase_push_in_v1":
            zoom, x = f"1+0.08*({progress})", "(iw-iw/zoom)/2"
        else:
            zoom, x = "1.08", f"(iw-iw/zoom)*({progress})"
        pad = f"tpad=stop_mode=clone:stop={frames - 91}," if i == 0 else ""
        graph.append(f"[{i}:v]{pad}scale={2 * VW}:{2 * VH},zoompan=z='{zoom}':x='{x}':"
                     f"y='(ih-ih/zoom)/2':d=1:s={VW}x{VH}:fps={FPS},trim=end_frame={frames},"
                     f"setpts=PTS-STARTPTS,settb=AVTB,fps={FPS},format=yuv420p[scene{i}]")
    last = "scene0"
    for i, offset in enumerate(plan["fade_start_frames"], 1):
        graph.append(f"[{last}][scene{i}]xfade=transition=fade:duration={plan['fade_frames'] / FPS:.12f}:"
                     f"offset={offset / FPS:.12f}[mix{i}]")
        last = f"mix{i}"
    graph.append(f"[{last}]trim=end_frame={plan['output_frames']},setpts=PTS-STARTPTS[picture]")
    return inputs, graph


def render_args(stills, voice, music, ass_path, moment, dur, look, out, *, edit_plan=None, hook_video=None):
    """Full-frame backgrounds and legacy zoom or validated editorial cameras/local hook;
    the film look, subtitles, narration of the window and ducked music."""
    n = len(stills)
    length = dur / n
    voice_s = moment["end"] - moment["start"]
    frames = int(round(dur * FPS))
    if edit_plan is not None:
        inputs, graph = editorial_picture(stills, moment, edit_plan, hook_video=hook_video)
        graph.append(f"[picture]{look},ass={ass_path},format=yuv420p[vout]")
    else:
        inputs = []
        for p in stills:
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{length + FADE_S:.3f}", "-i", str(p)]
        graph, last = [], "[0:v]"
        for k in range(1, n):
            graph.append(f"{last}[{k}:v]xfade=transition=fade:duration={FADE_S}:offset={k * length - FADE_S / 2:.3f}[x{k}]")
            last = f"[x{k}]"
        z0, z1 = ZOOM
        graph.append(f"{last}scale={2 * VW}:{2 * VH},"
                     f"zoompan=z='min({z1:.2f},{z0:.2f}+{z1 - z0:.2f}*on/{max(frames - 1, 1)})':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VW}x{VH}:fps={FPS},"
                     f"{look},ass={ass_path},format=yuv420p[vout]")
    a_voice, a_music = n, n + 1
    swell = f"volume='0.05+0.04*max(0,(t-{dur - 5:.2f})/5)':eval=frame"
    if edit_plan is not None:
        samples = round(dur * RATE_OUT)
        graph.append(f"[{a_voice}:a]aresample={RATE_OUT},asetpts=N/SR/TB,aformat=channel_layouts=stereo,"
                     f"apad=whole_len={samples},asplit=2[vo][key]")
        graph.append(f"[{a_music}:a]aresample={RATE_OUT},asetpts=N/SR/TB,aformat=channel_layouts=stereo,"
                     f"{swell},afade=t=in:d=0.5[m]")
        graph.append("[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600,"
                     f"afade=t=out:st={dur - 2:.3f}:d=2:curve=hsin[duck]")
        graph.append("[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=9,"
                     "alimiter=limit=0.75:attack=5:release=50:level=false,"
                     f"aresample={RATE_OUT},apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB,"
                     f"afade=t=out:st={voice_s:.3f}:d={TAIL_S}:curve=hsin[aout]")
    else:
        graph.append(f"[{a_voice}:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,"
                 f"afade=t=out:st={max(0.0, voice_s - 0.04):.3f}:d=0.04,apad=whole_dur={dur:.3f},asplit=2[vo][key]")
        graph.append(f"[{a_music}:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,{swell},afade=t=in:d=0.5,"
                 f"afade=t=out:st={dur - 0.8:.3f}:d=0.8[m]")
        graph.append("[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck]")
        graph.append("[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=9,"
                 "alimiter=limit=0.75:attack=5:release=50:level=false[aout]")
    # Thread options are input/output scoped: a flag before only the first
    # input cannot bound the other decoders or the final encoder. Keep the
    # legacy command byte-for-byte equivalent; this is the editorial path only.
    filters = ["-filter_complex_threads", "1", "-filter_threads", "1"] if edit_plan is not None else []
    audio_threads = ["-threads", "1"] if edit_plan is not None else []
    encoder_threads = ["-threads:v", "1"] if edit_plan is not None else []
    return ["ffmpeg", *filters, "-v", "error", "-y", *inputs,
            *audio_threads, "-ss", f"{moment['start']:.3f}", "-t", f"{voice_s:.3f}", "-i", str(voice),
            *audio_threads, "-ss", f"{MUSIC_OFFSET + moment['start']:.3f}", "-t", f"{dur:.3f}", "-i", str(music),
            "-filter_complex", ";".join(graph),
            "-map", "[vout]", "-map", "[aout]", *encoder_threads,
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE_OUT), "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]


def produce(work, moment, index, script, images, figure, music, out, depth_model=None, timeline_sentences=None, *, script_refs=None, edit_plan=None):
    """figure and depth_model are kept for interface compatibility; R1/R8 forbid the figure, and the Short
    uses one continuous zoom instead of per-scene parallax moves."""
    if timeline_sentences is None or script_refs is None:
        raise ValueError("FULL_SOURCE_REQUIRED")
    authoritative_refs = {s["id"]: s.get("reference") for s in script["segments"]}
    if script_refs != authoritative_refs:
        raise ValueError("SOURCE_REFS_MISMATCH")
    moment, reason = validate_candidate(timeline_sentences, authoritative_refs, moment)
    if reason:
        raise ValueError(reason)
    image_info = None
    if edit_plan is not None:
        from shorts_edit_plan import validate_plan_schema
        validate_plan_schema(edit_plan)
        if moment["start"] != edit_plan["candidate"]["start"] or moment["end"] != edit_plan["candidate"]["end"]:
            raise ValueError("EDITORIAL_CUT_MISMATCH")
        if script["pilot_id"] != edit_plan["source_pilot"]:
            raise ValueError("EDITORIAL_PILOT_MISMATCH")
        # All raw-byte and mapping checks precede every rendering/probing subprocess.
        if sha256(work.parent / "voice.flac") != edit_plan["voice"]["sha256"]:
            raise ValueError("VOICE_HASH_MISMATCH")
        if sha256(music) != edit_plan["music"]["sha256"]:
            raise ValueError("MUSIC_HASH_MISMATCH")
        for scene in edit_plan["scenes"]:
            meta = json.loads((images / (scene["image_id"] + ".json")).read_text())
            if meta.get("id") != scene["image_id"] or meta.get("release_asset") != scene["asset"] or meta.get("sha256") != scene["sha256"]:
                raise ValueError("IMAGE_MAPPING_MISMATCH")
            if not meta.get("models") or any(not value.get("license") for value in meta["models"].values()):
                raise ValueError("IMAGE_LICENSE_MISSING")
            if sha256(images / (scene["image_id"] + ".png")) != scene["sha256"]:
                raise ValueError("IMAGE_HASH_MISMATCH")
        image_info = {}
        for scene in edit_plan["scenes"]:
            data = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height", "-of", "json", str(images / (scene["image_id"] + ".png"))],
                                  check=True, capture_output=True, text=True)
            size = json.loads(data.stdout)["streams"][0]
            image_info[scene["image_id"]] = portrait_crop(size["width"], size["height"])
    import cinematic
    dur = moment["end"] - moment["start"] + TAIL_S
    tmp = out / f"tmp-{index:02d}"
    tmp.mkdir(parents=True, exist_ok=True)
    backgrounds = script["backgrounds"]
    n, _ = scene_plan(dur)
    picks = ([x["image_id"] for x in edit_plan["scenes"]] if edit_plan is not None else
             [backgrounds[(index * 5 + 3 + 2 * k) % len(backgrounds)] for k in range(n)])
    stills = []
    if edit_plan is not None:
        print("SHORTS_PHASE_PREPARE_START", flush=True)
    for k, b in enumerate(picks):
        p = tmp / f"s{k:02d}.png"
        vertical_still(images / f"{b}.png", p)
        cinematic.grade(p)
        stills.append(p)
    if edit_plan is not None:
        print("SHORTS_PHASE_PREPARE_END", flush=True)
    refs = {s["id"]: s.get("reference") for s in script["segments"]}
    hook = moment.get("hook")
    hook_mode = "caption_only" if edit_plan is not None else "overlay"
    (tmp / "s.ass").write_text(ass(moment, hook, refs, dur, timeline_sentences, hook_mode=hook_mode))
    hook_video = None
    if edit_plan is not None:
        print("SHORTS_PHASE_HOOK_START", flush=True)
        hook_video = write_opening_video(stills[0], tmp / "opening.mkv")
        print("SHORTS_PHASE_HOOK_END", flush=True)
    mp4 = out / f"short-{index:02d}.mp4"
    source_voice = work.parent / "voice.flac" if edit_plan is not None else work / "voice.wav"
    if edit_plan is not None:
        print("SHORTS_PHASE_ENCODE_START", flush=True)
    run(render_args(stills, source_voice, music, tmp / "s.ass", moment, dur, cinematic.look(VW, VH), mp4,
                    edit_plan=edit_plan, hook_video=hook_video))
    if edit_plan is not None:
        print("SHORTS_PHASE_ENCODE_END", flush=True)
    shutil.rmtree(tmp)
    shown = [r for _, _, r in reference_events(moment, refs, timeline_sentences)]
    record = {"file": mp4.name, "sha256": sha256(mp4), "seconds": round(probe_duration(mp4), 2),
            "source_start": moment["start"], "source_end": moment["end"], "segments": moment["segments"],
            "hook": hook, "hook_shown": hook_shown(moment, hook), "title": moment.get("title") or hook,
            "reference": shown[0] if shown else None,
            "scenes": picks, "parallax": False, "figure": False,
            "selection": {k: moment.get(k) for k in ("final_score", "measured_score", "features", "rubric")},
            "text": " ".join(s["text"] for s in moment["sentences"])}
    if edit_plan is not None:
        from shorts_edit_plan import frame_plan
        record.update(render_plan=frame_plan(edit_plan), source_image_info=image_info,
                      hook_mode=hook_mode, publish=False)
    return record


def snap_all(chosen, sentences, refs=None):
    moments, rejected = [], []
    for m in chosen:
        if refs is not None:
            snapped, why = validate_candidate(sentences, refs, m)
        else:
            snapped, why = snap(m, sentences)
        if snapped:
            moments.append(snapped)
        else:
            rejected.append({"start": m["start"], "end": m["end"], "reason": why})
    return moments, rejected


def main(work, selection, script_path, images_dir, figure, music, out_dir, depth_model=None):
    work, out = Path(work), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    sel = json.loads(Path(selection).read_text())
    timeline = json.loads((work / "timeline.json").read_text())  # the sentence clock is required (R8)
    edit_plan = sel.get("edit_plan")
    if sel.get("selection_mode") == "EDITORIAL_PLAN" and edit_plan is None:
        raise ValueError("EDITORIAL_PLAN_MISSING")
    if edit_plan is not None:
        from shorts_edit_plan import validate_plan, hash_file
        inputs_path = Path(script_path).parent / "shorts" / "inputs.json"
        prepared = validate_plan(edit_plan, timeline, script, json.loads(inputs_path.read_text()), raw_sha256={
            "timeline": hash_file(work / "timeline.json"), "script": hash_file(script_path), "inputs": hash_file(inputs_path)})
        if sel.get("chosen") != prepared["chosen"] or sel.get("selection_mode") != "EDITORIAL_PLAN":
            raise ValueError("EDITORIAL_SELECTION_MISMATCH")
        sel = prepared
    refs = {s["id"]: s.get("reference") for s in script["segments"]}
    moments, rejected = snap_all(sel["chosen"], timeline["sentences"], refs)
    if rejected:
        print(json.dumps({"rejected_r8": rejected}))
    if not moments:
        raise SystemExit("NO_SHORT_MEETS_R8")
    records = [produce(work, m, i, script, Path(images_dir), figure, music, out, depth_model, timeline["sentences"], script_refs=refs, edit_plan=edit_plan)
               for i, m in enumerate(moments)]
    (out / "shorts.json").write_text(json.dumps({"version": "shorts-produce-v2-r8", "source_pilot": script["pilot_id"],
                                                 "selection_rubric_model": sel.get("rubric_model"),
                                                 "rejected_r8": rejected, "shorts": records,
                                                 **({"edit_plan": edit_plan} if edit_plan is not None else {})},
                                                indent=1, ensure_ascii=False) + "\n")
    print(json.dumps([{k: r[k] for k in ("file", "seconds", "hook")} for r in records], ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:9])
