# Shared execution integration — 2026-10-30

Owner: keep Claude Code and ChatGPT connected to the same ongoing project; switch
responsibility when one is unavailable without redoing the other's accepted work.
This delivery changes coordination, not the production implementation.

Read migration/OPERATIONS.md, section Shared Claude Code / ChatGPT execution,
before any project-writing run.
The common GitHub control reference is claude/shared-executor-control. Its lease
must be acquired with an exact observed parent and a non-forced update/readback.
Existing media workflow claims still govern provider effects.

The original PR Review Toolkit prompts are available to the ChatGPT host through
the personal skill pr-review-toolkit (upstream revision and identity in the protocol).
A real specialist review of PR549 head 8e4decf8d87feb7c4b006688a3ceff24ed24f1bc
completed with five original specialists executed sequentially by Codex. It found
one Important: a timestamp with only whitespace can be marked EVIDENCE_COMPLETE
without a defect description. Publication flags remained false; no publishing bypass
was demonstrated. See migration/evidence/handoff/20261030-pr549-toolkit-review.md.
PR549 remains separate: reconcile this demonstrated finding and the separate
security-sweep requirement; do not regenerate media or redo accepted work.

Existing Short09/10 deliveries, current plans and media hashes remain as recorded.
No media was regenerated, submitted, approved or published by this coordination change.
Current work: reconcile the toolkit review, then continue the existing next delivery.
Scheduling is verified separately: do not infer routine activation from this document.
