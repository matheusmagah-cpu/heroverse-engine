# HeroVerse: execution entry points

`SYSTEM.md` is the current operating contract. `evidence/handoff/CURRENT.md` is the continuation point.
This file maps that contract to existing code. Credentials stay in repository secrets; unfinished private media,
provider URLs and recovery keys stay outside public code, logs and handoffs.

## Bible Short

| Work | Existing entry point |
|---|---|
| Validate the planned story | `production/bible/plan_check.py --strict PLAN`; exact Scripture through `kjv_check.py` |
| Inspect and approve sources | `shot-probe.yml`, `episode_build.py approve-shot`, `shot_sources.py`, `scene_stills.py`; current request/media bindings and explicit reviewer identity |
| Preserve an existing edit | `episode_build.py import-edit BINDING ROOT WORK`; keeps the original PCM, final mix, captions and exact timeline without voice synthesis |
| Check the current regular build | `episode_build.py preflight PLAN --voice VOICE_PYTHON PREPARED_WORK --refs --write`, then `verify-preflight PLAN` |
| Assemble approved shots | `episode.yml` → `episode_build.py` → `short_engine.py`; no new generation inside assembly |
| Inspect a private draft | `episode_build.py render-imported WORK OUT` / `production/draft_render.py`; DRAFT only, not a publication qualification |
| Native audiovisual evidence | `native-review.yml` → `production/bible/native_review.py`; actual complete master audio/video and saved result identity |
| Thumbnail | `production/bible/thumbs.py`: check/refs/finalize/sheet/approve; required for BibleShort part 9 onward |
| Check publication record | `episode_build.py check-record EPISODE_JSON [VIDEO]` → `episode_preflight.record_problems` → `publish_episode.problems` |
| Publish and reconcile | `publish-episode.yml` → `publish/publish_episode.py`; existing `publish/ledger.json`, episode record and `publish/receipts/` |
| Confirm completion | Read the same video's receipt/API state: public and processed; resume incomplete package work on that ID |

A regular build accepts only current preflight and approved source evidence. An imported edit is reconciled
against its own actual timeline and accepted audio; imports do not qualify sources or replace final review.
Before any publisher is called, the record must describe the actual passing review and qualified package.
`check-record` validates its implemented record checks; it does not perform perceptual review.

Private ingress must deliver the exact file to the existing episode publisher without publishing unfinished media
in a repository release or logging private URLs. Consult the workflow's current declared inputs and recorded
claims; do not invent an input name or a new approval format. The workflow remains `publish-episode.yml`.

## Story long

`production/bible/LONG_DESIGN.md` defines construction and its frozen profile. The implemented route is
`long_plan_check.py --strict` → long preflight → `long-build.yml` → `long_handoff.py`/technical evidence →
`production/long_review.py` → `approve.yml` → `publish/prepublish_gate.py` → `publish.yml`.
Use the exact allowed reviewer identities and evidence in `ops/CLAUDE_REVIEW.md`.
Only that workflow creates the long's `APPROVAL.json`. The Short uses its episode record and publisher instead.

Compilation long (owner, 2026-11-01; E251): an arc's complete story assembled from its public Shorts. Plan
`production/bible/compilations/<id>.json` → `compilation-build.yml` (`compilation_long.py`: masters by sha256, 16:9
over a blurred fill, chapter cards, the Keeper's new hook and close from Pavo clips at an exact zero-credit quote,
gain-only -14 LUFS, faded joins; QA `compilation-qa-criteria-v1`) → the Gemini native review as a defect finder →
`inspection/claude_review.json` with `defects` and a `publish_decision` by `claude-session-reviewer`
(`owner_quality_policy.compilation_problems`: no unresolved [a], [b] or [e]) → the same `approve.yml` →
`prepublish_gate.py` → `publish.yml`. The 9.5 track of the story longs is unchanged.

## Long-first and Short cuts

Owner, 2026-11-01 (DECISIONS.md "Long-first, Shorts cut from the long", E259): after the current Noah compilation the
story is made once as a 16:9 long, and the Shorts are coherent 9:16 cuts of it. Nothing below spends credits.

