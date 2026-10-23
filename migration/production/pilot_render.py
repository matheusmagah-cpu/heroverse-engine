#!/usr/bin/env python3
"""Pilot renderer (F5) built on preserved, rights-recorded inputs.

  pilot_render.py voice    WORK SCRIPT            (voice venv: original voice_phase5 adapter)
  pilot_render.py assemble WORK SCRIPT CATALOG MUSIC CLIP...   (ffmpeg)

Voice: original hero_engine.voice_phase5 Kokoro adapter, preserved hash-pinned
model, voice am_michael, sentence by sentence. Music: the owned instrumental
generator output (release FLAC), ducked under the voice. Picture: Creative
Commons clips (picture only), cut into 1.6-2.6 s shots with no source second
used twice, chosen by theme per script segment. Every input is recorded with
its hash in manifest.json. No upload, no publication.
"""
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys

RATE_OUT = 48000
LEAD_IN = 0.3
TAIL = 3.0
SENTENCE_GAP = 0.18
SHOT_RANGE = (1.6, 2.6)
MUSIC_OFFSET = 1200.0
SOURCE_SHA256 = "fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
THEMES = {"sunrise": "sunrise", "mountain": "sunrise", "morning light forest": "forest", "clouds": "sky",
          "ocean": "water", "river": "water", "flower": "flower", "candle": "candle"}
SEGMENT_THEMES = {"hook": ["sunrise"], "invitation": ["sunrise", "sky"], "scripture": ["sky", "sunrise"],
                  "reflection": ["forest", "water", "sky"], "stillness": ["candle", "water"],
                  "transition": ["candle", "forest"], "prayer": ["forest", "water", "flower", "candle"],
                  "declaration": ["sunrise", "sky"], "payoff": ["flower", "forest"],
                  "blessing": ["sky", "sunrise"], "cta": ["sunrise", "flower"]}
REFERENCES = {"scripture-1": "Deuteronomy 31:8 (KJV)", "scripture-2": "Lamentations 3:22-23 (KJV)",
              "scripture-3": "Psalm 143:8 (KJV)", "scripture-4": "Isaiah 41:10 (KJV)",
              "scripture-5": "Proverbs 3:5-6 (KJV)"}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(args):
    subprocess.run(args, check=True, capture_output=True)


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def escape(text):
    """drawtext text escaping: backslash, colon and single quote are special."""
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?:;])\s+", text) if s.strip()]


# KJV prints divine names in capitals ("the Lord GOD"); the voice spelled "GOD" letter by letter (pilot-008, 17:36,
# review 2026-10-20, E47). Only the text sent to the voice is changed: captions, script and timeline keep the KJV form.
DIVINE_CAPS = re.compile(r"\b(LORD|GOD|JEHOVAH|JESUS|CHRIST)\b")


def speech_text(sentence):
    return DIVINE_CAPS.sub(lambda m: m.group(1).capitalize(), sentence)


def prepare(work, archive):
    """Extract the hash-verified source archive (manifest-checked, no unsafe
    members) and fetch the hash-pinned public Kokoro assets, exactly as the
    qualified cloud voice diagnostic does."""
    import urllib.request
    import zipfile
    from pathlib import PurePosixPath
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from verify_public_voice_asset import ASSETS
    if sha256(archive) != SOURCE_SHA256:
        raise RuntimeError("SOURCE_ARCHIVE_IDENTITY_MISMATCH")
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            member = PurePosixPath(item.filename)
            if member.is_absolute() or ".." in member.parts or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise RuntimeError("UNSAFE_SOURCE_MEMBER")
        bundle.extractall(work / "source")
    report = json.loads((work / "source" / "SOURCE_TRANSFER_REPORT.json").read_text())
    for item in report["files"]:
        path = work / "source" / "project" / item["path"]
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise RuntimeError("SOURCE_MANIFEST_MISMATCH")
    models = work / "models" / "kokoro"
    models.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS:
        target = models / asset["name"]
        with urllib.request.urlopen(asset["url"], timeout=60) as response, target.open("wb") as out:
            for block in iter(lambda: response.read(1 << 20), b""):
                out.write(block)
        if target.stat().st_size != asset["size"] or sha256(target) != asset["sha256"]:
            raise RuntimeError("VOICE_ASSET_IDENTITY_MISMATCH")
    print(json.dumps({"source": "VERIFIED", "voice_assets": [a["sha256"] for a in ASSETS]}))


