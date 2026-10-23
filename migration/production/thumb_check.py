#!/usr/bin/env python3
"""R16 ruler for the finished thumbnail (thumbnail study 2026-10-23, 806 thumbnails in 89 channel-month strata).

Saturated thumbnails (mean saturation > 0.45) were dead x0.29 as often (p = 0.003); blue-dominant ones
(blue share > 0.4) broke out x0.26 as often (p = 0.008). The thumbnail must be saturated and not blue-dominant.
Usage: thumb_check.py THUMBNAIL OUT_JSON. Prints the verdict; exit 1 on FAIL.
"""
import json
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mining"))
import thumb_study  # noqa: E402

SATURATION_MIN = 0.45
BLUE_SHARE_MAX = 0.40


def verdict(m):
    fails = []
    if m["saturation"] <= SATURATION_MIN:
        fails.append(f"THUMB_NOT_SATURATED {m['saturation']:.2f} <= {SATURATION_MIN} (R16)")
    if m["blue_share"] > BLUE_SHARE_MAX:
        fails.append(f"THUMB_BLUE_DOMINANT {m['blue_share']:.2f} > {BLUE_SHARE_MAX} (R16)")
    return fails


def main(thumb, out):
    m = thumb_study.measure(Image.open(thumb).convert("RGB"))
    fails = verdict(m)
    result = {"status": "FAIL" if fails else "PASS", "fails": fails, "metrics": {k: round(v, 3) for k, v in m.items()}}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
