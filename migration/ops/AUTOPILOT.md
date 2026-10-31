# HeroVerse autopilot: a free way for the project to run without a live Claude session

Status: DESIGN (docs only, 2026-10-31). Nothing here is built, dispatched or enabled; no workflow was run and
`claude/shared-executor-control` was not touched. Owner decision (31/10): **Claude Code is the only coordinator**;
Codex/ChatGPT has no role on production. The autopilot workflows are the primary runner; Claude clocks/sessions are
optional supervisors and the escalation path. The lease stays only as a mutual-exclusion guard between the autopilot
and a Claude session.
Owner request (31/10): a FREE way for the project to move without this conversation, that really works and cannot fail.
Trigger: on 28/10 the Claude weekly limit stopped everything for 3 days.

Hard rules that bind every item below: no gate loosened (frozen QA v2/v3/v4/story v1..v5 and `pilot-NNN/qa_criteria.json`
untouched); zero new spending; `APPROVAL.json` only from `approve.yml` -> `prepublish_gate.py`; secrets only in
repository secrets; every change by `claude/*` branch, PR, squash; every failure gets `ERRORS.json` + antidote test.
Cadence fixed by the owner: 2 Shorts a day and one long every other day, each only at overall >= 9.5.

## 0. What the repository showed (facts, not intentions)

- Mechanical stages already run in Actions: `heartbeat.yml` (cron `41 * * * *`, dispatches by slot from run history,
  `ops/heartbeat.py`), `requests.yml` (commit `migration/requests/<name>.json` -> dispatch), `footage.yml`,
  `scene-stills.yml` (FLUX), `shot-probe.yml` (Pavo), `episode.yml`, `long-build.yml`, `native-review.yml`,
  `approve.yml`, `publish-episode.yml`, `publish.yml`, `reconcile.yml`, `tiktok.yml`, `arc-links.yml`,
  `comment-replies.yml` (6 a day; posts up to 4 replies Claude decided, queues new comments for Claude).
- The heartbeat is the only cron of the daily plan. Its watchdog is a **Claude** scheduled task (light clock :14,
  main clock every 4 h, per `evidence/audits/20261028-slim.md`). So the watchdog itself dies with the Claude limit.
  The headings "Shared Claude Code / ChatGPT execution" and "Clocks" cited in the request do not exist in the current
  `OPERATIONS.md` (only "Shared executor control"; "Clocks" survives only as references in comments). Fix in PR A-docs.
- Judgement is Claude-only in these places: plan authoring, source/still/clip approval (`approve-shot` writes a
  reviewer id), thumbnail approval, comment replies, PR creation and merge, and the final review of a Short (the
  Short09 route is already `native-review.yml` with `gemini-3.8-flash`, owner-authorized, but its dispatch, key
  proof, retry and consumption into the episode record are done by a session).
- `production/bible/reviewer_identity.py` accepts only `LONG_REVIEWERS` (`claude-session-reviewer`,
  `gpt-6-astra-session-reviewer`) for source, still and thumbnail approvals; `SHORTS_REVIEWER = gemini-3.8-flash` exists
  in `publish/owner_quality_policy.py` for Shorts only. A Gemini approval of a source is therefore **refused today**.
- Gemini as reviewer is NOT yet calibrated for strictness. `evidence/reviewer-calibration/` (same 6 published pilots,
  designated `gemini-3.8-flash` scores 8.0-9.3): `gemini-2.5-flash` scored 9.0-10 (lenient: would rubber-stamp),
  `gemini-3.5-flash` 6.3-7.1 and `gemini-3.6-flash` 6.0-7.0 (harsh, flags `figure_and_background_integrity` 5.0-5.2),
  `gemini-3-flash-preview` 6.0-6.8 plus 503s. `reviewer-probe` (24/10): `gemini-omni-*` 429, two models timed out at
  60 s, `gemini-3.8-flash` took 22.9 s for a trivial call. Model choice and variance are the main unmeasured risk.
- Gemini image *generation* is 0 on this key (`evidence/gemini-image/20261028-free-tier.json`). Image *understanding*
  with `gemini-3.8-flash` was never measured; this plan does not assume it (see 2.3).

## 1. Free tier limits, from Google's docs (read 2026-10-31)

