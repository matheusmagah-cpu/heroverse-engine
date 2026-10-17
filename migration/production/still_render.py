#!/usr/bin/env python3
"""pilot-002 grammar renderer: generated stills + synchronized captions.

  still_render.py assemble WORK SCRIPT IMAGES_DIR FIGURE_RGBA_PNG MUSIC

Picture (archetype amendment 2026-10-17): one persistent cut-out figure at
the left of the frame over generated backgrounds that change at sentence
starts about every BACKGROUND_TARGET seconds, with short cross-fades; a title
card first. Text (libass): large spoken-line captions in a translucent box at
right-centre timed from the exact per-sentence narration timeline, scripture
references, a channel mark, a rotating subscribe/like/share badge and a
persistent "Type AMEN" prompt. Audio: identical to pilot_render (voice forward, owned
music ducked, -15 LUFS). Writes pilot.mp4 and manifest.json; no upload.
"""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import REFERENCES, RATE_OUT, TAIL, MUSIC_OFFSET, probe_duration, run, sha256  # noqa: E402
import motion as camera  # noqa: E402

MOTIONS = ("push_in", "drift", "pull_out", "pan_right", "push_in", "pan_left")

FADE = 0.6
BACKGROUND_TARGET = 9.0
HOLD_MAX = 18.0
FIGURE_HEIGHT = 1000
FIGURE_X = 30
BOX = (1010, 330, 1850, 750)
BADGES = ("SUBSCRIBE", "LIKE", "SHARE")
BADGE_SECONDS = 6.0
CAPTION_WORDS_MAX = 8
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
    # guarantee: no line over the limit (the balanced split's last remainder can overflow)
    out = []
    for line in lines:
        out += [line] if len(line) <= CAPTION_CHARS_MAX else chunks_hard(line)
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
Style: Caption,DejaVu Sans,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,2,5,1040,100,0,1
Style: Box,DejaVu Sans,20,&H5A2A2A2A,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Title,DejaVu Serif,112,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,5,4,5,120,120,0,1
Style: Subtitle,DejaVu Sans,58,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,2,0,1,4,3,5,120,120,0,1
Style: Ref,DejaVu Serif,50,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,1,0,0,100,100,0,0,1,4,2,2,1040,100,250,1
Style: Brand,DejaVu Sans,36,&H20FFFFFF,&H00FFFFFF,&H64000000,&H00000000,1,0,0,0,100,100,2,0,1,3,1,7,50,0,40,1
Style: Badge,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H001A1AD0,&H00000000,1,0,0,0,100,100,1,0,3,10,0,9,0,50,46,1
Style: Amen,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,1,0,0,100,100,1,0,1,4,3,3,0,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    def add(style, a, b, text, layer=0, fade=(250, 250)):
        lines.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,,{{\\fad({fade[0]},{fade[1]})}}{ass_text(text)}")
    title_end = overlay["title_card_seconds"]
    add("Title", 0.0, title_end, overlay["title"], 2, (200, 300))
    lines.append(f"Dialogue: 2,{ts(0)},{ts(title_end)},Subtitle,,0,0,0,,{{\\fad(200,300)\\pos(960,700)}}{ass_text(overlay['subtitle'])}")
    add("Brand", title_end, total, overlay["brand"], 1, (300, 0))
    add("Amen", title_end, total, overlay["amen"], 1, (300, 0))
    t, k = title_end, 0
    while t < total - 1:
        add("Badge", t, min(total, t + BADGE_SECONDS - 0.3), BADGES[k % len(BADGES)], 1, (200, 200))
        t, k = t + BADGE_SECONDS, k + 1
    x0, y0, x1, y1 = BOX
    shape = f"m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1}"
    for e in caption_events(timeline["sentences"]):
        if e["end"] > title_end:
            a = max(e["start"], title_end)
            lines.append(f"Dialogue: 3,{ts(a)},{ts(e['end'])},Box,,0,0,0,,{{\\pos(0,0)\\p1}}{shape}{{\\p0}}")
            lines.append(f"Dialogue: 4,{ts(a)},{ts(e['end'])},Caption,,0,0,0,,{{\\pos({(x0 + x1) // 2},{(y0 + y1) // 2})}}{ass_text(e['text'])}")
    refs = {seg["id"]: seg["reference"] for seg in script["segments"] if seg.get("reference")} or REFERENCES
    for seg in timeline["segments"]:
        if seg["id"] in refs:
            add("Ref", seg["start"], seg["end"], refs[seg["id"]], 4)
    return head + "\n".join(lines) + "\n"


