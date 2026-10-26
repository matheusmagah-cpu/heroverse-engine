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
  | The scoffer (am_puck) | 3.55 (evidence/voice/20261026/kokoro-pace.json; 3.425 in the six lines above) |
  | The serpent (bm_fable) | 2.728 (kokoro-pace.json) |

  The table is `voice_pace.py`, shared with the Shorts' plan_check. At a single 2.75 words/s the first arc-1 voicing
  had five talking lines under the 4 s a talking clip fills. Both checks use each voice's measured pace, slowed by
  2.25/2.75 for the slowest case (the Shorts keep 2.75 for the narrator); a talking voice not in the table is refused
  (VOICE_PACE_UNMEASURED).
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

**Build blocker: v3 cannot be measured yet.** v2 and v3 rename keys that the readers index directly:
- `qa_pilot.py` reads `caption_coverage_of_speech_min`, `caption_hold_seconds_median`, `caption_chars_max`,
  `caption_words_max` and `caption_box`; v2 replaced them with the `srt_*` rows.
- It also reads `title_card_seconds`, `footage_picture_share_min` and `ai_video_picture_share_max` (0.55); v3
  replaced them with `first_shot`, `figures_allowed`, `ai_video_picture_share_max` 1.0 and `ai_video_clip_checks`.
- `prepublish_gate.py` knows only `story-qa-criteria-v1`: its hash, its file and its review dimensions.
- `render_queue.py` pins only v1's hash.

A render measured against v3 today would fail with a KeyError, or fall back to the wrong grammar. No long can be
rendered, measured or approved until slice 3 teaches these readers v3's keys. A test (`test_long_plan_check.py`
NoRendererReadsTheNewQaYet) fails any change that points a renderer, gate or workflow at v2 or v3 before
`qa_pilot.py` reads `srt_coverage_of_speech_min`, `figures_allowed` and `first_shot`, and before `prepublish_gate.py`
knows `story-qa-criteria-v3`. This PR does not wire them.

## 4. What is still open, or not resolved here (no gate loosened)

0. **v3's readers** (the build blocker above). Slice 3 has to come first.

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
