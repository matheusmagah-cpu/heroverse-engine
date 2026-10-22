# HeroVerse operations — current execution map

## Authority and boundaries

- `SYSTEM.md`: the canonical four-stage delivery contract: mining → modeling/production →
  originality, intention and critique → publication, with live intelligence across the cycle.
- `STANDARD.md`: production quality standard; frozen per-file criteria and bindings remain authoritative.
- `strategy/DECISIONS.md`: evidence required for strategy/cadence changes.
- `strategy/MODELING_SPEC.md`: modeling requirements and the reference/format documents it cites.
- `strategy/VIDIQ.md`: research budget, recorded validation and the call ledger.
- `ops/DOT_PROTOCOL.md`: delegated task delivery; `ops/RUNNER_WAKEUP.md`: existing runner-dispatch contract.
- `ops/ERRORS.json`: regression controls. Historical observations and `archive/` do not direct new execution.

Matheus owns the project (`matheusmagah@gmail.com`); Will is the YouTube account.
Channel: HeroVerse `@heroverse74`, `UCuMF6pJQkyMzaVoAxFL86yA`.
These facts do **not** establish ownership of the Gemini key or its Google Cloud project.
Both GitHub repositories are public. Credentials remain in configured secrets, never in files or logs.

The owner returned execution to this chat; Dot's execution was interrupted. Do not assume that
an old Claude/Dot scheduled session is running. An agent pause is not a repository-wide pause:
existing GitHub schedules and YouTube `publishAt` values have their own state. Inspect before changing them.

## Non-negotiable rules

- Additional cost: zero. No new paid service, billing, card or promotional-credit dependency.
  A historical free-tier observation, model allowlist or public price table is not proof of the
  current key/project configuration or recurring capacity.
- Original English Christian content; exact KJV quotations; no copied identity/recording,
  fear-bait, fabricated prophecy, or health/wealth promises. Retain provenance.
- Frozen QA, whole-file scan, rights/policy checks and the designated watched review must pass.
  The designated reviewer is `gemini-3.8-flash`; a fallback is not an approval.
  Review items require at least 7 and the base overall rubric at least 8; **new uploads also
  require the owner's additional overall floor of 9**. Historical owner exceptions are not a new default.
- Missing, errored, stale or hash-mismatched evidence blocks release. Nobody fills
  `APPROVAL.json` or eligibility flags manually. Preserve artifact identity across review and upload.
- The monetization deadlines are owner goals, not verified forecasts or promises.
  Official platform numbers, own estimates and model judgments must remain distinct.
- A cleanup is not permission to lower quality, bypass authentication or change publication schedules.
  Do not repeat approved audiovisual checks merely because code has moved.

## Active execution chain

Use the delivery/acceptance rules in `SYSTEM.md` to coordinate these existing entry points.
Shorts use the same production and review handoffs after the long prerequisite passes.
The contract does not add an orchestrator: the gaps listed below still require implementation
or qualification before the complete cycle can be called autonomous.

| Work | Entry point and current implementation |
|---|---|
| Research and modeling | vidIQ through the authorized agent; `structures/`, `strategy/` and `production/script_check.py` |
| Images | `nightly-images.yml` → `cf-images.yml`; reused assets retain their provenance |
| Render | runner's `.github/workflows/render.yml` or engine's manual `pilot-render-stills.yml` → `ci/render_pilot.sh` |
| Technical checks/package | `production/qa_pilot.py`, shared native instruments and `package_pilot.py` |
| Long review/gate | `approve.yml` → `long_review.py`, `three_stage.py`, `prepublish_gate.py` |
| Shorts | `shorts.yml` / `shorts-review.yml`; long prerequisites, exact media binding, technical and watched gates |
| Upload | `publish.yml` / `publish-shorts.yml`; ledger and receipts prevent blind re-upload |
| Reporting | `market-panel.yml`, `goal-report.yml`, `owned_feedback.py`, `learning_loop.py` |

`approve.yml` can dispatch production/publication work. It is **not** an isolated review-only test.
The current Short 006 recovery routes include historical consumed/expired attempts; do not replay them
as a fresh qualification. The handoff audit found no recovered Interactions implementation.
Its old “50 tests passed” report is not runnable code or proof of a real provider inference.

