# Pending second-report implementation for review

Local only. No commit, dispatch, OAuth or Reporting request performed in this revision.

## Scope and safeguards

The snapshot still identifies the original two reports, but FETCH_REPORT_IDS is exclusively ('20613781334',). Collection, ReportService, transport metadata/CSV allowlists, resource verification and download URL validation reject already-received 17695215035. Workflow no longer lists the first CSV as an upload input. No job creation/listing or public metadata collection exists.

Only run4/attempt1 is admitted. Private exact repository/main guards remain before credentials and upload. Each stage is limited to one operation, for a maximum of three: one refresh, one exact existing-report metadata GET, one CSV GET. CSV limit4MiB,20krows,90s. No retries, redirects, proxy forwarding, new scopes or credential persistence. Existing lightweight resource limits remain unchanged. Data API calls/units remain zero with no ledger edits.

All three historical execution receipts are hash-bound. Third execution and collection receipts are preserved byte-for-byte: third run is explicitly three HTTP200 network operations, whereas first and second are zero. The preserved collection receipt binds report17695215035, its 236 bytes and SHA256, and CSV_DATE_INVALID. No previous failure is rewritten into a success. No raw CSV is proposed for Git.

## Parser and CTR

Parser accepts only exact ASCII YYYYMMDD observed from the real provider, or exact ISO YYYY-MM-DD. Invalid calendar dates and dates outside the exact Pacific report interval fail. Raw provider date/CTR strings are untouched. Composite date/channel/video keys canonicalize dates to reject duplicate alternate encodings.

New receipts label CTR provider_raw_representation_unverified. No percent/proportion conversion, inferred clicks or aggregate CTR is produced. Raw1 remains raw1. The original third collection receipt retains its older label as historical immutable evidence only.

## Complete offline preflight

Reconstructed 14 checkout source/evidence files at immutable cfe8a2d6c617b4cbe3544127945b0523d05a5601 using saved exact remote content, then independently matched each Git blob against a fresh recursive tree from that commit. Includes original snapshot, both real auth helpers, all source/test/workflow files and prior receipts. Base proof is base-byte-proof.json. No LF normalization.

48 tests pass in checkout layout with global socket/urllib network guard and zero guard hits. Includes actual auth-helper imports/config checks using synthetic credentials, all snapshot/helper/receipt pins, complete synthetic main path, exact three-operation counts, single CSV output, first-report rejection at every network layer, repeated-request caps, third-receipt tampering, workflow private/main/run4 guards, strict compact dates, Pacific bounds and duplicate canonical keys.

Additionally parsed the already-preserved actual 236-byte CSV with the final candidate parser: three rows recovered, exact hash/date/CTR strings preserved, no live requests. actual-csv-offline-proof.json records this; raw input remains in the private local artifact directory. Parser source AST validation passed. tests.txt contains the full suite output; manifest.json and proposal.patch identify exactly ten changed/new paths.

## Remaining uncertainty

The first report has already proved refresh and existing-job report download access. The second report's present availability, response body and schema remain unobserved. Its permitted interval is 2026-10-12T07:00:00Z through 2026-10-13T07:00:00Z, exclusive end, created2026-10-14T05:30:29.360021Z. Any received bytes will be preserved before parse; parse recovery must use those bytes, never repeat a successful download. After retrieval, combine the two reports only offline and retain distinct receipt provenance.
