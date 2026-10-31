# Bible-story long: active design and technical interfaces

`../../SYSTEM.md` is the current operating contract. This guide describes the existing long-specific grammar,
source paths, audio, preflight and build. Current readiness comes from the actual plan, approvals and evidence,
not a dated estimate in this guide. `../../evidence/handoff/CURRENT.md` carries the next delivery.

A long uses `bible-long-plan-v1`, `structures/bible-story-long.json` and the exact frozen criteria selected by its
plan. The default v3, explicit v4, recorded v4 owner exception and explicit v5 have distinct supported readers.
Read the plan's `criteria` and current source policy; do not replace them with a different profile or edit frozen
rows to pass a source. Their files/hashes remain pinned by long_plan_check, qa_pilot, render_queue and prepublish_gate.

The delivery is current sources/preflight → `long-build.yml` → exact long handoff and technical evidence →
complete actual audio/video review → `approve.yml` → `prepublish_gate.py` → `publish.yml` → public/processed readback.
The true session identities are those in `owner_quality_policy.LONG_REVIEWERS`; `../../ops/CLAUDE_REVIEW.md` defines
evidence and the unchanged overall ≥9.5 floor. A contact sheet alone is not final audiovisual review.
The BibleShort has its separate episode publisher. No readiness, generation or publication is granted by this guide.

## 1. The plan grammar: every beat of the structure, in our format

A long plan is a Short plan (`bible-plan-v2`) laid out over the beat map of `structures/bible-story-long.json`. It
uses the same scene, speaker, God voice-over and Keeper shots, and the same `plan_check` functions check them. Each
shot names its `beat`, and chapter shots name their `chapter`. There is one chapter per Short of the arc, and each
chapter's title is that Short's title.

