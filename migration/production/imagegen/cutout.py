#!/usr/bin/env python3
"""Cut the chosen figure out of its generated image (rembg, ISNet general-use
model, MIT/Apache-2.0), feather the matte edge, trim to the subject and write
an RGBA PNG plus a JSON record (source image hash, its generation record,
cut-out model). usage: cutout.py IMAGE_PNG IMAGE_JSON OUT_PNG"""
import hashlib
import json
from pathlib import Path
import sys

MODEL = "isnet-general-use"


def main(image_path, meta_path, out_path):
    from PIL import Image, ImageFilter
    from rembg import new_session, remove
    image = Image.open(image_path).convert("RGB")
    cut = remove(image, session=new_session(MODEL), post_process_mask=True)
    alpha = cut.getchannel("A").filter(ImageFilter.GaussianBlur(1.2))
    cut.putalpha(alpha)
    box = alpha.point(lambda a: 255 if a > 24 else 0).getbbox()
    cut = cut.crop(box)
    cut.save(out_path)
    coverage = sum(1 for a in cut.getchannel("A").getdata() if a > 128) / (cut.width * cut.height)
    record = json.loads(Path(meta_path).read_text())
    record.update({"cutout_model": MODEL, "cutout_tool": "rembg",
                   "source_png_sha256": hashlib.sha256(Path(image_path).read_bytes()).hexdigest(),
                   "cutout_box": list(box), "cutout_size": [cut.width, cut.height],
                   "opaque_fraction_of_box": round(coverage, 3)})
    Path(out_path).with_suffix(".json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps({"size": [cut.width, cut.height], "opaque_fraction": round(coverage, 3)}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
