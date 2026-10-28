# Verified security sweep: slim-system-2, 2026-10-28

## Context

Scope: the PR on branch `claude/slim-system-2` (owner 28/10: "enxuga o sistema ... sem retrabalho"; the DECIDE items of
`migration/evidence/audits/20261028-slim.md`, approved by the coordinator).
- Workflows deleted: `shorts.yml` (`HERO_GEMINI_API_KEY`), `shorts-review.yml` (`HERO_GEMINI_API_KEY`),
  `publish-shorts.yml` (`HERO_YT_AUTHORIZED_USER_JSON`, `contents: write`), `voice-sample.yml` (no secret,
  `contents: read`), `agnes-clip.yml` (`AGNES_API_KEY`).
- Workflows edited: `approve.yml` (its last step, which dispatched `shorts.yml`, removed), `publish.yml` (the Shorts
  step, which held `HERO_YT_AUTHORIZED_USER_JSON` and ran `publish_shorts.py`, removed), `reconcile.yml` (the `shorts`
  dispatch removed), `heartbeat.yml` (the `pending_shorts.py` input and the `shorts_pending` flag removed; comment),
  `pr-checks.yml` (test list).
- Code: the prayer Shorts-from-long modules and tests deleted (`shorts_produce.py`, `shorts_006_*`,
  `publish_shorts.py`, `review_recovery.py`, `shorts_prerequisite.py`); `pending_shorts.py` keeps only the slot rule
  (E01/E02); `render_queue.py` reconcile no longer prints `shorts PILOT`; `dispatch_guard.py` loses `agnes-clip.yml`;
  `ops/heartbeat.py` loses the `publish-shorts.yml` and `channel-privacy.yml` tasks; `project_map.py` skips
  `migration/evidence/` in "not reached"; `refusal_registry.json` drops 19 codes no later stage raises any more.
- Unchanged: `prepublish_gate.py`, `publication_binding.py`, `publish_video.py`, `publish_episode.py`, `preflight.py`,
  `owner_quality_policy.py`, every frozen QA file, `ERRORS.json`.

Trigger: the PR touches `.github/workflows/` and `migration/publish/` (CLAUDE.md: a recorded sweep).

## Delegation

The implementing agent ran the sweep itself. Categories: secret reach after the change, a remaining caller of a
deleted workflow or module (fail-open dispatch), guard coverage of `workflow_dispatch` workflows, publish-gate
integrity (approve → prepublish_gate → publish, publish-episode), the scheduler's condition inputs, and the owner's
publication hold.

## Verification

| Finding | Zone | Verdict | Claimed | Verified | Reservations | Proof |
|---|---|---|---|---|---|---|
| S1 a dispatcher still names a deleted workflow | slim-system-2 | FALSE POSITIVE | < 8 | Yes | `approve.yml`, `reconcile.yml` and `ops/heartbeat.py` no longer name `shorts.yml` / `publish-shorts.yml`; no `gh workflow run` line names a deleted file; `migration/requests/` holds only `done/` requests. | `test_errors_register.test_heartbeat_dispatches_only_existing_workflows`; `test_render_queue` (no `shorts` line); search of `.github/` and `migration/` |
| S2 secrets lose a consumer or move | slim-system-2 | FALSE POSITIVE | < 8 | Yes | Three secret-holding jobs and one secret-holding step are gone; no secret added, renamed or moved. `AGNES_API_KEY` has no consumer left (the owner may delete it from the repository secrets). | `git diff origin/main -- .github/` |
| S3 the dispatch guard's coverage shrinks | slim-system-2 | FALSE POSITIVE | < 8 | Yes | Only `agnes-clip.yml` (deleted) left `WORKFLOWS`; EXEMPT lost only deleted workflows (`reviewer-calibration.yml` stays exempt, kept for E59); `test_dispatch_guard` still fails a new unguarded `workflow_dispatch` workflow. | `ops/test_dispatch_guard.py` |
| S4 the long's or the episode's publish path changed | slim-system-2 | FALSE POSITIVE | < 8 | Yes | `approve.yml` keeps every gate and the owner floor (E65) and still dispatches `publish.yml`; `publish.yml` keeps hold, binding, preflight, upload and release cleanup; `publish-episode.yml` is untouched. `publish.yml`'s `venv` step is unchanged and its only consumer is now `publish_video.py`. | `test_errors_register` (E50, E65), `test_release_video`, `publish/test_*.py` |
| S5 the reconcile queue changes what it retries | slim-system-2 | FALSE POSITIVE | < 8 | Yes | Only the `shorts` output left; approve (one, earliest: E25), publish, comment (E61), episode (E70) and the spent-quota wait (E29) are unchanged. | `production/test_render_queue.py` |
| S6 the heartbeat reads a condition at the wrong index | slim-system-2 | FALSE POSITIVE | < 8 | Yes | The condition builder lost one input; each flag is read at its own index on real files. | `ops/test_heartbeat.test_condition_builder_reads_every_input_at_its_own_index`, E90's antidote |
| S7 the publication hold stops less | slim-system-2 | FALSE POSITIVE | < 8 | Yes | `approve.yml`, `publish.yml`, `render_queue.py reconcile`, the heartbeat's TikTok and arc-links inputs keep their `PUBLICATION_HOLD` checks. | `test_render_queue.test_publication_hold_dispatches_nothing` |

0 of 7 claimed findings at 8 or above; the change removes attack surface (three secret-holding workflows, one
secret-holding publish step, one unused third-party API key consumer).
