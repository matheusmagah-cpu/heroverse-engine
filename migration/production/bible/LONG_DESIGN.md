# The Bible-story long, built like the Shorts (design, 2026-10-26)

Owner, 2026-10-26: "Adjust the long videos. They need maximum precision. Apply the mined structure and model it to
our format, without forgetting what we already agreed: the Keeper character narrating, and the Bible characters, who
must be the same whenever they repeat across stories."

This is the design with measured numbers, and slice 1 of the build:
- the long's plan grammar (`bible-long-plan-v1`) and its check (`long_plan_check.py`), with tests in
  `test_long_plan_check.py` that run in pr-checks through `test_plan_check.py`;
- the frozen story QA v2 and v3;
- the arc-1 draft plan (`plans/arc-01-long.json`);
- two direct 0-credit Pavo tests.

Nothing here is built or published, and no Actions run was dispatched. `episode.yml` and the publishing code are
unchanged.

Owner decisions of the same day (DECISIONS.md):
- "Nova régua, sem legenda": story QA v2 drops burned captions.
- "Sim, régua nova": story QA v3, written for the acted long.
- The long follows arcs.json: arc-01 is Genesis 1-3, Shorts 1-4.
- "Manter público": the repository stays public, so Actions minutes cost nothing. The long is built for wall-clock
  time.

## 1. The plan grammar: every beat of the structure, in our format

A long plan is a Short plan (`bible-plan-v2`) laid out over the beat map of `structures/bible-story-long.json`. It
uses the same scene, speaker, God voice-over and Keeper shots, and the same `plan_check` functions check them. Each
shot names its `beat`, and chapter shots name their `chapter`. There is one chapter per Short of the arc, and each
chapter's title is that Short's title.

