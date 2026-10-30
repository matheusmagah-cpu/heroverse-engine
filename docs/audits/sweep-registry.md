# Sweep registry: what exists, what ran, what it is worth

Proposals for sweeps are written here, not in conversation. The `Last run` column is derived from report filenames
by the skill's `scripts/sweep_status.py`; the other columns are written by hand.

## Candidates

| Zone | Argument | Last run | Yield |
|---|---|---|---|
| `workflows-secrets` | `.github/workflows/*.yml`: 18 of 27 workflows read secrets; dispatch inputs and the runner PAT. Not covered: the runner repository itself. | - | - |
| `publish-gate` | `migration/publish/` (`prepublish_gate.py`, `publication_binding.py`, `publish_*.py`): the owner's floor, money-equivalent. | - | - |
| `fresh-code` | Code shipped in the last 3 days; highest churn. | - | - |
| `pavo-mcp` | Private stdio Pavo client, video adapter, server, workflow and registration; excludes provider internals and other publishers. | 2026-10-25 | 0/5 |
| `actions-ci` | PR #417 CI changes: pr-checks, render smoke/preview/render, pavo-footage and voice-sample workflows; `render_pilot.sh`, `fetch_assets.sh`, `apt_install.sh`, `minutes.py`. Pre-existing P1-P3 recorded (depth model hash only printed, pip pins without hashes, render-smoke cancel grouped by `github.ref`). | 2026-10-26 | 0/5 security (none ≥ 8); 7 review fixes |
| `captions-e107` | PR #424: `channel-privacy.yml` captions-audit/captions-repair modes, `channel/captions_audit.py`, `publish/captions.py`, `publish_video.py` caption verification, `preflight.py`. Hardening H1 recorded (repair's `item["manifest"]` has no repository containment check). | 2026-10-26 | 0/5 security (none ≥ 8); 8 review fixes |
| `refusal-parity-e106` | PR #422: `episode.yml` verify-preflight and still-mouth checks, `pr-checks.yml`, `bible/episode_preflight.py`, `episode_build.py`, `plan_check.py`, `publish/publish_episode.py`, hookify rules. Noted S2 (report binding) and S3 (episode id on `--write`), both fixed. | 2026-10-26 | 0/5 security (none ≥ 8); 10 review fixes |
| `syncnet-e120` | PR #457: syncnet.py, lipsync_check.py, episode.yml and shot-probe.yml steps. Hardening H1 applied (`parse` made private, reached only after the hash check). | 2026-10-27 | 0/3 security (none ≥ 8) |
| `thumbs-460` | Former zone label `thumb-character-first`; report `2026-10-27-thumbs-460.md`. PR #460: thumbs.py, THUMB_NOT_APPROVED in publish_episode/publish_video/preflight, pr-checks.yml test path. Integrity S4-S7 fixed in the PR (E121). | 2026-10-27 | 0/9 security (none ≥ 8) |
| `long-qa-v3-e126` | PR (claude/long-qa-v3-gates): qa_pilot.py and prepublish_gate.py read story QA v3, render_queue pin, captions.py long .srt track, publish_video/preflight/captions_audit upload the recorded track, `pr-checks.yml` test path. H1 applied (`caption_track.file` only a bare name beside the manifest). | 2026-10-27 | 0/7 security (none ≥ 8) |
| `reach-ctr` | PR (this): `mining/reach_report.py` (YouTube Reporting API reach job, report download with the owner's token), `goal-report.yml` step with `HERO_YT_AUTHORIZED_USER_JSON` via `env:`, `pr-checks.yml` test path. S3 (token only to the Reporting API host), S9 (no token on redirect), S10 (step bounded, never crashes) fixed, S8 hardened. | 2026-10-27 | 0/10 security (none ≥ 8) |
| `long-preflight-e127` | PR (claude/long-preflight): `bible/long_preflight.py`, `episode_build.py` (check_plan, windows, risk_rank, probe-queue, the long's probe gate), `episode_preflight.py`, `dispatch_guard.py` shot-probe, `shot-probe.yml` plan step, `pr-checks.yml` test path. H1 applied (estimate path from the plan's episode id). | 2026-10-27 | 0/4 security (none ≥ 8) |
| `long-build` | PR (claude/long-build): `bible/long_build.py`, `episode_build.py` voice_layout and the long's compose prediction, `scene_stills.py` 16:9, `dispatch_guard.py` long-build, new `long-build.yml` (prepare, upscale matrix, assemble, record), `pr-checks.yml` test path. H1 (plan regex in every job), H2 (resume_run only from a long-build of main) and H3 (token per step) applied. | 2026-10-27 | 0/6 security (none >= 8) |
| `pavo-shared-quota-e128` | PR (claude/pavo-shared-quota): `integrations/pavo/quota.py` (units, probe-record usage, local refs read by a git subprocess), `video.py`/`image_gen.py`/`server.py` guard wiring, `episode_build.py` run-local ledger and budget stop, `long_preflight.py` units, `dispatch_guard.py` budget (REST read of probe records), `shot-probe.yml` guard name and `PAVO_BUDGET_USED` env. | 2026-10-27 | 0/5 security (none >= 8) |
| `owner-no-stall` | PR (claude/owner-no-stall): story QA v4 (new frozen file) and its readers (`qa_pilot.py`, `prepublish_gate.py`, `render_queue.py`, `publish_video.py`), `integrations/pavo/video.py` PAVO_PROMPT_BLOCKED, `bible/pavo_native.py`, `bible/shot_sources.py` (CDN fetch by sha256, git read of probe branches), `episode_build.py`/`long_build.py` sources and native mix, `pr-checks.yml` test path. H1 applied (speech sidecar path from the record). Review of #476: `shot-probe.yml` merge-blocks, `voice-reference`, still_motion via fetch_source; H2 applied (plain ids only into prompt-blocks.json). | 2026-10-27 | 0/9 security (none >= 8) |
| `slim-system` | PR (claude/slim-system): deletes `description-refresh.yml` and `reviewer-probe.yml` (write-scoped, YouTube / Gemini secrets) with their scripts, the RapidAPI diagnostics and `rekey_shots_e118.py`; `test_dispatch_guard.py` EXEMPT shrinks to existing workflows; docs only otherwise. | 2026-10-28 | 0/4 security (none >= 8) |
| `slim-system-2` | PR (claude/slim-system-2): deletes `shorts.yml`, `shorts-review.yml`, `publish-shorts.yml`, `voice-sample.yml`, `agnes-clip.yml`; unwires `approve.yml`, `publish.yml` (Shorts step), `reconcile.yml`, `heartbeat.yml` (shorts input); `dispatch_guard.py` loses agnes-clip; `render_queue.py` reconcile loses `shorts`; `pending_shorts.py` slot rule only. | 2026-10-28 | 0/7 security (none >= 8) |
| `native-review-pr549` | PR #549: native-review workflow, native_review.py and publishing regression tests; exact working hashes and original 1.4.0 Codex execution recorded in `2026-10-30-native-review-pr549.md`. | 2026-10-30 | 0/8 confirmed; schema limitations retained |
| `native-review-parser-e230` | E230 natural colon-separated issue timestamps; parser, regression and error record, with score/replay/approval boundaries retained. | 2026-10-30 | 0/7 confirmed; raw 6.0 preserved |
| `existing-edit-import` | Local existing-edit importer, CLI guards and bound draft-render consumption; original 1.4.0 Codex method, final hashes and historical findings-index gap in `2026-10-30-existing-edit-import.md`. | 2026-10-30 | 2/8 confirmed (1 Medium + 1 Low), fixed; 0 open; index gap |
| `pavo-private-audio` | Private exact-WAV bridge, workflow, recovery/retry, shared quota consumers; original 1.4.0 Codex sweep, commit-bound reproductions and final hashes in `2026-10-30-pavo-private-audio.md`. | 2026-10-30 | 2/9 confirmed (2 Medium), fixed; 0 open confirmed; provider-price limitation retained |
| `request-input-digits` | requests.yml key validator and real-shell/stub-CLI regressions; original 1.4.0 Codex small-zone sweep and commit-bound E229 reproduction in `2026-10-30-request-input-digits.md`. | 2026-10-30 | 1/4 confirmed (1 Medium), fixed; 0 open |
| `pavo-private-hook` | Silent approved-frame hook variant in the existing private bridge/workflow, exact manifest and dispatch dependencies; original 1.4.0 Codex sweep, final source hashes and offline adversarial guards in `2026-10-30-pavo-private-hook.md`. | 2026-10-30 | 0/5 confirmed; 4 refused leads, prior provider-price limitation retained |

## Manual reviews (not plugin sweeps)

These entries record manual reviews separately from plugin execution and yield.

| Zone | Scope | Review date | Method and result |
|---|---|---|---|
| `gpt-reviewer-handoff` | `claude/gpt-takeover-20261028`: exact long-reviewer allowlist, shared gate/upload policy, `approve.yml`, consuming tests and handoff documentation. | 2026-10-28 | **MANUAL independent static review**: no new blocking finding in the inspected diff; no `verified-security-sweep` or `pr-review-toolkit` execution or score claimed. See [report](2026-10-28-gpt-reviewer-handoff.md); functional results remain in the transition handoff. |
| `production-continuity-integration` | Same PR, based on `51cb8f7`: durable dispatch claims, reviewer/media bindings, long handoff, source revocation, fail-closed detectors and exact TikTok target checks. | 2026-10-28 | **MANUAL review and offline regressions**, including independent E189 writer/history reproduction and 10 focused integration tests. Scope and remaining environment limitations are explicit in the [integration addendum](2026-10-28-gpt-reviewer-handoff.md#integration-addendum-production-and-continuity-corrections). No plugin execution, audiovisual approval or whole-project certification claimed. |

## Proposed, not yet run

| Zone | Argument | Premise to re-verify before starting |
|---|---|---|

## Candidates verified and refused

Written here so they are not rediscovered. A refused candidate without a written reason comes back.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
