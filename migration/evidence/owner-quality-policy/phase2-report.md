# Pilot-006 single preserved Short recovery: phase 2

Baseline: 9f7c762638bad129206f136880e0a2fc73bec09f. SPEC v4 issue259 was consolidated at 2026-10-21T00:15:30Z after independent contract review.

Verified original manifest SHA256: 37465008e0b73a51f3d394d283500eab1426fdd679d36b571ed241d20689e402. All three original records have publish=false and NOT_REVIEWED_ProviderFailure. The historical detailed HTTP cause was discarded by the old reviewer and remains unknown.

Plan only: preserve short-00.mp4 hash 9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707 and review it once through the existing designated reviewer after code gates. No media approval or provider recovery is claimed. No provider, rendering or dispatch has occurred in phase 2.

Contract review caught a temporal rollover risk and required explicit recovery binding in pending/publisher, fixed 14:00 UTC slot, 13:15 UTC cutoff, context identity checks, immutable source fields and durable failure diagnostics. Existing criteria, rubric and ordinary finalizer stay unchanged.

Implementation and acceptance are pending. Issue259 remains open and working; not DONE.
