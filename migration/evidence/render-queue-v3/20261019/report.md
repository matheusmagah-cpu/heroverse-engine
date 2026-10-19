# Current-standard render readiness

The real005/006/007 files reproduce the deadlock: script_sha matches the recorded manifest, but QA is v2. The old due() marked these rendered while reconcile refused their non-v3 QA. They could neither render again nor proceed.

current_render now recognizes only a current script, valid matching output SHA, frozen v3 version/hash and completed QA status PASS or FAIL. Missing/malformed/unknown/legacy/stale evidence is incomplete. A completed v3 FAIL remains rendered to avoid repeatedly producing the same failing artifact; reconcile still requires PASS. This is render-completion state, never approval or creative qualification.

At fixed2026-10-19T23:10:00Z with48h horizon, the real queue now contains005,006,007 in schedule order, each images-complete/rendered=false. Pilot012 is excluded by the existing uploaded ledger. The source scripts, schedules, QA, manifests, frozen criteria, ledger and runner retry controller are unchanged, with hashes in queue-snapshot.json.

13 queue tests and11 runner-dispatch tests PASS. All37 CI scripts personally run locally PASS. Existing publication hold, horizon, six-hour tolerance, earliest approval, long-before-Shorts priority, quota wait/retry controls and uploaded exclusions remain intact. No workflow or production file changed; no dispatch or publication occurred. The next long must still pass actual v3 QA and designated watched review; software tests alone do not establish audiovisual quality.

Remote byte verification, final CI and independent review are recorded on the PR before integration.