| Item | Value | Source page |
|---|---|---|
| Free-tier text/multimodal input and output, no charge | Gemini 3.8 Flash, 3.6 Flash, 3 Flash Preview, 3.5 Flash-Lite, 3.1 Flash-Lite, 2.5 Pro, 2.5 Flash, 2.5 Flash-Lite (and TTS/Live/Transcribe/embedding models) | `/docs/pricing` |
| Not available on free tier (input and output) | Gemini 4 Argon, 3.1 Pro Preview, Omni Flash, every image-output model (3 Pro Image, 3.1 Flash Image, 3.1 Flash Lite Image, 2.5 Flash Image) | `/docs/pricing` |
| Numeric RPM / TPM / RPD per model | **Not published in the docs.** The page says "view your active rate limits in AI Studio". Scope: per project, not per key. RPD resets at midnight Pacific. Preview/experimental models are more restricted. Free-tier spend limit N/A | `/docs/rate-limits` (updated 2026-10-28) |
| Video understanding | Default 1 fps; low media resolution ~100 tokens/s (66 tokens per frame + 32 tokens/s audio), high ~300 tokens/s; 1M-context models: up to ~3 h at low resolution, ~1 h at high | `/docs/video-understanding` |
| Files API | 2 GB per file (free tier too), 20 GB per project, files auto-deleted after 48 h, no charge | `/docs/files`, `/docs/video-understanding` |
| Inline video | Page contradicts itself (under 20 MB total request vs under 100 MB): always use the Files API | `/docs/video-understanding` |

Consequences. (a) The binding numbers (RPM/TPM/RPD) can only be read from AI Studio or measured; design for them as
unknowns and keep a ledger (2.7). The existing `native_review.py` already demands a fresh key-bound free-tier proof
(`free_tier_evidence` with the SHA-256 of the key); reuse it, never bypass it. (b) A Short at the native review's 4 fps
costs about 296 tokens/s at 66 tokens/frame -> ~18k tokens for 60 s; a 10 min long ~178k tokens, fits one context but may
hit a tokens-per-minute cap: chunk by act and merge. These are arithmetic from the doc figures, not measurements.

### 1.1 Numeric free-tier limits read from AI Studio (owner's screen, 2026-10-31)

Source: the owner's AI Studio rate-limit page, project "Default Gemini Project", tier "Nível gratuito" (Free), billing
not configured; that project's 28-day usage showed 0. The repository's `GEMINI_API_KEY` had real usage on 10-30/31, so
the key may belong to a different project: these numbers bind that key only after its own project is read back or its
behaviour (free-tier quota errors) is observed. Do not assume.

| Model | RPM | TPM | RPD |
|---|---|---|---|
| gemini-3.8-flash (native review) | 5 | 250K | 20 |
| gemini-3.6-flash, gemini-3-flash, gemini-2.5-flash (each) | 5 | 250K | 20 |
| gemini-3.5-flash-lite, gemini-3.1-flash-lite (each) | 15 | 250K | 500 |
| 2.5 Pro, 3.1 Pro, 4 Argon, every image-output model | 0 | 0 | 0 (not available) |

RPD resets at midnight Pacific. Consequence: at the default media resolution (~290 tokens/s) a ~14.5 min long is ~250K
tokens, at or over the 250K TPM; review a long at low media resolution or in chunks under 250K tokens, at most 5
requests per minute and 20 per day on gemini-3.8-flash. A Short (175 s at 4 fps, ~52K tokens) fits one request.

### 1.2 A1-0 verification (2026-10-31, `evidence/autopilot/a1-0-verification.json`)
Repository public (standard runner minutes free); `main` has no branch protection and no rulesets, so nothing on
GitHub enforces `pr-checks` before a merge (A1-6 must check the exact head itself). The job token cannot read the
Actions settings (403): "Actions may create/approve PRs" stays an owner readback. The repository key answered text,
image input and a YouTube-URI video on `gemini-3.8-flash` (200, model identity returned); a URI without
`videoMetadata` is sampled at ~1 fps, so reviews set 4 fps explicitly; one multimodal call took 100-178 s.
Three 200s do not prove the free tier for this key's project: the 1.1 numbers remain to be read for that project.

## 2. Components and shared rules

### 2.1 Autopilot controller = one scheduled "tick" workflow (`autopilot.yml`, later)
A stateless tick reads `migration/ops/autopilot_state.json` (one current delivery, one next episode, step, attempt
counts, saved IDs), the lease, quotas and run history; decides ONE next action; performs it or no-ops. It extends the
heartbeat's decide-from-history pattern (`ops/heartbeat.py::decide`), not a new scheduler. Idempotent by saved IDs
(existing rule: never replay an uncertain POST; reconcile by GET).

