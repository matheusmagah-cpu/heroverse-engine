# Verified security sweep: slim-system, 2026-10-28

## Context

Scope: the PR on branch `claude/slim-system` (owner 28/10: "enxuga o sistema"; audit
`migration/evidence/audits/20261028-slim.md`).
- Workflows deleted: `.github/workflows/description-refresh.yml` (one-off pilot-012 chapter repair; `contents: write`,
  `HERO_YT_AUTHORIZED_USER_JSON`) and `.github/workflows/reviewer-probe.yml` (E58 Gemini probe; `contents: write`,
  `HERO_GEMINI_API_KEY`).
- Code deleted: `publish/refresh_description.py` and its test, `ops/reviewer_probe.py`, `bible/rekey_shots_e118.py`,
  `diagnostics/rapidapi-mcp/` and `diagnostics/rapidapi-native-av/{native_probe,preflight}.py`.
- `ops/test_dispatch_guard.py`: the two deleted workflows leave the EXEMPT table. Docs only otherwise.

Trigger: the PR touches `.github/workflows/` (CLAUDE.md: a recorded sweep for workflow changes).

## Delegation

The coordinating agent ran the sweep itself. Categories: secret reach after the change, a remaining caller of a
deleted path (a dispatch or `requests.yml` request that would now fail open), guard coverage of `workflow_dispatch`
workflows, and publish-gate integrity.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 a dispatcher still names a deleted workflow | slim-system | FALSE POSITIVE | < 8 | Yes | Neither file is in `ops/heartbeat.py` TASKS, `reconcile.yml`, `approve.yml` or any `gh workflow run` line; a `requests.yml` request naming a deleted file only logs `gh`'s 404 and runs nothing (no gate or secret is reached). | `test_errors_register.test_heartbeat_dispatches_only_existing_workflows`; search of `.github/` and `migration/` |
| S2 secrets lose a consumer or move | slim-system | FALSE POSITIVE | < 8 | Yes | Two `contents: write` jobs holding the YouTube and Gemini secrets are gone; no secret was added, renamed or moved to another step. `HERO_RAPIDAPI_KEY` had no workflow consumer before this PR. | `git diff origin/main -- .github/` (deletions only) |
| S3 the dispatch guard's coverage shrinks | slim-system | FALSE POSITIVE | < 8 | Yes | Only exemptions of deleted workflows were removed; `test_dispatch_guard` still fails a new unguarded `workflow_dispatch` workflow. | `ops/test_dispatch_guard.py` EXEMPT |
| S4 a publish path depended on a deleted module | slim-system | FALSE POSITIVE | < 8 | Yes | `refresh_description.py` was imported only by its own test and workflow; `publish_video.py`, `preflight.py`, `prepublish_gate.py`, `publication_binding.py` are unchanged; E52's antidote `test_package_chapters.py` stays. | `publish/test_*.py` in pr-checks |

0 of 4 claimed findings at 8 or above; the change removes attack surface (two write-scoped, secret-holding workflows).
