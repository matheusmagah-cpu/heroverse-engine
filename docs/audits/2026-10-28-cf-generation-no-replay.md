# E214: image-generation POSTs are not safe retries

Base: `1c7cf75606b51bb2cdb8e808c037b691c5432933`.

The pending Short09 material acquisition was inspected before another provider
request. `cf_images.run` retried the same generation POST four times on an HTTP
error. A lost or 5xx acknowledgement does not establish that no generation ran.

The new offline regression failed before the fix for all eight HTTP statuses
tested (400, 401, 403, 408, 500, 502, 503, 504): four calls instead of one. Three
transport/response cases also failed the local sanitized-error contract. No live
generation was used to reproduce this and no duplicate historical output is
claimed.

The fix removes the retry loop. The error now explicitly requires reconciliation
without replay, and does not include the provider response body. HTTP allocation
deferral remains supported. Successful direct-image and JSON/base64 responses
still pass; the existing E62 test preserves images made before allocation ends.
The four focused tests pass after the fix, including their subcases. The first
canonical run passed 83/84 suites: refusal parity correctly required registration
of the new uncertain-outcome code and removal of two retired codes. That registry
now classifies reconciliation as an external condition, never an automatic retry.
Final canonical and remote CI results must be recorded separately before integration.

Manual diff/security review: only the generator, its offline tests, refusal
classification, E214, this audit and the bounded request below change. There is no
credential export, new host, scheduler, approval writer, identity change, quota
increase or weakened QA. An
unknown result remains unresolved; a new invocation is not an automatic retry.
No unavailable review plugin or perceptual review is claimed.

This patch fixes acquisition safety, not the missing source approvals or the
session's unsupported audio input. It does not make a DRAFT source publishable.

## Bounded material request

The owner explicitly requested completion of the missing materials. One existing
`scene-stills.yml` request asks for a single candidate for each of three unmade
shots: `s-noah-door`, `s-rock`, `s-noah-lamp`. No new scheduler or provider bridge
is added. These non-speaking shots use the existing free FLUX route, not Pavo or
Buzzy credits. Existing footage was checked first; it does not show these actions.
The material preflight (`scene_stills.prepare`) accepted their current registered
prompts with no prop-reference requirement. This is not a build preflight PASS.

Main's candidates and 167 candidate metadata records on the one remote
`claude/stills-genesis-09-*` branch were reconciled: none belongs to these three
shots. The other rejected candidates are not resubmitted. The request is for the
UTC day after the recorded allocation exhaustion, and the existing live dispatch
guard must still accept its inputs, prior-failure dependency fix, capacity and
daily allocation before any provider call. Reset time is not proof of success.
An allocation refusal stops the run; no paid fallback is enabled.

The request goes through the existing durable claim dispatcher only after merge.
Monitor its exact run and candidate IDs. A missing acknowledgement is never
permission to repeat it. Every output stays DRAFT for genuine qualified review;
no approval, score, generation success or publication is asserted by this request.
