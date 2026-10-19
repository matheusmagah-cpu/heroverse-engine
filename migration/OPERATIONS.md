# HeroVerse operations — the single source of truth (rewritten 2026-10-18)

Read this file first. **It wins over every other document.** The only documents that direct the work are:
- `OPERATIONS.md` (this file): rules, roles, budgets, schedule, pipeline, status.
- `ops/DOT_PROTOCOL.md`: how Claude gives Dot tasks and accepts its work. `ops/RUNNER_WAKEUP.md`: the runner wake-up.
- `strategy/DECISIONS.md`: the decision protocol and the decisions in force.
- `strategy/MODELING_SPEC.md`: what each format must contain (with the rules it cites: `BEAT_THE_REFERENCE_RULE.md`,
  `FORMAT_OPINION_AND_CRITIQUE.md`, `FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md`).
- **`SYSTEM.md`: the master direction (owner, 2026-10-19): one loop of six stages, mining by structure (not by channel), few tools. Where anything here conflicts with it, SYSTEM.md wins. Structures are catalogued in `structures/`.**
- `STANDARD.md`: the production standard (measured on breakout videos with vidIQ). It overrides any visual, caption or CTA rule elsewhere.
- `strategy/VIDIQ.md`: the vidIQ research plan.
- `ops/ERRORS.json`: every error made, its fix and the automatic antidote that stops it coming back.

Everything else is evidence (`evidence/`, `receipts/`, registered forecasts) or instrument documentation
(`diagnostics/*/README.md`); it records what happened and directs nothing. The older plans and policies (integration
plan, operating policy, cutover status, monetization decision and plan, predictability contract, mining directives,
OAuth recovery, probe reviews) were deleted on 2026-10-18 so no one reads two versions of a rule; they remain in git
history. When something here changes, this file is edited in the same PR.

**Accounts (never switched):** channel HeroVerse @heroverse74 (`UCuMF6pJQkyMzaVoAxFL86yA`); repositories
`matheusmagah-cpu/heroverse-engine` (private) and `matheusmagah-cpu/heroverse-runner` (public). Credentials only in
GitHub secrets, never in files.

## Owner rules (Matheus, Brazilian: talk to him in Portuguese; the channel is English-only)

**Goal.** YouTube Partner Program (1,000 subscribers + 4,000 public long-form watch hours in 365 d, or 10 M Shorts
views in 90 d) in 14 days from 2026-10-18; 30 days at most.

**Who does what.**
- **Claude = direction** (the brain): strategy, decisions, specs, task order, gate rules, statistics, review, merges,
  scheduled tasks, reports to the owner. Claude does not loosen any rule to make something pass.
- **Dot = executor** of token-heavy work (full scripts, large code, long reading), only through `dot-task` issues and
  PRs (`ops/DOT_PROTOCOL.md`). Dot never merges, publishes, approves, edits frozen QA or touches secrets.
- **GitHub Actions** = the factory (images, renders, gates, publication, panel, mining). **The owner** decides money,
  accounts, permissions and anything outward that is not already authorised.

**Changes.** A change of strategy, format, packaging or cadence needs evidence of ≥ 90 % (one-sided p < 0.10, better
p < 0.01) of a clear effect toward the goal (`strategy/DECISIONS.md`). Defect fixes, policy compliance and conformance
to the registered strategy are always done. Nothing is removed to make the system worse; tools are added to improve.

**Errors.** Every error is fixed **and** gets an antidote in the same PR: an automatic check or test that fails if
the same error comes back, plus one line in `ops/ERRORS.json` (what happened, fix, antidote). PR checks fail a line
whose antidote does not exist (`ops/test_errors_register.py`). The same error twice is a defect of the antidote and is
fixed there. This applies to Claude's errors, Dot's and the pipeline's.

**Policy.** No borrowed identities or recordings, fear-bait, fabricated prophecy, reused content, health or wealth
promises. Original text; KJV Scripture quoted exactly. English only; Portuguese uploads stay hidden (reversible).

**Format (registered strategy).** Daily original prayer videos: morning ~25 min at 10:00 UTC, night ~28–33 min (prayer
+ Scripture for sleep) at 00:00 UTC; one Short per long video (D-03), cut from a QA-PASS render and reviewed. Its
slot (`schedule.json` `shorts_slots`, one entry): night pilot of day D at D 14:00 UTC, morning pilot of day D at D
20:00 UTC; `script_check.py` fails two pilots with the same Short slot (`SHORTS_SLOT_TAKEN`).