def voice(work, script_path):
    """Synthesize every sentence with the original adapter and lay out the
    narration timeline with the script's pauses. Writes voice.wav and timeline.json."""
    import numpy as np
    import onnxruntime as ort
    import soundfile as sf
    sys.path.insert(0, str(work / "source" / "project"))
    from hero_engine.voice_phase5 import build_local_voice, synthesize_voice_sample, KokoroFloatSpeed
    script = json.loads(Path(script_path).read_text())
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2

    def factory(model, voices, *, espeak_config):
        session = ort.InferenceSession(model, sess_options=options, providers=["CPUExecutionProvider"])
        return KokoroFloatSpeed.from_session(session, voices, espeak_config=espeak_config)
    engine = build_local_voice(work, engine_factory=factory)
    cfg = script["voice"]
    pieces, timeline, cursor, rate = [], [], LEAD_IN, None
    pieces.append(None)  # placeholder for lead-in silence
    spoken = []
    for segment in script["segments"]:
        start = cursor
        for index, sentence in enumerate(sentences(segment["text"])):
            path = work / "voice" / f"{segment['id']}-{index:02d}.wav"
            for attempt in range(3):  # the adapter occasionally returns empty audio; the same sentence then succeeds
                try:
                    receipt = synthesize_voice_sample(engine, text=speech_text(sentence), output_path=path,
                                                      voice_id=cfg["voice_id"], speed=cfg["speed"])
                    break
                except RuntimeError as e:
                    if "empty audio" not in str(e) or attempt == 2:
                        raise RuntimeError(f"VOICE_FAILED {segment['id']}-{index:02d}: {e}") from e
                    print(f"VOICE_RETRY {segment['id']}-{index:02d}", file=sys.stderr)
            if receipt["clipping"]:
                raise RuntimeError("VOICE_CLIPPING " + segment["id"])
            samples, rate = sf.read(path, dtype="float32")
            pieces.append(samples)
            spoken.append({"segment": segment["id"], "text": sentence, "start": round(cursor, 3),
                           "end": round(cursor + len(samples) / rate, 3)})
            pieces.append(np.zeros(int(SENTENCE_GAP * rate), dtype=np.float32))
            cursor += len(samples) / rate + SENTENCE_GAP
        timeline.append({"id": segment["id"], "start": round(start, 3), "end": round(cursor, 3)})
        pieces.append(np.zeros(int(segment["pause_after"] * rate), dtype=np.float32))
        cursor += segment["pause_after"]
    pieces[0] = np.zeros(int(LEAD_IN * rate), dtype=np.float32)
    narration = np.concatenate(pieces)
    sf.write(work / "voice.wav", narration, rate, subtype="PCM_16")
    total = len(narration) / rate
    (work / "timeline.json").write_text(json.dumps({"segments": timeline, "sentences": spoken, "voice_seconds": round(total, 3),
                                                   "sample_rate": rate, "voice_id": cfg["voice_id"],
                                                   "speed": cfg["speed"]}, indent=1))
    print(json.dumps({"voice_seconds": round(total, 2), "segments": len(timeline)}))


def theme_of(clip):
    query = clip["query"]
    return next((t for key, t in THEMES.items() if key in query), "sky")


def shot_plan(timeline, clips, total, seed=17):
    """Assign shots to the narration timeline: themed per segment, durations in
    SHOT_RANGE, never the same clip twice in a row, each source second once."""
    rng = random.Random(seed)
    cursor = {c["file"]: 0.0 for c in clips}
    by_theme = {}
    for c in clips:
        by_theme.setdefault(c["theme"], []).append(c)
    plan, t, last = [], 0.0, None

    def segment_at(time):
        for s in timeline:
            if s["start"] <= time < s["end"]:
                return s["id"]
        return "prayer"
    while t < total - 0.01:
        seg = segment_at(t)
        kind = next((k for k in SEGMENT_THEMES if seg.startswith(k)), "prayer")
        duration = min(round(rng.uniform(*SHOT_RANGE), 2), round(total - t, 2))
        options = [c for theme in SEGMENT_THEMES[kind] for c in by_theme.get(theme, [])]
        options = [c for c in options if c["file"] != last and cursor[c["file"]] + duration <= c["duration"] - 0.2]
        if not options:
            options = [c for c in clips if c["file"] != last and cursor[c["file"]] + duration <= c["duration"] - 0.2]
        if not options:
            raise RuntimeError("FOOTAGE_EXHAUSTED_AT_%.1f" % t)
        clip = rng.choice(options)
        plan.append({"file": clip["file"], "video_id": clip["video_id"], "source_start": round(cursor[clip["file"]], 3),
                     "duration": duration, "timeline_start": round(t, 3), "segment": seg})
        cursor[clip["file"]] += duration
        t += duration
        last = clip["file"]
    return plan