The runner's workflow is authoritative in **heroverse-runner**, not the archived copy formerly
at `ci/runner-render.yml`. Its two files remain useful; removing the repository would remove the
current executor. Consolidation into engine is unfinished work (#242), not part of this cleanup.
The pinned source ZIP is still extracted and verified by `pilot_render.py` for the original
Kokoro adapter. The ASR extraction helper and QA instruments also remain live.

## Actual scheduler (UTC; BRT = UTC−3)

At the cleanup baseline, engine `heartbeat.yml` registers `41 * * * *` (24 opportunities/day);
runner `render.yml` registers `13,43 * * * *`. These are intended opportunities, not guaranteed starts.
`ops/heartbeat.py` is the source of truth for dispatched tasks:

| Task | Slots | Condition |
|---|---|---|
| Missing images | 00:30, 01:30, 03:30, 12:30 | `images_missing` |
| Market panel | 07:17 | recorded-run/retry guard |
| Reconcile | 07:20, 10:20, 13:20, 16:20, 19:20, 22:20 | `reconcile_todo` |
| Publish Shorts | 07:35, 13:35, 19:35 | `shorts_pending` |
| Goal report | 07:45 | panel dependency, waiting until 09:30 at most |
| Channel privacy | 08:05 | currently dispatches the default **plan** mode |

No native/Gemini mining, packaging mining, structure mining or first-comment task is in this table.
Channel privacy's automatic run is a **plan**, not proof of changed visibility.
The manual metadata/comment/channel workflows remain available; do not call them completed
because an upload or a workflow is green.

Known limitations preserved for the next correction, not silently changed here:
- `render_queue.py` excludes slots over six hours late; unresolved work may leave the automatic selection.
- A failed render does not cause unlimited unchanged rerenders; material defects need correction.
- Historical Short-specific cutoffs do not create a new slot or a current review-only route.
- The four-day runway is a goal; an existing script, manifest or approval filename is not sufficient
  evidence of eligible stock. Check the full gate and exact artifact.
- A successful report can still say `HOLD` / insufficient evidence; that is not a demonstrated learning result.

## Qualification and budgets

The native acquisition/ASR/profile tools and regression tests are retained for shared QA and
pending instrument qualification (#140); mining arithmetic/modeling and authenticity work (#142/#141)
remain unfinished. Retiring old mining workflows does not approve their measurements or remove these goals.
The old native-first schedule and duplicate Gemini-mining instructions are superseded by `SYSTEM.md`.
Unqualified measurements must not become production targets.

The vidIQ cap remains at most 10 research calls/day and 2,000 credits/cycle, with the ledger and
`mining/market_evidence.py` enforcement. Provider limits and availability must be checked for the
actual configuration before a new route is adopted. No calls were made during cleanup.
The public-repository status does not establish zero cost for every external service.
The report's historical private-runner minute budget is not a payment authorization.

## Where current status lives

- `evidence/daily-report/latest.md`: last observed snapshot; read its timestamp.
- `production/<pilot>/out/{manifest,qa,review,gate}.json`: exact long-file state.
- `production/<pilot>/shorts/shorts.json`: canonical Short state; old correction histories are not replacements.
- `publish/ledger.json` and `publish/receipts/`: upload identity and reconciliation, not a substitute for public readback.
- Open issues/PRs: unresolved work. Keep completed/cancelled discussions in history.
- `evidence/reviewer-qualification/20261022-preflight.json`: current recorded reviewer preflight blocker.

Check the repository HEAD before changing anything. Never copy a stale local manifest over newer
canonical evidence. Upload, approval, workflow success and current public visibility are separate facts.

## Controlled dispatch and cleanup

When an authorized task needs the existing request interface, a request under
`migration/requests/<name>.json` has `{"workflow":"file.yml","inputs":{}}`.
`requests.yml` dispatches it once and moves it into `done/`. Keep this interface; it is not retired.
A request can trigger external effects; cleanup does not create any request.

`archive/ARCHIVE_PLAN.json` v2 inventories every tracked baseline path and gives exact relocations/hashes.
It replaces the stale bulk-move plan. Historical code is not runnable from its archived location.
See `archive/README.md` for recovery. Four generated bytecode caches were removed; evidence,
media, hashes, approvals and source archives remain recoverable and unchanged.
