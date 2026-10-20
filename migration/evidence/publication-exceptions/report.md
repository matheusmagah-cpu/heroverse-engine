# Owner temporal exception — implementation report

Task #257, baseline 38c7f70502904c3e961296b680e9526c9a9bef32. The owner explicitly requested a one-post exception mechanism on 20 October2026 at21:07:33UTC, with the normal time lock preserved. This is a separate development task, not the denied replacement of #231.

Preflight: current main has no temporal exception interface. Normal finalizer cutoff is19:30UTC. Actual Short cb3ce331529437f4fadc3b14dec01dfad18909a3e9f024a99cea141e91ae956f already has real QA PASS and designated watched-review overall8.5. It has not been uploaded. The owner explicitly retained authorization for this artifact; future content requires overall>=9 in addition to existing gates.

Trust boundary: dot attests the verified authenticated conversation, with literal evidence and IDs. The registry pins one admitted receipt digest. This is operational admission, not a human GitHub review or cryptographic identity proof. No arbitrary new receipt self-authorizes.

Implementation in progress: separate finalizer wrapper, closed registry, durable remote pre-upload reservation, same-ID readback and uncertain-result blocking. Ordinary cutoff and finalizer/file function ASTs are unchanged. CARD_OK on the current card. Code review, all tests, exact-SHA CI, real generated manifest and verified publication remain pending. Not DONE.
