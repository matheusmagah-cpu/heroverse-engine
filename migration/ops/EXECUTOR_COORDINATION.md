# Shared Claude Code / ChatGPT execution

Owner direction, 2026-10-30: both environments act on the same HeroVerse project.
When one cannot continue because of usage limits, the other continues from the
accepted delivery. Do not rebuild the other's work or alternate speculative fixes.

## One source of project truth

Read current main, AGENTS.md, CLAUDE.md, the latest migration/evidence/handoff,
DECISIONS.md and the relevant plans/receipts. Reconcile open PRs, workflow runs and
migration/requests/{inflight,done} before an effect. Private media packages remain
private; public handoffs refer to media hashes and task IDs, not private access links.
A completed test/review is reused while its exact inputs and criteria still match.
Fix only a demonstrated defect, at its responsible stage.

## Shared control reference

The operational branch `claude/shared-executor-control` carries coordination
metadata in its head commit message, prefixed `HEROVERSE_EXECUTOR_LEASE_V1\n`.
It is not a production branch, video ledger, scheduler, approval or merge candidate.
Its tree is unchanged from its parent. Do not merge it into main or use it to ship code.

Message JSON fields: `schema` = `heroverse-executor-lease-v1`, `owner` =
`codex`, `claude` or null, `run_id`, `state` = `active` or `idle`,
`renewed_at`, `expires_at` (UTC), `task`, `base_main_sha`, and `next_action`.
Never include credentials, private media links or account quota details.

For each scheduled or interactive project-writing run:
1. Read the control ref and its commit. Save its exact SHA. If missing/malformed,
   do read-only diagnosis; do not silently initialize a second controller.
2. If another run's active lease has not expired, monitor read-only and return.
   Availability of tokens does not justify interrupting its valid work.
3. If idle or expired, reconcile existing provider/workflow IDs and claims first.
   Expiry transfers supervision, never permission to replay an uncertain job.
4. To acquire: create a commit using exactly the observed head as parent and its
   unchanged tree; set owner/run_id/state active, renewed_at now and expires_at
   at most 55 minutes later. Update the control ref only as a fast-forward from
   that exact observed SHA (connector update_ref expected_sha + force=false;
   Git push without force, or GitHub ref PATCH force=false). Competing sibling
   commits must fail. Read back and require your new SHA before effects.
5. Renew before every effect and at least every 10 minutes during long work with
   the same compare-and-swap procedure. If ownership changed, stop new effects.
   An expired holder must reacquire, never assume it still owns the lease.
6. At a safe boundary, record the real delivery in the existing handoff/PR/receipt,
   then release by a similarly guarded commit: state idle, owner null,
   expires_at now, next_action describing the existing task. Do not release
   while an unrecorded side effect or specialist is still active.
7. On any uncertain write result, read the same ref/commit/operation before retry.
   Never force, delete or reset the coordination ref to win ownership.

## Scheduling and availability

Keep the existing GitHub heartbeat, existing ChatGPT supervision and existing
Claude routines. No additional polling clock. Each routine checks the shared
control reference before effects. The light Claude watchdog only handles mechanical
checks; it respects an active lease and never starts media work itself. Daily
analysis/mining also use the same lease and existing daily ledgers.

The first eligible scheduled executor acquires the lease. The other observes.
When a provider's usage limit prevents a run, the other can acquire the idle/expired
lease on its next scheduled execution. A returning executor reconciles state first.
Do not claim immediate switching or read the other provider's usage balance through
a tool that does not expose it. If both executors are unavailable, no agent can
continue reasoning; already-dispatched GitHub jobs retain their independent state.

## Same review workflow on either host

Use the original Anthropic `pr-review-toolkit` command and applicable specialist
prompts. The ChatGPT personal skill of that name packages upstream version 1.0.1,
revision `f8c5e7a1dcb71b10cb74586224b5401f3de5db28`, with host-tool mapping.
This is execution of that portable workflow by Codex, not a Claude login and not
a claim that Anthropic models reviewed the PR. Record the true executor, exact
head/base, upstream revision and actual specialists. Keep security sweeps separate.
The required review is not replaced with an unrecorded informal inspection.
Code changes still use claude/*, PR, required tests/reviews and squash merge.

## Existing execution tools

- GitHub: common code, handoffs, durable request claims, runs and publishing gates.
- Pavo: preserve `.mcp.json` / `heroverse-pavo` and the existing adapter/workflows.
  A host without its stdio MCP uses existing authorized GitHub request entry points;
  it does not copy tokens or create another provider implementation.
- Gemini native evidence: preserve native-review.yml, saved interaction IDs and
  actual model identity. Code-review tooling does not qualify audiovisual accuracy.
- Kokoro/ffmpeg/Cloudflare/footage: existing preparation and render paths only.
- vidIQ: existing connection, current ledger and spending restrictions. Connection
  does not authorize generation or repeat paid research.
- Buzzy: optional diagnostics/catalog connection only until its mutation route,
  zero-cost conditions, rights and quality gates are actually qualified.
- Runway stays excluded by current project spending policy. Ads stay on hold.
- Desktop-dependent helpers require an online authorized device. A connected
  plugin alone does not establish executor availability.
- Hookify, security-guidance, verified-security-sweep, social-media-skills,
  superpowers, headroom, ffmpeg-llm, image-generation, bible-by-midvash,
  feature-dev, commit-commands, claude-md-management, cartographer and
  claude-code-setup retain the purposes/limits documented in CLAUDE.md.
  Being installed on Claude does not establish installation on ChatGPT.
  Host-specific hooks are not silently converted into advisory checks.

All source/media approvals, frozen QA, the 9.5 floor and publication readback
remain required. No manual APPROVAL.json, copied reviewer identity or transferred score.