def holds(script, timeline, total):
    """Title card, then a new background at the first sentence start at least
    BACKGROUND_TARGET seconds after the previous change, cycling through the
    plan's backgrounds in order (never the same one twice in a row)."""
    overlay, backgrounds = script["overlay"], script["backgrounds"]
    plan = [{"image": overlay["title_image"], "start": 0.0, "figure": False}]
    last, k = overlay["title_card_seconds"], 0
    plan.append({"image": backgrounds[0], "start": last, "figure": True})
    for s in timeline["sentences"]:
        if s["start"] - last >= BACKGROUND_TARGET and total - s["start"] > BACKGROUND_TARGET / 2:
            k += 1
            plan.append({"image": backgrounds[k % len(backgrounds)], "start": s["start"], "figure": True})
            last = s["start"]
    for a, b in zip(plan, plan[1:]):
        a["end"] = b["start"]
    plan[-1]["end"] = total
    # no background held longer than HOLD_MAX: split long holds evenly with new backgrounds
    out = [plan[0]]
    for h in plan[1:]:
        parts = max(1, -(-(h["end"] - h["start"]) // HOLD_MAX))
        step = (h["end"] - h["start"]) / parts
        for p in range(int(parts)):
            if p:
                k += 1
                if backgrounds[k % len(backgrounds)] == out[-1]["image"]:
                    k += 1
            image = h["image"] if p == 0 else backgrounds[k % len(backgrounds)]
            out.append({"image": image, "start": round(h["start"] + p * step, 3),
                        "end": round(h["start"] + (p + 1) * step, 3), "figure": True})
    return out


def compose(background, figure, out, with_figure):
    """Background filled to 1920x1080 and slightly darkened, figure bottom-left."""
    vf = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,eq=brightness=-0.04:saturation=1.05[bg]"
    if with_figure:
        vf += f";[1:v]scale=-1:{FIGURE_HEIGHT}[fg];[bg][fg]overlay=x={FIGURE_X}:y=H-h[out]"
        args = ["-i", str(background), "-i", str(figure)]
    else:
        vf += ";[bg]null[out]"
        args = ["-i", str(background)]
    run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", vf, "-map", "[out]", "-frames:v", "1", str(out)])


def assemble(work, script_path, images_dir, figure_path, music_path):
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
         f"afade=t=in:d=2,afade=t=out:st={total - 4}:d=4[m];"
         "[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=20:release=600[duck];"
         "[v][duck]amix=inputs=2:normalize=0:duration=first,"
         "loudnorm=I=-15:TP=-2:LRA=11:linear=true,alimiter=limit=0.75:attack=5:release=50:level=false[out]",
         "-map", "[out]", "-ar", str(RATE_OUT), str(mix)])
    mark("mix")
    plan = holds(script, timeline, total)
    moving = script.get("motion", True)  # camera motion on backgrounds; the figure stays still on top (2.5D depth)
    frames, clips = work / "frames", work / "holds"
    frames.mkdir(exist_ok=True)
    clips.mkdir(exist_ok=True)
    used = {}
    for i, h in enumerate(plan):
        src = images / f"{h['image']}.png"
        meta = json.loads((images / f"{h['image']}.json").read_text())
        used[h["image"]] = {"sha256": sha256(src), "release_asset": meta.get("release_asset"), "models": meta["models"],
                            "seed": meta["seed"], "prompt": meta["prompt"]}
        compose(src, figure_path, frames / f"{i:03d}.png", h["figure"] and not moving)
    mark("frames")
    from concurrent.futures import ThreadPoolExecutor

    def length(i):
        return plan[i]["end"] - plan[i]["start"]

    cine = script.get("cinematic")  # {"depth_model": path or env, "atmosphere": [image ids with dust in the light]}
    if cine:
        import cinematic
        model = Path(os.environ.get("HERO_DEPTH_MODEL", cine.get("depth_model", "")))
        for i in range(len(plan)):
            cinematic.grade(frames / f"{i:03d}.png")
        graded_figure = work / "figure-graded.png"
        cinematic.grade(figure_path, graded_figure)
        cinematic.depth(model, [frames / f"{i:03d}.png" for i in range(len(plan))])
        mark("depth")
    if moving:
        # 1) each background moves for its hold plus the cross-fade tail: true depth parallax when
        #    cinematic, otherwise a smooth single-plane camera
        def raw(i):
            out, seconds = clips / f"raw-{i:03d}.mp4", length(i) + FADE
            if cine:
                plan[i]["motion"] = "dolly_in" if i == 0 else cinematic.MOVES[i % len(cinematic.MOVES)]
                plan[i]["atmosphere"] = plan[i]["image"] in cine.get("atmosphere", [])
                cinematic.parallax(frames / f"{i:03d}.png", frames / f"{i:03d}.depth.png", out, seconds,
                                   plan[i]["motion"], dust=plan[i]["atmosphere"], intermediate=True)
            else:
                plan[i]["motion"] = "push_in" if i == 0 else MOTIONS[i % len(MOTIONS)]
                camera.render(frames / f"{i:03d}.png", out, seconds, plan[i]["motion"], intermediate=True)
        with ThreadPoolExecutor(max_workers=2 if cine else 4) as pool:
            list(pool.map(raw, range(len(plan))))
        mark("moves")

        # 2) segment i = tail of the previous move cross-faded into the start of this one
        def segment(i):
            out = clips / f"{i:03d}.mp4"
            common = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-r", "30", "-pix_fmt", "yuv420p",
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
    else:
        def encode(i):
            out = clips / f"{i:03d}.mp4"
            common = ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "17", "-r", "30",
                      "-pix_fmt", "yuv420p", "-video_track_timescale", "15360", "-threads", "2"]
            # Stills are read at 1 fps and repeated to 30 fps by the fps filter: same frames,
            # without decoding the PNG 30 times per second.
            if i == 0:
                run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "1", "-t", f"{length(i) + 1:.3f}",
                     "-i", str(frames / "000.png"), "-vf", f"fps=30,trim=duration={length(i):.3f}", *common, str(out)])
            else:
                run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "1", "-t", "2",
                     "-i", str(frames / f"{i - 1:03d}.png"), "-loop", "1", "-framerate", "1", "-t", f"{length(i) + 1:.3f}",
                     "-i", str(frames / f"{i:03d}.png"), "-filter_complex",
                     f"[0:v]fps=30,trim=duration={FADE},setpts=PTS-STARTPTS[a];[1:v]fps=30,setpts=PTS-STARTPTS[b];"
                     f"[a][b]xfade=transition=fade:duration={FADE}:offset=0,trim=duration={length(i):.3f}",
                     *common, str(out)])
            return f"file '{out}'"
        with ThreadPoolExecutor(max_workers=4) as pool:
            listing = list(pool.map(encode, range(len(plan))))
    mark("hold_clips")
    (work / "holds.txt").write_text("\n".join(listing) + "\n")
    (work / "captions.ass").write_text(build_ass(script, timeline, total))
    final = work / "pilot.mp4"
    title_end = script["overlay"]["title_card_seconds"]
    graph = (f"[2:v]scale=-1:{FIGURE_HEIGHT}[fg];[0:v][fg]overlay=x={FIGURE_X}:y=H-h:enable='gte(t,{title_end})'"
             if moving else "[0:v]null")
    if cine:  # film finish on picture and figure together, under the captions (text stays clean)
        graph += f"[pic];[pic]{cinematic.LOOK}"
    graph += f",ass={work / 'captions.ass'},format=yuv420p[vout]"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "holds.txt"), "-i", str(mix),
         "-loop", "1", "-framerate", "30", "-i", str(graded_figure if cine else figure_path),
         "-filter_complex", graph, "-map", "[vout]", "-map", "1:a:0", "-shortest",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", "30", "-g", "60",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(RATE_OUT), "-t", f"{total:.3f}", "-movflags", "+faststart",
         str(final)])
    mark("final_encode")
    figure_meta = json.loads(Path(figure_path).with_suffix(".json").read_text())
    grammar = ("figure+depth-parallax-backgrounds+film-look+captions" if cine else
               "figure+moving-backgrounds+captions" if moving else "figure+backgrounds+captions")
    manifest = {"version": "pilot-manifest-v2", "pilot_id": script["pilot_id"], "grammar": grammar,
                "output_sha256": sha256(final), "output_seconds": probe_duration(final),
                "script_sha256": sha256(script_path),
                "voice": {"engine": script["voice"]["engine"], "voice_id": timeline["voice_id"],
                          "speed": timeline["speed"], "voice_wav_sha256": sha256(work / "voice.wav")},
                "music": {"file": Path(music_path).name, "sha256": sha256(music_path), "offset_seconds": MUSIC_OFFSET,
                          "rights": "Owned instrumental generator output (HeroVerse instrumental-v2 recipe)"},
                "figure": {"sha256": sha256(figure_path), **figure_meta},
                "images": used, "holds": plan, "captions_ass_sha256": sha256(work / "captions.ass"),
                "captions": [e for e in caption_events(timeline["sentences"]) if e["end"] > script["overlay"]["title_card_seconds"]],
                "sentences": timeline["sentences"],
                "overlay": {k: script["overlay"][k] for k in ("brand", "amen", "title", "title_card_seconds")},
                "badges": list(BADGES),
                "cinematic": ({"depth_model": {"name": "Depth Anything V2 Small (ONNX)", "licence": "apache-2.0",
                                               "sha256": sha256(model)}, "grade": cinematic.GRADE, "look": cinematic.LOOK,
                               "atmosphere": cine.get("atmosphere", [])} if cine else None),
                "clips": [], "shots": [], "timeline": timeline["segments"],
                "upload_performed": False, "publication_performed": False}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({"seconds": manifest["output_seconds"], "holds": len(plan), "images": len(used)}))


if __name__ == "__main__":
    if sys.argv[1] != "assemble":
        raise SystemExit(__doc__)
    assemble(*sys.argv[2:7])
