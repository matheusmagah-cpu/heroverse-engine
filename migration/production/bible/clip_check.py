#!/usr/bin/env python3
"""Check every clip before a Short is composed (PROMPT_GUIDE "Built for 9.5"): a clip that starts or ends on black
leaves a black flash at its cut (Genesis 4, 8.4 s: the forest clip opened on black), a low resolution or frame rate
looks cheap at 1080x1920. Run on the downloaded candidates; only clips with no flag go into the compose.

E109 (genesis-07 run 40357197063, s-well): Pavo returned a wide picture letterboxed inside the 9:16 frame, ~22 % black
above and below (cropdetect on the composed file: crop=1080:1062:0:428), and no check refused it. LETTERBOX_BARS: in
every sampled frame that is not all black, the rows (or columns) at both opposite edges are black (row max luma <=
BAR_LUMA) over more than BAR_SHARE of the side, each. Both edges, every frame: a night sky over a lit camp darkens one
edge only, and grain or a flame breaks a band; a padded picture's bars are flat on both sides from the first frame.

E111 (genesis-07 run 40389124871, s-still): with BAR_LUMA 24 a dusk camp under a black sky (top rows 14-24) over dark
ground read as bars at both edges, and all three new generations were refused. Measured: s-well's bars read luma 1 and
the night sky 14-24, so a bar is now a row at or under luma 8.

E117 (genesis-08 shot-probe run 40477936323, s-board round 1): Pavo returned the picture turned 90 degrees inside the
9:16 frame (the horizon ran down the frame, the people lay on their sides), clip_check passed it and only Claude's
review saw it. ROTATED_PICTURE: a landscape's sky-to-ground change runs down the frame, so the mean luma of the rows
spreads far more than the mean luma of the columns; turned 90 or 270 degrees it is the other way round. A clip is
flagged when, in every sampled picture frame, the column means spread (standard deviation) over ROT_SPREAD and over
ROT_RATIO times the row means' spread. Measured on the 90x160 grid: s-board round 1 column/row 4.56-5.31 (column
spread 53-54); 94 good clips (the 32 approved genesis-08 shots and its 5 other probe rounds, the 29 Pavo clips in
evidence/pavo, 28 genesis-09 candidates) at most 1.62 over their frames (genesis-06's lamp, spread 33), most under 1;
one mid-pan frame of a genesis-09 candidate read 3.47 alone, hence every frame. Fixtures: bible/fixtures/clip_check.
A turned close-up with no horizon has no such profile and is still the review's to see.

E127 (review of #468): the long asks Pavo for 16:9 and the Shorts for 9:16; a clip returned at another shape (a
9:16 clip in the 16:9 long, a square) would be cropped or padded by the compose and seen only at the review.
CLIP_ASPECT_MISMATCH: the returned width / height differs from the plan's aspect_ratio by more than ASPECT_TOL (Pavo
16:9 is 1280x720, 9:16 720x1280: exact). Checked by the build's own check on every probed, adopted and shipped clip.

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
BAR_LUMA = 8         # a letterbox bar: every pixel of the row (column) at or under this luma (pad black reads 1;
                     # a night sky reads 14-24, E111)
BAR_SHARE = 0.04     # more than 4 % of the side, at BOTH opposite edges, in every sampled frame: LETTERBOX_BARS
BAR_FRAMES = 5       # frames sampled evenly across the clip
BAR_GRID = 90        # the short side of the sampled frame (the long side keeps the clip's ratio)
ROT_SPREAD = 30      # ROTATED_PICTURE (E117): the column means' standard deviation over this (s-board r1: 53-54)
ASPECT_TOL = 0.02    # CLIP_ASPECT_MISMATCH (E127): |w/h - W/H| over this share of W/H
ROT_RATIO = 3.0      # and over 3x the row means' (s-board r1: 4.56-5.31; good clips at most 1.71), in every frame


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


def samples(path, info):
    """The grey frames (BAR_FRAMES, sampled evenly across the clip, on the BAR_GRID grid): (frames, w, h)."""
    portrait = info["height"] >= info["width"]
    short, long_ = BAR_GRID, max(BAR_GRID, round(BAR_GRID * max(info["width"], info["height"])
                                                 / max(1, min(info["width"], info["height"]))))
    w, h = (short, long_) if portrait else (long_, short)
    frames = []
    for k in range(BAR_FRAMES):
        t = info["seconds"] * (k + 0.5) / BAR_FRAMES
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf",
                              f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                             capture_output=True, check=True).stdout
        if len(raw) == w * h:
            frames.append(raw)
    return frames, w, h


def bars_of(frames, w, h):
    """The smallest bar share at each edge over the sampled frames: {"top", "bottom", "left", "right"} or None when
    no frame shows a picture."""
    found = [one for one in (frame_bars(raw, w, h) for raw in frames) if one]
    if not found:
        return None
    return {side: round(min(f[i] for f in found), 3) for i, side in enumerate(("top", "bottom", "left", "right"))}


def bars(path, info):
    return bars_of(*samples(path, info))


def _spread(values):
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


def frame_turn(raw, w, h):
    """(column spread, row spread) of one grey frame: the standard deviation of its column means and of its row
    means; None when the whole frame is black."""
    if max(raw) <= BAR_LUMA:
        return None
    rows = [sum(raw[y * w:(y + 1) * w]) / w for y in range(h)]
    cols = [sum(raw[x::w]) / h for x in range(w)]
    return _spread(cols), _spread(rows)


def turn_of(frames, w, h):
    """{"cols", "rows", "ratio"} of the sampled frame that looks least turned (lowest column/row ratio), or None."""
    found = [one for one in (frame_turn(raw, w, h) for raw in frames) if one]
    if not found:
        return None
    cols, rows = min(found, key=lambda f: f[0] / max(f[1], 1.0))
    return {"cols": round(cols, 1), "rows": round(rows, 1), "ratio": round(cols / max(rows, 1.0), 2)}


def rotated(turn):
    return bool(turn) and turn["cols"] > ROT_SPREAD and turn["ratio"] > ROT_RATIO


def letterboxed(b):
    return bool(b) and (min(b["top"], b["bottom"]) > BAR_SHARE or min(b["left"], b["right"]) > BAR_SHARE)


def aspect_mismatch(info, aspect):
    """E127: True when the clip's width / height is not the requested W:H (None asks nothing)."""
    if not aspect:
        return False
    w, h = (int(x) for x in str(aspect).split(":"))
    want = w / h
    return abs(info["width"] / max(1, info["height"]) - want) > ASPECT_TOL * want


def flags(info, head, tail, edges=None, turn=None, aspect=None):
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
    if rotated(turn):
        out.append("ROTATED_PICTURE")
    if aspect_mismatch(info, aspect):
        out.append("CLIP_ASPECT_MISMATCH")
    return out


def check(path, aspect=None):
    info = probe(path)
    head = lumas(path, 0, EDGE_SECONDS)
    tail = lumas(path, info["seconds"] - EDGE_SECONDS, EDGE_SECONDS)
    frames, w, h = samples(path, info)
    edges, turn = bars_of(frames, w, h), turn_of(frames, w, h)
    return dict(info, clip=path, head_min_luma=round(min(head), 1) if head else None,
                tail_min_luma=round(min(tail), 1) if tail else None, bars=edges, turn=turn,
                flags=flags(info, head, tail, edges, turn, aspect))


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