def assemble(work, script_path, catalog_path, music_path, clip_paths):
    script = json.loads(Path(script_path).read_text())
    timeline = json.loads((work / "timeline.json").read_text())
    catalog = {c["video_id"]: c for c in json.loads(Path(catalog_path).read_text())["catalog"]}
    clips = []
    for path in clip_paths:
        name = Path(path).name
        video_id = re.match(r"native-(.{11})-\d+-\d+s-sha256-", name).group(1)
        entry = catalog[video_id]
        clips.append({"file": str(path), "video_id": video_id, "duration": probe_duration(path),
                      "theme": theme_of(entry), "sha256": sha256(path), "attribution": entry["attribution"],
                      "license": entry["license"]})
    total = timeline["voice_seconds"] + TAIL
    # Audio: voice forward, owned music ducked under it, loudness to -15 LUFS / -1.5 dBTP.
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
    # Picture: themed CC shots, picture only.
    plan = shot_plan(timeline["segments"], clips, total)
    shots = work / "shots"
    shots.mkdir(exist_ok=True)
    listing = []
    for index, shot in enumerate(plan):
        out = shots / f"{index:04d}.mp4"
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(shot["source_start"]), "-t", str(shot["duration"]),
             "-i", shot["file"], "-an", "-vf",
             "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,"
             "eq=saturation=0.95:brightness=0.02,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", "30", str(out)])
        listing.append(f"file '{out}'")
    (work / "shots.txt").write_text("\n".join(listing) + "\n")
    texts = [("God has already gone ahead of you.", 0.3, 5.0)]
    for seg in timeline["segments"]:
        if seg["id"] in REFERENCES:
            texts.append((REFERENCES[seg["id"]], seg["start"] + 0.5, seg["end"]))
    draw = ",".join(
        f"drawtext=fontfile={FONT}:text='{escape(t)}':fontcolor=white:fontsize=46:borderw=3:bordercolor=black@0.6:"
        f"x=(w-text_w)/2:y=h-170:enable='between(t,{a:.2f},{b:.2f})'" for t, a, b in texts)
    final = work / "pilot.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "shots.txt"),
         "-i", str(mix), "-map", "0:v:0", "-map", "1:a:0", "-vf", draw + ",format=yuv420p",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-g", "60",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(RATE_OUT), "-t", str(total), "-movflags", "+faststart", str(final)])
    used = {c["video_id"]: c for c in clips if any(s["video_id"] == c["video_id"] for s in plan)}
    manifest = {"version": "pilot-manifest-v1", "pilot_id": script["pilot_id"], "output_sha256": sha256(final),
                "output_seconds": probe_duration(final), "script_sha256": sha256(script_path),
                "voice": {"engine": script["voice"]["engine"], "voice_id": timeline["voice_id"],
                          "speed": timeline["speed"], "voice_wav_sha256": sha256(work / "voice.wav")},
                "music": {"file": Path(music_path).name, "sha256": sha256(music_path), "offset_seconds": MUSIC_OFFSET,
                          "rights": "Owned instrumental generator output (HeroVerse instrumental-v2 recipe)"},
                "clips": [{"video_id": c["video_id"], "sha256": c["sha256"], "license": c["license"],
                           "attribution": c["attribution"], "picture_only": True} for c in used.values()],
                "shots": plan, "on_screen_text": [t for t, _, _ in texts], "timeline": timeline["segments"],
                "upload_performed": False, "publication_performed": False}
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({"seconds": manifest["output_seconds"], "shots": len(plan), "clips_used": len(used)}))


if __name__ == "__main__":
    command, work = sys.argv[1], Path(sys.argv[2]).resolve()
    if command == "prepare":
        prepare(work, sys.argv[3])
    elif command == "voice":
        voice(work, sys.argv[3])
    elif command == "assemble":
        assemble(work, sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:])
    else:
        raise SystemExit(__doc__)
