# Qualified plan to existing build: E213

Base: main `fd255c40895d2319b38418fd7fab37f4f265d14f`.

Observed runner `40775683203` exited QUEUE_EMPTY and skipped rendering. Its pilot
queue is not the Bible-plan queue. The heartbeat did not invoke episode/long-build
for a plan that eventually becomes qualified. Discovery alone did not close this.

The existing heartbeat now has an independent qualified-production job. It uses
the existing strict plan checks, exact preflight verification, Short ordering and
long publication-input check. It skips ledger identities and episode records,
holds active build/probe runs, evidence branches and prior inflight/done requests,
and writes at most one pending request. A failed queue push never produces the
ready output. The same requests.yml is called as a reusable workflow; its durable
claim must still be pushed before the actual dispatch POST. No new clock or ledger.

Tests reproduced missing wiring before the workflow change. Twelve offline bridge
tests cover readiness, blockers, evidence/active holds, pending reuse, claims,
incomplete run history and failed persistence. Eight existing dispatcher tests
still exercise claim-before-POST, crash/uncertain response and no replay. No live
generation, approval or publication is part of these tests.

Final local canonical validation: 84/84 suites PASS in 98.27 seconds. The first
integrated run passed 83/84: the unchanged discovery-isolation test's job boundary
also included the newly inserted writable jobs. Move those jobs before discovery,
preserving its read-only permissions and every original assertion; its five tests
and the final complete run pass. Remote CI remains required on the exact head.

Manual security/diff review of workflow and repository-write boundary: no provider
secret, new dependency, input interpolation or arbitrary workflow is introduced.
Only fixed episode/long-build destinations and regular validated plan paths are
produced. The existing dispatcher remains the sole submitter; uncertain history
fails closed. Permissions are scoped to the queue-producing job and the existing
dispatcher. The review/discovery job remains read-only. No unavailable automated
security-review plugin is claimed.

Limits: this is the ready-plan -> build transition, not ten-stage certification.
Blocked materials/preflight still block. The current Work session did not qualify
for perceptual audio review; no reviewer identity, score, criterion or approval is
changed. Historical evidence branches stop automation until genuinely reconciled.
Failure/resume after a claimed build is explicit, not automatic regeneration.
