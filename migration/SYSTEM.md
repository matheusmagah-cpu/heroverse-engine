# HeroVerse: one delivery workflow (owner alignment, 2026-10-22)

**Mine → model and produce → review originality, intention and quality → publish → mine again.**
Live intelligence follows the entire process and the market, using the results to improve the next cycle.

## Deliveries between stages

| Stage | Receives | Delivers | Next stage accepts when |
|---|---|---|---|
| **1. Mining** | Channel direction, current market and available results from our videos | A versioned structure: winners and weak contrasts, audiovisual evidence, measured attributes, production targets and publication pattern | The evidence supports the targets and the structure meets the validation rule below. A candidate is explicitly limited to a pilot. |
| **2. Modeling and production** | The accepted structure and its evidence | An original script and direction, sourced assets, the finished master, technical checks and proposed publication package | Required inputs are complete, technical checks pass and the exact files are identified. The material is ready for editorial review. |
| **3. Originality, intention and critique** | The exact master, script, sources, technical results and package | An approval bound to the file, or a specific rejection with evidence and the correction required | Originality, editorial intention, policy, frozen technical gates and designated audiovisual review all pass, including the owner's overall floor of 9.5. |
| **4. Publication** | The approved file and its qualified package | The YouTube identity, verified publication state, completed package and results available for learning | Readback confirms the intended publication and package. Upload alone does not complete this delivery. |

### Handoff rules

- The receiving stage validates the delivery before starting. An issue closed, PR merged or workflow green is not acceptance of a video.
- Use the existing structure, pilot and Short records, gates, ledger and receipts listed in `OPERATIONS.md`. Carry the content ID, structure/criteria version, exact media hash, evidence and next action through those records; do not create a second ledger or parallel status document.
- Return a rejected delivery to the stage responsible for its cause, with the failed criterion, evidence and required correction. An unsupported target returns to mining; a script, image, voice or edit defect returns to production; unavailable review remains with review; an upload or package defect remains with publication.
- Preserve valid work. Reuse approved evidence only while its file, inputs, criteria and validity still match. A changed master needs its own review. A provider outage does not require an unchanged master to be rendered or technically qualified again.
- Retry transient errors only within the recorded attempt/time/quota budget. After exhaustion, record the blocker and the concrete condition for resuming. Missing evidence, an expired slot or an unavailable reviewer never becomes approval.
- Work on the current blocking delivery until it is accepted or its external blocker is explicit. Track the next action in the existing work item. A completed correction must name the delivery it unblocked; no new stage or service is added just to move the problem elsewhere.

This is the operating contract. `OPERATIONS.md` maps the existing implementation and its remaining gaps; this document does not certify end-to-end autonomy. In the former v2 numbering, Shorts were stage 4, publication stage 5 and intelligence stage 6. Shorts now use production and review below; intelligence runs across all four stages. Historical records keep their original numbering.

## Product and quality

The goal is a channel that keeps finding the **structures that win right now** and produces original
videos that meet the full delivery contract. The unit of mining is the **structure**, never a channel. A structure is the complete,
repeatable shape of a video:
- format and length;
- the sequence of beats and their timing;
- the opening;
- the voice;
- the visual and cinematic grammar;
- on-screen text;
- calls to action;
- title and thumbnail.

The format may change whenever mining proves a better structure **in the same line** (the English KJV Bible
series, story by story, `production/bible/SERIES.md`; prayer longs stopped by the owner on 2026-10-26) that does not
conflict with the channel. No format is frozen.

Every stage, **from the channel configuration to the pinned comment**, is held to the same bar:
- **ultra-professional and measured;**
- **better than the market's current best.** For every measurable attribute, our target is the **best** value among the validated winners, never their median (`strategy/BEAT_THE_REFERENCE_RULE.md`). Where we can measure quality ourselves (sync, loudness, sharpness, caption accuracy, policy), our bar is stricter than any winner shows.

## Tools (only these)

