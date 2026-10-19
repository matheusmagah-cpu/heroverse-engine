# Animated faith story: execution spec v1 (candidate structure)

Structure: `structures/animated-faith-story.json` (candidate; pilot only, never scaled until validated).
Frozen QA: `qa_criteria_animation_v1.json` (frozen before the first render). The prayer criteria
`qa_criteria_v3.json` stay frozen and unchanged; each structure has its own criteria.

## Chain (one traceable record per step)

| Step | Input | Output (versioned in the repo, or a hash-named release asset) | Tool |
|---|---|---|---|
| 1 Research | vidIQ | `evidence/vidiq/<date>/animated-story/mining.json` | Claude |
| 2 Direction | mining | `structures/animated-faith-story.json`, this SPEC | Claude |
| 3 Script | direction | `<project>/script.json` (Kokoro voice format) | Claude / Dot |
| 4 Scenes | script | `<project>/scenes.json` (per scene: narration, duration rule, framing, camera, action, start/end state, motion, sound, hold, approval) | Claude / Dot |
| 5 Audio | script | `voice.wav` + `timeline.json` (reused `pilot_render.py voice`), owned music (hash-pinned) | runner |
| 6 Timing | timeline | `timing.json`: each scene's frame range at 24 fps = its span on the voice timeline | runner |
| 7 Render | bundle + timing | PNG frames per chunk, `frames.json` (index -> sha256) | Blender 4.3.2 on standard runners |
| 8 Assembly | frames + audio + SRT | `master.mp4` (1920x1080, 24 fps), `master.srt` | ffmpeg |
| 9 Shorts | master timeline + vertical frames | `short1.mp4`, `short2.mp4`, `shorts-map.json` (exact master seconds per span) | ffmpeg |
| 10 QA | files + manifests | `qa.json` against the frozen criteria | `qa_animation.py` |
| 11 Review | files | watched critique with timestamps; three-stage approval | existing approve chain |
| 12 Publication | approval | existing `publish.yml` / `publish-shorts.yml` | existing controls |

Order matters: the **voice is made before the animation**, and each scene lasts exactly its span
on the voice timeline. Picture never waits for or stretches the voice.

## Rules

- **Motion.** Real character animation at 24 unique fps (walk cycles with weight, head and eye turns,
  gestures, breathing). A camera move over a still never counts. Repeating frames to fill the container
  rate is a duplicate and fails `fluidity`. Only holds declared in `scenes.json` (≤ 2 s) are exempt.
- **Continuity.** Each scene's `start_state` equals the previous scene's `end_state`. Same models,
  wardrobe, props and light in master and vertical cameras.
- **Resolution.** Master renders natively at 1920x1080; Shorts render natively at 1080x1920 from
  their own cameras. No upscale, no crop of the master.
- **Shorts.** Exactly the spans named in `scenes.json` `shorts`, at speed 1.0, cut on sentence
  boundaries, each ending with the CTA line. `shorts-map.json` records each span's master start/end.
- **Scripture.** `Thou shalt love thy neighbour as thyself.` — Matthew 22:39 (KJV), spoken and carded exactly.
- **CTA.** `Subscribe to this channel for more stories of everyday faith.` — spoken and on screen, last.
- **Corrections.** A defect names scene ids. Only those scenes' chunks are re-rendered, and only the
  checks that depend on them re-run (render identity changes; the rest keeps its hashes).

## Render identity

`render_id = sha256(canonical JSON of {script, scenes, voice.wav, music, srt, every bundle file,
blender version, engine, samples, fps, resolution, criteria})`. Review and approval bind to it.
