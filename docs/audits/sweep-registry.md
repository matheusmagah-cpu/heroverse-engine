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
| `thumb-character-first` | PR #460: thumbs.py, THUMB_NOT_APPROVED in publish_episode/publish_video/preflight, pr-checks.yml test path. Integrity S4-S7 fixed in the PR (E121). | 2026-10-27 | 0/9 security (none ≥ 8) |
| `long-qa-v3-e126` | PR (claude/long-qa-v3-gates): qa_pilot.py and prepublish_gate.py read story QA v3, render_queue pin, captions.py long .srt track, publish_video/preflight/captions_audit upload the recorded track, `pr-checks.yml` test path. H1 applied (`caption_track.file` only a bare name beside the manifest). | 2026-10-27 | 0/7 security (none ≥ 8) |
| `reach-ctr` | PR (this): `mining/reach_report.py` (YouTube Reporting API reach job, report download with the owner's token), `goal-report.yml` step with `HERO_YT_AUTHORIZED_USER_JSON` via `env:`, `pr-checks.yml` test path. S3 (token only to the Reporting API host), S9 (no token on redirect), S10 (step bounded, never crashes) fixed, S8 hardened. | 2026-10-27 | 0/10 security (none ≥ 8) |
| `long-preflight-e127` | PR (claude/long-preflight): `bible/long_preflight.py`, `episode_build.py` (check_plan, windows, risk_rank, probe-queue, the long's probe gate), `episode_preflight.py`, `dispatch_guard.py` shot-probe, `shot-probe.yml` plan step, `pr-checks.yml` test path. H1 applied (estimate path from the plan's episode id). | 2026-10-27 | 0/4 security (none ≥ 8) |
| `long-build` | PR (claude/long-build): `bible/long_build.py`, `episode_build.py` voice_layout and the long's compose prediction, `scene_stills.py` 16:9, `dispatch_guard.py` long-build, new `long-build.yml` (prepare, upscale matrix, assemble, record), `pr-checks.yml` test path. H1 (plan regex in every job), H2 (resume_run only from a long-build of main) and H3 (token per step) applied. | 2026-10-27 | 0/6 security (none >= 8) |

## Proposed, not yet run

| Zone | Argument | Premise to re-verify before starting |
|---|---|---|

## Candidates verified and refused

Written here so they are not rediscovered. A refused candidate without a written reason comes back.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
