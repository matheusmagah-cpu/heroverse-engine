# Traceable audiovisual analysis cards

Implemented in `migration/mining/video_analysis_card.py`. The adapter uses only
Python's standard library and preserved local JSON. It does not collect data,
call a model, modify a gate or change the validated structure.

## Real execution

The CLI normalized the existing scenic research into exactly nine cards:
six winners and three weak contrasts, in their original order and with their
original identities, channel IDs and breakout values (including null).
The separate thumbnail reconciliation preserves all 20 source rows and matches
six of them to the validated cohort. It does not add the other fourteen to it.
Two runs produced byte-identical `analysis-cards.json`.

Every observation retains its source-file SHA256, JSON pointer, method, status
and temporal coverage. Image hashes are separate from JSON-file hashes.
Dimensions/luminance/colour are identified as reported instrumental measures;
image-content facts remain model reports. Cuts per minute remain estimates.
Reported false, zero and missing values are distinguished.

## Useful gaps exposed

- Ten thumbnail rows contain disagreement between the model's word count and a
  whitespace count of its reported text. Both values and their methods remain.
  These are reporting conflicts, not ten independently proven image/OCR errors.
- The source structure's thumbnail label says unmeasured despite existing data.
  The report identifies the mismatch; it does not silently update a policy.
- All nine promise sections remain UNKNOWN: an observed direct-address hook or
  a title does not establish which promise was actually made and fulfilled.
- The compact structure audit has no exact watched interval. Its booleans stay
  reported observations with unknown temporal coverage, not whole-file proof.
- The actual pilot012 review is a legacy shape without the newer audit field.
  A PASS review or failed/missing audit cannot create missing observations.
- Optional legacy windows retain paraphrased beat summaries and modality flags;
  they do not export full transcripts or infer an ending from a partial window.

Counts are descriptive, not causal claims, performance rules or CTR predictions.
No new driver label, approval, publish flag or originality detector is emitted.

## Verification

18 new offline tests PASS. Six existing suites also PASS: long_review,
structure_mining, packaging_mining, three_stage, script_check and errors_register.
Tests cover cohort separation, false/zero/null, estimates versus measurements,
conflicting sources, exact-byte hashes and pointers, image-vs-file hashes,
determinism, nonmutation, legacy missing/error audit, identity mismatch,
partial/unreceived media, no copied transcripts and source-overwrite refusal.

Source structure, structure audit, thumbnail audit and frozen QA v3 were checked
byte-identical to the base commit; hashes are in verification.json.
The sole workflow edit registers the new test in the existing PR test list.
Final delivered commit, remote byte verification and CI are recorded on PR206.

Run from repository root:

    python3 -I -B migration/mining/video_analysis_card.py migration/structures/guided-prayer-scenic.json migration/evidence/vidiq/20261019/structure_audit.json migration/evidence/vidiq/20261019/thumbnails.json OUTPUT.json

Originality pre-render reconciliation belongs to existing #141; owned48h/7d
feedback is a later patch. This deliverable supplies traceable inputs for those
steps without redoing the research or promoting unverified claims.

Independent review correction: disjoint or partially overlapping legacy windows are not automatically treated as source conflicts. Identical-window incompatible values remain visible. Three regression tests cover these cases.
