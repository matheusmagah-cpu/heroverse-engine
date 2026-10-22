# Archived workflows (2026-10-19)

One-off probes, qualifications and superseded execution routes. They are not
active GitHub workflows. The complete inventory and recovery instructions are
in `../ARCHIVE_PLAN.json` and `../README.md`. Restore dependencies together;
moving a workflow alone does not restore its helpers or grant execution authority.
The retained ASR extraction regression reads `second-opening-asr.yml` here as a
historical fixture; it does not dispatch it.

On 2026-10-22 the three retired Kaggle workflows (`kaggle-images.yml`,
`kaggle-render.yml`, `kaggle-collect.yml`) and their three Python helpers were
also moved unchanged, following `migration/kaggle/STATUS.md` and the Kaggle
subset of `migration/archive/ARCHIVE_PLAN.json` (#177). The active workflows,
scheduler and tests have no callers of these six files. This completes only
that subset of the archive plan. The later complete cleanup is recorded in the v2
manifest one directory above; its explicit retained dependencies take precedence.

The helpers are in `migration/archive/kaggle/`. To restore this historical
route, restore all six files to their original paths together, including the
helpers under `migration/kaggle/`. The route remains retired; restoring its
files does not approve its use. Its status record, pending-job evidence and
previously generated assets were retained.
