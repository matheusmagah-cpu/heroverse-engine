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
- **GitHub private repo (2,000 min/month):** panel ~10 min/day, publish, light jobs. Heavy renders go to the
  public `heroverse-runner` (no minute cap) once the `HERO_ENGINE_PAT` secret exists there.
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

## Pipeline gates (never edited after results)
1. **QA (frozen):** frozen criteria.
2. **Long video:** perceptual approval (`inspection/APPROVAL.json` bound to the file hash).
3. **Shorts:** `shorts_qa` plus the watched review (every item ≥ 7, overall ≥ 8).
4. **After publication:** the finished files are deleted from the release once YouTube confirms the upload.

## Status
- **pilot-002:** cinematic render running (private). The static PASS version (`9615503`, sha `52766f47…`) is the fallback for 2026-10-18 07:00 BRT.
- **Mining:**
  - Structure v2 on 4 teaching channels is done (`evidence/structure-mining/20261017`).
  - Clean prayer channels (United Prayer, Morning Grace Prayers, Prayer of Hope, Mercy Harbor Gospel) are being mined.
  - Grace & Glory is excluded (borrowed identity/recordings).
- **Next:**
  1. Accuracy check of the mining (native windows vs verbatim openings).
  2. Measured modeling spec (`blueprint_stats.py`).
  3. Scripts.
  4. Automate the daily chain.
- **Waiting on the owner:** `HERO_ENGINE_PAT` and `HERO_GEMINI_API_KEY` secrets in `heroverse-runner`.
