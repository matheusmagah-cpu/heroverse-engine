#!/usr/bin/env python3
"""Check every clip before a Short is composed (PROMPT_GUIDE "Built for 9.5"): a clip that starts or ends on black
leaves a black flash at its cut (Genesis 4, 8.4 s: the forest clip opened on black), a low resolution or frame rate
looks cheap at 1080x1920. Run on the downloaded candidates; only clips with no flag go into the compose.

E109 (genesis-07 run 40357197063, s-well): Pavo returned a wide picture letterboxed inside the 9:16 frame, ~22 % black
above and below (cropdetect on the composed file: crop=1080:1062:0:428), and no check refused it. LETTERBOX_BARS: in
every sampled frame that is not all black, the rows (or columns) at both opposite edges are black (row max luma <=
BAR_LUMA) over more than BAR_SHARE of the side, each. Both edges, every frame: a night sky over a lit camp darkens one
edge only, and grain or a flame breaks a band; a padded picture's bars are flat on both sides from the first frame.

usage: clip_check.py CLIP.mp4 [CLIP.mp4 ...]       prints one JSON line per clip; exit 1 when any clip is flagged
       clip_check.py --composed FILE.mp4 [DIP_S ...]  the composed Short: exit 1 on a black frame that is not at an
                                                     intended dip_to_black (seconds, +-0.5 s)

vidIQ compose (tested 2026-10-24, 8 s renders): "cut" changes scene cleanly; "fade" and "wipe" both start the incoming
scene from black (luma 4), so every faded scene change flashed black for 1-2 frames in Genesis 2-4. Use "cut" between
scenes and "dip_to_black" only where the black is meant.
"""
import json
import subprocess
import sys

BLACK_LUMA = 16      # mean luma (0-255) of a frame that reads as black
EDGE_SECONDS = 0.6   # the part of a clip a cut or a fade can show
MIN_SHORT_SIDE = 720
MIN_FPS = 24
BAR_LUMA = 24        # a letterbox bar: every pixel of the row (column) at or under this luma (black 16, +codec noise)
BAR_SHARE = 0.04     # more than 4 % of the side, at BOTH opposite edges, in every sampled frame: LETTERBOX_BARS
BAR_FRAMES = 5       # frames sampled evenly across the clip
BAR_GRID = 90        # the short side of the sampled frame (the long side keeps the clip's ratio)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    s = data["streams"][0]
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    return {"width": s["width"], "height": s["height"], "fps": round(num / den, 2),
            "seconds": float(data["format"]["duration"])}


def lumas(path, start, seconds):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(start, 0)), "-t", str(seconds), "-i", path,
                          "-vf", "scale=64:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True, check=True).stdout
    return [float(line.split("=")[1]) for line in out.splitlines() if "YAVG=" in line]


def edge_runs(lines):
    """How many lines from the start are a bar (max luma <= BAR_LUMA)."""
    n = 0
    for peak in lines:
        if peak > BAR_LUMA:
            break
        n += 1
    return n


def frame_bars(raw, w, h):
    """(top, bottom, left, right) bar shares of one grey frame, or None when the whole frame is black (that is
    BLACK_START/BLACK_END's business, not a letterbox)."""
    rows = [max(raw[y * w:(y + 1) * w]) for y in range(h)]
    if max(rows) <= BAR_LUMA:
        return None
    cols = [max(raw[x::w]) for x in range(w)]
    return (edge_runs(rows) / h, edge_runs(rows[::-1]) / h, edge_runs(cols) / w, edge_runs(cols[::-1]) / w)


def bars(path, info):
    """The smallest bar share at each edge over BAR_FRAMES frames: {"top", "bottom", "left", "right"} or None when
    no frame shows a picture."""
    portrait = info["height"] >= info["width"]
    short, long_ = BAR_GRID, max(BAR_GRID, round(BAR_GRID * max(info["width"], info["height"])
                                                 / max(1, min(info["width"], info["height"]))))
    w, h = (short, long_) if portrait else (long_, short)
    found = []
    for k in range(BAR_FRAMES):
        t = info["seconds"] * (k + 0.5) / BAR_FRAMES
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf",
                              f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        if len(raw) == w * h:
            one = frame_bars(raw, w, h)
            if one:
                found.append(one)
    if not found:
        return None
    return {side: round(min(f[i] for f in found), 3) for i, side in enumerate(("top", "bottom", "left", "right"))}


def letterboxed(b):
    return bool(b) and (min(b["top"], b["bottom"]) > BAR_SHARE or min(b["left"], b["right"]) > BAR_SHARE)


def flags(info, head, tail, edges=None):
    out = []
    if head and min(head) < BLACK_LUMA:
        out.append("BLACK_START")
    if tail and min(tail) < BLACK_LUMA:
        out.append("BLACK_END")
    if min(info["width"], info["height"]) < MIN_SHORT_SIDE:
        out.append("LOW_RES")
    if info["fps"] < MIN_FPS:
        out.append("LOW_FPS")
    if letterboxed(edges):
        out.append("LETTERBOX_BARS")
    return out


def check(path):
    info = probe(path)
    head = lumas(path, 0, EDGE_SECONDS)
    tail = lumas(path, info["seconds"] - EDGE_SECONDS, EDGE_SECONDS)
    edges = bars(path, info)
    return dict(info, clip=path, head_min_luma=round(min(head), 1) if head else None,
                tail_min_luma=round(min(tail), 1) if tail else None, bars=edges, flags=flags(info, head, tail, edges))


def black_runs(path):
    """Start times of black stretches in a composed file."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          "scale=64:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stdout
    runs, t, prev_black = [], None, False
    for line in out.splitlines():
        if "pts_time:" in line:
            t = float(line.split("pts_time:")[1].split()[0])
        elif "YAVG=" in line:
            black = float(line.split("=")[1]) < BLACK_LUMA
            if black and not prev_black:
                runs.append(round(t, 2))
            prev_black = black
    return runs


def unexpected(runs, dips, end=None):
    """Black that is neither an intended dip nor the last half second (the Short's own ending)."""
    return [r for r in runs if not any(abs(r - d) <= 0.5 for d in dips) and not (end and r >= end - 0.5)]


def main(paths):
    if paths and paths[0] == "--composed":
        runs = black_runs(paths[1])
        bad = unexpected(runs, [float(x) for x in paths[2:]], probe(paths[1])["seconds"])
        print(json.dumps({"composed": paths[1], "black_starts": runs, "unexpected": bad}))
        return 1 if bad else 0
    bad = 0
    for p in paths:
        r = check(p)
        bad += bool(r["flags"])
        print(json.dumps(r))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
