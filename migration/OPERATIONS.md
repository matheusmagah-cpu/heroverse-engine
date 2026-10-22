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

`reviewer-preflight.yml` is the manual, isolated qualification entry point. Its default `check`
mode makes no provider call. The explicit `review` mode is restricted to the preserved Short 006
and the current qualification in `production/reviewer_qualification.py`. It verifies the runtime
key against the fresh project observation, the exact release asset and its existing QA binding;
it does not repeat QA. A durable STARTED artifact reserves the qualification before one synchronous
Interactions request. Serialized runs, a reservation lookup, run-attempt checking and an atomic
local claim prevent an unchanged qualification from being replayed. No provider retry or fallback
is allowed. The result is an isolated artifact, always `publish=false`; canonical records, schedules,
approvals and publication are untouched. Permissions are contents/actions read, with no YouTube secret.
Existing production still uses generateContent; this qualification does not switch it automatically.

Activation result, 2026-10-22 12:32 UTC: run `39779111955` confirmed **MATCH** for the
current secret against the historical fingerprint, and for the preserved manifest/recorded QA
binding. The exact artifact receipt is retained in
`evidence/reviewer-qualification/20261022-runtime-preflight.json`; its original ZIP artifact is
`12425811724` (SHA-256 `401fbb196cd73aef489fa71bb5a2441c98256b3571e3c3f6be26ec11bf37d5e0`).
The job's final failure is the explicit activation block, after both receipt generation and upload
succeeded. No inference or publication occurred. This completes the fingerprint comparison for
this activation attempt; it does not prove the current project or billing configuration.

Earlier in this activation attempt, AI Studio was signed in as Matheus and showed no imported projects.
A direct read of the historical project's Google Cloud credentials page returned **Site Unavailable**,
including after one reload. This is an access limitation of this browser, not evidence that the
project was deleted or that Matheus lacks permission. No account switch, project import or credential
change was made by the agent at that point.

After the owner changed the selected account, direct UI observation at 16:07 UTC confirmed that
the project containing the existing runtime credential is Free tier with no billing account.
The credential was matched against the existing policy, closing the association gap for this
observation. No credential value, fingerprint, account or project identifier is added to the
public observation receipt: `evidence/reviewer-qualification/20261022-project-binding.json`.
The designated model's displayed limits are 5 RPM, 250,000 input TPM and 20 RPD. The one-day view
showed a peak of 4 RPD; it is delayed usage, not a reservation or guaranteed remaining balance.
The recurring free offer permits a bounded one-call qualification. It does not establish sustained
pipeline capacity: two longs and three Short candidates per long nominally require 8 decisions/day,
or 16 with one retry each, before backlog/corrections. The legacy shared retries still lack a proven
global budget.

Real qualification completed at 16:43 UTC: run `39816315756`, code `66b1d772a59a4e4cbe29f9cf9c441049b4ec3ad1`,
made **one** Interactions inference request for the unchanged `d6a7dc...` master after checking the
current credential, release bytes and recorded QA. The response was **HTTP 503** at the inference
stage; no review scores were obtained. Cleanup succeeded. The exact final artifact receipt is
`evidence/reviewer-qualification/20261022-interactions-short006.json`, artifact `12442217461`
(ZIP SHA-256 `15f901f1ee5625639159521fb588446c22a040c1a8932dc4145a2cd0e797c8dc`).
STARTED reservation artifact `12441419008` prevents replay of this consumed qualification.
The result is `NOT_REVIEWED`, `publish=false`; no render, repeated QA, canonical write or publication.
The new interface did not remove the 503. This establishes a provider-stage failure for this exact
request, not a proven root cause, quota exhaustion or platform-wide outage. Do not retry unchanged,
delete the reservation, rewrite it as approval or rerender the same master to address this failure.
Next: establish a concrete provider-side recovery condition or qualify an alternative reviewer with
the existing controls before another inference attempt. Native availability and sustained recurring
capacity remain blocked; the account/project/free-tier verification is complete for this observation.

The next bounded diagnosis is `reviewer-preflight.yml` with explicit mode `inline`, a separate
reservation `short006-20261022-inline-diagnosis-v1` and at most two inference calls within the same
600-second deadline. First, a text-only READY control tests the designated model. Failure stops
before any video call. Only a successful control permits the unchanged full MP4, with its original
embedded audio, to be sent as base64 bytes in the request. This tests provider-file resolution as
a hypothesis; it does not assume it is the cause. No Files API upload/deletion is used in inline
mode. The shared editorial prompt, sampling, score floors, output identity and QA binding are retained.
The earlier qualification and its consumed reservation remain untouched. The existing fresh free-project
observation is reused; no new key/project identifiers or fingerprints are published. Provider documentation
allows inline video below 100 MB (`https://ai.google.dev/gemini-api/docs/file-input-methods` and
`https://ai.google.dev/gemini-api/docs/video-understanding`); the client checks the actual request size.
Documentation establishes a supported candidate, not evidence that the media was received or reviewed.

PR 272 also corrected the validation setup after runs `39813213979` (global package-index refresh
timed out) and `39815089810` (stale Ubuntu index returned a package 404). The final check's complete
logs, run `39815812918` / job `119954008799`, record 51 test files passing, no pilot change and successful
cleanup. Dependency preparation took about 48 seconds with the bounded Ubuntu-only refresh.
Run/job summary responses lagged the completed logs during this session; inspect the final logs
before treating an old `queued`/`in_progress` snapshot as current. These are code tests, not new media QA.

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
- `evidence/reviewer-qualification/20261022-preflight.json`: earlier account-access checkpoint.
- `evidence/reviewer-qualification/20261022-project-binding.json`: current bounded free-project observation, without public credential identifiers.
- `evidence/reviewer-qualification/20261022-interactions-short006.json`: actual isolated request, HTTP 503; no audiovisual approval.

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
