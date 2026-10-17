# HeroVerse operations (compact state for any session)

Read this file first; do not re-read history, logs or whole evidence files.

## Budgets (owner rules)
- **Money:** zero. No paid API, plan or card. Paid video engines (Veo, Runway…) only after the
  channel earns.
- **Claude (owner's ~R$110/month plan):**
  - Claude supervises; it does not run the factory.
  - Everything recurring runs in GitHub Actions and the free APIs.
  - One short Claude check-in per day, in a fresh session reading this file and `migration/evidence/daily-report/latest.md`.
  - No polling loops, no full log dumps, no re-reading of large JSON (use `jq`/`python -c` to extract only the needed fields).
- **GitHub:**
  - Heavy renders run on the public `heroverse-runner` (owner decision, 2026-10-17). It has 4 cores and no minute cap.
  - The owner was told that GitHub's Actions terms restrict runners to work related to their own repository, and accepted the risk to the account.
  - Its logs are quiet (`PUBLIC_LOGS=1`): titles and script text go only to a private log in the release.
  - Fallback: the private `pilot-render-stills.yml` runs the same script. Keep each render within about 45 min where possible so the fallback fits the 2,000 private minutes.
  - The private repo handles the panel, publication and light jobs.
- **Cloudflare Workers AI (10k neurons/day, resets 00:00 UTC):** images only (FLUX + 2x upscale on GitHub).
- **Gemini free tier (no billing):** mining, Shorts selection/review, watched reviews.
- **YouTube Data API (10k units/day, resets 07:00 UTC):** panel 6,500; privacy 50/update; publish ~1,700/video.

## Daily schedule (UTC; BRT = UTC-3)
| UTC | What | Where |
|---|---|---|
| 07:17 | market panel + model + forecast scoring + daily intel | market-panel.yml |
| 08:05 | hide remaining Portuguese uploads (no-op when done) | channel-privacy.yml (cron) |
| 00:30 | images for next day's scripts | cf-images.yml (to automate) |
| 01:00 | render long + 5 Shorts + QA + watched review | runner render.yml / pilot-render-stills.yml |
| 10:00 / 14:00 / 20:00 / 23:00 | long video, then 3 Shorts go public (publishAt) | publish.yml / publish-shorts.yml |

## How publication starts (no Claude tools needed)
Each pilot has `schedule.json` (`publish_at` plus `shorts_slots`, in UTC).

1. A session reviews the render's inspection sheets.
2. If they are clean, it writes `inspection/APPROVAL.json`: `approved`, the `output_sha256` from `out/qa.json`, `reviewed_at` and notes.
3. It merges that file to main.
4. The push triggers `publish.yml`. It checks the gates, uploads the video scheduled at `publish_at`, publishes the reviewed Shorts at their slots, and deletes the finished files.

`git` push through the session proxy is enough to start this.

## Starting any workflow without GitHub API tools
Commit `migration/requests/<name>.json` with `{"workflow": "file.yml", "inputs": {...}}` to main, through a branch and merge. `requests.yml` dispatches it once and moves the file to `done/`.

Example: `{"workflow": "pilot-render-stills.yml", "inputs": {"pilot": "pilot-003"}}`.

## Pipeline gates (never edited after results)
1. **QA (frozen):** frozen criteria.
2. **Long video:** perceptual approval (`inspection/APPROVAL.json` bound to the file hash).
3. **Shorts:** `shorts_qa` plus the watched review (every item ≥ 7, overall ≥ 8).
4. **After publication:** the finished files are deleted from the release once YouTube confirms the upload.

## Status
- **pilot-002:** cinematic render running on the public runner (heroverse-runner run 39062600672, from 19:28 UTC; private run 39058782907 cancelled). If its `shorts.json` says `NOT_REVIEWED_NO_KEY`, re-run the Shorts review privately. The static PASS version (`9615503`, sha `52766f47…`) is the fallback for 2026-10-18 07:00 BRT.
- **Mining:**
  - Structure v2 on 4 teaching channels is done (`evidence/structure-mining/20261017`).
  - Clean prayer channels (United Prayer, Morning Grace Prayers, Prayer of Hope, Mercy Harbor Gospel): first run (39056485165) lost its push on a `blueprint.json` rebase conflict; Record now retries (PR #62) and a re-mining request is queued.
  - Accuracy check: 12 native windows requested (`requests/accuracy-windows-20261017.json`).
  - Grace & Glory is excluded (borrowed identity/recordings).
- **Next:**
  1. Accuracy check of the mining (native windows vs verbatim openings).
  2. Measured modeling spec (`blueprint_stats.py`).
  3. Scripts.
  4. Automate the daily chain.
- **Secrets (as they stand):** `HERO_GEMINI_API_KEY` exists in heroverse-engine only; `HERO_ENGINE_PAT` exists in heroverse-runner (its checkout of the engine works); whether the runner has the Gemini key is unknown.
- **Render path:** private-only is primary. Optimise one long video plus its Shorts to ~40 runner-minutes on the private 2-core workflow (depth parallax on the opening and Shorts only, reuse voice/images when the script hash is unchanged, single-pass assembly), measured from run 39058782907's stage timings.
- **Runner:** optional extra, now active for pilot-002; every Gemini step (Shorts select/review, mining, watched reviews) stays in the private repo so the runner never needs the Gemini key. No new keys are requested unless truly needed.
