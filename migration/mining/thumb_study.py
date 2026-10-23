#!/usr/bin/env python3
"""Thumbnail study: what the thumbnails of breakout videos share that the dead ones do not (2026-10-23).

Input: rows.json of the algorithm study (811 videos; ratio = views / own channel median).
For each video it downloads the public hqdefault thumbnail, measures it, and then tests every
feature inside the same channel and month (Mantel-Haenszel odds ratio, permutation p-value),
exactly like the title study (perm.py). It also writes contact sheets of hits and dead videos so
the pictures can be looked at, not only measured.

Usage: thumb_study.py ROWS_JSON OUT_DIR
Writes OUT_DIR/thumbs.json, OUT_DIR/thumb_perm.json, OUT_DIR/sheet-hit-N.jpg, OUT_DIR/sheet-dead-N.jpg.
"""
import io
import json
import random
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HIT, DEAD = 3.0, 0.5
TILE = (320, 180)
COLS, ROWS_PER_SHEET = 6, 8


def fetch(vid):
    for _ in range(3):
        try:
            with urllib.request.urlopen(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", timeout=20) as r:
                return Image.open(io.BytesIO(r.read())).convert("RGB")
        except Exception as e:  # noqa: BLE001 - network: retry, then record the type only
            err = type(e).__name__
            time.sleep(2)
    raise RuntimeError(err)


def crop_letterbox(img):
    """hqdefault is 480x360 with black bars around a 16:9 picture: keep the 480x270 middle."""
    w, h = img.size
    ch = round(w * 9 / 16)
    top = (h - ch) // 2
    return img.crop((0, top, w, top + ch))


def measure(img, faces=None, words=None):
    a = np.asarray(img.resize((320, 180)), dtype=np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(axis=2), a.min(axis=2)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    rg, yb = r - g, 0.5 * (r + g) - b
    colourful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    gy, gx = np.gradient(lum)
    edges = float((np.hypot(gx, gy) > 0.08).mean())
    warm = float(((r > b + 0.08) & (mx > 0.25)).mean())
    blue = float(((b > r + 0.08) & (mx > 0.15)).mean())
    m = {"brightness": float(lum.mean()), "contrast": float(lum.std()), "saturation": float(sat.mean()),
         "colourfulness": colourful, "edge_density": edges, "warm_share": warm, "blue_share": blue,
         "dark_share": float((lum < 0.15).mean()), "bright_share": float((lum > 0.85).mean()),
         "yellow_text_like": float(((r > 0.8) & (g > 0.7) & (b < 0.35)).mean())}
    if faces is not None:
        m["faces"] = faces
    if words is not None:
        m["ocr_words"] = words
    return m


def faces_and_words(img):
    """Optional detectors: OpenCV Haar faces and Tesseract word count. Absent tools give None."""
    faces = words = None
    try:
        import cv2
        grey = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = int(len(casc.detectMultiScale(grey, 1.1, 5, minSize=(30, 30))))
    except Exception:  # noqa: BLE001
        pass
    try:
        import pytesseract
        txt = pytesseract.image_to_string(img.resize((960, 540)))
        words = len([w for w in txt.split() if sum(c.isalpha() for c in w) >= 2])
    except Exception:  # noqa: BLE001
        pass
    return faces, words


FEATURES = {
    "bright (mean luminance > 0.45)": lambda m: m["brightness"] > 0.45,
    "dark (mean luminance < 0.30)": lambda m: m["brightness"] < 0.30,
    "high contrast (std > 0.25)": lambda m: m["contrast"] > 0.25,
    "saturated (mean sat > 0.45)": lambda m: m["saturation"] > 0.45,
    "very colourful (> 0.35)": lambda m: m["colourfulness"] > 0.35,
    "busy (edge density > 0.12)": lambda m: m["edge_density"] > 0.12,
    "warm dominant (warm share > 0.5)": lambda m: m["warm_share"] > 0.5,
    "blue dominant (blue share > 0.4)": lambda m: m["blue_share"] > 0.4,
    "yellow text-like pixels (> 2 %)": lambda m: m["yellow_text_like"] > 0.02,
    "a face": lambda m: (m.get("faces") or 0) >= 1,
    "text, 1-4 words": lambda m: m.get("ocr_words") is not None and 1 <= m["ocr_words"] <= 4,
    "text, 5+ words": lambda m: (m.get("ocr_words") or 0) >= 5,
    "no text": lambda m: m.get("ocr_words") == 0,
}


def mh_perm(rows, metrics, n=2000, seed=7):
    strata = defaultdict(list)
    for r in rows:
        if r["id"] in metrics:
            strata[(r["ch"], r["pub"][:7])].append(r)
    strata = {k: v for k, v in strata.items() if len(v) >= 2}
    hit = lambda r: r["ratio"] >= HIT  # noqa: E731
    dead = lambda r: r["ratio"] <= DEAD  # noqa: E731

    def mh(flags, outc):
        num = den = 0.0
        for k, rs in strata.items():
            fl = flags[k]
            a = sum(1 for r, f in zip(rs, fl) if f and outc(r))
            b = sum(1 for r, f in zip(rs, fl) if f and not outc(r))
            c = sum(1 for r, f in zip(rs, fl) if not f and outc(r))
            d = sum(1 for r, f in zip(rs, fl) if not f and not outc(r))
            t = a + b + c + d
            num += a * d / t
            den += b * c / t
        return num / den if den else float("inf")

    rnd = random.Random(seed)
    out = []
    for name, f in FEATURES.items():
        flags = {k: [bool(f(metrics[r["id"]])) for r in rs] for k, rs in strata.items()}
        nf = sum(sum(v) for v in flags.values())
        res = {"feature": name, "n_with": nf}
        for label, outc in (("hit", hit), ("dead", dead)):
            obs = mh(flags, outc)
            ge = 0
            for _ in range(n):
                o = mh({k: rnd.sample(v, len(v)) for k, v in flags.items()}, outc)
                if (obs >= 1 and o >= obs) or (obs < 1 and o <= obs):
                    ge += 1
            res[f"or_{label}"] = None if obs == float("inf") else round(obs, 3)
            res[f"p_{label}"] = round((ge + 1) / (n + 1), 4)
        out.append(res)
    return {"strata": len(strata), "videos": sum(len(v) for v in strata.values()), "features": out}


def sheets(rows, images, out, label, pick):
    chosen = sorted((r for r in rows if pick(r) and r["id"] in images), key=lambda r: -r["ratio"] if label == "hit" else r["ratio"])
    per = COLS * ROWS_PER_SHEET
    names = []
    for s in range(0, len(chosen), per):
        page = chosen[s:s + per]
        sheet = Image.new("RGB", (COLS * TILE[0], ((len(page) + COLS - 1) // COLS) * (TILE[1] + 18)), "white")
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(page):
            x, y = (i % COLS) * TILE[0], (i // COLS) * (TILE[1] + 18)
            sheet.paste(images[r["id"]].resize(TILE), (x, y))
            d.text((x + 3, y + TILE[1] + 2), f"{r['ratio']:.2f}x {r['ch'][:22]} {r['min']:.0f}m", fill="black")
        name = f"sheet-{label}-{s // per + 1}.jpg"
        sheet.save(out / name, quality=82)
        names.append(name)
    return names


def main(rows_path, out_dir):
    rows = json.load(open(rows_path))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    metrics, images, failed = {}, {}, {}
    for r in rows:
        try:
            img = crop_letterbox(fetch(r["id"]))
        except RuntimeError as e:
            failed[r["id"]] = str(e)
            continue
        images[r["id"]] = img
        metrics[r["id"]] = measure(img, *faces_and_words(img))
    json.dump({"measured": len(metrics), "failed": failed, "metrics": metrics}, open(out / "thumbs.json", "w"), indent=1)
    perm = mh_perm(rows, metrics)
    names = sheets(rows, images, out, "hit", lambda r: r["ratio"] >= HIT) + \
        sheets(rows, images, out, "dead", lambda r: r["ratio"] <= DEAD)
    perm["sheets"] = names
    json.dump(perm, open(out / "thumb_perm.json", "w"), indent=1)
    print(json.dumps({"measured": len(metrics), "failed": len(failed), "sheets": len(names)}))
    for f in sorted(perm["features"], key=lambda f: min(f["p_hit"], f["p_dead"])):
        print(f"{f['feature']:36} n={f['n_with']:4} OR_hit={f['or_hit']} p={f['p_hit']} OR_dead={f['or_dead']} p={f['p_dead']}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
