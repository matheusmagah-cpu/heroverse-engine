# One existing synthetic c01 File, one bounded inference

Prepared for owner request `Sentinel_0212eae8ba548191890633bc89023ab1` (2026-10-16 01:42:19 UTC), following the verified upload and explicit request to continue. This code preparation is not a completed inference or a quality result.

## Narrow manual entry

Use the existing `official-evidence.yml` workflow on private `main` with `av_synthetic_c01=true`, `checkpoint_only=true`, every other optional stage false, and run attempt 1. No new workflow, manager, ledger or scheduler is introduced. The original 09:17 UTC cron and all normal branches remain unchanged. The new stage does not run the public collector, YouTube acquisition, master, asset restoration or cancelled AV recovery. The parent must review the final patch and current gates before dispatch.

The existing `durable_evidence_checkpoint.py claim` owns the run and restores the existing SQL into its existing ephemeral SQLite path. A read-only preflight refuses a missing SQL export, historical-row changes and unresolved claims, so it cannot bootstrap/reset history. The 53 historical AV rows totaling 28,800 seconds on 2026-10-14 must match exactly. The daily local cap remains 28,800 seconds, UTC. Google RPD resets in the Pacific timezone; neither local accounting nor historical UI peaks establishes Google's remaining quota.

## Order and limits

1. Offline tests, exact neutral prompt/captured metadata/provenance checks, current FREE project/no-billing/zero-price policy and internal secret fingerprint match.
2. Existing observer run claim and durable checkpoint of the metadata attempt. One GET of exactly `files/qe6pn3aifbkw`, returning its actual URI. Recheck ACTIVE, exact hash, 19,083 bytes, MP4, six seconds and expiry. No reupload or listing. The saved capture did not contain a URI and is never represented as having done so.
3. Persist preflight in the existing evidence checkpoint. Reserve six seconds using `ExistingObserverLedger.reserve`, which pushes the reservation before authorizing a call. Recheck freshness and expiration after the checkpoint.
4. Exactly one existing transport call to `gemini-3.8-flash`: explicit STATIC, 10 FPS across [0,6], one candidate, maximum 4,096 output tokens, 110-second whole-call deadline (the reused transport's clipped-input socket timeout is 90 seconds). No tools, search, grounding, token-count call, upload, retry or fallback.
5. Preserve failures before reservation too: preparation failures have a redacted local artifact; metadata GET/validation failures are checkpointed in the original evidence directory with one attempted GET and zero generations. No automatic GET retry occurs. Persist the response or terminal failure using the same ledger. Completed means terminal accounting only. Output remains NOT_REVIEWED and NOT_ADJUDICATED with all quality/production/publication authority false. A 429 stops; it never triggers retry/fallback. Uncertain persistence leaves a CLAIMED reservation and blocks another call.
6. Finalize only when no unresolved AV claim exists; preserve observer-state and all original quota/history rows. Terminal reruns replay without another GET or generation.

The request identity binds content hash, exact prompt hash, model and effective processing/generation configuration. It excludes date, run ID, expiring File ID and policy verification time. The actual wire-payload hash and provider-returned URI remain in receipts for audit.

## Prompt and evaluation

Only `fileData` for the uploaded control and the exact frozen evaluator prompt reach Google. No manifest, expected result, labels describing timing, recipe, operator-only data or adjudication is added. The transport response is preserved privately; model statements are claims awaiting independent review, not proof of real audiovisual understanding. This single control cannot establish precision on the other four controls or real reference videos.

## Compatibility caveat

`rest-contract-20261016.json` records the primary sources. Current discovery revision 20261015 and the current guide expose `Part.videoMetadata.fps`, including the range (0,24], and `Part.mediaProcessing=STATIC`. `VideoMetadata` is explicitly deprecated but remains present. No replacement `processingOptions` payload was invented. This is a documented compatibility choice, not a claim that deprecation disappeared or a live validation of acceptance.

## Offline checks

Run from the repository root:

    python3 -m unittest discover -s migration/runtime_bridge -p 'test_synthetic_files_av.py' -v
    python3 -m unittest discover -s migration/runtime_bridge -p 'test_*public_av.py' -v

Fixtures use a fake secret and mock every HTTP call and durable git commit. They exercise the real existing ledger with the historical SQL. Runtime credentials are neither read nor exposed during these tests. No model call, metadata GET, upload, dispatch or commit occurs in preparation.
