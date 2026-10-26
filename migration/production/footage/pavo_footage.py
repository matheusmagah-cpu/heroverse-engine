#!/usr/bin/env python3
"""Pavo AI clips for the long (owner, 2026-10-25, DECISIONS.md "Pavo is the first source of AI video": ~50 % Pavo,
~50 % licensed footage). A Pavo clip is a 1280x720 24 fps Agnes Video Flash MP4 with an unwanted AAC track; here it
becomes a library clip exactly like footage.py's: 2560x1440 30 fps H.264 crf 18, no audio, recorded in
library/<id>.json with its sha256, released through ci/assets.sh by pavo-footage.yml.

The 1440p picture comes from AI super-resolution, never a plain resize (owner, 2026-10-23): every native frame goes
through Real-ESRGAN general x4v3 on CPU (the stills' model, weights and code: imagegen/upscale.py). Measured on a
real Pavo clip (921,600 px a frame, as 1280x720), 4 CPU threads of a 2.8 GHz Xeon, 2026-10-25: 4x of the full frame
costs ~12 s a frame (6 s at 24 fps = 144 frames, ~29 min a clip); 4x of the frame area-downscaled to 640x360 lands on
exactly 2560x1440 at ~2.7 s a frame for the model alone, and this whole command took 543 s for a 6 s clip (download
excluded, decode + model + x264 encode, on a host with other load), so that is the path (under the ~10 min budget of
a GitHub runner). Frames are upscaled at the native 24 fps and only then converted to 30 fps (fps filter, no
interpolated frames), which saves a fifth of the work.

Nothing here publishes. The record starts with vetting PENDING: Claude reviews the frame sheet and sets APPROVED in a
later PR (script_check refuses a clip that is not APPROVED).

usage:
  pavo_footage.py plan LIST.json [LIBRARY]                ids of LIST not yet in the library, as a JSON list
  pavo_footage.py make LIST.json ID OUT_DIR WEIGHTS.pth   download, strip audio, upscale; OUT_DIR/ID.mp4 + ID.json
LIST.json is a list of {id, conversation_id, url, prompt, words} (or {"clips": [...]}).
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "imagegen"))
import upscale  # noqa: E402  (Real-ESRGAN tiles, weights URL and hash: one copy for stills and Pavo clips)

W, H, FPS = 2560, 1440, 30
PICTURE = f"{W}x{H} {FPS} fps H.264 crf 18, no audio"   # = footage.py
SR_IN = (W // 4, H // 4)    # the model's native 4x lands on the frame: 640x360 -> 2560x1440
MIN_SOURCE = (1280, 720)    # a Pavo long clip is 720p 16:9; anything smaller would be blown up further
MAX_BYTES = 200 * 1024 * 1024
URL = re.compile(r"^https://cos-aigc-default\.agnes-ai\.space/(?!.*\.\.)[A-Za-z0-9._~/-]+\.mp4$")
ID = re.compile(r"^pavo-[a-z0-9][a-z0-9-]{1,70}$")
LICENCE = "Pavo generated (owner-owned)"
LICENCE_URL = "https://app.pavo-ai.work/terms"
CREDIT = "AI video: Pavo (Agnes Video Flash), owner-owned output"
UA = {"User-Agent": "HeroVerse/1.0 (https://github.com/matheusmagah-cpu/heroverse-engine; pavo footage)"}
LIBRARY = Path(__file__).resolve().parent / "library"


def url_ok(url):
    """Only the Pavo CDN, https, an .mp4 path, no query string, fragment, credentials or port."""
    return isinstance(url, str) and bool(URL.fullmatch(url))   # fullmatch: "$" alone lets a trailing newline through


def entries(list_path):
    data = json.loads(Path(list_path).read_text())
    items = data.get("clips") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise SystemExit("PAVO_LIST_EMPTY")
    seen, problems = set(), []
    for e in items:
        cid = e.get("id") if isinstance(e, dict) else None
        if not isinstance(cid, str) or not ID.fullmatch(cid):
            problems.append(f"PAVO_BAD_ID {cid!r}")
            continue
        if cid in seen:
            problems.append(f"PAVO_DUPLICATE_ID {cid}")
        seen.add(cid)
        if not url_ok(e.get("url")):
            problems.append(f"PAVO_URL_REFUSED {cid}")
        for k in ("conversation_id", "prompt", "words"):
            if not isinstance(e.get(k), str) or not e[k].strip():
                problems.append(f"PAVO_MISSING_{k.upper()} {cid}")
    if problems:
        raise SystemExit("\n".join(problems))
    return {e["id"]: e for e in items}


def plan(list_path, library=LIBRARY):
    have = {p.stem for p in Path(library).glob("*.json")}
    return [cid for cid in entries(list_path) if cid not in have]


def download(url, dst):
    if not url_ok(url):
        raise SystemExit("PAVO_URL_REFUSED")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        if not url_ok(r.geturl()):   # a redirect off the Pavo CDN is refused too
            raise SystemExit("PAVO_URL_REFUSED (redirect)")
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise SystemExit("PAVO_TOO_LARGE")
    Path(dst).write_bytes(data)


def probe(path):
    """(width, height, fps, seconds, has_audio) of a video file."""
    out = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                     "stream=codec_type,width,height,avg_frame_rate:format=duration", "-of", "json",
                                     str(path)], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
    return (v["width"], v["height"], num / den if den else 0.0, float(out["format"]["duration"]),
            any(s["codec_type"] == "audio" for s in out["streams"]))


def real_esrgan(weights):
    """A frame function (uint8 360x640x3 -> uint8 1440x2560x3) running Real-ESRGAN general x4v3 on CPU."""
    if upscale.sha256(weights) != upscale.WEIGHTS_SHA256:
        raise SystemExit("WEIGHTS_SHA256_MISMATCH")
    import numpy as np
    import torch
    from spandrel import ModelLoader
    torch.set_num_threads(4)
    desc = ModelLoader().load_from_file(weights).eval()
    if desc.scale != 4:
        raise SystemExit(f"MODEL_SCALE {desc.scale}")
    net = desc.model.to(memory_format=torch.channels_last)   # measured 1.7x faster on CPU than the default layout

    def model(t):
        return net(t.contiguous(memory_format=torch.channels_last))

    def frame(img):
        out = upscale.sr(model, img.astype(np.float32) / 255, 4)
        return (out * 255 + 0.5).astype(np.uint8)
    return frame


def render(src, dst, frame_fn):
    """Every native frame of SRC (area-downscaled to 640x360, audio dropped) through FRAME_FN, then 30 fps H.264
    crf 18 yuv420p without audio. Returns the source (width, height, fps, seconds)."""
    w, h, fps, seconds, _ = probe(src)
    if w < MIN_SOURCE[0] or h < MIN_SOURCE[1] or w * 9 != h * 16:
        raise SystemExit(f"PAVO_SOURCE_NOT_720P_16_9 {w}x{h}")
    iw, ih = SR_IN
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", str(src), "-an", "-map", "0:v:0",
                            "-vf", f"scale={iw}:{ih}:flags=area", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-framerate", f"{fps:.6f}", "-i", "-", "-an", "-vf", f"fps={FPS},format=yuv420p",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(FPS),
                            "-movflags", "+faststart", str(dst)], stdin=subprocess.PIPE)
    import numpy as np
    size, n = iw * ih * 3, 0
    try:
        while True:
            buf = dec.stdout.read(size)
            if len(buf) < size:
                break
            out = frame_fn(np.frombuffer(buf, np.uint8).reshape(ih, iw, 3))
            if out.shape != (H, W, 3) or out.dtype != np.uint8:
                raise SystemExit(f"UPSCALE_SHAPE {out.shape} {out.dtype}")
            enc.stdin.write(out.tobytes())
            n += 1
            if n % 24 == 0:
                print(json.dumps({"frames": n}), flush=True)
    finally:
        enc.stdin.close()
        dec.stdout.close()
    if dec.wait() or enc.wait() or n == 0:
        raise SystemExit(f"PAVO_RENDER_FAILED frames={n}")
    ow, oh, ofps, _, audio = probe(dst)
    if (ow, oh) != (W, H) or round(ofps) != FPS or audio:
        raise SystemExit(f"PAVO_OUTPUT_SPEC {ow}x{oh} {ofps} fps audio={audio}")
    return w, h, fps, seconds


def record(e, dst, source, upscaler):
    w, h, fps, seconds = source
    return {"id": e["id"], "theme": "pavo", "query": e["words"], "source": "pavo", "title": e["prompt"][:120],
            "page": e["url"], "author": "Pavo (Agnes Video Flash)", "licence_url": LICENCE_URL, "licence": LICENCE,
            "licence_as_published": "Pavo Terms of Service: the user keeps ownership of generated content (§42)",
            "source_seconds": round(seconds, 3), "source_height": h, "source_width": w, "source_fps": round(fps, 3),
            "start": 0.0, "seconds": round(probe(dst)[3], 3), "credit": CREDIT, "picture": PICTURE, "frame": [W, H],
            "sha256": hashlib.sha256(Path(dst).read_bytes()).hexdigest(),
            "conversation_id": e["conversation_id"], "prompt": e["prompt"], "words": e["words"],
            "upscaler": upscaler, "vetting": "PENDING",
            "vetting_note": "Claude reviews the frame sheet (library/sheets/pavo-<run>.jpg) and sets APPROVED in a later PR",
            "release_asset": None, "release_tag": None}


def make(list_path, cid, out_dir, weights, frame_fn=None, fetch=download):
    e = entries(list_path).get(cid)
    if e is None:
        raise SystemExit(f"PAVO_ID_NOT_IN_LIST {cid}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw, dst = out / f"{cid}.src.mp4", out / f"{cid}.mp4"
    fetch(e["url"], raw)
    try:
        if frame_fn is None:
            frame_fn = real_esrgan(weights)
            upscaler = {"model": "Real-ESRGAN general x4v3 (4x of every native frame area-downscaled to 640x360, "
                                 "then 30 fps)", "licence": "bsd-3-clause", "weights_sha256": upscale.WEIGHTS_SHA256,
                        "source": upscale.WEIGHTS_URL}
        else:
            upscaler = {"model": "stub (tests only)", "licence": "bsd-3-clause", "source": upscale.WEIGHTS_URL}
        source = render(raw, dst, frame_fn)
    finally:
        raw.unlink(missing_ok=True)
    rec = record(e, dst, source, upscaler)
    (out / f"{cid}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    return rec


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "plan":
        print(json.dumps(plan(*sys.argv[2:4])))
    elif len(sys.argv) == 6 and sys.argv[1] == "make":
        r = make(*sys.argv[2:6])
        print(json.dumps({"made": r["id"], "sha256": r["sha256"], "seconds": r["seconds"]}))
    else:
        raise SystemExit(__doc__)
