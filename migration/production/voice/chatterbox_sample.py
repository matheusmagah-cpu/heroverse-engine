#!/usr/bin/env python3
"""A/B voice sample (owner, 2026-10-23: "the voice must be perfect"): the opening of a pilot narrated by Chatterbox
(Resemble AI, MIT licence, emotion control) cloned from our own Kokoro narration, next to the Kokoro original.
Measures CPU time per second of audio so a 16-minute render can be judged feasible. Nothing here publishes.

usage: chatterbox_sample.py SCRIPT_JSON REFERENCE_WAV OUT_DIR [SEGMENTS]
"""
import json
from pathlib import Path
import re
import sys
import time


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?:;])\s+", text) if s.strip()]


def main(script_path, reference, out_dir, n_segments="4"):
    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.tts import ChatterboxTTS
    torch.set_num_threads(max(1, torch.get_num_threads()))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(script_path).read_text())
    text = [s for seg in script["segments"][:int(n_segments)] for s in sentences(seg["text"])]
    t0 = time.time()
    model = ChatterboxTTS.from_pretrained(device="cpu")
    load_s = time.time() - t0
    results = {}
    for name, exaggeration, cfg in (("calm", 0.4, 0.5), ("warm", 0.6, 0.35)):
        pieces, t1 = [], time.time()
        for s in text:
            wav = model.generate(s, audio_prompt_path=reference, exaggeration=exaggeration, cfg_weight=cfg)
            pieces += [wav.squeeze(0).numpy(), np.zeros(int(0.3 * model.sr), dtype=np.float32)]
        audio = np.concatenate(pieces)
        sf.write(out / f"chatterbox-{name}.wav", audio, model.sr)
        seconds = len(audio) / model.sr
        results[name] = {"exaggeration": exaggeration, "cfg_weight": cfg, "audio_s": round(seconds, 1),
                         "cpu_s": round(time.time() - t1, 1), "cpu_per_audio_s": round((time.time() - t1) / seconds, 2)}
    report = {"model": "ResembleAI/chatterbox (MIT)", "load_s": round(load_s, 1), "sentences": len(text), **results}
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main(*sys.argv[1:5])
