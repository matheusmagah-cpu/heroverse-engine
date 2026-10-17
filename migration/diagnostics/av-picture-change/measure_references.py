#!/usr/bin/env python3
"""Classify picture changes of reference openings and render spot-check sheets:
for every change, the frame before (t-0.3 s) and after (t+0.3 s), framed blue
for SCENE and orange for LOCAL, four pairs per row, one sheet per file."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import av_picture_change as apc  # noqa: E402

TW, TH, B = 224, 126, 4
COLOURS = {"SCENE": (40, 110, 255), "LOCAL": (255, 150, 0), "EDGE": (128, 128, 128)}


def rgb_frames(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf",
                          f"scale={TW}:{TH}:force_original_aspect_ratio=increase,crop={TW}:{TH},fps=30,format=rgb24",
                          "-f", "rawvideo", "pipe:1"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, TH, TW, 3)


def spot_sheet(path, changes, out):
    frames = rgb_frames(path)
    tiles = []
    for c in changes:
        pair = []
        for dt in (-0.3, 0.3):
            i = min(len(frames) - 1, max(0, int(round((c["time"] + dt) * 30))))
            tile = np.zeros((TH + 2 * B, TW + 2 * B, 3), np.uint8)
            tile[:] = COLOURS[c["kind"]]
            tile[B:-B, B:-B] = frames[i]
            pair.append(tile)
        tiles.append(np.concatenate(pair + [np.zeros((TH + 2 * B, 12, 3), np.uint8)], 1))
    if not tiles:
        return
    per_row = 4
    rows = [np.concatenate(tiles[i:i + per_row] + [np.zeros_like(tiles[0])] * (per_row - len(tiles[i:i + per_row])), 1)
            for i in range(0, len(tiles), per_row)]
    canvas = np.concatenate(rows, 0)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                    f"{canvas.shape[1]}x{canvas.shape[0]}", "-i", "pipe:0", "-q:v", "5", str(out)],
                   input=canvas.tobytes(), check=True)


def main(out_dir, labels_json, paths):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    labels = json.loads(Path(labels_json).read_text()) if labels_json != "-" else {}
    records = []
    for p in paths:
        r = apc.analyze(p)
        vid = Path(p).name.split("native-")[-1][:11]
        r["video_id"], r["cohort"] = vid, labels.get(vid)
        spot_sheet(p, r["changes"], out / f"spot-{vid}.jpg")
        records.append(r)
        print(vid, r["cohort"], json.dumps(r["summary"]))
    (out / "reference-picture-changes.json").write_text(json.dumps({"version": "reference-picture-changes-v1",
                                                                    "records": records}, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
