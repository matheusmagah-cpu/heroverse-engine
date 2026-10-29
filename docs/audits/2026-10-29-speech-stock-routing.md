# E218 — Pavo speech and licensed stock routing

Manual code/security review by this ChatGPT Codex session. The Claude-hosted
pr-review-toolkit and verified-security-sweep plugins are unavailable here;
this document does not claim either plugin ran or grant media approval.

The opt-in source policy is set on the five active plans. Allocation and the
two provider generation entry points agree: new on-camera talking clips use
Pavo; other new pictures go through licensed footage selection. Valid old
approvals remain readable. Existing matching clips are reconciled before a
new fallback is selected. The assembly step only consumes approved bytes and
does not use these generation entry points. Unknown policies fail closed.

The sources report now verifies a fallback's request digest instead of treating
every fallback record as ready. Still approval cannot silently replace the
new policy. Character/period/rights restrictions and actual designated review
remain required. Frozen QA, reviewer identities and approval writers are
unchanged. No credentials, network endpoints or publication permissions added.

Validation: all 85 canonical suites passed across the full run and two focused
reruns. The initial run passed 83 suites; two fixtures still asserted the
superseded 28 October still exception/date. The historical still fixture now
explicitly opts into its historical policy; the calendar assertion expects the
owner's 29 October recovery target. Those suites pass with 46 and 20 tests.
Eight routing regressions cover quota, voice-over, character refusals, existing
clips, provider boundaries, invalid policy, stale digest and still refusal.
No FFmpeg command changed. git diff --check passed.

Concurrent PR539 already integrated the same date correction plus the complete
recovery calendar/report. PR540 preserves those main09e982a6 versions, drops
duplicate historical-guide edits and retains only source routing and its bounded
stock acquisition. No private material is introduced into the public repository.

The bounded stock request uses the existing free footage workflow, two retained
candidates per query and existing page/hash deduplication. It does not approve
or publish results. Scene suitability must be checked on actual footage and
the final portrait crop, not inferred from query words or automatic vetting.
