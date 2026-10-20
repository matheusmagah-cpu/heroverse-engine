# Shorts phase 1: structural plans, not qualified media

Refs #231. SPEC v3. Implementation and local acceptance are complete. Remote CI and final independent review are recorded against the delivered SHA in the PR/issue, not inferred from this report.

## Provenance and scope

Baseline: `7fb9e9e1fad9396b80c029212f0a3144c1428d51`. The six dated fixture files are exact copies of the baseline's pilot-005 and pilot-006 script, timeline and Shorts records. `phase1-inputs.json` records their SHA256 hashes, fifteen frozen-file hashes and four reviewer AST hashes. The existing undated historical fixture is unchanged.

Claim: 2026-10-20T16:36:45Z. Draft: https://github.com/matheusmagah-cpu/heroverse-engine/pull/251 . This phase does not close #231.

Implemented scope: deterministic structural opening and ending checks; whole referenced segments; source reconstruction before production; explicitly provider-free measured-only planning; strictly categorical failure evidence. Helper concepts are reused from PR204, without its intrashot changes or mutable-pilot tests. No workflow trigger, permission, schedule, retry or publication-selection change is included. The workflow diff only adds the new test file to its existing test loop.

## Measured plans

Commands, executed locally without provider or render:

```
python3 -I -B migration/production/shorts_select.py migration/production/fixtures/shorts-pilot-005-20261020/out/timeline.json migration/production/fixtures/shorts-pilot-005-20261020/script.json migration/evidence/shorts-v2/pilot-005-candidates.json --measured-only
python3 -I -B migration/production/shorts_select.py migration/production/fixtures/shorts-pilot-006-20261020/out/timeline.json migration/production/fixtures/shorts-pilot-006-20261020/script.json migration/evidence/shorts-v2/pilot-006-candidates.json --measured-only
```

Pilot 005: 331 opening starts, 63 structurally eligible starts, 354 eligible-length pairs, 54 accepted structural pairs. Three nonoverlapping plans selected by deterministic score: 563.353–602.745, 1088.684–1135.949, 1393.612–1440.736 seconds.

Pilot 006: 364 opening starts, 77 structurally eligible starts, 442 eligible-length pairs, 82 accepted structural pairs. Three nonoverlapping plans selected: 706.625–757.141, 240.169–278.997, 1311.607–1346.297 seconds. Full text, counts, reasons and exact input hashes are in the candidate JSON files. These are plans, not accepted Shorts.

## Editorial assessment of text only

The temporary technical direction reviewed the 005 texts independently of the ranking. The three ranked hooks are not selected editorially: “The armour is his, not yours.” has an antecedent-dependent pronoun; “Peace on your feet.” is fragmentary; “Thy going out and thy coming” is a truncated fragment. The frozen structural heuristic intentionally does not claim general grammar or semantic comprehension. Its numerical ranking must not be presented as editorial approval.

The preferred text-only candidate is 459.860–499.672 (39.812 seconds before the unchanged 0.5 second tail). It passed the initial structural validator and contains:

> Lord, protect my relationships. Guard marriages from coldness and from anything that would divide them. Protect friendships from gossip and misunderstanding. Where there is tension, bring honest conversations and quick forgiveness. Let love win in every home today. Father, set a guard over my mouth today. Protect me from words I would regret: harsh words, careless words, words spoken in anger. Let what I say build people up. Let my words carry your peace into every room I enter.

This has a coherent relationships-and-speech theme, an autonomous prayer opening and a complete closing sentence. It contains no partial Scripture, channel CTA, or promise of money or healing. This assessment does not qualify the actual narration, pictures, rhythm, ending or loop. The algorithm was not altered to force this candidate to win. Phase 2 must define and verify any explicit editorial selection and real-media execution.

## Unresolved media and original failure evidence

Visual rhythm remains unresolved: current rendering uses 15–18 second scenes. Actual acoustic onset, audiovisual ending and loop are unknown. `technical_qa=null` and `watched_review=null` for these plans; no new video bytes exist in this phase.

