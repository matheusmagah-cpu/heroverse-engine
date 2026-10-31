#!/usr/bin/env python3
"""Image generation on Cloudflare Workers AI (free daily allocation; the free
Workers plan fails instead of billing when the allocation is used up).

Engines (commercial use allowed by the model licence):
  flux  -> @cf/black-forest-labs/flux-1-schnell   (Apache-2.0; square output, steps <= 8)
  sdxl  -> @cf/bytedance/stable-diffusion-xl-lightning (Open RAIL++-M base; width/height)
Credentials only from CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID (GitHub secrets).
Writes <id>.png + <id>.json (prompt, seed, engine, model, licence) like gen_images.py.
usage: cf_images.py PROMPTS_JSON OUT_DIR [ENGINE]
"""
import base64
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ENGINES = {
    "flux": {"model": "@cf/black-forest-labs/flux-1-schnell", "license": "apache-2.0",
             "licence_source": "https://huggingface.co/black-forest-labs/FLUX.1-schnell"},
    "sdxl": {"model": "@cf/bytedance/stable-diffusion-xl-lightning", "license": "openrail++",
             "licence_source": "https://huggingface.co/ByteDance/SDXL-Lightning"},
}


def account_id():
    """CLOUDFLARE_ACCOUNT_ID, or the token's only account when that secret is not set."""
    if os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        return os.environ["CLOUDFLARE_ACCOUNT_ID"]
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/accounts",
                                 headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        accounts = json.loads(r.read()).get("result") or []
    if len(accounts) != 1:
        raise SystemExit(f"CF_ACCOUNT_ID_UNRESOLVED ({len(accounts)} accounts visible to the token; set CLOUDFLARE_ACCOUNT_ID)")
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = accounts[0]["id"]
    return accounts[0]["id"]


def run(model, payload):
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id()}/ai/run/{model}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
                                          "Content-Type": "application/json"})
    # E214: this POST creates a result, not a read. A lost/5xx acknowledgement may follow a completed generation.
    # Never retry it here; the existing guarded workflow must reconcile its request/run before any new attempt.
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body, ctype = r.read(), r.headers.get("Content-Type", "")
        if ctype.startswith("image/"):
            return body
        data = json.loads(body)
        result = data.get("result") if isinstance(data, dict) else None
        image = result.get("image") if isinstance(result, dict) else None
        if not isinstance(image, str) or not image:
            raise ValueError("no image in acknowledgement")
        return base64.b64decode(image, validate=True)
    except urllib.error.HTTPError as e:
        code = e.code
        msg = e.read(300).decode(errors="replace")
        e.close()
        if code == 429 or "limit" in msg.lower() or "used up your daily free allocation" in msg.lower():
            raise SystemExit("CF_DAILY_ALLOCATION_EXHAUSTED HTTP_%s" % code) from None
        # Provider response bodies are not public evidence; do not put account/credential echoes in Actions logs.
        raise RuntimeError("CF_GENERATION_OUTCOME_UNCERTAIN_NO_REPLAY HTTP_%s" % code) from None
    except (TimeoutError, OSError, ValueError, TypeError):
        raise RuntimeError("CF_GENERATION_OUTCOME_UNCERTAIN_NO_REPLAY") from None


def main(prompts_path, out_dir, engine="flux"):
    from PIL import Image
    spec = json.loads(Path(prompts_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    eng = ENGINES[engine]
    only = {x for x in os.environ.get("ONLY", "").split(",") if x}
    for item in spec["images"]:
        if only and item["id"] not in only:
            continue
        prompt = item["prompt"] + ", " + spec["style"]
        if engine == "flux":  # Workers AI flux-1-schnell accepts only prompt and steps (no seed: the saved PNG is the record)
            payload = {"prompt": prompt[:2048], "steps": 8}
        else:
            payload = {"prompt": prompt[:2000], "seed": item["seed"], "width": spec["width"], "height": spec["height"],
                       "negative_prompt": spec["negative"], "num_steps": 8}
        t0 = time.time()
        try:
            raw = run(eng["model"], payload)
        except SystemExit as e:
            if not str(e).startswith("CF_DAILY_ALLOCATION_EXHAUSTED"):
                raise
            # E62: the images made before the allocation ran out are kept (saved by the workflow); the rest wait for
            # the next nightly slot. A used-up free allocation is a deferral, not a failure.
            print("CF_ALLOCATION_EXHAUSTED_DEFERRED", str(e)[:200], flush=True)
            return "DEFERRED"
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        image.save(out / f"{item['id']}.png")
        (out / f"{item['id']}.json").write_text(json.dumps({
            "id": item["id"], "prompt": prompt, "negative": spec.get("negative") if engine != "flux" else None,
            "seed": item["seed"] if engine != "flux" else None,
            "size": list(image.size), "engine": f"cloudflare-workers-ai:{eng['model']}",
            "models": {eng["model"]: {"license": eng["license"], "revision": "workers-ai-managed", "source": eng["licence_source"]}},
            "seconds": round(time.time() - t0, 1), "generated_by": "HeroVerse pipeline (AI-generated image)"}, indent=1) + "\n")
        print(item["id"], image.size, round(time.time() - t0, 1), flush=True)
    return "DONE"


if __name__ == "__main__":
    main(*sys.argv[1:4])
