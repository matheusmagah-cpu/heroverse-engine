#!/usr/bin/env python3
"""pilot-002 grammar renderer: generated stills + synchronized captions.

  still_render.py assemble WORK SCRIPT IMAGES_DIR MUSIC

Picture: one generated image per visual-plan entry, held over its script
segments with a slow push-in (per-frame scaling at 2x then downscale, so the
motion is sub-pixel smooth) and 1 s cross-fades. Text (libass): a title card,
large spoken-line captions in a translucent box timed from the exact
per-sentence narration timeline, scripture references, a channel mark and
engagement prompts. Audio: identical to pilot_render (voice forward, owned
music ducked, -15 LUFS). Writes pilot.mp4 and manifest.json; no upload.
"""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_render import REFERENCES, RATE_OUT, TAIL, MUSIC_OFFSET, probe_duration, run, sha256  # noqa: E402

FADE = 1.0
PUSH = 0.07
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
    return [line for part in merged for line in split_balanced(part.split())]


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
Style: Caption,DejaVu Sans,74,&H00FFFFFF,&H00FFFFFF,&H64000000,&H00000000,1,0,0,0,100,100,0,0,3,22,0,2,160,160,150,1
Style: Title,DejaVu Serif,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,5,4,5,120,120,0,1
Style: Subtitle,DejaVu Sans,54,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,2,0,1,4,3,5,120,120,0,1
Style: Ref,DejaVu Serif,52,&H00A3E7FF,&H00FFFFFF,&H00000000,&H96000000,1,1,0,0,100,100,0,0,1,4,2,8,120,120,70,1
Style: Brand,DejaVu Sans,34,&H50FFFFFF,&H00FFFFFF,&H64000000,&H00000000,1,0,0,0,100,100,2,0,1,2,0,9,0,50,40,1
Style: Prompt,DejaVu Sans,60,&H00FFFFFF,&H00FFFFFF,&H0040301E,&H00000000,1,0,0,0,100,100,0,0,3,18,0,8,160,160,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    def add(style, a, b, text, layer=0, fade=(250, 250)):
        lines.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{style},,0,0,0,,{{\\fad({fade[0]},{fade[1]})}}{ass_text(text)}")
    title_end = overlay["title_card_seconds"]
    add("Title", 0.0, title_end, overlay["title"], 2, (400, 500))
    lines.append(f"Dialogue: 2,{ts(0)},{ts(title_end)},Subtitle,,0,0,0,,{{\\fad(400,500)\\pos(960,660)}}{ass_text(overlay['subtitle'])}")
    add("Brand", 0.0, total, overlay["brand"], 1, (0, 0))
    for e in caption_events(timeline["sentences"]):
        if e["end"] > title_end:
            add("Caption", max(e["start"], title_end), e["end"], e["text"], 3, (80, 80))
    for seg in timeline["segments"]:
        if seg["id"] in REFERENCES:
            add("Ref", seg["start"], seg["end"], REFERENCES[seg["id"]], 3)
    for p in overlay["prompts"]:
        seg = next(s for s in timeline["segments"] if s["id"] == p["segment"])
        a = seg["start"] if p.get("at") != "end" else seg["end"]
        add("Prompt", a, a + p["seconds"], p["text"], 4, (300, 300))
    return head + "\n".join(lines) + "\n"


def holds(script, timeline, total):
    """Each visual-plan entry covers its segments; starts at its first segment's start."""
    starts = {s["id"]: s["start"] for s in timeline["segments"]}
    plan = []
    for i, entry in enumerate(script["visual_plan"]):
        start = 0.0 if i == 0 else starts[entry["from"]]
        plan.append({"image": entry["image"], "start": start})
    for a, b in zip(plan, plan[1:]):
        a["end"] = b["start"]
    plan[-1]["end"] = total
    return plan


def assemble(work, script_path, images_dir, music_path):
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
         "loudnorm=I=-15:TP=-1.5:LRA=11:linear=true[out]",
         "-map", "[out]", "-ar", str(RATE_OUT), str(mix)])
    plan = holds(script, timeline, total)
    clips = work / "holds"
    clips.mkdir(exist_ok=True)
    used = {}
    for i, h in enumerate(plan):
        src = images / f"{h['image']}.png"
        meta = json.loads((images / f"{h['image']}.json").read_text())
        used[h["image"]] = {"sha256": sha256(src), "release_asset": meta.get("release_asset"), "models": meta["models"],
                            "seed": meta["seed"], "prompt": meta["prompt"]}
        length = h["end"] - h["start"] + (FADE if i < len(plan) - 1 else 0)
        h["clip_seconds"] = round(length, 3)
        out = clips / f"{i:03d}.mp4"
        zoom = f"(1+{PUSH}*t/{length:.3f})" if i % 2 == 0 else f"(1+{PUSH}-{PUSH}*t/{length:.3f})"
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", f"{length:.3f}", "-i", str(src),
             "-vf", f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
                    f"scale=w='trunc(3840*{zoom}/2)*2':h='trunc(2160*{zoom}/2)*2':eval=frame:flags=bicubic,"
                    "crop=3840:2160,scale=1920:1080:flags=area,eq=brightness=-0.03,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", "30", str(out)])
    # Chain cross-fades.
    inputs, chain, last, offset = [], [], "[0:v]", 0.0
    for i, h in enumerate(plan):
        inputs += ["-i", str(clips / f"{i:03d}.mp4")]
    for i in range(1, len(plan)):
        offset += plan[i - 1]["end"] - plan[i - 1]["start"]
        label = f"[x{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{label}")
        last = label
    (work / "captions.ass").write_text(build_ass(script, timeline, total))
    chain.append(f"{last}ass={work / 'captions.ass'},format=yuv420p[vout]")
    final = work / "pilot.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", str(mix), "-filter_complex", ";".join(chain),
         "-map", "[vout]", "-map", f"{len(plan)}:a:0", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "30", "-g", "60", "-c:a", "aac", "-b:a", "192k", "-ar", str(RATE_OUT), "-t", f"{total:.3f}",
         "-movflags", "+faststart", str(final)])
    manifest = {"version": "pilot-manifest-v2", "pilot_id": script["pilot_id"], "grammar": "stills+captions",
                "output_sha256": sha256(final), "output_seconds": probe_duration(final),
                "script_sha256": sha256(script_path),
                "voice": {"engine": script["voice"]["engine"], "voice_id": timeline["voice_id"],
                          "speed": timeline["speed"], "voice_wav_sha256": sha256(work / "voice.wav")},
                "music": {"file": Path(music_path).name, "sha256": sha256(music_path), "offset_seconds": MUSIC_OFFSET,
                          "rights": "Owned instrumental generator output (HeroVerse instrumental-v2 recipe)"},
                "images": used, "holds": plan, "captions_ass_sha256": sha256(work / "captions.ass"),
                "clips": [], "shots": [], "timeline": timeline["segments"],
                "upload_performed": False, "publication_performed": False}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({"seconds": manifest["output_seconds"], "holds": len(plan), "images": len(used)}))


if __name__ == "__main__":
    if sys.argv[1] != "assemble":
        raise SystemExit(__doc__)
    assemble(*sys.argv[2:6])
