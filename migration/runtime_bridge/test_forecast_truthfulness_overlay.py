"""Offline tests of exact patched functions; no cv2/provider/production imports."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import zipfile
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from apply_forecast_truthfulness_overlay import EXPECTED, apply

ROOT = Path(__file__).resolve().parents[2]
SOURCE = None
ARCHIVE_SHA256 = 'fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'


def config():
    return {
        'channel': {'deadline_days': 7, 'name': 'Fixture', 'handle': '@fixture',
            'target_subscribers': 1000, 'current_subscribers': 10,
            'target_valid_watch_hours': 4000, 'current_valid_watch_hours': 2},
        'publishing': {'long_videos_per_day': 1, 'shorts_per_day': 1},
        'forecast': {'simulations': 4, 'scenarios': [{
            'name': 'base', 'average_view_duration_minutes': 3,
            'subscriber_conversion_rate': 0.01, 'median_views_per_long': 90,
            'median_views_per_short': 40, 'breakout_probability_per_long': 0.01,
            'breakout_median_views': 900, 'short_breakout_probability': 0.01,
            'short_breakout_median_views': 400}]}}


class ForecastTruthfulnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global SOURCE
        archive = Path(os.environ.get('HERO_FORECAST_SOURCE_ARCHIVE', str(ROOT / 'HeroVerse_Linux_Source_Ready_20261013_v2.zip')))
        if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError('Immutable source archive identity mismatch')
        cls.temporary = tempfile.TemporaryDirectory()
        SOURCE = Path(cls.temporary.name) / 'original'
        (SOURCE / 'hero_engine').mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            for relative in EXPECTED:
                (SOURCE / relative).parent.mkdir(parents=True, exist_ok=True)
                (SOURCE / relative).write_bytes(z.read('project/' + relative))
        cls.shadow = Path(cls.temporary.name) / 'shadow'
        cls.receipt = apply(SOURCE, cls.shadow)
        spec = importlib.util.spec_from_file_location('forecast_truthfulness_under_test', cls.shadow / 'hero_engine/forecast.py')
        cls.forecast = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.forecast
        spec.loader.exec_module(cls.forecast)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def cli(self, samples, cfg=None, **extra):
        # Compile the unmodified AST nodes from the actual patched CLI source.
        # Exclude unrelated module imports requiring unavailable cv2/providers.
        tree = ast.parse((self.shadow / 'hero_engine/cli.py').read_text())
        names = {'_forecast_context', 'command_forecast'}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        supplied = cfg if cfg is not None else config()
        namespace = {'argparse': argparse, 'json': json, 'load_config': lambda: supplied,
                     'rows': lambda query: samples, 'forecast_module': self.forecast, **extra}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'patched-cli-functions', 'exec'), namespace)
        return namespace

    def test_no_sample_remains_prior_only(self):
        _, info = self.cli([])['_forecast_context']()
        self.assertEqual(info['status'], 'prior_only')
        self.assertEqual(info['predictive_calibration_status'], 'UNAVAILABLE')

    def test_counts_never_unlock_calibration(self):
        for n in (9, 10, 11, 100):
            with self.subTest(n=n):
                samples = [{'format': kind, 'views': 100, 'average_view_duration_seconds': 30}
                           for kind in ('long', 'short') for _ in range(n)]
                cfg, info = self.cli(samples)['_forecast_context']()
                self.assertEqual(info['status'], 'empirical_inputs_only')
                self.assertEqual(info['observed_long_videos'], n)
                result = self.forecast.all_scenarios(cfg, calibration=info)[0]
                self.assertIsNone(result['probability']['reach_both'])

    def test_missing_metrics_do_not_become_observed_defaults(self):
        cfg = config(); before = copy.deepcopy(cfg)
        samples = [{'format': kind, 'views': None, 'average_view_duration_seconds': None}
                   for kind in ('long', 'short') for _ in range(10)]
        result, info = self.cli(samples, cfg)['_forecast_context']()
        self.assertEqual(result, before)
        self.assertEqual(cfg, before)
        self.assertNotIn('base_observed_assumptions', info)
        self.assertNotIn('minimum_per_format', info)

    def test_claimed_calibrated_label_does_not_unlock_output(self):
        claim = {'status': 'calibrated', 'observed_long_videos': 100,
                 'observed_shorts': 100, 'interpretation': 'Guaranteed!',
                 'predictive_calibration_status': 'VALIDATED'}
        before = copy.deepcopy(claim)
        result = self.forecast.all_scenarios(config(), calibration=claim)[0]
        self.assertEqual(claim, before)
        self.assertEqual(result['calibration']['status'], 'empirical_inputs_only')
        self.assertEqual(result['calibration']['predictive_calibration_status'], 'UNAVAILABLE')
        self.assertTrue(all(x is None for x in result['probability'].values()))
        self.assertTrue(all(x is None for x in result['distribution'].values()))
        self.assertEqual(result['probability_status'], 'withheld_unvalidated_predictive_calibration')

    def test_missing_operational_inputs_keep_specific_blocker(self):
        cfg = config(); cfg['channel']['current_valid_watch_hours'] = None
        result = self.forecast.all_scenarios(cfg)[0]
        self.assertEqual(result['probability_status'], 'withheld_missing_operational_inputs')
        self.assertIsNone(result['deterministic_target']['watch_hour_gap'])

    def test_conditional_simulation_is_explicit_not_predictive_validation(self):
        cfg = config(); result = self.forecast.simulate(cfg, cfg['forecast']['scenarios'][0], 7)
        self.assertEqual(result['probability_status'], 'conditional_assumptions_not_validated_prediction')
        self.assertEqual(result['assumptions']['median_views_per_long'], 90)

    def test_report_removes_count_based_calibration_claim(self):
        cfg = config(); results = self.forecast.all_scenarios(cfg)
        report = self.forecast.markdown_report(cfg, results)
        self.assertNotIn('Mínimo operacional para recalibrar', report)
        self.assertIn('Contagem de publicações não comprova', report)
        self.assertIn('UNAVAILABLE', report)

    def test_real_command_path_writes_withheld_files_and_database_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); db = root / 'test.sqlite'
            with sqlite3.connect(db) as con:
                con.execute('CREATE TABLE daily_forecasts (generated_at TEXT, scenario TEXT, horizon_days INTEGER, payload TEXT)')
            samples = [{'format': kind} for kind in ('long', 'short') for _ in range(10)]
            namespace = self.cli(samples, ROOT=root, connect=lambda: sqlite3.connect(db),
                                 utc_now=lambda: '2026-10-15T00:00:00Z', _print_json=lambda value: None)
            namespace['command_forecast'](argparse.Namespace(days=7))
            result = json.loads((root / 'output/reports/forecast-7d.json').read_text())[0]
            self.assertIsNone(result['probability']['reach_both'])
            with sqlite3.connect(db) as con:
                stored = json.loads(con.execute('SELECT payload FROM daily_forecasts').fetchone()[0])
            self.assertEqual(stored, result)
            self.assertIn('UNAVAILABLE', (root / 'output/reports/forecast-7d.md').read_text())

    def test_sources_unchanged_and_shadow_explicit(self):
        for path, digest in EXPECTED.items():
            self.assertEqual(hashlib.sha256((SOURCE / path).read_bytes()).hexdigest(), digest)
        self.assertEqual(self.receipt['status'], 'SHADOW_PATCH_NOT_DEPLOYED')
        self.assertFalse(self.receipt['predictive_calibration_available'])

    def test_changed_source_is_rejected_before_shadow_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; (source / 'hero_engine').mkdir(parents=True)
            for path in EXPECTED:
                (source / path).parent.mkdir(parents=True, exist_ok=True)
                (source / path).write_bytes((SOURCE / path).read_bytes())
            (source / 'hero_engine/cli.py').write_bytes(b'# changed\n')
            with self.assertRaisesRegex(PermissionError, 'FORECAST_SOURCE_IDENTITY_CHANGED'):
                apply(source, root / 'shadow')
            self.assertFalse((root / 'shadow').exists())

    def test_existing_destination_is_rejected(self):
        with self.assertRaisesRegex(PermissionError, 'NEW_SEPARATE_SHADOW_REQUIRED'):
            apply(SOURCE, self.shadow)

    def test_revenue_scenarios_preserve_conditional_arithmetic(self):
        result = self.forecast.audio_revenue_scenarios(views=1000, monetized=False,
            scenarios=[{'name': 'fixture', 'assumption_basis': 'hypothetical only',
                        'assumed_rpm_usd': 2, 'cost_usd': 1}])
        self.assertEqual(result['scenarios'][0]['modeled_revenue_usd'], 0)
        self.assertEqual(result['scenarios'][0]['modeled_profit_usd'], -1)
        self.assertIsNone(result['observed_revenue_usd'])

if __name__ == '__main__':
    unittest.main()
