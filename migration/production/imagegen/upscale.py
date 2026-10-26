#!/usr/bin/env python3
"""Super-resolution of generated images on CPU (4x by default, UPSCALE_TARGET to change) (Real-ESRGAN general x4v3, the
compact SRVGG model, BSD-3-Clause, loaded through spandrel, MIT; its 4x output is
downsampled to 2x with Lanczos, which also supersamples away upscaling grain). A 1024x1024 FLUX image becomes 2048x2048, which
crops to a full 2048x1152 frame for 16:9 and 1152x2048 for vertical Shorts.
Processed in overlapping tiles so memory stays small. The metadata JSON of each
image records the upscaler and its weight hash; the PNG is replaced in place.
usage: upscale.py WEIGHTS.pth IMAGE.png [IMAGE.png ...]
"""
import hashlib
import json
from pathlib import Path
import sys

import os

TILE, PAD = 256, 12
# FLUX 1024 px -> 4096 px (4x, the model's native scale): a 16:9 crop of 4096x2304 covers 2560x1440 (owner,
# 2026-10-23: never below 1440p). UPSCALE_TARGET=2 re-processes an existing 2048 px image into 4096 px.
TARGET = int(os.environ.get("UPSCALE_TARGET", "4"))


WEIGHTS_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"
WEIGHTS_SHA256 = "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292"   # = images-upres.yml


def sr(model, img, scale, tile=TILE, pad=PAD):
    """The model over an HxWx3 float32 image in overlapping tiles; returns the (h*scale)x(w*scale)x3 float32 result.
    Shared with footage/pavo_footage.py (every frame of a Pavo clip)."""
    import numpy as np
    import torch
    h, w, _ = img.shape
    out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
    with torch.inference_mode():
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y0, x0 = max(0, y - pad), max(0, x - pad)
                y1, x1 = min(h, y + tile + pad), min(w, x + tile + pad)
                t = torch.from_numpy(np.ascontiguousarray(img[y0:y1, x0:x1].transpose(2, 0, 1))).unsqueeze(0)
                r = model(t).squeeze(0).clamp(0, 1).numpy().transpose(1, 2, 0)
                oy, ox = (y - y0) * scale, (x - x0) * scale
                th, tw = min(tile, h - y) * scale, min(tile, w - x) * scale
                out[y * scale:y * scale + th, x * scale:x * scale + tw] = r[oy:oy + th, ox:ox + tw]
    return out


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(weights, images):
    import numpy as np
    import torch
    from PIL import Image
    from spandrel import ModelLoader
    torch.set_num_threads(4)
    model = ModelLoader().load_from_file(weights).eval()
    scale = model.scale
    wsha = sha256(weights)
    for path in images:
        img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255
        h, w, _ = img.shape
        out = sr(model, img, scale)
        result = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
        if scale != TARGET:
            result = result.resize((w * TARGET, h * TARGET), Image.LANCZOS)
        result.save(path)
        meta = Path(path).with_suffix(".json")
        if meta.exists():
            m = json.loads(meta.read_text())
            m["size"] = [w * TARGET, h * TARGET]
            m["upscaler"] = {"model": f"Real-ESRGAN general x4v3 (output {TARGET}x of a {w} px input)", "licence": "bsd-3-clause",
                             "weights_sha256": wsha,
                             "source": WEIGHTS_URL}
            meta.write_text(json.dumps(m, indent=1) + "\n")
        print(Path(path).name, (w, h), "->", (w * TARGET, h * TARGET), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