| Work | Existing entry point |
|---|---|
| Plan the long | `plans/<id>.json` (bible-plan-v2) with `"track": "buzzy-long"`, `"aspect_ratio": "16:9"`, 480–720 s measured, every prompt "centred in the frame" (PROMPT_GUIDE "Long-first"), and `long` = pilot, title, description with `{chapters}`, tags, first_comment, chapters on shot ids, thumbnail frame; `plan_check.py --strict` |
| Sources, preflight, build | the Short's own route: `shot-probe.yml` / `scene_stills.py` / `shot_sources.py` at 16:9, `episode_build.py preflight … --write`, `episode.yml` (1920x1080, 16:9 captions, owned music, -14 LUFS) |
| What the cuts need | `episode.yml` record job: master `bible-<id>-sha256-<sha>.mp4` and caption-free master `bible-<id>-clean-sha256-<sha>.mp4` in the release; `evidence/episodes/<id>/report-<run>.json` binds both hashes, the sentence timeline (`composed.sentences`) and the shot timeline (`composed.timeline`) |
| The long's pilot | merge the report, then `buzzy-long-pilot.yml` (plan, report) → `buzzy_long.py qa` (buzzy-long-qa-criteria-v1) + `materialize` → `<pilot>-sha256-<sha>.mp4` alias and the pilot on `claude/long-<id>-<run>` (PR) |
| Review and publish the long | `native-review.yml` (plan = the long's plan, defect finder) as evidence; the session reviewer writes `inspection/claude_review.json` (defects, publish decision); thumbnail approved through `thumbs.py` (format long); then `approve.yml` → `prepublish_gate.py` → `publish.yml`, on the defect-gated buzzy-long track |
| Cut the Shorts | `cuts/<long>.json` (bible-cuts-v1, track buzzy-cut, pilot, report, cuts: id, start, end, optional x, title, description with "full story", tags, first_comment); `short_cuts.py check SPEC` refuses a cut inside speech, off sentence edges or outside 20–179 s; `short-cuts.yml` renders them (centre 9:16, Short captions, gain-only -14 LUFS, fades), puts `bible-<cut>-sha256-<sha>.mp4` in the release and draft `episodes/<cut>.json` (track buzzy-cut, parent long) on `claude/cuts-<long>-<run>` |
| Review and publish each cut | `native-review.yml` with plan = the cuts spec and the cut's own sha256 (never the long's score), the session reviewer's `review` (defects, publish decision) in its record, `episode_build.py check-record`, then `publish-episode.yml`; `arc_links.py` links each cut to its long through `parent.pilot` |