**Publication.** Only a final decision **PASS** (`publish/prepublish_gate.py` → `out/gate.json`) publishes: frozen QA,
preflight, whole-file scan, scorecard rows measured on our own file, watched review by the **designated model only**
(`gemini-3.8-flash`; a fallback model's answer is UNKNOWN). Missing or errored evidence = UNKNOWN = no publication,
retried. **Nobody writes `APPROVAL.json` by hand.** Frozen QA criteria are never edited after a render. After YouTube
confirms an upload the finished files are deleted from the release.

**Measurement.** Official numbers (Data API / Analytics API) are separated from own calculations and estimates; YPP
counters are estimated as YPP counts them (public long-form hours 365 d, public Shorts views 90 d).

## Budgets (owner rules)
- **Money:** zero. No paid API, plan or card. Paid video engines (Veo, Runway…) only after the
  channel earns.
- **Claude (owner's plan):** direction only; token-heavy writing goes to Dot. Claude runs in the main session
  (it has repository access; fresh routine sessions do not): an hourly clock (dispatch the heartbeat, review Dot's
  deliveries) and the daily analysis at 08:05 UTC. No polling loops, no full log dumps; extract only needed fields.
- **Dot:** heavy writing through `dot-task` issues; its own scheduled check of the issue queue at least every 2 h.
- **Repository visibility (owner decision 2026-10-19):** The repository is to be public and otherwise identical, so standard GitHub-hosted Actions minutes are free. Nothing is removed and history is not rewritten. Production workflows use `github.repository == 'matheusmagah-cpu/heroverse-engine' && github.ref == 'refs/heads/main'`. Secrets are never sent to pull requests from forks. Historical diagnostic workflows retain their private-only guard and do not run while the repository is public. The owner may return the repository to private when the channel earns revenue; the private Actions minutes budget then applies again. The owner changes visibility after Claude approves this PR.
- **GitHub Actions minutes of the private engine (owner decision 2026-10-19: everything stays private; the owner pays
  the overage):**
  - **Budget:** 7,000 min per 30 days (2,000 included + paid overage), about 233 min a day.
  - **Monitoring:** the daily report's "Actions minutes" section (`ops/minutes.py`) shows the last 24 h / 7 d / 30 d, the
    projection and the top consumers. It alerts at 1.5× the daily target and at a projection ≥ 90 % of the budget.
  - **Savings applied:**
    - the heartbeat runs at :41 plus the Claude clock at :14 (was 72 beats a day); its two jobs stay separate so the runner token never shares a job with GH_TOKEN;
    - no approval retry while the Gemini daily quota is known spent (it resets at 07:00 UTC);
    - heavy renders run on the public runner (free).
  - **Cutting order if the projection exceeds the budget:**
    1. structure mining weekly instead of daily;
    2. acquisition windows down to 12 a day;
    3. PR checks only on pilot and code paths.
    Production (approve, publish, Shorts) is never cut.
- **GitHub:**
  - Heavy renders run on the public `heroverse-runner` (owner decision, 2026-10-17). It has 4 cores and no minute cap.
  - The owner was told that GitHub's Actions terms restrict runners to work related to their own repository, and accepted the risk to the account.
  - Its logs are quiet (`PUBLIC_LOGS=1`): titles and script text go only to a private log in the release.
  - Fallback: the private `pilot-render-stills.yml` runs the same script. Keep each render within about 45 min where possible so the fallback fits the 2,000 private minutes.
  - The private repo handles the panel, publication and light jobs.
- **Cloudflare Workers AI (10k neurons/day, resets 00:00 UTC):** images only (FLUX + 2x upscale on GitHub).
- **RapidAPI free plan (500 units/day, 14 per native window, floor 100 → ≤ 28 windows a day):** native reference windows for mining — 12 a day for the accuracy holdout, the rest for native measurement.
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
fresh routine sessions get GitHub 403), dispatches `heartbeat.yml` every hour at :14. Since engine PR #106
(Dot) the heartbeat's own `runner-wake` job wakes the runner (`HERO_RUNNER_PAT`, active-run guard, cooldown,
per-hash attempt bound, `migration/ops/RUNNER_WAKEUP.md`), so the clock no longer dispatches `render.yml` itself.
First real `runner-wake` run 2026-10-18 13:11 UTC: success, QUEUE_EMPTY (nothing due); first real dispatch pending.
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

**Quota claims need the provider's own words (E29).** A quota is called "spent for the day" only when the recorded `quota_ids` say PerDay; any other 429 is retried after 30 min, and nobody (Claude included) tells the owner otherwise.

