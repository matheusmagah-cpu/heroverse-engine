# Dot card: animation backend for "The Bag He Almost Passed" (candidate structure)

Director: Claude. Executor: Dot. Dot opens **draft PRs only**; Dot never dispatches workflows, never
edits frozen criteria, never writes APPROVAL.json, never touches secrets. Claude reviews, merges and runs.

## Read first (do not change)

- `migration/production/animation/SPEC.md` (chain, rules, render identity)
- `migration/production/animation/qa_criteria_animation_v1.json` (frozen; sha256 recorded in the PR that froze it)
- `migration/production/animation/the-bag-he-almost-passed/scenes.json` (15 scenes, Shorts plan)
- `migration/production/animation/the-bag-he-almost-passed/script.json` (voice input, Kokoro format)
- `migration/production/pilot_render.py` `voice()` (reused as is for the narration)

## Allowed paths (checked by `dot_scope.py` on every Dot PR; anything else fails CI)

```allowed
migration/production/animation/the-bag-he-almost-passed/render-bundle/*
migration/production/animation/timing.py
migration/production/animation/assemble.py
migration/production/animation/qa_animation.py
migration/production/animation/render_identity.py
migration/production/animation/test_*.py
```

`scenes.json`, `script.json` and the criteria are Claude's (the words, the scene states and the limits); ask on the card if one must change.

## Interfaces that exist today (checked by `card_check.py`)

```interfaces
migration/production/pilot_render.py: def voice(work, script_path):
migration/production/pilot_render.py: "sentences": spoken, "voice_seconds": round(total, 3),
migration/production/animation/the-bag-he-almost-passed/render-bundle/README.txt: RENDER_OUT=/work/output blender -b -t 8 --python production.py -- master 0 100
migration/production/animation/qa_criteria_animation_v1.json: "version": "animation-qa-criteria-v1",
migration/production/animation/the-bag-he-almost-passed/scenes.json: "version": "scenes-v1",
```

## Deliverables (one draft PR each, in this order)

### A. `timing.py` (pure Python, stdlib only)
- `python3 timing.py TIMELINE SCENES OUT_DIR` reads the `timeline.json` written by `pilot_render.py voice`
  (`segments[].id/start/end`, `sentences[]`), and writes:
  - `timing.json`: `{"fps": 24, "frames_total": N, "scenes": [{"id", "start_s", "end_s", "first_frame", "end_frame"}]}`;
    frame = round(seconds × 24); scenes contiguous, no gap, no overlap; last frame = master end.
  - `shorts-map.json`: for `short1` and `short2`, the ordered spans `{scene, master_start_s, master_end_s}` cut on
    sentence boundaries of `timeline.sentences`, speed 1.0, plus `total_s`. FAIL (exit 1) if a total is outside the
    frozen Shorts durations.
- Tests: contiguity, rounding at 24 fps, sentence-boundary cuts, the duration FAIL.

### B. Render bundle v2 (`production.py`, `scene_base.py`)
- Interface: `RENDER_OUT=... blender -b -t 0 --python production.py -- master|vertical START END --timing timing.json [--shorts shorts-map.json]`.
  Master indexes are frames 0..frames_total-1 at **24 fps**; vertical indexes are the frames of the Shorts spans.
  Output `hd-frames/%05d.png` (1920x1080) and `vertical-frames/<short>-%05d.png` (1080x1920, own cameras, never cropped).
- Characters (see `scenes.json` `characters`): armature-rigged humanoids with a walk cycle with weight shift,
  head and eye turns, hand and arm gestures, breathing, blinks, and simple facial expressions (brows, mouth).
  Primitive stacked shapes are not acceptable. Perspective cameras per scene `framing_and_camera`.
- Every scene: body animation for its whole span; `start_state` and `end_state` exactly as in `scenes.json`.
- Eevee Next, deterministic (same input → same PNG bytes), no network, no external assets, writes only under `RENDER_OUT`.
- Measure locally and report in the PR: seconds per frame (master, vertical) and peak memory on your machine.

### C. `assemble.py`
- `python3 assemble.py WORK SCENES TIMING SHORTS_MAP MUSIC OUT` with frames + `voice.wav` + owned music:
  - `master.mp4` H.264 yuv420p 24 fps 1920x1080, AAC 48 kHz stereo, loudness -15 LUFS (range -16..-14), true peak ≤ -1 dBTP,
    music ≥ 12 dB under the voice;
  - verse card exactly `Thou shalt love thy neighbour as thyself.` / `Matthew 22:39 (KJV)` only while spoken;
  - CTA card exactly `Subscribe to this channel for more stories of everyday faith.` while spoken (S15);
  - `master.srt` from `timeline.sentences` (text identical to the narration);
  - `short1.mp4`, `short2.mp4` (1080x1920, 24 fps) from `shorts-map.json`, burned phrase captions of 1-5 words from the
    same timeline, each ending with the CTA; `short1.srt`, `short2.srt`.
- Fonts: `fonts-dejavu-core` only.

### D. `qa_animation.py` + `render_identity.py`
- `qa_animation.py OUT_DIR CRITERIA` checks **every row** of the frozen criteria; refuses to run if the criteria file's
  sha256 differs from the frozen one; writes `qa.json` rows `{id, value, limit, PASS|FAIL|UNKNOWN}`.
  Fluidity is counted from `frames.json` (output frame → rendered PNG sha256), never estimated.
- `render_identity.py` returns the `render_id` defined in SPEC.md.
- Tests with tiny synthetic fixtures (a 2-second 24 fps clip made by ffmpeg in the test).

## Done means
CI green; each PR lists its tests and their output; no file outside the allowed paths; no change to frozen criteria.
Claude then runs the voice and the matrix render on the standard runners and the QA.
