"""Hash-bound forecast correction in a new shadow; no calibration or deployment claim."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

EXPECTED = {
    'tests/test_engine.py': '4485d357516d65ee89e4a1dbcb6331f727e403b9d91e37b38cae207633c831db',
    'hero_engine/cli.py': '35de28f1b7f09842dee9fa5a4a628a62615d2333ffe9548f457bfae59e48307e',
    'hero_engine/forecast.py': '5f5628fe8e567f7ae98a20d94666ab3db49b87138e648ca232f233cc464f7bf6',
}
CONTEXT = '''def _forecast_context() -> tuple[dict, dict[str, object]]:
    config = load_config()
    samples = rows(
        """
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY youtube_video_id
                ORDER BY COALESCE(age_hours, 0) DESC, captured_at DESC
            ) AS rn
            FROM performance_snapshots
        )
        SELECT * FROM ranked WHERE rn=1
        """
    )
    # Counts describe available inputs, not predictive accuracy. These snapshots
    # have no verified common horizon/cohort or out-of-sample evaluation contract.
    info: dict[str, object] = {
        "status": "empirical_inputs_only" if samples else "prior_only",
        "observed_long_videos": sum(s["format"] == "long" for s in samples),
        "observed_shorts": sum(s["format"] == "short" for s in samples),
        "predictive_calibration_status": "UNAVAILABLE",
        "assumption_basis": "CONFIGURED_CONDITIONAL_HYPOTHESES_NOT_FITTED_OBSERVATIONS",
        "interpretation": (
            "Stored observations are input inventory only; their count does not validate "
            "predictive calibration. Configured conditional assumptions are unchanged."
        ),
    }
    # Do not backfill missing observed metrics with priors and call them calibrated.
    # Preserve the explicit scenario assumptions until an applicable validation
    # contract and its consumer exist; no sample-size threshold substitutes for it.
    return config, info
'''


def _replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise PermissionError('EXACT_FORECAST_ANCHOR_REQUIRED')
    return text.replace(anchor, replacement)


def patch(originals):
    cli = originals['hero_engine/cli.py'].decode()
    tree = ast.parse(cli)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_forecast_context')
    lines = cli.splitlines(keepends=True)
    cli = ''.join(lines[:node.lineno - 1]) + CONTEXT + ''.join(lines[node.end_lineno:])
    forecast = originals['hero_engine/forecast.py'].decode()
    forecast = _replace_once(forecast, '    return {\n        "scenario": scenario["name"],\n',
        '    return {\n        "probability_status": "conditional_assumptions_not_validated_prediction",\n        "scenario": scenario["name"],\n')
    start = forecast.index('    calibration_info = calibration or {', forecast.index('def all_scenarios('))
    end = forecast.index('    results = ', start)
    forecast = forecast[:start] + '''    supplied = calibration or {}
    # This legacy API has no validator for calibration provenance/evaluation.
    # A caller-supplied label or sample count cannot unlock predictive output.
    calibration_info = {
        "status": "empirical_inputs_only" if (
            supplied.get("observed_long_videos", 0) or supplied.get("observed_shorts", 0)
        ) else "prior_only",
        "observed_long_videos": supplied.get("observed_long_videos", 0),
        "observed_shorts": supplied.get("observed_shorts", 0),
        "predictive_calibration_status": "UNAVAILABLE",
        "assumption_basis": "CONFIGURED_CONDITIONAL_HYPOTHESES_NOT_VALIDATED_PREDICTIONS",
        "interpretation": "No applicable predictive calibration validation contract is implemented in this API.",
    }
''' + forecast[end:]
    forecast = _replace_once(forecast,
        'if calibration_info.get("status") != "calibrated" and result.get("probability_status") != "withheld_missing_operational_inputs":',
        'if result.get("probability_status") != "withheld_missing_operational_inputs":')
    forecast = forecast.replace('"withheld_unobserved_channel_sample"', '"withheld_unvalidated_predictive_calibration"')
    forecast = _replace_once(forecast,
        '                f"- Mínimo operacional para recalibrar: {calibration.get(\'minimum_per_format\', 10)} publicações por formato.",',
        '                "- Contagem de publicações não comprova calibração preditiva; validação aplicável permanece UNAVAILABLE.",')
    legacy_test = originals['tests/test_engine.py'].decode()
    legacy_test = _replace_once(legacy_test,
        'def test_channel_samples_recalibrate_forecast_assumptions(self):',
        'def test_channel_samples_do_not_prove_predictive_calibration(self):')
    legacy_test = _replace_once(legacy_test,
        '        self.assertEqual(calibration["status"], "calibrated")\n'
        '        self.assertEqual(base["median_views_per_long"], 1450)\n'
        '        self.assertEqual(base["median_views_per_short"], 725)\n'
        '        self.assertEqual(base["average_view_duration_minutes"], 5.0)\n',
        '        self.assertEqual(calibration["status"], "empirical_inputs_only")\n'
        '        self.assertEqual(calibration["predictive_calibration_status"], "UNAVAILABLE")\n'
        '        self.assertEqual(calibrated_config, load_config())\n')
    patched = {'hero_engine/cli.py': cli.encode(), 'hero_engine/forecast.py': forecast.encode(),
               'tests/test_engine.py': legacy_test.encode()}
    for path, raw in patched.items():
        compile(raw, path, 'exec')
    return patched


def apply(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists() or destination == source or source in destination.parents:
        raise PermissionError('NEW_SEPARATE_SHADOW_REQUIRED')
    originals = {p: (source / p).read_bytes() for p in EXPECTED}
    for path, raw in originals.items():
        if hashlib.sha256(raw).hexdigest() != EXPECTED[path]:
            raise PermissionError('FORECAST_SOURCE_IDENTITY_CHANGED: ' + path)
    patched = patch(originals)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__'))
    changes = []
    for path, raw in patched.items():
        (destination / path).write_bytes(raw)
        changes.append({'path': path, 'original_sha256': EXPECTED[path],
                        'shadow_sha256': hashlib.sha256(raw).hexdigest()})
    receipt = {'version': 'forecast-truthfulness-shadow-v1', 'changes': changes,
               'status': 'SHADOW_PATCH_NOT_DEPLOYED', 'original_preserved': True,
               'predictive_calibration_available': False, 'production_ready': False}
    (destination / 'forecast-truthfulness-overlay.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    print(json.dumps(apply(args.source, args.destination), indent=2))
