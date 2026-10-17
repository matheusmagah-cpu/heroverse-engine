#!/usr/bin/env python3
"""Produce each chosen Short as its own edit (not a crop of the long video).

Input: the moments chosen by shorts_select.py (analysis of the whole video).
Per Short, 1080x1920, from the long video's own sources (owned narration,
music, generated images, the figure):
  * picture: a new background every ~SCENE_S seconds, each a real depth-parallax
    camera move (cinematic.py, vertical), graded; the last scene returns to the
    first image so the end flows back into the start (loop);
  * figure: the same cut-out figure, lower third, under a soft light;
  * text inside the Shorts safe area (clear of the top bar, the right-hand
    buttons and the bottom caption/title zone): the on-screen hook for the first
    2.5 s, the scripture reference, captions of 2-4 words with the spoken word
    lit (karaoke timing from the sentence clock), the CTA in the last 4 s;
  * film finish (halation, vignette, grain) under the text;
  * sound: the exact narration, music ducked under the voice with a gentle swell
    at the end, loudness -14 LUFS, true peak under -1 dBTP.
Falls back to single-plane camera motion when no depth model is given.
usage: shorts_produce.py WORK SELECTION_JSON SCRIPT IMAGES_DIR FIGURE MUSIC OUT_DIR [DEPTH_MODEL]
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import RATE_OUT, MUSIC_OFFSET, run, sha256, probe_duration  # noqa: E402
from still_render import ts, ass_text  # noqa: E402

VW, VH = 1080, 1920
SCENE_S = 7.0
FIGURE_H = 900
MOVES = ("dolly_in", "crane_up", "truck_left", "arc", "dolly_out", "truck_right")
CTA = "Full prayer on the channel ▶"
LEAN = {"the", "a", "an", "to", "of", "and", "or", "in", "on", "at", "for", "with", "your", "my", "his", "that", "is", "be"}

HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,84,&H0000D7FF,&H00FFFFFF,&H00000000,&H78000000,1,0,0,0,100,100,0,0,1,7,3,5,110,170,0,1
Style: Hook,DejaVu Sans,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,3,18,0,8,90,170,300,1
Style: Ref,DejaVu Serif,50,&H00A3E7FF,&H00FFFFFF,&H00000000,&H64000000,1,1,0,0,100,100,0,0,1,4,2,8,90,170,520,1
Style: Cta,DejaVu Sans,50,&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,1,0,0,0,100,100,0,0,3,14,0,8,90,170,1180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def word_groups(text, max_words=4, max_chars=18):
    """Short caption groups (2-4 words) that respect punctuation."""
    groups, cur = [], []
    for w in text.split():
        if cur and (len(cur) == max_words or len(" ".join(cur + [w])) > max_chars):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[,.;:!?]$", w) and len(cur) >= 2:
            groups.append(cur)
            cur = []
    # never leave a line hanging on a function word ("the", "to", ...): it moves to the next line
    for k in range(len(groups) - 1):
        while len(groups[k]) > 1 and groups[k][-1].lower() in LEAN:
            groups[k + 1].insert(0, groups[k].pop())
    if cur:
        if groups and len(cur) == 1 and len(" ".join(groups[-1] + cur)) <= max_chars + 6:
            groups[-1] += cur
        else:
            groups.append(cur)
    return groups


def captions(moment):
    """Karaoke lines: white text with the current word lit gold (\\k timing by characters)."""
    t0, lines = moment["start"], []
    for s in moment["sentences"]:
        groups = word_groups(s["text"])
        chars = sum(len(" ".join(g)) for g in groups)
        t = s["start"] - t0
        for g in groups:
            span = (s["end"] - s["start"]) * len(" ".join(g)) / chars
            per = [span * len(w) / sum(len(x) for x in g) for w in g]
            body = "".join(f"{{\\k{max(1, int(round(d * 100)))}}}{ass_text(w)} " for w, d in zip(g, per)).rstrip()
            # SecondaryColour (white) before the word is spoken, PrimaryColour (gold) once it is
            lines.append(f"Dialogue: 4,{ts(t)},{ts(t + span)},Cap,,0,0,0,,{{\\pos(500,860)\\fad(60,40)}}{body}")
            t += span
    return lines


def ass(moment, hook, reference, dur):
    lines = [f"Dialogue: 5,{ts(0)},{ts(min(2.5, dur))},Hook,,0,0,0,,{{\\fad(0,200)}}{ass_text(hook)}"]
    if reference:
        lines.append(f"Dialogue: 3,{ts(0.4)},{ts(dur)},Ref,,0,0,0,,{{\\fad(300,0)}}{ass_text(reference)}")
    lines += captions(moment)
    lines.append(f"Dialogue: 5,{ts(max(0, dur - 4.0))},{ts(dur)},Cta,,0,0,0,,{{\\fad(200,0)}}{ass_text(CTA)}")
    return HEAD + "\n".join(lines) + "\n"


def vertical_still(src, out):
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf",
         f"scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},eq=brightness=-0.05:saturation=1.05",
         "-frames:v", "1", str(out)])


def produce(work, moment, index, script, images, figure, music, out, depth_model=None):
    import cinematic
    dur = moment["end"] - moment["start"] + 0.6
    tmp = out / f"tmp-{index:02d}"
    tmp.mkdir(parents=True, exist_ok=True)
    backgrounds = script["backgrounds"]
    n = max(2, round(dur / SCENE_S))
    picks = [backgrounds[(index * 5 + 3 + 2 * k) % len(backgrounds)] for k in range(n - 1)]
    picks.append(picks[0])  # loop: the last scene returns to the first image
    stills = []
    for k, b in enumerate(picks):
        p = tmp / f"s{k:02d}.png"
        vertical_still(images / f"{b}.png", p)
        cinematic.grade(p)
        stills.append(p)
    if depth_model:
        cinematic.depth(depth_model, stills)
    length = dur / n
    fade = 0.5
    clips = []
    for k, p in enumerate(stills):
        c = tmp / f"c{k:02d}.mp4"
        move = MOVES[(index + k) % len(MOVES)]
        if depth_model:
            cinematic.parallax(p, p.with_suffix(".depth.png"), c, length + fade, move,
                               dust=picks[k] in script.get("cinematic", {}).get("atmosphere", []), size=(VW, VH))
        else:
            run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", f"{length + fade:.3f}", "-i", str(p),
                 "-vf", f"scale={int(VW * 1.1)}:{int(VH * 1.1)},zoompan=z='1+0.0008*on':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={VW}x{VH}:fps=30",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", str(c)])
        clips.append(c)
    # cross-fade the scenes into one background track
    inputs = sum((["-i", str(c)] for c in clips), [])
    graph, last = [], "[0:v]"
    for k in range(1, len(clips)):
        label = f"[x{k}]"
        graph.append(f"{last}[{k}:v]xfade=transition=fade:duration={fade}:offset={k * length - fade / 2:.3f}{label}")
        last = label
    bg = tmp / "bg.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(graph) if graph else "[0:v]null", "-map",
         last if graph else "0:v", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", str(bg)])
    hook, reference = moment["hook"], moment.get("reference")
    (tmp / "s.ass").write_text(ass(moment, hook, reference, dur))
    graded_fig = tmp / "figure.png"
    cinematic.grade(figure, graded_fig)
    mp4 = out / f"short-{index:02d}.mp4"
    swell = f"volume='0.05+0.04*max(0,(t-{dur - 5:.2f})/5)':eval=frame"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(bg), "-loop", "1", "-framerate", "30", "-i", str(graded_fig),
         "-ss", f"{moment['start']:.3f}", "-t", f"{dur:.3f}", "-i", str(work / "voice.wav"),
         "-ss", str(MUSIC_OFFSET + moment["start"]), "-t", f"{dur:.3f}", "-i", str(music),
         "-filter_complex",
         f"[1:v]scale=-1:{FIGURE_H}[fg];[0:v][fg]overlay=x=(W-w)/2:y=H-h-120[pic];[pic]{cinematic.look(VW, VH)}[look];"
         f"[look]ass={tmp / 's.ass'},format=yuv420p[vout];"
         f"[2:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,afade=t=out:st={dur - 0.5:.3f}:d=0.5,asplit=2[vo][key];"
         f"[3:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,{swell},afade=t=in:d=0.5,"
         f"afade=t=out:st={dur - 0.8:.3f}:d=0.8[m];[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck];"
         "[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=9,"
         "alimiter=limit=0.75:attack=5:release=50:level=false[aout]",
         "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-r", "30",
         "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE_OUT), "-t", f"{dur:.3f}", "-movflags", "+faststart", str(mp4)])
    shutil.rmtree(tmp)
    return {"file": mp4.name, "sha256": sha256(mp4), "seconds": round(probe_duration(mp4), 2),
            "source_start": moment["start"], "source_end": moment["end"], "segments": moment["segments"],
            "hook": hook, "title": moment.get("title") or hook, "reference": reference,
            "scenes": picks, "parallax": bool(depth_model),
            "selection": {k: moment.get(k) for k in ("final_score", "measured_score", "features", "rubric")},
            "text": " ".join(s["text"] for s in moment["sentences"])}


def main(work, selection, script_path, images_dir, figure, music, out_dir, depth_model=None):
    work, out = Path(work), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    sel = json.loads(Path(selection).read_text())
    records = [produce(work, m, i, script, Path(images_dir), figure, music, out, depth_model)
               for i, m in enumerate(sel["chosen"])]
    (out / "shorts.json").write_text(json.dumps({"version": "shorts-produce-v1", "source_pilot": script["pilot_id"],
                                                 "selection_rubric_model": sel.get("rubric_model"), "shorts": records},
                                                indent=1, ensure_ascii=False) + "\n")
    print(json.dumps([{k: r[k] for k in ("file", "seconds", "hook")} for r in records], ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:9])
