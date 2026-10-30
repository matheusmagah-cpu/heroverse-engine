# Native audio/video review evidence

Manual code/security review by Codex. The Claude-hosted review/security plugins
are not available in this runtime; this document does not claim they ran or
approve any media.

The owner explicitly requested the tested Gemini route and authorized publication
on 29 October (America/Sao_Paulo). Two synthetic native-audio samples completed;
one earlier call is uncertain and is not retried or described as passed. The
owner accepted that partial calibration. A sample result is never a master review.

This manual entry point obtains evidence for an existing Bible Short. It does
not add a scheduler, replace a plan, modify the designated identities of other
flows, write approvals, upload to YouTube or change the 9.5 floor/frozen rubric.
The full exact MP4 goes to the official Files API, with native audio and explicit
4-fps static video sampling. This is not a claim of inspecting every 30-fps frame.
The real model identity, provider file hash, full-timeline observations, actual
scores and limitations remain in the receipt for subsequent integration gates.

Security boundaries reviewed: main-only workflow; read-only GitHub token;
existing shared subject concurrency/dispatch guard; all historical runs checked
for exact-content duplicates; no rerun or POST retry after uncertainty; Free Tier
readback <=1 hour and bound to the configured API key hash; strict HTTPS host
allowlists/no redirect; bounded body size; local and provider hashes agree before
inference; background provider ID saved and encrypted artifact uploaded before
GET polling. The resumable upload URL is encrypted before leaving the runner; the caller
sends the exact local bytes directly to Google. Only the API key is a repository
secret and it never leaves the runner. No private media URL is a dispatch input
or log field. The Files API confirms the full input hash and size before inference. No raw API exception/body is logged. Receipt
artifacts are CMS encrypted to an owner-controlled public certificate validated
before upload; the private recovery key stays outside the public repository.
No media, private account identifiers, Library identifiers or plaintext review
receipts are committed or uploaded to public release assets. Completed provider
media is deleted; pending/uncertain operations are preserved for GET recovery.

Validation: nine focused tests cover replay, URL/redirect boundaries, paid/stale
proofs, altered input, uncertain POST, missing audio/timeline coverage, encryption
roundtrip, exact native-video request and durable interaction ID, and workflow
privacy. Dispatch guard tests pass. All 87 canonical suites pass locally. Four initially lacked clone history or
OpenCV in the isolated interpreter; after restoring history and the dependency,
only those four were rerun, without source changes to the tested modules.
No FFmpeg command or renderer changed.
