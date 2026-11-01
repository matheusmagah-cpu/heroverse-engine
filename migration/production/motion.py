"""Camera motion for stills, at zero cost (CPU only).

The legacy move (render): the still is upscaled once to a 2x master (3840x2160); every output frame is an eased crop
window of that master, downscaled to 1920x1080, so motion moves in half-pixel steps (smooth, no judder) without
rescaling the source per frame. Motions: push_in, pull_out, pan_left, pan_right, rise, drift, static.

The cinematic engine (owner 2026-11-01, DECISIONS "Cinematic still animation"): a long-first long holds about 25-30
approved stills of 15-20 s each, and each one moves as its scene needs. direct() is the auto-director: per still it
reads the beat (hook, escalation, KJV line, climax, Keeper insight, aftermath), the emotion the prompt names, the
spoken span and the picture (face and saliency, Depth Anything V2 depth or a proxy, sky, water, fire), then picks a
keyframed move (MOTIONS), its easing and size, and up to three atmosphere layers (ATMOSPHERES), never the same move
twice in a row, and records why. A plan shot's `motion` / `atmosphere` overrides it. Every frame is one sub-pixel
resampling of a 2x master with the subject box kept inside the centre 9:16 band (the long's Shorts are centre cuts,
short_cuts.py), no edge shown, bit-exact for the same input.

usage: motion.py IMAGE OUT.mp4 SECONDS MOTION                                the legacy move
       motion.py cinematic IMAGE OUT.mp4 SECONDS MOVE [ATMOS,...] [WxH]      one cinematic move, for a test
       motion.py depth MODEL.onnx OUT_DIR IMAGE...                            Depth Anything V2 maps: OUT_DIR/<sha256>.png
       motion.py moves IMAGE OUT.jpg                                          every move at its start, middle and end
       motion.py sheet VIDEO OUT.jpg                                          a contact sheet of a rendered clip
"""
import hashlib
import math
import os
import re
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




# ---------- cinematic still animation (owner 2026-11-01: 25-30 stills of 15-20 s each, moved as the scene needs) ----------

ENGINE = "cinematic-v2"
MOTIONS = ("push_in", "pull_back", "pan_left", "pan_right", "tilt_up", "tilt_down", "pan_to_subject", "drift",
           "parallax_2_5d", "hold_then_push", "hold")
TRIVIAL_MOTIONS = ("hold",)          # a locked frame: refused for a still held 12-20 s (plan_check)
EASES = ("in_out", "settle", "build", "gentle")
ATMOSPHERES = ("dust", "embers", "mist", "rain", "water_shimmer", "god_rays", "torch_flicker", "film_grain", "vignette")
ATMOSPHERE_MAX = 3
OVERRIDE_KEYS = ("move", "ease", "hold", "strength")
HOLD_RANGE = (0.1, 0.5)              # hold_then_push: the share of the span held before the move
STRENGTH_RANGE = (0.4, 1.5)
FAMILY = {"push_in": "in", "hold_then_push": "in", "pull_back": "out", "pan_left": "x", "pan_right": "x",
          "pan_to_subject": "x", "drift": "x", "parallax_2_5d": "z", "tilt_up": "y", "tilt_down": "y", "hold": "hold"}
BASE_SCALE = 1.06                    # the still always covers the frame with headroom: no edge, ever
MAX_SCALE = 1.45
PUSH = 0.15                          # a full-strength push: 15 % of scale over the span
PARALLAX_SLIDE = 0.012               # parallax_2_5d: near against far, a share of the width over the move
PARALLAX_ZOOM = 0.03                 # and near things grow this much more than far ones
PREFILTER = 0.7                      # the 2x master is low-passed once, so the ~0.55x sampling never crawls
SUBJECT_SHARE = (0.6, 0.7)           # the default centred subject box: of the band's width, of the frame height
DEPTH_MODEL = {"name": "Depth Anything V2 Small (ONNX)", "licence": "apache-2.0", "size": 518,
               "url": "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/"
                      "4472b7362082ad9968fee890ca0f1e5aca36b93d/onnx/model.onnx",
               "sha256": "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c"}


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ease(name, t):
    """in_out: cosine, soft start and landing; settle: moving at the cut, a long soft landing; build: a slow creep
    that gathers pace and still lands softly; gentle: an almost even glide."""
    t = min(max(t, 0.0), 1.0)
    cos = lambda u: 0.5 - 0.5 * math.cos(math.pi * u)  # noqa: E731
    if name == "settle":
        return 1 - (1 - t) ** 3
    if name == "build":
        return cos(t ** 1.7)
    if name == "gentle":
        return 0.5 * t + 0.5 * cos(t)
    return cos(t)


def band_half(frame):
    """Half the centre 9:16 column a Short cuts from this frame (short_cuts.py), a share of the frame width."""
    w, h = frame
    return min(w, h * 9 / 16) / (2 * w)


def default_subject(frame):
    """(x0, y0, x1, y1): the centred subject box, in picture shares from its centre (every long-first still is
    centred, E259)."""
    hw, hh = SUBJECT_SHARE[0] * band_half(frame), SUBJECT_SHARE[1] / 2
    return (-hw, -hh, hw, hh)


def x_room(s, subject, frame, extra=0.0):
    """The camera x interval at scale s (the picture point at the frame centre, a share of the width from the
    picture's centre): no still edge shown and the subject box inside the centre band."""
    e = (1 - 1 / s) / 2 - 1.0 / frame[0] - extra
    hb = band_half(frame) - extra
    return max(-e, subject[2] - hb / s), min(e, subject[0] + hb / s)


def y_room(s, subject, frame):
    e = (1 - 1 / s) / 2 - 1.0 / frame[1]
    cy = (subject[1] + subject[3]) / 2
    return max(-e, cy - 0.42 / s), min(e, cy + 0.42 / s)


def camera(keys, f):
    """(scale, x, y) at fraction f of the span: keys [f, s, x, y, ease], each segment eased by its end key's curve
    (scale and position share it, so a move inside the room at both ends stays inside between them)."""
    if f <= keys[0][0]:
        return tuple(keys[0][1:4])
    for a, b in zip(keys, keys[1:]):
        if f <= b[0]:
            e = ease(b[4], (f - a[0]) / max(b[0] - a[0], 1e-9))
            return tuple(a[k] + (b[k] - a[k]) * e for k in (1, 2, 3))
    return tuple(keys[-1][1:4])


def parallax_extra(move, strength):
    return PARALLAX_SLIDE * strength / 2 + PARALLAX_ZOOM / 4 if move == "parallax_2_5d" else 0.0


def path_problems(keys, subject, frame, extra=0.0, steps=240):
    """Why a keyed move cannot be shown: a still edge revealed (black border) or the subject out of the centre 9:16
    band, sampled densely along the eased path."""
    for k in range(steps + 1):
        s, x, y = camera(keys, k / steps)
        lo, hi = x_room(s, subject, frame, extra)
        ylo, yhi = y_room(s, subject, frame)
        if not lo - 1e-6 <= x <= hi + 1e-6:
            return [f"MOTION_SUBJECT_OUTSIDE_SAFE_AREA at {k / steps:.2f} (or the still's edge)"]
        if not ylo - 1e-6 <= y <= yhi + 1e-6:
            return [f"MOTION_EDGE at {k / steps:.2f} (the still's top or bottom edge)"]
    return []


