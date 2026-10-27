#!/usr/bin/env python3
"""Re-sync the Keeper's lips to OUR narration line with LatentSync 1.5 on CPU (decisive test, owner-approved 2026-10-27;
decision in migration/strategy/LIPSYNC_TOOLS.md; Apache-2.0 code https://github.com/bytedance/LatentSync, 0 credits).

LatentSync as shipped needs CUDA. This wrapper runs the upstream pipeline unchanged, with a minimal CPU patch applied
at runtime (no upstream file is edited):
  1. FaceDetector: InsightFace on onnxruntime's CPUExecutionProvider (ctx_id -1) instead of CUDAExecutionProvider;
     same model (buffalo_l det_10g + 2d106det), same det_size 512, same filters and threshold 0.5.
  2. ImageProcessor: the pipeline builds it with device="cuda"; here it is built on the CPU with that CPU detector, and
     its AlignRestore (affine warp / paste back) runs in float32 (kornia's float16 path is a GPU path).
  3. Device "cpu" and dtype float32 everywhere (scripts/inference.py picks fp16 only on a CUDA card with
     capability > 7; whisper tiny on the CPU).
Everything else is scripts/inference.py: configs/unet/stage2.yaml (256 px, 16-frame windows), DDIM from configs/,
default 20 steps, guidance 1.5, DeepCache (interval 3, branch 0), seed 1247, sd-vae-ft-mse (scaling 0.18215).

usage: latentsync_sync.py detect --latentsync DIR CLIP25.mp4 OUT.json
           LatentSync's own face stage on every frame (FaceDetector + affine warp): detected/total, never raises
       latentsync_sync.py sync --latentsync DIR --ckpt latentsync_unet.pt --vae DIR CLIP25.mp4 LINE.wav OUT.mp4
           prints one JSON line (frames, seconds, missing checkpoint keys)
The clip must already be 25 fps (LatentSync's audio windows assume 25 fps; the pipeline does not resample).
"""
import argparse
import json
import os
import sys
import time


def setup(latentsync_dir):
    """Import LatentSync from its checkout (its code uses paths relative to the repo root) and apply the CPU patch."""
    os.chdir(latentsync_dir)
    sys.path.insert(0, latentsync_dir)
    import torch
    from insightface.app import FaceAnalysis
    import latentsync.pipelines.lipsync_pipeline as lp
    import latentsync.utils.face_detector as fd
    import latentsync.utils.image_processor as ip
    from latentsync.utils.affine_transform import AlignRestore

    def detector_init(self, device="cpu"):          # patch 1
        self.app = FaceAnalysis(allowed_modules=["detection", "landmark_2d_106"], root="checkpoints/auxiliary",
                                providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=-1, det_size=(fd.INSIGHTFACE_DETECT_SIZE, fd.INSIGHTFACE_DETECT_SIZE))
    fd.FaceDetector.__init__ = detector_init

    class CPUImageProcessor(ip.ImageProcessor):      # patch 2
        def __init__(self, resolution=512, device="cpu", mask_image=None):
            super().__init__(resolution, device="cpu", mask_image=mask_image)
            self.restorer = AlignRestore(resolution=resolution, device="cpu", dtype=torch.float32)
            self.face_detector = fd.FaceDetector(device="cpu")
    lp.ImageProcessor = CPUImageProcessor
    return CPUImageProcessor


def read_frames(path):
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))   # the pipeline reads RGB (read_video_cv2)
    return frames, fps


def detect(a):
    import numpy as np
    clip = os.path.abspath(a.clip)
    proc = setup(a.latentsync)(256)
    frames, fps = read_frames(clip)
    t0 = time.time()
    missed, boxes, scores = [], [], []
    for i, f in enumerate(frames):
        faces = proc.face_detector.app.get(f)
        bbox, _ = proc.face_detector(f)
        if bbox is None:
            missed.append(i)
            continue
        boxes.append(bbox)
        scores.append(max(float(x.det_score) for x in faces))
        proc.affine_transform(f)                       # the pipeline's own warp must also succeed
    out = {"clip": a.clip, "fps": fps, "frames": len(frames), "detected": len(frames) - len(missed),
           "missed_frames": missed, "all_detected": not missed and len(frames) > 0,
           "det_score_min": round(min(scores), 3) if scores else None,
           "box_median": np.median(np.array(boxes), axis=0).astype(int).tolist() if boxes else None,
           "seconds": round(time.time() - t0, 1)}
    with open(a.out_json, "w") as fh:
        json.dump(out, fh)
    print(json.dumps(out))