| Beat (structure) | Our format | Check (code) | Number from |
|---|---|---|---|
| cold_open 0-30 s, acted, never the Keeper | The first shot is a scene whose spoken line starts at 0 s. A character or God speaks the conflict (`conflict: true`). It ends on an open question. Its words end by 30 s, and the build holds its last frame (under the music, at most 3 s) so the Keeper starts at exactly 30 s. | OPEN_NOT_SPOKEN, COLD_OPEN_CONFLICT, KEEPER_IN_COLD_OPEN, COLD_OPEN_LENGTH (> 30 s, on its own), COLD_OPEN_SHORT (more than 3 s of held frame), COLD_OPEN_NO_QUESTION | gate.cold_open_s, keeper_in_cold_open; QA v3 grammar.first_shot |
| keeper_promise 30-50 s | Keeper shots only, facing the lens with the supported talking or explicit Plan B voice-over route. Lines of kind `promise`. | KEEPER_PROMISE_LENGTH, KEEPER_BEAT_SCENE | gate.keeper_promise_max_s (= the beat's at_s span) |
| chapters, one per Short | `chapters` lists arcs.json's Shorts in order. Acted scenes use the arc's approved cast. | ARC_SHORTS, CHAPTER_EMPTY, CHAPTER_ORDER | arcs.json |
| re-hooks >= 6, one at every chapter end | A narration line or spoken line with `rehook: true` | REHOOKS, CHAPTER_END_NO_REHOOK, REHOOK_GAP (<= 240 s apart: the 4-min chapter rule) | gate.rehooks_min, rehook_gap_max_s |
| climax at 0.6-0.85, on the KJV line | Exactly one `climax: true` acted scene with people on screen. A referenced line is spoken in that shot or the shot before it (God's voice-over or the hero). | CLIMAX_COUNT, CLIMAX_POSITION, CLIMAX_NOT_ACTED (E92), CLIMAX_NO_KJV_LINE | gate.climax_at |
| payoff | `payoff` shots after the climax | PAYOFF_MISSING, PAYOFF_BEFORE_CLIMAX | - |
| keeper_insight <= 125 s | Keeper lines of kind `insight` (>= 20 words). Cut-aways are allowed (windows of earlier clips). | KEEPER_INSIGHT_LENGTH, INSIGHT_SHORT | gate.keeper_insight_max_s |
| keeper_close <= 30 s | The Keeper is last, with a comment question and the next story | KEEPER_CLOSE_LENGTH, KEEPER_MUST_CLOSE, CLOSE_NO_QUESTION, CLOSE_NO_NEXT | gate.keeper_close_max_s |
| Keeper <= 25 % | Keeper shots appear only in the three Keeper beats | KEEPER_SHARE, KEEPER_OUT_OF_BEAT | gate.keeper_share_max |
| slow stretches and establishing share | The structure bounds voice/visual runs; the selected profile supplies its actual establishing-share limit | SLOW_STRETCH, ESTABLISHING_SHARE | gate.slow_stretch_max_s; selected grammar.establishing_share_max |
| one complete story, 14-18 min | The estimate: each line at its voice's measured Kokoro pace (VOICE_PACE), 0.6 s between lines (LONG_LINE_GAP) | LONG_LENGTH | gate.length_min |
| no burned captions | `burned_captions: false`, with the .srt track (QA v2/v3) | BURNED_CAPTIONS | gate.burned_captions |
| 16:9 | `aspect_ratio: "16:9"`, inspected on the actual source and final crop | ASPECT_RATIO | gate.aspect_ratio |

**One source, no copies.** The numbers come from two places:
- The structure's `script.gate` block, read through `script_check.story_gate()`. That is the same reader
  `structure_problems` uses for the long's script (#415). The block contains the numbers the beat map states, and a test keeps the gate equal to the beat map.
- The frozen QA file.

**Characters stay the same.**
- Every character in a long is a `characters.json` entry with its `look` word for word (CHARACTER_UNKNOWN,
  CHARACTER_LOOK_CHANGED). That is the same entry, seed, references and voice as in the Shorts. The rules are
  `plan_check`'s own shared helpers (`character_problems`, `figures_problems`, `scene_seconds_problems`,
  `lines_order_problems`, `establishing_only`), so the Short and the long cannot drift apart.
- An entry with no `look` is CHARACTER_NO_LOOK. An APPROVED entry with no kept reference image is CHARACTER_NO_REFS,
  or KEEPER_NO_REFS for the Keeper: the same face could not go in.
- A character named in a prompt must be in that shot's `characters`, so its references go in (CHARACTER_NOT_LISTED).
- A DRAFT character is one pending row (CHARACTER_PENDING). `--strict`, which the build runs, refuses to start while
  any pending row is open.
- God speaks only as a voice-over over a shot with no person (GOD_SHOT_*).
- The Keeper never acts in a scene. His shots pass the same five-part prompt rules as every shot (PROMPT_*,
  GOD_AS_A_FIGURE), plus his look, wardrobe and pose (KEEPER_POSE, E98).
- A talking speaker needs a human face (TALKING_WITHOUT_A_FACE), under any QA version: lipsync_check reads a face.
- `rehook: true` belongs to a line: on a shot that speaks no line it is REHOOK_ON_SILENT_SHOT.
- Words are never carried by landscape alone (ESTABLISHING_ONLY: a voice run whose shots are all establishing). The
  Short's 2 s establishing hold does not apply: a long's holds are 4-7 s.

**The frozen QA, checked on the plan.** The check reads the selected profile with its sha256 pinned. The following
baseline v3 rows are retained by the later profiles unless their explicit rows say otherwise:

- Every cut is a 4-7 s hold (`grammar.scene_seconds`: HOLD_UNDER_QA, HOLD_OVER_QA). A talking line is checked at its
  slowest pace.
- "You" appears in the first 8 s (HOOK_SECOND_PERSON).
- The pace is 115-165 words a minute (WORDS_PER_MINUTE_EST).
- Speech presence is >= 0.85 (SPEECH_PRESENCE_EST).
- v3's three acted-long rows are checks:
  - the first shot is the acted cold open;
  - figures are approved characters only, and a DRAFT character stays pending;
  - all picture may be Pavo, but every talking clip must pass lipsync_check, so its speaker must have a human face.
- Against v2, the same rows show as pending owner rows (QA_CONFLICT_*). The check never decides them.

**Windows.** A shot with `window_of: "<earlier scene>"` shows another part of that clip, with no new generation.
- It is never right after its source (WINDOW_ADJACENT).
- The clip must cover all its holds, slowed 1.3x at most (FOOTAGE_SHORT).
- Windows are used for the Keeper's recap and for intercutting.

## 2. Source coverage and capacity

Reuse approved matching sources first. Source selection, request identity, licences, references, revocations and
actual context must match the current plan. The long's 16:9 crop is inspected directly; a vertical Short clip or a
previous speaking line does not automatically cover a different picture or audio requirement.

A `window_of` shot reuses a distinct part of its approved source. Check non-adjacency, actual combined coverage
and the existing maximum slowdown. No generation is needed for a valid window. Camera-only still movement stays
classified as such and must meet the applicable long source/grammar requirements.

Pavo work belongs to the existing source probe path, with current shared quota, exact zero-credit quote and
durable request identity. Reconcile saved jobs before submitting another one. A historical timing measurement
or concurrency experiment is not permission to generate a chapter in parallel or a promise of a one-day build.
Use the current workflow's actual concurrency/capacity. The build assembles approved bytes and does not generate.

The existing long upscale matrix handles approved sources at the declared profile's frame. Estimate wall-clock
work from current accepted inventory and observed runs; preserve matching completed upscale artifacts.
Historical feasibility measurements remain in `evidence/long/` and `evidence/pavo/`, not as a pending test queue.

## 3. Audio

- **The Keeper.** He narrates in `am_michael`, the voice the QA pins: `qa_pilot.voice_model_pinned` reads the
  manifest's narrator voice. He is on screen only for the promise, insight and close, using the selected qualified
  talking route or explicit silent Plan B. Preserve the accepted voice and actual source checks.
- **Each voice has its own pace, measured** (`evidence/long/20261026/arc-01-voice.json`, the arc-1 draft voiced
  locally with the pinned model):

  | Voice | Words a second |
  |---|---|
  | The narrator (am_michael) | 2.874 (lines 2.21-3.65) |
  | God (am_onyx at 0.9) | 2.811 |
  | Adam (am_fenrir) | 3.975 |
  | Eve (af_heart) | 3.732 |
  | Noah (bm_george) | 2.970 (evidence/long/20261026/noah-scoffer-voice.json) |
  | The scoffer (am_puck) | 3.579 (evidence/voice/20261026/kokoro-pace.json; 3.425 in the six lines above) |
  | The serpent (bm_fable) | 2.728 (kokoro-pace.json) |

  The table is `voice_pace.py`, shared with the Shorts' plan_check. At a single 2.75 words/s the first arc-1 voicing
  had five talking lines under the 4 s a talking clip fills. Both checks give each speaker two measured bounds: the
  table's (fastest run) for a line too short, and `VOICE_SLOWEST` (the slower of the slowest run x 2.25/2.75 and the
  slowest line measured, E104) for a line too long or unreachable. The narration is its pace x 2.25/2.75 (the Shorts
  keep 2.75 / 2.25). A talking voice not in the table is refused (VOICE_PACE_UNMEASURED).
