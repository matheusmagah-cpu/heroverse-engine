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
| `reach-ctr` | PR (this): `mining/reach_report.py` (YouTube Reporting API reach job, report download with the owner's token), `goal-report.yml` step with `HERO_YT_AUTHORIZED_USER_JSON` via `env:`, `pr-checks.yml` test path. S3 (token only to the Reporting API host), S9 (no token on redirect), S10 (step bounded, never crashes) fixed, S8 hardened. | 2026-10-27 | 0/10 security (none ≥ 8) |
| `studio-mcp` | Unofficial read-only YouTube Studio analytics MCP: `integrations/studio/` client and server, `.mcp.json`, `studio-mcp.yml`, `pr-checks.yml` path, cookie shell hookify rule. Residual S5 (env var visible to the session container) and S6 (egress proxy) recorded; S7 custom range UNVERIFIED until the live check. | 2026-10-27 | 0/9 security (none ≥ 8); 1 hardening applied |

## Proposed, not yet run

| Zone | Argument | Premise to re-verify before starting |
|---|---|---|

## Candidates verified and refused

Written here so they are not rediscovered. A refused candidate without a written reason comes back.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
