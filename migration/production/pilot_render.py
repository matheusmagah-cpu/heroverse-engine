#!/usr/bin/env python3
"""Pilot renderer (F5) built on preserved, rights-recorded inputs.

  pilot_render.py voice    WORK SCRIPT            (voice venv: original voice_phase5 adapter)

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
SENTENCE_GAP_V4 = 0.30  # E53: 0.45 s put pilot-010 at speech presence 0.844 < 0.85 (QA v4)
MUSIC_OFFSET = 1200.0
SOURCE_SHA256 = "fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
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
    # v4 (footage) narration breathes between sentences: the measured winners pause ~1-2 s between lines
    # (evidence/vidiq/20261023/hook_audit.md); 0.45 s keeps the QA words-per-minute band (115-165)
    gap = SENTENCE_GAP_V4 if script.get("footage") else SENTENCE_GAP
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
            pieces.append(np.zeros(int(gap * rate), dtype=np.float32))
            cursor += len(samples) / rate + gap
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


if __name__ == "__main__":
    command, work = sys.argv[1], Path(sys.argv[2]).resolve()
    if command == "prepare":
        prepare(work, sys.argv[3])
    elif command == "voice":
        voice(work, sys.argv[3])
    else:
        raise SystemExit(__doc__)