### 2.2 Lease
Purpose: only to stop the autopilot and a live Claude session from writing the same delivery at once. The schema allows
`codex`/`claude` today (`private_audio.py`, `native_review_recovery.py`). Simplest: the autopilot holds it as owner
`claude` with `task: autopilot` and `run_id` = the Actions run id (no code change; `codex` simply goes unused).
Alternative: add an `autopilot` owner (code and tests in both readers). Compare-and-swap exactly per
`OPERATIONS.md` (parent = observed head, unchanged tree, expiry <= 55 min, force=false, read back, renew <= 10 min,
release idle at a safe boundary). Behaviour: lease held by an unexpired Claude session -> the tick is read-only and exits
`LEASE_BUSY` (no effects); expired -> reconcile saved IDs first, then take it. Release is in an `if: always()` step; a
crashed run self-heals by expiry (<= 55 min).

### 2.3 Gemini as the free reviewer (owner-named)
Use cases and what is proven:
| Use | Input | Model | Status |
|---|---|---|---|
| Plan drafting, query derivation, comment replies | text | `gemini-3.8-flash` (fallback `gemini-3.5-flash-lite`) | text works (probe 200) |
| Clip/footage review | the mp4 via Files API (video+audio) | `gemini-3.8-flash` | same route as `native-review.yml`; per-clip use unmeasured |
| Still review | contact sheet / PNG as image input | `gemini-3.8-flash` | image input works (A1-0, run 41235834541: 20-frame sheet read correctly, 178 s); judgement not calibrated |
| Final Short/long review | full master, native audio, 4 fps | `gemini-3.8-flash` | authorized for Short09; long not yet allowed (identity list) |
Rules: schema-validated JSON (the existing `validate_report` shape), timestamps and heard excerpts must be grounded in
the media; no repair-by-guess; below 9.5 or any item < 7 or ungrounded -> not PASS; the model id recorded is the one
the API returned. One model fixed per rubric (no model shopping until one passes 9.5: that is the "resubmit to seek a
higher score" the rules forbid). **Calibration gate before any autonomy**: replay the reviewer on the already-reviewed
corpus (6 pilots plus Short08, which has a Claude session review) and require that it fails the known-bad items and does not
differ from the human ground truth by more than the owner accepts; record in `evidence/reviewer-calibration/`. If
calibration fails, Gemini stays a *pre-filter* (can reject, never accept) and acceptance stays with Claude.
Identity: needs an explicit PR extending the approval allowlist with `gemini-3.8-flash` for sources/stills/thumbnails
(and a separate owner decision for longs). It is not a loosening of QA criteria, but it changes who may approve, so the
owner confirms it in `DECISIONS.md` first.

### 2.4 Merge by workflow, never by hand-written approval
`autopilot-merge.yml` merges an autopilot PR only if a pure, tested function returns MERGE: PR head only touches
allow-listed paths (plans, source approvals, episode record, requests; never `.github/`, frozen QA, `publish/`, ERRORS,
code); `pr-checks` green on the exact head; reviewer evidence bound to the same hashes; lease held; no `needs-human`
label. Code PRs (engine changes) are never auto-merged. GitHub limitations to verify first (A1-0, read-only): PRs and
pushes made with `GITHUB_TOKEN` do not trigger `pull_request` workflows, so required checks would never start; options
are a fine-grained PAT in a repository secret (owner action, same pattern as `HERO_RUNNER_PAT`), or running the same
test list inside the autopilot job and merging with `gh pr merge --squash` under repo settings that allow it. Also check
whether branch protection exists at all (`requests.yml`/heartbeat already push claims to `main`).

### 2.5 Clock: no single point of failure, no Claude
Layers, all free, any one sufficient to keep going:
1. L1 `heartbeat.yml` cron `41 * * * *` (exists). Add a tick call at its end.
2. L2 self-chaining: the tick, when work is still due, dispatches the next heartbeat/tick itself
   (`actions: write`, `workflow_dispatch` is allowed for `GITHUB_TOKEN`) using `if: always()`, with a minimum spacing;
   plus long jobs (`episode.yml`, `long-build.yml`) end by dispatching the tick. A chain only breaks if every run fails.
3. L3 second repository clock: `heroverse-runner` already has cron `13,43`; add a step that dispatches the engine
   heartbeat when its last beat is >55 min old (the watchdog logic now done by Claude, moved to an Action). Needs a
   fine-grained PAT (Actions read/write on the engine only) stored as a secret in the runner repository: owner action.
4. L4 external pinger on a free account the owner already has: a Cloudflare Worker Cron Trigger (free plan; the
   Cloudflare account exists for FLUX) calling `workflow_dispatch` every 15 min. It needs that same narrow PAT stored
   as a Worker secret: the secret leaves GitHub, so this is an explicit owner decision, not assumed. Third-party
   cron sites are rejected for the same reason.
5. Staleness alarm without Claude: a tick that sees beat age >2 h opens/updates a single GitHub Issue (owner gets the
   GitHub email) and writes the daily report with `STALLED`.
Also: scheduled workflows are disabled after 60 days without repository activity; the autopilot's own commits count.
Residual: GitHub can drop crons (17-18/10 all daily crons dropped); L2-L4 reduce, not eliminate, this.

### 2.6 Fallback ladder (order, never skipping a gate)
quota/provider out -> wait + retry next tick (bounded) -> alternate free route for the same step -> park the delivery
`BLOCKED:<reason>` with a Issue for the owner and a Claude-visible note in `autopilot_state.json`. Never lower 9.5,
never publish unreviewed, never spend.

### 2.7 Budget ledger
`evidence/autopilot/budget.json`: per UTC/Pacific day, Gemini calls by model, status codes, tokens when returned, and the
last AI Studio readback; Pavo credits from the existing ledgers; vidIQ ledger untouched (<=200/day rule). The tick
refuses a call that would exceed 80% of the last measured limit and records the refusal.

## 3. Inventory: every step from plan to publish

Legend: Today = who performs it now (A = Action, C = Claude session, O = owner). Cost = money /
scarce resource. "Free replacement" is what the autopilot does; Claude remains the escalation.

### 3.1 Bible Short
| # | Step | Today | Cost | Free autonomous replacement | Needs |
|---|---|---|---|---|---|
| S1 | Choose next story (arcs.json, SERIES.md order) | C | Claude tokens | deterministic: next unplanned part of the arc; reserve rule from SERIES.md | code |
| S2 | Write `bible-plan-v2` (KJV text, narration, shots, timing) | C | Claude tokens (largest text step) | Gemini text drafts from a template + the previous plan; `kjv_check`, `plan_check --strict`, `script_check` (8-word shingle <5%, last-10 <15%) run in the job; failing finding fed back, max 3 attempts | PR A1-4 |
| S3 | Open plan PR, checks, squash | C | Claude tokens | workflow opens PR; 2.4 merge rule | repo settings |
| S4 | Preflight (`episode_build.py preflight`, `verify-preflight`) | A (dispatched by C/heartbeat) | free | tick dispatches via `requests` | none |
| S5 | Pick source queries/prompts per shot | C | Claude tokens | derive from shot spec deterministically; Gemini text only to rephrase after a rejection | A1-5 |
| S6 | Get candidates: footage (`footage.yml`: Pexels/Pixabay/Commons), FLUX stills (`scene-stills.yml`, Workers AI free allocation), Pavo (`shot-probe.yml`, quote must be exactly zero) | A | free (Pavo capped by quote/quota) | same Actions, started by the tick | none |
| S7 | Clip checks (`clip_check`, lipsync/syncnet, ASR of Pavo speech) | A | free | unchanged deterministic gates; their FAIL is final | none |
| S8 | Review each source >= 9.5 (frames, motion, identity, context) | C | **Claude tokens, the heaviest** | Gemini video/image reviewer (2.3) after calibration, on top of S7 | A1-2 |
| S9 | Write source approval (`approve-shot`/`approve` with `--reviewer`) and PR/merge | C | Claude tokens | workflow runs the same writer with the model id Gemini returned; 2.4 merge | owner decision on identity |
| S10 | Build (`episode.yml` -> `short_engine`) | A | free | tick dispatch | none |
| S11 | Thumbnail (`thumbs.py` check/refs/finalize/approve; part >= 9) | A + C approval | Claude tokens | FLUX + Gemini review of the PNG (image input unmeasured) | A1-2 |
| S12 | Final audiovisual review >= 9.5 | C or `native-review.yml` (session-run) | tokens or free Gemini | `native-review.yml` dispatched by tick; key proof, single transient retry per CURRENT; consume result | A1-8 |
| S13 | Episode record + `check-record` | C | Claude tokens | script writes it only from the real review artifact | A1-8 |
| S14 | Publish (`publish-episode.yml`) and readback public+processed | A (dispatched by C) | free | tick dispatches after S13; reconcile by video ID | none |
| S15 | Mirror and links (`tiktok.yml`, `arc-links.yml`, `reconcile.yml`) | A (heartbeat) | free | unchanged | none |
| S16 | Lease take/renew/release | C by hand | tokens | `autopilot_lease.py` (2.2) | A1-3 |

### 3.2 Story long (every other day)
| # | Step | Today | Cost | Free autonomous replacement |
|---|---|---|---|---|
| L1 | `long_plan_check --strict`, long preflight | A/C | free / tokens | unchanged; plan drafted by Gemini text like S2 with LONG_DESIGN.md as the template |
| L2 | Sources for ~10 min of footage/stills/Pavo (many shots) | A + C review | **very heavy Claude** | same as S6-S9 in batches per act, budgeted |
| L3 | `pilot-preview.yml` / `preview_gate.py` (heartbeat dispatches) | A + C review | free + tokens | Gemini preview review, deterministic gate unchanged |
| L4 | `long-build.yml` (Real-ESRGAN 1440p, up to 240 min jobs) | A | free (runner minutes) | tick dispatch, resume by saved IDs |
| L5 | Long review (`inspection/claude_review.json`), `claude-session-reviewer` (the allowlist's historical GPT id is unused now) | C | Claude tokens | Gemini native review at 4 fps per act + merge. **Blocked by policy**: needs the owner to add a Gemini identity to `LONG_REVIEWERS`, or Claude stays the long's acceptor |
| L6 | `approve.yml` -> `prepublish_gate.py` -> `publish.yml` | A | free | unchanged; the only path to `APPROVAL.json` |

### 3.3 Cross-cutting
| # | Step | Today | Cost | Replacement |
|---|---|---|---|---|
| X1 | Watchdog of heartbeat | C light clock | Claude tokens | 2.5 layers L2-L5 |
| X2 | Comments: triage, decide replies | C (writes `comment_replies.json` via PR) | Claude tokens | Gemini text decides, deterministic policy filter (no promises, no theology claims beyond KJV text, no links, no off-topic bait; ledger prevents repeats); anything doubtful goes to `needs-human`; existing 20/day cap stays |
| X3 | Daily report and learning (`goal-report.yml`, `live_intel.py`) | A + C reading | tokens | report job writes `evidence/daily-report/<date>.md` plus a short status Issue |
| X4 | vidIQ research | C (ledger <=200/day) | vidIQ credits | optional; autopilot does not depend on it |
| X5 | Code fixes, ERRORS entries, PRs | C | tokens | not automated; the autopilot only files an Issue with the failing run and the proposed class |

## 4. Failure modes, fallbacks, antidotes (each antidote is a test that runs on every PR)
| Failure | Detection | Fallback | Antidote test (to add) |
|---|---|---|---|
| Gemini quota out (429, RESOURCE_EXHAUSTED, ledger at 80%) | HTTP 429 / ledger | stop Gemini calls for the day, keep deterministic work, resume after midnight PT; delivery parked, cadence re-anchored to actual qualifications (existing policy) | `test_autopilot_budget`: no call past the limit; 429 never counts as a score |
| Gemini returns 503/timeout/unparseable | status | single bounded retry on the same input and model (existing `retry_transient_once` rule), then park | `test_gemini_review`: an error, partial output or schema failure is never PASS |
| Review below 9.5 or item <7 or ungrounded | validator | route the named defect to the responsible stage (regenerate that shot only); max 3 attempts per shot, then try the next candidate source; after the bound, park `needs-human`. Never resubmit unchanged media | `test_review_loop`: same hash never reviewed twice for a better score; scores not copied across hashes |
| Gemini lenient/inconsistent | calibration corpus replay | demote to pre-filter | `test_reviewer_calibration`: known-bad pilots must fail |
| No footage for a shot | empty result of `footage.yml` | broaden query within the shot's meaning, FLUX still with motion (true provenance), then Pavo if quote is zero, else park the shot's Short | `test_autopilot_sources`: provenance label never altered |
| Pavo down / quote not zero / claim unresolved | `pavo_status`, quote | Plan B voiceover Keeper with matching footage, or free footage for non-spoken shots (story QA v5); never submit without a fresh zero quote; reconcile saved conversation IDs | extend existing Pavo tests: autopilot never POSTs on an unresolved claim |
| Actions cron dropped | beat age > 55 min | 2.5 layers L2-L4; Issue alarm at 2 h | `test_clock_layers`: staleness decision pure function; chain step has `if: always()`; no secret in inputs/logs |
| Lease held by a Claude session | lease read | read-only tick; never force | `test_autopilot_lease`: sibling CAS fails; busy lease means zero effects; expired lease reconciles first; release on failure |
| Lease holder crashes | expiry | next tick reacquires after <=55 min and reconciles IDs | same test, crash case |
| Concurrent tick + session writing the same files | concurrency group + lease | second writer aborts | `test_autopilot_state`: write requires holding lease |
| Double publish | publish ledger / video ID | publishers already idempotent; tick reconciles by ID | existing publish tests + tick never dispatches publish twice per episode |
| Autopilot PR cannot merge (checks never start under `GITHUB_TOKEN`) | PR stays pending > N min | PAT route or in-job tests; else park | `test_merge_decision`: only allow-listed paths, exact head |
| Secret leakage | scan | n/a | existing hookify + `test_autopilot_no_secret_in_logs` |
| Runner minutes exhausted | `ops/minutes.py` | pause heavy jobs (long build), keep Shorts | existing `test_minutes`, plus tick respects it |
| Owner rule violated by prompt injection in fetched text (footage metadata, comments) | n/a | model outputs only fill data fields; never choose workflow, path or gate | `test_autopilot_untrusted_text` |

## 5. What cannot be guaranteed (plain)
- "Cannot fail" is not achievable on GitHub's free platform: crons can be delayed or dropped, runners can be
  unavailable, providers (Pavo, Gemini, YouTube, Pexels/Pixabay) can be down or change terms. The design makes failures
  *safe and visible* (park, alarm, resume) rather than impossible.
- The Gemini free quota is unknown until read from AI Studio; it is per project and shared with `native-review` and any
  other use. 2 Shorts + 1 long per 2 days at the review depth in 2.3 may exceed it. If so, cadence drops instead of quality.
- Gemini may not reach Claude's judgement. Calibration (2.3) can fail; then the autopilot only pre-filters and some
  delivery steps still wait for Claude (so a weekly-limit stall like 28/10 can recur for those steps). This is the largest residual risk to "no session needed".
- 4 fps sampling does not see everything (disclosed, as for Short09). Images as reviewer input are unmeasured.
- A model that approves wrongly publishes a wrong video; the deterministic gates, frozen QA, originality shingle checks,
  policy checks and revocation lists limit but do not remove this. A kill switch (`autopilot_state.json: paused=true`
  plus repository variable) lets the owner stop it; unpublishing remains an owner action.
- Policy/identity changes (Gemini as source/long approver, PAT placement, Cloudflare Worker secret) are owner decisions.
- Actions minutes: `SYSTEM.md` says standard runners are free for public repositories while `RUNNER_WAKEUP.md` calls the
  engine "private"; verify the actual repository visibility and the free-minute allowance before relying on 24/7 ticks.
- Hosting/credentials expire (YouTube token, Pavo token, PATs with 1-year expiry): the tick checks and alarms, it cannot renew.

## 6. Phased build plan
Order matters; each PR is `claude/*`, squash, `ERRORS.json` entry if a failure is found, tests added to `pr-checks.yml`.
No PR below is merged or dispatched while a Claude session holds the lease for the same files; A-docs and tests-only PRs
carry no production effect.

### Phase 1: Shorts autopilot (target: a Short from plan to public with no session)
| PR | Content | Tests | Antidotes |
|---|---|---|---|
| A-docs (this) | AUTOPILOT.md; fix OPERATIONS.md references to "Clocks" | `test_hookify_rules` etc. unchanged | n/a |
| A1-0 probe (evidence only; DONE 31/10, `evidence/autopilot/a1-0-verification.json`) | one-off `claude/autopilot-probe` workflow (push-triggered like the 28/10 image probe, removed before merge): Gemini 3.8 Flash text, image input, 30 s video, 429 shape, AI Studio limits readback by the owner; `gh api` for branch protection, Actions-can-approve-PRs, repo visibility, minutes | evidence JSON | decisions for 2.2/2.4/2.5 |
| A1-1 budget | `ops/autopilot_budget.py` + ledger | `test_autopilot_budget` | quota out |
| A1-2 reviewer | `production/bible/gemini_review.py` (text, image, clip modes, schema, grounding, pre-filter vs accept mode) + calibration replay; identity allowlist PR after owner decision | `test_gemini_review`, `test_reviewer_calibration` | below 9.5, lenient reviewer, 503 |
| A1-3 lease | `ops/autopilot_lease.py` (+ `autopilot` owner) | `test_autopilot_lease` | lease busy / crash |
| A1-4 planner | `autopilot_plan.py` + `autopilot-plan.yml`: S1-S3 | `test_autopilot_plan` (gates run before PR; bounded retries) | bad plan never reaches a PR |
| A1-5 sources | `autopilot_sources.py`: S5-S9 loop via `requests`, per-shot bound, fallbacks | `test_autopilot_sources`, `test_review_loop` | no footage, Pavo down, repeat review | Implemented (dispatch-only): public Commons images via `public_sources.fetch` + vetted library clips; Gemini flash-lite pre-filter may only REJECT/MAYBE (evidence); sheet + list in a PR; nothing approved; Pavo/Buzzy shots routed to Claude.
| A1-6 merge | `autopilot-merge.yml` + decision function | `test_merge_decision` | PR stuck, wrong path |
| A1-7 tick + clock | `autopilot.yml`, `autopilot_state.json`, layers L2/L3 (L4 after owner decision), stale alarm Issue | `test_clock_layers`, `test_autopilot_state` | cron dropped |
| A1-8 finish | thumbnail, `native-review.yml` dispatch/consume, record writer, publish dispatch, readback | `test_autopilot_finish` | double publish, unreviewed publish |
| A1-9 dry run | tick in `dry` mode for 3 days on the real queue: logs what it would do, no effects | evidence | before enabling |
Enable order: dry -> one Short supervised by the owner -> autonomous with kill switch. Claude tokens saved (estimated,
to be measured as "Claude turns per published video" before/after): S2, S5, S8, S9, S11-S14, S16 and the watchdog, i.e.
nearly all per-Short judgement; Claude keeps code PRs and escalations.

### Phase 2: Long autopilot
PRs: B-1 long planner from `LONG_DESIGN.md` (L1); B-2 batched source loop per act with budget awareness; B-3 preview
and Gemini chunked native review per act (`long_review` evidence shape, `inspection/claude_review.json` unchanged);
B-4 owner decision + PR on the long reviewer identity (else Claude accepts the long and only the rest is automated);
B-5 long tick through `long-build.yml` resumption, `approve.yml`, `publish.yml`.
Tests: `test_long_autopilot_plan`, `test_long_chunk_merge` (chunk failure = FAIL), `test_long_resume`.
Antidotes: quota out mid-long (resume next day, no re-review of reviewed hashes), a failing act regenerates only that
act, runner minute exhaustion pauses.
Saved: the biggest Claude cost (hundreds of shots/clips reviewed) if calibration passes; otherwise only planning and orchestration.

### Phase 3: Comments and daily report
PRs: C-1 Gemini comment triage and reply drafting with the deterministic policy filter and `needs-human` queue, using the
existing ledger and 20/day cap; C-2 daily report job (what shipped, public/processed state, quota use, parked items,
beat age) written to `evidence/daily-report/` and a single rolling status Issue; C-3 learning loop reads reports,
suggests but never auto-changes strategy.
Tests: `test_comment_policy`, `test_comment_no_double_reply`, `test_daily_report`.
Antidotes: injected comment text cannot trigger actions; duplicate replies blocked by the ledger; Issue spam capped.
Saved: all comment and report tokens (Claude previously read each queue and report).

## 7. Open owner decisions (one line each)
1. Allow `gemini-3.8-flash` as source/still/thumbnail approver (and later, long reviewer) in the approval allowlist.
2. Place a fine-grained Actions PAT in the runner repository secrets (L3), and optionally the Cloudflare Worker secret (L4).
3. Lease: reuse owner `claude` with `task: autopilot` (default) or add owner `autopilot`.
4. Whether engine PR checks may be satisfied by in-job tests or by a PAT-created PR.
5. Read the AI Studio free-tier limits for the project and paste them into `evidence/autopilot/budget.json` (A1-0).
