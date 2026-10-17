#!/usr/bin/env python3
"""Vertical Shorts cut from a rendered long video's own sources (not a crop of
the 16:9 frame): exact narration sentences, the same figure and backgrounds,
large centred captions, a hook line first and a CTA to the full video.

Selection rules (precision, no mid-sentence cut):
  - a window of consecutive sentences from ONE script segment run, 30-55 s;
  - it starts at a sentence that does not lean on prior context (no leading
    And/But/So/This/That/It/He/She/They/Notice) and ends on a full sentence;
  - preference: scripture anchors with their reflection, then prayers;
  - at most N windows, never overlapping.
usage: shorts_cut.py WORK SCRIPT IMAGES_DIR FIGURE MUSIC OUT_DIR [N]
"""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import RATE_OUT, MUSIC_OFFSET, run, sha256, probe_duration  # noqa: E402
from still_render import chunks, ts, ass_text  # noqa: E402

MIN_S, MAX_S = 30.0, 55.0
CONTEXT_START = re.compile(r"(?i)^(and|but|so|this|that|it|he|she|they|notice|then|because|or|yet)\b")
PRIORITY = (("scripture", 3), ("reflection", 2), ("payoff", 2), ("declaration", 2), ("prayer", 1))


def family(segment_id):
    return next((w for name, w in PRIORITY if segment_id.startswith(name)), 0)


def windows(sentences, script):
    order = [s["id"] for s in script["segments"]]
    # pair each scripture anchor with the segment that follows it
    groups, i = [], 0
    while i < len(order):
        ids = [order[i]]
        if order[i].startswith("scripture") and i + 1 < len(order):
            ids.append(order[i + 1])
        groups.append(ids)
        i += len(ids)
    found = []
    for ids in groups:
        run_s = [s for s in sentences if s["segment"] in ids]
        for a in range(len(run_s)):
            if CONTEXT_START.match(run_s[a]["text"]) and a != 0:
                continue
            for b in range(a, len(run_s)):
                length = run_s[b]["end"] - run_s[a]["start"]
                if length > MAX_S:
                    break
                if length >= MIN_S:
                    score = max(family(x) for x in ids) * 100 - abs(length - 42)
                    found.append({"start": run_s[a]["start"], "end": run_s[b]["end"], "segments": ids,
                                  "sentences": run_s[a:b + 1], "score": score})
                    break
    found.sort(key=lambda w: w["score"], reverse=True)
    chosen = []
    for w in found:
        if all(w["end"] <= c["start"] or w["start"] >= c["end"] for c in chosen) and \
                all(set(w["segments"]).isdisjoint(c["segments"]) for c in chosen):
            chosen.append(w)
    return chosen


def ass_vertical(w, hook, cta, reference):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,3,5,90,90,0,1
Style: Hook,DejaVu Sans,82,&H0000E5FF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,7,3,8,70,70,230,1
Style: Ref,DejaVu Serif,52,&H00A3E7FF,&H00FFFFFF,&H00000000,&H64000000,1,1,0,0,100,100,0,0,1,4,2,8,70,70,470,1
Style: Cta,DejaVu Sans,50,&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,1,0,0,0,100,100,0,0,3,14,0,2,80,80,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    t0, dur = w["start"], w["end"] - w["start"] + 0.6
    lines = [f"Dialogue: 3,{ts(0)},{ts(min(3.0, dur))},Hook,,0,0,0,,{{\\fad(0,250)}}{ass_text(hook)}"]
    if reference:
        lines.append(f"Dialogue: 2,{ts(0)},{ts(dur)},Ref,,0,0,0,,{ass_text(reference)}")
    for s in w["sentences"]:
        parts = chunks(s["text"])
        total = sum(len(p) for p in parts)
        t = s["start"] - t0
        for p in parts:
            span = (s["end"] - s["start"]) * len(p) / total
            lines.append(f"Dialogue: 4,{ts(t)},{ts(t + span)},Cap,,0,0,0,,{{\\pos(540,720)}}{ass_text(p)}")
            t += span
    lines.append(f"Dialogue: 4,{ts(max(0, dur - 4.0))},{ts(dur)},Cta,,0,0,0,,{{\\fad(200,0)}}{ass_text(cta)}")
    return head + "\n".join(lines) + "\n", dur


def main(work, script_path, images_dir, figure, music, out_dir, n="3"):
    work, out = Path(work), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    timeline = json.loads((work / "timeline.json").read_text())
    refs = {s["id"]: s.get("reference") for s in script["segments"]}
    chosen = windows(timeline["sentences"], script)[: int(n)]
    backgrounds = script["backgrounds"]
    records = []
    for i, w in enumerate(chosen):
        ref = next((refs[x] for x in w["segments"] if refs.get(x)), None)
        hooks = {s["id"]: s.get("short_hook") for s in script["segments"]}
        hook = next((hooks[x] for x in w["segments"] if hooks.get(x)), None) or (
            "Read this before your day starts" if ref else "Pray this with me right now")
        ass, dur = ass_vertical(w, hook, "Full prayer on the channel ▶", ref)
        (out / f"short-{i:02d}.ass").write_text(ass)
        bg = Path(images_dir) / f"{backgrounds[(i * 5 + 3) % len(backgrounds)]}.png"
        mp4 = out / f"short-{i:02d}.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", str(bg),
             "-i", str(figure), "-ss", f"{w['start']:.3f}", "-t", f"{dur:.3f}", "-i", str(work / "voice.wav"),
             "-ss", str(MUSIC_OFFSET + w["start"]), "-t", f"{dur:.3f}", "-i", str(music),
             "-filter_complex",
             "[0:v]scale=-2:1920,crop=1080:1920,eq=brightness=-0.08,"
             f"scale=w='trunc(1080*(1+0.05*t/{dur:.3f})/2)*2':h='trunc(1920*(1+0.05*t/{dur:.3f})/2)*2':eval=frame,"
             "crop=1080:1920[bg];[1:v]scale=-1:820[fg];[bg][fg]overlay=x=(W-w)/2:y=H-h-250[v];"
             f"[v]ass={out / f'short-{i:02d}.ass'},format=yuv420p[vout];"
             f"[2:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,afade=t=out:st={dur - 0.5:.3f}:d=0.5,asplit=2[vo][key];"
             f"[3:a]aresample={RATE_OUT},aformat=channel_layouts=stereo,volume=0.05,afade=t=in:d=0.5,"
             f"afade=t=out:st={dur - 0.8:.3f}:d=0.8[m];[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck];"
             "[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=9[aout]",
             "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30",
             "-c:a", "aac", "-b:a", "160k", "-ar", str(RATE_OUT), "-t", f"{dur:.3f}", "-movflags", "+faststart", str(mp4)])
        records.append({"file": mp4.name, "sha256": sha256(mp4), "seconds": round(probe_duration(mp4), 2),
                        "source_start": w["start"], "source_end": w["end"], "segments": w["segments"],
                        "hook": hook, "reference": ref, "text": " ".join(s["text"] for s in w["sentences"])})
    (out / "shorts.json").write_text(json.dumps({"version": "shorts-cut-v1", "source_pilot": script["pilot_id"],
                                                 "shorts": records}, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps([{k: r[k] for k in ("file", "seconds", "segments")} for r in records]))


if __name__ == "__main__":
    main(*sys.argv[1:8])
