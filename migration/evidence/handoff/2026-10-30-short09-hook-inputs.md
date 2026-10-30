# Short 09 — hook prepared, no generation submitted

Owner direction, 2026-10-30: use Pavo for the hook and speaking characters/Keeper;
use newly generated GPT images with cinematic animation for the other 17 visuals.
Plan and prepare inputs to reach at least 9.5 before generation, then establish the
actual score through audiovisual review. A target or an approved first frame is
not a review of the resulting video.

Prepared data: `migration/evidence/pavo/prepared/genesis-09-s-voice-20261030.json`.
The strict execution manifest is
`migration/integrations/pavo/private-inputs/genesis-09-s-voice-20261030.json`.
Its file SHA256 is `de9fa240faab052bcf4968de12bbe0929219989b96095ccabe91252be07ffc4c`;
the canonical request digest for workflow input `sha256` is
`1d2213f3d715bbafafa87ec516f101a2e466dafe1741de48851b78fa1f894713`.
No file has been added under `migration/requests/`, no live quote was obtained and
no generation was submitted.

## Exact editorial scope

One visual, 0–10 seconds (frames 0–300 at 30fps), covering the existing God voice
to 6.4 seconds and narrator thereafter. The boundary is inherited from the private
edit binding, not a new word-alignment claim. Both voices stay offscreen. Animate
the exact approved Genesis 09 s-voice first frame: a rigid, flat-roofed black
rectangular ark on dry ground, storm clouds, brief existing lightning, restrained
dust and grass movement, a slow approximately 3% forward camera move to 6.4 seconds.
At 6.4 seconds the storyboard requests a clean cut to a visibly tighter steady
three-quarter view of the same near square end and adjacent long plank wall.
This is intended distinct coverage inside one provider result; the returned
frames must prove it. Neither the cut timing nor two valid takes are claimed in
advance. No figure,
face or mouth for God. No new dialogue, music, heavy rain or floodwater.

The preparation binds the first frame, original 175-second narration, unchanged
final AAC file, captions and the exact first 240,000 PCM sample frames by SHA256.
No audio was synthesized, stretched, copied into a second audio file or sent to a
provider. Request a silent frames_to_video result with one first-frame image,
10 seconds, 9:16, no last frame, no references array, no input audio and sound=false.
Discard any incidental provider audio during later integration. Preserve the
master and its 8,205 AAC packets unchanged.

## Pre-generation checklist and truthful executor limit

1. Re-read the approved first-frame record and verify image SHA256. Confirm the
   prompt preserves its geometry, dry-ground continuity, single camera move and
   offscreen voices. The record's existing score is 9.5; no new score is assigned.
2. Read the active shared lease, current quota and existing claims. Use one stable
   request identity bound to the input hashes and slot. Persist the claim before
   uploads or creation. Allow one generation, no automatic retry, at most 2 quota
   units. A unique nonce cannot override an earlier claim.
3. Obtain a fresh exact quote for precisely these inputs. Both required_credits
   and final_points must be zero, is_estimate=false and zero_cost_confirmed=true.
   No such quote has been obtained by this preparation. The adapter must recheck
   the quote before any upload or creation; a free label is insufficient.
4. Persist the resulting conversation ID and reconcile that same ID with GETs.
   Unknown acknowledgement or missing ID must never trigger another submission.
5. Measure the actual output and normalize only video at 1x, then use 300 frames.
   If output is too short, stop for explicit evidence-based handling. Do not loop,
   stretch or duplicate the next s-finished scene. Preserve all other slots and
   the completed three Keeper clips. Review the definitive combined master under
   the unchanged 9.5 gates; do not manufacture an approval.

The existing Pavo adapter supports this exact first-frame mode. This branch adds
the strict `pavo-private-hook-v1` variant to the existing private workflow: it
accepts only Genesis09 s-voice, 10 seconds, the pinned approved first frame and no
audio fields. Preparation quotes the frame without requesting an audio upload;
submission obtains a second fresh quote through the existing generator. The
existing private certificate, shared lease, quota, persistent claim, encrypted
receipts and GET-only recovery remain in use. A changed prompt digest cannot
reopen the same hook slot, and hook retry_run is refused. No media upload is
needed from the operator for this variant.

The three exact-WAV Keeper variants remain unchanged. The separate pavo-mcp
workflow still only diagnoses or uploads attachments.
The shot-probe workflow requires the full plan (still 20 known blockers), generates
voices unless adopting a run, and invokes MediaPipe/SyncNet. Neither path is a
safe substitute. Do not relabel the hook as Keeper or create a partial plan.

Before dispatch, finish the original Toolkit/Sweep reviews, canonical offline
tests and the normal PR/merge process. No publication gate or QA file is changed.
Use `pavo-private-audio.yml` with the existing plan path, the strict manifest path,
the canonical digest above, the existing public receipt certificate and the live
owner lease ID. Keep reconcile_run/retry_run empty for the single initial claim.
On uncertain result, use only reconcile_run with the original run ID and the
same manifest/digest; never recreate a queue request to force another generation.
Local MediaPipe/SyncNet retry is prohibited after the recorded
automatic-review block; preserve that evidence and defer real AV review to the
definitive master.

## Preserved checkpoint

The three real Keeper clips are integrated into a DRAFT 175-second/5,250-frame
checkpoint, SHA256 b5cf0574443595acc00afe5b5de919ce8673f59f1d2a7747df5db7ee035f97c4.
All 8,205 AAC packets and 68 protected original files are unchanged; the insight
slot uses 346 actual frames plus 14 repeated final frames, and question uses 180
actual frames. These are technical checks, not audiovisual approval. The private
v15 package is valid with 273 entries, preserving all 204 v14 entries byte for
byte. It is a checkpoint before the new 17-image direction, not the final master.
