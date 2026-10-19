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
"""
import json
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import RATE_OUT, MUSIC_OFFSET, run, sha256, probe_duration  # noqa: E402
from still_render import ts, ass_text, chunks, KJV  # noqa: E402
from shorts_select import CONTEXT_START, FULL_STOP, NOT_IN_SHORTS, opening_reason, ending_reason  # noqa: E402

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
    why=opening_reason(inside[0])
    if why:return None, why
    if {s["segment"] for s in inside} & NOT_IN_SHORTS:
        return None, "CTA_OR_TRANSITION_SEGMENT"
    length = inside[-1]["end"] - inside[0]["start"]
    if not WINDOW_S[0] <= length <= WINDOW_S[1]:
        return None, f"LENGTH_{length:.1f}S"
    why=ending_reason(inside,sentences)
    if why:return None, why
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


def ass(moment, hook, refs, dur, timeline_sentences=None):
    """The Short's subtitles: captions, the reference while a verse is read, the hook only when it is the
    first line's own words; no CTA. refs maps segment id -> reference."""
    lines = []
    hook_end = 0.0
    if hook_shown(moment, hook):
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


def render_args(stills, voice, music, ass_path, moment, dur, look, out):
    """The one ffmpeg call that makes a Short: full-frame backgrounds cross-faded, one continuous zoom over
    the whole Short, the film look, the subtitles; the narration of the window and the ducked music."""
    n = len(stills)
    length = dur / n
    voice_s = moment["end"] - moment["start"]
    frames = int(round(dur * FPS))
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
    graph.append(f"[{a_voice}:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,"
                 f"afade=t=out:st={max(0.0, voice_s - 0.04):.3f}:d=0.04,apad=whole_dur={dur:.3f},asplit=2[vo][key]")
    graph.append(f"[{a_music}:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,{swell},afade=t=in:d=0.5,"
                 f"afade=t=out:st={dur - 0.8:.3f}:d=0.8[m]")
    graph.append("[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck]")
    graph.append("[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=9,"
                 "alimiter=limit=0.75:attack=5:release=50:level=false[aout]")
    return ["ffmpeg", "-v", "error", "-y", *inputs,
            "-ss", f"{moment['start']:.3f}", "-t", f"{voice_s:.3f}", "-i", str(voice),
            "-ss", f"{MUSIC_OFFSET + moment['start']:.3f}", "-t", f"{dur:.3f}", "-i", str(music),
            "-filter_complex", ";".join(graph),
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE_OUT), "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)]


def produce(work, moment, index, script, images, figure, music, out, depth_model=None, timeline_sentences=None):
    """figure and depth_model are kept for interface compatibility; R1/R8 forbid the figure, and the Short
    uses one continuous zoom instead of per-scene parallax moves."""
    import cinematic
    dur = moment["end"] - moment["start"] + TAIL_S
    tmp = out / f"tmp-{index:02d}"
    tmp.mkdir(parents=True, exist_ok=True)
    backgrounds = script["backgrounds"]
    n, _ = scene_plan(dur)
    picks = [backgrounds[(index * 5 + 3 + 2 * k) % len(backgrounds)] for k in range(n)]
    stills = []
    for k, b in enumerate(picks):
        p = tmp / f"s{k:02d}.png"
        vertical_still(images / f"{b}.png", p)
        cinematic.grade(p)
        stills.append(p)
    refs = {s["id"]: s.get("reference") for s in script["segments"]}
    hook = moment.get("hook")
    (tmp / "s.ass").write_text(ass(moment, hook, refs, dur, timeline_sentences))
    mp4 = out / f"short-{index:02d}.mp4"
    run(render_args(stills, work / "voice.wav", music, tmp / "s.ass", moment, dur, cinematic.look(VW, VH), mp4))
    shutil.rmtree(tmp)
    shown = [r for _, _, r in reference_events(moment, refs, timeline_sentences)]
    return {"file": mp4.name, "sha256": sha256(mp4), "seconds": round(probe_duration(mp4), 2),
            "source_start": moment["start"], "source_end": moment["end"], "segments": moment["segments"],
            "hook": hook, "hook_shown": hook_shown(moment, hook), "title": moment.get("title") or hook,
            "reference": shown[0] if shown else None,
            "scenes": picks, "parallax": False, "figure": False,
            "selection": {k: moment.get(k) for k in ("final_score", "measured_score", "features", "rubric")},
            "text": " ".join(s["text"] for s in moment["sentences"])}


def snap_all(chosen, sentences):
    moments, rejected = [], []
    for m in chosen:
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
    moments, rejected = snap_all(sel["chosen"], timeline["sentences"])
    if rejected:
        print(json.dumps({"rejected_r8": rejected}))
    if not moments:
        raise SystemExit("NO_SHORT_MEETS_R8")
    records = [produce(work, m, i, script, Path(images_dir), figure, music, out, depth_model, timeline["sentences"])
               for i, m in enumerate(moments)]
    (out / "shorts.json").write_text(json.dumps({"version": "shorts-produce-v2-r8", "source_pilot": script["pilot_id"],
                                                 "selection_rubric_model": sel.get("rubric_model"),
                                                 "rejected_r8": rejected, "shorts": records},
                                                indent=1, ensure_ascii=False) + "\n")
    print(json.dumps([{k: r[k] for k in ("file", "seconds", "hook")} for r in records], ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:9])
