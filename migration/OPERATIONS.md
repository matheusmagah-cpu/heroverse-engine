# HeroVerse operations — what runs (revised 2026-10-28)

Owner: Matheus. Channel: HeroVerse `@heroverse74` (`UCuMF6pJQkyMzaVoAxFL86yA`), account Will. Claude Code and ChatGPT/Codex share the
scripts, code and fixes under the coordination protocol below; the GitHub workflows do the heavy work. Credentials live only in repository secrets.

## Rules that never move
- Zero additional cost: no billing, paid service or promotional credit.
- Niche: the KJV Bible series, story by story (`production/bible/SERIES.md`), exact KJV quotations, no fear-bait,
  prophecy or health/wealth promises. Prayer longs are stopped (owner, 2026-10-26: "stop the prayer videos; the channel
  is going in another direction"): `render_queue.story_pilot` keeps every non-story pilot out of images, preview,
  render, review, approval, upload and comment retries.
- Quality: `STANDARD.md` R1–R12, frozen QA (`production/qa_criteria_v3.json`, `qa_criteria_v4.json`), the designated
  watched review by Claude (`ops/CLAUDE_REVIEW.md`; items ≥ 7, overall ≥ 8) and the owner floor overall ≥ 9.5 for every new upload.
  Missing, errored or hash-mismatched evidence blocks; nobody writes approvals by hand.
- Every failure: root cause, fix, an antidote test and an entry in `ops/ERRORS.json`.
- Plan and dates: day 1 = 2026-10-18; the current goal, slots and cadence are the latest entries of
  `strategy/DECISIONS.md` (day 14 is out of reach since 2026-10-26; the arc and its long carry the plan).

## The production line
| Step | Entry point |
|---|---|
| Script | Claude writes `production/pilot-NNN/script.json` (+ `images.json`, `schedule.json`); `production/script_check.py` gates it (R12 hook, length, originality, rights) |
| Footage | `footage.yml` → `production/footage/footage.py` (Pixabay when `PIXABAY_API_KEY` is set, Pexels when `PEXELS_API_KEY` is set, Wikimedia Commons CC0/PD/CC BY), automatic vetting; `footage/assign.py` picks a pilot's clips by mood |
| Pavo footage | `pavo-footage.yml` (input `production/pilot-NNN/pavo(-N).json`: `{id, conversation_id, url, prompt, words}` per clip, Pavo CDN URLs only) → `production/footage/pavo_footage.py`: one clip per job (10 in parallel), audio dropped, every native frame through Real-ESRGAN x4v3 on CPU (640x360 → 2560x1440, then 30 fps), `footage-<id>-sha256-<sha>.mp4` through `ci/assets.sh`, records `library/pavo-*.json` (vetting PENDING) and sheet `library/sheets/pavo-<run>.jpg` committed to main; Claude reviews the sheet and approves in a PR. The long uses them only under the story format's own frozen QA (QA v4 does not list the Pavo licence) |
| Images | `cf-images.yml` (FLUX on the Workers AI free allocation, Real-ESRGAN 4×), `nightly-images.yml`; `images-upres.yml` brings older stills to 4096 px |
| Scene stills (image first) | `scene-stills.yml` (plan, shots, candidates 1-3) → `production/bible/scene_stills.py prepare` (the still prompts in `bible/stills/<id>.json`, scene rules) → `imagegen/cf_images.py` FLUX → centre crop 9:16 → Real-ESRGAN → `bible/stills/candidates/<still>-<run>-<n>.jpg/.json` (sha256, DRAFT) and `bible/stills/sheets/<episode>-<run>.jpg`, pushed to `claude/stills-<episode>-<run>`; Claude reviews and runs `scene_stills.py approve <still> <candidate> --score S --note TEXT` by PR. A shot's `first_frame`/`last_frame` then goes to Pavo as frames_to_video (plan_check.frame_problems; the digest carries the still's sha256) |
| Thumbnails (character first, owner 27/10) | spec `production/bible/thumbs/<episode>.json` (character APPROVED, emotion, close-up, scene, text <= 4 words, period, prompt with the look word for word) → `thumbs.py check` → `thumbs.py refs` (the character's approved references, sha256-verified) → Pavo `agnes-image` after a fresh exact 0-credit quote (16:9 long, 9:16 Short) → `thumbs.py finalize SPEC IMAGE RUN N META` (crop 1280x720 / 1080x1920, our own text, R16, `thumbs/candidates/<episode>-<run>-<n>`) → `thumbs.py sheet` → Claude reviews with the stills → `thumbs.py approve <episode> <candidate> --score S --note TEXT` by PR. `publish_episode.py` (from part 9) and `publish_video.py` (package `series` bible, `thumb_episode`) upload only the approved image; `episode_build.py check-record` and `publish/preflight.py` refuse THUMB_NOT_APPROVED first |
| Render | runner `heroverse-runner/.github/workflows/render.yml` (every 30 min) or `pilot-render-stills.yml` in parallel → `ci/render_pilot.sh` → `still_render.py`; `ops/RENDER_HOLD` pauses the queue |
| QA + package | `production/qa_pilot.py` (frozen criteria), `package_pilot.py` (title, description with footage credits, chapters, thumbnail) |
| Review + approval | `approve.yml` → `long_review.py`, `three_stage.py`, `publish/prepublish_gate.py`, `owner_quality_policy.py` |
| Publish | `approve.yml` → `prepublish_gate.py` → `publish.yml` (long), `publish-episode.yml` (Bible Shorts, from `episode.yml`), `first-comment.yml`. The prayer Shorts-from-long line (`shorts.yml`, `shorts-review.yml`, `publish-shorts.yml`) is retired (slim audit 2026-10-28) |
| Arc links (Shorts ↔ long) | `arc-links.yml` (no cron: `heartbeat.yml` dispatches it at 10:20, 13:50, 23:35 UTC when `publish/arc_links.py todo` finds work in the repo files; input `mode` plan = print only) → `publish/arc_links.py`: for each arc of `production/bible/arcs.json` whose long is public (videos.list), each public Short gets first description line "▶ The full story: https://youtu.be/<long>" (rest and KJV/AI disclosure kept, else skipped) and one comment linking the long; the long's description ends with its Shorts and the next arc's first Short. Only videos in `arcs.json` are ever written; same credential as `publish_video.py`, scopes checked each run; every change in `publish/arc_links_ledger.json`. Stops under `ops/PUBLICATION_HOLD` (and `todo` reports nothing); the long must be public and `processed`; a Short skipped for a missing disclosure or a comment refused for good is recorded with its reason and not retried |
| TikTok mirror | `tiktok.yml` (dispatched by the heartbeat at :40 every hour while a Short waits, E90; its own 20-min cron is only a second chance because this repository's crons are dropped; the Claude clocks never dispatch it; `discover` to check the channel) → `publish/tiktok_publish.py`: every Bible Short already on YouTube goes to TikTok through Buffer's free plan (GraphQL API, `BUFFER_API_KEY`, automatic publishing), same file by its public release URL (sha256 checked), caption pointing to the long on YouTube and stating the AI visuals and voice; one per run; `publish/tiktok_ledger.json` |
| Comment replies, YouTube | `comment-replies.yml` (no cron: the heartbeat dispatches it at 01:10, 05:10, 09:10, 13:10, 17:10, 21:10 UTC; inputs `run`, `fetch`, `dry`) → `publish/comment_replies.py`: `post` answers up to 4 decided comments a run and 20 a UTC day (`comments.insert`, `parentId`), each checked live first (still there, on our channel, not already answered by us), then `fetch` queues viewers' new top-level comments (`commentThreads.list allThreadsRelatedToChannelId`) in `publish/comment_queue.json` with the video's title and episode. Claude decides each queued comment in `publish/comment_replies.json` (REPLY with text and optional checked `verse`, or SKIP with a reason) by PR; `comment_replies.py check` and `publish/reply_policy.py` gate it; ledger `publish/comment_replies_ledger.json`. Same credential as `publish_video.py` (youtube.force-ssl). The API cannot like comments. Stops under `ops/PUBLICATION_HOLD` |
| Comment replies, TikTok | `integrations/tiktok-local/` on the owner's PC (`C:\HeroVerse\tiktok-runner`, device "Matheus", Desktop Commander): `runner.py comments` → `out\comments.json`; Claude writes `out\replies.json`; `runner.py reply --in out\replies.json` likes and answers (3 a run, 20 a day, 45-240 s apart; ledger on the PC). Its own Chrome profile, logged in once by the owner (`runner.py login`); never the owner's everyday profiles or cookies. Stories: not on TikTok's web, so not posted. [README](integrations/tiktok-local/README.md) |
| Short episode (Keeper + acted scenes) | Claude writes `production/bible/plans/<episode-id>.json` (`bible-plan-v2`); `production/bible/plan_check.py` gates it (Shorts v2, PROMPT_GUIDE: KJV exact on narration and spoken lines, 170-179 s from part 7, the first shot a spoken conflict line (a character or God's voice, never the Keeper), spoken lines by APPROVED characters with a voice, God's lines Scripture-only over a scene with no person, a `climax: true` acted shot, the Keeper only after it for the insight and close at <= 25 %, lesson <= 25 %, talking lines 2-12 s, approved characters with their look word for word, anonymous figures or <= 2 s establishing shots at <= 15 %, God never a figure). Every shot first through `shot-probe.yml` (manual, main only: plan, shots, attempts, or `adopt_run` to adopt clips a build run already made; the build's own request, checks and regenerations, clips as `shot-<id>-<shot>-sha256-<sha>.mp4`, sheets and record on `claude/shot-probe-<id>-<run>`), approved by Claude's frame review at >= 9.5 with `episode_build.py approve-shot` into `production/bible/shots/<id>.json` by PR (E114). `episode.yml` (manual, main only, input `plan`, no Pavo secret; refused until every shot has an approved clip of its current request) → `production/bible/episode_build.py`: Kokoro line by line (narration am_michael, each spoken line in its speaker's voice from characters.json, God am_onyx), each approved clip downloaded by its sha256 and checked again with `clip_check.py` and `lipsync_check.py` (no shot generated; the probe used the same request: each talking line as Pavo input audio with its references, a fresh exact 0-credit quote on `PavoVideoClient`), `short_engine.py` compose (cuts every 2-4 s, captions, owned music, -14 LUFS), `clip_check.py --composed`; `bible-<id>-sha256-<sha>.mp4` through `ci/assets.sh`, 20-frame sheet and per-shot report pushed to branch `claude/episode-<id>-<run>` (`evidence/episodes/<id>/`). Nothing is published: Claude reviews the sheet at >= 9.5, writes `episodes/<id>.json` and dispatches `publish-episode.yml` |
| Bible-story long (LONG_DESIGN slice 3) | `long-build.yml` (manual, main only, inputs `plan` = `production/bible/plans/<arc>-long.json`, `resume_run`; no Pavo secret, nothing generated) → `production/bible/long_build.py` around episode_build's steps: `long_plan_check --strict`, `verify-preflight` first, Kokoro at LONG_LINE_GAP with the cold open held to 30 s, approved clips by sha256 checked again, the long's cuts (one a shot, story QA v3 4-7 s holds, windows on their source clip), one Real-ESRGAN job a clip to 2560x1440 (matrix, 20 at once), the assembly (no burned captions, owned music, -15 LUFS / -1.5 dBTP, the .srt by `captions.track_record`, `manifest.json` for qa_pilot v3); `bible-<long>-sha256-<sha>.mp4` and `.srt` through `ci/assets.sh`, sheet, manifest and report on `claude/long-<long>-<run>`. Nothing is published |
| Preflight (before every build, E106; the long too, E127) | `episode_build.py preflight <plan> --voice <Kokoro venv python> <work prepared by pilot_render.py prepare> --refs --write` → `production/bible/episode_preflight.py` (+ `long_preflight.py`), local, 0 Actions, 0 credits; report `evidence/preflight/<episode>.json` by PR; `episode.yml` / `long-build.yml` run `verify-preflight` first; `check-record <episode json>` before `publish-episode.yml`. What it checks and refuses is the contract in `SYSTEM.md` "No rework" (one copy, E115 class drift); refusal codes in `ops/refusal_registry.json` (`ops/test_refusal_parity.py`) |
| Stills from ChatGPT (owner's PC) | [integrations/chatgpt-local/README.md](integrations/chatgpt-local/README.md): `C:\HeroVerse\chatgpt-runner` on device "Matheus" (Desktop Commander), the runner's own Chrome profile signed in once by the owner (`runner.py login`). Cloud agents: `bridge.py job <still> "<subject>" <approved refs>` → write the job on the PC → `runner.py job` (refs by URL and sha256, ONE 16:9 image, the full file, record with prompt, refs, conversation URL, time, sha256 and OpenAI's ownership terms) → review with `read_file`; `bridge.py push` sends it to `claude/chatgpt-image-<id>` (gh on the PC). One at a time, 3 min apart, 30 a day; a challenge or usage limit stops it (exit 4/5). Stdio MCP `mcp_server.py` for a session on the PC. A DRAFT candidate like any still: Claude's still review decides |
| AI video (Pavo, first source) | `.mcp.json` → [integrations/pavo/README.md](integrations/pavo/README.md): `heroverse-pavo` MCP in the main session, Agnes Flash 720p 4-12 s, text / first frame (+ last) / up to 5 references, with references up to 3 narration audios (.mp3/.wav, 2-12 s in total) and an optional `sound` flag (v0.4), only at a fresh exact zero-credit quote that prices them (a nonzero quote refuses with the number); standing owner authorization (2026-10-25); without input audio the output track is stripped before use. When Pavo's free quota runs out, silent shots take free fallbacks (footage library, FLUX stills with motion; owner R1-R4, DECISIONS 2026-10-27); the direct Agnes route (`agnes-clip.yml`) is retired (DECISIONS 2026-10-28). |
| Keep it moving | `heartbeat.yml` dispatches the scheduled work (the clocks below); `reconcile.yml` retries errors; `render_queue.py stale` reports passed slots; `ops/runway.py` (goal-report.yml) checks the long cadence: one Bible-story long every 2 days at 10:00 UTC from 28/10, counted as "script" only when the full `script_check` passes (its structure gate `structures/bible-story-long.json` `script.gate` included), stage rule `runway.long_stage` shared with the daily report; a prayer pilot still scheduled ahead alerts PRAYER_LONG_SCHEDULED; `prepublish_gate.py` (row `format`) and `publication_binding.py` (NOT_STORY_LONG, run by publish.yml before any upload) refuse a non-story pilot |
| Voice change (ruler) | `production/voice/voice_judge.py` judges any future voice change (DECISIONS 2026-10-26 "Voice"); the Chatterbox A/B (`voice-sample.yml`) is closed and retired (Kokoro stays) |
| Hold a scheduled upload | `channel-privacy.yml` mode `unschedule` → `channel/channel_privacy.py`: each id of `channel/hold-plan.json` becomes private with no publishAt (videos.update status; nothing deleted; the receipt keeps the old publishAt for the undo); a video already public is never changed (SKIPPED_ALREADY_PUBLIC). Dispatched by hand only |
| Caption tracks: audit and repair (E107) | `channel-privacy.yml` mode `captions-audit` → `channel/captions_audit.py audit`: read-only (GET only), every upload in `captions_scope` (engine = the ledger's videos, english, all) gets its tracks from captions.list (status serving/syncing/failed, failureReason, trackKind, isDraft) and one verdict (OK, FAILED, SYNCING, DRAFT, NO_UPLOADED_TRACK); receipt `channel/captions-audit-<run>.json`, ids and statuses only; stops at `captions_units_max` (50 units a video). Mode `captions-repair` re-uploads our English track (delete our failed track, never the ASR one; insert; wait for serving) only for the videos of a reviewed `channel/captions-repair-plan.json` (at most `MAX_PLAN` a run), each bound to its manifest by the ledger key; it updates that ledger entry and writes its receipt after every delete and insert. Both dispatched by hand only. `publish_video.py` itself now waits (bounded, `captions.WAIT_CALLS`) for the inserted track to serve; a failed track is re-inserted at most once a run, then CAPTIONS_FAILED; a resumed upload with an invalid legacy SRT only warns (CAPTIONS_SRT_INVALID) and leaves the step to the repair; preflight validates the exact SRT (`publish/captions.py`) |
| Measure | `goal-report.yml` (daily YPP report in `evidence/daily-report/`; impressions, thumbnail CTR and derived clicks per video and per day from the YouTube Reporting API reach report `channel_reach_basic_a1`, `mining/reach_report.py` → `daily-report/reach.json`, PENDING/UNKNOWN with the reason when absent), `market-panel.yml`, vidIQ research (≤ 10 calls/day, ledger in `evidence/vidiq/`) |

## Clocks (single-clock design, active 2026-10-28)
One GitHub scheduler of record; the existing Claude and ChatGPT routines share the control lease described below. Only its holder performs agent-directed effects. Their schedules remain unchanged.
| Clock | When | Does | Never does |
|---|---|---|---|
| `heartbeat.yml` (GitHub cron) | :41 every hour | dispatches what `ops/heartbeat.py` TASKS says is due from the run history: nightly-images, market-panel 07:17 → goal-report 07:45, reconcile, tiktok (:40 slot, while a Short waits), arc-links, comment-replies (six slots) | the only GitHub cron besides `tiktok.yml`'s own second-chance cron (`ops/test_schedules.py`) |
| Light clock (Claude, Haiku, fresh session) | :14 every hour | mechanical watchdog: re-dispatches `heartbeat.yml` when its last run is > 55 min old, reports failed runs, missed slots and TikTok ledger states (`publish/tiktok_ledger.json`) to the main session | dispatches `tiktok.yml` or any production workflow |
| Main clock (Claude, main session) | every 4 h at :29 | production: the long and Shorts pipeline, Claude reviews (`render_queue.py review`/`preview-review` when they list anything), PRs; then the comment replies (below) | re-checks the heartbeat or the TikTok mirror |
| Daily pass (Claude) | 08:05 UTC | after goal-report 07:45: the report, the day's decision (`strategy/DECISIONS.md` protocol) and the live-intelligence loop (`SYSTEM.md`) | |
| Daily mining (Claude) | 09:47 UTC | vidIQ mining under the same budget (≤ 10 calls/day, ledger first) | |
| Existing ChatGPT supervision | :14 every hour | continue the accepted delivery under the shared control lease; reconcile existing jobs first | duplicate a valid owner's work, replay an uncertain request or bypass production gates |
**Comment replies in the main clock** (after production, a few minutes; owner 2026-10-28):
1. YouTube: `python3 migration/publish/comment_replies.py todo` lists the queued comment ids without a decision. For
   each, read its entry in `publish/comment_queue.json` (text, video title, episode; the episode's plan or
   `episodes/<id>.json` for the story) and write a decision in `publish/comment_replies.json`; `comment_replies.py
   check` must PASS; branch `claude/replies-<date>-<hhmm>`, PR, squash merge. The next heartbeat slot posts them.
2. TikTok (device "Matheus" online): `C:\HeroVerse\tiktok-runner\.venv\Scripts\python runner.py status`; when
   `LOGGED_IN`, `runner.py comments`, read `out\comments.json`, write `out\replies.json` (same decision format, plus
   `comment_id`, `video_id`, `author`, `comment_text`), check it with `reply_policy.py check FILE tiktok` (copy in the
   session) and start `runner.py reply --in out\replies.json` as a background process (it paces itself for up to
   ~12 min). `NOT_LOGGED_IN`, `CHALLENGE` or `UNCERTAIN` go to the owner in one line; never retried by hand.

`channel-privacy.yml` left the heartbeat (a finished job): it runs only when dispatched by hand. The runner's own
`render.yml` cron (:13, :43) lives in heroverse-runner.

## Known limits (measured)
- Offline editorial drafts: `production/draft_render.py MANIFEST --output PREVIEW` consumes the existing
  private editing package, never the production approval queue. Sources must match their hashes; reuse of
  existing stills is explicit. The CLI locks the output, resumes matching segments, and delivers atomically
  only after video frame/duration and full-decode checks. An optional hash-bound `audio_copy` input preserves
  AAC payloads and packet timing. A matching delivered file is reused without another render. The existing
  supervisor can invoke this command after materializing the editing package; no additional scheduler,
  public media transfer, source approval or production-plan substitution is implied. A receipt is technical
  DRAFT evidence only. `heroverse-runner/render.yml` still selects legacy pilot renders; `QUEUE_EMPTY` there
  is not a statement about Bible draft readiness. Qualified Bible production uses the handoff below.
- Existing private edits (E224): `production/bible/episode_build.py import-edit BINDING ROOT WORK`
  imports an existing edit without Kokoro, retiming, extra gaps or an added tail. The binding uses schema
  `heroverse-existing-edit-v1`, episode, fps 30, total frames, hash-bound relative `path`/`sha256` records for
  plan, manifest, master_audio, final_mix and captions, plus contiguous visual frame spans. Each visual has
  its manifest id, ordered `logical_shots` with shot/start_frame/end_frame and exact `narration_units`
  (kind, text, voice and reference when present). The manifest retains source hashes, crops, speed and starts.
  No symlinks or parent paths are accepted. A new private WORK receives the byte-identical master, final mix,
  captions and media, exact PCM Keeper slices and an `existing-edit.json` receipt. Repeating the same import
  verifies all delivered hashes; a partial or changed WORK is refused. `render-imported WORK OUT` uses the
  existing DRAFT renderer and copies the mix; OUT must be outside WORK. Regular voice/compose/probe commands
  refuse this workspace. Imports keep every full-plan blocker, contain no fabricated word boundaries,
  submit no provider requests and grant no source, audiovisual or publication approval. Keep private inputs
  outside tracked files. Actions/Pavo transport and approved-shot integration remain separate gates.
- Qualified production handoff (E213): the existing heartbeat checks Bible plans independently of the pilot
  render queue. A current strict-plan/preflight/order PASS can queue one `episode.yml` or `long-build.yml` request
  in `migration/requests/`, then invoke the same reusable durable-claim dispatcher. Prior claims/acknowledgements,
  active builds and discovered evidence stop automatic replacement. Refusals are visible in the job summary.
  This closes ready-plan -> build, not mining/modeling, source approval, perceptual review or publication readback.
- Build evidence discovery (E207): the existing heartbeat's independent read-only `review-discovery` job
  lists `claude/long-*` and `claude/episode-*` branches with exact commit and build run IDs in its log/summary.
  The designated supervisor reads this inventory before the main-tree review queue, fetches each report at
  that commit and reconciles its media hash/current plan against existing reviews. Retained historical branches
  are not automatically pending work. Discovery neither validates the evidence nor invokes a reviewer;
  reviewer invocation remains an explicit operational gap. No new clock, approval or parallel ledger is added.
- Long videos are reviewed by Claude (`ops/CLAUDE_REVIEW.md`) since 2026-10-24: `gemini-3.8-flash` answered only
  intermittently on the free tier and every free Gemini candidate failed calibration. Bible Shorts are reviewed by
  Claude on their frame sheets (`approve-shot`, E114); only the retired Shorts-from-long line (`shorts_review.py`,
  prayer pilots) still calls Gemini.
- Workers AI free allocation: about 44 FLUX images a day (resets 00:00 UTC).
- 1440p footage needs `PIXABAY_API_KEY` (Pexels stopped issuing keys in October 2026): Wikimedia Commons has little ≥ 1440p nature footage. Pinterest is not a source: its pins carry no licence (copyright and reused-content risk).

- The one manual step of the arc links (YouTube Data API v3, discovery revision 20261022,
  `evidence/youtube-api/20261026-related-video-and-pin.json`): the API has no field for a Short's "related video"
  and no way to pin a comment. When an arc's long goes public, in YouTube Studio: each of the arc's Shorts →
  Details → Related video = the long; on each Short, pin the channel's comment that links the long. Never by a
  browser script or the owner's cookies.

## Shared Claude Code / ChatGPT execution

Owner direction, 2026-10-30: both environments act on the same HeroVerse project.
When one cannot continue because of usage limits, the other continues from the
accepted delivery. Do not rebuild the other's work or alternate speculative fixes.

### One source of project truth

Read current main, AGENTS.md, CLAUDE.md, the latest migration/evidence/handoff,
DECISIONS.md and the relevant plans/receipts. Reconcile open PRs, workflow runs and
migration/requests/{inflight,done} before an effect. Private media packages remain
private; public handoffs refer to media hashes and task IDs, not private access links.
A completed test/review is reused while its exact inputs and criteria still match.
Fix only a demonstrated defect, at its responsible stage.

## Shared control reference

The operational branch `claude/shared-executor-control` carries coordination
metadata in its head commit message, prefixed `HEROVERSE_EXECUTOR_LEASE_V1\n`.
It is not a production branch, video ledger, scheduler, approval or merge candidate.
Its tree is unchanged from its parent. Do not merge it into main or use it to ship code.

Message JSON fields: `schema` = `heroverse-executor-lease-v1`, `owner` =
`codex`, `claude` or null, `run_id`, `state` = `active` or `idle`,
`renewed_at`, `expires_at` (UTC), `task`, `base_main_sha`, and `next_action`.
Never include credentials, private media links or account quota details.

For each scheduled or interactive project-writing run:
1. Read the control ref and its commit. Save its exact SHA. If missing/malformed,
   do read-only diagnosis; do not silently initialize a second controller.
2. If another run's active lease has not expired, monitor read-only and return.
   Availability of tokens does not justify interrupting its valid work.
3. If idle or expired, reconcile existing provider/workflow IDs and claims first.
   Expiry transfers supervision, never permission to replay an uncertain job.
4. To acquire: create a commit using exactly the observed head as parent and its
   unchanged tree; set owner/run_id/state active, renewed_at now and expires_at
   at most 55 minutes later. Update the control ref only as a fast-forward from
   that exact observed SHA (connector update_ref expected_sha + force=false;
   Git push without force, or GitHub ref PATCH force=false). Competing sibling
   commits must fail. Read back and require your new SHA before effects.
5. Renew before every effect and at least every 10 minutes during long work with
   the same compare-and-swap procedure. If ownership changed, stop new effects.
   An expired holder must reacquire, never assume it still owns the lease.
6. At a safe boundary, record the real delivery in the existing handoff/PR/receipt,
   then release by a similarly guarded commit: state idle, owner null,
   expires_at now, next_action describing the existing task. Do not release
   while an unrecorded side effect or specialist is still active.
7. On any uncertain write result, read the same ref/commit/operation before retry.
   Never force, delete or reset the coordination ref to win ownership.

### Scheduling and availability

Keep the existing GitHub heartbeat, existing ChatGPT supervision and existing
Claude routines. No additional polling clock. Each routine checks the shared
control reference before effects. The light Claude watchdog only handles mechanical
checks; it respects an active lease and never starts media work itself. Daily
analysis/mining also use the same lease and existing daily ledgers.

The first eligible scheduled executor acquires the lease. The other observes.
When a provider's usage limit prevents a run, the other can acquire the idle/expired
lease on its next scheduled execution. A returning executor reconciles state first.
Do not claim immediate switching or read the other provider's usage balance through
a tool that does not expose it. If both executors are unavailable, no agent can
continue reasoning; already-dispatched GitHub jobs retain their independent state.

### Same review workflow on either host

Use the original Anthropic `pr-review-toolkit` command and applicable specialist
prompts. The ChatGPT personal skill of that name packages upstream version 1.0.1,
revision `f8c5e7a1dcb71b10cb74586224b5401f3de5db28`, with host-tool mapping.
This is execution of that portable workflow by Codex, not a Claude login and not
a claim that Anthropic models reviewed the PR. Record the true executor, exact
head/base, upstream revision and actual specialists. Keep security sweeps separate.
The required review is not replaced with an unrecorded informal inspection.
Code changes still use claude/*, PR, required tests/reviews and squash merge.

### Existing execution tools

- GitHub: common code, handoffs, durable request claims, runs and publishing gates.
- Pavo: preserve `.mcp.json` / `heroverse-pavo` and the existing adapter/workflows.
  A host without its stdio MCP uses existing authorized GitHub request entry points;
  it does not copy tokens or create another provider implementation.
- Gemini native evidence: preserve native-review.yml, saved interaction IDs and
  actual model identity. Code-review tooling does not qualify audiovisual accuracy.
- Kokoro/ffmpeg/Cloudflare/footage: existing preparation and render paths only.
- vidIQ: existing connection, current ledger and spending restrictions. Connection
  does not authorize generation or repeat paid research.
- Buzzy: optional diagnostics/catalog connection only until its mutation route,
  zero-cost conditions, rights and quality gates are actually qualified.
- Runway stays excluded by current project spending policy. Ads stay on hold.
- Desktop-dependent helpers require an online authorized device. A connected
  plugin alone does not establish executor availability.
- Hookify, security-guidance, verified-security-sweep, social-media-skills,
  superpowers, headroom, ffmpeg-llm, image-generation, bible-by-midvash,
  feature-dev, commit-commands, claude-md-management, cartographer and
  claude-code-setup retain the purposes/limits documented in CLAUDE.md.
  Being installed on Claude does not establish installation on ChatGPT.
  Host-specific hooks are not silently converted into advisory checks.

All source/media approvals, frozen QA, the 9.5 floor and publication readback
remain required. No manual APPROVAL.json, copied reviewer identity or transferred score.

## Documents
One home per subject (the same list as CLAUDE.md "Read first"):
- `SYSTEM.md`: the four-stage delivery contract, "No rework", token budget, the clocks, the daily live-intelligence loop.
- This file: what runs and its entry points.
- `production/bible/SERIES.md` (niche, cadence), `production/bible/PROMPT_GUIDE.md` (a Short built for 9.5),
  `production/bible/LONG_DESIGN.md` (the Bible-story long).
- `ops/CLAUDE_REVIEW.md` (Claude's review), `ops/ERRORS.json` (regression register), `ops/RUNNER_WAKEUP.md`.
- `strategy/DECISIONS.md` (measurements and decisions), `strategy/VIDIQ.md`, `strategy/MODELING_SPEC.md`,
  `STANDARD.md` (the still-render standard, R3 fallback).
- Audits: `evidence/audits/` (system audits, e.g. `20261028-slim.md`), `../docs/audits/` (security sweeps).

## Private Pavo talking DRAFT (E226)

`pavo-private-audio.yml` transfers an existing exact WAV through a Pavo upload address encrypted to the existing operator certificate. A committed metadata manifest binds the PCM container hash, measured duration, approved Keeper reference and exact prompt; no private media or URL enters GitHub. The caller decrypts the `pavo-private-upload` CMS artifact and PUTs the matching WAV directly to its validated storage destination. The job verifies bytes/PCM, refreshes shared quota and uses the existing zero-credit-quote generator once. Public claims and conversation IDs live on the existing `claude/shot-probe-<episode>-<run>` record branch. Provider URLs/results remain in encrypted artifacts.

Use `reconcile_run` only to GET the saved conversation ID of an earlier run; no attachment, quote or generation is repeated. A claim without an ID is unresolved and cannot be automatically retried. `retry_run` is a separate explicit request for one probe after a terminal failure: every prior matching claim must be FAILED with a CID, the selected source must be the latest, at least three hours must have passed since its first terminal readback, and a fresh Pavo GET must still prove failed with no video before the new claim. The new claim records `retry_of`; shared quota and zero quote still apply. Three hours is a minimum wait, never proof of quota reset. The job itself never repeats a generation. The active shared executor lease must match `lease_run_id`. This bounded DRAFT path does not approve the unfinished full plan or bypass source, lip-sync, speech, audiovisual or publication gates. No new clock or provider credential is introduced.