def base_scale(subject, frame, extra=0.0):
    s = BASE_SCALE
    while s < MAX_SCALE:
        lo, hi = x_room(s, subject, frame, extra)
        if lo <= hi and y_room(s, subject, frame)[0] <= y_room(s, subject, frame)[1]:
            return s
        s = round(s + 0.01, 4)
    return None


def build_keys(move, frame, subject=None, strength=1.0, ease_name="in_out", hold=0.3, direction=1):
    """The keyframes of a move over a span [0, 1], the subject kept centred where it can be ("home"), each key
    clamped into the room; a move the room cannot hold is made smaller (x0.7, five times) before it becomes a hold."""
    sub = tuple(subject or default_subject(frame))
    extra = parallax_extra(move, strength)
    b = base_scale(sub, frame, extra)
    if b is None:   # a subject wider than the band at any sane scale: centred, and the record says so
        sub, b = default_subject(frame), BASE_SCALE + 0.02
    cx, cy = (sub[0] + sub[2]) / 2, (sub[1] + sub[3]) / 2
    for attempt in range(6):
        a = strength * 0.7 ** attempt

        def home(s, dx=0.0, dy=0.0, ez=ease_name):
            lo, hi = x_room(s, sub, frame, extra)
            ylo, yhi = y_room(s, sub, frame)
            return [round(s, 6), round(min(max(cx + dx, lo), hi), 6), round(min(max(cy + dy, ylo), yhi), 6), ez]

        p = PUSH * a
        if move == "push_in":
            keys = [[0.0] + home(b), [1.0] + home(b + p)]
        elif move == "pull_back":
            keys = [[0.0] + home(b + p), [1.0] + home(b)]
        elif move in ("pan_left", "pan_right"):
            sgn, s, d = (1 if move == "pan_right" else -1), b + 0.05 + 0.03 * a, 0.03 * a + 0.008
            keys = [[0.0] + home(s, -sgn * d), [1.0] + home(s + 0.01 * a, sgn * d)]
        elif move in ("tilt_up", "tilt_down"):
            sgn, s, d = (-1 if move == "tilt_up" else 1), b + 0.06 + 0.03 * a, 0.035 * a + 0.01
            keys = [[0.0] + home(s, 0, -sgn * d), [1.0] + home(s + 0.01 * a, 0, sgn * d)]
        elif move == "pan_to_subject":   # from the picture's centre side, landing with the subject centred
            vx, vy = -cx, -cy
            n = math.hypot(vx, vy)
            if n < 0.03:
                vx, vy, n = float(direction), -0.3, math.hypot(1.0, 0.3)
            m = 0.05 * a
            keys = [[0.0] + home(b + 0.03, vx / n * m, vy / n * m), [1.0] + home(b + 0.03 + 0.05 * a)]
        elif move == "drift":
            keys = [[0.0] + home(b + 0.02, -direction * 0.018 * a, 0.01 * a),
                    [1.0] + home(b + 0.02 + 0.035 * a, direction * 0.018 * a, -0.01 * a)]
        elif move == "parallax_2_5d":
            keys = [[0.0] + home(b + 0.03, -direction * 0.012 * a), [1.0] + home(b + 0.03 + 0.04 * a, direction * 0.012 * a)]
        elif move == "hold_then_push":
            keys = [[0.0] + home(b), [round(hold, 6)] + home(b), [1.0] + home(b + 1.1 * p, ez="in_out")]
        elif move == "hold":
            keys = [[0.0] + home(b + 0.02), [1.0] + home(b + 0.02)]
        else:
            raise SystemExit(f"MOTION_UNKNOWN {move!r} ({', '.join(MOTIONS)})")
        if not path_problems(keys, sub, frame, extra):
            return keys, sub, round(a, 6)
    keys = [[0.0] + home(b + 0.02), [1.0] + home(b + 0.02)]
    return keys, sub, 0.0


def override_problems(motion):
    """A plan's `motion`: a name of MOTIONS, or {"move": name, "ease": EASES, "hold": 0.1-0.5, "strength": 0.4-1.5}."""
    if motion is None:
        return []
    if isinstance(motion, str):
        return [] if motion in MOTIONS else [f"MOTION_UNKNOWN {motion!r} ({', '.join(MOTIONS)})"]
    if not isinstance(motion, dict) or set(motion) - set(OVERRIDE_KEYS) or motion.get("move") not in MOTIONS:
        return [f"MOTION_INVALID {motion!r} (a name of {', '.join(MOTIONS)}, or {{move, ease, hold, strength}})"]
    out = []
    if "ease" in motion and motion["ease"] not in EASES:
        out.append(f"MOTION_INVALID ease {motion['ease']!r} ({', '.join(EASES)})")
    for key, (lo, hi) in (("hold", HOLD_RANGE), ("strength", STRENGTH_RANGE)):
        v = motion.get(key)
        if key in motion and (type(v) not in (int, float) or not lo <= v <= hi):
            out.append(f"MOTION_INVALID {key} {v!r} ({lo}-{hi})")
    return out


def override_move(motion):
    return motion if isinstance(motion, str) else (motion or {}).get("move")


def atmosphere_problems(atmosphere):
    if atmosphere is None:
        return []
    if not isinstance(atmosphere, list) or not all(isinstance(a, str) for a in atmosphere):
        return ["ATMOSPHERE_INVALID (a list of names)"]
    bad = [a for a in atmosphere if a not in ATMOSPHERES]
    if bad:
        return [f"ATMOSPHERE_UNKNOWN {', '.join(bad)} ({', '.join(ATMOSPHERES)})"]
    if len(set(atmosphere)) != len(atmosphere) or len(atmosphere) > ATMOSPHERE_MAX:
        return [f"ATMOSPHERE_INVALID (at most {ATMOSPHERE_MAX} different names)"]
    return []
def read_still(image):
    import cv2
    import numpy as np
    img = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if img is None:   # a format OpenCV does not read: Pillow
        from PIL import Image
        img = cv2.cvtColor(np.asarray(Image.open(image).convert("RGB")), cv2.COLOR_RGB2BGR)
    return img


def cover(img, size):
    """The still scaled to cover `size` and centre-cropped (Lanczos up, area down)."""
    import cv2
    w, h = size
    k = max(w / img.shape[1], h / img.shape[0])
    sw, sh = max(w, round(img.shape[1] * k)), max(h, round(img.shape[0] * k))
    img = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_LANCZOS4 if k > 1 else cv2.INTER_AREA)
    x, y = (sw - w) // 2, (sh - h) // 2
    return img[y:y + h, x:x + w].copy()


