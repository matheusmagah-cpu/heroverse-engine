#!/usr/bin/env python3
"""Compose a Bible-series Short with the engine, at no credit cost (owner, 2026-10-25: "montar no motor, grátis").

The voice is the long's pinned Kokoro voice (`pilot_render.py voice`, am_michael) and the picture is a list of
approved clips (Pavo or licensed footage, each already through clip_check.py). Every scene change is a cut
(PROMPT_GUIDE "Built for 9.5"; vidIQ's fade/wipe flashed black); the only black is the fade-out on the last
second. Captions are burned large (about 7 % of the frame height) from the voice timeline; the owned music
(release FLAC, sha256 checked by the caller) is ducked under the voice and the mix is normalised near -14 LUFS.

usage: short_engine.py PLAN.json OUT.mp4
PLAN: {"voice": WAV, "timeline": timeline.json, "music": FLAC, "music_offset": s, "tail": s,
       "shots": [{"clip": MP4, "start": s, "end": s, "src_start": s, "speed": f?}, ...]}   shots tile [0, voice end + tail]
       ("speed", optional: the planned slow-down factor 1-MAX_SLOW of a clip cut into several shots; else computed;
        "talk", optional: {"start", "end"} of the line a talking clip carries - the Keeper or a character speaking -
        which must sit on that line at normal speed, from 0 s or the measured source onset in native_onsets;
        "hold", optional: seconds of the clip's last frame held after it, <= HOLD_MAX, E95)
The voice WAV holds every line in order, the spoken lines in their speakers' own voices; clips are muted (-an), so
a talking clip's lips meet its line in the mix only through that alignment.
"""
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

W, H, FPS = 1080, 1920, 30
MAX_SLOW = 1.3            # a clip may be slowed this much to fill its words, never looped
HOLD_MAX = 1.3            # a talking clip's last frame held at most this long (plan_check.TALK_HOLD_MAX, E95)
CAPTION_WORDS = 2         # words per caption card (large type fits two words on 1080 px)
FONT = "DejaVu Sans"
FONT_SIZE = 132           # line height about 7 % of 1920 (PROMPT_GUIDE: captions ~7 % of the frame height)
SCR_FONT = "DejaVu Serif"   # E249: KJV Scripture is set apart from our own captions: serif italic, gold, and cited
SCR_SIZE = 112
SCR_COLOUR = "&H0000D7FF"   # gold (ASS is BGR)
REF_SIZE = 66
REF_MARGIN_V = 880          # the citation sits above the (up to two-line) caption
MARGIN_V = 560            # above the Shorts UI at the bottom
MUSIC_DB = -22.0
FADE_OUT = 0.8


def run(args):
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"FFMPEG_FAILED {done.returncode}: {done.stderr.strip()[-600:]}")


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def check_shots(shots, total):
    """Shots must tile the whole Short with no gap or overlap, each at least 1 s."""
    problems, cursor = [], 0.0
    for i, s in enumerate(shots):
        if abs(s["start"] - cursor) > 1e-3:
            problems.append(f"SHOT_GAP_OR_OVERLAP {i} at {s['start']}")
        if s["end"] - s["start"] < 1.0:
            problems.append(f"SHOT_TOO_SHORT {i}")
        cursor = s["end"]
    if abs(cursor - total) > 0.05:
        problems.append(f"SHOTS_END_{round(cursor, 2)}_NOT_{round(total, 2)}")
    return problems


def talk_problems(shots, sentences, native_onsets=None):
    """A talking shot (the Keeper, a character speaking its line; `talk` = its line's span in the voice track) plays
    its clip from 0 s (Kokoro) or the exact measured source onset used in native_voice's premix, at normal speed,
    starting exactly on its line's first word and running past its last. The span must be on the voice track. A
    positive video offset without the native audio binding still fails; the synchronization rule is unchanged."""
    problems = []
    native_onsets = native_onsets or {}
    for i, s in enumerate(shots):
        t = s.get("talk")
        if not t:
            continue
        onset, src = native_onsets.get(s.get("shot"), 0.0), s.get("src_start", 0.0)
        aligned = (isinstance(onset, (int, float)) and math.isfinite(onset) and onset >= 0
                   and isinstance(src, (int, float)) and math.isfinite(src) and src == round(onset, 3))
        if (abs(s["start"] - t["start"]) > 1e-3 or not aligned or s.get("speed", 1.0) != 1.0
                or s["end"] + 1e-3 < t["end"]):
            problems.append(f"TALK_NOT_ALIGNED {i}")
        if (not any(abs(x["start"] - t["start"]) <= 0.05 for x in sentences)
                or not any(abs(x["end"] - t["end"]) <= 0.05 for x in sentences)):
            problems.append(f"TALK_NOT_ON_THE_VOICE {i}")
    return problems


def speed(shot, clip_seconds):
    """Playback factor (>= 1 slows the clip) so the clip fills its span from src_start; None when it cannot."""
    need = shot["end"] - shot["start"]
    have = clip_seconds - shot.get("src_start", 0.0)
    if have >= need:
        return 1.0
    factor = need / have if have > 0 else None
    return factor if factor is not None and factor <= MAX_SLOW else None


def explicit_speed(shot, clip_seconds):
    """A planned factor (episode_build cuts one clip into several shots): 1 <= factor <= MAX_SLOW and enough clip
    after src_start; None when it cannot."""
    factor = shot["speed"]
    need = shot["end"] - shot["start"]
    have = clip_seconds - shot.get("src_start", 0.0)
    hold = shot.get("hold", 0.0)
    if not 1.0 <= factor <= MAX_SLOW or not 0.0 <= hold <= HOLD_MAX or have * factor + hold + 0.02 < need:
        return None
    return factor


