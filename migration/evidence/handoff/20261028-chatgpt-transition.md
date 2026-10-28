# HeroVerse transition to ChatGPT — 2026-10-28

## Scope and evidence

Baseline: `362ee8fc1c88496f7b3a745f299fc740f801d4f7` on engine `main`.
Operational observations below were taken on 28 October at approximately
14:06 UTC (11:06 America/Sao_Paulo). They are a snapshot, not a live monitor.

The engine's commits for PRs #519, #522 and #523 name
`session_01J6965eGRpV1J5ZDLkPxvjc`, matching the Claude session identified for the
handoff. The private Claude transcript was not retrieved: sign-in required a
human-verification step. This report reconstructs the repository's recorded
decisions and implementation; it does not claim to reproduce the entire chat.

Read `CLAUDE.md`, `migration/SYSTEM.md`, `migration/OPERATIONS.md`,
`migration/ops/CLAUDE_REVIEW.md`, the series/prompt/long design documents and the
latest decisions before acting. Current plans and later decisions supersede old
handoff dates and old prayer-format instructions.

## Direction and invariants

- Product: the English KJV Bible series on `@heroverse74`, with Shorts and story
  longs. Prayer production, ads and the digital product remain retired/on hold
  as recorded in the authoritative documents.
- Quality floor: 9.5 for new uploads, plus the existing objective gates,
  criterion hashes and media/plan bindings. No manually fabricated approval or
  editorial evidence.
- Additional spending: zero. Existing source quotas and the exact zero-credit
  quote requirement still apply; this transition is not a new spending approval.
- Prefer already-produced, valid assets. A change of assistant is not a reason
  to regenerate an asset, discard a source approval or duplicate a ledger.

## Actual production readiness

Counts below are existing records, not new visual approvals or guarantees that
each remote media URL is currently available.

| Plan | Independent shots | Recorded approvals | Without an approval record | Preflight for current plan | Thumbnail |
|---|---:|---:|---:|---|---|
| `arc-01-long` | 135 | 53 | 82 | Existing report is BLOCKED and stale | DRAFT |
| `genesis-09-short` | 22 | 9 | 13 | Old PASS is stale | DRAFT |
| `genesis-10-short` | 21 | 3 | 18 | Absent | Absent |
| `genesis-11-short` | 19 | 3 | 16 | Absent | Absent |

The long has 138 shots in total, including three `window_of` shots. Two window
sources have an approval record; `s-ki-trees` depends on `s-c2-walk`, which does
not. Of the long's 53 records, 50 are fallback approvals (30 footage, 20 stills)
whose request digests match the current plan; the three Pavo request digests
were not independently recomputed in this audit. The 9/3/3 Short fallback
request digests also match their current plans.

The old long preflight binds plan hash `f37c0f20...`, while the current plan is
`0f66c159...`. Genesis-09's report binds `30e810c6...`, while its current plan is
`7f66f3c8...`. Code bindings changed as well. Re-run preflight on the current
inputs; do not reuse the old PASS or treat old refusal counts as current.

One source record needs reconciliation before reuse: the long's `s-open`
approval names `arc-01-long-s-open` with media hash `f3fc8d87...`, but
`production/bible/stills/arc-01-long-s-open.json` is DRAFT, without the source
hash/approval fields. The committed JPG was checked locally: its SHA-256 is
`f3fc8d87791860513815a69ba5d4f7673aeb35be22061d06ab6f9f676e538052`, matching the
shot approval. Verify the real review history and the source-record contract
before deciding whether its metadata should be completed; do not invent an
approval or generate a replacement by default. This metadata discrepancy alone
is not evidence of a visual defect or a failed build.

Genesis-09 has six thumbnail candidates, two with technical R16 PASS, but its
specification has no editorial approval. Technical PASS is not the final review.
No episode delivery records exist for these four IDs. `pilot-015` has
preparatory assets but no active `script.json` or `schedule.json` in git.

The current arc-01 slot in `bible/arcs.json` and the specific `SERIES.md` table
row is **28 October, 22:00 UTC / 19:00 Sao Paulo**. Older text mentions 29 October,
4 November or the general 10:00 UTC slot. The current slot is a plan, not proof
that the work above can be completed by that time.

## Automation status

The active executor repository is `matheusmagah-cpu/heroverse-runner`, baseline
`c0849b902296cb9b23f452b316ecd1128c5dfd8d`. Its `render.yml` checks the engine's
main branch at minutes 13 and 43. The last inspected run, `40681293282`, ended
successfully at 28 October 11:36 UTC, but its render/QA/package step was skipped.
A green runner result therefore does not demonstrate that a video was rendered.