- **Talking lines.** A QA hold is 4-7 s: the line at its voice's slowest pace plus the 0.6 s gap must fit 7 s
  (HOLD_OVER_QA), and at the normal pace it must fill 4 s.
  - The Keeper: 11-14 words.
  - Adam: about 14-20 words.
  - Eve: about 13-19 words.
- **Kokoro-route characters** speak in their own voices from the same pinned model (`voices-v1.0.bin`, sha256
  bca610b8...):
  - Adam am_fenrir;
  - Eve af_heart;
  - God am_onyx at 0.9 speed, voice-over only.

  The QA pins the model hash and the narrator voice, so no gate changes. The render manifest must list every
  speaker's actual voice.
- **The serpent is silent.** lipsync_check finds a human face and lips, and a snake has neither, so a talking
  serpent clip would fail every generation (TALKING_WITHOUT_A_FACE). The Keeper narrates its KJV words.
- **Music.** The owned track (`OWNED_MUSIC_SHA256`), ducked under the voice.
- **Loudness.** The story QA wants -16 to -14 LUFS integrated and a true peak at or below -1 dBTP. The Shorts engine
  normalises to -14 LUFS / -1.5 dBTP, at the top edge of the long's band, so the long's mix targets -15 LUFS /
  -1.5 dBTP.
- **Speech rows.**
  - First word within 1.5 s: the cold open speaks at 0 s.
  - "You" within 8 s, measured on the current accepted speech.
  - WER at or below 0.1.
  - Speech presence at or above 0.85, measured on the actual file.
  - Pace 115-165 words a minute. The long uses LONG_LINE_GAP and its measured accepted layout; a previous
    voicing estimate does not establish the current result.

**Profile selection.** Use the profile the plan declares. V3 introduced the acted-long baseline below; v4 added
qualified native speech and v5 added its explicit fallback rules. Older files remain frozen for the records they govern.
The owner's existing permission remains in force: on 26 October, "Sim, régua nova"; on 27 October,
"Libera o pavo no longo." The immutable v3 basis retains the original decision reference. Its three changes from v2 are:

