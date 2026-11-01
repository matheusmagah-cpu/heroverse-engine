# Bible-story construction: build for 9.5

Use the current workflow in `../../SYSTEM.md`. This guide specifies how to construct the actual episode before
final review. Preserve valid sources and the accepted audio; correct a demonstrated defect in its source,
framing or sequence. An intended score is not a source approval or an audiovisual review.

Pavo is the current first route for the hook and speaking Keeper/characters, with a fresh exact zero-credit quote,
current shared capacity and approved references. Appropriate other visuals may use licensed/public-domain video
or GPT-generated stills with cinematic motion. Record the actual origin and rights. Camera movement alone does not
prove body action, fluid motion or lip-sync. Use the applicable format's existing checks, never a misidentified
provider or unrelated frozen profile. No new spending or unqualified paid fallback.

## Prompt structure

Describe five things in this order:

1. **Cinematography:** shot size and one camera move.
2. **Subject:** the concrete person or object actually shown.
3. **Action:** one dominant physical action.
4. **Context:** period, place, time, weather and light.
5. **Style and ambience:** the series' visual anchor and the intended feeling.

Duration and aspect belong in the tool fields. Write observable action rather than metaphors. Use positive
descriptions instead of lists of unwanted objects that can prime a model to draw them. Match the selected source
to the exact words and dramatic purpose; a stock description or prompt is not evidence of what the source shows.
Use cut transitions; a deliberate fade to black is reserved for an intentional ending, not every scene change.

## Identity, period and recurring objects

`production/characters/characters.json` is the character identity record. Every visible named character needs
APPROVED references; prompts retain the exact look and a valid wardrobe variant. Send the appropriate approved
references through the selected route and keep their hashes. New characters are qualified before use.
God is never a person, face, body or throne: exact KJV words play over the appropriate non-person scene.

Every scene uses its validated period setting and exclusions from `plan_check.py`. Inspect for actual modern
buildings, roads, clothing, equipment, symbols and writing. Anonymous figures may appear only as the permitted
rear/silhouette coverage; an unapproved face is not made acceptable by calling it anonymous.

The ark stays the same recurring prop, with its approved reference images. For current flood prompts, use
`plan_check.ARK_PHRASE` exactly:

> a giant long rectangular wooden crate of rough planks smeared pitch-black, with a flat plank roof and flat square ends, as tall at both ends as in the middle

Use the positive phrase within the shot's sentence; do not add alternate vessel names or negated mast/funnel
descriptions. Keep the flood period sentence and prop-reference proof required by the current source checks.
Inspect the actual geometry, scale and continuity. A correct prompt does not establish a correct image.

For image-first requests, inspect and approve the actual still before requesting motion. Keep its source hash in
the request. Describe the required motion/camera without redescribing an incompatible second composition.
Scene stills, source clips and thumbnails retain their own exact approvals and actual reviewer identities.

## Built for 9.5 before compose

Complete source/script checks before the full final compose, including free and imported edits. Resolve
construction defects in short contextual samples with the incoming/outgoing cuts, accepted sound and captions.

1. Inspect every selected source and its actual final-format crop. The intended subject stays visible, with
   sound anatomy, identity, period and texture; source descriptions alone do not qualify it.
2. The picture matches the exact spoken units and advances the dramatic purpose. Check observed action and
   continuity, including the acted climax; camera-only motion is classified honestly.
3. Construct readable, correctly timed captions and a clear mix using the existing Short engine parameters.
   Its output is 1080×1920 at 30 fps, with large captions and a mix targeted near −14 LUFS.
   KJV Scripture is set apart (E249): gold serif italic, with a "Genesis 7:9 · KJV" citation (from the line's
   `reference`) shown for the whole quotation; our own commentary stays in the normal white captions.
4. Inspect the composed picture and review the complete actual audio/video before publication. Contact sheets
   support the review; they cannot establish sound quality. Every demonstrated sub-floor defect is corrected.
