# Animation backend: proposal before integration (2026-10-19)

Status: **proposal**. Nothing below changes the prayer pipeline until it is merged. The prayer
criteria (`qa_criteria_v3.json`, frozen) and every publication control stay as they are.

## 1. What is reused (no second pipeline)

| Existing component | Reused for |
|---|---|
| `pilot_render.py voice` (Kokoro v1.0, hash-pinned, per-sentence timeline) | narration + `timeline.json` (sentence start/end) that drives scene timing and subtitles |
| Owned music asset (sha256-pinned, private release) | music bed |
| `render_pilot.sh` stages: tools, voice, QA, package, private release upload, evidence commit | the same script with one `BACKEND=animation` branch for the assemble and Shorts stages |
| `render_queue.py` (queue, dedupe), manifest + hashes | the animation render is a queue entry; its manifest carries the `render_id` |
| `signal_scan.py`, `long_review.py`, `three_stage.py`, `prepublish_gate.py`, `approve.yml`, `publish.yml`, `publish-shorts.yml` | review, approval and publication unchanged; the gate selects the criteria file named by the render manifest |
| `animation-render-test.yml` (#189) | becomes the frame-render step (chunks), nothing else |

## 2. Minimal changes

1. `render_pilot.sh`: if `script.json` has `"backend": "animation"`, the Assemble stage runs `animation/assemble.py`
   on frames downloaded from the chunk artifacts (hash-checked) instead of `still_render.py`; QA runs `qa_animation.py`
   with `qa_criteria_animation_v1.json`. Every other stage is unchanged.
2. Shorts count: `shorts_select.py ... 3` becomes the count from the script (`script.json` `shorts.count`, default 3).
   The animation test uses 2, from `scenes.json`, so no model selection is involved.
3. Render identity: the manifest gains `render_id` (SPEC.md): script, scenes, voice, music, SRT, every bundle file,
   Blender version, engine, samples, fps, resolution, criteria. Approval binds to it.
4. `render_queue.STANDARD_QA` becomes a set: `{"pilot-qa-criteria-v3", "animation-qa-criteria-v1"}`; the gate checks
   the frozen sha of whichever criteria the manifest names (both listed in `FROZEN_CRITERIA_SHA256`).
5. Chunk render workflow (from the test): `workflow_dispatch` with `chunks` input; matrix with `max-parallel: 4`;
   each chunk uploads one lossless FFV1 clip `frames-<a>-<b>.mkv` (retention 1 day) with `frames.json` (index → sha256). A resume run is
   dispatched with only the missing or invalid chunk ranges, found by `qa_animation.py` (`frame_set_contiguous`).

## 3. Tests

- Unit (CI, no network): `timing.py`, `assemble.py` (2-second synthetic clip), `qa_animation.py` (one PASS and one
  FAIL fixture per row), `render_identity.py` (any field change → new id), Shorts count from the script.
- Integration on the standard runner: (a) the measured chunk test (#189 run, below); (b) voice + timing only;
  (c) full matrix render; (d) assembly + QA; (e) watched critique with timestamps.
- Regression: the full existing suite in `pr-checks.yml` must stay green; a prayer render (pilot-012 files) must give the
  same QA result as before.

## 4. Expected consumption (no additional spending)

Both repositories are **public**: standard GitHub-hosted runner minutes are free; no paid or larger runners are used.
Measured on the standard runner (run 39311356367): see `MEASURED` below; the full-render estimate is
`frames × seconds_per_frame / 4 jobs` and is not a promise of linear speed-up (each job also pays preparation).

MEASURED (run 39311356367, `the-bag-he-almost-passed/evidence/render-test-39311356367.json`):
- graphics: **EGL headless works**; Xvfb not needed;
- preparation: 35 s (apt 14 s, verified Blender download 2 s, extract 19 s) + ~20 s Blender start per process;
- **28.8 s per frame** (master and vertical alike, 4-CPU runner), peak memory **1.8 GB**, PNG ~2.9 MB per frame;
- join of two chunks from separate processes: exact (10/10 frames, all distinct); 84 GB disk free.

| Render | Frames | Job time | Wall time with 4 jobs |
|---|---|---|---|
| Current bundle (10 fps, 152 s + 2 Shorts) | 1,520 + 470 = 1,990 | ~16 h | ~4 h |
| Target bundle (24 fps, 152 s + ~83 s of Shorts) | 3,648 + ~1,990 = ~5,640 | ~45 h | ~11-12 h |

The target figure assumes today's cost per frame; rigged characters may cost more and are measured again on the
first chunk of the new bundle before any matrix. Consequences, built into the design:
- **job limit**: a standard job stops at 6 h, so chunks are sized to ≤ 3 h (~350 frames) and a run has 16 chunks,
  4 at a time;
- **artifact size**: 5,640 PNGs would be ~16 GB. Each chunk job encodes its frames into one lossless FFV1 clip (its size is measured on the first chunk) and
  uploads only that plus `frames.json` (index → sha256), retention **1 day**; the assembly job deletes nothing it did
  not verify;
- **resume**: a second run is dispatched only with the chunk ranges that are missing or fail the hash/dimension check.

No paid runner, no larger runner, no external service. Cost stays at zero.

## 5. Rollback

- Every change is one squash-merged PR; reverting it restores the previous behaviour.
- The animation branch in `render_pilot.sh` runs only when `script.json` says `"backend": "animation"`; prayer pilots never take it.
- Frozen criteria are never edited; a new version is a new file.
- Chunk artifacts expire after 1 day (the test's after 3); nothing is published without the unchanged three-stage approval.