**The engine never stops (content runway).** Every day has two publication slots (night 00:00, morning 10:00 UTC).
Claude keeps scripts **4 days ahead**: at each daily analysis (08:05) Claude opens the Dot cards for the two slots of
day D+4 (topic from the decisions protocol + vidIQ), so Dot's cycle, images, render and gate always fit. The daily
report's **Content runway** (`ops/runway.py`) lists every slot of the next 4 days with its stage and alerts when a slot
has no script < 72 h before, no render < 36 h before, or no gate PASS < 24 h before (owner 2026-10-19: approve one
full day ahead, so a provider error or a FAIL has a day to be fixed; quality is never traded for time). An alert is handled the same day. Scheduled workflows of the public runner stop after 60 days without a commit there.

## External tools
- **vidIQ** (connected 2026-10-18, account linked to HeroVerse): research only — demand, rising topics, outliers
  (comparables), audience comments, title scores, competitor curves, reference transcripts. 30-day plan with caps
  ≤ 10 research calls a day and ≤ 2,000 credits per cycle (`strategy/VIDIQ.md`, ledger `evidence/vidiq/ledger.json`).
  Informative until validated (first validation FAIL, ρ 0.40). Its opinion travels in `gate.json` as
  `market_evidence_not_deciding`. Write tools are denied in `.claude/settings.json`.

## How publication starts (automatic)
1. A render pushes `out/qa.json` → `approve.yml`: QA, preflight, scorecard, watched review, whole-file scan →
   `out/gate.json`. Only PASS writes `inspection/APPROVAL.json` (bound to the file hash) and dispatches `publish.yml`.
2. `publish.yml` re-checks the gate for that hash, uploads private + `publishAt` from `schedule.json`, captions,
   thumbnail, playlist, receipt and ledger; then deletes the finished file from the release.
3. `publish-shorts.yml` uploads the approved Short of a published long video at its slot (ledger, no duplicates).
4. ERROR/UNKNOWN (quota, fallback reviewer, missing evidence) is retried by `reconcile.yml`; FAIL stops and is reported.

## Starting any workflow without GitHub API tools
Commit `migration/requests/<name>.json` with `{"workflow": "file.yml", "inputs": {...}}` to main, through a branch and merge. `requests.yml` dispatches it once and moves the file to `done/`.

Example: `{"workflow": "pilot-render-stills.yml", "inputs": {"pilot": "pilot-003"}}`.

## Mining: native-first (owner rule 2026-10-19: mining is a strong point, never a weak one)
- **Weak point found (2026-10-19 audit):**
  - The structure miner is a free Gemini model watching the video and reporting what it heard.
  - On 12 native test windows: 4 were invalid (times outside the window, incomplete transcript); one valid-looking window agreed 11 % with the real audio; the pass rate was 50 % against an 80 % criterion.
  - Its accuracy was never proven on independent (holdout) windows.
  - The prayer sample had 2 usable winners.
  - So every modeling number derived from it is informative only.
- **Rule from now:**
  - **Numbers:** every modeling number comes from **measurement of the original audio**: our faster-whisper ASR, YAMNet sound classes and the picture-change meter on natively acquired 60 s windows (`mining/native_metrics.py`).
  - **Validation per video:** a mined video counts only when its own native windows agree ≥ 0.85 with the mined transcript.
  - **Targets:** a format's numbers become targets only with ≥ 8 validated winners (90 % bootstrap intervals). Otherwise they are INSUFFICIENT and shown, never used.
  - **What Gemini keeps:** labelling structure on validated transcripts.
