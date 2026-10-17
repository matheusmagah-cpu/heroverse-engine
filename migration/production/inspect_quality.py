#!/usr/bin/env python3
"""Perceptual-inspection support for a pilot (offline, no publication).

Produces what the automatic QA cannot judge, for human/AI visual review:
  1. contact sheet of the pilot (one frame every 20 s) and of reference
     openings (frames at 2, 10, 20, 30 s) for side-by-side comparison;
  2. burned-in text / watermark scan of every source clip with OCR
     (tesseract) on frames at 5, 20 and 35 s;
  3. sharpness per clip (variance of a Laplacian on a 480x270 gray proxy).
Outputs small JPEG sheets and a JSON report.
"""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


def frame(path, seconds, width, height):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3) if len(raw) == width * height * 3 else None


def sheet(frames, columns, out):
    frames = [f for f in frames if f is not None]
    h, w, _ = frames[0].shape
    rows = -(-len(frames) // columns)
    canvas = np.zeros((rows * h, columns * w, 3), np.uint8)
    for i, f in enumerate(frames):
        r, c = divmod(i, columns)
        canvas[r * h:(r + 1) * h, c * w:(c + 1) * w] = f
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                    f"{canvas.shape[1]}x{canvas.shape[0]}", "-i", "pipe:0", "-q:v", "4", str(out)],
                   input=canvas.tobytes(), check=True)


def ocr(image):
    tmp = Path("/tmp/ocr_frame.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                    f"{image.shape[1]}x{image.shape[0]}", "-i", "pipe:0", str(tmp)], input=image.tobytes(), check=True)
    text = subprocess.run(["tesseract", str(tmp), "-", "--psm", "11"], capture_output=True, text=True).stdout
    return [w for w in text.split() if sum(ch.isalnum() for ch in w) >= 3]


def sharpness(image):
    g = image.mean(2)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def main(pilot, clips_dir, refs_dir, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     pilot], capture_output=True, text=True, check=True).stdout)
    sheet([frame(pilot, t, 320, 180) for t in np.arange(1, duration, 20)], 6, out / "pilot-contact-sheet.jpg")
    refs = sorted(Path(refs_dir).glob("*.mp4"))
    if refs:
        sheet([frame(r, t, 320, 180) for r in refs for t in (2, 10, 20, 30)], 4, out / "reference-openings-sheet.jpg")
    report = []
    for clip in sorted(Path(clips_dir).glob("*.mp4")):
        samples = [frame(clip, t, 960, 540) for t in (5, 20, 35)]
        words = sorted({w for s in samples if s is not None for w in ocr(s)})
        report.append({"clip": clip.name.split("-sha256-")[0], "ocr_words": words[:30],
                       "burned_text_suspected": len(words) >= 2,
                       "sharpness": round(float(np.median([sharpness(s) for s in samples if s is not None])), 1)})
    sharp = [r["sharpness"] for r in report]
    for r in report:
        r["soft_relative_to_set"] = r["sharpness"] < 0.5 * float(np.median(sharp))
    (out / "inspection.json").write_text(json.dumps({"version": "pilot-inspection-v1", "clips": report,
                                                     "clips_with_burned_text": sum(r["burned_text_suspected"] for r in report),
                                                     "soft_clips": sum(r["soft_relative_to_set"] for r in report)},
                                                    indent=1) + "\n")
    print(json.dumps({"clips": len(report), "burned_text": sum(r["burned_text_suspected"] for r in report),
                      "soft": sum(r["soft_relative_to_set"] for r in report)}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
