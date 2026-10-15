# Forecast truthfulness correction — staged only

## Existing gap and runtime route

Verified against repository main fa03f7ae6fd0b9759bf68ad3c1ed29dcd532574f and source archive SHA-256 fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10.

Native `hero_engine/cli.py:command_forecast` invokes `_forecast_context` -> `forecast.all_scenarios` -> report JSON/Markdown and `daily_forecasts` SQLite insert. Other CLI summary/report consumers also use `_forecast_context` and `all_scenarios`. The patch changes these actual functions rather than introducing an unused helper.

Current repository `migration/runtime_bridge/apply_prediction_provenance_overlay.py` modifies only `hero_engine/phase6_intelligence.py`. It does not patch this CLI route; its receipt is explicitly SHADOW_GUARD_NOT_DEPLOYED. The current `migration/PREDICTABILITY_CONTRACT.md` likewise says that guard is not installed. No valid calibration consumer contract exists in the legacy CLI API. A caller-supplied `calibrated` string cannot establish one.

The repository materializes native code from the immutable source archive. `migration/qualify_linux_overlay_cloud.py` extracts to `original/project`, applies `migration/apply_linux_production_overlay.py` into a new shadow, then tests it. That applier modifies renderer/font and one OAuth fixture, not forecast source. `.github/workflows/linux-validation.yml` validates source/infrastructure without installing this correction.

## Staged changes

- `migration/runtime_bridge/apply_forecast_truthfulness_overlay.py`: verifies exact original hashes, refuses existing/in-place destinations, creates a separate shadow and patches real native CLI and forecast modules. It may follow the existing Linux production overlay because their touched source files do not overlap; hash verification must succeed before application.
- `_forecast_context` inventories available long/short observations as empirical_inputs_only (or prior_only), keeps configured conditional assumptions unchanged, and no longer fabricates observed measurements or validated calibration from 10+10 samples.
- `all_scenarios` always withholds predictive probabilities/distributions because this API has no implemented calibration validation contract. Supplied labels do not bypass this. Missing operational inputs retain their original specific withholding reason.
- Raw `simulate` remains a conditional arithmetic/simulation facility, with an explicit conditional_assumptions_not_validated_prediction status. It is not a forecast-validation authority.
- Reports no longer describe a publication-count threshold as sufficient to recalibrate.
- `tests/test_engine.py` has one obsolete count-based calibration assertion replaced in the successor shadow. The original archive, original test, historical receipts and original source files remain unchanged. Full legacy test suite was not run.
- Revenue arithmetic, quality/release gates, publication, format selection, providers and account state are unchanged.

## Offline verification

12 tests pass. They materialize only the three exact source files from the hash-verified archive. Coverage: 9/10/11/100 samples per format; missing metrics; forged calibrated label; missing YPP inputs; conditional simulation labeling; report text; actual patched command function generating JSON/Markdown and storing a temporary SQLite payload; source hash rejection; destination rejection; preserved original bytes; unchanged conditional revenue arithmetic.

The test harness compiles exact `_forecast_context` and `command_forecast` AST nodes from the patched CLI, calling the actual patched forecast module. It deliberately excludes unrelated imports. Full CLI import in this environment failed on missing `cv2`; no dependency was installed and no full CLI/bootstrap success is claimed.

Run from the repository root after staging these two migration files:

    python -m unittest discover -s migration/runtime_bridge -p test_forecast_truthfulness_overlay.py -v

The default input is the repository-root source ZIP. An explicit HERO_FORECAST_SOURCE_ARCHIVE path can locate the identical archive elsewhere.

## Remaining installation work

