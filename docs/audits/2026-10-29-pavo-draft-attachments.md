# E216 — remote DRAFT attachment transfer

The remote consumer was missing despite the existing Pavo upload client. Reuse
that client in an upload-only job of pavo-mcp.yml, with no new scheduler.
The authorized three JPEG candidates from PR536 are already public; no private
original, Library ID or historical package is copied. Unknown generation prompts
remain null. OpenAI provenance and canonical reference hashes remain explicit.

Manual code/security review by this ChatGPT Codex session: input travels through
an environment variable, not shell interpolation. Main-only workflow, serialized
claims, exact local SHA256 validation, fixed CDN/storage hosts, no redirects,
no bearer on PUT/readback. The client permits quote/upload/inspect only; create
and stream are refused. Claims are pushed before effects; a failed push stops
transfer. Any preexisting claim blocks all retries, including uncertain outcomes.
Hash readback is bounded to 15 MiB. Only unsigned public URLs enter receipts.
Receipt push failure retains the prior remote claim and workflow artifact.
Cancellation can leave a claim requiring reconciliation; it never permits replay.

One exact zero quote is required before each upload; there is no generation,
so this operation does not assert generation quota or consume its job ledger.
Receipt means storage transfer only: production qualification, source license,
visual approval and audiovisual review remain pending. Frozen criteria and all
production approvals stay unchanged. No reviewer/model identity is invented.

The Claude-hosted review and security plugins are unavailable in this execution;
this is a manual review, not a claim that those plugins ran. Tests exercise hash,
provenance, null prompts, destination, replay, zero quote, uncertain outcome and
readback failure. The initial adapted fixture lacked its new manifest directory;
it was corrected in test setup before validation. No provider call occurred.

Validation: 85/85 canonical local suites passed. Initially 83 passed; the same
two historical OpenCV import failures passed unchanged in a temporary venv that
exposed the already installed runtime package. Pavo client/video/image tests
also passed (offline). 11 attachment tests passed. git diff --check passed.
Remote checks and actual transfer receipts remain required.