- **First holdout verdict, 2026-10-19 00:44 UTC: FAIL.**
  - 12 independent native windows, all compared: median agreement 0.909; window pass rate 0.75 against the 0.80 criterion.
  - Two windows were invented text (agreement 0.075 and 0.226) and one fell short at 0.838.
  - Evidence: `evidence/structure-mining/20261018/accuracy.json`.
  - Consequence: the Gemini miner stays informative and never decides. Numbers come only from the native instrument once it is qualified (#140).
- **Proof:** the miner's holdout check (criteria fixed 2026-10-18: agreement ≥ 0.85, openings ≥ 0.80, window pass rate ≥ 0.80) runs every night. Only PASS lets miner rows decide in the gate.
- **Sample:** ≥ 10 prayer winners from ≥ 4 policy-clean channels, plus median and weak videos of the same channels, chosen with vidIQ outliers and the panel.
- **Work:** Dot card #136 (native_metrics + native_plan, tested). Claude wires the nightly measurement windows into the heartbeat and recomputes MODELING_SPEC from MEASURED numbers only.

## Qualify before use (owner rule 2026-10-19)
An instrument is a strong point **before** it is used, proven on known answers with criteria frozen before any result
(SHA-256 asserted in the tests). If it fails, it is fixed and qualified again; it is never used while failing.
- **Mining:** the native instrument (ASR + YAMNet + picture meter) and Gemini labelling, run on our own renders, whose
  every word, timing, Scripture and picture change is known (incl. degraded copies) — card #140, workflow
  `mining-qualification.yml`.
- **Authenticity and originality:** a detector against our pilots and the mined competitor transcripts and titles
  (verbatim, close paraphrase, title near-copies; Scripture never counts), qualified on a labelled holdout corpus and
  enforced in `script_check.py` — card #141.
- **Modeling:** exact numbers, honest 90 % intervals (simulated coverage 85–95 %) and every acceptance rule proven to
  accept good scripts and reject each bad mutation — card #142 (after #136).
Claude reviews each delivery against its card; a stage is called a strong point only with its qualification PASS on file.

## Pipeline gates (never edited after results)
1. **Script acceptance** (before images): `production/script_check.py` — PR checks run it on every pilot a PR touches.
2. **Render QA (frozen criteria v2).**
3. **Final decision** `prepublish_gate.py`: PASS / FAIL / UNKNOWN per dimension (binding, technical, audio, transcript,
   captions, sync, image, rights, content/policy, scorecard, whole-file scan, preflight).
4. **Shorts:** `shorts_qa` + watched review by the designated model (items ≥ 7, overall ≥ 8), from QA-PASS renders only.

## Status (2026-10-18 17:20 UTC) — day 1 of the plan

**Publication calendar (UTC; one Short per long video, D-03):**

| Day | Long video | Short | State |
|---|---|---|---|
| 10-18 | pilot-002 10:00 ✅ `v4zN53ZiUIs` | 14:00 ✅ `_sUdOLxWy5c` | published |
| 10-19 | pilot-003 10:00 | 14:00 | render, QA, scan, preflight PASS; Short approved (gemini-3.8-flash). Watched review waits for the Gemini reset 07:00 → approve → upload before 10:00 |
| 10-20 | pilot-004 00:00 · pilot-005 10:00 | 14:00 · 20:00 | 004 as 003 (Short approved); 005 images after 00:00 UTC, then render |
| 10-21 | pilot-006 00:00 · pilot-007 10:00 | 14:00 · 20:00 | scripts on main; images and render in the nights before |
| 10-22 | pilot-008 00:00 · pilot-009 10:00 | 14:00 · 20:00 | 008: Dot finishing PR #117 (card #114 SPEC v2, due 10-19 06:00); 009: card #119 waits TOPIC CONFIRMED |
| 10-23 | pilot-010 00:00 · (D+4 card) | 14:00 · 20:00 | 010: card #120 waits TOPIC CONFIRMED; next cards opened at each daily analysis |

**Dot:** contract `ops/DOT_PROTOCOL.md` (8-part cards, ALLOWED PATHS enforced by PR checks). Open: #114 (SPEC v2),
#119, #120. Dot's own 2-hour polling is not yet confirmed; a card not delivered shows up as a Content runway alert.

**Today's changes (all PR checks green):** #121 superseded documents deleted · #122 one Short slot per pilot ·
#123 late Shorts never take another pilot's slot; more tests in PR checks · #124 Claude–Dot contract with scope check
· #125 error register with enforced antidotes (`ops/ERRORS.json`) · #126 content runway in the daily report.

**Scheduler:** heartbeat (GitHub crons unreliable: dropped again 14:41) + runner-wake (Dot, PR #106) + hourly Claude
clock at :14 (dispatching the heartbeat every hour since 12:14).

**Checkpoints:** 02:15 first real runner-wake dispatch (pilot-005) · 06:00 Dot deadline #114 · 07:25 approval of
pilot-003 (deadline 10:00) and 004 · 08:05 daily analysis (TOPIC CONFIRMED for #119/#120, cards for D+4).

**Not yet proven:** gate PASS on a real render; runner-wake real dispatch; Short reviewed by the designated model and
published by the pipeline; review calibration; mining holdout; vidIQ title score vs CTR.

**Indicators (official 2026-10-18):** 263 subscribers; public long-form watch hours 365 d ≈ 3.3 (own calc.); public
Shorts views 90 d ≈ 40.

**Decisions active:** D-01/D-04 lengths (conformance), D-02 fear-bait hidden (compliance), D-03 one Short per long
video (p = 0.062, observational). D-05 subscribe ask reverted.
