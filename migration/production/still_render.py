#!/usr/bin/env python3
"""Production renderer (migration/STANDARD.md v1): generated stills + synchronized captions.

  still_render.py assemble WORK SCRIPT IMAGES_DIR FIGURE_RGBA_PNG MUSIC

Picture: full-frame scenery, no person or figure (R1; FIGURE_RGBA_PNG is accepted
for the job interface and not drawn), every scene in continuous camera motion (R2),
a new scene at a sentence start every SCENE_TARGET seconds or more, 18-36 s, and
no image again within REPEAT_GAP seconds (R3); a title card first. Text (libass):
phrase captions centred in the lower third, bold white with an outline and no box
(R4); the verse being read in a rounded Scripture card with its reference, only
while it is read (R5); two short mid-video calls to action and a small channel
mark, nothing else persistent (R6). Audio: identical to pilot_render (voice
forward, owned music ducked, -15 LUFS). Writes pilot.mp4 and manifest.json; no upload.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import REFERENCES, RATE_OUT, TAIL, MUSIC_OFFSET, probe_duration, run, sha256  # noqa: E402
import motion as camera  # noqa: E402

# final file: crf 18 (visually lossless); a slower preset where the CPU allows packs the same quality in fewer bytes
FINAL_PRESET = "medium" if (os.cpu_count() or 2) >= 4 else "veryfast"
MOTIONS = ("push_in", "drift", "pull_out", "pan_right", "push_in", "pan_left")

FADE = 0.6
SCENE_TARGET = 22.0  # STANDARD R3: winners change scene every 20-30 s
HOLD_MIN = 18.0
HOLD_MAX = 36.0      # a longer hold is split in equal parts, each >= HOLD_MAX / 2 = HOLD_MIN
REPEAT_GAP = 300.0   # no image again within 5 minutes
# pilot-qa-criteria-v4 (owner, 2026-10-23: "4 to 7 s, bet on dynamics"): real licensed footage alternates with the
# stills in 4-7 s shots, cut on a varied cadence (the fast-cutting breakout winners hold ~3.3-5 s per scene,
# evidence/vidiq/20261023/hook_audit.md); each clip gives up to FOOTAGE_SEGMENTS distinct shots
FOOTAGE_TARGET, FOOTAGE_HOLD_MIN, FOOTAGE_HOLD_MAX = 5.5, 4.0, 7.0
FOOTAGE_CADENCE = (4.5, 6.0, 5.0, 6.5, 5.5, 4.8, 6.2)
FOOTAGE_SNAP = 0.7       # a cut moves to a sentence start this close, so cuts land on breath
FOOTAGE_SEGMENTS = 3     # shots per 20 s clip, at FOOTAGE_SEGMENT_STEP apart
FOOTAGE_SEGMENT_STEP = 6.5
CARD = (310, 300, 1610, 700)  # Scripture card (R5), rounded, centred
CARD_RADIUS = 36
CTA = (("SUBSCRIBE", 60.0), ("LIKE", 0.45))  # R6: (text, start: seconds, or fraction of the length if < 1)
CTA_SECONDS = 8.0
CAPTION_WORDS_MAX = 7
CAPTION_CHARS_MAX = 40
CAPTION_HOLD_AFTER = 0.35


WEAK_ENDINGS = {"the", "a", "an", "to", "of", "and", "for", "with", "that", "into", "in", "on", "at", "be",
                "is", "are", "my", "your", "his", "i", "you", "who", "what", "but", "or", "not"}
MERGE_CHARS, MERGE_WORDS = 32, 6


def split_balanced(words):
    """Split one phrase into the fewest lines within the limits, balanced by
    characters, never ending a line on a function word when avoidable."""
    text_len = len(" ".join(words))
    n = max(-(-len(words) // CAPTION_WORDS_MAX), -(-text_len // CAPTION_CHARS_MAX), 1)
    if n == 1:
        return [" ".join(words)]
    lines, rest = [], list(words)
    for k in range(n, 1, -1):
        target = len(" ".join(rest)) / k
        best, best_cost = 1, None
        for cut in range(1, len(rest)):
            head = " ".join(rest[:cut])
            cost = abs(len(head) - target) + (12 if rest[cut - 1].lower().strip(",.;:") in WEAK_ENDINGS else 0)
            if len(head) <= CAPTION_CHARS_MAX and cut <= CAPTION_WORDS_MAX and (best_cost is None or cost < best_cost):
                best, best_cost = cut, cost
        lines.append(" ".join(rest[:best]))
        rest = rest[best:]
    lines.append(" ".join(rest))
    return lines


def chunks(sentence):
    """Caption lines for a sentence: punctuation phrases, short neighbours merged,
    long phrases split in balance."""
    parts = re.split(r"(?<=[,;:])\s+", sentence)
    merged = []
    for part in parts:
        if merged and len(merged[-1]) + 1 + len(part) <= MERGE_CHARS and \
                len((merged[-1] + " " + part).split()) <= MERGE_WORDS:
            merged[-1] += " " + part
        else:
            merged.append(part)
    lines = [line for part in merged for line in split_balanced(part.split())]
    # guarantee: no line over the limits (the balanced split's last remainder can overflow)
    out = []
    for line in lines:
        for part in ([line] if len(line) <= CAPTION_CHARS_MAX else chunks_hard(line)):
            words = part.split()
            while len(words) > CAPTION_WORDS_MAX:
                half = -(-len(words) // 2)
                out.append(" ".join(words[:half]))
                words = words[half:]
            out.append(" ".join(words))
    return out


def chunks_hard(line):
    words, out, cur = line.split(), [], []
    target = -(-len(line) // -(-len(line) // CAPTION_CHARS_MAX))  # even split under the limit
    for w in words:
        if cur and len(" ".join(cur + [w])) > min(target + 6, CAPTION_CHARS_MAX):
            out.append(" ".join(cur))
            cur = []
        cur.append(w)
    out.append(" ".join(cur))
    return out


def caption_events(sentences):
    """Time each caption line within its sentence in proportion to its characters."""
    events = []
    for s in sentences:
        lines = chunks(s["text"])
        total = sum(len(x) for x in lines)
        t = s["start"]
        for i, line in enumerate(lines):
            span = (s["end"] - s["start"]) * len(line) / total
            end = t + span if i < len(lines) - 1 else s["end"] + CAPTION_HOLD_AFTER
            events.append({"start": round(t, 3), "end": round(end, 3), "text": line})
            t += span
    for a, b in zip(events, events[1:]):  # never overlap the next line
        a["end"] = min(a["end"], b["start"])
    return events


def ts(seconds):
    cs = int(round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def hook_lines(text, chars=26):
    """The hook sentence in centred lines of at most ~26 characters (ASS hard breaks), clean of override braces."""
    lines, cur = [], ""
    for w in ass_text(text).split():
        if cur and len(cur) + 1 + len(w) > chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return "\\N".join(lines)


def ass_text(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(script, timeline, total):
    overlay = script["overlay"]
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,1,0,0,0,100,100,0,0,1,4,2,2,120,120,90,1
Style: Card,DejaVu Sans,20,&H50140F0A,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Verse,DejaVu Serif,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,3,1,5,0,0,0,1
Style: Title,DejaVu Serif,112,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,5,4,5,120,120,0,1
Style: Subtitle,DejaVu Sans,58,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,2,0,1,4,3,5,120,120,0,1
Style: Ref,DejaVu Serif,44,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,1,0,0,100,100,0,0,1,3,1,5,0,0,0,1
Style: Brand,DejaVu Sans,36,&H20FFFFFF,&H00FFFFFF,&H64000000,&H00000000,1,0,0,0,100,100,2,0,1,3,1,7,50,0,40,1
Style: Badge,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H001A1AD0,&H00000000,1,0,0,0,100,100,1,0,3,10,0,9,0,50,46,1
Style: Hook,DejaVu Serif,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,5,4,5,160,160,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    def add(style, a, b, text, layer=0, fade=(250, 250)):
        lines.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,,{{\\fad({fade[0]},{fade[1]})}}{ass_text(text)}")
    title_end = overlay["title_card_seconds"]
    if script.get("footage") and timeline["sentences"]:
        # v4 hook (evidence/vidiq/20261023/hook_audit.md, 4/5 winners): the spoken hook line itself, large and
        # centred from the first frame over moving footage, until it has been said; no separate title card
        first = timeline["sentences"][0]
        title_end = first["end"]
        lines.append(f"Dialogue: 2,{ts(0)},{ts(title_end)},Hook,,0,0,0,,{{\\fad(0,250)}}{hook_lines(first['text'])}")
    else:
        add("Title", 0.0, title_end, overlay["title"], 2, (200, 300))
        lines.append(f"Dialogue: 2,{ts(0)},{ts(title_end)},Subtitle,,0,0,0,,{{\\fad(200,300)\\pos(960,700)}}{ass_text(overlay['subtitle'])}")
    add("Brand", title_end, total, overlay["brand"], 1, (300, 0))
    for c in cta_events(total, script):
        add("Badge", c["start"], c["end"], c["text"], 1, (200, 200))
    x0, y0, x1, y1 = CARD
    cards = scripture_cards(script, timeline)
    for c in cards:
        lines.append(f"Dialogue: 3,{ts(c['start'])},{ts(c['end'])},Card,,0,0,0,,{{\\fad(250,250)\\pos(0,0)\\p1}}"
                     f"{rounded(x0, y0, x1, y1, CARD_RADIUS)}{{\\p0}}")
        lines.append(f"Dialogue: 4,{ts(c['start'])},{ts(c['end'])},Ref,,0,0,0,,{{\\fad(250,250)\\pos({(x0 + x1) // 2},{y1 - 50})}}"
                     f"{ass_text(c['reference'])}")
    for e in caption_events(timeline["sentences"]):
        if e["end"] > title_end:
            a = max(e["start"], title_end)
            mid = (a + e["end"]) / 2
            if any(c["start"] <= mid < c["end"] for c in cards):  # the verse is read: its words go in the card
                lines.append(f"Dialogue: 5,{ts(a)},{ts(e['end'])},Verse,,0,0,0,,{{\\pos({(x0 + x1) // 2},{(y0 + y1) // 2 - 30})}}"
                             f"{ass_text(e['text'])}")
            else:
                lines.append(f"Dialogue: 4,{ts(a)},{ts(e['end'])},Caption,,0,0,0,,{ass_text(e['text'])}")
    return head + "\n".join(lines) + "\n"


def rounded(x0, y0, x1, y1, r):
    """ASS drawing of a rectangle with rounded corners (cubic Bezier corners)."""
    k = r * 0.45
    return (f"m {x0 + r} {y0} l {x1 - r} {y0} b {x1 - k} {y0} {x1} {y0 + k} {x1} {y0 + r} "
            f"l {x1} {y1 - r} b {x1} {y1 - k} {x1 - k} {y1} {x1 - r} {y1} "
            f"l {x0 + r} {y1} b {x0 + k} {y1} {x0} {y1 - k} {x0} {y1 - r} "
            f"l {x0} {y0 + r} b {x0} {y0 + k} {x0 + k} {y0} {x0 + r} {y0}")


def cta_events(total, script=None):
    """R6: two short mid-video calls to action, the first not before 0:45; nothing else is persistent.
    v4 (footage) pilots have none: 3 watched reviews named the Subscribe/Like badges as breaking the immersion
    (pilot-004, 007, 012); the spoken amen invitation after the payoff stays, and the bell goes in the pinned comment."""
    if script and script.get("footage"):
        return []
    out = []
    for text, start in CTA:
        a = start if start >= 1 else round(total * start, 3)
        if a + CTA_SECONDS < total - 60 and (not out or a >= out[-1]["end"] + 60):  # never over the outro or each other
            out.append({"text": text, "start": a, "end": round(a + CTA_SECONDS, 3)})
    return out


def scripture_cards(script, timeline):
    """R5: one card per Scripture segment, from its first KJV sentence to the end of the last one."""
    refs = {seg["id"]: seg["reference"] for seg in script["segments"] if seg.get("reference")} or REFERENCES
    cards = []
    for seg in timeline["segments"]:
        if seg["id"] in refs:
            quoted = quoted_sentences(seg["id"], timeline["sentences"])
            if quoted:
                cards.append({"segment": seg["id"], "reference": refs[seg["id"]], "start": quoted[0]["start"],
                              "end": reference_end(seg, timeline["sentences"])})
    return cards


KJV = re.compile(r"\b(thee|thou|thy|thine|ye|unto|hath|shalt|shall|art|LORD|saith|doth|cometh)\b")


def quoted_sentences(segment_id, sentences):
    """The KJV sentences of a Scripture segment. A verse without archaic words ("In every thing give thanks...",
    "There is therefore now no condemnation...") is still the quotation: when none of the segment's sentences
    matches KJV, all of them are (pilot-012 read 1 Thessalonians 5:18 with no card, review 2026-10-20)."""
    own = [s for s in sentences if s["segment"] == segment_id]
    return [s for s in own if KJV.search(s["text"])] or own


def reference_end(seg, sentences):
    """The reference stays while the Scripture is read: until the last KJV sentence of the segment, not over
    the words that follow it in the same segment (pilot-003: 'Numbers 6:24-26' stayed over 'In Jesus' name, amen')."""
    quoted = [s["end"] for s in quoted_sentences(seg["id"], sentences)]
    return max(quoted) if quoted else seg["end"]


def scene_target(backgrounds):
    """R3: scenes of at least SCENE_TARGET s, longer when there are too few images to keep REPEAT_GAP."""
    target = max(SCENE_TARGET, REPEAT_GAP / len(backgrounds) + 1.0)
    if target > HOLD_MAX:
        raise SystemExit(f"TOO_FEW_BACKGROUNDS: {len(backgrounds)} images cannot keep {REPEAT_GAP:.0f} s between repeats")
    return target


def holds(script, timeline, total):
    """Title card, then a new scene at the first sentence start at least scene_target() seconds after the
    previous change (and at least HOLD_MIN before the end), cycling through the plan's backgrounds in order.
    With script["footage"] (v4) scenes are 6-14 s and alternate real footage and stills, footage first.
    No person or figure is drawn (STANDARD R1)."""
    overlay, backgrounds = script["overlay"], script["backgrounds"]
    footage = script.get("footage") or []
    if footage:
        return footage_holds(script, timeline, total)
    if footage:
        target, hold_min, hold_max = FOOTAGE_TARGET, FOOTAGE_HOLD_MIN, FOOTAGE_HOLD_MAX
    else:
        target, hold_min, hold_max = scene_target(backgrounds), HOLD_MIN, HOLD_MAX
    plan = [{"image": overlay["title_image"], "start": 0.0, "figure": False}]
    last = overlay["title_card_seconds"]
    plan.append({"start": last, "figure": False})
    for s in timeline["sentences"]:
        if s["start"] - last >= target and total - s["start"] >= hold_min:
            plan.append({"start": s["start"], "figure": False})
            last = s["start"]
    for a, b in zip(plan, plan[1:]):
        a["end"] = b["start"]
    plan[-1]["end"] = total
    # no background held longer than hold_max: split long holds evenly
    out = [plan[0]]
    for h in plan[1:]:
        parts = max(1, -(-(h["end"] - h["start"]) // hold_max))
        step = (h["end"] - h["start"]) / parts
        for p in range(int(parts)):
            out.append({"image": None, "start": round(h["start"] + p * step, 3),
                        "end": round(h["start"] + (p + 1) * step, 3), "figure": False})
    # images assigned once, in plan order over the final holds: choosing them before the split let a split
    # piece and the next hold get the same background (pilot-004, QA FAIL 2026-10-18)
    for j, h in enumerate(out[1:]):
        if footage and j % 2 == 0:
            h["image"], h["kind"] = footage[(j // 2) % len(footage)], "footage"
        elif footage:
            h["image"], h["kind"] = backgrounds[(j // 2) % len(backgrounds)], "still"
        else:
            h["image"] = backgrounds[j % len(backgrounds)]
    # scene_target() only guarantees REPEAT_GAP for unsplit holds; split pieces can be HOLD_MAX / 2 = 18 s, so
    # 11 backgrounds came back after ~260 s and QA failed after a 2 h render (pilot-009, pilot-011; E46).
    # Refuse the plan here, before any encode.
    last = {}
    for h in out[1:]:
        if h["image"] in last and h["start"] - last[h["image"]] < REPEAT_GAP - 1e-6:
            raise SystemExit(f"REPEAT_GAP_VIOLATION: {h['image']} back after {h['start'] - last[h['image']]:.1f} s "
                             f"< {REPEAT_GAP:.0f} s with {len(backgrounds)} backgrounds and {len(footage)} clips "
                             "(need more images or footage)")
        last[h["image"]] = h["end"]
    return out


def frame_size():
    """Output frame: 1920x1080, or HERO_FRAME (2560x1440 for pilot-qa-criteria-v4, owner 2026-10-23: >= 1440p)."""
    return tuple(int(v) for v in os.environ.get("HERO_FRAME", "1920x1080").split("x"))


def footage_cuts(timeline, total):
    """v4 cut times: a varied 4-7 s cadence from 0, each cut moved to a nearby sentence start, the last shot kept
    >= FOOTAGE_HOLD_MIN. The first cut waits for the hook sentence to end when that stays within 7 s."""
    starts = [s["start"] for s in timeline["sentences"]]
    first_end = timeline["sentences"][0]["end"] if timeline["sentences"] else 0.0
    cuts, t, k = [0.0], 0.0, 0
    while True:
        want = t + FOOTAGE_CADENCE[k % len(FOOTAGE_CADENCE)]
        k += 1
        if len(cuts) == 1 and FOOTAGE_HOLD_MIN <= first_end + 0.3 <= FOOTAGE_HOLD_MAX:
            want = max(want, first_end + 0.3)   # the hook line stays on its opening shot
        near = [x for x in starts if abs(x - want) <= FOOTAGE_SNAP and FOOTAGE_HOLD_MIN <= x - t <= FOOTAGE_HOLD_MAX]
        cut = min(near, key=lambda x: abs(x - want)) if near else want
        if total - cut < FOOTAGE_HOLD_MIN:
            break
        cuts.append(round(cut, 3))
        t = cut
    if total - cuts[-1] > FOOTAGE_HOLD_MAX:   # stretch the tail evenly over the last two shots
        mid = round((cuts[-1] + total) / 2, 3)
        cuts.append(mid)
    return cuts


def footage_holds(script, timeline, total):
    """v4 plan: real footage only (E66: the Claude review of pilot-009 found the AI stills, a third of the picture,
    visibly painterly between real footage). A still is used only where the next footage shot would come back
    within REPEAT_GAP. Footage shot ids are "clip#k" (k-th 6.5 s segment of the clip); every id obeys REPEAT_GAP."""
    backgrounds, footage = script["backgrounds"], script["footage"]
    cuts = footage_cuts(timeline, total)
    shots = [f"{c}#{k}" for k in range(FOOTAGE_SEGMENTS) for c in footage]
    # Bible-story longs (SERIES.md): a segment may name the stills of its story moments ("stills": [...]); the
    # first cuts that start inside that segment show them, in order. Everything else stays real footage.
    wanted = {x["id"]: list(x.get("stills", [])) for x in script.get("segments", []) if x.get("stills")}
    spans = [(g["start"], g["end"], g["id"]) for g in timeline.get("segments", []) if g.get("id") in wanted]
    out, nf, ns, seen = [], 0, 0, {}
    for a, b in zip(cuts, cuts[1:] + [total]):
        h = {"start": a, "end": round(b, 3), "figure": False}
        moment = next((wanted[i] for lo, hi, i in spans if lo - 1e-6 <= a < hi and wanted[i]), None)
        shot = shots[nf % len(shots)] if shots else None
        if moment and a > 0:
            h["image"], h["kind"] = moment.pop(0), "still"
        elif shot and (shot not in seen or a - seen[shot] >= REPEAT_GAP - 1e-6):
            h["image"], h["kind"] = shot, "footage"
            nf += 1
        else:
            h["image"], h["kind"] = backgrounds[ns % len(backgrounds)], "still"
            ns += 1
        seen[h["image"]] = h["end"]
        out.append(h)
    last = {}
    for h in out:
        if h["image"] in last and h["start"] - last[h["image"]] < REPEAT_GAP - 1e-6:
            raise SystemExit(f"REPEAT_GAP_VIOLATION: {h['image']} back after {h['start'] - last[h['image']]:.1f} s "
                             f"< {REPEAT_GAP:.0f} s with {len(backgrounds)} backgrounds and {len(footage)} clips "
                             "(need more images or footage)")
        last[h["image"]] = h["end"]
    return out


def clip_of(shot):
    """'clip-x#2' -> ('clip-x', 2)."""
    clip, _, k = shot.partition("#")
    return clip, int(k or 0)


def compose(background, out):
    """Background filled to the output frame and slightly darkened (full frame, no figure: STANDARD R1)."""
    w, h = frame_size()
    sw, sh = (int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                               "stream=width,height", "-of", "csv=p=0", str(background)],
                                              capture_output=True, text=True, check=True).stdout.strip().split(","))
    if min(sw / w, sh / h) < 1.0:   # R10: never a plain upscale; re-run the AI super-resolution instead
        raise SystemExit(f"IMAGE_BELOW_FRAME {Path(background).name} {sw}x{sh} < {w}x{h} cover")
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},eq=brightness=-0.04:saturation=1.05"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(background), "-vf", vf, "-frames:v", "1", str(out)])


def footage_raw(clip, out, seconds, start=0.0):
    """A real footage scene (v4): the vetted clip, slowed only when it is shorter than the scene (never sped up),
    graded like the stills so footage and stills read as one film."""
    import cinematic
    have = probe_duration(clip) - start
    slow = max(1.0, seconds / max(have, 0.1))
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", str(clip), "-an", "-vf",
         f"setpts={slow:.4f}*(PTS-STARTPTS),fps=30,scale={frame_size()[0]}:{frame_size()[1]}:force_original_aspect_ratio=increase,"
         f"crop={frame_size()[0]}:{frame_size()[1]},"
         f"{cinematic.GRADE},trim=duration={seconds:.3f},setpts=PTS-STARTPTS,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", "30", str(out)])
    return slow


def assemble(work, script_path, images_dir, figure_path, music_path, footage_dir=None):
    import time
    t0 = time.time()

    def mark(stage):
        print(json.dumps({"stage": stage, "elapsed_s": round(time.time() - t0, 1)}), flush=True)
    work, images = Path(work), Path(images_dir)
    script = json.loads(Path(script_path).read_text())
    timeline = json.loads((work / "timeline.json").read_text())
    total = timeline["voice_seconds"] + TAIL
    mix = work / "mix.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(work / "voice.wav"),
         "-ss", str(MUSIC_OFFSET), "-t", str(total), "-i", str(music_path),
         "-filter_complex",
         f"[0:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,apad=whole_dur={total},asplit=2[v][key];"
         f"[1:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,volume=0.04,"
         f"afade=t=in:d={0.3 if script.get('footage') else 2},afade=t=out:st={total - 4}:d=4[m];"
         "[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck];"
         "[v][duck]amix=inputs=2:normalize=0:duration=first,"
         "loudnorm=I=-15:TP=-2:LRA=11:linear=true,alimiter=limit=0.75:attack=5:release=50:level=false,"
         # true-peak safety: the sample limiter misses inter-sample peaks (pilot-004: -0.2 dBTP after AAC from one
         # plosive at 1087 s); limiting at 4x oversampling gave -2.8 dBTP on that audio, loudness -15.6 LUFS
         f"aresample=192000,alimiter=limit=0.70:attack=1:release=100:level=false,aresample={RATE_OUT}[out]",
         "-map", "[out]", "-ar", str(RATE_OUT), str(mix)])
    mark("mix")
    plan = holds(script, timeline, total)
    frames, clips = work / "frames", work / "holds"
    frames.mkdir(exist_ok=True)
    clips.mkdir(exist_ok=True)
    used, footage_used = {}, {}
    footage = Path(footage_dir) if footage_dir else None
    for i, h in enumerate(plan):
        if h.get("kind") == "footage":
            clip = clip_of(h["image"])[0]
            if clip in footage_used:
                continue
            meta = json.loads((footage / f"{clip}.json").read_text())
            if sha256(footage / f"{clip}.mp4") != meta["sha256"]:
                raise SystemExit(f"FOOTAGE_HASH_MISMATCH {clip}")
            footage_used[clip] = {k: meta.get(k) for k in ("id", "source", "page", "author", "licence",
                                                                 "licence_url", "credit", "vetting", "sha256",
                                                                 "release_asset")}
            continue
        src = images / f"{h['image']}.png"
        meta = json.loads((images / f"{h['image']}.json").read_text())
        used[h["image"]] = {"sha256": sha256(src), "release_asset": meta.get("release_asset"), "models": meta["models"],
                            "seed": meta["seed"], "prompt": meta["prompt"]}
        compose(src, frames / f"{i:03d}.png")
    mark("frames")
    from concurrent.futures import ThreadPoolExecutor

    def length(i):
        return plan[i]["end"] - plan[i]["start"]

    cine = script.get("cinematic")  # {"depth_model": path or env, "atmosphere": [image ids with dust in the light]}
    if cine:
        import cinematic
        model = Path(os.environ.get("HERO_DEPTH_MODEL", cine.get("depth_model", "")))
        stills = [i for i in range(len(plan)) if plan[i].get("kind") != "footage"]
        for i in stills:
            cinematic.grade(frames / f"{i:03d}.png")
        cinematic.depth(model, [frames / f"{i:03d}.png" for i in stills])
        mark("depth")
    # 1) each background moves for its hold plus the cross-fade tail: true depth parallax when
    #    cinematic, otherwise a smooth single-plane camera
    def raw(i):
        out, seconds = clips / f"raw-{i:03d}.mp4", length(i) + FADE
        if plan[i].get("kind") == "footage":
            clip, k = clip_of(plan[i]["image"])
            src = footage / f"{clip}.mp4"
            start = max(0.0, min(k * FOOTAGE_SEGMENT_STEP, probe_duration(src) - seconds))
            plan[i]["motion"], plan[i]["source_start"] = "footage", round(start, 3)
            plan[i]["slow"] = round(footage_raw(src, out, seconds, start), 4)
        elif cine:
            plan[i]["motion"] = "dolly_in" if i == 0 else cinematic.MOVES[i % len(cinematic.MOVES)]
            plan[i]["atmosphere"] = plan[i]["image"] in cine.get("atmosphere", [])
            cinematic.parallax(frames / f"{i:03d}.png", frames / f"{i:03d}.depth.png", out, seconds,
                               plan[i]["motion"], dust=plan[i]["atmosphere"], intermediate=True)
        else:
            plan[i]["motion"] = "push_in" if i == 0 else MOTIONS[i % len(MOTIONS)]
            camera.render(frames / f"{i:03d}.png", out, seconds, plan[i]["motion"], intermediate=True)
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2) if cine else 4) as pool:
        list(pool.map(raw, range(len(plan))))
    mark("moves")

    # 2) segment i = tail of the previous move cross-faded into the start of this one
    def segment(i):
        out = clips / f"{i:03d}.mp4"
        common = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", "30", "-pix_fmt", "yuv420p",
                  "-video_track_timescale", "15360", "-threads", "2"]
        if i == 0:
            run(["ffmpeg", "-v", "error", "-y", "-i", str(clips / "raw-000.mp4"), "-vf",
                 f"trim=duration={length(0):.3f},setpts=PTS-STARTPTS", *common, str(out)])
        else:
            run(["ffmpeg", "-v", "error", "-y", "-i", str(clips / f"raw-{i - 1:03d}.mp4"), "-i", str(clips / f"raw-{i:03d}.mp4"),
                 "-filter_complex", f"[0:v]trim=start={length(i - 1):.3f},setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];"
                 f"[a][b]xfade=transition=fade:duration={FADE}:offset=0,trim=duration={length(i):.3f}", *common, str(out)])
        return f"file '{out}'"
    with ThreadPoolExecutor(max_workers=4) as pool:
        listing = list(pool.map(segment, range(len(plan))))
    for raw_clip in clips.glob("raw-*.mp4"):  # every segment is built: free the disk before the final pass
        raw_clip.unlink()
    mark("hold_clips")
    (work / "holds.txt").write_text("\n".join(listing) + "\n")
    (work / "captions.ass").write_text(build_ass(script, timeline, total))
    final = work / "pilot.mp4"
    title_end = script["overlay"]["title_card_seconds"]
    graph = "[0:v]null"  # STANDARD R1: full-frame scenery, no figure on top
    if cine:  # film finish on the picture, under the captions (text stays clean)
        graph += f"[pic];[pic]{cinematic.LOOK}"
    graph += f",ass={work / 'captions.ass'},format=yuv420p[vout]"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "holds.txt"), "-i", str(mix),
         "-filter_complex", graph, "-map", "[vout]", "-map", "1:a:0", "-shortest",
         "-c:v", "libx264", "-preset", FINAL_PRESET, "-crf", "18", "-r", "30", "-g", "60",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(RATE_OUT), "-t", f"{total:.3f}", "-movflags", "+faststart",
         str(final)])
    mark("final_encode")
    grammar = "standard-v1:fullframe-depth-parallax+film-look+captions" if cine else "standard-v1:fullframe-moving+captions"
    if footage_used:
        grammar = "standard-v4:licensed-footage+depth-parallax+film-look+captions"
    manifest = {"version": "pilot-manifest-v2", "pilot_id": script["pilot_id"], "grammar": grammar,
                "output_sha256": sha256(final), "output_seconds": probe_duration(final),
                "script_sha256": sha256(script_path),
                "voice": {"engine": script["voice"]["engine"], "voice_id": timeline["voice_id"],
                          "speed": timeline["speed"], "voice_wav_sha256": sha256(work / "voice.wav")},
                "music": {"file": Path(music_path).name, "sha256": sha256(music_path), "offset_seconds": MUSIC_OFFSET,
                          "rights": "Owned instrumental generator output (HeroVerse instrumental-v2 recipe)"},
                "figure": None,
                "images": used, "holds": plan, "captions_ass_sha256": sha256(work / "captions.ass"),
                "captions": [e for e in caption_events(timeline["sentences"]) if e["end"] > script["overlay"]["title_card_seconds"]],
                "sentences": timeline["sentences"],
                "overlay": {k: script["overlay"][k] for k in ("brand", "title", "title_card_seconds")},
                "persistent_overlays": ["brand"],
                "caption_style": {"box": False, "alignment": "bottom-centre", "outline": 4, "words_max": CAPTION_WORDS_MAX},
                "cta": cta_events(total, script),
                "scripture_cards": scripture_cards(script, timeline),
                "scene_target_seconds": FOOTAGE_TARGET if script.get("footage") else scene_target(script["backgrounds"]),
                "crossfade_seconds": FADE,
                "cinematic": ({"depth_model": {"name": "Depth Anything V2 Small (ONNX)", "licence": "apache-2.0",
                                               "sha256": sha256(model)}, "grade": cinematic.GRADE, "look": cinematic.LOOK,
                               "atmosphere": cine.get("atmosphere", [])} if cine else None),
                "clips": list(footage_used.values()), "shots": [], "timeline": timeline["segments"],
                "upload_performed": False, "publication_performed": False}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({"seconds": manifest["output_seconds"], "holds": len(plan), "images": len(used)}))


if __name__ == "__main__":
    if sys.argv[1] != "assemble":
        raise SystemExit(__doc__)
    assemble(*sys.argv[2:8])