def depth_proxy(img):
    """A smooth near/far map (1 = near) of a still, at a small size, with no model: the subject GrabCut finds in the
    centre band (every long-first still is centred), the in-focus detail and the lower frame count as near. Blurred
    wide, so the 2.5D warp bends smoothly and never tears an edge. Deterministic (OpenCV's RNG is seeded)."""
    import cv2
    import numpy as np
    w = 320
    h = max(8, round(img.shape[0] * w / img.shape[1]))
    small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    band = 2 * band_half((w, h)) * w
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fg = np.exp(-(((xx - w / 2) / (band * 0.5)) ** 2 + ((yy - h * 0.55) / (h * 0.5)) ** 2)).astype(np.float32)
    mask = np.zeros((h, w), np.uint8)
    cv2.setRNGSeed(0)
    try:
        cv2.grabCut(small, mask, (int(w / 2 - band * 0.45), int(h * 0.06), int(band * 0.9), int(h * 0.9)),
                    np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 4, cv2.GC_INIT_WITH_RECT)
        cut = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.float32)
        if 0.03 <= float(cut.mean()) <= 0.6:   # else GrabCut found nothing usable: the centred ellipse stays
            fg = 0.7 * cut + 0.3 * fg
    except cv2.error:
        pass
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sharp = cv2.GaussianBlur(np.abs(cv2.Laplacian(gray, cv2.CV_32F)), (0, 0), w / 40)
    sharp = np.clip(sharp / max(float(np.percentile(sharp, 99)), 1e-6), 0, 1)
    d = 0.55 * fg + 0.25 * (yy / (h - 1)) + 0.20 * sharp
    d = cv2.GaussianBlur(d, (0, 0), w * 0.05)
    lo, hi = float(np.percentile(d, 1)), float(np.percentile(d, 99))
    return np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1).astype(np.float32)




def depth_maps(model, images, out_dir):
    """Depth Anything V2 Small (onnxruntime, CPU) for each still: OUT_DIR/<still sha256>.png, 16-bit, 65535 = near.
    The model's sha256 is checked first (DEPTH_MODEL); run by episode.yml's depth step in its own venv."""
    if file_sha256(model) != DEPTH_MODEL["sha256"]:
        raise SystemExit(f"DEPTH_MODEL_SHA256_MISMATCH {model}")
    import cv2
    import numpy as np
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 4   # fixed: the same maps on every run
    sess = ort.InferenceSession(str(model), opts, providers=["CPUExecutionProvider"])
    name, n = sess.get_inputs()[0].name, DEPTH_MODEL["size"]
    mean, std = np.float32([0.485, 0.456, 0.406]), np.float32([0.229, 0.224, 0.225])
    os.makedirs(out_dir, exist_ok=True)
    done = []
    for image in images:
        rgb = cv2.cvtColor(read_still(image), cv2.COLOR_BGR2RGB)
        x = (cv2.resize(rgb, (n, n), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255 - mean) / std
        d = sess.run(None, {name: x.transpose(2, 0, 1)[None]})[0].reshape(n, n)
        d = cv2.resize(d, (n, max(8, round(n * rgb.shape[0] / rgb.shape[1]))), interpolation=cv2.INTER_CUBIC)
        lo, hi = np.percentile(d, 1), np.percentile(d, 99)
        out = os.path.join(out_dir, file_sha256(image) + ".png")
        cv2.imwrite(out, (np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1) * 65535).astype(np.uint16))
        done.append(out)
    return done


