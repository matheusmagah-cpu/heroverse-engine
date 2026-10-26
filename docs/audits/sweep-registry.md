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

## Proposed, not yet run

| Zone | Argument | Premise to re-verify before starting |
|---|---|---|

## Candidates verified and refused

Written here so they are not rediscovered. A refused candidate without a written reason comes back.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
