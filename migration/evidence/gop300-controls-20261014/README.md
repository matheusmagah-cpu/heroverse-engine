# Current GOP300 transport calibration — 2026-10-14

This is the next bounded acceptance step after the final production review.
The eight independent codec controls and strict disjoint holdout PASS. All 300
native RGB frames per final control were inventoried. The original calibration
function, font/palette/geometry domain and metric implementations remain pinned.
The existing master and completed master frame/audio/ASR observations were reused.

External binding: `8ea5bf876957b112e1575118be68f610329052f45c5a60a9a0a3ac104993d13e`.
Policy v2 SHA256: `ddbf013c9bc5a9cc11797793a90add7e7a738bdbff1f3964fdfd02964422d377`.
Policies were committed before the corresponding effect, in commits
602edb9cfbc7fac7d0ad2b2656791d3927793559 and 9cd1737faaa207f5cfeb22448d30e59017ce56b4.

Limits: text-local SSIM loss <= 0.001375963269988123; maximum CIE76 delta-E <=
35.72235107421875. These are reference-conditioned transport error limits,
not a perceptual colour tolerance, semantic review or market-performance score.
The known corruptions test missing text plus colour shifts; this does not prove
sensitivity to every possible visual defect. The preserved exact current RGB
measurements are within the limits. The source is excluded from calibration.

The original native GOP60 reader and execution verifier have not been modified.
Next: integrate this authenticated GOP300 binding into a versioned native reader
and current execution bridge, then test it against the target package. Keep the
old domain, original music-reference requirement and market AV handoff intact.
No production/release approval or publication authority was emitted.

## Restore and reopen without media effects

Extract controls-evidence.zip to a NEW working directory. It includes the exact
scripts, controls, failed attempts, manifests and test log. Restore the immutable
native source archive by the existing procedure, then apply the existing
apply_linux_composition_overlay.py to a NEW composition-shadow in that directory.
Use the existing Pillow/NumPy/native dependencies and OpenCV 4.13.0.92. The new
reader imports only the pinned native metric module, not the live publisher.

From the extracted working directory, run:

```bash
python verify_transport_gop300.py --directory controls-v3 \
  --binding-sha 8ea5bf876957b112e1575118be68f610329052f45c5a60a9a0a3ac104993d13e \
  --policy-sha ddbf013c9bc5a9cc11797793a90add7e7a738bdbff1f3964fdfd02964422d377 \
  --native-root composition-shadow \
  --producer calibrate_transport_gop300_recovery_v3.py
python test_transport_gop300.py
```

Expected reader output: AUTHENTICATED_GOP300_INSTRUMENT_OBSERVATIONS,
separation_passed=true, quality_authorized=false, publication_authorized=false,
subprocess_calls=0 and provider_calls=0. Seven targeted tests passed. Do not run
the calibration producers again for already completed unchanged inputs.

Two failed attempts are preserved. Attempt 1 lacked cv2 after the first encode;
its exact MP4 was reused. Attempt 2 completed measurements but the native strict
calibrator rejected four identical negative MP4s. Policy v2 changes only the
negative corruption to preserve distinct remaining glyphs; it reuses the four
completed positives without encoding or decoding. Thresholds were not tuned.