def hold_filter(shot):
    """A talking clip's last frame held for `hold` seconds (E95: Pavo keeps our audio only in a clip about 0.45 s
    longer than the speech, so the gap or the closing tail after it is a still frame)."""
    hold = shot.get("hold", 0.0)
    return f"tpad=stop_mode=clone:stop_duration={hold:.3f}," if hold > 0 else ""


def chunks(sentence):
    """Caption cards of up to CAPTION_WORDS words, timed by their share of the sentence's characters."""
    words = sentence["text"].split()
    groups = [words[i:i + CAPTION_WORDS] for i in range(0, len(words), CAPTION_WORDS)]
    total = sum(len(" ".join(g)) for g in groups) or 1
    t, out = sentence["start"], []
    for g in groups:
        span = (sentence["end"] - sentence["start"]) * len(" ".join(g)) / total
        out.append({"start": t, "end": t + span, "text": " ".join(g)})
        t += span
    return out


def ass_time(t):
    h, r = divmod(max(t, 0.0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def citation(reference):
    """'Genesis 7:9 (KJV)' -> 'Genesis 7:9 · KJV' (book chapter:verse and the version)."""
    ref = re.sub(r"\s*\(KJV\)\s*$", "", reference or "").strip()
    return f"{ref} · KJV" if ref else ""


def build_ass(sentences):
    head = ("[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nPlayResX: %d\nPlayResY: %d\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding\n"
            "Style: Cap,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,8,3,2,60,60,%d,1\n"
            "Style: Scr,%s,%d,%s,%s,&H00000000,&H64000000,1,1,0,0,100,100,0,0,1,8,3,2,60,60,%d,1\n"
            "Style: Ref,%s,%d,%s,%s,&H00000000,&H64000000,1,0,0,0,100,100,2,0,1,6,2,2,60,60,%d,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            % (W, H, FONT, FONT_SIZE, MARGIN_V, SCR_FONT, SCR_SIZE, SCR_COLOUR, SCR_COLOUR, MARGIN_V,
               FONT, REF_SIZE, SCR_COLOUR, SCR_COLOUR, REF_MARGIN_V))
    lines = []
    for s in sentences:
        scripture = s.get("kind") == "scripture" and bool(citation(s.get("reference")))
        for c in chunks(s):
            text = re.sub(r"[{}\\]", "", c["text"])
            style = "Scr" if scripture else "Cap"
            lines.append(f"Dialogue: 0,{ass_time(c['start'])},{ass_time(c['end'])},{style},,0,0,0,,{text}")
        if scripture:   # the citation stays up for the whole quotation
            lines.append(f"Dialogue: 1,{ass_time(s['start'])},{ass_time(s['end'])},Ref,,0,0,0,,{citation(s['reference'])}")
    return head + "\n".join(lines) + "\n"


def main(plan_path, out):
    plan = json.loads(Path(plan_path).read_text())
    timeline = json.loads(Path(plan["timeline"]).read_text())
    total = round(timeline["voice_seconds"] + plan.get("tail", 1.2), 3)
    shots = plan["shots"]
    problems = check_shots(shots, total) + talk_problems(shots, timeline["sentences"], plan.get("native_onsets"))
    if problems:
        raise SystemExit("PLAN_REFUSED " + "; ".join(problems))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        for i, s in enumerate(shots):
            clip_seconds = duration(s["clip"])
            factor = explicit_speed(s, clip_seconds) if "speed" in s else speed(s, clip_seconds)
            if factor is None:
                raise SystemExit(f"CLIP_TOO_SHORT shot {i} {s['clip']}")
            need = s["end"] - s["start"]
            part = tmp / f"p{i:02d}.mp4"
            run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(s.get("src_start", 0.0)), "-i", s["clip"], "-an",
                 "-vf", f"setpts={factor:.4f}*PTS,{hold_filter(s)}scale={W}:{H}:flags=lanczos:"
                        "force_original_aspect_ratio=increase,"
                        f"crop={W}:{H},fps={FPS},format=yuv420p",
                 "-t", f"{need:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "17", str(part)])
            parts.append(part)
        (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-c", "copy", str(tmp / "picture.mp4")])
        (tmp / "captions.ass").write_text(build_ass(timeline["sentences"]))
        fade_at = total - FADE_OUT
        audio = (f"[1:a]aresample=48000,apad=whole_dur={total},asplit=2[v][vk];"
                 f"[2:a]aresample=48000,atrim=start={plan.get('music_offset', 0.0)}:duration={total},asetpts=PTS-STARTPTS,"
                 f"volume={MUSIC_DB}dB[m];[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md];"
                 f"[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,"
                 f"afade=t=out:st={fade_at}:d={FADE_OUT},aformat=sample_rates=48000:channel_layouts=stereo[a]")
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(tmp / "picture.mp4"), "-i", plan["voice"],
             "-i", plan["music"], "-filter_complex",
             f"[0:v]subtitles={tmp / 'captions.ass'},fade=t=out:st={fade_at}:d={FADE_OUT}[pv];{audio}",
             "-map", "[pv]", "-map", "[a]", "-t", str(total), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print(json.dumps({"out": out, "seconds": total, "shots": len(shots), "fade_out_at": round(fade_at, 2)}))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
