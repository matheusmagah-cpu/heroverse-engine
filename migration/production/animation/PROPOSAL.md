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
   each chunk uploads `frames-<a>-<b>` (retention 3 days) with `frames.json` (index → sha256). A resume run is
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

MEASURED: pending the test run.

## 5. Rollback

- Every change is one squash-merged PR; reverting it restores the previous behaviour.
- The animation branch in `render_pilot.sh` runs only when `script.json` says `"backend": "animation"`; prayer pilots never take it.
- Frozen criteria are never edited; a new version is a new file.
- Artifacts expire after 3 days; nothing is published without the unchanged three-stage approval.
