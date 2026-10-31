# HeroVerse: actual audiovisual review

This file specifies review evidence and the unchanged rubric. `../SYSTEM.md` determines the current workflow.
The name CLAUDE_REVIEW and legacy `claude-review-v1` interfaces do not identify who performed a new review.

## Authorized identities and format routes

BibleShorts follow their own episode route: source/preflight → composition → complete audiovisual review →
qualified episode record → `publish-episode.yml`. Historical BibleShort08 has a Claude session review.
The owner authorized the tested native Gemini route for Short09 on 29 October. It records its actual
`gemini-3.8-flash` identity; that authorization is not a claim that all calibration samples passed and not an
approval of any video. A permitted session must record its true identity and actual access to audio and video.

Long reviews use the explicit `publish/owner_quality_policy.py` LONG_REVIEWERS allowlist:
`claude-session-reviewer` and `gpt-6-astra-session-reviewer`. Long evidence retains the existing schema/interface,
then goes through `approve.yml` → `prepublish_gate.py` → `publish.yml`. Only that workflow writes its APPROVAL.json.

Bible-production still, thumbnail and source approval writers require the actual `--reviewer MODEL` from their
existing allowlist and record it (E149). Preserve historical approvals as recorded. Never relabel a GPT review as
Claude, a provider review as a session review, or a construction target as an observed score.

## Required viewing and hearing

Review the complete actual master, bound by its media hash. Verify its technical evidence and package first.
Observe the opening, every narrative segment and the ending with native audio and video. Record heard excerpts,
speaker/delivery observations, image/action correspondence, motion and timestamped defects.

Contact sheets, source frames, the full script and waveform/loudness measures are supporting evidence.
A frame sheet does not establish what was heard. Passing loudness, peak or speech-presence measurements do not
by themselves justify a score for diction, expressiveness, music balance, pronunciation or audio continuity.
If the available executor cannot actually hear the master, that audiovisual review is not complete.

Inspect the relevant source/scene evidence, captions and word timing, title, thumbnail, description, disclosure,
originality comparison and support critique. Technical/source findings remain binding independently of the score.

## Rubric (0–10 each)

opening_and_promise, picture_quality, figure_and_background_integrity, captions_readable_and_synced,
audio_clarity_and_mix, pacing_and_visual_variety, scripture_on_screen, policy_safe; then overall.

Anchors: 10 = nothing to improve; 9.5 = one tiny issue; 9 = minor issues a viewer would not mention;
8 = noticeable issues; 7 = clearly amateur in places; below 7 = fails.
Each item must be ≥7; the base review floor is overall ≥8, and every new upload needs the owner's overall ≥9.5.
The construction target is 9.5 in every dimension; it does not silently change the existing individual-item gate.

Each sub-9.5 score names its issue and timestamp with grounded evidence. Preserve raw results, scores and failed
reviews. Correct the demonstrated defect and review the changed file. Do not repeat an unchanged master to seek a
higher score, copy a score across hashes, omit unfavorable findings or fill an absent measure with PASS.

## Native Gemini evidence

`native-review.yml` → `production/bible/native_review.py` obtains exact-file native audio/video evidence with the
existing configured key and a fresh key-bound Free Tier readback. Upload sessions and evidence are encrypted to
the operator certificate; recovery keys and private media stay outside the public repository.

Invoke once for the exact master under the existing concurrency/lease and saved request identity. Reconcile an
uncertain upload/interaction by its saved IDs. Do not replace a timed-out POST with another submission.
The evidence records the actual model, raw answer, media hash, complete timeline coverage and explicit 4 fps
video sampling with native audio. State that sampling accurately; it is not complete 30 fps frame inspection.
Validate the evidence shape and grounding, including traceable heard content, before consuming its scores.

Native evidence does not create an approval itself. Source, thumbnail, applicable QA, current construction and
publication checks still need their real results. A retained low score remains a diagnostic of that reviewed file.

## Review records and previews

For a BibleShort, retain the complete evidence with the exact master and record the actual review in its episode
record before `episode_build.py check-record` and `publish-episode.yml`. Preserve the schema expected by the existing
publisher; no new long-style approval file is introduced.

For a long, retain `inspection/claude_review.json` with version, actual model, pilot_id, output_sha256, reviewed_at,
the eight scores, overall, timestamped issues, strongest_moment and evidence. The current long handoff and automatic
gate bind it to the exact file. Use the normal branch/PR/checks path.

Source inspection and short contextual samples happen before a full final render. A long's existing
`pilot-preview.yml` / `preview_gate.py` checks stay bound to its actual script and source evidence. Preview review
identifies construction defects early; it cannot approve a complete master the reviewer has not watched and heard.
