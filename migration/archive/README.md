# Archive (2026-10-19)

GitHub issue #177, "v2 step 1: archive everything unreachable".

## What moved

- 163 Python files from `migration/` to `migration/archive/` at the same relative path
  (`migration/X/y.py` became `migration/archive/X/y.py`). These were one-off probes,
  qualifications, overlays and evidence collectors from the v1 Linux, RapidAPI, Kaggle and Gemini
  chains, plus the tests that covered only those files.
- 18 workflows from `.github/workflows/` to `migration/archive/workflows/`, next to the ones
  archived earlier (see `workflows/README.md`).

Each file was moved with `git mv` and its content is unchanged, so `git log --follow` still
shows its history.

## Why

`ARCHIVE_PLAN.json` in this folder lists every file and comes from a full import and invocation
trace. Nothing live imports, runs or dispatches these files. Live means the remaining workflows,
`migration/ci`, `migration/ops`, `migration/production`, `migration/publish`, the live mining
libraries and `migration/runtime_bridge/gemini_public_av.py`.

Two kinds of files stayed in place:

- The plan's `kept_as_errors_antidote` and `kept_live_library` lists.
- Any listed file that a live or kept file still imports. Four files stayed for this reason.
  `migration/acquisition/test_acquire_window.py` is the antidote for error E19 in
  `migration/ops/ERRORS.json`. It imports `migration/acquisition/acquire_window.py`, which
  imports `migration/diagnostics/rapidapi-native-av/preflight.py` and
  `migration/diagnostics/rapidapi-native-av/native_probe.py`. Both of those import
  `migration/diagnostics/rapidapi-mcp/connection_probe.py`.

## How to restore

Move a file back to its original path, for example:

```
git mv migration/archive/mining/native_metrics.py migration/mining/native_metrics.py
git mv migration/archive/workflows/requests.yml .github/workflows/requests.yml
```

If you restore a test, add it back to the unit-test list in `.github/workflows/pr-checks.yml`.