The historical 005 short-00 output SHA256 is `eb0646b09bd28a0623dcc32bdfe69aa3959111f522aff1f5797876f66caba74c`: technical QA passed but watched review failed rhythm 5, ending/loop 5.5 and overall 7.2. Short-01 SHA256 `19b9569e93d53d71e9d22026e4a0384414abcddf538bac1d3aa1b3c01273d8b7` failed hook 5, rhythm 5.5, ending 6 and overall 7.1. Prior reviewer findings include a context-dependent opening, long held images and an unresolved ending. Those failures are not erased by this patch.

005 short-02 and all three historical 006 Shorts have `NOT_REVIEWED_ProviderFailure`. Their underlying HTTP causes are unknown: the old code discarded them. Neither workflow success nor a guessed 503 establishes review acceptance. Existing `structure_mining.call` already handles up to two attempts per 503/model; this phase adds no retry.

## Acceptance status

Initial checks: card_check printed `CARD_OK`; test_no_live_pilot_data ran 4 tests, `OK`; git diff --check returned exit 0. All fifteen frozen-file SHA256 values and four reviewer AST hashes matched the pinned inventory. The diagnostic suite ran 20 tests, `OK`; the error-register suite ran 3 tests, `OK`. A baseline-vs-patch reviewer harness printed `BASELINE` with categorical error, actual output hash and preserved prior FAIL all false, `PATCH` with all three true, then `REGRESSION: BASELINE_FAIL_PATCH_PASS`.

`python3 -I -B /tmp/231-selector-antidote.py` compared the pinned baseline and patch on three synthetic negative answers. Dependent reference: old accepted 1, patch 0. Overlong opening: old 1, patch 0. Unresolved ending: old 2, patch 0. The first harness run expected only one old result in the last case; that expectation failed and was corrected to two after inspecting the old enumeration. It was not reported as a pass before correction.

Independent code review reproduced and closed a direct-entry escape: forged script_refs could remove a Scripture reference despite the producer receiving the authoritative script. The producer now derives authoritative refs and rejects `SOURCE_REFS_MISMATCH` before any rendering helper. Correct refs reject the partial cut as `PARTIAL_SCRIPTURE`. Both cases now have zero mocked rendering calls. Candidate top-level text is also reconstructed from source, not retained from untrusted metadata.

Local acceptance completed at 2026-10-20 16:47 UTC:

- `python3 -I -B migration/production/test_shorts_produce.py`: 45 tests, OK. The historical OFFLINE + RECORDED media-helper coverage is retained, alongside explicit negative and synthetic positive cases.
- `python3 -I -B migration/production/test_shorts_review.py`: 20 tests, OK.
- `python3 -I -B migration/production/test_no_live_pilot_data.py`: 4 tests, OK.
- `python3 -I -B migration/ops/test_errors_register.py`: 3 tests, OK.
- `PATH=/tmp/hv228-venv/bin:$PATH RUNNER_TEMP=/tmp/231-tests bash /tmp/231-all-tests.sh`: all 43 test files PASS, exit 0. This is the existing PR loop with only test_shorts_review.py added. Synthetic test fixtures are not production renders or media qualification.
- `python3 -I -B migration/ops/card_check.py ../heroverse-audit/card-231-v3.md`: CARD_OK.
- Scope validation: IN_SCOPE 17 files. `git diff --check`: exit 0.
- Exact hash checks: six source snapshots, fifteen frozen files and four reviewer AST nodes PASS. Workflow bytes equal the baseline plus only the test-loop filename insertion.

Remote byte/newline verification, exact-SHA CI and final independent review are reported in the delivery comment after they complete. The patch must not be described as media PASS.

Overall result remains BLOCKED pending phase 2 real editing, technical QA and watched review. Structural unit tests are not substitutes for those gates. E32 is PARTIAL, not resolved.
