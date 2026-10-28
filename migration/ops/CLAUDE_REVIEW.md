# Session review (Claude since 2026-10-24; GPT continuity, 2026-10-28)

Owner, 2026-10-24: "replace gemini-3.8-flash; I cannot have this in the system; find another AI". Every free Gemini
candidate failed the calibration (`evidence/reviewer-calibration/`), so Claude became the designated reviewer.

## Explicit reviewer handoff
For the owner's request on 2026-10-28 that GPT take over the project's continuity, the long-video allowlist is
`publish/owner_quality_policy.py`'s `LONG_REVIEWERS`: `claude-session-reviewer` and
`gpt-6-astra-session-reviewer` only. `long_review.py`, `prepublish_gate.py`, automatic approval and the final upload
check all use that same list. No prefix, other GPT model or automatic fallback qualifies. The Shorts policy is
unchanged.

The reviewer must inspect the evidence below and record its **true session identity** in `model`; never label a GPT
review as Claude. `inspection/claude_review.json`, schema `claude-review-v1` and existing diagnostic names stay as
legacy interfaces so the same approval trigger and stored Claude evidence remain compatible. Keeping those names
does not change the reviewer identified in the record. The rubric, hash bindings, frozen QA and 9.5 owner floor
are unchanged. This handoff neither creates a review nor approves a video: only the existing
`approve.yml` → `prepublish_gate.py` path may write `APPROVAL.json`.

Bible-production still, thumbnail, per-shot and source approvals use the same explicit session identities (E149).
Their writers require `--reviewer MODEL` and record `model`; still/thumbnail `by` records the same actual identity.
Never omit the identity to imply a historical Claude review. Existing historical approvals without a `model` stay
unchanged; a present unknown identity is refused by the production/publish consumer. This does not change the
separate Gemini Shorts-from-long review policy, authorize a generation provider, or substitute for viewing.

## When
Every main-clock run: `render_queue.py migration/production migration/publish/ledger.json review 72` lists due renders
with QA PASS and no review for their hash. Each one is reviewed in the same run by a designated reviewer.

## What is looked at (evidence)
- `inspection/review-sheet.jpg`: 16 frames evenly across the video at 640×360 (picture, captions, cards).
- `inspection/opening-sheet.jpg`: the first 40 s, every 2.5 s (hook and promise).
- `inspection/pilot-contact-sheet.jpg`: a frame every 20 s (pacing, variety, repetition).
- `inspection/thumbnail.jpg` and `out/thumbnail_check.json` (R16).
- `out/timeline.json` and `script.json`: the full spoken text, the hook within 8 s, roadmap, re-hooks, CTA (R12, R13).
- `out/qa.json`: the objective audio and speech measures (loudness, true peak, speech presence, WER, wpm, music
  under the voice). The session reviewer does not hear the file; the frozen QA measures it and already failed anything outside
  its bands.
- `out/package.json`: title (R14), description (R15), chapters.

## Rubric (0–10 each; the same items as before)
opening_and_promise, picture_quality, figure_and_background_integrity, captions_readable_and_synced,
audio_clarity_and_mix, pacing_and_visual_variety, scripture_on_screen, policy_safe; then overall.
Anchors: 10 = nothing to improve; 9.5 = one tiny issue; 9 = minor issues a viewer would not mention; 8 = issues a
viewer notices; 7 = clearly amateur in places; below 7 = fails. audio_clarity_and_mix is scored from the QA
measures (each band met with margin = 9.5+). Every score below 9.5 names its issue with a timestamp.
Gate: items ≥ 7 and overall ≥ 8; publication needs overall ≥ 9.5 (owner floor).

## Output
`inspection/claude_review.json`: `version` claude-review-v1, `model` the actual designated session identity, `pilot_id`,
`output_sha256` (the render's hash), `reviewed_at`, the eight scores, `overall`, `issues` (list, timestamps),
`strongest_moment`, `evidence` (the files read). Committed through a branch, PR and squash merge; the push starts
`approve.yml`, which binds it to the file and runs every other gate.

## Preview review, before the full render (owner, 2026-10-24: "built for 9.5, no rework")
A full render takes about 2.5 h, so every script is previewed first (`pilot-preview.yml`, ~15 min, dispatched by the
heartbeat from `render_queue.py ... preview 72`). Every main-clock run lists the previews to review with
`render_queue.py migration/production migration/publish/ledger.json preview-review 72` and reviews each one:
- `inspection/preview/opening-sheet.jpg`: the opening rendered for real, every 2.5 s for 60 s (hook, captions, mood).
- `inspection/preview/footage-sheet-NN.jpg`: every footage clip of the FULL video in pages of 12, three frames each
  (start, middle, end), numbered with its id: each clip must fit the script's mood (night prayer = night picture, E69/E71), show no modern
  object, person, text or brand, and be sharp. In a story long each clip must also show what its segment says
  (`segments[].shots`: the serpent on the serpent's words, the river on the river); a clip that only fits the mood is
  an issue (owner, 2026-10-25).
- `inspection/preview/thumbnail.jpg`, `script.json` (hook within 8 s, promise, roadmap, title, description).
Same rubric and anchors as above; footage counts once for the whole video. Output: `inspection/preview_review.json`
with `version` preview-review-v1, `pilot_id`, `script_sha256` (from `inspection/preview/preview.json`), `reviewed_at`,
the eight scores, `overall`, `issues` (each with the clip number or the second), `evidence`. Committed through a
branch, PR and squash merge. Below 9.5, fix the cause in the script (e.g. reassign footage, rewrite the hook): the
changed script is previewed again automatically. `render_pilot.sh` refuses a full render unless this review of the
current script is at 9.5 or more (`preview_gate.py gate`), on the engine and on the public runner alike.
Every main-clock run also runs `render_queue.py ... reassign 168`: a pilot listed there still names clips the library no
longer approves, so preview and render skip it (E78) until `footage/assign.py PILOT_DIR` reassigns it (PR as above).
