# DataFanatic metadata preflight (OFFLINE STAGING ONLY)

Prepared in a separate folder; no HeroVerse source was changed. No API request,
subscription, checkout, workflow dispatch, commit, or push was performed here.

## Intended scope

One GET JSON metadata request to the official endpoint and preregistered source
in `request.json`. Expected source duration is 12,708 seconds. The observed GUI
configuration is `urlAccess=normal`, expected to consume 3 quota units. This is
an expectation from the supplied GUI evidence, not measured usage. Basic's supplied
terms are $0/month, 100 requests hard limit, 10 GiB bandwidth, and $0.001/MB
bandwidth overage. The bandwidth recurring gate remains BLOCKED; this probe does
not approve permanent adoption or change billing.

Before publication/execution, root must review the current HeroVerse HEAD (the
parent provided c20ece9, with another change in progress), reconcile file paths,
verify private repository status, obtain explicit subscription approval, verify
activation, and approve the one JSON query. This staged workflow is not installed.
Do not copy a secret into source. The workflow references only the existing
`HERO_RAPIDAPI_KEY` GitHub secret.

## Installation review

Candidate files: `migration/diagnostics/datafanatic-native-av/{probe.py,test_probe.py,request.json,README.md}`, `.github/workflows/datafanatic-json-once.yml`. Keep response and
artifact files out of Git. Preserve existing producer/supervisor OFF status.
The workflow is manual-only, contents-read-only, private-repository-only, two
minutes maximum, first workflow run and first attempt only. An invalid first
run deliberately burns the first-run guard. Never rename/delete/recreate the
workflow to bypass the one-shot control. Concurrency serializes runs. The local
exclusive claim is written before transport; any uncertain result means stop
and inspect, never rerun. Distributed exactly-once delivery cannot be proven by
these controls if an operator replaces the workflow or executes outside it.

## What the response means

Full valid JSON is retained only in the private temporary artifact, unless the
credential is reflected (including JSON-escaped reflection), an access challenge
is recognized, or validation fails before persistence. HTTP error bodies are not
read or persisted. URLs never appear in stdout; unknown object keys are hashed,
known keys are allowlisted, and string values are never included. The receipt
contains structure, types/counts, candidate ID/duration checks, and only integer
values from the explicit quota-header allowlist.

The traversal recognizes candidate `videoId`/`video_id` and
`duration`/`durationSeconds`/`lengthSeconds` fields anywhere in JSON. It does not
assume any response wrapper or claim generic `id` means source ID. A missing
field stays unverified. A duration with another format stays unverified; nested
related entities may produce mismatches. A match is not schema equivalence.
The private artifact requires human inspection to identify actual source fields,
confirm duration, and locate native URLs with audio/video characteristics.
No URLs are fetched, and no media, transcoding, clipping, merging, cookies, proxy
configuration changes, or alternate network routes are attempted.

One application response-body read requests at most 1 MiB. Exactly-limit bodies
are rejected without an extra read. This does NOT bound headers, TLS/network
buffering, provider-side processing, or provider-billed bandwidth. A 30-second
process alarm bounds the request and local processing. The workflow upload uses
one-day retention and a checked aggregate file-size limit of 2 MiB; this is local
artifact size, not provider billing evidence. The upload requires that size check
to succeed. Artifacts are repository-private, not owner-only: existing repository
readers may access them. Verify those readers are authorized before execution.

## Offline tests

Run only `python3 -m unittest discover -s migration/diagnostics/datafanatic-native-av -p 'test_probe.py'`.
All transport objects are fixtures; tests make no network calls and do not read
the real secret. Synthetic quota headers never count as proof of consumed quota.
`test-results.txt` records the offline result. Do not run the probe entrypoint
until authorization and subscription activation have both been verified.

HTTP errors retain the numeric status and allowlisted integer quota headers in
a sanitized failure receipt, plus one attempted request, zero media requests,
zero native-response files, and explicit uncertainty. Error bodies are never read.
Only repository matheusmagah-cpu/heroverse-engine is accepted by both script and workflow.