1. Review and commit only the applier, tests, source diff and explicit qualification/integration notes as appropriate; repository preservation does not constitute runtime activation.
2. At the selected environment's existing native-source materialization boundary, apply the overlay to a new separate successor shadow after compatible prior overlays. Do not overwrite the archive or active working source.
3. Run the dependency-complete CLI smoke and native regression suite against that exact shadow. Qualifier workflows may call this stage, but a test workflow alone is not installation into the active runtime.
4. Inspect the actual runtime launcher/source root and switch only through its existing authorized activation path, preserving previous state and receipts. That launcher and active runtime are not verified here. Confirm loaded source hashes before claiming deployment.
5. Future predictive calibration needs an implemented, provenance-checked, applicable evaluation contract. This correction invents no receipt schema, holdout threshold, precision target, profit guarantee or authority to publish.

Current status: SHADOW_PATCH_NOT_DEPLOYED. Broad comparative strategy research and production format binding remain separate pending work.

## Staged fresh-runner qualification (not dispatched)

Added `.github/workflows/forecast-truthfulness-qualification.yml`, manual-only, contents-read, 10-minute job limit. Dependency installation gets five minutes; qualification gets four. It creates an isolated venv and installs official-PyPI binary distributions needed by the actual CLI import graph: opencv-python/numpy, faster-whisper, Pillow, rapidocr/onnxruntime, jsonschema and yt-dlp. It does not execute the broad requirements.txt (which would also install unrelated model/audio stacks). Direct dependency versions are pinned with their evidence in DEPENDENCIES.md; resolved transitive versions are recorded but are not a pre-qualified full lockfile.

Before native imports/tests, `migration/runtime_bridge/qualify_forecast_truthfulness_cloud.py` runs in a fresh Linux network namespace created by `sudo unshare --net`. It verifies namespace separation and loopback-only interfaces. A Python audit hook independently denies socket connection/DNS/send operations and child-process execution, with denial self-tests; any unexpected denied attempt fails the qualification. Offline HF environment switches are defense in depth. No model is constructed, downloaded or run. No provider/OAuth action is selected. Installation network access occurs only before the isolated native qualification, via official PyPI.

The qualifier selectively extracts code, engine config and the single reviewed native test module from the existing hash-verified ZIP into a new temporary original directory. It applies the forecast correction to a separate shadow, then runs:

- the existing 12 guard tests;
- actual `hero_engine.cli` and `hero_engine.forecast` imports without stubs;
- actual `cli.main()` with `--help`;
- four individually selected native forecast regression methods;
- actual imported `command_forecast()` producing JSON/Markdown and a disposable SQLite payload, with only input rows/output-root/database connection patched for isolation.

Receipt includes imported code SHA-256, original/source/shadow integrity, resolved dependency versions, exact test names/counts and explicit `active_runtime_installed=false`, `predictive_calibration_available=false`, `production_ready=false`. Only this small receipt is uploaded; temporary media/model/source trees are not attached. Original archive integrity is rechecked after qualification.

Local preparation checks: Python syntax passes; YAML parsing and 10-minute job bound pass; invocation without a fresh network namespace fails before native imports and creates no receipt. The complete fresh-runner workflow has NOT run. Missing dependencies are therefore an outstanding verified qualification gap, not claimed resolved by staging this workflow. This document records pre-dispatch preparation; repository preservation is not runtime installation.


### Review hardening

The workflow now requires the exact repository `matheusmagah-cpu/heroverse-engine`, private visibility, `refs/heads/main`, `workflow_dispatch`, and first run attempt. These checks appear both in the job admission expression and before checkout/install. No run-number=1 restriction is inferred.

The config relocation concern was checked against the actual native `db.load_config` function: it reads `db.DEFAULT_CONFIG`, computed from the imported shadow module, not `cli.ROOT`. Patching `cli.ROOT` only relocates report output. A local isolated function test successfully loaded shadow/config/engine.json after changing cli.ROOT to a directory without config. The qualifier now asserts the default config path, unchanged config value and hash before executing the actual command, and records that hash in its receipt.

The network namespace is process-scoped and temporary; this workflow neither changes host networking nor creates persistent security settings. Failure to create/verify it is terminal, with no alternate network-enabled qualification path.
