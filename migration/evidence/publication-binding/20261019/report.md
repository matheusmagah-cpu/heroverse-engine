# Fail-closed publication binding

The old workflow only loaded the final gate when reviewer began with `HeroVerse automatic gates`. The current approval writer uses `HeroVerse three-stage approval`, so that defensive check was skipped. This was a real branching defect; pilot012 nevertheless has a genuine matching PASS gate, and this report does not claim an improper upload occurred.

The workflow now always invokes a pure helper before preflight/upload. QA PASS, strict boolean approval, four valid matching SHA256 values, gate PASS/eligibility and internally consistent nonempty PASS dimensions/items are required for every reviewer identity. Missing/malformed/FAIL/UNKNOWN/stale evidence fails closed. Checks remain active under Python -O. No reviewer/manual exception remains.

Only the Gates inline Python was replaced. Triggers, permissions, credentials references, pilot validation, publication hold, concurrency, schedules, upload/resume, Shorts and cleanup remain unchanged. No actual APPROVAL, QA, manifest or gate file was modified. This validates recorded evidence binding; it does not replace the upstream perceptual review, recalculate its rubric, or qualify a new render.

17 new tests PASS. All37 CI test scripts were personally run locally and pass. The actual pilot012 documents pass with output SHA82276559bdfdb5600e7e0ae13b5e7b337611fdacf0d2c2cc25d3533957e9dbfe. Integrity hashes are in verification.json. Final remote byte verification, exact-SHA CI and independent review are reported on the PR before integration.

Independent-review correction: canonical dimensions and static QA/review/binding/scorecard rows are derived from prepublish_gate definitions and required, not merely a nonempty self-consistent subset. All14 v3 dimensions are individually deletion-tested. Unknown QA criteria versions fail. An existing review document must still be PASS and hash-bound. The parser retains the existing v2 schema for compatibility; this is not authorization to publish legacy v2 manually. Planned production validation remains v3-only.