| Tool | Used for | Limits |
|---|---|---|
| vidIQ (MCP, authorized research agent) | Mining and live intelligence: outliers, watched audits, transcripts, stats, our public videos and analytics; generation (voice, stock search, compose) only as the second choice after Pavo | Research ≤10 calls/day and ≤2,000 credits/cycle; generation ≤200 credits/day; write tools denied; every spend in `evidence/vidiq/ledger.json` (`strategy/VIDIQ.md`) |
| Claude, designated reviewer (long videos since 2026-10-24; Bible Shorts' clips and frame sheets, E114) | Stage 3: review of the inspection sheets, transcript, thumbnail and QA audio measures, bound to the render hash (`ops/CLAUDE_REVIEW.md`) | `gemini-3.8-flash` was replaced (intermittent on the free tier, E58); free Gemini candidates failed calibration |
| Pavo (`heroverse-pavo` MCP and Actions; Agnes Flash video, agnes-image stills) | Stage 2: the first source of AI video and of scene stills and thumbnails (DECISIONS 2026-10-25) | Only at a fresh exact zero-credit quote; one shared free budget for MCP and Actions (`integrations/pavo/quota.py`, E124, E128) |
| Kokoro voice, FLUX images (Cloudflare), licensed footage, ffmpeg | Stage 2 execution (FLUX and footage are the R3 fallback) | Preserve existing hashes; verify capacity under the zero-additional-cost rule |
| YouTube Data API | Stage 4 publication and reconciliation | Our OAuth |
| Buffer, free plan | Mirror Shorts already public on YouTube to TikTok (`tiktok.yml`) | Never a paid plan, never a first publication (owner exception, 2026-10-25) |
| GitHub Actions and the authorized execution agent | Execute the existing production, review and publication entry points | Public repositories; account, executor and dispatch boundaries are in `OPERATIONS.md`; media passes the same gates |

Nothing else is added unless a stage cannot meet its bar without it, and that is proven first.

**Format feasibility rule (owner, 2026-10-20).** A winning structure is not rejected merely because the current renderer cannot make it. Record the required capability and qualify an actual media delivery through the same gates before adopting that production route. A prompt, task assignment or provider claim is not proof that the required format can be produced within the zero-additional-cost limit.

## Channel configuration (setup, then maintained by live intelligence)

The channel is configured as a top KJV Bible-story channel (SERIES.md; formerly prayer), and **every setting that can influence reach or trust is decided from evidence**, never left at its default. Evidence comes from two sources:
- **the official YouTube Help pages**, with source and verification date;
- **what the validated winners' channels do**, measured with vidIQ.

| Setting | Set by | Rule |
|---|---|---|
| Name, handle, profile picture, banner (sizes per Help) | owner in Studio (the handle cannot be set by the API) | Evidence-based spec in `structures/channel.json` |
| Channel description and keywords; country, default language; trailer for non-subscribers | API (`channels.update` brandingSettings) | From the winners' channels and Help, with no keyword stuffing |
| Home sections and playlists, one per active structure | API (`channelSections`, `playlists`) | Every video goes into its structure's playlist |
| Upload defaults: category, language, licence, comments, description template | Studio, plus the per-video API fields | Category = the most frequent among the validated winners (measured, not assumed) |
| Altered/synthetic disclosure | per video (`containsSyntheticMedia`, already on) | Help: realistic synthetic voice narration requires disclosure |

`structures/channel.json` records each setting's value, its source, and when it was last verified. Live intelligence re-verifies it weekly.

## 1. Mine winning structures

1. **Find.** `vidiq_outliers` (long and short, last 3 months, minimum views) for every format in our line, plus
   `vidiq_youtube_search` and `vidiq_similar_videos` around each candidate.
   - **Winners:** breakout score ≥ 50.
   - **Weak contrasts:** videos of the same shape whose views are at or below their channel's norm.
2. **Group by structure.** Group by shape, not by channel: length band, beat sequence, visual grammar.
3. **Audit every video in the group** with the same prompt (`AUDIT_PROMPT`, in `production/long_review.py` after #178):
   - `vidiq_video_watch` for long videos, `vidiq_watch_shortform_content` for Shorts;
   - `vidiq_video_transcript` for exact pace, word counts and the beat text. Only the counts are stored, never third-party text.
4. **Measure every attribute** into the structure record (`structures/<id>.json`). Each attribute is labelled:
   - **driver**: in ≥ 70 % of winners and ≤ 30 % of weak contrasts;
   - **hygiene**: in ≥ 70 % of both;
   - **anti**: in ≥ 50 % of weak contrasts and ≤ 20 % of winners;
   - **free**: varies. Free attributes are where our videos vary, which the authenticity rules need.
5. **Validation (no channel lock).** A structure is `validated` only with:
   - ≥ 6 winners from ≥ 4 distinct channels;
   - no channel providing more than a third of the winners;
   - ≥ 3 weak contrasts;
   - every driver confirmed by a measured count (an estimate does not count; a model's estimate is refuted by a count, as with the 2026-10-19 pace).

   Until then it is a `candidate` and can only be piloted, never scaled.
6. **Conflict check** before a new structure enters production:
   - same language and faith line;
   - same audience (`vidiq_similar_channels` overlap);
   - no policy risk;
   - it does not make the channel incoherent.

The delivery includes how each target was obtained: source, time window, instrument, count and limitations. Metadata or a transcript alone does not prove access to the reference's image and audio. Model estimates remain labelled as estimates; unqualified instruments cannot supply production targets. Missing evidence returns to mining before modeling begins.

## 2. Model and produce

A validated structure becomes three things:
- **The script.** Every driver and hygiene beat, our own words, KJV Scripture only. `script_check.py` holds the structure's rules.
- **The execution spec.** Render parameters per structure: scene length, motion, caption style, cards, CTA timing, sound, Shorts windows.
- **The QA criteria for that structure version**, frozen before its first render. They are deterministic, every row blocks, and nothing is loosened after results.

The direction specifies the viewer's need, the original idea and the intended progression: what the opening promises, what each beat adds and how the ending resolves it. Voice delivery, pauses, pictures, motion, captions and music must serve that progression. Resolve known script, source and feasibility problems before rendering.

Produce the master and package, retain provenance, and deliver the frozen technical QA and signal scan with the file identity. Stage 3 judges the actual result through the designated audiovisual review and comparison with the mined references; a production task cannot approve its own output by declaring it complete.

### No rework (owner, 2026-10-26: "these repetitions are horrible for the project"; E99)

- A plan is checked against its validated structure (`plan_check.py --strict`) before any build. `plan_check` also runs the build's own functions on its estimate (`episode_build.predict`, `reference_problems`: "BUILD ..."), so a refusal the plan already holds is never met in the build (E106).
- **Every build is preceded by a preflight** (E106): `episode_build.py preflight <plan> --voice <Kokoro python> <prepared work> --refs --write`, locally, with 0 Actions minutes and 0 credits: plan_check --strict, each character's status and next step, cf-images used today against the free allocation, the pinned Kokoro voice and `episode_build lines` on it (retime, talking lines, shares, measured length), the compose on that layout, the reference images and every Pavo request through the adapter's own checks, and each talking line against `evidence/pavo/setups.json`. Its report `evidence/preflight/<episode>.json` goes in by PR; `episode.yml` stops in its first step unless that report is PASS for the exact plan and `characters.json` (`verify-preflight`), and hookify blocks a dispatch not chained to `verify-preflight`.
- Every talking line (its words, with its speaker, reference and prompt binding) is first tested with direct 0-credit Pavo calls and `lipsync_check.py`, with the pass rate recorded in `evidence/pavo/` and its entry in `evidence/pavo/setups.json` (generations, passes, evidence file). The rate belongs to the line, not to the setup (#419: line-01 7 of 14, genesis-07's Keeper lines 1 of 33 with everything else equal), so a probe on one line never vouches for another. The preflight refuses a talking shot whose line has fewer than 6 recorded generations (PROBE_REQUIRED) or whose chance of passing within its 6 attempts is under 0.9 (PROBE_RATE_LOW). Only then is a build dispatched.
- Every refusal a later stage can raise is classified in `ops/refusal_registry.json` (A predicted early by the same function, B a hole with its open reason, C knowable only after a generation with its cheapest probe, D external with its resume path, I invariant, N not a refusal); `ops/test_refusal_parity.py` fails a PR that adds a later-stage refusal without saying how the early stage predicts it, or why it cannot.
- A voice-over Keeper shot (plan B, #423) needs no talking probe; its exact prompt and talking frame need still-mouth probes in `evidence/pavo/setups.json` (`lipsync_check --still-mouth`, at least 2 generations, read by the rule of succession), and `episode.yml` checks the still-mouth tool on a passing and a talking clip before any generation.
- **Production comes out at 9.5; the review only confirms** (owner, 2026-10-26: "never produce loosely and fix it later"). `ops/refusal_registry.json` `review` maps every rubric item of `ops/CLAUDE_REVIEW.md` (Short and long), every "Built for 9.5" item of PROMPT_GUIDE and every row of story QA v3 to the earlier check that guarantees it (plan, preflight, build gate, render QA), or states it `open` or `review_only` with its reason and the `residual` the review still has to see; `ops/test_refusal_parity.py` fails when one has no mapping. A rubric item that can become a plan rule becomes one (visual variety: `PROMPT_REPEATED`).
  Owner clarification 2026-10-30: apply these dimensions to the actual source and its contextual construction sample
  before a complete render for final review, including free/imported edits. Bind observed content to the source hash
  and real timeline; resolve demonstrated construction defects there. The procedure in `production/bible/PROMPT_GUIDE.md`
  adds no automatic score or source approval; final audiovisual review and all existing publication gates remain required.
- Every scene prompt states its story's period word for word, the setting and the exclusions (`plan_check`
  PERIOD_SETTING / PERIOD_EXCLUDE, SCENE_PERIOD_MISSING, SCENE_PERIOD_CONFLICT, PERIOD_INVALID, PERIOD_AMBIGUOUS; the
  plan's `period` or its passage; the Short and the long, `plan_period_problems`),
  and a rewritten scene prompt is probed with `shot-probe.yml` and a frame sheet before the build (E108, E114:
  genesis-07 run 40341856955 showed a European street, a glass lantern and church towers in 8 of 30 scene shots).
- A prop seen in many shots (the ark) holds its look the way a character does: its sentences word for word (E113)
  and its approved reference images (`production/characters/props.json`, `props.py`; E122: genesis-09's 64 stills
  carried the sentences and still drew a tower, a barn or a bow). A still whose prompt names the prop is made with
  every approved reference of it, recorded by sha256 with Pavo's read-back (STILL_PROP_UNREFERENCED in scene_stills
  and plan_check); from part 9 a scene shot that names it starts from such a still (PROP_SHOT_WITHOUT_STILL).
  From part 9 the words are positive only (E123: E113's negated sentences primed bows and funnels even with the
  references): the ark is named only by `plan_check.ARK_PHRASE`, no prompt says ark/hull/ship/mast/funnel... (ARK_WORDS),
  and the flood's period sentence names no ark; the phrase is what makes a still need the references.
- An episode record is checked with `episode_build.py check-record <episodes/<id>.json>` (publish_episode's own rules) before `publish-episode.yml` is dispatched.
- `shot-probe.yml` generates the shots that can fail first: talking characters, the Keeper talking, then God's and the Keeper's voice-overs, then wide and establishing scenes, then the rest (`risk_order`, `risk_rank`); `episode_build.py probe-queue PLAN` resumes from the approvals in that order, in batches that fit one run.
- **The long has the same contract** (E127): every kind of plan in `plans/` (the Short's `bible-plan-v2`, the long's `bible-long-plan-v1`) goes through the preflight, `verify-preflight`, `shot-probe.yml` and `approve-shot`. The long's preflight runs long_plan_check `--strict` and the frozen story QA v3, and is BLOCKED while any long review row of `ops/refusal_registry.json` is `open` (LONG_REVIEW_OPEN); `check-probe` refuses its probes without a clean preflight of the exact plan (LONG_PROBE_PREFLIGHT); a `window_of` shot ships its source's approved clip (LONG_DESIGN.md section 7).
- **Every expensive workflow runs `ops/dispatch_guard.py` first** (E116; episode, shot-probe, long-build, cf-images, pilot render and preview, footage, pavo-footage, scene-stills, publish-episode), before any secret: its inputs (and E112's order), capacity (assets in the newest release + the run's uploads <= 1000, the Cloudflare allocation for FLUX runs, YouTube's record limits), one run per episode / pilot / library (a shared job-level concurrency group `heroverse-subject-<subject>`), no new dispatch on a subject whose last run of that workflow failed unless main has a commit since that touches what the run depends on (or `evidence/dispatch/retries.json` records an external cause), and the imports of every script it calls in the job's environment. `ops/test_dispatch_guard.py` fails a new `workflow_dispatch` workflow that is neither guarded nor exempted with its reason.
- An error's antidote covers its class, not the instance (E115): an `ERRORS.json` entry names its `class`, the earlier entries of that class (`prior`) and the class its antidote covers (`test_errors_register`); only `heartbeat.yml` may rely on cron (`test_schedules`).
- A failed build is never dispatched again without new evidence and a fix merged. A resume (`resume_run`) keeps every clip already made.
- **The clip Claude reviewed is the clip the build ships** (E114, owner 27/10: "no rework, ever"; genesis-07 took 8 builds, genesis-08 had 7 of 29 shots rejected after a full build because the probe vouched for a wording and the build made a new clip). Every shot is first generated by `shot-probe.yml` (plan, shot ids, attempts) with the build's own request and checks; its clips go to the release under content-hash names, its frame sheets and record (request and clip sha256, checks) to `claude/shot-probe-<episode>-<run>`. Claude reviews the sheets and approves one clip per shot at >= 9.5 with `episode_build.py approve-shot <record> <shot> <asset> <score> "<note>"` into `production/bible/shots/<episode>.json`, by PR; a clip a build run already made and Claude approved is adopted instead of generated (`shot-probe.yml` with `adopt_run`: its recorded request must equal the plan's now, the checks run again). `verify-preflight` refuses the build until every shot has an approved clip of the request the plan sends now (SHOT_NOT_REVIEWED, SHOT_REQUEST_CHANGED); the build downloads those exact clips, checks them again and generates none, so it only composes and the post-build review confirms the composed video (cuts, captions, audio).
- A rejected clip is replaced only through `shot-probe.yml` and a new approval: the build generates nothing and holds no Pavo secret, and `episode.yml` `regenerate` is refused whatever it names (SHOT_APPROVED_USE_PROBE). `resume_run` still keeps the approved clips already fetched after a compose-level or external failure. The request digest covers only what decides the clip (prompt, clip seconds sent, aspect, references by sha256, speaker, voice and spoken words), never a measured length, so the local preflight and the runners agree. No prompt is edited only to force a new clip.
- An engine PR is reviewed before merge, not after.
- Actions minutes cost nothing: the engine repository is public, and standard GitHub-hosted runners are free for public repositories (owner, 2026-10-26: it stays public; E102). The daily report (`ops/minutes.py`) lists minutes per workflow as a speed and wall-clock measure only. A repeated build is still the first thing to cut, because it delays the work.

### Token budget (owner, 2026-10-26: "never run out of tokens; manage them intelligently")

The biggest cost is context re-read on every turn, not output. Rules for every session:
- **One orchestrator, kept small.** When the main session's context passes ~400k tokens (get_session `context_usage.used_tokens`), it writes a handoff (`evidence/handoff/<date>-<n>.md`: in-flight PRs, agents, tasks, decisions) and a fresh orchestrator session continues from it. Triggers are re-pointed to the new session id. On its first turn the new orchestrator archives every earlier HeroVerse session (list_sessions `mine`, then archive_session on each one that is not archived, itself excluded), so only one session is live (owner, 2026-10-27: "sempre que iniciar nova sessão, arquive as outras").
- **Model by task.** Mechanical checks (light clock, sweeps of small diffs, CI reading) on Haiku; reviews, fixes and plans on Sonnet when the work is routine; Opus only for design, diagnosis and the 9.5 review. Never more than 3 agents at once, and never two on the same subject.
- **Briefs closed.** Every agent gets a bounded brief (files, limits, generation cap, stop rule) and reports once; follow-ups go to the same agent, never a new one.
- **One review pass** (code-review low) per PR, plus a security sweep only when workflows, secrets or `migration/publish/` change. Fixes from review go back to the same author in one message.
- **No polling.** Unsubscribe from a PR at merge; one self check-in per waiting item; the light clock pings the orchestrator only on failures.
- **One clock per job** (single-clock design, slim audit 2026-10-28; table in `OPERATIONS.md` "Clocks"). `heartbeat.yml`
  is the only GitHub cron of record (`tiktok.yml` keeps its own cron only as a second chance, E90; `test_schedules`).
  The light clock (Claude, Haiku, :14 hourly) is the only watchdog: heartbeat older than 55 min (re-dispatch it),
  failed runs, missed slots, TikTok ledger states; it never dispatches `tiktok.yml`. The main clock (every 4 h at :29)
  does production (long and Shorts pipeline, reviews, PRs) and the comment replies (below), and re-checks neither the
  heartbeat nor the TikTok mirror. The daily pass at 08:05 UTC does the report, the decision and the live
  intelligence (below).
- **No rework** (section above): a probe or preflight before any build, so a failure costs one cheap call, not a build plus its review.
- **Rate limit.** Before a fan-out, read `rate_limit_info`; when the five-hour window is close to its limit, defer non-urgent work to after `resetsAt`.

### Shorts are a production delivery, with their own review

A Bible Short is its own episode (`episode.yml` → `publish-episode.yml`), built from its own plan, linked to its arc's long (`arc-links.yml`). Deliver each Short through stages 2 and 3 with its own hash, technical checks and audiovisual approval. The long video's approval does not approve a Short. An existing preserved Short resumes at its missing check rather than restarting production. The prayer Shorts-from-long line (`shorts.yml`, `shorts-review.yml`, `publish-shorts.yml`, `shorts_prerequisite.py`) is retired (slim audit 2026-10-28).

## 3. Originality, intention and critique

YouTube policy (Help Center, YPP monetization policies):
- **Inauthentic content** (renamed 2025-07-15) is mass-produced or repetitive content: made from a template with little to no variation across videos, or easily replicable at scale. It applies to the **whole channel**. "Image slideshows or scrolling text with little narrative or commentary value" is an official example.
- **Reused content** is other people's content without significant original commentary, modification, or educational or entertainment value.

Every video passes all of these, or it is not published:
- **Original text.** The script's 8-word shingles overlap < 5 % with every reference transcript mined. Only shingle hashes are stored, never the text.
- **No template.** Against our last 10 videos: a different opening line, a different Scripture set, a different image set, and a title that differs in more than its keywords. Script shingle overlap < 15 % with any of them. Free attributes vary.
- **Narrative value.** ≥ 35 % of the spoken words are original reflection or teaching, not Scripture quotation or set formulas. The structure gives it a story or a teaching arc, so it is never a slideshow with narration.
- **Intention.** Check the result against the direction: the title/opening promise is fulfilled; each beat adds meaning; voice, image, movement and music support the message; the ending resolves it. Motion or decorative effects alone do not establish cinematic quality. Findings identify the affected passage or time and the correction needed, using the existing editorial rubric rather than inventing a substitute score.
- **Critique.** A support-model pass reads the script and the audit against the two policies above and against our content rules:
  - no fear-bait;
  - no fabricated prophecy;
  - no health or wealth promise;
  - no borrowed identity.

  Any finding blocks until it is fixed.
- **Disclosure.** Realistic synthetic people or events are disclosed as altered or synthetic content; scenery-only videos say so in the record.

The receiving reviewer validates the existing technical evidence and its binding, then evaluates the complete audiovisual file. Base review requires every item ≥ 7 and overall ≥ 8; **new uploads additionally require overall ≥ 9.5** (owner, 2026-10-23), under `publish/owner_quality_policy.py`. The designated reviewer of long videos is Claude (`ops/CLAUDE_REVIEW.md`). No fallback, manual score, provider error or approval for another file satisfies this handoff.

## 4. Publish the complete package

The long video is published by `approve.yml` → `prepublish_gate.py` → `publish.yml`, and each Bible Short by `publish-episode.yml`. Every hard row blocks. Only a file with valid approval and a qualified package can enter upload; a transient ERROR uses bounded recovery and never passes by default.

**The publication package is part of the structure** and is mined like the video itself: the winners' titles, thumbnails, descriptions, hashtags, tags, chapters, first and pinned comments, end screens, publish hour and playlist use.

Each video ships the full package, and `preflight.py` checks every measurable item:
- **title**: the structure's measured pattern; ≤ 100 characters (Help); the promise matches the first 30 s;
- **thumbnail**: 1280×720, under the Help size limit; the structure's measured pattern (#173 item 5); a clear subject and readable text at small size;
  for the Bible series (owner, 27/10) it is the story character (APPROVED, made with its reference images), a close-up face with a clear emotion and our own text of at most 4 words, no Keeper face; a candidate reviewed with the episode's stills BEFORE publish (`production/bible/thumbs.py`), and publish uploads only the approved image (THUMB_NOT_APPROVED in check-record and the long's preflight);
- **description**:
  - the promise in its first lines;
  - **chapters** (Help rules: start at 0:00, at least 3, each ≥ 10 s);
  - the Scripture references;
  - one call to action;
  - **≤ 3 hashtags**, which show above the title;
  - ≤ 5,000 characters;
- **tags**: ≤ 500 characters, taken from vidIQ keyword research, never stuffed;
- **captions**: our exact narration SRT (already sent), never auto-captions;
- **first comment**: posted by the channel through the API (`commentThreads.insert`), with the structure's measured CTA. **Pinning it is manual**: the API cannot pin, so the owner pins it, or it is listed for the owner on publication day;
- **end screen and cards**: the API cannot set them. They come from the channel's default end-screen template, set once in Studio by the owner, pointing to the structure's playlist and to subscribe;
- **playlist**: the structure's playlist;
- **publish hour**: the structure's measured best window for the audience;
- **disclosure**: on.

Every item and its source are written into the package. An item without evidence is marked `UNMEASURED` and listed for stage 1. It is never guessed.

After upload, reconcile the existing video ID and the intended visibility/schedule, captions, playlist, disclosure and remaining package items. Record items that require Studio as pending until verified. An incomplete comment, end screen or readback does not justify another upload. An expired slot remains unresolved until a valid scheduling decision is recorded; it does not count as a delivered publication.

### Comment replies (owner, 2026-10-28: every comment answered, coherently and automatically)

Every viewer's comment on our YouTube and TikTok videos gets an answer written by Claude (the main clock), in the
series' voice (`production/bible/brand-profile.md` "Voice"): coherent with that video's story and with the comment,
short, reverent, never preachy; an exact KJV verse only when it fits (its `verse` is checked by `kjv_check`). Spam,
hate and provocation get a SKIP with its reason, never an argument. `publish/reply_policy.py` gates every decision on
both platforms (length, no link/mention/hashtag, banned words, verse checked, no reply text used twice). At most 20
replies a day per platform, every action in a ledger so nothing is answered twice.
- **YouTube** (official Data API): `comment-replies.yml` (heartbeat, six slots) posts the decided replies
  (`comments.insert` with `parentId`, at most 4 a run) and queues new comments in `publish/comment_queue.json`; Claude
  writes `publish/comment_replies.json` by PR; ledger `publish/comment_replies_ledger.json`. The API cannot like a
  comment, so nothing tries.
- **TikTok** (no API for this; TikTok refuses datacenter IPs): `integrations/tiktok-local/` runs on the owner's PC
  through Desktop Commander, in its own Chrome profile logged in once by the owner; it lists comments, likes and
  answers each one Claude decided, paced like a person (45-240 s between comments, 3 a run). Stories are not posted:
  TikTok's web upload has no Story option.

## Live intelligence: observe every stage and feed the next mining cycle

- **The process.** Follow the existing deliveries from reference to publication: evidence quality, rejection reasons, rework, waiting time, provider failures, recurring free capacity and approved stock. Correct a proven defect at the stage that caused it. Keep one concrete next action for the current blocker, with evidence and an acceptance condition.
- **Our videos.** At 48 h and at 7 days after publication: `vidiq_video_watch` on our public video with `AUDIT_PROMPT`, plus real analytics (views, retention, CTR, subscribers). Compare with an appropriate baseline at the same publication age. Catalogue **good**, **bad** or **neutral** only when the evidence permits; insufficient data remains inconclusive. An observed association is a hypothesis about an attribute, not proof of cause.
- **The market.** Every day, within the vidIQ limits: new outliers, then new or changed structures, then the catalogue (`structures/`). Structures move:
  - `candidate` → `validated` → `active`;
  - `active` → `retired` when our own results or the market turn against them.
- **Decisions** follow `strategy/DECISIONS.md` (90 % evidence for strategy). Defects and compliance are always fixed.
- **Return delivery.** Feed mining a specific improvement or opportunity: evidence, affected structure/stage, proposed change and expected measurable result. Evaluate that change in the next cycle. No supported change means keep the current standard; never lower criteria to clear a queue. Market direction stays within the channel's audience and editorial line.

### Daily loop (owner, 2026-10-24: "a inteligência viva precisa começar a trabalhar")

Runs once a day in the daily pass at 08:05 UTC, after goal-report (07:45): report → decision → live intelligence. At most 20 vidIQ credits, every spend in the ledger.

1. **Measure our videos.** `vidiq_channel_analytics` by video (last 14 d) and by traffic source; `vidiq_get_videos_by_ids`
   for anything published in the last 48 h (Analytics lags about 48 h).
2. **Verdict at 48 h and 7 d.** Each video is good, weak/bad or neutral against the series median at the same age;
   under 48 h it stays inconclusive. Record it in `evidence/learning/<YYYYMMDD>.json` (same schema as 20261024).
   The verdicts come from `mining/live_intel.py` (tested): each episode against the series median at a similar age
   (0.75-1.33x), inconclusive under 48 h or 100 views; snapshots accumulate in `evidence/learning/state.json`.
   `publish_episode.py` writes each episode's `video_id` into its record (`publish-episode.yml` commits it), and
   live_intel refuses a published episode (in `publish/ledger.json`) whose record lacks it, never skipping it (E140).
3. **Turn it into one change.** Name the single change the next episodes make (hook, title pattern, length, visual,
   end card, slot), the stage it touches and how it will be measured. Write it into `production/bible/SERIES.md` or
   `PROMPT_GUIDE.md` so production uses it; the next day's run checks whether it worked.
   A change is a hypothesis in `state.json` (one attribute of the episode record's `attributes`, its new value,
   expected effect): KEPT after 2 consecutive good episodes carrying it, REVERTED after 2 bad, otherwise RUNNING; only
   one runs at a time, and the authenticity layer (KJV text, references, reflection, prayer, AI disclosure, own script)
   is never a hypothesis.
4. **Tell the owner only when there is a verdict or a change.** Two lines: what the numbers show, what changes.

Market research can continue within its budget while existing videos mature; it does not need to wait seven days for every upload. Missing 48-hour/7-day evidence remains pending and is incorporated when available. A report generated without usable evidence is not a completed learning cycle.

## 5. Ads: paid promotion measured for real predictability (owner, 2026-10-24)

**ON HOLD (owner, 2026-10-24: "vamos deixar essa etapa para depois, vamos tentar concluir aí")**: no campaign, test or
product work until the owner reopens this stage; the facts and the model stay for when it does.

Facts and sources: `evidence/ads/20261024-research.json`; model: `strategy/ads_model.py` (tested).
- **Paid results never count for YPP.** Watch hours and subscribers from ad campaigns are excluded from the YPP
  thresholds (YouTube Promote help); the counter only moves with organic viewing. Reports keep paid and organic apart.
- **What a budget buys is measured, not assumed.** Each campaign has one video, one budget, one window, and records
  cost per view, cost per subscriber, CTR and retention of the paid audience, and k = organic views caused per paid
  view (organic views of the channel during and 7 days after the campaign minus the series baseline at the same age).
  The model is recalibrated with each measured value; the forecast for a budget is always the model with our own data.
- **Gate.** No campaign runs without the owner's written approval of the budget; campaigns are run from the owner's
  account (YouTube Studio Promote or Google Ads), never by the engine. Only a video already at the 9.5 floor and with an
  organic baseline of at least 48 h is promoted.

## Approval: automatic qualification (owner, 2026-10-19 23:55 UTC)

The system approves or rejects each video; personal first-sample approval is not required. This is the active governance rule. The historical personal-approval wording in the immutable `production/qa_criteria_v3.json` is not an additional active approval step; its technical, speech, rights and grammar requirements remain unchanged, as do its bytes and SHA256. Automated qualification does not establish owner visual inspection or audience success.

A video publishes when it passes **three existing gate dimensions**, each measured against the mining. These are checks within the workflow above, not three additional production stages:
1. **Structure.** It carries the drivers and hygiene of its validated structure and the measured publication package (`publish/three_stage.py` `structure_rows`).
2. **Modeling.** Execution quality: frozen QA v3, the signal scan, and the designated watched review (`prepublish_gate.py`).
3. **Authenticity.** Every rule of stage 3 (`three_stage.py` `authenticity_rows`), plus the support-model critique (`out/critique.json`).

`prepublish_gate.py` blocks on every row. FAIL is final until the defect is fixed. UNKNOWN requires the missing evidence; retrying without changing that condition does not resolve it. Public visibility requires current readback of the existing video, not just an upload receipt or the absence of an unschedule record.