| Workflow | Latest run observed | Result |
|---|---|---|
| Engine heartbeat | `40649409088`, 28 Oct 07:20 UTC | success; about 6h46 old at observation |
| Market panel | `40649445970`, 28 Oct 07:20 UTC | success |
| Reconcile | `40649448212`, 28 Oct 07:20 UTC | success; not proof of publication |
| Goal report | `40525684836`, 27 Oct 14:54 UTC | success; no 28 Oct report observed |

The engine heartbeat is configured hourly at minute 41. The repository also
documents external Claude clocks: watchdog at :14 hourly, production at :29
every four hours, daily analysis at 08:05 UTC and mining at 09:47 UTC. Those
external schedules were not inspected or transferred. Earlier
`workflow_dispatch` events do not identify which external agent started them.

An unconditional heartbeat recovery is not a diagnostic-only action: it can
dispatch reconcile, publication, comment replies, TikTok mirroring and arc-link
updates. There were no HOLD files in the audited tree. Inspect the due work and
the current authorization before activating such a chain. The isolated
`goal-report.yml` can refresh measurements without dispatching publication, but
it still uses API quota and writes its report to the repository.

The current GitHub connector exposes repository edits and reads, but no direct
new-workflow-dispatch operation was available during this audit. An appropriate
authorized executor is still required for a new manual dispatch.

## Proposed reviewer migration

The draft change accompanying this handoff proposes the explicit identity
`gpt-6-astra-session-reviewer` alongside the historical
`claude-session-reviewer`, sharing the long-reviewer allowlist across the reader,
prepublication gate and upload policy. The legacy review path/schema can remain
for compatibility while `model` preserves the actual reviewer's identity.

This is a prepared change, not evidence that any video was reviewed. Merging
it would not transfer a schedule, create a score, approve a render or publish a
video. The unchanged 9.5 floor and all objective gates still apply. Do not write
a GPT review with a Claude identity merely to satisfy the old allowlist.

## Validation of the proposed change

The complete test list was extracted from `.github/workflows/pr-checks.yml` and
executed locally against this diff: **80 of 80 suites passed, reporting 1,256
tests**. Each suite ran in its own Python process with `-I -B`, at most two
processes at a time. The isolated validation environment supplied OpenCV; no
project dependency or workflow dependency was changed.

The first run passed 78 suites. The two other suites require historical plan
fixtures from commits `1c1ed798a610db8659fff08c61b92d89a8f6f6da` and
`04d6923c40aca5a0907bdccfc50fdbf51846914e`, absent from the initial shallow clone.
After fetching those exact commits and their fixture files, both affected
suites passed unchanged: `test_plan_check.py` (110 tests) and
`test_episode_build.py` (85 tests). The count above uses their successful reruns,
not duplicate totals. No test was skipped to resolve the checkout issue.

The focused reviewer tests also passed, including exact identity matching,
rejection under the Shorts policy, insufficient scores, missing evidence,
incorrect media hashes and altered frozen criteria. `git diff --check` passed.
An independent manual review found no new blocking security or correctness
issue in the diff; its method, scope and limits are recorded in
`docs/audits/2026-10-28-gpt-reviewer-handoff.md`. The Claude-hosted
`verified-security-sweep` and `pr-review-toolkit` plugins were not available or
executed. This record does not claim those plugin checks or a GitHub CI result.

## Next actions

1. Review the migration diff, inspect GitHub CI and resolve the required review
   gates before merge. Local tests passed as recorded above; the change remains
   a draft until the deployment decision is made.
2. Recover the private conversation when its sign-in step is completed, checking
   for owner decisions absent from the repository.
3. Refresh the daily report with a properly authorized executor; verify the
   latest run history and inspect due work before recovering the full heartbeat.
4. Reconcile existing source records, then fill the missing shots and thumbnail
   specifications using the current v5 source order and actual visual reviews.
5. Recompute preflights for the exact current plans, then build, inspect and
   apply the normal approval/publication gates.
6. Configure and verify any replacement assistant schedules explicitly, avoiding
   duplicate watchdogs when Claude becomes available again. No replacement
   background schedule was installed by this handoff.

## Evidence pointers

Paths below are relative to `migration/`, except for the explicit workflow path.

- Production: `production/bible/plans/`, `production/bible/shots/`,
  `production/bible/thumbs/`, `evidence/preflight/`, `production/bible/arcs.json`.
- Rules: `SYSTEM.md`, `OPERATIONS.md`, `strategy/DECISIONS.md`,
  `ops/CLAUDE_REVIEW.md`, `ops/ERRORS.json`.
- Reviewer enforcement: `production/long_review.py`,
  `publish/prepublish_gate.py`, `publish/owner_quality_policy.py`,
  `publish/publish_video.py`, `../.github/workflows/approve.yml`.
- GitHub runs: the run IDs above, plus footage searches `40681959318` and
  `40681962983` (both completed successfully and recorded the latest library
  commits). Success here proves workflow completion, not editorial acceptance.
