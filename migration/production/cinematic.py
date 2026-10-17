#!/usr/bin/env python3
"""Cinematic layer for stills, at zero cost (CPU only, open weights).

1. depth: a monocular depth map per background (Depth Anything V2 Small,
   Apache-2.0, ONNX on CPU), saved as a 16-bit PNG next to the image.
2. parallax: a real 2.5D camera move. Each output pixel samples the still
   displaced in proportion to its depth, so near things slide past far things
   (dolly, truck, crane), instead of the whole picture zooming as one plane.
   Frames are computed with OpenCV remap and piped to ffmpeg.
3. film finish: a gentle grade per still (GRADE) and one cheap pass on the
   final picture (LOOK: halation, vignette, grain), plus optional dust drifting
   in the light (atmosphere) drawn into the parallax frames.

usage:
  cinematic.py depth MODEL.onnx IMAGE.png [IMAGE.png ...]
  cinematic.py parallax IMAGE.png DEPTH.png OUT.mp4 SECONDS MOVE
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H = 1920, 1080
MARGIN = 1.12         # master is 12% larger than the frame, so moves never show an edge
DEPTH_SIZE = 518      # Depth Anything V2 input
MOVES = ("dolly_in", "truck_right", "crane_up", "dolly_out", "truck_left", "arc")
# camera amplitudes in output pixels (parallax at the nearest depth; far depth moves less)
AMP = {"dolly_in": 0.0, "dolly_out": 0.0, "truck_right": 70.0, "truck_left": 70.0, "crane_up": 45.0, "arc": 55.0}
ZOOM = {"dolly_in": 0.07, "dolly_out": 0.07, "truck_right": 0.02, "truck_left": 0.02, "crane_up": 0.02, "arc": 0.04}

# film finish, in two parts so the per-frame pass stays cheap:
# GRADE once per still (and the figure): warm highlights, slightly cooler shadows, gentle contrast;
# LOOK once on the final picture: halation on highlights (luma only, computed at quarter size),
# vignette, fine temporal grain.
GRADE = "colorbalance=rs=-0.015:bs=0.02:rh=0.03:gh=0.01:bh=-0.03,eq=contrast=1.04:saturation=1.04"
LOOK = ("split[base][glow];"
        "[glow]scale=480:270,curves=all='0/0 0.72/0 1/1',gblur=sigma=6,scale=1920:1080[halo];"
        "[base][halo]blend=c0_mode=screen:c0_opacity=0.16:c1_mode=normal:c1_opacity=1:c2_mode=normal:c2_opacity=1,"
        "vignette=angle=PI/6:mode=forward,"
        "noise=c0s=4:c0f=t+u")


def grade(image, out=None):
    """Apply GRADE to a still in place (or to out); alpha is kept."""
    out = out or image
    tmp = Path(out).with_name(Path(out).stem + ".graded.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(image), "-vf", GRADE, str(tmp)], check=True)
    Path(tmp).replace(out)


def smoothstep(x):
    return x * x * (3 - 2 * x)


def depth(model_path, images):
    """Write IMAGE.depth.png (16-bit, 0 = far, 65535 = near) for each image."""
    import cv2
    import onnxruntime as ort
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    mean, std = np.array([0.485, 0.456, 0.406], np.float32), np.array([0.229, 0.224, 0.225], np.float32)
    for image in images:
        rgb = cv2.cvtColor(cv2.imread(str(image)), cv2.COLOR_BGR2RGB)
        x = cv2.resize(rgb, (DEPTH_SIZE, DEPTH_SIZE), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
        x = ((x - mean) / std).transpose(2, 0, 1)[None]
        d = sess.run(None, {name: x})[0].reshape(DEPTH_SIZE, DEPTH_SIZE)  # relative inverse depth: larger = nearer
        d = cv2.resize(d, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
        lo, hi = np.percentile(d, 1), np.percentile(d, 99)
        d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
        cv2.imwrite(str(Path(image).with_suffix(".depth.png")), (d * 65535).astype(np.uint16))


def load(image, depth_png):
    """Master image and smoothed depth at MARGIN x the output size."""
    import cv2
    mw, mh = int(W * MARGIN), int(H * MARGIN)
    img = cv2.imread(str(image))
    scale = max(mw / img.shape[1], mh / img.shape[0])
    size = (int(np.ceil(img.shape[1] * scale)), int(np.ceil(img.shape[0] * scale)))
    img = cv2.resize(img, size, interpolation=cv2.INTER_LANCZOS4)
    d = cv2.imread(str(depth_png), cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535
    d = cv2.resize(d, size, interpolation=cv2.INTER_LINEAR)
    # smoothing the depth turns tears at object edges into soft stretches the eye does not catch
    d = cv2.GaussianBlur(d, (0, 0), sigmaX=size[0] / 300)
    y0, x0 = (size[1] - mh) // 2, (size[0] - mw) // 2
    return img[y0:y0 + mh, x0:x0 + mw].copy(), d[y0:y0 + mh, x0:x0 + mw].copy()


def camera(move, e):
    """(dx, dy, zoom) at eased progress e in 0..1; dx/dy are near-plane shifts in output pixels."""
    a, z = AMP[move], ZOOM[move]
    if move == "dolly_in":
        return 0.0, 0.0, 1 + z * e
    if move == "dolly_out":
        return 0.0, 0.0, 1 + z * (1 - e)
    if move == "truck_right":
        return -a * (e - 0.5), 0.0, 1 + z * e
    if move == "truck_left":
        return a * (e - 0.5), 0.0, 1 + z * e
    if move == "crane_up":
        return 0.0, a * (e - 0.5), 1 + z * e
    if move == "arc":
        return -a * np.sin(np.pi * (e - 0.5)), -0.3 * a * (e - 0.5), 1 + z * e
    raise ValueError(move)


class Dust:
    """Sparse motes drifting in the light: depth-sorted, soft, slow (atmosphere, not effect)."""

    def __init__(self, n=70, seed=7):
        rng = np.random.default_rng(seed)
        self.p = rng.random((n, 2)) * (W, H)
        self.v = (rng.random((n, 2)) - 0.5) * (10, 6) + (2, -4)  # px/s, gently upward
        self.z = rng.random(n)                                   # 0 far .. 1 near
        self.phase = rng.random(n) * 6.28

    def draw(self, frame, t, dx, dy):
        import cv2
        layer = np.zeros_like(frame)
        for (x, y), (vx, vy), z, ph in zip(self.p, self.v, self.z, self.phase):
            px = (x + vx * t + dx * (0.5 + z)) % W
            py = (y + vy * t + dy * (0.5 + z)) % H
            r = 1.0 + 2.5 * z
            a = (0.25 + 0.35 * z) * (0.6 + 0.4 * np.sin(ph + t * 0.8))
            cv2.circle(layer, (int(px), int(py)), int(np.ceil(r)), (215 * a, 235 * a, 255 * a), -1, cv2.LINE_AA)
        return cv2.add(frame, cv2.GaussianBlur(layer, (0, 0), 1.6))


def frames(img, d, move, n, dust=None, fps=30):
    """Yield n BGR frames of the parallax move. Backward warp: each output pixel looks up
    the source displaced by its own depth (two fixed-point passes keep edges stable).
    The displacement field is smooth (blurred depth), so it is solved at half resolution
    and upsampled; only the final image lookup runs at full resolution."""
    import cv2
    mh, mw = d.shape
    gx, gy = np.meshgrid(np.linspace(0, W - 1, W // 2, dtype=np.float32), np.linspace(0, H - 1, H // 2, dtype=np.float32))
    cx, cy = (mw - 1) / 2, (mh - 1) / 2
    focus = float(np.median(d))  # the median depth stays put; nearer slides one way, farther the other
    for i in range(n):
        e = smoothstep(i / max(n - 1, 1))
        dx, dy, zoom = (float(v) for v in camera(move, e))  # python floats keep the maps float32
        bx = cx + (gx - (W - 1) / 2) / zoom
        by = cy + (gy - (H - 1) / 2) / zoom
        sx, sy = bx, by
        for _ in range(2):
            k = cv2.remap(d, sx, sy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) - focus
            # dolly: near things also grow faster than far things
            par = 1 + (zoom - 1) * 1.5 * k
            sx = cx + (bx - cx) / par - dx * k
            sy = cy + (by - cy) / par - dy * k
        sx = cv2.resize(sx, (W, H), interpolation=cv2.INTER_LINEAR)
        sy = cv2.resize(sy, (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.remap(img, sx, sy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if dust is not None:
            out = dust.draw(out, i / fps, dx, dy)
        yield out


def parallax(image, depth_png, out, length, move, fps=30, dust=False, intermediate=True):
    img, d = load(image, depth_png)
    n = int(round(length * fps))
    preset, crf = ("ultrafast", "12") if intermediate else ("veryfast", "18")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", crf,
                          "-pix_fmt", "yuv420p", "-threads", "2", str(out)], stdin=subprocess.PIPE)
    for f in frames(img, d, move, n, Dust() if dust else None, fps):
        p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"ffmpeg failed for {out}")


if __name__ == "__main__":
    if sys.argv[1] == "depth":
        depth(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "parallax":
        parallax(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6], dust=True, intermediate=False)