Long-first stills move by need (E261): `episode.yml` maps each approved still's depth (Depth Anything V2 Small, ONNX
on CPU, sha256-pinned; unreachable model: a depth proxy, recorded) and `episode_build.py generate` renders every still
with `motion.direct`'s move, fitted to its spoken span (about 15–60 s of CPU per 15–20 s shot at 1080p). The move and its reason
are in the report's `motion_direction`; a plan shot's `motion`/`atmosphere` overrides it (PROMPT_GUIDE "Cinematic
still animation").

The 9.5 story long (`approve.yml` on story-qa-criteria), the Short episode route, the compilation and every frozen
QA file keep their rules; the buzzy-long and buzzy-cut tracks apply only to their own criteria and records.

## Sources and private provider work

Reuse approved matching material first. Existing source tools include `shot-probe.yml`, `scene-stills.yml`,
`production/bible/shot_sources.py`, `production/footage/`, the image tools and ffmpeg. The authorized GPT-still route
retains its real provenance; source/rights/identity/context checks still apply.

`pavo-private-audio.yml` supports the existing private exact-audio and first-frame requests. It uses the current
shared lease, quota, exact zero-credit quote, encrypted transfer and durable claim. A saved conversation ID is
reconciled by GET, never resubmitted because a caller timed out. A claim without a definitive result is unresolved.
Any bounded retry must satisfy the existing helper/workflow's recorded failure and eligibility checks; elapsed
time does not prove capacity. These paths return source evidence, not final audiovisual approval.

`native-review.yml` uses the existing operator certificate and configured provider credential without exposing the
credential to the caller. Verify current Free Tier eligibility before submission. Preserve upload/interaction IDs,
raw answers, exact model identity and media binding. Reconcile uncertain outcomes rather than repeating a POST.
Every run also writes non-sensitive score evidence (status, provider error codes, overall, per-criterion scores and
timed issues; no media, provider IDs or secrets) to its job summary and the 90-day `native-review-public-evidence`
artifact, so a later executor never needs another executor's private key to read a score (E233).
The runner never holds the master (E248): after a new run reaches `Persist upload state before inference`, the
caller downloads that run's `native-review-upload` artifact, decrypts it with the matching private key, and sends the
exact master bytes once to the receipt's `upload_url` (`X-Goog-Upload-Command: upload, finalize`, offset 0). Until
then the provider has no file and `Await exact-byte upload` can only time out. If a run timed out that way, upload
to its saved `upload_url` and dispatch `resume_before_inference=<run>` with a fresh Free Tier proof.

## Existing automation and its limits

| Surface | Existing responsibility | Evidence of operation |
|---|---|---|
| `heartbeat.yml` / `ops/heartbeat.py` | Durable request dispatch, qualified plan handoff, build evidence discovery and existing package/mirror tasks | Current workflow runs, summaries and request acknowledgements |
| `ops/production_handoff.py` | Queue an eligible `episode.yml` or `long-build.yml` request in the existing request path | Current plan/preflight/order results and saved request claim |
| `ops/review_discovery.py` | Discover build evidence branches and exact commits/run IDs | Inventory; it does not itself view media or approve it |
| Existing ChatGPT / Claude supervisors | Continue production, source inspection and actual audiovisual review under one shared lease | Actual available executor and saved results; installed tools alone do not prove availability |
| Existing watchdog | Detect stale heartbeat, failed runs and missed delivery; respect the active lease | Current run and observed condition |
| Existing daily report/learning | `goal-report.yml`, `mining/live_intel.py`, learning records | Actual public video/readback and age-matched analytics |
| `arc-links.yml` | Link public Shorts and their public, processed long | `publish/arc_links_ledger.json` |
| `tiktok.yml` | Free Buffer mirror of an already-public YouTube Short | `publish/tiktok_ledger.json` |

Keep the existing clock configuration; no additional polling scheduler. A heartbeat success or QUEUE_EMPTY from a
pilot renderer does not prove that a Bible Short has been reviewed or published. Perceptual review requires an
available authorized executor. Describe a handoff or restart as complete only after observing the relevant run.

After publication, existing comment/reply tasks use their current authorization, policy checks and ledgers.
Studio-only tasks such as related-video selection, pinning or end screens remain pending until verified.
They do not justify a duplicate upload.

## Shared executor control

The operational ref `claude/shared-executor-control` carries coordination metadata in its commit message after
`HEROVERSE_EXECUTOR_LEASE_V1\n`. Its tree equals its parent's tree. It is not a production branch or merge candidate.

Fields: schema `heroverse-executor-lease-v1`, owner `codex`/`claude`/`autopilot`/null (`autopilot` = `ops/autopilot_lease.py`; it never authorises a Pavo effect), run_id, state active/idle, renewed_at,
expires_at, task, base_main_sha and next_action. Keep descriptions generic; never store private links or credentials.

1. Read the ref and exact head SHA. Missing/malformed control permits read-only diagnosis, not a second controller.
2. If another active lease is unexpired, observe read-only. Available tokens do not transfer ownership.
3. Before taking idle/expired control, reconcile saved provider/workflow IDs, claims and acknowledgements.
4. Acquire by creating a commit whose parent is exactly that observed head and whose tree is unchanged; expiry is
   at most 55 minutes later. Update the ref with expected SHA and force=false. Competing sibling commits must fail.
   Read back your new SHA before effects.
5. Renew before effects and at least every 10 minutes during long work, using the same compare-and-swap procedure.
   Stop new effects if ownership changes. An expired holder reacquires.
6. At a safe boundary, record the real result and next action in CURRENT and the existing evidence/receipt, then
   release with state idle, owner null and expiry now. Do not release while a specialist or unrecorded effect runs.
7. An uncertain write is reconciled by reading the same operation/ref. Never force, reset or delete the ref.

Switching hosts transfers supervision of existing work; it never permits replaying an uncertain operation.
If neither executor is available, already-started GitHub jobs keep their state but no chat agent is reasoning.

## Code changes and document ownership

Use the existing `claude/*` → PR → checks/reviews → squash process. The original PR Review Toolkit and applicable
security sweep record the real executor, exact head/base and findings. Keep `ops/ERRORS.json` and antidote tests;
code-review evidence is not media approval. Existing host guards remain active.

One current home per subject:

- `SYSTEM.md`: operating contract; `evidence/handoff/CURRENT.md`: current continuation.
- This file: execution entry points and shared control.
- `production/bible/SERIES.md`, `PROMPT_GUIDE.md`, `LONG_DESIGN.md`: series, construction and long-specific design.
- `ops/CLAUDE_REVIEW.md`: actual audiovisual review; `ops/ERRORS.json`: regression evidence;
  `ops/RUNNER_WAKEUP.md`: runner mechanics when that execution surface is needed.
- `ops/AUTOPILOT.md`: the free, session-independent pipeline design (autopilot phases, fallbacks).
- `strategy/DECISIONS.md`: current generic policy; `MODELING_SPEC.md`, `VIDIQ.md`,
  `BEAT_THE_REFERENCE_RULE.md`: research/measurement details subject to SYSTEM and current no-spending policy.
- `STANDARD.md`: applicable rendering mechanics; historical audits and evidence are records, not another work queue.

## Shared Claude Code / ChatGPT execution: token budget

The token budget (`SYSTEM.md` "Token budget") counts Claude Code only, from the local Claude transcripts. ChatGPT/Codex
executor usage is a different account and is not counted here; the 50% cap governs Claude Code, and Codex keeps its own limits.
