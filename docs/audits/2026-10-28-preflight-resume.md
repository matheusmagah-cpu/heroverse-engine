# Preflight voice resume (E211)

Base: `230397ff614a65e6f55706283708f857b7d85898`.

## Reproduction

The old voice step deleted its work directory on every call. The new regression
reproduced two synthesis calls for identical inputs, deletion of retained work,
and replay after an incomplete synthesis. Before the implementation, the six
initial resume tests reported five failures and four missing-receipt subcase
errors. This was a local regression, not a claim about duplicate published videos.

## Fix and manual review

The existing preflight now holds a nonblocking local POSIX lock and preserves its
work. A successful renderer exit, structurally valid PCM/timeline, matching inputs
before/after synthesis, and hashes of the raw output produce an atomic completion
checkpoint. The input binding covers the generated voice script, renderer,
prepared source and models, Python binary/version, installed package bytes and
eSpeak data. Existing bytecode is included because Python's `-B` disables writing,
not reading, cached code. Downstream review/layout changes do
not themselves force new speech synthesis.

A retry verifies the exact receipt, inputs and raw outputs, then reruns the
current layout/compose guards. Previous derived layouts are archived by hash;
an early refusal cannot fall back to an older successful measurement. Changed,
corrupt, partial or unreceipted legacy work is retained and blocked, not adopted
after the fact or silently regenerated. Another active owner is refused. Paths
outside the work root, traversal and unexpected symlinks are refused.

Manual diff/security review: no new provider, network request, secret, scheduler,
approval writer, policy identity or publication action. The raw voice and timeline
are read-only after sealing; layout creates separate derived files. Failed
synthesis keeps its evidence, and a parent interruption cannot silently replay a
child's uncertain result. The checkpoint is a local computation receipt, not a
quality verdict or proof of tamper-resistant storage. No Claude-hosted review
plugin was invoked or claimed. No frozen QA or threshold changed.

## Observed verification

Nine resume tests and the existing sixteen preflight tests pass; the thirteen
error-register tests pass. The real installed runtime input probe completed
without synthesis. During manual review an additional subcase reproduced that
ignoring pre-existing bytecode missed a changed input; it now participates in
the binding. The bytecode mutation test failed before that correction.

A separate one-line engineering diagnostic used real Kokoro, not a mocked voice
renderer. After the bytecode-binding correction, a fresh diagnostic synthesized
and sealed a checkpoint in 21.30 seconds; its retry reused it in 1.80 seconds.
Both calls correctly retained the current
`SHORT_LENGTH` refusal (4.464 seconds versus the production plan's 170-179).
The same checkpoint hash was returned twice:
`8cf465815f5baebb5db10ccfa3a3d6fa3318d97a8f6c7ceb5e94d6b74479ad24`.
Raw voice hash:
`a264ba056be38b68269e41ba55ab82304a6322b990ecd93b63895e217b9bccb6`.
Timeline hash:
`773ea8dcd34fbc0c917e420364cdb6a96aa382f76d43ad76726a92b38488ef9f`.
This is a small cache/retake test, not production, a render, an audiovisual
review, or permission to publish.

Initial canonical validation: all 83 suites passed locally in the existing
isolated validation environment, reporting 1,343 tests in 66.73 seconds.
The 25-test preflight suite passed after the bytecode-binding correction.
Final canonical run after that correction: 83/83 suites, 1,343 reported tests,
74.45 seconds; implementation, test and error-register hashes were unchanged
from start to end of the run. `git diff --check` passed. Remote CI must still
validate the submitted head.

## Remaining boundaries

The pre-existing arc-01 voice has no receipt from its synthesis start and must
not be automatically attested by this change. It remains preserved separately.
Its existing native-speech/media mismatch is not corrected or bypassed here.
Changing preflight code invalidates old report bindings as designed; it never
turns the current blocked arc into a PASS or makes an old Short report current.
This change does not persist work directories between cloud instances or make
the entire ten-stage cycle autonomous. Exact materials, current preflight,
genuine designated audiovisual review and publication read-back remain required.
