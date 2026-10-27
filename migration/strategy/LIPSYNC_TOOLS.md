# Keeper lip sync: which free tool, on public evidence (2026-10-27)

Research only: no repository change, no generation, no paid service, no sign-up.
Owner's updates during the work (via coordinator): (1) **license is not a criterion**, since non-commercial tools are acceptable
and the owner accepts the risk; licenses are listed only for reference. (2) The output is **one decision**, and the runner-up is only
the fallback if the decisive test fails.

## 0. Our case, as measured (repository evidence)

- Judge: `migration/production/bible/lipsync_check.py` measures the inner-lip gap (MediaPipe landmarks 13/14 over face height)
  against the speech envelope. To pass, a clip needs mouth corr >= 0.45 at |lag| <= 84 ms, speak/pause opening >= 1.5, and the
  face found in >= 80 % of frames. Calibration: Pavo with our audio scored 0.52 at 0 ms.
- The silent Keeper probe clips (`migration/evidence/pavo/20261026/keeper-vo/probe-*.mp4`) are **720x1280, 24 fps**. The
  face box MuseTalk used is about **200 x 285 px** (`box_median` [282,197,483,482] in the `*.run.json` files), so a 256 px face
  crop already holds at least as much detail as the source face. This matters when choosing a version below.
- MuseTalk 1.5 on CPU, best per line across rounds 1-4 (branches `origin/claude/musetalk-probe-*`, files
  `migration/evidence/pavo/20261026/musetalk/run-*/*.check.json`):
  k-close 0.549 / 0.535 PASS; k-question 0.457 (round 1 face mask, beard blurred), otherwise 0.36-0.43 FAIL (lit source 0.468 but
  face found in only 71 % of frames); k-insight 0.23-0.37 FAIL, with MOUTH_OPEN_IN_PAUSES in several variants. CPU time was
  **~9-25 min per clip** (`seconds_total` 545-1507 s for 109-202 frames).
- Diagnosis from those numbers: the failures are **not enough mouth articulation that follows the audio** (corr 0.3-0.4, low
  speak/pause ratios of 1.2-1.7). They are not lag failures (lag is mostly 0-42 ms), and not face loss, except on the lit source.
  A model with stronger audio-to-mouth coupling is therefore what is needed. Restoration tricks around MuseTalk will not supply it.

## 1. Candidates (video-to-video first, image-to-video as fallback)

### A. Video-to-video lip editing (what we need)

