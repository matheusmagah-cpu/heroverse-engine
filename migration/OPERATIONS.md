# HeroVerse operations — what runs (2026-10-23)

Owner: Matheus. Channel: HeroVerse `@heroverse74` (`UCuMF6pJQkyMzaVoAxFL86yA`), account Will. Claude writes the
scripts, code and fixes; the GitHub workflows do the heavy work. Credentials live only in repository secrets.

## Rules that never move
- Zero additional cost: no billing, paid service or promotional credit.
- Niche: original English Christian prayer, exact KJV quotations, no fear-bait, prophecy or health/wealth promises.
- Quality: `STANDARD.md` R1–R12, frozen QA (`production/qa_criteria_v3.json`, `qa_criteria_v4.json`), the designated
  watched review (`gemini-3.8-flash`, items ≥ 7, overall ≥ 8) and the owner floor overall ≥ 9.5 for every new upload.
  Missing, errored or hash-mismatched evidence blocks; nobody writes approvals by hand.
- Every failure: root cause, fix, an antidote test and an entry in `ops/ERRORS.json`.
- Plan: 14 days (day 1 = 2026-10-18, day 14 = 2026-10-31); 21 days only as an extraordinary extension.

## The production line
| Step | Entry point |
|---|---|
| Script | Claude writes `production/pilot-NNN/script.json` (+ `images.json`, `schedule.json`); `production/script_check.py` gates it (R12 hook, length, originality, rights) |
| Footage | `footage.yml` → `production/footage/footage.py` (Pexels when `PEXELS_API_KEY` is set, Wikimedia Commons CC0/PD/CC BY), automatic vetting; `footage/assign.py` picks a pilot's clips by mood |
| Images | `cf-images.yml` (FLUX on the Workers AI free allocation, Real-ESRGAN 4×), `nightly-images.yml`; `images-upres.yml` brings older stills to 4096 px |
| Render | runner `heroverse-runner/.github/workflows/render.yml` (every 30 min) or `pilot-render-stills.yml` in parallel → `ci/render_pilot.sh` → `still_render.py`; `ops/RENDER_HOLD` pauses the queue |
| QA + package | `production/qa_pilot.py` (frozen criteria), `package_pilot.py` (title, description with footage credits, chapters, thumbnail) |
| Review + approval | `approve.yml` → `long_review.py`, `three_stage.py`, `publish/prepublish_gate.py`, `owner_quality_policy.py` |
| Publish | `publish.yml` (long), `shorts.yml` / `shorts-review.yml` / `publish-shorts.yml` (Shorts), `first-comment.yml`, `description-refresh.yml` |
| Keep it moving | `heartbeat.yml` dispatches the scheduled work; `reconcile.yml` retries errors; `render_queue.py stale` reports passed slots |
| Measure | `goal-report.yml` (daily YPP report in `evidence/daily-report/`), `market-panel.yml`, vidIQ research (≤ 10 calls/day, ledger in `evidence/vidiq/`) |

## Known limits (measured)
- The designated reviewer on the free tier returned HTTP 503 from 2026-10-21 to at least 2026-10-23; with it down
  nothing publishes. 20 requests/day when it answers.
- Workers AI free allocation: about 44 FLUX images a day (resets 00:00 UTC).
- 1440p footage needs `PEXELS_API_KEY`: Wikimedia Commons has little ≥ 1440p nature footage.

## Documents
`SYSTEM.md` (the four-stage delivery contract), `STANDARD.md` (production standard), `strategy/DECISIONS.md`
(measurements and decisions), `strategy/MODELING_SPEC.md`, `strategy/VIDIQ.md`, `ops/RUNNER_WAKEUP.md`,
`ops/ERRORS.json` (regression register).
