#!/usr/bin/env python3
"""Camera motion for a still (the shared building block of every visual recipe).

The still is scaled once to 2x the output (3840x2160); each frame is a float
crop window of that master, downscaled to 1920x1080, so motion moves in
half-pixel steps (smooth, no judder) without rescaling the source per frame.
Motions: push_in, pull_out, pan_left, pan_right, rise, drift (subtle diagonal),
static. Easing is smoothstep so moves start and stop softly.
usage (test): motion.py IMAGE OUT.mp4 SECONDS MOTION
"""
import os
import subprocess
import sys

W, H = (int(v) for v in os.environ.get("HERO_FRAME", "1920x1080").split("x"))  # v4: 2560x1440
MW, MH = 2 * W, 2 * H
ZOOM = 0.10       # push/pull amount (fraction of the frame)
PAN = 0.12        # pan distance (fraction of the master width)


def zoompan(motion, frames, fps=30):
    """zoompan over the 2x master: integer coordinates there are half-pixel steps
    in the output. 'on' is the output frame index; e is smoothstep 0..1."""
    e = f"(3*pow(on/{frames},2)-2*pow(on/{frames},3))"
    base = 1 / (1 - ZOOM)  # keep a margin so pans and drifts never show an edge
    z = {"push_in": f"({1:.4f}+{base - 1:.4f}*{e})", "pull_out": f"({base:.4f}-{base - 1:.4f}*{e})"}.get(motion, f"{base:.4f}")
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    if motion == "pan_left":
        cx = f"(iw-iw/zoom)*(1-{e})"
    elif motion == "pan_right":
        cx = f"(iw-iw/zoom)*{e}"
    elif motion == "rise":
        cy = f"(ih-ih/zoom)*(1-{e})"
    elif motion == "drift":
        cx, cy = f"(iw-iw/zoom)*(0.3+0.4*{e})", f"(ih-ih/zoom)*(0.7-0.4*{e})"
    return (f"scale={MW}:{MH}:force_original_aspect_ratio=increase,crop={MW}:{MH},"
            f"zoompan=z='{z}':x='{cx}':y='{cy}':d={frames}:s={W}x{H}:fps={fps}")


def render(image, out, length, motion, fps=30, extra_vf="", intermediate=False):
    frames = int(round(length * fps))
    if motion == "static":
        vf = f"loop=loop={frames}:size=1,fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    else:
        vf = zoompan(motion, frames, fps)
    vf += (("," + extra_vf) if extra_vf else "") + f",trim=end_frame={frames},format=yuv420p"
    # intermediate clips are re-encoded later: fastest preset at near-lossless quality
    preset, crf = ("veryfast", "16") if intermediate else ("veryfast", "18")  # intermediates: near-transparent, ~15x smaller than ultrafast crf12
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(image), "-vf", vf, "-c:v", "libx264", "-preset", preset,
                    "-crf", crf, "-r", str(fps), "-pix_fmt", "yuv420p", "-threads", "2", str(out)], check=True)


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4])