1. Figures: `figure_present_fraction_max` is replaced by `figures_allowed`, permitting APPROVED characters.
2. AI share: `footage_picture_share_min` and `footage_picture_share_counts` are removed;
   `ai_video_picture_share_max` becomes 1.0, with `ai_video_clip_checks` requiring clip_check and, for talking clips,
   lipsync_check. There is no real-footage minimum; the former maximum AI share was 55%.
3. First shot: `title_card_seconds` is replaced by `first_shot`, the acted cold-open conflict.

Everything else is v2's, unchanged: audio, loudness, pace, the 4-7 s holds, the .srt track, the 9.5 floor and the
authorized complete audiovisual review. v2 is v1 with the burned captions replaced by an .srt track. v1 and v2 stay frozen and byte-identical,
and a test asserts all three.

**v3's readers (E126, 2026-10-27).** v2 and v3 renamed keys that the readers indexed directly, so until E126 no
long could be measured or approved. Now:
- `qa_pilot.py` reads v3 by its own rows: `STORY_V3_ROWS` maps every row of technical, speech, rights and grammar to
  the checks that measure it (`grammar_checks_story_v3`: the acted cold open, approved figures with the Keeper only in
  his beats, every Pavo clip's clip_check / lipsync_check / face_check, AI share up to 1.0, no footage minimum, no
  burned captions, the .srt rows). A check whose evidence is missing is UNKNOWN, never a pass. The older pilots keep
  their frozen criteria and grammar.
- `prepublish_gate.py` pins v3's hash and file and adds one item per v3 row (PASS / FAIL / UNKNOWN); `render_queue.py`
  pins v3.
