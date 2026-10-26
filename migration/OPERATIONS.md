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
| Images | `cf-images.yml` (FLUX on the Workers AI free allocation, Real-ESRGAN 4×), `nightly-images.yml`; `images-upres.yml` brings older stills to 4096 px |
| Render | runner `heroverse-runner/.github/workflows/render.yml` (every 30 min) or `pilot-render-stills.yml` in parallel → `ci/render_pilot.sh` → `still_render.py`; `ops/RENDER_HOLD` pauses the queue |
| QA + package | `production/qa_pilot.py` (frozen criteria), `package_pilot.py` (title, description with footage credits, chapters, thumbnail) |
| Review + approval | `approve.yml` → `long_review.py`, `three_stage.py`, `publish/prepublish_gate.py`, `owner_quality_policy.py` |
| Publish | `publish.yml` (long), `shorts.yml` / `shorts-review.yml` / `publish-shorts.yml` (Shorts), `first-comment.yml`, `description-refresh.yml` |
| TikTok mirror | `tiktok.yml` (13:41 and 23:41 UTC; `discover` to check the channel) → `publish/tiktok_publish.py`: every Bible Short already on YouTube goes to TikTok through Buffer's free plan (GraphQL API, `BUFFER_API_KEY`, automatic publishing), same file by its public release URL (sha256 checked), caption pointing to the long on YouTube and stating the AI visuals and voice; one per run; `publish/tiktok_ledger.json` |
| AI clip test (Agnes) | `agnes-clip.yml` → `production/agnes_clip.py`: one Agnes Video 2.5 Flash clip (free tier, 720p, 4-12 s, `AGNES_API_KEY`) kept as a run artifact with `clip_check.py` and a frame sheet; TEST ONLY until the terms allow commercial use and the free output shows no watermark |
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

## Documents
`SYSTEM.md` (the four-stage delivery contract), `STANDARD.md` (production standard), `strategy/DECISIONS.md`
(measurements and decisions), `strategy/MODELING_SPEC.md`, `strategy/VIDIQ.md`, `ops/RUNNER_WAKEUP.md`,
`ops/ERRORS.json` (regression register).
