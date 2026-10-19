#!/usr/bin/env python3
"""Synthetic controls q1-q5 for av-picture-change (criteria.json). Builds each
control with ffmpeg from seeded smooth random images, classifies it, and
writes qualification.json."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import av_picture_change as apc  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS, STEP, N = 1280, 720, 30, 2.0, 10
LINES = ["The Lord goes before you", "He will be with you today", "Fear not, neither be dismayed",
         "His mercies are new", "Every single morning", "Great is his faithfulness",
         "Trust in the Lord", "He shall direct your paths", "You do not walk alone", "Amen"]


def background(seed, path):
    rng = np.random.default_rng(seed)
    small = rng.uniform(20, 235, (9, 16, 3))
    img = np.kron(small, np.ones((80, 80, 1)))
    for _ in range(3):  # smooth like a photograph, no hard grid edges
        img = (img + np.roll(img, 40, 0) + np.roll(img, 40, 1) + np.roll(img, -40, 0) + np.roll(img, -40, 1)) / 5
    img = np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                    "-i", "pipe:0", str(path)], input=img.tobytes(), check=True)


def esc(text):
    return text.replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def captions(y_expr, size, box):
    parts = []
    for i, line in enumerate(LINES):
        parts.append(f"drawtext=fontfile={FONT}:text='{esc(line)}':fontsize={size}:fontcolor=white:"
                     f"x=(w-text_w)/2:y={y_expr}:enable='between(t,{i * STEP},{(i + 1) * STEP - 0.001})'"
                     + (":box=1:boxcolor=black@0.55:boxborderw=24" if box else ":borderw=4:bordercolor=black"))
    return ",".join(parts)


def build(kind, tmp, out):
    imgs = []
    for i in range(N):
        p = tmp / f"{kind}-bg{i}.png"
        background(7 if kind in ("q1", "q4") else 100 * int(kind[1]) + i, p)
        imgs.append(p)
    if kind in ("q1", "q4"):
        inputs = ["-loop", "1", "-t", str(N * STEP), "-i", str(imgs[0])]
        chain = "[0:v]" + (captions("h*0.78", 54, False) if kind == "q1" else captions("(h-text_h)/2", 72, True))
    else:
        inputs = []
        for p in imgs:
            inputs += ["-loop", "1", "-t", str(STEP), "-i", str(p)]
        chain = "".join(f"[{i}:v]" for i in range(N)) + f"concat=n={N}:v=1:a=0"
        if kind == "q3":
            chain += "," + captions("h*0.78", 54, False)
        if kind == "q5":
            chain += (",drawbox=x=iw*0.40:y=ih*0.22:w=iw*0.20:h=ih*0.62:color=0xE8D8C0@1:t=fill,"
                      "drawbox=x=iw*0.45:y=ih*0.26:w=iw*0.10:h=ih*0.16:color=0x6B4A3A@1:t=fill")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", chain + ",format=yuv420p",
                    "-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-t", str(N * STEP), str(out)], check=True)


EXPECT = {"q1": "LOCAL", "q2": "SCENE", "q3": "SCENE", "q4": "LOCAL", "q5": "SCENE"}


def main(out_path):
    results, planted = {}, N - 1
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for kind, expected in EXPECT.items():
            video = tmp / f"{kind}.mp4"
            build(kind, tmp, video)
            r = apc.analyze(video)
            kinds = [c["kind"] for c in r["changes"] if c["kind"] != "EDGE"]
            hits = sum(any(abs(c["time"] - k * STEP) <= 0.1 for c in r["changes"]) for k in range(1, N))
            agree = sum(k == expected for k in kinds) / len(kinds) if kinds else 0.0
            results[kind] = {"expected": expected, "detected": len(r["changes"]), "planted": planted,
                             "planted_detected": hits, "agreement": round(agree, 3),
                             "changed_fractions": [c["changed_fraction"] for c in r["changes"]],
                             "summary": r["summary"],
                             "pass": agree >= 0.9 and hits / planted >= 0.8}
    status = "PASS" if all(v["pass"] for v in results.values()) else "FAIL"
    Path(out_path).write_text(json.dumps({"version": "av-picture-change-qualification-v1",
                                          "criteria_version": "av-picture-change-criteria-v1",
                                          "status": status, "controls": results}, indent=1) + "\n")
    print(json.dumps({k: (v["pass"], v["agreement"], v["planted_detected"], v["changed_fractions"]) for k, v in results.items()}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