def depth_for(src, frame, depth_png=None):
    """(near/far map at the frame, 1 = near, its source): the model's map when there is one, else depth_proxy."""
    import cv2
    import numpy as np
    if depth_png and os.path.isfile(depth_png):
        d = cv2.imread(str(depth_png), cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535
        d = cv2.resize(d, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_LINEAR)
        return cover(d, frame), "depth-anything-v2-small"
    return cv2.resize(depth_proxy(cover(src, frame)), frame, interpolation=cv2.INTER_LINEAR), "proxy"


def face_detector():
    import cv2
    for d in (getattr(getattr(cv2, "data", None), "haarcascades", None), "/usr/share/opencv4/haarcascades",
              "/usr/share/opencv/haarcascades"):
        p = os.path.join(d or "", "haarcascade_frontalface_default.xml")
        if d and os.path.isfile(p):
            c = cv2.CascadeClassifier(p)
            if not c.empty():
                return c
    return None


def analyse(picture, depth=None, frame=(1920, 1080)):
    """What the director reads in a still (covered to the frame): the subject box (a face, else spectral-residual
    saliency with the near depth), sky, water, fire and darkness. Shares of the picture, from its centre."""
    import cv2
    import numpy as np
    h, w = picture.shape[:2]
    gray = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
    luma = gray.astype(np.float32) / 255
    out = {"faces": 0, "subject_from": "centred"}
    det = face_detector()
    if det is not None:
        k = 640 / w
        g = cv2.equalizeHist(cv2.resize(gray, (640, max(8, round(h * k))), interpolation=cv2.INTER_AREA))
        faces = det.detectMultiScale(g, 1.1, 6, minSize=(max(12, int(g.shape[0] * 0.06)),) * 2)
        faces = sorted((tuple(int(v) for v in f) for f in faces), key=lambda f: (-f[2] * f[3], f))
        out["faces"] = len(faces)
        if faces:
            x, y, fw, fh = (v / k for v in faces[0])
            cx, cy = (x + fw / 2) / w - 0.5, (y + fh / 2) / h - 0.5
            hw = 0.8 * fw / w
            out.update(subject=[cx - hw, cy - fh / h, cx + hw, cy + fh / h], subject_from="face",
                       face=[round(cx, 4), round(cy, 4)])
    if out["subject_from"] != "face":
        sm = cv2.resize(luma, (64, max(8, round(64 * h / w))), interpolation=cv2.INTER_AREA)
        F = np.fft.fft2(sm)
        logamp = np.log(np.abs(F) + 1e-6)
        sal = np.abs(np.fft.ifft2(np.exp(logamp - cv2.blur(logamp, (3, 3)) + 1j * np.angle(F)))) ** 2
        sal = cv2.GaussianBlur(sal.astype(np.float32), (0, 0), 2.5)
        sal = (sal - sal.min()) / max(float(sal.max() - sal.min()), 1e-9)
        if depth is not None:
            sal = 0.6 * sal + 0.4 * cv2.resize(depth, sal.shape[::-1], interpolation=cv2.INTER_AREA)
        top = sal >= np.percentile(sal, 88)
        ys, xs = np.nonzero(top)
        if len(xs) and float(sal[top].mean()) > 1.6 * float(sal.mean()):
            sw, sh = sal.shape[1], sal.shape[0]
            wts = sal[ys, xs]
            cx, cy = float((xs * wts).sum() / wts.sum() + 0.5) / sw - 0.5, float((ys * wts).sum() / wts.sum() + 0.5) / sh - 0.5
            hw = min((np.percentile(xs, 90) - np.percentile(xs, 10)) / sw / 2, SUBJECT_SHARE[0] * band_half(frame))
            hh = min((np.percentile(ys, 90) - np.percentile(ys, 10)) / sh / 2, 0.4)
            out.update(subject=[cx - hw, cy - hh, cx + hw, cy + hh], subject_from="saliency")
    lap = np.abs(cv2.Laplacian(luma, cv2.CV_32F))
    top, low = slice(0, int(h * 0.22)), slice(int(h * 0.7), h)
    out["sky"] = bool(luma[top].mean() > 0.42 and lap[top].mean() < 0.6 * lap.mean())
    gx, gy = np.abs(cv2.Sobel(luma[low], cv2.CV_32F, 1, 0)), np.abs(cv2.Sobel(luma[low], cv2.CV_32F, 0, 1))
    b, r = picture[low][..., 0].mean(), picture[low][..., 2].mean()
    out["water"] = bool(gy.mean() > 1.5 * gx.mean() and b >= 0.95 * r)
    hsv = cv2.cvtColor(picture, cv2.COLOR_BGR2HSV)
    fire = (hsv[..., 0] >= 4) & (hsv[..., 0] <= 24) & (hsv[..., 1] > 140) & (hsv[..., 2] > 190)
    out["fire"] = bool(fire.mean() > 0.004)
    out["dark"] = bool(luma.mean() < 0.3)
    if depth is not None:
        out["depth_spread"] = round(float(depth.std()), 4)
    if "subject" in out:
        out["subject"] = [round(float(v), 4) for v in out["subject"]]
    return out


def analyse_still(image, frame, depth_png=None):
    src = read_still(image)
    depth, kind = depth_for(src, frame, depth_png)
    an = analyse(cover(src, frame), depth if kind != "proxy" else None, frame)
    an["depth"] = kind
    return an


# ---------- the auto-director ----------

EMOTIONS = {   # the plan's mood sentence ("Mocking and uneasy."): words to the need they carry
    "dread": "dread fear fearful afraid terror terrified ominous menace menacing foreboding uneasy doom threat dark",
    "awe": "awe astonished wonder wondering majestic glory glorious holy vast sublime reverent hushed amazed",
    "grief": "grief grieving sorrow sorrowful mourning weeping loss lonely alone despair bereft sad heavy",
    "calm": "calm peace peaceful still quiet tender gentle serene rest restful patient",
    "urgency": "urgent panic panicked chaos frantic fury furious rage violent storm fleeing desperate",
    "joy": "joy joyful relief relieved hope hopeful glad triumph triumphant rejoicing thankful",
    "tension": "mocking heedless defiant scorn scornful tense tension suspicious strange proud",
}
CLIMAX_CLAUSE = re.compile(r"climax([^;]*)")
SHOT_ID = re.compile(r"\b[sk]-[a-z0-9-]+")


def emotion_of(prompt):
    words = re.findall(r"[a-z]+", (prompt or "").lower())
    best, score = "neutral", 0
    for name, lex in EMOTIONS.items():
        n = sum(1 for x in words if x in lex.split())
        if n > score:
            best, score = name, n
    return best


def beats_of(plan):
    """{shot id: (beat, progress)}: hook (the first shot), kjv (a scripture line), climax (named in the plan's beats
    after "climax", else the last scripture shot in the last 45 % before the Keeper), keeper (insight or close),
    aftermath (after the climax), escalation (the rest; progress 0-1 through the story)."""
    shots = [s for s in plan.get("shots") or [] if isinstance(s, dict)]
    narr = plan.get("narration") or []
    n = max(len(shots), 1)

    def kinds(s):
        return {narr[x].get("kind") for x in s.get("lines") or [] if type(x) is int and 0 <= x < len(narr)
                and isinstance(narr[x], dict)}

    keeper = {s.get("id") for s in shots if s.get("kind") == "keeper" or kinds(s) & {"insight", "cta"}}
    kjv = {s.get("id") for s in shots if "scripture" in kinds(s) or s.get("reference") or s.get("speaker") == "god"}
    m = CLIMAX_CLAUSE.search(plan.get("beats") if isinstance(plan.get("beats"), str) else "")
    climax = set(SHOT_ID.findall(m.group(1))) & {s.get("id") for s in shots} if m else set()
    first_keeper = next((i for i, s in enumerate(shots) if s.get("id") in keeper), n)
    if not climax:
        last = [i for i, s in enumerate(shots[:first_keeper]) if s.get("id") in kjv and i >= 0.55 * first_keeper]
        climax = {shots[last[-1]]["id"]} if last else set()
    last_climax = max((i for i, s in enumerate(shots) if s.get("id") in climax), default=n)
    out = {}
    for i, s in enumerate(shots):
        sid = s.get("id")
        beat = ("hook" if i == 0 else "keeper" if sid in keeper else "climax" if sid in climax
                else "aftermath" if i > last_climax else "kjv" if sid in kjv else "escalation")
        out[sid] = (beat, round(i / max(n - 1, 1), 4))
    return out


BEAT_STYLE = {   # beat: (base scores, ease, strength, hold)
    "hook": ({"push_in": 3.0, "pull_back": 2.6, "parallax_2_5d": 2.2, "pan_to_subject": 2.0, "tilt_up": 1.4}, "settle", 1.15, 0.3),
    "escalation": ({"push_in": 2.4, "pan_to_subject": 2.2, "pan_left": 2.0, "pan_right": 2.0, "parallax_2_5d": 2.0,
                    "tilt_up": 1.4, "tilt_down": 1.2, "drift": 1.2, "pull_back": 1.0, "hold_then_push": 1.0},
                   "in_out", 0.85, 0.3),
    "kjv": ({"hold_then_push": 3.4, "push_in": 2.4, "parallax_2_5d": 1.8, "tilt_up": 1.6, "drift": 1.4}, "in_out", 0.9, 0.3),
    "climax": ({"hold_then_push": 3.6, "push_in": 2.8, "tilt_up": 1.6, "parallax_2_5d": 1.6}, "in_out", 1.3, 0.35),
    "keeper": ({"drift": 3.0, "parallax_2_5d": 2.6, "pull_back": 1.6, "push_in": 1.2}, "gentle", 0.6, 0.3),
    "aftermath": ({"pull_back": 3.0, "tilt_down": 2.2, "drift": 2.0, "parallax_2_5d": 1.6}, "settle", 0.8, 0.3),
}
EMOTION_STYLE = {   # emotion: (score changes, ease or None, strength factor)
    "awe": ({"tilt_up": 2.0, "pull_back": 1.5, "parallax_2_5d": 0.5}, None, 1.0),
    "dread": ({"push_in": 1.5, "hold_then_push": 1.0, "drift": 0.5}, "build", 0.9),
    "grief": ({"pull_back": 1.5, "tilt_down": 1.2, "drift": 1.0}, "gentle", 0.8),
    "calm": ({"drift": 1.5, "parallax_2_5d": 1.0}, "gentle", 0.8),
    "urgency": ({"pan_left": 1.5, "pan_right": 1.5, "push_in": 1.0, "pan_to_subject": 0.8}, "settle", 1.15),
    "joy": ({"tilt_up": 1.5, "pull_back": 1.0}, None, 1.0),
    "tension": ({"pan_left": 1.0, "pan_right": 1.0, "push_in": 0.6, "hold_then_push": 0.5}, "build", 1.0),
    "neutral": ({}, None, 1.0),
}
LATERAL = {"pan_left": -1, "pan_right": 1}
PROMPT_CAMERA = ((r"push(ing)?[- ]in|dolly(ing)? in|moves? in", "push_in"), (r"pull(s|ing)?[- ](back|out)|dolly out", "pull_back"),
                 (r"tilt(s|ing)? up|crane up|rises", "tilt_up"), (r"tilt(s|ing)? down", "tilt_down"),
                 (r"pan(s|ning)? left", "pan_left"), (r"pan(s|ning)? right", "pan_right"),
                 (r"tracking|truck(s|ing)?|parallax", "parallax_2_5d"), (r"drift(s|ing)?", "drift"))
SENTENCE = re.compile(r"[^.!?]+[.!?]?")


def own_words(plan):
    """{shot id: its prompt without the sentences most of the plan's prompts share (the style and world lines), so
    the director reads what this shot asks for, not the series' boilerplate."""
    shots = [s for s in plan.get("shots") or [] if isinstance(s, dict)]
    seen = {}
    for s in shots:
        for x in set(t.strip() for t in SENTENCE.findall(s.get("prompt") or "")):
            seen[x] = seen.get(x, 0) + 1
    common = {x for x, n in seen.items() if len(shots) >= 3 and n >= 0.5 * len(shots)}
    return {s.get("id"): " ".join(t.strip() for t in SENTENCE.findall(s.get("prompt") or "") if t.strip() not in common)
            for s in shots}


def mood_of(prompt):
    """The emotion of the mood sentence ("Mocking and uneasy."), else of the whole prompt."""
    short = [t for t in SENTENCE.findall(prompt or "") if 1 <= len(re.findall(r"[a-z]+", t.lower())) <= 4]
    for t in short:
        e = emotion_of(t)
        if e != "neutral":
            return e
    return emotion_of(prompt)


def tiebreak(sid, move):
    return int(hashlib.sha256(f"{sid}|{move}".encode()).hexdigest()[:6], 16) / 16 ** 6 * 0.01


def choose_atmosphere(prompt, emotion, beat, an):
    """Up to three layers the scene asks for: from the prompt's words, the picture (fire, water, sky, darkness) and
    the need (dread and grief haze, the climax and the Keeper a vignette). [(name, why)]."""
    p, an = (prompt or "").lower(), an or {}
    has = lambda pat: re.search(pat, p) is not None  # noqa: E731
    sc = {}
    if has(r"\b(rain|raining|storm|downpour)\b"):
        sc["rain"] = (3.0, "rain in the prompt")
    if has(r"\b(torch|torches|lamp|lamps|candle|candles|firelight|hearth)\b"):
        sc["torch_flicker"] = (2.6 + 0.4 * an.get("fire", False), "a lamp or torch in the prompt")
    if has(r"\b(fire|fires|flame|flames|campfire|burning|embers|altar)\b") or an.get("fire"):
        sc["embers"] = (2.2 if has(r"\b(fire|fires|flame|flames|campfire|burning|embers|altar)\b") else 1.5,
                        "fire in the prompt" if has(r"\bfire|flame|burning|embers|altar") else "fire in the picture")
    if has(r"\b(sea|water|waters|river|flood|waves|lake|deep|shore)\b") and an.get("water", True):
        sc["water_shimmer"] = (2.4 if an.get("water") else 1.2, "water in the prompt" +
                               (" and in the lower frame" if an.get("water") else ""))
    if has(r"\b(mist|fog|haze|smoke|clouds?|dawn)\b") or emotion in ("dread", "grief"):
        sc["mist"] = (2.0 if has(r"\b(mist|fog|haze|smoke)\b") else 1.3, "haze for " + (
            "the prompt's mist or smoke" if has(r"\b(mist|fog|haze|smoke)\b") else emotion))
    if (has(r"\b(sun|sunlight|rays|beams?|heaven|heavens|glory|shaft|dawn)\b") or emotion == "awe") and not an.get("dark"):
        sc["god_rays"] = (1.4 + 0.6 * (emotion == "awe") + 0.4 * an.get("sky", False), "light from above for " + (
            "awe" if emotion == "awe" else "the prompt's light"))
    if has(r"\b(dust|dusty|sand|desert|dry|wind|road|threshing)\b"):
        sc["dust"] = (2.0, "dust or wind in the prompt")
    if beat in ("climax", "kjv", "keeper") or emotion in ("dread", "grief") or an.get("dark"):
        sc["vignette"] = (1.2 + 0.4 * (beat == "climax"), "a breathing vignette for the " + beat if beat in (
            "climax", "kjv", "keeper") else "a breathing vignette for the dark")
    if an.get("dark"):
        sc["film_grain"] = (1.1, "grain holds the dark gradients")
    if "rain" in sc:
        for k in ("dust", "god_rays", "embers"):
            sc.pop(k, None)
    if "mist" in sc:
        sc.pop("dust", None)
    ranked = sorted(sc.items(), key=lambda kv: (-kv[1][0], ATMOSPHERES.index(kv[0])))
    return [(k, why) for k, (v, why) in ranked if v >= 1.0][:ATMOSPHERE_MAX]


def decide(shot, beat, progress, emotion, span, an, prev, frame):
    """One still's move: the beat's style, the emotion's, the span's and the picture's needs scored, the previous
    move never repeated and its family and direction varied; a plan override wins. Returns the direction record."""
    sid = shot.get("id")
    an = an or {}
    base, ez, strength, hold = BEAT_STYLE[beat]
    emo, emo_ease, emo_k = EMOTION_STYLE.get(emotion, EMOTION_STYLE["neutral"])
    score = {m: base.get(m, 0.6) + emo.get(m, 0.0) for m in MOTIONS if m != "hold"}
    why = [f"beat {beat}", f"emotion {emotion}", f"span {span:g} s"]
    asked = next((m for pat, m in PROMPT_CAMERA if re.search(r"\b" + pat, (shot.get("prompt") or "").lower())), None)
    if asked:
        score[asked] += 2.0
        why.append(f"the prompt names {asked}")
    off = an.get("face") and math.hypot(*an["face"]) > 0.05
    if an.get("subject_from") == "face":
        score["pan_to_subject"] += 2.0 if off else 0.4
        score["push_in"] += 0.5
        why.append("a face " + ("off centre: the pan lands on it" if off else "found: the push closes on it"))
    if an.get("depth") == "depth-anything-v2-small" and an.get("depth_spread", 0) > 0.22:
        score["parallax_2_5d"] += 1.5
        why.append("clear near/far depth: parallax")
    elif an.get("depth") == "proxy":
        score["parallax_2_5d"] -= 0.6
    if an.get("sky"):
        score["tilt_up"] += 0.8
    if span < 7:
        score["hold_then_push"] -= 2.0
        score["parallax_2_5d"] -= 0.5
    elif span >= 14:
        for m in ("hold_then_push", "parallax_2_5d", "drift"):
            score[m] += 0.5
    last = prev[-1] if prev else None
    if last:
        score.pop(last["move"], None)
        for m in score:
            score[m] -= 1.5 if FAMILY[m] == FAMILY[last["move"]] else 0.0
            score[m] -= 0.75 if len(prev) > 1 and m == prev[-2]["move"] else 0.0
        if last.get("dir") in (-1, 1):
            for m, d in LATERAL.items():
                if m in score and d == last["dir"]:
                    score[m] -= 0.8
    ranked = sorted(score, key=lambda m: (-(score[m] + tiebreak(sid, m)), m))
    move, source = ranked[0], "director"
    o = shot.get("motion")
    if o is not None:
        move, source = override_move(o), "override"
        why = [f"plan override {move}"] + why
    elif last:
        why.append(f"after {last['move']}: varied")
    ez = emo_ease if emo_ease and beat not in ("keeper", "climax") else ez
    if move == "pan_to_subject":
        ez = "settle"
    elif move in ("drift", "parallax_2_5d") and beat != "hook":
        ez = "gentle"
    strength = strength * emo_k * min(max(span / 15, 0.55), 1.15) * (1 + 0.3 * progress * (beat == "escalation"))
    if isinstance(o, dict):
        ez, hold = o.get("ease", ez), o.get("hold", hold)
        strength = o.get("strength", strength)
    strength = round(min(max(strength, STRENGTH_RANGE[0]), STRENGTH_RANGE[1]), 4)
    direction = -last["dir"] if last and last.get("dir") in (-1, 1) else (1 if tiebreak(sid, "dir") < 0.005 else -1)
    if move in LATERAL:
        direction = LATERAL[move]
    keys, sub, used = build_keys(move, frame, an.get("subject"), strength, ez, hold, direction)
    if used < strength:
        why.append("made smaller to keep the subject in the 9:16 band" if used else "held: no room for a move")
    if an.get("subject") and list(sub) != list(an["subject"]):
        why.append("subject wider than the band: centred")
    if shot.get("atmosphere") is not None:
        atmos = [(a, "plan override") for a in shot["atmosphere"]]
    else:
        atmos = choose_atmosphere(shot.get("prompt"), emotion, beat, an)
    return {"engine": ENGINE, "move": move, "source": source, "ease": ez, "strength": used,
            "hold": hold if move == "hold_then_push" else None, "dir": direction,
            "atmosphere": [a for a, _ in atmos], "atmosphere_why": [w for _, w in atmos],
            "beat": beat, "emotion": emotion, "span": round(float(span), 3), "reason": "; ".join(why),
            "subject": [round(float(v), 4) for v in sub], "subject_from": an.get("subject_from", "centred"),
            "depth": an.get("depth"), "keys": keys,
            "seed": int(hashlib.sha256(str(sid).encode()).hexdigest()[:8], 16)}


def plan_frame(plan):
    return (1920, 1080) if plan.get("aspect_ratio") == "16:9" else (1080, 1920)


def direct(plan, ids, spans=None, analyses=None, frame=None):
    """The director over a plan, in shot order: {shot id: direction} for the still shots `ids`. spans: the spoken
    span of each (the build's layout; else the shot's seconds); analyses: what analyse_still read in each still
    (none at plan_check: the plan's words alone)."""
    frame = tuple(frame or plan_frame(plan))
    beats, words = beats_of(plan), own_words(plan)
    out, prev = {}, []
    for s in plan.get("shots") or []:
        if not isinstance(s, dict) or s.get("id") not in ids:
            continue
        sid = s["id"]
        span = float((spans or {}).get(sid) or s.get("seconds") or 8)
        beat, progress = beats.get(sid, ("escalation", 0.5))
        shot = dict(s, prompt=words.get(sid, s.get("prompt")))
        d = decide(shot, beat, progress, mood_of(shot["prompt"]), span, (analyses or {}).get(sid), prev, frame)
        out[sid] = d
        prev.append(d)
    return out
class Atmosphere:
    """Procedural overlays (no stock files), seeded, so the same still and plan give the same frames. Light and haze
    (mist, god rays, torch flicker, the vignette, the water's glints) are smooth fields, solved at a quarter of the
    frame and applied as one gain and one offset; particles (dust, embers, rain) move on continuous paths drawn at
    1/16-pixel precision (cv2 shift), so nothing steps; grain is a fixed bank of plates."""

    def __init__(self, names, size, fps, seed=0):
        import cv2
        import numpy as np
        self.names, (self.w, self.h), self.fps = tuple(names or ()), size, fps
        r, w, h = np.random.default_rng(seed), self.w, self.h
        self.k = k = w / 1920
        self.lo = lw, lh = max(16, w // 4), max(9, h // 4)
        ly, lx = np.mgrid[0:lh, 0:lw].astype(np.float32)
        ly, lx = (ly + 0.5) * h / lh, (lx + 0.5) * w / lw   # quarter-frame cells in output pixels
        if "dust" in self.names:
            n = 140
            self.dust = dict(p=r.random((n, 2)) * (w, h), v=(r.random((n, 2)) - 0.5) * (14 * k, 8 * k) + (3 * k, 2 * k),
                             z=r.random(n), ph=r.random(n) * 6.283, f=0.3 + r.random(n) * 0.6)
        if "embers" in self.names:
            n = 70
            self.embers = dict(p=r.random((n, 2)) * (w, h), vy=-(28 + r.random(n) * 46) * k,
                               sw=(6 + r.random(n) * 14) * k, z=r.random(n), ph=r.random(n) * 6.283,
                               f=0.4 + r.random(n) * 1.2)
        if "rain" in self.names:
            n = 320
            self.rain = dict(p=r.random((n, 2)) * (w, h), v=(1.25 + r.random(n) * 0.5) * h,
                             ln=(16 + r.random(n) * 26) * k, a=0.12 + r.random(n) * 0.25)
        if "mist" in self.names:   # two octaves of soft noise, wider than the frame so it can drift
            tex = np.zeros((lh, int(lw * 1.6)), np.float32)
            for cell, amp in ((max(2, lw // 7), 0.65), (max(2, lw // 22), 0.35)):
                g = r.random((lh // cell + 3, tex.shape[1] // cell + 3)).astype(np.float32)
                big = cv2.resize(g, ((tex.shape[1] // cell + 3) * cell, (lh // cell + 3) * cell),
                                 interpolation=cv2.INTER_CUBIC)
                tex += amp * big[cell:cell + lh, cell:cell + tex.shape[1]]
            tex = cv2.GaussianBlur(tex, (0, 0), lw / 90)
            self.mist = (tex - tex.min()) / max(float(tex.max() - tex.min()), 1e-6)
            self.mist_ramp = np.clip((ly / h - 0.25) / 0.75, 0, 1) ** 1.3
        if "god_rays" in self.names:   # shafts from a source above the frame
            sx, sy = w * (0.35 + 0.3 * r.random()), -0.25 * h
            self.ray_idx = np.clip((np.arctan2(ly - sy, lx - sx) / np.pi * 4096).astype(np.int32), 0, 4095)
            self.ray_fall = np.exp(-((np.hypot(lx - sx, ly - sy) / h - 0.25) / 1.1) ** 2).astype(np.float32)
            self.ray_waves = [(int(f), r.random() * 6.283, 0.15 + 0.35 * r.random()) for f in r.integers(18, 70, 6)]
        if "water_shimmer" in self.names:
            self.water = np.clip((ly - 0.68 * h) / (0.1 * h), 0, 1)
            self.wy, self.wx = ly, lx
            self.wgrid = np.mgrid[int(h * 0.68):h, 0:w].astype(np.float32)
        if "vignette" in self.names:
            self.rad = ((((lx - w / 2) / (w / 2)) ** 2 + ((ly - h / 2) / (h / 2)) ** 2) / 2) ** 1.1
        if "film_grain" in self.names:
            self.grain = [cv2.GaussianBlur(r.standard_normal((h, w)).astype(np.float32), (0, 0), 0.6) * 5.5
                          for _ in range(8)]
            self.grain_order = r.permutation(8)
        self.flick = r.random(3) * 6.283

    def light(self, t):
        """(gain, offset) at a quarter of the frame, 3 channels, 0-255 scale: out = in * gain + offset."""
        import cv2
        import numpy as np
        lw, lh = self.lo
        gain, off = np.ones((lh, lw, 3), np.float32), np.zeros((lh, lw, 3), np.float32)
        k = self.k
        if "water_shimmer" in self.names:   # glints running across the lower third
            g = np.clip(np.sin(self.wx * 0.012 / k + self.wy * 0.09 / k - 2.4 * t)
                        * np.sin(self.wx * 0.0047 / k - 0.9 * t)
                        * np.sin(self.wx * 0.0031 / k - self.wy * 0.021 / k + 0.6 * t), 0, 1) ** 6
            off += (18 * g * self.water)[..., None]
        if "mist" in self.names:   # drifting sideways, thicker low in the frame
            m = cv2.warpAffine(self.mist, np.float32([[1, 0, 9 * k * t * lw / self.w], [0, 1, 0]]), (lw, lh),
                               flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            a = ((0.12 + 0.30 * self.mist_ramp) * (0.55 + 0.45 * m))[..., None]
            gain *= 1 - a
            off = off * (1 - a) + a * np.float32([204, 204, 199])
        if "god_rays" in self.names:   # swaying and breathing slowly; screen-blended, warm (BGR)
            th = np.arange(4096, dtype=np.float32) / 4096 * np.pi
            prof = sum(a * (0.5 + 0.5 * np.cos(fq * th + ph + 0.35 * np.sin(0.21 * t + ph)))
                       for fq, ph, a in self.ray_waves)
            prof = np.clip(prof / max(float(prof.max()), 1e-6), 0, 1) ** 3 * (0.85 + 0.15 * np.sin(0.4 * t))
            ray = (prof[self.ray_idx] * self.ray_fall * 0.16)[..., None] * np.float32([0.80, 0.93, 1.0])
            gain *= 1 - ray
            off = off * (1 - ray) + 255 * ray
        if "torch_flicker" in self.names:   # a warm gain breathing irregularly (three incommensurate sines)
            p = self.flick
            g = 1 + 0.035 * np.sin(2 * np.pi * 1.3 * t + p[0]) + 0.02 * np.sin(2 * np.pi * 2.9 * t + p[1]) \
                + 0.012 * np.sin(2 * np.pi * 4.7 * t + p[2])
            gain *= np.float32([g * 0.97, g, g * 1.03])
        if "rain" in self.names:
            gain *= 0.93
        if "vignette" in self.names:   # a soft edge darkening that breathes over ~9 s
            v = (1 - (0.20 + 0.04 * np.sin(2 * np.pi * t / 9.0)) * self.rad)[..., None]
            gain *= v
            off *= v
        return gain.astype(np.float32), off.astype(np.float32)

    def particles(self, t):
        """The particle layer at full size (uint8), or None."""
        import cv2
        import numpy as np
        if not {"dust", "embers", "rain"} & set(self.names):
            return None
        w, h, k, S = self.w, self.h, self.k, 16
        layer = np.zeros((h, w, 3), np.uint8)
        if "dust" in self.names:   # motes drifting and turning in the light
            d = self.dust
            pos = d["p"] + d["v"] * t + np.stack([np.sin(d["ph"] + t * d["f"]),
                                                  np.cos(d["ph"] * 1.3 + t * d["f"])], 1) * 6 * k
            for (x, y), z, ph, fr in zip(pos, d["z"], d["ph"], d["f"]):
                a = (0.25 + 0.45 * z) * (0.65 + 0.35 * np.sin(ph + t * fr * 1.7))
                cv2.circle(layer, (int((x % w) * S), int((y % h) * S)), int((0.8 + 2.0 * z) * k * S),
                           (205 * a, 228 * a, 250 * a), -1, cv2.LINE_AA, 4)
        if "rain" in self.names:   # thin slanted streaks, falling fast
            r = self.rain
            for (x0, y0), v, ln, a in zip(r["p"], r["v"], r["ln"], r["a"]):
                y = (y0 + v * t) % (h + ln) - ln
                x = (x0 + 0.18 * v * t) % w
                cv2.line(layer, (int(x * S), int(y * S)), (int((x + 0.18 * ln) * S), int((y + ln) * S)),
                         (200 * a, 195 * a, 185 * a), max(1, int(k)), cv2.LINE_AA, 4)
        layer = cv2.GaussianBlur(layer, (0, 0), 1.2 * max(k, 0.5))
        if "embers" in self.names:   # sparks rising and swaying, flickering, with a glow
            e, sparks = self.embers, np.zeros((h, w, 3), np.uint8)
            for (x0, y0), vy, sw, z, ph, fr in zip(e["p"], e["vy"], e["sw"], e["z"], e["ph"], e["f"]):
                x = (x0 + sw * np.sin(ph + t * fr)) % w
                y = (y0 + vy * t) % h
                a = (0.45 + 0.55 * z) * (0.55 + 0.45 * np.sin(ph * 2 + t * fr * 5.0))
                cv2.circle(sparks, (int(x * S), int(y * S)), int((0.9 + 1.6 * z) * k * S),
                           (40 * a, 140 * a, 255 * a), -1, cv2.LINE_AA, 4)
            sparks = cv2.GaussianBlur(sparks, (0, 0), 1.0 * max(k, 0.5))
            glow = cv2.resize(cv2.GaussianBlur(cv2.resize(sparks, (w // 2, h // 2), interpolation=cv2.INTER_AREA),
                                               (0, 0), 2 * max(k, 0.5)), (w, h), interpolation=cv2.INTER_LINEAR)
            layer = cv2.add(layer, cv2.addWeighted(sparks, 1.0, glow, 3.0, 0))
        return layer

    def apply(self, frame, i):
        import cv2
        import numpy as np
        if not self.names:
            return frame
        t, (w, h) = i / self.fps, (self.w, self.h)
        if "water_shimmer" in self.names:   # the lower third ripples a pixel or two, feathered in (maps at half size)
            y0 = int(h * 0.68)
            yy, xx = np.mgrid[y0:h:2, 0:w:2].astype(np.float32)
            amp = 1.6 * self.k * np.clip((yy - y0) / (0.12 * h), 0, 1)
            dy = amp * np.sin(yy * 0.09 / self.k + 2.1 * t) * np.sin(xx * 0.011 / self.k + 0.7 * t)
            dx = 0.6 * amp * np.sin(yy * 0.05 / self.k - 1.3 * t)
            gy, gx = self.wgrid
            mx = gx + cv2.resize(dx, (w, h - y0), interpolation=cv2.INTER_LINEAR)
            my = gy + cv2.resize(dy, (w, h - y0), interpolation=cv2.INTER_LINEAR)
            frame = frame.copy()
            frame[y0:] = cv2.remap(frame, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        gain, off = self.light(t)
        f = frame.astype(np.float32)
        f = cv2.multiply(f, cv2.resize(gain, (w, h), interpolation=cv2.INTER_LINEAR))
        f = cv2.add(f, cv2.resize(off + 0.5, (w, h), interpolation=cv2.INTER_LINEAR))
        p = self.particles(t)
        if p is not None:
            f = cv2.add(f, p.astype(np.float32))
        if "film_grain" in self.names:   # luma grain (about 2 % of the range)
            f += self.grain[self.grain_order[i % 8]][..., None]
        return np.clip(f, 0, 255).astype(np.uint8)




# ---------- the render ----------

class Renderer:
    """One still and its direction: each frame a single resampling of the low-passed 2x master (an affine warp, or
    the 2.5D map for parallax_2_5d), then the atmosphere."""

    def __init__(self, image, direction, frame=(1920, 1080), fps=30, depth_png=None):
        import cv2
        import numpy as np
        self.d, self.frame, self.fps = direction, tuple(frame), fps
        w, h = self.frame
        src = read_still(image)
        self.master = cv2.GaussianBlur(cover(src, (2 * w, 2 * h)), (0, 0), PREFILTER)
        self.atmos = Atmosphere(direction.get("atmosphere"), self.frame, fps, direction.get("seed", 0))
        self.parallax = direction["move"] == "parallax_2_5d"
        if self.parallax:   # anti-tearing: the near region dilated past its silhouette, then blurred wide, so the
            depth, _ = depth_for(src, self.frame, depth_png)   # stretch falls softly in the background, never a rip
            r = max(3, int(0.012 * w) | 1)
            depth = cv2.dilate(depth, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r)))
            self.depth = cv2.GaussianBlur(depth, (0, 0), 0.01 * w)
            self.hx, self.hy = np.meshgrid(np.linspace(0, w - 1, w // 2, dtype=np.float32) - (w - 1) / 2,
                                           np.linspace(0, h - 1, h // 2, dtype=np.float32) - (h - 1) / 2)

    def camera_frame(self, f):
        import cv2
        import numpy as np
        w, h = self.frame
        s, x, y = camera(self.d["keys"], f)
        if not self.parallax:
            # master coordinate = 2 * (X / s + x * w + (w - 1) / 2) + 0.5, X the output pixel from the frame centre
            m = np.float64([[2 / s, 0, 2 * (-(w - 1) / (2 * s) + x * w + (w - 1) / 2) + 0.5],
                            [0, 2 / s, 2 * (-(h - 1) / (2 * s) + y * h + (h - 1) / 2) + 0.5]])
            return cv2.warpAffine(self.master, m, self.frame, flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                                  borderMode=cv2.BORDER_REPLICATE)
        e = ease(self.d["keys"][-1][4], f)
        u, v = self.hx / s + x * w, self.hy / s + y * h   # picture coordinates from its centre (the far plane)
        dd = cv2.remap(self.depth, u + (w - 1) / 2, v + (h - 1) / 2, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_REPLICATE) - 0.5
        grow = 1 + PARALLAX_ZOOM * dd * e
        u = u / grow + PARALLAX_SLIDE * self.d.get("strength", 1.0) * w * dd * (2 * e - 1) * self.d.get("dir", 1)
        v = v / grow
        mx = cv2.resize(2 * (u + (w - 1) / 2) + 0.5, self.frame, interpolation=cv2.INTER_LINEAR)
        my = cv2.resize(2 * (v + (h - 1) / 2) + 0.5, self.frame, interpolation=cv2.INTER_LINEAR)
        return cv2.remap(self.master, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def frames(self, seconds):
        """The clip's frames: the move fitted to the direction's span (the shot's spoken span), then held."""
        n = int(round(seconds * self.fps))
        last = max(1, int(round(min(self.d.get("span") or seconds, seconds) * self.fps)) - 1)
        for i in range(n):
            yield self.atmos.apply(self.camera_frame(min(i / last, 1.0)), i)


def render_direction(image, out, seconds, direction, frame=(1920, 1080), fps=30, depth_png=None):
    """Render a direction to H.264, no audio, bit-exact (the same still and direction give the same sha256). Like
    every intermediate clip (render(intermediate=True)), veryfast at CRF 16: near-transparent, re-encoded at the
    compose."""
    if direction.get("engine") != ENGINE:
        raise SystemExit(f"STILL_MOTION_ENGINE_UNKNOWN {direction.get('engine')!r} ({ENGINE})")
    bad = path_problems(direction["keys"], direction["subject"], frame,
                        parallax_extra(direction["move"], direction.get("strength", 1.0)))
    bad += atmosphere_problems(direction.get("atmosphere"))
    if bad:
        raise SystemExit("; ".join(bad))
    w, h = frame
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s",
                          f"{w}x{h}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf",
                          "16", "-pix_fmt", "yuv420p", "-threads", "4", "-fflags", "+bitexact", "-flags:v", "+bitexact",
                          "-map_metadata", "-1", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in Renderer(image, direction, frame, fps, depth_png).frames(seconds):
            p.stdin.write(f.tobytes())
    finally:
        p.stdin.close()
        err = p.stderr.read().decode(errors="replace")
        p.stderr.close()
        code = p.wait()
    if code:
        raise SystemExit(f"STILL_MOTION_FAILED {err.strip()[-300:]}")
    return out


def direction_for(move, frame=(1920, 1080), seconds=15.0, atmosphere=None, beat="escalation", prompt="", an=None):
    """A direction for one named move (a test, the CLI, the moves sheet): the director with that move as override."""
    shot = {"id": "test", "motion": move, "prompt": prompt, "atmosphere": atmosphere}
    if atmosphere is None:
        shot.pop("atmosphere")
    return decide(shot, beat, 0.5, mood_of(prompt), seconds, an, [], tuple(frame))


def moves_sheet(image, out, frame=(384, 216), atmosphere=None):
    """One JPEG for a reviewer: a row per move, its start, middle and end, the centre 9:16 band marked."""
    import cv2
    import numpy as np
    w, h = frame
    rows = []
    hb = band_half(frame) * w
    for move in MOTIONS:
        r = Renderer(image, direction_for(move, frame, 4.0, atmosphere or []), frame)
        cells = []
        for f in (0.0, 0.5, 1.0):
            c = r.camera_frame(f)
            for xx in (int(w / 2 - hb), int(w / 2 + hb) - 1):
                cv2.line(c, (xx, 0), (xx, h - 1), (90, 90, 90), 1)
            cells.append(np.pad(c, ((2, 2), (2, 2), (0, 0))))
        row = np.hstack(cells)
        cv2.putText(row, move, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(row)
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out
def contact_sheet(video, out, n=8, cols=4, width=480):
    """One JPEG of n frames evenly through the clip, for a reviewer to see the move at a glance (not a review)."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(video)], capture_output=True, text=True, check=True).stdout.strip())
    rows = -(-n // cols)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-vf",
                    f"fps={n / dur:.6f},scale={width}:-2,tile={cols}x{rows}:padding=4:color=black", "-frames:v", "1",
                    "-q:v", "3", str(out)], check=True)
    return out




if __name__ == "__main__":
    a = sys.argv
    if len(a) >= 6 and a[1] == "cinematic":
        size = tuple(int(v) for v in a[7].split("x")) if len(a) > 7 else (1920, 1080)
        atm = [x for x in a[6].split(",") if x] if len(a) > 6 else []
        render_direction(a[2], a[3], float(a[4]), direction_for(a[5], size, float(a[4]), atm), size)
    elif len(a) >= 5 and a[1] == "depth":
        print("\n".join(depth_maps(a[2], a[4:], a[3])))
    elif len(a) == 4 and a[1] == "moves":
        moves_sheet(a[2], a[3])
    elif len(a) == 4 and a[1] == "sheet":
        contact_sheet(a[2], a[3])
    else:
        render(a[1], a[2], float(a[3]), a[4])
