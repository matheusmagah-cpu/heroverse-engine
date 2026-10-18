# HeroVerse operations (compact state for any session)

Read this file first; do not re-read history, logs or whole evidence files.

## Owner rules (the owner, Matheus, is Brazilian: talk to him in Portuguese; the channel is English-only)

**Goal and pace**
- **Goal:** all YPP requirements in 14 days. 30 days is only the error margin.
- **Benchmarks:** the fastest *policy-clean* channels.
- **Decisions:** daily, from market data, not on 7/14-day cycles.

**Policy and channel**
- **Policy first:** nothing that risks demonetisation. Never use borrowed identities or recordings, fear-bait, fabricated prophecy or reused content.
- **Channel:** English only. Portuguese uploads are hidden; that is reversible.
- **Format:** long videos plus Shorts, and every format model the system can produce.

**Mining**
- **Scope:** whole-video structure mining — script, structure, hook, theme, picture/video format, pacing, music, packaging, comments. Never opening-only.
- **Accuracy:** must be measured.

**Modelling**
- **Bar:** the model must BEAT the mined reference. It needs measured targets and the same-instrument scorecard.
- **After that:** an authenticity layer of own reasoning, opinion and critique.

**Production**
- **Look:** truly cinematic at zero cost: FLUX images, upscale, depth parallax, film finish.
- **Paid video engines:** only after revenue.
- **Shorts:** never a blind cut. Analyse the whole video for the best moments, give each Short its own edit, and run a watched review before publishing.

**Publication**
- **Order:** validate BEFORE upload. Upload public, or private + publishAt when scheduled.
- **Authority:** automatic publication is authorised once everything passes the gates.
- **After upload:** once YouTube confirms it, delete the finished video files. Keep only production files.
- **Compression:** yes, but never at a loss of quality.

**Cost and workflow**
- **Spending:** zero money.
- **Claude usage:** everything must fit the owner's Claude Code plan. Claude supervises in short sessions; GitHub, Cloudflare and Gemini do the recurring work. Open new lean sessions yourself when useful.
- **No rework:** if something fails, find another way, unless an equally good alternative exists.
- **The owner decides:** for example, the public runner is kept by his decision. He communicates directly; "Dot" is his assistant that does GitHub UI steps.

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
- **YouTube Data API (10k units/day, resets 07:00 UTC):** panel 2,400 (half of the queries each day, alternating); packaging mining 500 (Sundays); long video ~2,100 (upload 1,600 + captions 400 + thumbnail/playlist); each Short ~1,650. A normal day: panel + 1 long + 3 Shorts = 9,450. Uploads go after the 07:00 UTC reset when the day's units are spent. A second Google Cloud project's API key for the public reads (panel, packaging) would free the whole 10k for uploads.

