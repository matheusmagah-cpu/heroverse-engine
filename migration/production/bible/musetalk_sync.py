#!/usr/bin/env python3
"""Re-sync the Keeper's lips to OUR narration line with MuseTalk 1.5 (owner, 2026-10-26: "sincronize a fala do
guardião com a narração"; MIT, https://github.com/TMElyralab/MuseTalk, CPU, 0 credits).

Input: a silent Keeper clip (plan B, mouth closed, still-mouth probes) and the line's Kokoro WAV. MuseTalk repaints only
the lower half of the face from the audio (one UNet pass per frame over sd-vae-ft-mse latents, whisper-tiny audio
features); the rest of the frame is the Pavo clip unchanged. The audio is never stretched: the output lasts exactly the
WAV, and the clip's frames are cycled forward and back if the clip is shorter.

Differences from MuseTalk's scripts/inference.py (so no mmpose/DWPose and no face-parsing weights are needed): the face
box comes from our pinned MediaPipe face landmarker (the 68-point rule of MuseTalk's preprocessing mapped to MediaPipe
points: x from the face oval, y2 the chin + 10 px, y1 = nose bridge - (chin - nose bridge)), smoothed over time; the
paste mask is the lower face oval under the nose tip, feathered.

usage: musetalk_sync.py --musetalk DIR --models DIR --face-model face_landmarker.task CLIP.mp4 LINE.wav OUT.mp4
       (models: musetalkV15/{unet.pth,musetalk.json}, sd-vae/, whisper/ as MuseTalk's download_weights.sh lays them)
"""
import argparse
import json
import math
import subprocess
import sys
import time

import numpy as np

OVAL_LOWER = [234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323, 454]
OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149,
        150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
LIPS_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185]
CHIN, NOSE_BRIDGE, NOSE_TIP = 152, 195, 1
EXTRA_MARGIN = 10


def read_frames(path):
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    return frames, fps


def landmarks(frames, fps, model):
    import mediapipe as mp
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from lipsync_check import landmarker
    from mediapipe.tasks.python import vision
    lm = landmarker(model, vision.RunningMode.VIDEO)
    out = []
    for i, f in enumerate(frames):
        rgb = f[:, :, ::-1].copy()
        r = lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(i * 1000 / fps))
        if r.face_landmarks:
            h, w = f.shape[:2]
            out.append(np.array([[p.x * w, p.y * h] for p in r.face_landmarks[0]]))
        else:
            out.append(None)
    return out


def fill_missing(pts):
    """Frames with no face take the nearest found frame's points (refused when none is found)."""
    found = [i for i, p in enumerate(pts) if p is not None]
    if not found:
        raise SystemExit("FACE_NOT_FOUND")
    return [pts[i] if pts[i] is not None else pts[min(found, key=lambda j: abs(j - i))] for i in range(len(pts))]