5. Downloaded candidates pass `clip_check.py` before composition: decode, opening/ending, size, frame rate and the
   relevant visible-content checks. Reused sources retain their byte identity and valid approval.
6. Use cuts between scenes. Keep intentional dark transitions explicit; no accidental black flashes from fades
   or wipes. Do not hide a coverage gap with an unreviewed transition.
7. The final file passes `clip_check.py --composed` and its applicable technical checks. Record actual measured
   results against the file hash. A DRAFT render receipt is not final audiovisual or publication approval.
8. Every Scripture line is referenced and passes `kjv_check.py` against the pinned KJV text before new speech.
   Preserve an accepted existing voice track. Do not count unreferenced KJV quotation as original narration.
9. The current Short contract passes `publish_episode.short_problems`: measured 170–179 seconds from part 7,
   ≥40% original spoken words, an original insight of at least 20 words and a close naming the full story.
   The narration is recorded as scripture/story/insight/cta; known older published exceptions do not set new targets.

### Actual construction record

For every source interval, retain its real frame boundaries, exact spoken units, dramatic purpose, source hash,
observed figures/action, movement capability, approval evidence and remaining defect. Apply the eight dimensions in
`../../ops/CLAUDE_REVIEW.md` while constructing the source and its contextual sample. A target of 9.5 is not a
measured grade. Source approval and the final complete audiovisual review remain separate evidence.

Inspect first/middle/last frames for a crop or movement change and the corresponding contextual sample. Fix the
demonstrated source, framing or sequence before another complete final render. Reuse unchanged accepted work.
Never repeatedly submit an unchanged master to obtain a more favorable score.

For a private preserved edit, reconcile the plan with the actual bound timeline before acting on stale refusals.
Measured frame/PCM duration and narration estimates are different evidence. Keep the original audio/mix/captions,
true provenance and explicit unknowns. `episode_build.py import-edit` preserves those inputs without synthesizing
voice, retiming, extra gaps or a tail. Its receipt and construction samples remain DRAFT evidence until qualified.

## Long-first: the centre 9:16 safe area

Owner, 2026-11-01 (E259): after the Noah compilation the story is made as a 16:9 long first (plan `"track":
"buzzy-long"`, `"aspect_ratio": "16:9"`, about 8–12 minutes) and its Shorts are 9:16 centre cuts of it
(`short_cuts.py`). Every picture must survive that crop:

- The subject (the speaking face, the acting figure, the object the line names) stays inside the centre 9:16 column:
  the middle 56 % of the frame width (607 px of 1920 at full height). Wide establishing shots may fill the frame, but
  what the line is about stays in that column.
- Every scene, Keeper and still prompt says so in words: "centred in the frame" (`plan_check.SAFE_AREA_UNSTATED`
  otherwise), and names no off-centre framing — off-centre, rule of thirds, split screen, at the left/right edge or
  third (`SAFE_AREA_OFF_CENTRE`). FLUX stills of this track get the centre-column style (`scene_stills.LONG_FIRST_STYLE`).
- The words cannot prove the picture: the source review still looks at the actual 16:9 frame and its centre 9:16
  crop. A cut may move its window (`x`, 0–1) for one range; a subject that leaves the column is a [b] defect of the cut.
- The long's own captions are burned at 16:9 sizes (about 7 % of 1080 px, four words a card, `short_engine.caption_style`);
  the caption-free master is kept for the cuts, which get the Short's own caption style from the same sentences.

## BibleShort story grammar

The plan is `bible-plan-v2`, with narration records and ordered shots. `plan_check.sequence` gives the spoken
sequence: narration in the Keeper's pinned voice and each speaking character's own line/voice.

- **Opening (0–3%):** a spoken conflict starts at zero, through an approved character or God's exact KJV voice.
  The Keeper, a title card or unrelated atmosphere does not open the episode.