- The .srt track: `captions.py long <compose-timeline.json> <out>/captions.srt` writes it from the voice timeline
  (cues of at most 7 words and 44 characters, the sentence's words unchanged, timed inside its voice span) and prints
  the `caption_track` record the manifest carries. `captions.manifest_srt` is the one track publish_video uploads
  (YouTube captions, never burned in), preflight checks and qa_pilot measures against the script words, the voice
  timeline and the words heard. A v3 long without its recorded track is refused (CAPTIONS_TRACK_MISSING).
- The render manifest the long's build writes carries, beside v4's fields: `holds[].beat`,
  `holds[].characters`, `holds[].shot_kind`; `sentences[].speaker` on spoken lines; per clip `source`, `licence`,
  `model`, `upscaler`, `audio`, `vetting`, `credit`, `sha256`, `clip_check`, `talking`, `lipsync_check`,
  `voiceover`, `face_check`; `burned_captions: false`; `caption_track`.
- Antidote: `test_qa_pilot.py` fails when a frozen QA a plan check reads is not pinned, with the same hash, by
  prepublish_gate and render_queue and read by qa_pilot.

## 4. Readiness of the actual plan

Read the current `plans/<arc>-long.json`, `arcs.json`, character/source approvals and exact preflight binding.
Run the existing strict checks and retain their actual result. Old cast counts, estimated durations, promised
dates or previous PASS reports do not establish readiness after inputs or code change.

Use measured accepted voice timing and the current composition prediction before a full build. Resolve the
specific source, coverage, cold-open, line-length or review-row refusal at its responsible stage. Keep unchanged
approved material and its saved jobs. Do not repeat historical concurrency tests or regenerate every shot.

## 5. Long preflight and approved-source contract

The long shares the existing early-check and approved-source helpers (E106, E114, E99); `long_preflight.py`
holds the long-specific behavior:
- **Preflight before anything is built.** `episode_build.py preflight plans/arc-01-long.json --voice ... --refs --write`
  runs long_plan_check `--strict` and the selected frozen story QA (`episode_build.check_plan`), the pinned Kokoro voice laid
  out at LONG_LINE_GAP against the structure's gate (length, Keeper share, measured), every request through the
  adapter's offline checks and its digest, and every talking line's direct probe. It is BLOCKED (LONG_REVIEW_OPEN)
  while any applicable story QA row or rubric `long` entry of `ops/refusal_registry.json` is `open`. The report binds the plan,
  the characters' entries (look, references, voice), their image records, the matched probes, the review rows and the
  code by sha256.
- **The build ships approved clips only.** `verify-preflight` (the build's first step) refuses a long without a PASS
  report bound to it, with a review row open now, or with a generated shot that has no approved clip of the request the
  plan sends now. `generate_step` downloads those clips and generates none. A `window_of` shot is never generated:
  it ships its source's clip, so it has no digest, probe or approval of its own.
- **Probes.** `shot-probe.yml` takes the long's plan (long_plan_check, 16:9, its own shot ids, windows refused by the
  dispatch guard and by `check-probe`, PROBE_WINDOW_SHOT). For a long, `check-probe` also refuses a plan without a clean
  committed preflight of these exact bytes (LONG_PROBE_PREFLIGHT); only the open review rows and the talking probes
  may still block that report, since neither changes a request. An authorized source reviewer records the actual
  identity and approves one clip per shot with
  `approve-shot` into `shots/arc-01-long.json`.
- **Risk order and resume.** `risk_rank`: talking characters, the Keeper's talking shots, voice-overs, wide and
  establishing scenes, then the rest. `episode_build.py probe-queue PLAN` lists the shots without an approved clip of
  their request now, in that order, cut into batches of one rank that each fit one shot-probe run.
- **Assembly only.** Submission and recovery belong to the probes, not to the build: the build composes
  approved clips (16:9 at LONG_LINE_GAP, the .srt, -15 LUFS, the upscale matrix) and never holds a Pavo secret.

The production estimate (no generation) is `evidence/long/20261027/arc-01-long-production-estimate.json`
(`long_preflight.py estimate PLAN --write`).

## 6. The existing long build

`long-build.yml` (manual, main only, inputs `plan` and `resume_run`; no Pavo secret, nothing generated) runs
`long_build.py` around the Short's own steps:
1. **prepare**: the dispatch guard, `long_plan_check --strict`, `episode_build.py verify-preflight` (PASS report bound
   to this plan, no review row open, every generated shot approved for its request now), then episode_build's
   voice-script, Kokoro, `lines`, `refs` and `generate` (approved clips by sha256, clip_check / lipsync_check / face
   check again). `lines` lays the voice at LONG_LINE_GAP and holds the cold open's last frame in silence until the
   Keeper at exactly 30 s, re-checked on the measured voice (`episode_build.voice_layout` →
   `long_build.cold_open_layout`: COLD_OPEN_LENGTH, COLD_OPEN_SHORT; the preflight predicts the same).
   `long_build.py timeline` cuts the long on the 720p clips before any upscale.
2. **upscale** (matrix, 20 at once): each approved clip through Real-ESRGAN general x4v3 to 2560x1440 30 fps
   (`pavo_footage.render`), recorded with the approved clip's sha256. A window is never upscaled: it reuses its
   source's picture.
3. **assemble**: one cut a shot, every cut 4-7 s (story QA v3 `grammar.scene_seconds`: HOLD_UNDER_QA, HOLD_OVER_QA);
   the shots of one voice run share it equally (long_plan_check's model); a talking shot from its first word at
   normal speed to the next line, its last frame held for the gap; a window shows the next unseen part of its
   source clip (source and windows slowed together, at most 1.3x: FOOTAGE_SHORT). No burned captions; the owned
   music ducked under the voice; two-pass loudnorm to -15 LUFS / -1.5 dBTP, measured again on the file. The .srt
   comes from `captions.track_record` (`captions.py long`), and `manifest.json` carries the
   fields qa_pilot reads for v3 (section 3). The preflight now predicts this compose too (`compose_problems`).
4. **record**: `bible-<long>-sha256-<sha>.mp4` and `bible-<long>-sha256-<sha>.srt` into the release; the report,
   manifest, .srt and a 16:9 sheet on `claude/long-<long>-<run>`. The exact master must receive a complete
   watched-and-heard review (>= 9.5) by its actual authorized reviewer before publication.

`resume_run` keeps the upscaled clips of an earlier run whose artifact (`long-up-<long>--<shot>-<sha16>`) is of the
clip approved now; a shot approved again since is upscaled again.

Image-first shots use 16:9 stills: `scene_stills.py` prepares, crops, finalizes (1920x1080), sheets and
approves at the plan's aspect, and refuses a picture at another aspect instead of stretching it
(STILL_ASPECT_MISMATCH). A historical zero quote does not authorize a new call; verify the exact current request.

## 7. Native speech, reuse and the selected source profile

These are long-profile interfaces. Current SYSTEM direction, the declared criteria and `source_policy` select
the eligible route; they do not authorize a native-audio mode for a different format.

- **Which QA.** A long may declare v4 or v5 through its supported criteria field; the default remains v3. V4 adds
  native-speech rows to the v3 baseline; v5 adds its explicit fallback rules. long_plan_check, qa_pilot,
  prepublish_gate and render_queue pin the applicable files. A different profile is not selected merely to pass a result.
- **Native speech.** On the eligible native long route, `"audio_route": "kokoro"` retains the pinned voice.
  A shot selected for Pavo speech uses sound on and the supported SOUND sentence (`pavo_native.sound_sentence`: the speaker's fixed voice from
  `voices.json`, on camera or off screen, the exact line once, pronunciation hints, the plan's `ambience`, no music).
  A silent scene's request is unchanged, so its approval stays valid. Each kept clip is measured
  (`episode_build.py speech-check`: medium.en words, YAMNet music and singing, loudness, the speaker cosine against
  `voices.json` references, its lips / still mouth / no face) and approve-shot refuses it unless
  `pavo_native.speech_verdict` passes (exact words WER 0, consistent and distinct voice, one gain to -18 LUFS within
  +12 dB, no music, no singing). The voice is bound to `voices.json` by sha256 (review of #476): measured against
  exactly the speaker's recorded reference (VOICE_REFERENCE_MISSING / _MISMATCH; a REFS file that is not that clip is
  refused, VOICE_REFERENCE_FILE_MISMATCH) and against every other speaker's reference (VOICE_OTHERS_MISSING when there
  is none, VOICE_OTHERS_MISMATCH when one is left out). A reference is chosen by an authorized source review (>= 9.5, true identity) of a probed
  native clip that passed every other check: `episode_build.py voice-reference RECORD SHOT ASSET SCORE NOTE`, by PR. The build lays each clip's speech into the voice track at its line
  (`pavo_native.premix`: one gain, 80 ms fades, a continuous 60-900 Hz bed), starts the talking cut at the speech
  onset, then ducks the owned music and loudnorms as before; a native line's layout takes its approved clip's speech
  span.
- **One God voice (owner, 28/10).** A spoken shot may say `"audio_route": "kokoro"` on a native plan and keep our
  Kokoro voice-over (never the reverse: AUDIO_ROUTE_UNKNOWN). God remains one pinned offscreen voice throughout;
  select and verify each actual line through the plan's current routing.
- **Refused words.** A line holding a word Pavo's filter refuses (`evidence/pavo/prompt-blocks.json`) is voiced by
  the supported Kokoro route. Record a new block (PAVO_PROMPT_BLOCKED, E129), reconcile the saved request and
  qualify the eligible replacement; a refusal is not permission for an immediate duplicate submission.
- **R1, reuse.** probe-queue lists a shot with a clean clip of its request (main's records, the shot-probe branches,
  clip inventories) under `awaiting_review`, never in a batch; a spoken shot with a clean clip of its Kokoro request
  keeps that route. An inventory clip on Pavo's CDN is approved with `approve-source ... pavo_reuse` and fetched by
  sha256.
- **R2/R3, budget and fallbacks.** `episode_build.py sources PLAN [--write]` (and probe-queue's `sources`) spends the
  shared available capacity (quota.py) in risk order, the spoken shots first; a silent, character-free shot it does not
  reach gets licensed-footage candidates (APPROVED, seen, frozen licence list, 2560x1440, sharing words with its
  subject and line, no period clash or person) or an APPROVED still of the shot in camera motion; a spoken shot or a
  shot with a character follows the selected profile's stricter source rules, including v5's explicit exceptions.
  An authorized reviewer approves a candidate with `approve-source` (>= 9.5, a note and true identity); the build ships
  that source (footage at its frame, a still rendered in motion at 2560x1440) and the manifest names it per shot.
- **The Keeper at 16:9 (E130).** Plan B (the voice-over Keeper) is a path of the long; under v4 a 16:9 Keeper prompt
  says "Close-up from the chest up, his face large in the centre of the frame" (KEEPER_FRAMING_16X9).

## 8. Planned source allocation and repeat identity

The plan's `source_design` is consumed by `shot_sources.planned_fallbacks`. An eligible shot assigned to
`footage` or `still_motion` does not consume Pavo budget in `episode_build.py sources` and is not queued as a new
generation by probe-queue. The current source policy/profile decides eligibility. `SOURCE_DESIGN_*` checks refuse
unknown or duplicated IDs, incompatible source assignments, invalid windows and missing sources.

The build records a hold's actual source part as `<source shot>#<src_start>`; a distinct window is a different
part of the clip, not permission to repeat the same part. The selected frozen image-repeat rule remains binding.
Review the complete sequence for visible repetition and narrative value.

An owner-authorized source choice must be represented truthfully through the applicable source interface and
profile. A source's origin or licence is never relabeled to fit an older field. Missing technical or rights evidence
stays explicit; no automatic score or passing boolean is introduced by an adapter.
