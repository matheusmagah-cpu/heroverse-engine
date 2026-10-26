# The Bible-story long, built like the Shorts (design, 2026-10-26)

Owner, 2026-10-26: "Adjust the long videos. They need maximum precision. Apply the mined structure and model it to
our format, without forgetting what we already agreed: the Keeper character narrating, and the Bible characters, who
must be the same whenever they repeat across stories."

This is the design with measured numbers, and slice 1 of the build: the long's plan grammar (`bible-long-plan-v1`),
its check (`long_plan_check.py`, tests in `test_long_plan_check.py`, run in pr-checks through `test_plan_check.py`),
the frozen story QA v2 (owner: "Nova régua, sem legenda") and a draft arc-1 plan (`plans/arc-01-long.json`).
Nothing here is built, voiced, generated or published; `episode.yml` and the publishing code are unchanged.

## 1. The plan grammar: every beat of the structure, in our format

A long plan is a Short plan (`bible-plan-v2`: the same scene, speaker, God voice-over and Keeper shots, checked by
the same `plan_check` functions) laid out over the beat map of `structures/bible-story-long.json`. Each shot names
its `beat`; chapter shots name their `chapter` (one per Short of the arc, its title = the Short's title).

| Beat (structure) | Our format | Check (code) | Number from |
|---|---|---|---|
| cold_open 0-30 s, acted, never the Keeper | first shot a scene whose spoken line starts at 0 s; a character or God speaks the conflict (`conflict: true`); ends on an open question | OPEN_NOT_SPOKEN, COLD_OPEN_CONFLICT, KEEPER_IN_COLD_OPEN, COLD_OPEN_LENGTH, COLD_OPEN_NO_QUESTION | gate.cold_open_s, keeper_in_cold_open |
| keeper_promise 30-50 s | Keeper shots only (lip-synced, facing the lens, static camera, E95/E98), lines of kind `promise` | KEEPER_PROMISE_LENGTH, KEEPER_BEAT_SCENE | gate.keeper_promise_max_s (= beat at_s span) |
| chapters, one per Short | `chapters` = arcs.json's Shorts in order; acted scenes with the arc's approved cast | ARC_SHORTS (owner row), CHAPTER_EMPTY, CHAPTER_ORDER | arcs.json |
| re-hooks >= 6, one at every chapter end | a narration line or spoken line with `rehook: true` | REHOOKS, CHAPTER_END_NO_REHOOK, REHOOK_GAP (<= 240 s apart: the 4-min chapter rule) | gate.rehooks_min, rehook_gap_max_s |
| escalation | acted chapter scenes and speakers (no number in the structure) | (the shot rules below) | - |
| climax at 0.6-0.85, the KJV line | exactly one `climax: true` acted scene with people on screen, on a referenced line spoken in it or in the shot before (God's voice-over or the hero) | CLIMAX_COUNT, CLIMAX_POSITION, CLIMAX_NOT_ACTED (E92), CLIMAX_NO_KJV_LINE | gate.climax_at |
| payoff | `payoff` shots after the climax | PAYOFF_MISSING, PAYOFF_BEFORE_CLIMAX | - |
| keeper_insight <= 125 s | Keeper lines of kind `insight` (>= 20 words), cut-aways allowed (windows of earlier clips) | KEEPER_INSIGHT_LENGTH, INSIGHT_SHORT | gate.keeper_insight_max_s |
| keeper_close <= 30 s | Keeper last; a comment question and the next story | KEEPER_CLOSE_LENGTH, KEEPER_MUST_CLOSE, CLOSE_NO_QUESTION, CLOSE_NO_NEXT | gate.keeper_close_max_s |
| Keeper <= 25 % | Keeper shots only in the three Keeper beats | KEEPER_SHARE, KEEPER_OUT_OF_BEAT | gate.keeper_share_max |
| no slow stretch > 20 s | no run of shots without a person on screen, and no single voice run, over 20 s | SLOW_STRETCH, ESTABLISHING_SHARE (<= 15 %) | gate.slow_stretch_max_s |
| one complete story, 14-18 min | the estimate (Kokoro 2.75 words/s, 0.35 s between lines) | LONG_LENGTH | gate.length_min |
| no burned captions | `burned_captions: false`; the .srt track (QA v2) | BURNED_CAPTIONS | gate.burned_captions |
| 16:9 | `aspect_ratio: "16:9"` | ASPECT_RATIO | gate.aspect_ratio |

One source, no copies: the numbers are the structure's `script.gate` block, read through
`script_check.story_gate()` (the same reader `structure_problems` uses for the long's script, #415), and the frozen
QA file. This PR adds to that block only what the plan needs and the beat map already says (aspect ratio, the Keeper
beats' maxima, the 20 s slow-stretch limit, the 240 s re-hook gap); a test keeps the gate equal to the beat map.

**Characters stay the same.** Every character in a long is a `characters.json` entry with its `look` word for word
(CHARACTER_UNKNOWN, CHARACTER_LOOK_CHANGED): the same entry, seed, references and voice as in the Shorts. A character
named in a prompt must be in that shot's `characters`, so its references go in (CHARACTER_NOT_LISTED). A DRAFT
character is one pending row each (CHARACTER_PENDING); `--strict` (the build) refuses to start while any is open.
God speaks only as a voice-over over a shot with no person (GOD_SHOT_*); the Keeper never acts in a scene.

**The frozen QA, checked on the plan** (story QA v2, the rows a plan can predict): every cut a 4-7 s hold
(`grammar.scene_seconds`: HOLD_UNDER_QA, HOLD_OVER_QA; a talking line at its slowest pace), "you" in the first 8 s
(HOOK_SECOND_PERSON), 115-165 words a minute (WORDS_PER_MINUTE_EST), speech presence >= 0.85 (SPEECH_PRESENCE_EST).
The rows an acted all-Pavo long cannot meet are pending owner rows (QA_CONFLICT_*, section 4).

**Windows.** A shot with `window_of: "<earlier scene>"` shows another part of that clip (no new generation), never
right after it (WINDOW_ADJACENT), and the clip must cover all its holds (FOOTAGE_SHORT, slowed 1.3 at most). Used for
the Keeper's recap and for intercutting.

## 2. Footage: how many clips, and what they cost

**Cuts.** A 15-min long cut every 2-4 s (the Shorts' rhythm) would need ~300 holds. The frozen story QA does not
allow that: every hold is 4-7 s (`scene_seconds`), so a 15-min long has 129-225 holds, ~164 at 5.5 s. The draft
arc-1 plan has 180 holds over 14.5 min (4.8 s each).

**Pavo time, measured** (episode.yml on genesis-07-short, 2026-10-26; job step timings from the Actions API, shot
lists from the run logs and the `report.json` on the `claude/episode-genesis-07-short-*-failed` branches):

| Run | Generations in the Pavo step | Step time | Per generation |
|---|---|---|---|
| 40263488773 | 25 scenes, 2 regenerated after an unknown submission, then PAVO_UNREACHABLE (28 submissions) | 8,062 s | 288 s |
| 40278642295 | 5 scenes + 3 Keeper talking clips | 2,469 s | ~274 s a scene with 366 s a talking clip |
| 40285879529 | 3 Keeper talking clips (all refused, E94/E95) | 1,101 s | 367 s |
| 40297987571 | 3 Keeper talking clips (all refused, E98) | 1,096 s | 365 s |

So a scene generation holds the runner ~4.8 min and a talking one ~6.1 min (lipsync_check included). Each is a
submit, then a poll every 15 s (`episode_build.POLL_S`) until Pavo finishes: >95 % of that time the runner waits.

**One long with today's sequential polling** (the draft: 146 scenes, 7 God voice-overs, 20 talking, 7 windows):
153 x 288 s + 20 x 366 s = **856 min** of generation, ~1,030 min with the measured regeneration rates (7 % of scenes;
talking clips assumed 2 generations each), over the 300-min job limit (4 runs at least). Then the frozen QA's
picture: Pavo is 1280x720 and the QA wants 2560x1440 through Real-ESRGAN, never a plain resize; on a runner that is
543 s for a 6 s clip (`pavo_footage.py`), so the draft's 1,053 clip-seconds cost **~1,590 min** of CPU upscaling
(~1,310 min if only the shown 870 s were upscaled). Voice ~2 min, compose and QA ~30 min.
**Total ~2,650 runner-minutes for one long**, ~11 days of the 233/day target (2,346 used in the last 24 h).

**Options.**
- *Reuse the arc's Short clips.* Honestly little: Shorts 1-5 are vidIQ veo-3.1-lite and stock clips (no approved
  character in any of them; the character sheets were approved on 25/10), Short 6 is Pavo landscapes, and every
  Short clip is 9:16 (720x1280). A 16:9 band of a 9:16 clip is 720x405: that is as many pixels as the 640x360
  `pavo_footage.py` already feeds Real-ESRGAN, so the picture quality would hold, but the band keeps 32 % of the
  frame: only wide skies, storms, tents and crowds survive (~10-15 of genesis-07's 30 clips, after Claude's frame
  check); no talking clip (its lips are bound to the Short's line, and the face falls outside the band). Saves
  ~5-8 % of the generations.
- *Fewer, longer clips with windows.* An 8-12 s clip shown as two non-adjacent windows (intercut, recap). The draft
  uses 7; the ceiling is ~30 % fewer generations, since a QA hold is 4-7 s and windows must not sit side by side.
- *No polling waste (submit and leave).* Submit every shot of a chapter (risk order, E99) and end the job; a later
  short run collects what Pavo finished (clip_check, lipsync_check, regenerations) and submits the next. Runner time
  drops to the work itself: ~173 x ~0.5 min ≈ 90 min plus a few 3-min collect runs, instead of ~1,030.

**Recommendation: submit and leave, with new 16:9 clips** (plus windows where the edit wants them, and the few
genesis-07 wide shots that survive a 16:9 band). It removes ~90 % of the generation minutes and needs no gate
change. Before it is built: one direct 0-credit Pavo test of (a) two submissions at once (is Pavo concurrent or a
queue?) and (b) a 16:9 request (`aspect_ratio` is passed through but has never been asked for). The upscaling
(~1,300-1,600 min) is the frozen QA's rule, not a polling cost: it is an owner question (section 4). Note: the
Actions API reports this repository as **public**; GitHub does not bill standard hosted-runner minutes on public
repositories, so check the bill before `minutes.py`'s 7,000-minute paid budget is taken as the constraint.

## 3. Audio

- **The Keeper** narrates in `am_michael` (the voice the QA pins: `qa_pilot.voice_model_pinned` reads the manifest's
  narrator voice) and is on screen only for the promise, the insight and the close, lip-synced (E95 binding, E98
  pose). Every talking line in a long is 11-14 words: a QA hold is at most 7 s, so the line at the slowest Kokoro pace
  (2.25 words/s) plus the 0.35 s gap must fit 7 s (HOLD_OVER_QA), and at the normal pace it must fill 4 s.
- **Characters** speak in their own Kokoro voices from the same pinned model (`voices-v1.0.bin`, sha256
  bca610b8...): Adam am_fenrir, Eve af_heart, Noah bm_george, the scoffer am_puck; God am_onyx at 0.9, voice-over
  only. The QA pins the model hash and the narrator voice, so no gate changes; the render manifest must list every
  speaker's voice (slice 2). **The serpent cannot be a talking shot:** lipsync_check finds a human face and lips, a
  snake has neither, so every serpent clip would fail FACE_NOT_FOUND. The draft keeps it silent and the Keeper
  narrates its KJV words; a creature voice-over mode is a later design item.
- **Music**: the owned track (`OWNED_MUSIC_SHA256`), ducked under the voice. **Loudness**: story QA wants -16 to -14
  LUFS integrated and a true peak <= -1 dBTP; the Shorts engine normalises to -14 LUFS / -1.5 dBTP, at the top edge of
  the long's band. The long's mix targets -15 LUFS / -1.5 dBTP.
- **Speech rows**: first word <= 1.5 s (the cold open speaks at 0 s), "you" within 8 s (Eve's line, 0.7 s), WER
  <= 0.1, speech presence >= 0.85 (estimate 0.95), 115-165 words a minute: the draft estimates 156.7 at 2.75 words/s,
  but Kokoro measured up to 2.98 words/s on Genesis 6 (~170 wpm): the measured voice decides, and if it runs fast the
  fix is longer pauses at chapter ends, never a faster cut.

**Which frozen QA applies.** The only frozen criteria for a Bible-story long were `qa_criteria_story_v1.json`
(2026-10-25). Owner, 2026-10-26, "Nova régua, sem legenda": `qa_criteria_story_v2.json`, frozen here, is v1 with the
burned-caption rows replaced by an uploaded .srt track held to the same numbers (a test asserts v1 is unchanged and
v2 differs only in those rows). **v2 is still not enough for this design**: it keeps v1's no figure on screen
(`figure_present_fraction_max` 0.0), at least 40 % real licensed footage, at most 55 % AI video, and a 4-7 s title
card as the first hold. An acted long with the Keeper on screen meets none of them (the draft: 81 % of the picture
shows people, 100 % Pavo). So **one more frozen version, decided by the owner, is needed before the first render**
of this long; this design does not write it. The plan check shows those rows as pending (QA_CONFLICT_*) so no build
starts on them. Also pending for the render: `qa_pilot.py`, `render_queue.py` and `prepublish_gate.py` know only
v1's hash and grammar (publishing code, not touched here).

## 4. Conflicts with a gate (not resolved here, no gate loosened)

1. **Acted characters and the Keeper on screen vs the story QA**: figures 0.0, real footage >= 40 %, AI <= 55 %
   (v1 and v2). Every acted long fails these rows. Owner decision: a new frozen QA version.
2. **The cold open, acted and spoken at 0 s, vs the QA's 4-7 s title card** as the first hold.
3. **Genesis 1-7 in one long vs arcs.json and the structure**: arc-01 is Genesis 1-3 (Shorts 1-4, long "Creation,
   Eden and the Fall"), arc-02 Genesis 4-6 (Shorts 5-8). A 1-7 long covers two arcs, would repeat arc-02's long, and
   strains "one complete story" (one weak contrast sprawled several stories). The check reports ARC_SHORTS; the owner
   sets the arc, and arcs.json changes by PR.
4. **Cutting**: the QA's 4-7 s holds vs the Shorts' 2-4 s; the long cuts slower, and its talking lines are 11-14 words.
5. **Upscaling**: the QA's 1440p Real-ESRGAN costs ~1,300-1,600 runner-minutes a long against the 233/day target.
6. **The render path**: `still_render`/`pilot_render` (the long's render) has no talking or lip-sync path; only
   `episode_build` (the Shorts') does. The long's build is episode_build's path at 16:9 (slice 3).
7. **The cast**: Cain, Abel and Enoch have no characters.json entry, so they are anonymous figures from behind; for
   9.5 they likely need entries and reference sheets (cf-images, free allocation). Noah and the scoffer are DRAFT.

## 5. The arc-1 draft (`plans/arc-01-long.json`)

Genesis 1:1-6:10, seven chapters = Shorts genesis-01 to genesis-07, with their titles. Estimate: **14.5 min (870.5
s)**, 2,274 words, 157 words a minute, climax at 0.83 (God's Genesis 6:7, then the acted terror around the
scoffer), 11 re-hooks (largest gap 108 s), Keeper 7.8 % (promise 16 s, insight 85 s with recap windows, close 11 s),
180 holds, 173 Pavo generations (146 scenes, 7 God voice-overs, 20 talking: 13 Keeper, 3 Eve, 3 Adam, 1 scoffer) and
7 windows. Cast: Adam, Eve, the serpent (APPROVED, silent), the Keeper, God (voice), Noah and the scoffer (DRAFT:
pending rows). It passes `long_plan_check.py` with no problem; its pending rows are the two DRAFT characters, the
arc scope, and the four QA conflicts. The estimate is near both edges (14.5 of 14-18 min, climax 0.83 of
0.6-0.85): measure the voice locally (`pilot_render.py voice`) before any build, as for Genesis 7 (174.3 s
estimated, 173.8 s measured).

## 6. Slices
1. (this PR) the grammar and its check, story QA v2 frozen, the draft plan.
2. The owner's decisions (QA version, arc scope, upscaling); Noah and the scoffer approved; a 0-credit Pavo test of
   concurrency and 16:9.
3. episode_build for a long: 16:9, submit and leave, per-chapter collect runs, the .srt track, -15 LUFS, the manifest
   the QA reads; qa_pilot/render_queue/prepublish_gate learn the new frozen version.
