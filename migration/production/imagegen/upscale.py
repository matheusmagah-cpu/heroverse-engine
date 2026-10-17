#!/usr/bin/env python3
"""2x super-resolution of generated images on CPU (Real-ESRGAN general x4v3, the
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

TILE, PAD = 256, 12
TARGET = 2


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
        out = np.zeros((h * scale, w * scale, 3), dtype=np.float32)
        with torch.inference_mode():
            for y in range(0, h, TILE):
                for x in range(0, w, TILE):
                    y0, x0 = max(0, y - PAD), max(0, x - PAD)
                    y1, x1 = min(h, y + TILE + PAD), min(w, x + TILE + PAD)
                    t = torch.from_numpy(img[y0:y1, x0:x1].transpose(2, 0, 1)).unsqueeze(0)
                    r = model(t).squeeze(0).clamp(0, 1).numpy().transpose(1, 2, 0)
                    oy, ox = (y - y0) * scale, (x - x0) * scale
                    th, tw = min(TILE, h - y) * scale, min(TILE, w - x) * scale
                    out[y * scale:y * scale + th, x * scale:x * scale + tw] = r[oy:oy + th, ox:ox + tw]
        result = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
        if scale != TARGET:
            result = result.resize((w * TARGET, h * TARGET), Image.LANCZOS)
        result.save(path)
        meta = Path(path).with_suffix(".json")
        if meta.exists():
            m = json.loads(meta.read_text())
            m["size"] = [w * TARGET, h * TARGET]
            m["upscaler"] = {"model": "Real-ESRGAN general x4v3 (downsampled to 2x)", "licence": "bsd-3-clause",
                             "weights_sha256": wsha,
                             "source": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"}
            meta.write_text(json.dumps(m, indent=1) + "\n")
        print(Path(path).name, (w, h), "->", (w * TARGET, h * TARGET), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
