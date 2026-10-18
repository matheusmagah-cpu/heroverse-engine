#!/usr/bin/env python3
"""Copy the image records a pilot reuses (images.json "reused": {source_pilot: [ids]}) into its own images/ folder,
which is where the render and render_queue read them. Idempotent; fails if a source record is missing.
usage: hydrate_reused.py PILOT_DIR
"""
import json
from pathlib import Path
import shutil
import sys


def hydrate(pilot_dir):
    d = Path(pilot_dir)
    spec = json.loads((d / "images.json").read_text())
    (d / "images").mkdir(exist_ok=True)
    copied, missing = [], []
    for source, ids in (spec.get("reused") or {}).items():
        for i in ids:
            src, dst = d.parent / source / "images" / f"{i}.json", d / "images" / f"{i}.json"
            if dst.exists():
                continue
            if not src.exists():
                missing.append(f"{source}/{i}")
                continue
            shutil.copyfile(src, dst)
            copied.append(i)
    return copied, missing


if __name__ == "__main__":
    c, m = hydrate(sys.argv[1])
    print(json.dumps({"copied": c, "missing": m}))
    sys.exit(1 if m else 0)
