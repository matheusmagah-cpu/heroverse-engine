# HeroVerse operations — current execution map

Transfer checkpoint: `HANDOFF_NEXT_CHAT_20261023.md`; the observations below supersede its pending upload state. The earlier AI Studio 8.9 remains **invalid**, as recorded in `evidence/reviewer-qualification/20261022-aistudio-short006-validation.json`. The current Short 006 remains unapproved and unpublished in the pipeline. Native automatic review is still blocked.

New observation, 2026-10-23 UTC: one fresh AI Studio upload showed 4,327 media tokens.
A content-only probe correctly identified the closing words, both scenes, transition, male voice
and piano/pads, with approximate timings. The unchanged review prompt/schema then returned overall
8.0, rhythm 6.5 and ending 6.5: a rejection. The UI has no captured transport/modality trace,
estimates 41 rather than 42 seconds and calls camera motion parallax; those limitations are
explicit in `evidence/reviewer-qualification/20261023-aistudio-short006-validation.json`.
No canonical review, production change or publication follows from this observation. The previous
8.9 remains invalid. Native automatic review and recurring capacity remain unqualified.

The isolated workflow now offers explicit `stream` mode: the documented SSE response transport
is the concrete change from the consumed buffered-JSON attempts. It retains the exact file, model,
prompt, schema, existing QA, free-project observation, STARTED reservation and shared two-call/600 s
budget. Only a fully completed READY control permits video. Partial HTTP 200 or text is not success;
video also requires positive audio and picture token usage. There is no reconnect, retry or fallback.
This is a consumed qualification, not an activated production route.

Actual SSE result, 2026-10-23 at 02:42:54 UTC: run `39891051684`, code
`8e201caba48de4bc67576f4bf03f07879632f1a6`. The text control returned HTTP 503 /
`service_unavailable` after 2.54 s. Exactly one inference was attempted; video was correctly
skipped. There was no render, repeated QA, canonical write or publication. Exact result:
`evidence/reviewer-qualification/20261023-stream-diagnosis-short006.json`.
The original result ZIP is artifact `12474851206`, SHA-256
`765d69638da0ea6df83247c5cbd341c1cbb2b60a9921ac15f679db7f756e03ea`.
STARTED artifact `12474861170`, SHA-256
`d505df70de91a591e6644aec1833d010a5a3604add54aa85bc9cee48000ad640`,
is also preserved verbatim in `20261023-stream-start-short006.json` in that directory.
Do not delete/reuse this reservation or repeat an unchanged stream attempt.

PR #275 was merged after CI `39890736005` passed all 51 test files, including the existing
document-register check corrected to recognize the transfer checkpoint. This qualifies the
tested code, not provider availability. Before the isolated call, the UI still displayed Free tier;
the model row showed 1/5 RPM, 234/250K TPM and 12/20 RPD for the selected reporting window.
Those delayed maximum-usage displays are not a reserved balance. The existing binding
observation remained valid and matched the runtime credential; no credential or billing change
was made.

Next: obtain a concrete provider recovery condition or qualify a native audiovisual route under
the existing criteria before another API call or production correction. A public operational
status page and the grounded UI rejection do not establish API recovery. The UI's approximate
timings and inaccurate parallax label must not become production instructions. Learning
integration, 008/009/011 corrections, 010 review, approved stock and publication remain pending
behind this reviewer block. Existing GitHub schedules were not globally disabled by this work.

Execution audit, 2026-10-23: reproduced and corrected a streaming reader defect: text
already present in `step.start.content` was discarded (`REA` + `DY` became `DY`).
The provider-error adapter also now recognizes Interactions string codes and propagates
the failed control as `ProviderFailure`, preserving `HTTP_503_UNAVAILABLE` rather than
rewriting it as `NOT_REVIEWED_ValueError` / `UNKNOWN`. Public receipts retain categorical
diagnostics without arbitrary provider prose or account data. Checked-in STARTED/final
receipts now prevent replay even after the remote Actions artifact expires.
These are real client fixes; they do not explain or erase the previously received HTTP 503.
No new inference, reservation identifier, model, rubric or master change is part of this fix.
Google's thinking documentation confirms that omitted thinking level and the UI's Medium
selection have the same effective default for gemini-3.8-flash. The UI shows `No API key
selected`; linking a key offers a paid-key/billing flow, which was closed without changes.
The successful UI response therefore does not establish availability of the credentialed API.

PR #276 merged as `1b27df70806db58699b0d2b896796aec7234dd5f`; CI run `39931031364`
passed all 51 test files. These checks exercised client behavior without any new provider call.

