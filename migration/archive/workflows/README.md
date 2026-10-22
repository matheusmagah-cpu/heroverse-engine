# Archived workflows (2026-10-19)

One-off probes, qualifications and the superseded pilot renderer. None is referenced by
the live chain (heartbeat → images → render → approve → publish → Shorts), by any test, or by
any code. They are kept here unchanged so any one can be restored with
`git mv migration/archive/workflows/<name>.yml .github/workflows/`.

On 2026-10-22 the three retired Kaggle workflows (`kaggle-images.yml`,
`kaggle-render.yml`, `kaggle-collect.yml`) and their three Python helpers were
also moved unchanged, following `migration/kaggle/STATUS.md` and the Kaggle
subset of `migration/archive/ARCHIVE_PLAN.json` (#177). The active workflows,
scheduler and tests have no callers of these six files. This completes only
that subset of the archive plan.

The helpers are in `migration/archive/kaggle/`. To restore this historical
route, restore all six files to their original paths together, including the
helpers under `migration/kaggle/`. The route remains retired; restoring its
files does not approve its use. Its status record, pending-job evidence and
previously generated assets were retained.
