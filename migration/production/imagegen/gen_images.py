#!/usr/bin/env python3
"""Generate still images for a pilot with an open-weight model on CPU.

Model: stabilityai/stable-diffusion-xl-base-1.0 (CreativeML Open RAIL++-M,
commercial use permitted under its use restrictions) accelerated with
latent-consistency/lcm-lora-sdxl. The resolved model revisions and the
licence fields reported by the Hub are written next to every image so the
rights record is evidence, not memory. Seeds are fixed per prompt.
usage: gen_images.py PROMPTS_JSON OUT_DIR SHARD SHARDS
"""
import json
from pathlib import Path
import sys
import time

BASE = "stabilityai/stable-diffusion-xl-base-1.0"
LORA = "latent-consistency/lcm-lora-sdxl"
ALLOWED_LICENCES = {"openrail++", "openrail++-m", "creativeml-openrail-m", "apache-2.0", "mit"}


def rights():
    from huggingface_hub import model_info
    record = {}
    for repo in (BASE, LORA):
        info = model_info(repo)
        licence = (info.card_data or {}).get("license") if info.card_data else None
        record[repo] = {"revision": info.sha, "license": licence}
        if str(licence).lower() not in ALLOWED_LICENCES:
            raise SystemExit(f"LICENCE_NOT_ALLOWED {repo} {licence}")
    return record


def main(prompts_path, out_dir, shard, shards):
    import torch
    from diffusers import DiffusionPipeline, LCMScheduler
    spec = json.loads(Path(prompts_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    record = rights()
    torch.set_num_threads(4)
    pipe = DiffusionPipeline.from_pretrained(BASE, revision=record[BASE]["revision"], torch_dtype=torch.float32,
                                             use_safetensors=True, variant="fp16")
    pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    pipe.load_lora_weights(LORA, revision=record[LORA]["revision"])
    pipe.set_progress_bar_config(disable=True)
    style, negative = spec["style"], spec["negative"]
    items = [p for i, p in enumerate(spec["images"]) if i % int(shards) == int(shard)]
    for item in items:
        t0 = time.time()
        image = pipe(prompt=item["prompt"] + ", " + style, negative_prompt=negative,
                     num_inference_steps=spec["steps"], guidance_scale=spec["guidance"],
                     width=spec["width"], height=spec["height"],
                     generator=torch.Generator().manual_seed(item["seed"])).images[0]
        image.save(out / f"{item['id']}.png")
        meta = {"id": item["id"], "prompt": item["prompt"] + ", " + style, "negative": negative,
                "seed": item["seed"], "steps": spec["steps"], "guidance": spec["guidance"],
                "size": [spec["width"], spec["height"]], "models": record,
                "seconds": round(time.time() - t0, 1), "generated_by": "HeroVerse pipeline (AI-generated image)"}
        (out / f"{item['id']}.json").write_text(json.dumps(meta, indent=1) + "\n")
        print(item["id"], meta["seconds"], flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:5])