A blind UI audiovisual control at 09:25–09:33 UTC now demonstrates actual picture and audio
access: an independent 9-second, caption-free fixture was uploaded once, and the designated
model identified all three colored shapes and the exact sentence present only in audio.
The first full-file answer omitted one of two tones, so its completeness check **failed**.
One focused examination of the final three seconds recovered both tones and their correct
relative pitch without being told their number, pitch or timestamps. That follow-up does not
erase the initial omission or qualify a complete single-pass review.
The preserved MP4, construction source, expected content, raw answers, decoded-AAC check,
screenshot and validation are in `evidence/reviewer-qualification/20261023-ui-av-control/`.
This closes the narrow UI media-access uncertainty; automatic pipeline integration and recurring
capacity remain unqualified. No new credentialed API inference, master correction, repeated
master QA, canonical score/eligibility write or publication occurred. The 8.9 remains invalid;
the separate 8.0 UI rejection and its limitations remain preserved.

## Authority and boundaries

- `SYSTEM.md`: the canonical four-stage delivery contract: mining → modeling/production →
  originality, intention and critique → publication, with live intelligence across the cycle.
- `STANDARD.md`: production quality standard; frozen per-file criteria and bindings remain authoritative.
- `strategy/DECISIONS.md`: evidence required for strategy/cadence changes.
- `strategy/MODELING_SPEC.md`: modeling requirements and the reference/format documents it cites.
- `strategy/VIDIQ.md`: research budget, recorded validation and the call ledger.
- `ops/DOT_PROTOCOL.md`: delegated task delivery; `ops/RUNNER_WAKEUP.md`: existing runner-dispatch contract.
- `ops/ERRORS.json`: regression controls. Historical observations and `archive/` do not direct new execution.

Matheus owns the project; Will is the YouTube account.
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
  require the owner's additional overall floor of 9.5** (raised from 9 on 2026-10-23). Historical owner exceptions are not a new default.
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

Diagnosis result, run `39822372027`: the designated model returned HTTP 200 and READY for text
(244.8 s), then HTTP 503 with provider code `service_unavailable` for the exact inline video
(5.5 s; request 20,494,356 bytes). There were two calls, zero Files uploads, no new scores and no
publication. Receipt: `evidence/reviewer-qualification/20261022-inline-diagnosis-short006.json`,
artifact `12444883451`, ZIP SHA-256 `95fd559ec95af5f606a23e49a62d09c0c8c537e1e603d8416586542cab0f2256`.
This rules out a failure limited to resolving the provider-hosted file URI; it does not isolate
the video-processing backend, structured response handling or service capacity as the root cause.

The next supported candidate tested was the stable `v1/interactions` route, explicit mode `stable`,
reservation `short006-20261022-stable-inline-v1`. Official `api-versions` and `interactions-api-v1`
documentation confirms the same model, static fps, structured output and response schema support.
It keeps the same text control, exact inline MP4, rubric and two-call/600-second budget. Only the
endpoint version changes; the earlier beta reservations remain consumed. It is not adopted into
production until its real result is qualified. A fresh no-cache API read confirmed the preceding
CI completion when cached summary responses were stale; completed logs also record 51 PASS files.

Stable-route result at 17:46 UTC, run `39825632213`, code `a3ba3d46b3d57c31a0f430dedbaf8d586592a3a3`:
the text control itself returned HTTP 503 / `service_unavailable` in 0.45 s. The video call was
correctly skipped. One call, no Files upload, render, repeated QA, canonical write or publication.
Exact receipt: `evidence/reviewer-qualification/20261022-stable-diagnosis-short006.json`,
artifact `12447000483`, ZIP SHA-256 `e5e6dff093db7e53443482561f7d1aa306daa02f26f833ff3d091f35ae139dc4`.
Reservation `12446885743` is consumed. This failure is not confined to this MP4, but does not
establish a platform-wide outage or explain the earlier beta video failures. Do not repeat any
of these three unchanged qualifications. PR 274's complete CI logs (run `39824476302`) record
51 passing test files; the dependency installation correction passed, independently of provider availability.

The current handoff remains **review blocked**, not production activated. Resume only with a
concrete recovery condition or a genuinely qualified native audiovisual alternative. A calibration
review of the existing backup receipts found no qualified replacement: Flash Lite falsely approved
three defect cases, Flash 3.6 rejected controls and had provider failures, and the local model failed
ASR prerequisites. These are historical results, not new inference tests. No fallback is enabled.
After a valid review, apply the unchanged score floors, correct actual material defects if found,
then qualify a fresh publication package; the expired October 21 slot cannot be reused.

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