def boxes(pts, shape):
    h, w = shape[:2]
    raw = []
    for p in pts:
        x1, x2 = p[OVAL, 0].min(), p[OVAL, 0].max()
        y2 = p[CHIN, 1]
        y1 = p[NOSE_BRIDGE, 1] - (y2 - p[NOSE_BRIDGE, 1])
        raw.append([x1, y1, x2, y2 + EXTRA_MARGIN])
    raw = np.array(raw)
    k = 5   # moving average over 5 frames: the box must not jitter while the head is still
    pad = np.pad(raw, ((k // 2, k // 2), (0, 0)), mode="edge")
    smooth = np.stack([pad[i:i + k].mean(axis=0) for i in range(len(raw))])
    smooth[:, [0, 2]] = smooth[:, [0, 2]].clip(0, w)
    smooth[:, [1, 3]] = smooth[:, [1, 3]].clip(0, h)
    return smooth.round().astype(int)


def mask_for(p, box, shape):
    import cv2
    m = np.zeros(shape[:2], np.uint8)
    top = p[NOSE_TIP, 1]
    poly = [(x, max(y, top)) for x, y in p[OVAL_LOWER]]
    cv2.fillPoly(m, [np.array(poly, np.int32)], 255)
    x1, y1, x2, y2 = box
    m[:, :x1] = 0
    m[:, x2:] = 0
    m[:y1 + (y2 - y1) // 2, :] = 0           # MuseTalk only repaints the lower half of its crop
    k = int(0.08 * (y2 - y1)) // 2 * 2 + 1
    m = cv2.erode(m, np.ones((3, 3), np.uint8), iterations=2)
    return cv2.GaussianBlur(m, (k, k), 0).astype(np.float32) / 255.0


def lips_mask(p, shape, scale=1.9):
    """Only the mouth and the beard right around it: the outer-lip hull scaled about its centre (wider downwards,
    where the jaw opens), feathered."""
    import cv2
    lips = p[LIPS_OUTER]
    c = lips.mean(axis=0)
    w = lips[:, 0].max() - lips[:, 0].min()
    pts = (lips - c) * scale + c
    pts[:, 1] = np.where(pts[:, 1] > c[1], c[1] + (pts[:, 1] - c[1]) * 1.6 + 0.15 * w, pts[:, 1])
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [cv2.convexHull(pts.astype(np.int32))], 255)
    k = int(0.35 * w) // 2 * 2 + 1
    return cv2.GaussianBlur(m, (k, k), 0).astype(np.float32) / 255.0


def mouth_core(p, shape):
    """Where the mouth opens (lips width, down to ~0.7 of it below the lip line): no detail transfer there, so the
    closed lips of the source never ghost over an open mouth."""
    import cv2
    lips = p[LIPS_OUTER]
    c = lips.mean(axis=0)
    w = lips[:, 0].max() - lips[:, 0].min()
    m = np.zeros(shape[:2], np.uint8)
    cv2.ellipse(m, (int(c[0]), int(c[1] + 0.12 * w)), (int(0.5 * w), int(0.38 * w)), 0, 0, 360, 255, -1)
    k = int(0.3 * w) // 2 * 2 + 1
    return cv2.GaussianBlur(m, (k, k), 0).astype(np.float32) / 255.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--musetalk", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--face-model", required=True)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--mask", choices=["face", "lips"], default="face")
    ap.add_argument("--detail", action="store_true", help="put the source's fine texture back outside the mouth")
    ap.add_argument("--ref-image", default="", help="identity reference crop for every frame (a talking frame)")
    ap.add_argument("clip")
    ap.add_argument("wav")
    ap.add_argument("out")
    a = ap.parse_args()
    t0 = time.time()
    sys.path.insert(0, a.musetalk)
    import cv2
    import torch
    from transformers import WhisperModel
    from musetalk.models.unet import PositionalEncoding, UNet
    from musetalk.models.vae import VAE
    from musetalk.utils.audio_processor import AudioProcessor
    torch.set_num_threads(max(1, torch.get_num_threads()))
    dev = torch.device("cpu")

    frames, fps = read_frames(a.clip)
    fps_i = int(round(fps))
    pts = fill_missing(landmarks(frames, fps, a.face_model))
    bx = boxes(pts, frames[0].shape)

    vae = VAE(model_path=f"{a.models}/sd-vae")
    unet = UNet(unet_config=f"{a.models}/musetalkV15/musetalk.json", model_path=f"{a.models}/musetalkV15/unet.pth",
                device=dev)
    pe = PositionalEncoding(d_model=384)
    ap_ = AudioProcessor(feature_extractor_path=f"{a.models}/whisper")
    whisper = WhisperModel.from_pretrained(f"{a.models}/whisper").to(dev).eval()
    feats, n_samples = ap_.get_audio_feature(a.wav)
    with torch.no_grad():
        chunks = ap_.get_whisper_chunk(feats, dev, torch.float32, whisper, n_samples, fps=fps_i)
    n_out = len(chunks)

    cyc = list(range(len(frames))) + list(range(len(frames) - 1, -1, -1))
    order = [cyc[i % len(cyc)] for i in range(n_out)]
    latents = {}
    ref_lat = None
    with torch.no_grad():
        if a.ref_image:
            ref = cv2.imread(a.ref_image)
            rp = fill_missing(landmarks([ref], fps, a.face_model))
            rx1, ry1, rx2, ry2 = boxes(rp, ref.shape)[0]
            ref_lat = vae.encode_latents(vae.preprocess_img(
                cv2.resize(ref[ry1:ry2, rx1:rx2], (256, 256), interpolation=cv2.INTER_LANCZOS4), half_mask=False))
        for i in sorted(set(order)):
            x1, y1, x2, y2 = bx[i]
            crop = cv2.resize(frames[i][y1:y2, x1:x2], (256, 256), interpolation=cv2.INTER_LANCZOS4)
            if ref_lat is None:
                latents[i] = vae.get_latents_for_unet(crop)
            else:
                masked = vae.encode_latents(vae.preprocess_img(crop, half_mask=True))
                latents[i] = torch.cat([masked, ref_lat], dim=1)
    t_prep = time.time() - t0

    h, w = frames[0].shape[:2]
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-i", a.wav, "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-shortest", a.out], stdin=subprocess.PIPE)
    ts = torch.tensor([0])
    with torch.no_grad():
        for s in range(0, n_out, a.batch):
            idx = order[s:s + a.batch]
            wb = torch.stack([chunks[j] for j in range(s, s + len(idx))])
            lb = torch.cat([latents[i] for i in idx], dim=0)
            pred = unet.model(lb, ts, encoder_hidden_states=pe(wb)).sample
            recon = vae.decode_latents(pred)
            for i, face in zip(idx, recon):
                x1, y1, x2, y2 = bx[i]
                frame = frames[i].astype(np.float32)
                paste = frame.copy()
                paste[y1:y2, x1:x2] = cv2.resize(face.astype(np.uint8), (x2 - x1, y2 - y1),
                                                 interpolation=cv2.INTER_LANCZOS4)
                if a.detail:
                    core = mouth_core(pts[i], frame.shape)[..., None]
                    hf = frame - cv2.GaussianBlur(frame, (0, 0), 2.0)
                    paste = paste - (paste - cv2.GaussianBlur(paste, (0, 0), 2.0)) * (1 - core) + hf * (1 - core)
                m = lips_mask(pts[i], frame.shape) if a.mask == "lips" else mask_for(pts[i], bx[i], frame.shape)
                m = m[..., None]
                enc.stdin.write((frame * (1 - m) + paste * m).clip(0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("ENCODE_FAILED")
    print(json.dumps({"clip": a.clip, "wav": a.wav, "out": a.out, "frames": n_out, "fps": fps,
                      "clip_frames": len(frames), "cycled": n_out > len(frames),
                      "seconds_prep": round(t_prep, 1), "seconds_total": round(time.time() - t0, 1),
                      "box_median": np.median(bx, axis=0).astype(int).tolist(),
                      "mask": a.mask, "detail": a.detail, "ref_image": a.ref_image}))


if __name__ == "__main__":
    main()
