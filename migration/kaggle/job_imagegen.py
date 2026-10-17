# Kaggle GPU job: SDXL base 1.0 + LCM-LoRA, fp16 on CUDA. PAYLOAD is prepended
# by kaggle_run.py (images.json of a pilot plus an optional id filter).
import json
import subprocess
import sys
import time
from pathlib import Path

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "diffusers==0.31.0", "transformers==4.46.3",
                "peft==0.13.2", "accelerate==1.1.1", "huggingface_hub==0.26.2"], check=True)
import torch  # noqa: E402
from diffusers import DiffusionPipeline, LCMScheduler  # noqa: E402
from huggingface_hub import model_info  # noqa: E402

BASE, LORA = "stabilityai/stable-diffusion-xl-base-1.0", "latent-consistency/lcm-lora-sdxl"
ALLOWED = {"openrail++", "openrail++-m", "creativeml-openrail-m", "apache-2.0", "mit"}
spec = json.loads(PAYLOAD)  # noqa: F821
only = set(spec.get("only") or [])
out = Path("/kaggle/working/img")
out.mkdir(parents=True, exist_ok=True)
record = {}
for repo in (BASE, LORA):
    info = model_info(repo)
    lic = (info.card_data or {}).get("license") if info.card_data else None
    if str(lic).lower() not in ALLOWED:
        raise SystemExit(f"LICENCE_NOT_ALLOWED {repo} {lic}")
    record[repo] = {"revision": info.sha, "license": lic}
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32
pipe = DiffusionPipeline.from_pretrained(BASE, revision=record[BASE]["revision"], torch_dtype=dtype,
                                         use_safetensors=True, variant="fp16").to(device)
pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
pipe.load_lora_weights(LORA, revision=record[LORA]["revision"])
pipe.set_progress_bar_config(disable=True)
for item in spec["images"]:
    if only and item["id"] not in only:
        continue
    t0 = time.time()
    image = pipe(prompt=item["prompt"] + ", " + spec["style"], negative_prompt=spec["negative"],
                 num_inference_steps=spec["steps"], guidance_scale=spec["guidance"],
                 width=spec["width"], height=spec["height"],
                 generator=torch.Generator(device).manual_seed(item["seed"])).images[0]
    image.save(out / f"{item['id']}.png")
    (out / f"{item['id']}.json").write_text(json.dumps({
        "id": item["id"], "prompt": item["prompt"] + ", " + spec["style"], "negative": spec["negative"],
        "seed": item["seed"], "steps": spec["steps"], "guidance": spec["guidance"],
        "size": [spec["width"], spec["height"]], "models": record, "device": device,
        "seconds": round(time.time() - t0, 1), "generated_by": "HeroVerse pipeline (AI-generated image)"}, indent=1))
    print(item["id"], device, round(time.time() - t0, 1), flush=True)
