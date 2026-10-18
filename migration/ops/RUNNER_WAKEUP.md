# Engine → runner wake-up

The existing engine heartbeat (`11,41 * * * *`, UTC) now has an independent
`runner-wake` job. It runs even if the daily engine scheduler has nothing due
or fails. This removes the need for an assistant session to request a render.
GitHub schedules may still be delayed/dropped: this is a redundant wake-up,
not an exact timer or availability guarantee. The runner's `13,43` cron remains.

## Deployment order

1. Merge the runner change adding optional `dispatch_key` and its opaque run name.
   Existing cron/manual execution, empty `pilot`, concurrency and gates are unchanged.
2. User installs `HERO_RUNNER_PAT` as an Actions secret in the **private engine**:
   fine-grained, only `heroverse-runner`, Actions read/write, one-year expiry.
   No token belongs in Git, logs, artifacts, inputs, or this document.
3. Merge the engine change. Do not dispatch a real workflow while provisioning.
   Check the next normal heartbeat's `runner-wake` summary and runner history.

`HERO_RUNNER_PAT` is scoped to the one dispatch step; checkout has no persisted
credential and the engine scheduler keeps using its own `github.token`.
Missing token fails the job clearly, including when the queue is empty. API,
credential, invalid queue/history and truncated pagination errors fail closed.
`DISPATCH_ACCEPTED` means only HTTP 204, never render success or approval.

## Decision and bounds

Use the unchanged `render_queue.due` policy: publish within 48 h (including its
existing 6 h look-back), images complete, no manifest for current script, not
already published. A candidate key is SHA-256(pilot name + NUL + script bytes).
Only this opaque key appears in the public runner's run name. It is a correlation
hint, **not** an approval, file-integrity proof, or authoritative selected pilot.
The runner rechecks current engine `main` and chooses its own next pilot; no
explicit `pilot` is sent. Queue movement between these checks remains possible.

All active states (including queued/waiting) block dispatch regardless of age.
Recent completed runs allow five minutes for settlement. Attempts with the same
key back off 45 minutes, with at most three observed dispatches per rolling 24 h.
A different artifact can proceed after settlement: there is no global renders/day
cap. Cron/manual runs without the key are not charged against this retry budget.
These bounds apply to this integration, not to the existing independent cron.
History is paginated to 1,000 rows; incomplete/invalid history blocks dispatch.
POST is not retried within a heartbeat, even on an uncertain response; later
heartbeats inspect actual history again before deciding.

The engine heartbeat concurrency serializes its own wake-ups. A runner cron can
still race the API check/dispatch; no cross-repository atomic lock is claimed.
Existing runner `heroverse-render`, `cancel-in-progress: false`, and its fresh
queue/manifest check serialize and skip already-rendered work. No mining, QA,
publication gate, paid service, cost policy or rendering behavior is changed.

## Offline checks

```
python3 -I -B migration/ops/test_runner_dispatch.py
python3 -I -B migration/production/test_render_queue.py
python3 -I -B migration/ops/test_heartbeat.py
```

Rollback: remove only `runner-wake` job (or revert engine integration). The
original heartbeat and runner cron remain operational. Optional runner input can
remain; remove it only after reverting engine dispatch code. Secret rotation or
revocation is performed by the user, not by code in this integration.
