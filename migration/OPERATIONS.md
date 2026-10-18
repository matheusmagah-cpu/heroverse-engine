# HeroVerse operations — the single source of truth (rewritten 2026-10-18)

Read this file first. **It wins over every other document.** The only documents that direct the work are:
- `OPERATIONS.md` (this file): rules, roles, budgets, schedule, pipeline, status.
- `ops/DOT_PROTOCOL.md`: how Claude gives Dot tasks and accepts its work. `ops/RUNNER_WAKEUP.md`: the runner wake-up.
- `strategy/DECISIONS.md`: the decision protocol and the decisions in force.
- `strategy/MODELING_SPEC.md`: what each format must contain (with the rules it cites: `BEAT_THE_REFERENCE_RULE.md`,
  `FORMAT_OPINION_AND_CRITIQUE.md`, `FORMAT_ARCHETYPE_MORNING_PRAYER_DIRECT_ADDRESS.md`).
- `strategy/VIDIQ.md`: the vidIQ research plan.

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

Claude's part: write the next scripts (2 per day: morning + night prayer) with schedule.json and images.json, at least 2 days ahead, and read the daily report. Scheduled workflows of the public runner stop after 60 days without a commit there.

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

## Pipeline gates (never edited after results)
1. **Script acceptance** (before images): `production/script_check.py` — PR checks run it on every pilot a PR touches.
2. **Render QA (frozen criteria v2).**
3. **Final decision** `prepublish_gate.py`: PASS / FAIL / UNKNOWN per dimension (binding, technical, audio, transcript,
   captions, sync, image, rights, content/policy, scorecard, whole-file scan, preflight).
4. **Shorts:** `shorts_qa` + watched review by the designated model (items ≥ 7, overall ≥ 8), from QA-PASS renders only.

## Status (2026-10-18 14:30 UTC)
- **Published:** pilot-002 `v4zN53ZiUIs` (public 2026-10-18 10:00 UTC, owner-approved before the gate existed);
  its Short `_sUdOLxWy5c` public 14:00 UTC.
- **Queue:** pilot-003 morning 10-19 10:00 (render PASS QA; gate UNKNOWN until the designated reviewer, retried
  after the Gemini reset 07:00) · pilot-004 night 10-20 00:00 (re-render QA PASS; gate pending, same) · pilot-005
  morning Psalm 91 10-20 10:00 (images after 00:00 UTC, then render) · pilot-006 night healing 10-21 00:00 (images
  after 00:00) · pilot-007 morning 10-21 10:00 (written by Dot, merged, no new images) · pilot-008 night Psalm 23
  10-22 00:00 (Dot, PR #117 in progress).
- **Scheduler:** heartbeat + runner-wake (Dot, PR #106) + hourly Claude clock; GitHub crons unreliable. First real
  runner dispatch expected tonight (pilot-005).
- **Proofs pending:** first gate PASS on a real render; first runner-wake dispatch; Shorts with the designated
  reviewer; review calibration; mining holdout; vidIQ title-score vs CTR.
- **Indicators (official 2026-10-18):** 263 subscribers; public long-form watch hours 365 d ≈ 3.3 (own calc.);
  public Shorts views 90 d ≈ 40.
- **Decisions active:** D-01/D-04 lengths (conformance), D-02 fear-bait hidden (compliance), D-03 one Short per
  long video (p = 0.062, observational). D-05 subscribe ask reverted.
