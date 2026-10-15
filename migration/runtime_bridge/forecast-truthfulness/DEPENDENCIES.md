# Native CLI qualification dependency evidence

Direct requirements are pinned in migration/runtime_bridge/forecast-qualification-requirements.txt. These are candidate qualification inputs, not proof that their combination has already passed on Linux. No installation, resolver run or workflow dispatch has been performed for this successor.

- jsonschema 4.26.0, numpy 2.2.6 and Pillow 11.3.0: exact pins in existing `.github/workflows/linux-overlay-qualification.yml` at main fa03f7ae6fd0b9759bf68ad3c1ed29dcd532574f. They are the existing cloud qualification versions, deliberately not the newer native-Windows requirement floors.
- faster-whisper 1.2.1: existing `.github/workflows/second-opening-asr.yml`; source archive `docs/PHASE6_NARRATION_CONTINUITY_FINDINGS.md` also records it.
- yt-dlp 2026.8.19: existing `.github/workflows/official-evidence.yml` exact pin, plus archive `docs/PHASE_0_AUDIT.md` and market collector policy.
- rapidocr 3.9.2: exact pin in immutable source `requirements.txt`, `docs/DECISIONS.md`, and `docs/PHASE_2_PREFLIGHT.md`.
- opencv-python 5.0.0.93: source `hero_engine/phase6_av_publicity_runtime.py` identifies the installed distribution family and `phase6_av_detector_semantics.py` identifies the corresponding core/distribution versions. Use this evidenced package, rather than inventing a headless version. Linux wheel availability and joint dependency compatibility remain unverified.
- onnxruntime 1.29.0: explicit minimum in immutable source `requirements.txt` (`>=1.29.0,<2`). Pinning that declared minimum is an engineering qualification choice, not evidence that this exact version was observed in an already-passed Linux run. This is the weakest version provenance; keep that limitation visible. Do not silently loosen or substitute if resolution fails.

All eight correspond to native CLI imports or their selected import backend. The narrow path does not require Google client/OAuth packages, torch, torchaudio, kokoro, audio-quality stacks, model assets or FFmpeg execution. No such packages are separately installed by this workflow. Transitive dependencies required by the eight packages still resolve via official PyPI; the receipt records the entire installed name/version inventory and verifies every direct pin. This is not a hashed full dependency lock.

## Why importing is different from running models

Native `hero_engine/mining/adapters.py` imports cv2, numpy, WhisperModel, PIL and RapidOCR at module scope. It constructs WhisperModel/RapidOCR only inside adapter methods; selected forecast/help tests do not instantiate those adapters. `hero_engine/observatory/collectors.py` imports yt_dlp, but collection is not invoked.

Official Faster Whisper v1.2.1 source shows package import exporting WhisperModel, while model download occurs in WhisperModel.__init__ when a nonlocal model name/path is supplied. Import alone does not call that constructor. Sources:
- https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/__init__.py
- https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py#L581-L646

RapidOCR's official installation instructions specify rapidocr plus onnxruntime; ONNX Runtime is its supported default CPU inference backend, rather than an unrelated addition. No inference engine/model is instantiated in the reviewed forecast path. Source:
- https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/

These are source-based findings, not a substitute for a successful fresh import. The qualifier still runs inside an isolated network namespace and a Python network/process denial guard, with offline Hugging Face switches. Any unexpected import-time network or process attempt fails closed rather than downloading a model or calling a provider.
