# Historical components, not a second pipeline

The October 22, 2026 cleanup inventories every tracked path in both HeroVerse
repositories. `ARCHIVE_PLAN.json` records the exact baseline, dispositions,
source/destination paths and hashes. It supersedes the October 19 move list:
shared imports, regression tests and instruments needed by pending qualification
were retained rather than moved merely because they were listed there.

Retired components include the cutover observer/overlays, completed one-shot
preservation probes, the superseded CPU image generator and CC-clip inspection,
retired Gemini mining workflows, the failed hosted-player diagnostic, the old
runner-workflow copy and the obsolete observer proposal. The operational ZIP
is a recovery snapshot, not the source used by the current renderer. Kaggle
was already retired in PR #268.

All relocated files retain their exact bytes. Only generated Python caches are
deleted. Current media, approvals, receipts, frozen criteria, test fixtures and
the pinned voice-source ZIP are preserved. Duplicate evidence is intentional:
a dated record or independent fixture must not silently become a mutable alias.

## Recovery

These files are historical, **not runnable from this directory**. Their original
relative imports and evidence paths remain unchanged. To restore a component,
use the manifest to move its files back to their original paths and restore its
dependent fixtures/workflows together; inspect current dependencies and run
tests first. Do not reactivate an obsolete workflow just to run an old test.
The baseline commit also preserves all original paths. Restoration is not an
approval to spend quota, change quality rules, publish, or replay a completed
media check.

The authoritative runner workflow remains in `heroverse-runner`, not the archived
copy in `ci/`. QA instruments and the ASR model extraction helper remain at their
original active paths. Qualification gaps and unavailable review are not solved
by archiving this history.
