"""Fresh offline native-import qualification. Never activates an operational runtime."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import socket
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ARCHIVE_SHA = 'fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'
DEPENDENCIES = ('opencv-python', 'numpy', 'faster-whisper', 'Pillow',
                'rapidocr', 'onnxruntime', 'jsonschema', 'yt-dlp')
BLOCKED = []


def install_offline_guard(host_netns):
    current = os.readlink('/proc/self/ns/net')
    if not host_netns or current == host_netns:
        raise PermissionError('FRESH_NETWORK_NAMESPACE_REQUIRED')
    interfaces = sorted(name for _, name in socket.if_nameindex())
    if interfaces != ['lo']:
        raise PermissionError('ISOLATED_NAMESPACE_MUST_HAVE_ONLY_LOOPBACK')
    forbidden = {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg',
                 'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.fork', 'os.exec'}
    def audit(event, args):
        if event in forbidden:
            BLOCKED.append(event)
            raise PermissionError('OFFLINE_QUALIFICATION_DENIED:' + event)
    sys.addaudithook(audit)
    for action in (lambda: socket.getaddrinfo('invalid.example', 443),
                   lambda: os.system('exit 99')):
        try:
            action()
        except PermissionError:
            pass
        else:
            raise RuntimeError('OFFLINE_DENIAL_SELF_TEST_FAILED')
    if BLOCKED != ['socket.getaddrinfo', 'os.system']:
        raise RuntimeError('OFFLINE_DENIAL_SELF_TEST_DIVERGED')
    return {'fresh_network_namespace': True, 'interfaces': interfaces,
            'python_network_and_process_audit_guard': True,
            'denial_self_tests_passed': 2}


def selected_extract(archive, source):
    names = set()
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = PurePosixPath(info.filename)
            wanted = (info.filename.startswith('project/hero_engine/') and info.filename.endswith('.py')) or info.filename in {
                'project/config/engine.json', 'project/tests/test_engine.py', 'project/tests/__init__.py'}
            if not wanted:
                continue
            if info.filename in names or name.is_absolute() or '..' in name.parts or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise PermissionError('UNSAFE_OR_DUPLICATE_SELECTED_SOURCE_ENTRY')
            names.add(info.filename)
            destination = source.joinpath(*name.parts[1:])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(z.read(info))
    return len(names)


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--host-netns', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    # Installed before any third-party/native module import or test execution.
    guard = install_offline_guard(args.host_netns)
    archive = args.archive.resolve()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise PermissionError('IMMUTABLE_ARCHIVE_IDENTITY_CHANGED')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      DO_NOT_TRACK='1', PYTHONDONTWRITEBYTECODE='1',
                      HERO_FORECAST_SOURCE_ARCHIVE=str(archive))
    sys.dont_write_bytecode = True
    here = Path(__file__).resolve().parent
    from apply_forecast_truthfulness_overlay import apply, EXPECTED
    pinned = {}
    for line in (here / 'forecast-qualification-requirements.txt').read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.count('==') != 1:
            raise RuntimeError('EXACT_DIRECT_DEPENDENCY_PIN_REQUIRED')
        name, version = line.split('==')
        if importlib.metadata.version(name) != version:
            raise RuntimeError('INSTALLED_DIRECT_DEPENDENCY_VERSION_DIFFERS:' + name)
        pinned[name] = version
    with tempfile.TemporaryDirectory(prefix='heroverse-forecast-qualification-') as temporary:
        root = Path(temporary); source = root / 'original'; shadow = root / 'shadow'
        selected_count = selected_extract(archive, source)
        overlay = apply(source, shadow)
        # First run the 12 exact-function/negative guard tests against the same archive.
        checks = load_file('forecast_overlay_checks', here / 'test_forecast_truthfulness_overlay.py')
        suite = unittest.defaultTestLoader.loadTestsFromModule(checks)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful() or result.testsRun != 12:
            raise RuntimeError('TWELVE_OFFLINE_GUARD_TESTS_REQUIRED')
        sys.path.insert(0, str(shadow))
        # Actual dependency-complete module import; no import stubs or AST extraction.
        import hero_engine.cli as cli
        import hero_engine.forecast as forecast
        import hero_engine.db as db
        loaded = {}
        for module in (cli, forecast):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(shadow):
                raise PermissionError('NATIVE_MODULE_NOT_LOADED_FROM_EXACT_SHADOW')
            loaded[path.relative_to(shadow).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        help_output = io.StringIO()
        with patch.object(sys, 'argv', ['hero-engine', '--help']), contextlib.redirect_stdout(help_output):
            try:
                cli.main()
            except SystemExit as exc:
                if exc.code != 0:
                    raise
            else:
                raise RuntimeError('CLI_HELP_DID_NOT_EXIT_NORMALLY')
        if 'forecast' not in help_output.getvalue():
            raise RuntimeError('CLI_FORECAST_COMMAND_NOT_ADVERTISED')
        # Only reviewed pure forecast methods, never broad test discovery.
        native_tests = load_file('native_forecast_tests', shadow / 'tests/test_engine.py')
        selected = ('test_deterministic_math',
                    'test_operational_config_does_not_impute_ypp_progress_or_cadence',
                    'test_forecast_is_reproducible',
                    'test_channel_samples_do_not_prove_predictive_calibration')
        native_suite = unittest.TestSuite(native_tests.HeroEngineTests(name) for name in selected)
        native_result = unittest.TextTestRunner(verbosity=2).run(native_suite)
        if not native_result.wasSuccessful() or native_result.testsRun != 4:
            raise RuntimeError('SELECTED_NATIVE_FORECAST_REGRESSION_FAILED')
        # Exercise real imported command -> JSON/Markdown -> disposable SQLite.
        db_path = root / 'forecast.sqlite'
        with sqlite3.connect(db_path) as con:
            con.execute('CREATE TABLE daily_forecasts (generated_at TEXT, scenario TEXT, horizon_days INTEGER, payload TEXT)')
        config_path = shadow / 'config/engine.json'
        if db.DEFAULT_CONFIG.resolve() != config_path.resolve() or not config_path.is_file():
            raise RuntimeError('NATIVE_CONFIG_BINDING_DIVERGED')
        original_config = cli.load_config()
        config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
        # cli.ROOT is an output-root binding; load_config resolves db.DEFAULT_CONFIG.
        # Assert that distinction before executing the real command.
        with patch.object(cli, 'ROOT', root):
            if cli.load_config() != original_config:
                raise RuntimeError('OUTPUT_ROOT_CHANGED_NATIVE_CONFIG')
        samples = [{'format': kind} for kind in ('long', 'short') for _ in range(10)]
        with patch.object(cli, 'ROOT', root), patch.object(cli, 'rows', return_value=samples), \
             patch.object(cli, 'connect', side_effect=lambda: sqlite3.connect(db_path)), \
             patch.object(cli, '_print_json'), contextlib.redirect_stdout(io.StringIO()):
            cli.command_forecast(argparse.Namespace(days=7))
        file_results = json.loads((root / 'output/reports/forecast-7d.json').read_text())
        with sqlite3.connect(db_path) as con:
            stored = [json.loads(row[0]) for row in con.execute('SELECT payload FROM daily_forecasts')]
        if stored != file_results or not stored or any(
            r['calibration']['status'] != 'empirical_inputs_only' or
            r['calibration']['predictive_calibration_status'] != 'UNAVAILABLE' or
            any(v is not None for v in r['probability'].values()) for r in stored):
            raise RuntimeError('NATIVE_FORECAST_REPORT_OR_DATABASE_TRUTHFULNESS_FAILED')
        for path, digest in EXPECTED.items():
            if hashlib.sha256((source / path).read_bytes()).hexdigest() != digest:
                raise RuntimeError('ORIGINAL_SOURCE_CHANGED')
        expected_loaded = {row['path']: row['shadow_sha256'] for row in overlay['changes']}
        if any(expected_loaded[path] != digest for path, digest in loaded.items()):
            raise RuntimeError('LOADED_SHADOW_HASH_DIVERGED')
        if BLOCKED != ['socket.getaddrinfo', 'os.system']:
            raise RuntimeError('UNEXPECTED_NETWORK_OR_PROCESS_ATTEMPT_DURING_QUALIFICATION')
        receipt = {'version': 'forecast-truthfulness-cloud-qualification-v1',
            'status': 'OFFLINE_SHADOW_NATIVE_CLI_QUALIFIED_NOT_DEPLOYED',
            'archive_sha256': ARCHIVE_SHA, 'selected_archive_entries': selected_count,
            'overlay_changes': overlay['changes'], 'loaded_code_sha256': loaded,
            'guard': guard, 'offline_guard_tests_passed': result.testsRun,
            'native_forecast_tests_passed': native_result.testsRun,
            'native_forecast_tests': list(selected), 'actual_cli_help_passed': True,
            'actual_cli_report_and_temporary_database_passed': True,
            'native_config_sha256': config_hash,
            'temporary_output_root_preserves_native_config': True,
            'direct_dependency_versions': pinned,
            'resolved_environment_versions': {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()},
            'original_preserved': True, 'active_runtime_installed': False,
            'predictive_calibration_available': False, 'production_ready': False,
            'publication_performed': False, 'models_downloaded': False,
            'provider_calls_performed': False, 'full_regression_suite_run': False}
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise RuntimeError('ARCHIVE_CHANGED_DURING_QUALIFICATION')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