- **Stake/open loop (3–10%):** establish the danger, question or conflict clearly.
- **Escalation (10–60%):** rising story steps with a visual action and continuing question; cuts maintain momentum.
- **Climax (60–80%):** the decisive story moment is acted, with people on screen and a `climax:true` scene.
  If God's line delivers the turn over sky/light, the acted scene following it supplies the climax.
- **Payoff (80–85%):** show the outcome rather than adding another unfulfilled promise.
- **Keeper close (85–100%):** only after the last climax, for the original insight and CTA. He closes the story.
  Keeper and lesson shares are each ≤25%; the composition uses actual intervals, not a convenient word estimate.
  Aim for the existing shorter lesson target where the story supports it.

The current spoken-line route retains exact character/voice bindings and the existing limits in `plan_check.py`,
`voice_pace.py` and `episode_build.py`. A new regular plan is measured before dispatch; the measured full duration
decides its length, not a word-count estimate. Quotes are exact KJV and referenced; narration cannot invent a
character's dialogue. God's voice is pinned offscreen and the source is checked for visible faces.

A talking clip must match its exact audio, references and prompt, with passing speech and lip-sync evidence.
The regular route's existing line/clip retime rules apply before acceptance; an imported accepted master is not
stretched later to fit a replacement. Preserve actual failures and their measures. A good clip from another line
does not establish synchronization for this line.

Approved reused clips are selected by their exact hashes and the supported request/reuse binding. Check current
revocations, aspect, character identity, source coverage and the changed context. Reuse does not imply generation
and does not create a new review score. Whether repeated imagery harms the episode is judged in the complete result.

## Keeper voice-over: authorized Plan B

A Keeper shot may explicitly carry `voiceover:true`. It shows him silent, with his lips closed, while the accepted
narration plays as voice-over. The current Genesis09 plan permits this mode. A Keeper shot without that flag is a
talking shot and must pass its actual speech/lip-sync checks.

- Keep the approved look/wardrobe and the appropriate `talk_refs` frame. The prompt says his lips are closed and
  he is silent; it names no speech. He faces the lens with his head level and a static camera.
- This request sends no input audio and requests no speech. Strip incidental provider audio. The original voice
  track carries his words and captions unchanged.
- Use the approved still-mouth source and its matching evidence. The existing `lipsync_check.py --still-mouth`
  tests mouth motion, sustained opening and face coverage. Its recorded failures remain failures.
- The established checks include face coverage ≥80%, no talking-window motion above the existing threshold and
  no sustained open mouth after the allowed settling period. The implementation, calibration and exact tool
  version determine the result; never replace them with an asserted boolean.
- The regular build uses one unbroken source from its start, with at most the existing 1.3 slowdown and no loop.
  The line plus its actual gap/tail must fit the source coverage rule. Preserve the audio; a replacement needs
  its own actual visual coverage and contextual check.
- This mode keeps the same placement, ≤25% shares, story purpose and 9.5 source/final quality requirements.
  It is a legitimate presentation choice, not a passing label for a rejected talking clip.

The preflight's still-mouth probe requirement belongs to the exact prompt/reference. Reuse existing matching
qualified probes and approved footage; do not generate replacements merely because the next executor starts.

## Existing build and review order

For a regular episode: `plan_check.py --strict` → measured voice/timeline and references → source probes/review →
`approve-shot` or the supported source approval → current preflight/verify-preflight → `episode.yml` assembly →
composed technical checks → complete actual audiovisual review → episode record/check-record →
`publish-episode.yml` → public/processed receipt.

The source probe owns bounded generation, shared quota and zero quote. Assembly downloads only the approved bytes
and checks them again; it does not regenerate them. A failed probe is diagnosed before any authorized retry.
An imported edit resumes at its missing qualification and preserves accepted inputs through the existing import
route. Detailed command interfaces and shared execution are in `../../OPERATIONS.md`.
