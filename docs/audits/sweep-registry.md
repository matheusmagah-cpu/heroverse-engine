# Sweep registry: what exists, what ran, what it is worth

Proposals for sweeps are written here, not in conversation. The `Last run` column is derived from report filenames
by the skill's `scripts/sweep_status.py`; the other columns are written by hand.

## Candidates

| Zone | Argument | Last run | Yield |
|---|---|---|---|
| `workflows-secrets` | `.github/workflows/*.yml`: 18 of 27 workflows read secrets; dispatch inputs and the runner PAT. Not covered: the runner repository itself. | - | - |
| `publish-gate` | `migration/publish/` (`prepublish_gate.py`, `publication_binding.py`, `publish_*.py`): the owner's floor, money-equivalent. | - | - |
| `fresh-code` | Code shipped in the last 3 days; highest churn. | - | - |

## Proposed, not yet run

| Zone | Argument | Premise to re-verify before starting |
|---|---|---|

## Candidates verified and refused

Written here so they are not rediscovered. A refused candidate without a written reason comes back.

| Zone | Reason |
|---|---|
| `oauth-compliance` | heroverse-oauth-compliance holds only static HTML (privacy, terms); no code or credentials. |