## Daily schedule (UTC; BRT = UTC-3) — the nightly chain runs without Claude
**Scheduler:** GitHub delays and drops scheduled runs under load (2026-10-17/18: every daily cron of the engine was
dropped). The engine has one cron, `heartbeat.yml` at minutes 11 and 41 (48 chances a day). Each beat reads the
real run history and dispatches every task whose slot has passed without a run since it (a failed run is retried
after 45 min, up to the task's attempts); tasks with a work condition run only when there is work
(`migration/ops/heartbeat.py`, tested). The daily report lists the health of every task, of the heartbeat and of
the runner, with alerts (`migration/ops/health.py`). The public runner checks the render queue at :13 and :43.
**External clock (2026-10-18):** GitHub then fired none of the heartbeat's or the runner's crons for hours, so an
hourly scheduled task of the Claude platform, bound to the main Claude session (which has repository access;
fresh routine sessions get GitHub 403), dispatches `heartbeat.yml` and the runner's `render.yml` every hour at :14.
Both are idempotent, so the GitHub crons that do fire and the clock never double any work. The daily Claude
analysis (08:05 UTC) is bound to the same session; the two older routines that ran in fresh sessions were disabled
(no repository access; one still told the session to write APPROVAL.json by hand, bypassing the gate).

| Slot (UTC) | What | Where | Runs when |
|---|---|---|---|
| 00:20 | native windows of videos never checked, then accuracy.json | mining-accuracy.yml → acquire-reference-window.yml | daily |
| 00:30, 01:30, 03:30, 12:30 | missing images of pilots publishing in the next 72 h (FLUX + 2x upscale) | nightly-images.yml → cf-images.yml | images missing |
| :13 and :43 hourly | next pilot of the queue (publishes ≤ 48 h, images complete, no render of this script): long video, QA; Shorts handed off | heroverse-runner render.yml (render_queue.py) | queue not empty |
| after each render | Shorts (QA-PASS render only): selection, own edit, watched review (gemini-3.8-flash only) | shorts.yml (on shorts/inputs.json) | push |
| after each render | gates: QA, preflight, scorecard, watched review (gemini-3.8-flash only), whole-file scan → gate.json PASS/FAIL/UNKNOWN; PASS → APPROVAL.json → publish | approve.yml → publish.yml | push |
| 07:17 | market panel (2,400 units) + model + forecast + daily intel | market-panel.yml | daily |
| 07:20, 10:20, 13:20, 16:20, 19:20, 22:20 | retry approvals (ERROR/UNKNOWN), Shorts never reviewed, failed publications | reconcile.yml | work waiting |
| 07:35, 13:35, 19:35 | the approved Short (one per long video) at its slot | publish-shorts.yml (pending_shorts.py) | Short pending |
| 07:45 | goal report + scheduler health (waits for the panel until 09:30) | goal-report.yml | daily |
| 07:50 Sun | packaging mining (3 adjacent niches) | packaging-mining.yml | production idle |
| 08:05 | hide remaining Portuguese uploads | channel-privacy.yml | daily |
| 08:05 | **daily Claude analysis**: goal report + intel → decisions protocol → next scripts | scheduled Claude session | daily |
| 08:30 | structure mining, incremental | structure-mining.yml | production idle |
| schedule.json | long video at publish_at; Shorts at their slots | YouTube publishAt | — |

Claude's part: write the next scripts (2 per day: morning + night prayer) with schedule.json and images.json, at least 2 days ahead, and read the daily report. Scheduled workflows of the public runner stop after 60 days without a commit there.

## External tools
- vidIQ: research only (keyword demand, outliers, trending), informative until validated; budget ≤ 30 MCP calls
  a month on Free; never a source of our own channel's numbers; rules in `strategy/VIDIQ.md`.

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
- **Decisions:** every change follows strategy/DECISIONS.md (evidence → checks → measurement → keep or revert). Active: D-01 night ~28–33 min and D-04 morning ~25 min (conformance to the registered strategy), D-02 four fear-bait videos hidden (compliance), D-03 one Short per long video (one-sided p = 0.062, observational, 48 channels). D-05 subscribe ask reverted (pilot-003 rendered with it before the revert). First measurements: 48 h after pilot-003/004 open.
- **Published:** pilot-002 (v4zN53ZiUIs) opens 2026-10-18 10:00 UTC; its Shorts were re-made privately with the review fixes and publish at 07:35 UTC if they pass.
- **Next videos:** pilot-003 (morning prayer, strength) 2026-10-19 10:00 UTC; pilot-004 (night prayer, sleep) 2026-10-20 00:00 UTC. Scripts, images.json, schedule.json in place; images generated 2026-10-18 ~00:00 UTC; renders by the nightly chain.
- **Spec:** strategy/MODELING_SPEC.md (measured targets, scorecard, policy). Teaching format needs its own frozen QA criteria before its first render.
- **Mining:** structure 20261017 (+ prayer); accuracy check automated weekly (first windows requested 2026-10-18); packaging mining weekly.
- **Quota:** YouTube may count uploads and searches separately since 2026-06 (secondary sources; official page unreachable from the session). Until confirmed, the panel stays at 2,400 units. Never split the project to get more quota (sharding is prohibited by the YouTube Developer Policies); more quota only through the API Compliance Audit.