| Beat (structure) | Our format | Check (code) | Number from |
|---|---|---|---|
| cold_open 0-30 s, acted, never the Keeper | The first shot is a scene whose spoken line starts at 0 s. A character or God speaks the conflict (`conflict: true`). It ends on an open question. Its words end by 30 s, and the build holds its last frame (under the music, at most 3 s) so the Keeper starts at exactly 30 s. | OPEN_NOT_SPOKEN, COLD_OPEN_CONFLICT, KEEPER_IN_COLD_OPEN, COLD_OPEN_LENGTH (> 30 s, on its own), COLD_OPEN_SHORT (more than 3 s of held frame), COLD_OPEN_NO_QUESTION | gate.cold_open_s, keeper_in_cold_open; QA v3 grammar.first_shot |
| keeper_promise 30-50 s | Keeper shots only: lip-synced, facing the lens, static camera (E95, E98). Lines of kind `promise`. | KEEPER_PROMISE_LENGTH, KEEPER_BEAT_SCENE | gate.keeper_promise_max_s (= the beat's at_s span) |
| chapters, one per Short | `chapters` lists arcs.json's Shorts in order. Acted scenes use the arc's approved cast. | ARC_SHORTS, CHAPTER_EMPTY, CHAPTER_ORDER | arcs.json |
| re-hooks >= 6, one at every chapter end | A narration line or spoken line with `rehook: true` | REHOOKS, CHAPTER_END_NO_REHOOK, REHOOK_GAP (<= 240 s apart: the 4-min chapter rule) | gate.rehooks_min, rehook_gap_max_s |
| climax at 0.6-0.85, on the KJV line | Exactly one `climax: true` acted scene with people on screen. A referenced line is spoken in that shot or the shot before it (God's voice-over or the hero). | CLIMAX_COUNT, CLIMAX_POSITION, CLIMAX_NOT_ACTED (E92), CLIMAX_NO_KJV_LINE | gate.climax_at |
| payoff | `payoff` shots after the climax | PAYOFF_MISSING, PAYOFF_BEFORE_CLIMAX | - |
| keeper_insight <= 125 s | Keeper lines of kind `insight` (>= 20 words). Cut-aways are allowed (windows of earlier clips). | KEEPER_INSIGHT_LENGTH, INSIGHT_SHORT | gate.keeper_insight_max_s |
| keeper_close <= 30 s | The Keeper is last, with a comment question and the next story | KEEPER_CLOSE_LENGTH, KEEPER_MUST_CLOSE, CLOSE_NO_QUESTION, CLOSE_NO_NEXT | gate.keeper_close_max_s |
| Keeper <= 25 % | Keeper shots appear only in the three Keeper beats | KEEPER_SHARE, KEEPER_OUT_OF_BEAT | gate.keeper_share_max |
| no slow stretch > 20 s | No run of shots without a person on screen, and no single voice run, longer than 20 s | SLOW_STRETCH, ESTABLISHING_SHARE (<= 15 %) | gate.slow_stretch_max_s |
| one complete story, 14-18 min | The estimate: each line at its voice's measured Kokoro pace (VOICE_PACE), 0.6 s between lines (LONG_LINE_GAP) | LONG_LENGTH | gate.length_min |
| no burned captions | `burned_captions: false`, with the .srt track (QA v2/v3) | BURNED_CAPTIONS | gate.burned_captions |
| 16:9 | `aspect_ratio: "16:9"` (Pavo honours it: section 2) | ASPECT_RATIO | gate.aspect_ratio |

**One source, no copies.** The numbers come from two places:
- The structure's `script.gate` block, read through `script_check.story_gate()`. That is the same reader
  `structure_problems` uses for the long's script (#415). This PR adds to the block only the numbers the beat map
  already states, and a test keeps the gate equal to the beat map.
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

**The frozen QA, checked on the plan.** The check reads story QA v3, with its sha256 pinned:
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

## 2. Footage: how many clips, and how long they take

**Cuts.** A 15-min long cut every 2-4 s (the Shorts' rhythm) would need ~300 holds. The frozen story QA allows 4-7 s
holds, so a 15-min long has 129-225 holds, about 164 at 5.5 s each. The arc-1 draft has 175 holds over 14.5 min,
about 5 s each.

**Pavo time, measured.** The figures come from episode.yml runs on genesis-07-short on 2026-10-26: step times from
the Actions API, shot lists from the run logs and from the `report.json` files on the
`claude/episode-genesis-07-short-*-failed` branches.

| Run | Generations in the Pavo step | Step time | Per generation |
|---|---|---|---|
| 40263488773 | 25 scenes, 2 regenerated after an unknown submission, then PAVO_UNREACHABLE (28 submissions) | 8,062 s | 288 s |
| 40278642295 | 5 scenes + 3 Keeper talking clips | 2,469 s | ~274 s a scene, 366 s a talking clip |
| 40285879529 | 3 Keeper talking clips (all refused, E94/E95) | 1,101 s | 367 s |
| 40297987571 | 3 Keeper talking clips (all refused, E98) | 1,096 s | 365 s |

A scene generation takes about 4.8 min, and a talking one about 6.1 min including lipsync_check. episode_build
submits one, polls every 15 s until Pavo finishes, then submits the next.

**One long, as today's Shorts are built.**
- Generation: the arc-1 draft has 136 scenes, 9 God voice-overs and 20 talking clips, plus 10 windows. In sequence
  that is about 818 min of generation, and about 1,000 min with the measured regeneration rates. That is over the
  300-min job limit, so it would take 4 runs or more.
- Upscaling: Pavo delivers 1280x720, and the QA wants 2560x1440 through Real-ESRGAN, never a plain resize. That is
  543 s for a 6 s clip on one runner, so the draft's 1,008 clip-seconds take about 1,520 CPU-minutes.
- With the repository public (owner), these minutes cost nothing. What matters is the wall-clock time: about 14 h of
  generation plus about 26 h of upscaling, if each runs in sequence.

**Two direct Pavo tests (0 credits, no Actions run).** Full record:
`evidence/pavo/20261026/long-16x9-and-concurrency.json`.
1. **16:9 works.** A 16:9 request returns 1280x720 at 24 fps (6.58 s for 6 s asked), using the full frame, at an
   exact 0-credit quote.
2. **Two submissions in a row ran at the same time.** Both clips were done within 7 min of the first submission. In
   sequence they would take about 9.6 min. The second clip, submitted 11 s later, finished first. How many jobs can
   run at once is not measured yet; the next test is 4 at once.

Test 2's river clip also showed modern houses at the frame edge. Every clip still needs Claude's frame check, and
outdoor prompts need a stated ancient setting.

**Options.**
- **Reuse the arc's Short clips.** This gives little.
  - Shorts 1-4 (arc 1) are vidIQ veo-3.1-lite and stock clips, and none shows an approved character (the character
    sheets were approved on 25/10).
  - Every Short clip is 9:16 (720x1280). A 16:9 band cut from one is 720x405. That is as many pixels as the 640x360
    that `pavo_footage.py` already feeds Real-ESRGAN, so the quality would hold, but only 32 % of the frame survives.
  - Only wide skies and landscapes survive, after a frame check. No talking clip survives: its lips belong to the
    Short's line.
- **Fewer, longer clips with windows.** An 8-12 s clip is shown as two non-adjacent windows (intercut, recap). The
  draft uses 10. The ceiling is about 30 % fewer generations, because QA holds are 4-7 s and windows cannot sit side
  by side.
- **No polling wait (submit and leave).**
  - Submit a chapter's shots, risky ones first (E99), and let the job end.
  - Later short runs collect what Pavo finished (clip_check, lipsync_check, regenerations) and submit the next.
  - With 2 or more Pavo jobs at once (measured), generation for the draft drops from about 14 h to about 7 h or less.

**Recommendation: submit and leave, new 16:9 clips, and a matrix upscale.**
1. Generate new 16:9 clips, submitting each chapter at once (submit and leave).
2. Use windows where the edit wants them.
3. Upscale in a matrix of parallel jobs. GitHub runs up to 20 at once for a free plan: 1,520 CPU-minutes become about
   1.5 h of wall-clock, plus downloads.

The long then needs about a working day of wall-clock time, not several days.

## 3. Audio

- **The Keeper.** He narrates in `am_michael`, the voice the QA pins: `qa_pilot.voice_model_pinned` reads the
  manifest's narrator voice. He is on screen only for the promise, the insight and the close, lip-synced (E95
  binding, E98 pose).
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
- **Characters** speak in their own Kokoro voices from the same pinned model (`voices-v1.0.bin`, sha256
  bca610b8...):
  - Adam am_fenrir;
  - Eve af_heart;
  - God am_onyx at 0.9 speed, voice-over only.

  The QA pins the model hash and the narrator voice, so no gate changes. The render manifest must list every
  speaker's voice (slice 3).
- **The serpent is silent.** lipsync_check finds a human face and lips, and a snake has neither, so a talking
  serpent clip would fail every generation (TALKING_WITHOUT_A_FACE). The Keeper narrates its KJV words.
- **Music.** The owned track (`OWNED_MUSIC_SHA256`), ducked under the voice.
- **Loudness.** The story QA wants -16 to -14 LUFS integrated and a true peak at or below -1 dBTP. The Shorts engine
  normalises to -14 LUFS / -1.5 dBTP, at the top edge of the long's band, so the long's mix targets -15 LUFS /
  -1.5 dBTP.
- **Speech rows.**
  - First word within 1.5 s: the cold open speaks at 0 s.
  - "You" within 8 s: Eve's line, at 0.7 s.
  - WER at or below 0.1.
  - Speech presence at or above 0.85: the estimate is 0.92.
  - Pace 115-165 words a minute. With the Shorts' 0.35 s between lines, the measured arc-1 voice ran 164.5 words a
    minute, at the ceiling. The long breathes 0.6 s between lines (LONG_LINE_GAP), which measured 159.0. pilot_render's
    v4 long widened its sentence gap for the same row. The long's build must use the same gap (slice 3).

**Which frozen QA applies: story QA v3, frozen in this PR** (owner, "Sim, régua nova"). It is v2 with only three
rules replaced by the structure's own:
1. Figures: approved characters on screen are allowed (v2: none).
2. AI share: 100 % Pavo is allowed, provided each clip passes clip_check and every talking clip passes
   lipsync_check (v2: at least 40 % real licensed footage and at most 55 % Pavo).
3. First shot: the acted cold-open conflict replaces the 4-7 s title card.

Everything else is v2's, unchanged: audio, loudness, pace, the 4-7 s holds, the .srt track, the 9.5 floor and the
Claude review. v2 is v1 with the burned captions replaced by an .srt track. v1 and v2 stay frozen and byte-identical,
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
- The render manifest the long's build writes (slice 3) carries, beside v4's fields: `holds[].beat`,
  `holds[].characters`, `holds[].shot_kind`; `sentences[].speaker` on spoken lines; per clip `source`, `licence`,
  `model`, `upscaler`, `audio`, `vetting`, `credit`, `sha256`, `clip_check`, `talking`, `lipsync_check`,
  `voiceover`, `face_check`; `burned_captions: false`; `caption_track`.
- Antidote: `test_qa_pilot.py` fails when a frozen QA a plan check reads is not pinned, with the same hash, by
  prepublish_gate and render_queue and read by qa_pilot.

## 4. What is still open, or not resolved here (no gate loosened)

0. **v3's readers**: done (E126, above). The long's build (slice 3) still has to write the manifest fields and the
   `caption_track` listed there.

1. **Cutting.** The QA's 4-7 s holds replace the Shorts' 2-4 s, so the long cuts slower and its talking lines are
   sized to fit them (section 3). Settled by the frozen QA; noted here because it differs from the Shorts.
2. **The render path.** `still_render` and `pilot_render`, the long's old render, have no talking or lip-sync path;
   only `episode_build` (the Shorts') does. The long's build is episode_build's path at 16:9, with submit and leave
   and a matrix upscale (slice 3).
3. **The cast.** Cain and Abel have no characters.json entry. Arc 2's long will need them (owner: not for now).
4. **Pavo concurrency.** Two jobs at once is measured; the ceiling is not. The next 0-credit test is 4 at once.

## 5. The arc-1 draft (`plans/arc-01-long.json`)

- **Scope.** Genesis 1:1-3:24, four chapters: Shorts genesis-01 to genesis-04 with their titles, as `arcs.json`
  arc-01 lists them, pilot-015. One complete story: how a very good world broke in one afternoon, and the promise
  inside the curse.
- **Cast.** Adam, Eve and the serpent are APPROVED. The serpent is silent and the Keeper narrates its lines. God is a
  voice only. The Keeper appears in his three beats.
- **Check result.** It passes `long_plan_check.py --strict` with no problem and no pending row.
- **Estimate.**
  - 14.52 min (871.1 s), 2,313 words, 159 words a minute.
  - The cold open's words end at 29.8 s, so the Keeper starts at 30 s.
  - The climax is at 0.78: God's Genesis 3:17 line ("cursed is the ground for thy sake"), then Adam on his knees in
    the storm.
  - 8 re-hooks, largest gap 105 s.
  - Keeper share 8.5 %: promise 16 s, insight 92 s with recap windows, close 11 s.
  - 175 holds; 165 Pavo generations (136 scenes, 9 God voice-overs, 20 talking: 14 Keeper, 3 Eve, 3 Adam) plus 10
    windows.
- **Measured voice.** Kokoro, voiced locally line by line in each speaker's voice, laid with the 0.6 s gap:
  - **14.59 min (875.4 s)**, within 0.5 % of the estimate.
  - 158.5 words a minute, climax at 0.78, Keeper 8.6 %.
  - Every talking hold is inside 4-7 s.
  - The cold open's words end at 27.1 s, so its last frame holds 2.9 s before the Keeper at 30 s (the limit is 3 s).
    The estimate puts that end at 29.8 s, and the window is narrow, so the build must re-check it on the measured
    voice (slice 3).

  The first voicing, before the talking lines were lengthened and with the 0.35 s gap, measured 13.97 min and 164.5
  words a minute.
- **The local preflight (27/10, `evidence/preflight/arc-01-long.json`)** compose-predicted the measured voice with the
  long's own cut (#470) and found four plan problems the estimate missed, fixed in the plan without touching a gate:
  - FOOTAGE_SHORT s-c1-both: its 8 s clip had to cover 10.55 s (its own hold and the s-ki-valley window), 1.32x > 1.3:
    it is now a 9 s clip.
  - HOLD_UNDER_QA s-co-adam, s-co-eye, s-co-hide (3.86 s each on lines 0-1): three cuts did not fit those two lines,
    and two lines more would make one 25 s voice run (SLOW_STRETCH). s-co-eye (the serpent's eye) is cut; s-co-adam
    and s-co-hide hold lines 0-1, s-co-gate and s-co-exile lines 2-3.
  - HOLD_UNDER_QA s-c3-turn, s-c3-listen (3.90 s on line 63): the four shots of lines 63 and 64 now share both lines
    (about 4.3 s each).
  - HOLD_OVER_QA g-c4-woman (8.12 s): Kokoro pauses at the semicolon of "I will greatly multiply thy sorrow and thy
    conception; in sorrow thou shalt bring forth children". The first clause alone reads under 4 s at God's fastest
    pace; the line is now "in sorrow thou shalt bring forth children, and thy desire shall be to thy husband" (Genesis
    3:16 word for word, kjv_check PASS, one comma for the semicolon so it is one sentence).
  The draft is now 174 holds, 164 generations (135 scenes); measured 14.54 min (872.6 s), Keeper 7.5 %. Plan, voice
  and every request digest are clean; only the talking-line probes block (`evidence/pavo/20261027/arc-01-long-talk`).

## 6. Slices
1. (This PR.)
   - The grammar and its check.
   - Story QA v2 and v3, frozen.
   - The arc-1 draft, estimated and voiced.
   - The 16:9 and concurrency tests.
2. Before the build:
   - A 0-credit test of 4 Pavo jobs at once.
   - The arc-1 long's still frames (first-frame stills where light or particles are risky).
3. episode_build for a long:
   - 16:9, submit and leave with per-chapter collect runs, and a matrix upscale.
   - The .srt track and -15 LUFS.
   - The manifest the QA reads.
   - qa_pilot, render_queue and prepublish_gate learn v3.

## 7. The no-rework contract of the Shorts, for the long (E127, 2026-10-27)

Owner, 27/10: get the arc-01 long publishable with no rework. The long now goes through the Shorts' own contract
(E106, E114, E99), by the same code (`long_preflight.py` holds only what differs):
- **Preflight before anything is built.** `episode_build.py preflight plans/arc-01-long.json --voice ... --refs --write`
  runs long_plan_check `--strict` and the frozen story QA v3 (`episode_build.check_plan`), the pinned Kokoro voice laid
  out at LONG_LINE_GAP against the structure's gate (length, Keeper share, measured), every request through the
  adapter's offline checks and its digest, and every talking line's direct probe. It is BLOCKED (LONG_REVIEW_OPEN)
  while any story QA v3 row or rubric `long` entry of `ops/refusal_registry.json` is `open`. The report binds the plan,
  the characters' entries (look, references, voice), their image records, the matched probes, the review rows and the
  code by sha256.
- **The build ships approved clips only.** `verify-preflight` (the build's first step) refuses a long without a PASS
  report bound to it, with a review row open now, or with a generated shot that has no approved clip of the request the
  plan sends now. `generate_step` downloads those clips and generates none. A `window_of` shot is never generated:
  it ships its source's clip, so it has no digest, probe or approval of its own.
- **Probes.** `shot-probe.yml` takes the long's plan (long_plan_check, 16:9, its own shot ids, windows refused by the
  dispatch guard and by `check-probe`, PROBE_WINDOW_SHOT). For a long, `check-probe` also refuses a plan without a clean
  committed preflight of these exact bytes (LONG_PROBE_PREFLIGHT); only the open review rows and the talking probes
  may still block that report, since neither changes a request. Claude approves one clip a shot with
  `approve-shot` into `shots/arc-01-long.json`.
- **Risk order and resume.** `risk_rank`: talking characters, the Keeper's talking shots, voice-overs, wide and
  establishing scenes, then the rest. `episode_build.py probe-queue PLAN` lists the shots without an approved clip of
  their request now, in that order, cut into batches of one rank that each fit one shot-probe run.
- **Slice 3 changes accordingly.** "Submit and leave" applies to the probes, not to the build: the build composes
  approved clips (16:9 at LONG_LINE_GAP, the .srt, -15 LUFS, the upscale matrix) and never holds a Pavo secret.

The production estimate (no generation) is `evidence/long/20261027/arc-01-long-production-estimate.json`
(`long_preflight.py estimate PLAN --write`).

## 8. The long's build (slice 3, 2026-10-27)

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
   comes from `captions.track_record` (the writer of #469, `captions.py long`), and `manifest.json` carries the
   fields qa_pilot reads for v3 (section 3). The preflight now predicts this compose too (`compose_problems`).
4. **record**: `bible-<long>-sha256-<sha>.mp4` and `bible-<long>-sha256-<sha>.srt` into the release; the report,
   manifest, .srt and a 16:9 sheet on `claude/long-<long>-<run>` for Claude's review (>= 9.5).

`resume_run` keeps the upscaled clips of an earlier run whose artifact (`long-up-<long>--<shot>-<sha16>`) is of the
clip approved now; a shot approved again since is upscaled again.

The 9 image-first shots get 16:9 stills: `scene_stills.py` prepares, crops, finalizes (1920x1080), sheets and
approves at the plan's aspect, and refuses a picture at another aspect instead of stretching it
(STILL_ASPECT_MISMATCH). Pavo agnes-image at 16:9 quoted 0 credits (`evidence/pavo/20261027/agnes-image-16x9-quote.json`).