def sync(a):
    clip, wav, out, ckpt, vae_dir = (os.path.abspath(p) for p in (a.clip, a.wav, a.out, a.ckpt, a.vae))
    tmp = os.path.abspath(a.temp_dir)
    t0 = time.time()
    setup(a.latentsync)
    import torch
    from accelerate.utils import set_seed
    from diffusers import AutoencoderKL, DDIMScheduler
    from omegaconf import OmegaConf
    from latentsync.models.unet import UNet3DConditionModel
    from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
    from latentsync.whisper.audio2feature import Audio2Feature
    from DeepCache import DeepCacheSDHelper

    dtype = torch.float32                              # patch 3
    config = OmegaConf.load("configs/unet/stage2.yaml")
    scheduler = DDIMScheduler.from_pretrained("configs")
    audio_encoder = Audio2Feature(model_path="checkpoints/whisper/tiny.pt", device="cpu",
                                  num_frames=config.data.num_frames, audio_feat_length=config.data.audio_feat_length)
    vae = AutoencoderKL.from_pretrained(vae_dir, torch_dtype=dtype)
    vae.config.scaling_factor = 0.18215
    vae.config.shift_factor = 0
    # UNet3DConditionModel.from_pretrained loads with strict=False and says nothing; load the same way here but count
    # the keys, so a checkpoint/config mismatch cannot pass silently.
    unet = UNet3DConditionModel.from_config(OmegaConf.to_container(config.model))
    sd = torch.load(ckpt, map_location="cpu", weights_only=True, mmap=True)["state_dict"]
    res = unet.load_state_dict(sd, strict=False)
    del sd
    if res.missing_keys:
        raise SystemExit(f"CHECKPOINT_KEYS_MISSING {len(res.missing_keys)}: {res.missing_keys[:5]}")
    unet = unet.to(dtype=dtype)
    pipeline = LipsyncPipeline(vae=vae, audio_encoder=audio_encoder, unet=unet, scheduler=scheduler).to("cpu")
    helper = DeepCacheSDHelper(pipe=pipeline)
    helper.set_params(cache_interval=3, cache_branch_id=0)
    helper.enable()
    set_seed(a.seed)
    t_load = time.time() - t0
    t1 = time.time()
    pipeline(video_path=clip, audio_path=wav, video_out_path=out, num_frames=config.data.num_frames,
             num_inference_steps=a.inference_steps, guidance_scale=a.guidance_scale, weight_dtype=dtype,
             width=config.data.resolution, height=config.data.resolution,
             mask_image_path=config.data.mask_image_path, temp_dir=tmp)
    t_run = time.time() - t1
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        raise SystemExit("NO_OUTPUT")
    import cv2
    cap = cv2.VideoCapture(out)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(json.dumps({"clip": a.clip, "wav": a.wav, "out": a.out, "frames": n, "threads": torch.get_num_threads(),
                      "inference_steps": a.inference_steps, "guidance_scale": a.guidance_scale, "deepcache": True,
                      "seed": a.seed, "dtype": "float32", "device": "cpu",
                      "unexpected_keys": len(res.unexpected_keys), "seconds_load": round(t_load, 1),
                      "seconds_inference": round(t_run, 1), "seconds_per_frame": round(t_run / max(n, 1), 2),
                      "seconds_total": round(time.time() - t0, 1)}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--latentsync", required=True)
    d.add_argument("clip")
    d.add_argument("out_json")
    s = sub.add_parser("sync")
    s.add_argument("--latentsync", required=True)
    s.add_argument("--ckpt", required=True)
    s.add_argument("--vae", required=True)
    s.add_argument("--inference-steps", type=int, default=20)
    s.add_argument("--guidance-scale", type=float, default=1.5)
    s.add_argument("--seed", type=int, default=1247)
    s.add_argument("--temp-dir", default="ls-temp")
    s.add_argument("clip")
    s.add_argument("wav")
    s.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "detect":
        a.out_json = os.path.abspath(a.out_json)
        detect(a)
    else:
        sync(a)


if __name__ == "__main__":
    main()
