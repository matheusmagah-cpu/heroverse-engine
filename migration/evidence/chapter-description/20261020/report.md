# Pilot012 opening chapter correction

The public player and package showed `0:00 Good morning`; the actual script opens `Good evening`. The root cause was a hard-coded morning label in package_pilot.chapters_from_script. The generator now preserves an explicit chapter first, otherwise uses the exact morning/evening greeting; unknown openings and the legacy no-script path use `Opening prayer`. It never guesses from publication time or title.

Only the package description's opening chapter is changed for012. Script, audio/render provenance, QA, review, approval, thumbnail and schedule are unchanged, with hashes in verification.json. Other chapter times, labels and package fields are identical.

The bounded metadata updater accepts only pilot012/video1bT9pEROuhI on the configured HeroVerse channel. It requires the exact known old or desired description and existing title, preserves all mutable snippet fields, uses the resource ETag as If-Match, and writes only part=snippet. Missing ETag, wrong identity, edits by someone else, HTTP conflict and verification failure stop. Already-correct is read-only/idempotent. No status, visibility, upload or media operation is issued. The final read verifies preserved metadata/status and exact new description. A failed or uncertain write is never blindly repeated.

The new manual workflow is fixed to this repair, uses existing configured credentials/pinned dependencies and the publication concurrency group. The API operation uses50 YouTube quota units, not a monetary purchase. There is no schedule or broad dispatch. Live success requires a separate recorded execution and public-page verification; unit tests alone do not establish it.

Owner explicitly authorized opening the technical issue and correcting only this chapter at2026-10-20T00:36:06Z, requesting regression prevention.4 generator tests and8 mocked updater tests pass; all40 CI scripts pass. API semantics were checked against official videos.update and ETag documentation.
