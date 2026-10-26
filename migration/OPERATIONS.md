# HeroVerse operations — what runs (2026-10-23)

Owner: Matheus. Channel: HeroVerse `@heroverse74` (`UCuMF6pJQkyMzaVoAxFL86yA`), account Will. Claude writes the
scripts, code and fixes; the GitHub workflows do the heavy work. Credentials live only in repository secrets.

## Rules that never move
- Zero additional cost: no billing, paid service or promotional credit.
- Niche: original English Christian prayer, exact KJV quotations, no fear-bait, prophecy or health/wealth promises.
- Quality: `STANDARD.md` R1–R12, frozen QA (`production/qa_criteria_v3.json`, `qa_criteria_v4.json`), the designated
  watched review by Claude (`ops/CLAUDE_REVIEW.md`; items ≥ 7, overall ≥ 8) and the owner floor overall ≥ 9.5 for every new upload.
  Missing, errored or hash-mismatched evidence blocks; nobody writes approvals by hand.
- Every failure: root cause, fix, an antidote test and an entry in `ops/ERRORS.json`.
- Plan: 14 days (day 1 = 2026-10-18, day 14 = 2026-10-31); 21 days only as an extraordinary extension.

## The production line
| Step | Entry point |
|---|---|
| Script | Claude writes `production/pilot-NNN/script.json` (+ `images.json`, `schedule.json`); `production/script_check.py` gates it (R12 hook, length, originality, rights) |
| Footage | `footage.yml` → `production/footage/footage.py` (Pixabay when `PIXABAY_API_KEY` is set, Pexels when `PEXELS_API_KEY` is set, Wikimedia Commons CC0/PD/CC BY), automatic vetting; `footage/assign.py` picks a pilot's clips by mood |
| Pavo footage | `pavo-footage.yml` (input `production/pilot-NNN/pavo(-N).json`: `{id, conversation_id, url, prompt, words}` per clip, Pavo CDN URLs only) → `production/footage/pavo_footage.py`: one clip per job (10 in parallel), audio dropped, every native frame through Real-ESRGAN x4v3 on CPU (640x360 → 2560x1440, then 30 fps), `footage-<id>-sha256-<sha>.mp4` through `ci/assets.sh`, records `library/pavo-*.json` (vetting PENDING) and sheet `library/sheets/pavo-<run>.jpg` committed to main; Claude reviews the sheet and approves in a PR. The long uses them only under the story format's own frozen QA (QA v4 does not list the Pavo licence) |
| Images | `cf-images.yml` (FLUX on the Workers AI free allocation, Real-ESRGAN 4×), `nightly-images.yml`; `images-upres.yml` brings older stills to 4096 px |
| Render | runner `heroverse-runner/.github/workflows/render.yml` (every 30 min) or `pilot-render-stills.yml` in parallel → `ci/render_pilot.sh` → `still_render.py`; `ops/RENDER_HOLD` pauses the queue |
| QA + package | `production/qa_pilot.py` (frozen criteria), `package_pilot.py` (title, description with footage credits, chapters, thumbnail) |
| Review + approval | `approve.yml` → `long_review.py`, `three_stage.py`, `publish/prepublish_gate.py`, `owner_quality_policy.py` |
| Publish | `publish.yml` (long), `shorts.yml` / `shorts-review.yml` / `publish-shorts.yml` (Shorts), `first-comment.yml`, `description-refresh.yml` |
| Arc links (Shorts ↔ long) | `arc-links.yml` (no cron: `heartbeat.yml` dispatches it at 10:20, 13:50, 23:35 UTC when `publish/arc_links.py todo` finds work in the repo files; input `mode` plan = print only) → `publish/arc_links.py`: for each arc of `production/bible/arcs.json` whose long is public (videos.list), each public Short gets first description line "▶ The full story: https://youtu.be/<long>" (rest and KJV/AI disclosure kept, else skipped) and one comment linking the long; the long's description ends with its Shorts and the next arc's first Short. Only videos in `arcs.json` are ever written; same credential as `publish_video.py`, scopes checked each run; every change in `publish/arc_links_ledger.json`. Stops under `ops/PUBLICATION_HOLD` (and `todo` reports nothing); the long must be public and `processed`; a Short skipped for a missing disclosure or a comment refused for good is recorded with its reason and not retried |
| TikTok mirror | `tiktok.yml` (dispatched by the heartbeat at :40 every hour while a Short waits, E90; its own 20-min cron is only a second chance because this repository's crons are dropped; `discover` to check the channel) → `publish/tiktok_publish.py`: every Bible Short already on YouTube goes to TikTok through Buffer's free plan (GraphQL API, `BUFFER_API_KEY`, automatic publishing), same file by its public release URL (sha256 checked), caption pointing to the long on YouTube and stating the AI visuals and voice; one per run; `publish/tiktok_ledger.json` |
| AI clip test (Agnes) | `agnes-clip.yml` → `production/agnes_clip.py`: one Agnes Video 2.5 Flash clip (free tier, 720p, 4-12 s, `AGNES_API_KEY`) kept as a run artifact with `clip_check.py` and a frame sheet; TEST ONLY until the terms allow commercial use and the free output shows no watermark |
| Short episode (Keeper + acted scenes) | Claude writes `production/bible/plans/<episode-id>.json` (`bible-plan-v2`); `production/bible/plan_check.py` gates it (Shorts v2, PROMPT_GUIDE: KJV exact on narration and spoken lines, 170-179 s from part 7, the first shot a spoken conflict line (a character or God's voice, never the Keeper), spoken lines by APPROVED characters with a voice, God's lines Scripture-only over a scene with no person, a `climax: true` acted shot, the Keeper only after it for the insight and close at <= 25 %, lesson <= 25 %, talking lines 2-12 s, approved characters with their look word for word, anonymous figures or <= 2 s establishing shots at <= 15 %, God never a figure). `episode.yml` (manual, main only, input `plan`) → `production/bible/episode_build.py`: Kokoro line by line (narration am_michael, each spoken line in its speaker's voice from characters.json, God am_onyx), each talking line (the Keeper's, a character's) as Pavo input audio with its references, every shot one Pavo generation at a fresh exact 0-credit quote (`PavoVideoClient`), `clip_check.py` on every clip and `lipsync_check.py` on every talking clip (at most 2 regenerations, 5 for a talking clip (E98), then the run fails naming the shot), `short_engine.py` compose (cuts every 2-4 s, captions, owned music, -14 LUFS), `clip_check.py --composed`; `bible-<id>-sha256-<sha>.mp4` through `ci/assets.sh`, 20-frame sheet and per-shot report pushed to branch `claude/episode-<id>-<run>` (`evidence/episodes/<id>/`). Nothing is published: Claude reviews the sheet at >= 9.5, writes `episodes/<id>.json` and dispatches `publish-episode.yml` |
| AI video (Pavo, first source) | `.mcp.json` → [integrations/pavo/README.md](integrations/pavo/README.md): `heroverse-pavo` MCP in the main session, Agnes Flash 720p 4-12 s, text / first frame (+ last) / up to 5 references, with references up to 3 narration audios (.mp3/.wav, 2-12 s in total) and an optional `sound` flag (v0.4), only at a fresh exact zero-credit quote that prices them (a nonzero quote refuses with the number); standing owner authorization (2026-10-25); without input audio the output track is stripped before use. Then `agnes-clip.yml`, then vidIQ's generator only when both fail (DECISIONS.md 2026-10-25). |
| Keep it moving | `heartbeat.yml` dispatches the scheduled work; `reconcile.yml` retries errors; `render_queue.py stale` reports passed slots |
| Voice A/B | `voice-sample.yml` → `production/voice/chatterbox_sample.py` (Chatterbox, MIT, cloned from our own Kokoro narration; samples as a run artifact, nothing published) |
| Measure | `goal-report.yml` (daily YPP report in `evidence/daily-report/`), `market-panel.yml`, vidIQ research (≤ 10 calls/day, ledger in `evidence/vidiq/`) |

## Known limits (measured)
- Long videos are reviewed by Claude (`ops/CLAUDE_REVIEW.md`) since 2026-10-24: `gemini-3.8-flash` answered only
  intermittently on the free tier and every free Gemini candidate failed calibration. Shorts still use it until they
  move to the same reviewer.
- Workers AI free allocation: about 44 FLUX images a day (resets 00:00 UTC).
- 1440p footage needs `PIXABAY_API_KEY` (Pexels stopped issuing keys in October 2026): Wikimedia Commons has little ≥ 1440p nature footage. Pinterest is not a source: its pins carry no licence (copyright and reused-content risk).

- The one manual step of the arc links (YouTube Data API v3, discovery revision 20261022,
  `evidence/youtube-api/20261026-related-video-and-pin.json`): the API has no field for a Short's "related video"
  and no way to pin a comment. When an arc's long goes public, in YouTube Studio: each of the arc's Shorts →
  Details → Related video = the long; on each Short, pin the channel's comment that links the long. Never by a
  browser script or the owner's cookies.

## Documents
`SYSTEM.md` (the four-stage delivery contract), `STANDARD.md` (production standard), `strategy/DECISIONS.md`
(measurements and decisions), `strategy/MODELING_SPEC.md`, `strategy/VIDIQ.md`, `ops/RUNNER_WAKEUP.md`,
`ops/ERRORS.json` (regression register).