| Tool | License (reference only) | Published sync / quality | Compute | Known failure modes |
|---|---|---|---|---|
| **LatentSync 1.5 / 1.6** (ByteDance) | Code Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/bytedance/LatentSync/main/LICENSE)); 1.6 weights tagged openrail++ ([HF](https://huggingface.co/bytedance/LatentSync-1.6)) | HDTF, own paper: Sync_conf **8.9** vs Wav2Lip 8.2, Diff2Lip 7.9, VideoReTalking 7.5, MuseTalk 6.8; FID 7.22, FVD 162.7, the best in the table ([arXiv 2412.09262 Table 1](https://arxiv.org/html/2412.09262)). **MuseTalk's own paper concedes LatentSync has the best LSE-C (7.90 on HDTF)** ([arXiv 2410.10122](https://arxiv.org/pdf/2410.10122)). JOLT3D (third party) also finds LatentSync best on LSE-C/LSE-D ([arXiv 2507.20452](https://arxiv.org/pdf/2507.20452)). | GPU: 8 GB (1.5, 256 px), 18 GB (1.6, 512 px) ([README](https://github.com/bytedance/LatentSync)). Default 20 steps, CFG 1.5, DeepCache (`inference.sh`). **CPU not supported as shipped**: `image_processor.py` raises `NotImplementedError("Using the CPU for face detection is not supported")`, and in [PR #36](https://github.com/bytedance/LatentSync/pull/36) a reviewer reports a CPU-only run "gets stuck". Patchable (InsightFace on the onnxruntime CPU provider, or our MediaPipe box). On T4/P100 the code picks fp32 (`get_device_capability()[0] > 7`), so 1.6 on a 16 GB card is doubtful (unverified). | Facial-hair, teeth and lip flicker named by the authors and addressed with TREPA ([paper](https://arxiv.org/html/2412.09262v2)). Higher guidance improves sync but may jitter ([README](https://github.com/bytedance/LatentSync)). 1.5 was blurry at large faces, which 1.6 fixes ([README](https://github.com/bytedance/LatentSync)). Its mask regenerates the whole lower face: `mask.png` rows 95-242 of 256, 41 % of the crop (measured here). |
| **KeySync** (Imperial / Wrocław, 2025) | Code Apache-2.0 ([GitHub](https://github.com/antonibigata/keysync)); weights tagged apache-2.0 ([HF](https://huggingface.co/toninio19/keysync)) | Own paper, cross-sync: LipScore **0.48** vs LatentSync 0.14, Diff2Lip 0.16; FVD 206 vs LatentSync 362; LipLeak 0.16 vs 0.33; Elo 1145 vs 1086 ([HF papers 2505.00497](https://huggingface.co/papers/2505.00497)). 512x512. | "CUDA-compatible GPU" only; VRAM and speed not published ([GitHub](https://github.com/antonibigata/keysync)). Two diffusion stages (keyframes plus interpolation). **CPU: not realistic** (my assessment, unverified). | Handles *object* occlusions with SAM2 masking; nothing published on beards. A practitioner benchmark kept LatentSync 1.6 ahead after an A/B against KeySync ([Instavar, May 2026](https://instavar.com/research/ai-video/open-source-lip-sync-models), seen only through search snippets because the page was unreachable). |
| **MuseTalk 1.5** (Tencent Music) | MIT code; weights "available for any purpose, even commercially" ([GitHub](https://github.com/TMElyralab/MuseTalk)) | Best FID 6.52 / CSIM 0.86 on HDTF, but LSE-C below LatentSync ([arXiv 2410.10122](https://arxiv.org/pdf/2410.10122)). Sync_conf 6.8 (the lowest) in LatentSync's table. | 4 GB GPU; 30 fps+ on a V100; **CPU works (measured here, 9-25 min per clip)**. | README: "mustache, lip shape and color" are not well preserved, plus jitter from single-frame generation ([GitHub](https://github.com/TMElyralab/MuseTalk)). LatentSync paper: with MuseTalk "the man's beard becomes sparse". **Ours: 1 of 3 lines, soft halo.** |
| **Wav2Lip** (+ HD/GFPGAN variants) | **Non-commercial** ("personal/research/non-commercial", [GitHub](https://github.com/Rudrabha/Wav2Lip)); now in scope per the owner | Strong sync (Sync_conf 8.2 HDTF) but FID 12.5, the worst ([LatentSync Table 1](https://arxiv.org/html/2412.09262)). | CPU feasible, ~1-2 s per frame (ONNX Space estimate, [HF Space](https://huggingface.co/spaces/WeReCooking/wav2lip/blob/main/app.py)). | 96x96 mouth, blurry ([MuseTalk paper](https://arxiv.org/pdf/2410.10122)); "two mouths" artifacts ([README](https://github.com/Rudrabha/Wav2Lip)). A blurred box over a long beard would fail the 9.5 visual review. |
| **VideoReTalking** | Apache-2.0 ([GitHub](https://github.com/OpenTalker/video-retalking)) | Sync_conf 7.5, FID 9.5 ([LatentSync Table 1](https://arxiv.org/html/2412.09262)). | GPU (CUDA 11.1 pinned); CPU untested. | Rewrites the whole face expression and restores it with a face enhancer, a risk to identity and beard texture; "DNet cannot handle extreme poses" ([GitHub](https://github.com/OpenTalker/video-retalking)). |
| **Diff2Lip** | CC BY-NC 4.0 ([GitHub](https://github.com/soumik-kanad/diff2lip)) | Sync_conf 7.9 ([LatentSync](https://arxiv.org/html/2412.09262)); LipScore 0.16, FVD 602 ([KeySync](https://huggingface.co/papers/2505.00497)). | GPU, pixel diffusion; checkpoint on Google Drive. | No beard evidence. |
| **InfiniteTalk** (MeiGen, video-to-video "sparse-frame dubbing") | Apache-2.0 ([GitHub](https://github.com/MeiGen-AI/InfiniteTalk)) | Claims better lips than MultiTalk; notes that LatentSync/MuseTalk FID/FVD look good because they edit only the mouth ([arXiv 2508.14033](https://arxiv.org/pdf/2508.14033)). | Wan2.1 14B; fp8 and low-VRAM modes; **no CPU**. | Regenerates the whole frame: camera only approximated, colour shift, ID loss with FusionX ([GitHub](https://github.com/MeiGen-AI/InfiniteTalk)). Too heavy for free compute at our cadence. |
| **HighSync** (2026) | MIT ([GitHub](https://github.com/saeed5959/high_sync)) | Claims SOTA at 512; FID 7.36 HDTF ([arXiv 2605.16918](https://arxiv.org/pdf/2605.16918)). No table on the repo. | GPU; VRAM not published. | Unverified, new, no community use found. |
| OmniSync, UniSync, ComplexSync, FlashLips (2025-26 papers) | n/a | Strong claims on AIGC, stylized faces and occlusion ([OmniSync](https://arxiv.org/html/2505.21448v1), [UniSync](https://arxiv.org/html/2603.03882v1), [ComplexSync](https://arxiv.org/pdf/2609.29225), [FlashLips](https://arxiv.org/html/2512.20033v1)) | **No public code or weights found.** ComplexSync had to use OmniSync through Kling. | Not usable. |

### B. Image-to-video talkers (fallback category only: they replace the whole performance, not just the mouth)

| Tool | License | Compute | Note |
|---|---|---|---|
| EchoMimic v3 | Apache-2.0 | 12 GB (Flash), Wan2.1-1.3B ([GitHub](https://github.com/antgroup/echomimic_v3)) | Image plus audio; no video-to-video. |
| EchoMimic v1/v2 | Apache-2.0 | V100 16 GB tested; v1 ~50 s per 240 frames on V100 ([mirror](https://gitee.com/hf-models/EchoMimic)) | Image-driven. |
| Hallo2 / Hallo3 | MIT tags on HF ([Hallo2](https://huggingface.co/fudan-generative-ai/hallo2/tree/main)); Hallo3 builds on CogVideoX-5B | GPU, VRAM not published | Image-driven. |
| Sonic (Tencent) | CC BY-NC-SA 4.0 ([GitHub](https://github.com/jixiaozhong/Sonic)) | "tested on a single 32G GPU" | Image-driven. |
| FantasyTalking | Apache-2.0 ([GitHub](https://github.com/Fantasy-AMAP/fantasy-talking)) | Wan2.1-I2V-14B: 5 GB at 42.6 s/it on an A100 | Image-driven. |
| OmniAvatar | Apache-2.0 ([GitHub](https://github.com/Omni-Avatar/OmniAvatar)) | 14B: 8 GB at 22 s/it on an A800 | Image-driven. |
| MultiTalk | Apache-2.0 weights ([HF](https://huggingface.co/MeiGen-AI/MeiGen-MultiTalk/blob/refs%2Fpr%2F3/README.md)) | 480p on one 4090 (low-VRAM mode) | Image-driven. |
| HunyuanVideo-Avatar | Tencent license (not read) | 24 GB minimum, "very slow"; 10 GB through Wan2GP ([GitHub](https://github.com/Tencent-Hunyuan/HunyuanVideo-Avatar)) | Image-driven. |
| JoyVASA (+ LivePortrait) | MIT ([GitHub](https://github.com/jdh-algo/JoyVASA)) | 8 GB laptop GPU tested | Animates a *still image* only. LivePortrait itself has v2v but no audio mode ([GitHub](https://github.com/KwaiVGI/LivePortrait)). |

None of group B has CPU support, and all of them regenerate the face from one still, so the beard would be re-synthesised every
frame. Pavo already does this route and gets 1 in ~40.

## 2. Specific evidence: beards, occlusion and AI-generated faces

- **Beards.** The only head-to-head beard statement found is in the LatentSync paper: MuseTalk "does not preserve facial features
  well, the man's beard becomes sparse", while LatentSync's LPIPS and TREPA target "teeth, lips and facial hair" flicker
  ([arXiv 2412.09262](https://arxiv.org/html/2412.09262v2)). This is the authors' own claim. MuseTalk's README admits it does not
  preserve the mustache. No GitHub issue on beards was found in LatentSync (search "beard": one unrelated issue,
  [#315](https://github.com/bytedance/LatentSync/issues?q=beard), about whitish mouth corners) or in MuseTalk (0 results).
  Vendor pages (sync.so) claim beards break open models, but they sell a competing API and cite no data.
- **AI-generated faces (the most relevant third-party data).** OmniSync's AIGC-LipSync benchmark has 615 AI-generated videos,
  scored by generation success. A success means the video is synchronised and passes human checks.

  | Tool | Overall | Stylized |
  |---|---|---|
  | MuseTalk | 92.2 % | 67.8 % |
  | LatentSync | 74.96 % | 35.56 % |
  | Wav2Lip | 71.38 % | 26.67 % |

  Sources: [OmniSync](https://arxiv.org/html/2505.21448v1) and a leaderboard mirror; the column mapping of the mirror is unverified.
  The gap is mostly on stylized and cartoon faces, where LatentSync's InsightFace detector fails. ThinkDiffusion also says the
  LatentSync 1.6 workflow does not support anime or cartoon faces
  ([guide](https://learn.thinkdiffusion.com/seamless-lip-sync-create-stunning-videos-with-latentsync/)). The Keeper is a
  photoreal AI face, but the beard over the mouth could still upset InsightFace's 106 landmarks. **This is the main risk, and it
  is cheap to test (step 0 below).**
- **Occlusion.** KeySync (SAM2 masking) and UniSync/ComplexSync address *objects* in front of the mouth. A moustache is part
  of the face, so their occlusion handling does not directly apply. UniSync and ComplexSync have no code.

## 3. Free compute routes (no spending)

| Route | GPU | Limits | Fit |
|---|---|---|---|
| GitHub Actions hosted runner | none (4 vCPU, 16 GB) | 6 h per job; minutes are unlimited on public repos and 2,000 per month on a private Free plan (repo visibility not checked) | MuseTalk measured. LatentSync needs a CPU patch. My estimate (unverified): 1.5 at 256 px costs about 20x MuseTalk's per-frame UNet time (20 steps x CFG, about halved by DeepCache), roughly **2-6 h per 8 s clip**. It fits with one matrix job per line, or by splitting into 16-frame chunks; 1.6 at 512 px is ~4x more and does not fit. |
| Hugging Face ZeroGPU | half an RTX Pro 6000 (48 GB) | Free account: **5 min GPU per day**; can host 2 ZeroGPU Spaces if the account is older than 30 days ([docs](https://huggingface.co/docs/hub/spaces-zerogpu)). The public [fffiloni/LatentSync](https://huggingface.co/spaces/fffiloni/LatentSync/blob/main/app.py) Space books 180 s per call and trims audio to 8 s. | Good for a 3-clip test over 1-3 days; too small for production. Needs an HF account (sign-up by the owner). |
| Kaggle notebooks | P100 16 GB or 2x T4 | ~30 GPU-h per week, 12 h sessions ([summary](https://gpuperhour.com/blog/free-cloud-gpus-and-credits); quota not officially fixed) | Enough for production volume. Needs an account with phone verification and a Kaggle API key as a repo secret. On these GPUs LatentSync falls back to fp32, so use 1.5, or patch fp16 for 1.6 (unverified). |
| Google Colab free | T4 | Variable, interactive; poor for automation | Manual test only. |

## 4. Ranking for our case (license ignored)

| # | Tool | CPU on Actions | Sync evidence | Beard / AI-face evidence | Verdict |
|---|---|---|---|---|---|
| 1 | **LatentSync (1.5 on CPU / 1.6 on GPU)** | Patch needed; ~2-6 h per clip (estimate) | Best open sync in its own paper, in MuseTalk's paper and in JOLT3D | Beard kept vs MuseTalk (authors); TREPA for facial hair; AIGC success 75 % (detector risk) | **Decision** |
| 2 | KeySync | No (GPU: Kaggle / ZeroGPU) | Highest LipScore vs LatentSync (own paper only) | Object occlusion only; no beard data; practitioner still preferred LatentSync | Fallback |
| 3 | MuseTalk 1.5 | Yes, measured | Lowest LSE-C of the modern three | Thins beard and mustache; best AIGC robustness 92 % | Tried: 1/3 |
| 4 | Wav2Lip (+HD) | Yes | High sync (8.2) | Blurry 96 px mouth: fails 9.5 | Out on visuals |
| 5 | VideoReTalking | Unrealistic | 7.5 | Whole-face rewrite + enhancer | Out |
| 6 | Diff2Lip | No | 7.9 | none | Out |
| 7 | InfiniteTalk / HighSync | No | Self-reported | Full-frame regen / unproven | Out for now |
| - | Group B talkers | No | n/a | Re-synthesise the beard each frame | Only if lip editing is abandoned |

## 5. Decision

**LatentSync** is the decision. Use the 1.5 checkpoint (256 px) on the GitHub Actions CPU runner. Our face is only ~200x285 px,
so 256 px loses nothing, and that runner is the same free infrastructure as the MuseTalk probe. 1.6 is for later, only if a free
GPU is added.

Evidence:
1. It is the only open model whose lip-sync lead is confirmed outside its own paper. MuseTalk's authors concede LatentSync's
   LSE-C is the best (7.90 HDTF), and JOLT3D independently confirms it.
2. Its sync is SyncNet-supervised, so it produces larger mouth movements that follow the audio. That is exactly what our MuseTalk
   runs lacked (corr 0.3-0.4, speak/pause 1.2-1.7). This link from the evidence to our failure mode is my inference.
3. Its paper directly contrasts its beard preservation with MuseTalk thinning a beard.
4. It edits only the face region of an existing clip, so the Pavo shot, lighting and identity outside the mask stay intact.

Still uncertain:
- Face detection on our bearded AI face (InsightFace, AIGC success only 75 %).
- Real CPU time: my estimate only; LatentSync has no official CPU path.
- Whether the mouth closes in pauses: no public evidence either way.
- Whether regenerating the whole lower face keeps the 9.5 beard texture. That claim comes from the authors only.
- The fps mismatch: LatentSync expects 25 fps and our clips are 24.

**Fallback if the decisive test fails: KeySync** on Kaggle or a ZeroGPU Space. It has the strongest self-reported sync among
released video-to-video models and runs at 512 px, but it needs a free GPU account.

## 6. The decisive test (one workflow run, same inputs as MuseTalk rounds 1-4)

0. **Detector gate (minutes, CPU):** run LatentSync's own `FaceDetector` (InsightFace, CPU provider) on every frame of the three
   silent probes: `probe-k-close-1`, `probe-k-insight-1` and `probe-k-question-1`. Required: a face on 100 % of frames, so that
   inference never raises "Face not detected". If this fails, go straight to KeySync.
1. **Run** LatentSync 1.5 on each probe with its genesis-07 Kokoro WAV (k-close, k-insight, k-question). Use one matrix job per
   line, the source resampled to 25 fps, 20 steps, guidance 1.5 and DeepCache, recording seconds per frame.
2. **Judge** with `lipsync_check.py`, thresholds unchanged, plus the CLAUDE_REVIEW visual rubric (beard texture, halo, identity,
   flicker).
   - **Confirmed:** all 3 lines pass the check, including **k-insight**, which MuseTalk never got above 0.37, and the visual review
     reaches 9.5.
   - **One allowed retry:** guidance 2.0 on the failing lines only, if the first pass lifts mouth corr clearly above MuseTalk's
     best on each line but misses one.
   - **Otherwise:** go to KeySync.

The measured CPU time also settles production feasibility on Actions. Kaggle is the escalation if it exceeds the 6 h job limit.

## Not verified / caveats

- arXiv, alphaxiv, instavar.com, sotaverified and the sota2 mirror could not be fetched from this sandbox. Their numbers come
  from search-engine extracts of those pages (LatentSync Table 1, MuseTalk's concession, the OmniSync AIGC rates and Instavar's
  verdict). The arXiv links are given for checking.
- Not verified: KeySync VRAM and speed; HunyuanVideo-Avatar license text; LatentSync CPU runtime (my FLOP-ratio estimate from our
  MuseTalk timings); Kaggle quota (not officially fixed); this repository's visibility, which affects Actions minutes.
- All published metrics are on HDTF/VoxCeleb2 real faces, except OmniSync's AIGC set. No public result covers a long white beard
  over the mouth, so the decisive test is the only real proof.
