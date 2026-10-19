#!/usr/bin/env python3
"""Known-answer arithmetic and boundary tests; not native-instrument qualification."""
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_metrics as nm

TEXT = 'you thou thee thy thine hath doth unto ye shalt saith walketh you love peace today always trust in god'


def profile(text=TEXT, speech=.5, music=.25):
    return {"sound_classes": {"transcript": text, "presence_fraction": {"speech": speech, "music": music}},
            "editing": {"picture_changes_per_minute": 3}, "loudness": {"integrated_lufs": -16}}


def mined(start=0, end=60, text=TEXT):
    return [{"window_start_seconds": start, "window_end_seconds": end,
             "transcript": [{"start_seconds": start, "text": text}], "beats": []}]


def measured_window(start=0, p=None):
    return nm.window_metrics('v', start, start + 60, profile() if p is None else p, mined(start, start + 60))


class WindowTests(unittest.TestCase):
    def test_exact_known_answer(self):
        row = measured_window()
        self.assertEqual(row['speech_fraction'], .5)
        self.assertEqual(row['music_fraction'], .25)
        self.assertEqual(row['wpm'], 40)
        self.assertEqual(row['you_per_100'], 10)
        self.assertEqual(row['kjv_markers_per_min'], 22)
        self.assertEqual(row['picture_changes_per_minute'], 3)
        self.assertEqual(row['integrated_lufs'], -16)
        self.assertEqual(row['opening_words'], TEXT.split())
        self.assertEqual(row['agreement'], 1)
        self.assertEqual(row['comparison']['status'], 'COMPARED')
        self.assertEqual(row['reasons'], {})

    def test_opening_20_tokens_only_at_zero(self):
        p = profile(TEXT + ' extra words')
        self.assertEqual(measured_window(p=p)['opening_words'], TEXT.split())
        row = measured_window(120)
        self.assertIsNone(row['opening_words'])
        self.assertIn('opening_words', row['reasons'])

    def test_wpm_speech_threshold_is_exact(self):
        self.assertEqual(measured_window(p=profile(speech=1/6))['wpm'], 120)
        row = measured_window(p=profile(speech=.16))
        self.assertIsNone(row['wpm'])
        self.assertEqual(row['reasons']['wpm'], 'speech duration below 10 seconds')
        self.assertAlmostEqual(row['kjv_markers_per_min'], 11 / 9.6 * 60)

    def test_missing_is_null_with_reason_not_zero(self):
        row = measured_window(p={})
        for key in nm.METRICS + ('opening_words',):
            self.assertIsNone(row[key], key)
            self.assertTrue(row['reasons'][key], key)
        self.assertEqual(row['comparison']['status'], 'ASR_MISSING')

    def test_zero_observations_preserved_and_no_division_by_zero(self):
        p = profile('', speech=0, music=0)
        p['editing']['picture_changes_per_minute'] = 0
        row = measured_window(p=p)
        self.assertEqual(row['speech_fraction'], 0)
        self.assertEqual(row['music_fraction'], 0)
        self.assertEqual(row['picture_changes_per_minute'], 0)
        for key in ('wpm', 'you_per_100', 'kjv_markers_per_min', 'agreement'):
            self.assertIsNone(row[key])
            self.assertIn(key, row['reasons'])

    def test_marker_words_not_substrings_and_no_double_count(self):
        row = measured_window(p=profile('thou hath walketh you youth otherwise method', speech=1))
        self.assertEqual(row['kjv_markers_per_min'], 3)
        self.assertAlmostEqual(row['you_per_100'], 100 / 7)

    def test_agreement_is_comparator_not_model_or_profile_value(self):
        p = profile()
        p['agreement'] = .1
        self.assertEqual(measured_window(p=p)['agreement'], 1)
        missing = nm.window_metrics('v', 0, 60, p, [])
        self.assertIsNone(missing['agreement'])
        self.assertEqual(missing['reasons']['agreement'], 'MINED_WINDOW_MISSING')
        invalid = nm.window_metrics('v', 0, 60, p, mined(text='word ' * 800))
        self.assertIsNone(invalid['agreement'])
        self.assertEqual(invalid['comparison']['status'], 'MINED_WINDOW_INVALID')

    def test_invalid_nonfinite_fraction_is_unknown(self):
        for value in (True, -1, 2, float('nan'), float('inf')):
            row = measured_window(p=profile(speech=value))
            self.assertIsNone(row['speech_fraction'])
            self.assertIn('speech_fraction', row['reasons'])


class VideoTests(unittest.TestCase):
    def test_three_windows_and_exact_threshold(self):
        windows = [measured_window(s) for s in (0, 120, 240)]
        windows[0]['agreement'] = .85
        summary = nm.video_summary('v', windows, {'format': 'prayer', 'role': 'winner'})
        self.assertTrue(summary['validated'])
        self.assertEqual(summary['n_windows'], 3)
        self.assertEqual(summary['n_compared'], 3)
        self.assertEqual(summary['role'], 'winner')
        self.assertEqual(summary['wpm'], 40)
        self.assertFalse(nm.video_summary('v', windows[:2], {})['validated'])
        windows[0]['agreement'] = .849
        self.assertFalse(nm.video_summary('v', windows, {})['validated'])

    def test_invalid_or_missing_window_rejects(self):
        for status in ('MINED_WINDOW_INVALID', 'MINED_WINDOW_MISSING', 'MINED_OMISSION', 'ASR_SILENT_MINED_SPEECH'):
            windows = [measured_window(s) for s in (0, 120, 240)]
            windows[-1]['comparison'] = {'status': status}
            windows[-1]['agreement'] = None
            row = nm.video_summary('v', windows, {})
            self.assertFalse(row['validated'])
            self.assertEqual(row['validation_reason'], 'BAD_WINDOW:' + status)

    def test_v3_compared_minimum_and_no_speech(self):
        windows = [measured_window(s) for s in (0, 120, 240)]
        for w in windows:
            w['comparison'] = {'status': 'NO_SPEECH'}
            w['agreement'] = None
        row = nm.video_summary('v', windows, {})
        self.assertFalse(row['validated'])
        self.assertEqual(row['n_compared'], 0)
        self.assertEqual(row['validation_reason'], 'FEW_COMPARED')
        windows[0] = measured_window(0)
        self.assertEqual(nm.video_summary('v', windows, {})['validation_reason'], 'FEW_COMPARED')
        windows[1] = measured_window(120)
        self.assertTrue(nm.video_summary('v', windows, {})['validated'])

    def test_v3_first_failing_reason_order(self):
        windows = [measured_window(s) for s in (0, 120, 240)]
        windows[0]['agreement'] = .849
        windows[2]['comparison'] = {'status': 'MINED_OMISSION'}
        windows[2]['agreement'] = None
        self.assertEqual(nm.video_summary('v', windows[:2], {})['validation_reason'], 'FEW_WINDOWS')
        windows[1]['comparison'] = {'status': 'NO_SPEECH'}
        windows[1]['agreement'] = None
        self.assertEqual(nm.video_summary('v', windows, {})['validation_reason'], 'FEW_COMPARED')
        windows[1] = measured_window(120)
        self.assertEqual(nm.video_summary('v', windows, {})['validation_reason'], 'LOW_AGREEMENT')
        windows[0]['agreement'] = .85
        self.assertEqual(nm.video_summary('v', windows, {})['validation_reason'], 'BAD_WINDOW:MINED_OMISSION')
        windows[2] = measured_window(240)
        self.assertTrue(nm.video_summary('v', windows, {})['validated'])

    def test_video_median_not_mean_and_missing_metadata(self):
        windows = [measured_window(s) for s in (0, 120, 240)]
        for w, value in zip(windows, [10, 20, 99]):
            w['wpm'] = value
        row = nm.video_summary('v', windows, {})
        self.assertEqual(row['wpm'], 20)
        for key in ('role', 'format'):
            self.assertIsNone(row[key])
            self.assertIn(key, row['reasons'])

    def test_empty_video_has_nulls_and_failure_reason(self):
        row = nm.video_summary('v', [], {})
        self.assertFalse(row['validated'])
        self.assertEqual(row['n_windows'], 0)
        for key in nm.METRICS:
            self.assertIsNone(row[key])
            self.assertIn(key, row['reasons'])


class BootstrapTests(unittest.TestCase):
    def test_known_constant_population(self):
        self.assertEqual(nm.bootstrap([12] * 8), {'median': 12, 'interval_90': [12, 12], 'n': 8, 'reason': None})
        self.assertEqual(nm.bootstrap([1, 3, 90])['median'], 3)

    def test_exact_independent_resampling_answer(self):
        values = [1, 2, 3, 5, 8, 13, 21, 34]
        rng = random.Random(20261019)
        sample = []
        for _ in range(2000):
            draw = [values[int(rng.random() * len(values))] for _ in values]
            draw.sort()
            sample.append((draw[3] + draw[4]) / 2)
        sample.sort()
        expected = [sample[99] * .05 + sample[100] * .95,
                    sample[1899] * .95 + sample[1900] * .05]
        self.assertEqual(nm.bootstrap(values)['interval_90'], expected)
        self.assertEqual(nm.bootstrap(values), nm.bootstrap(list(reversed(values))))

    def test_missing_and_singleton(self):
        empty = nm.bootstrap([None])
        self.assertIsNone(empty['median'])
        self.assertIsNone(empty['interval_90'])
        self.assertTrue(empty['reason'])
        self.assertEqual(nm.bootstrap([4, None])['interval_90'], [4, 4])

    def test_group_threshold_roles_and_video_resampling(self):
        videos = [nm.video_summary(str(i), [measured_window(s) for s in (0, 120, 240)],
                                   {'format': 'prayer', 'role': 'winner'}) for i in range(8)]
        for i, row in enumerate(videos):
            row['wpm'] = i
        group = nm.group_summary(videos)[0]
        self.assertEqual(group['status'], 'MEASURED')
        self.assertEqual(group['n_videos'], 8)
        self.assertEqual(group['n_validated'], 8)
        self.assertEqual(group['measures']['wpm'], nm.bootstrap(list(range(8))))
        videos[-1]['validated'] = False
        self.assertEqual(nm.group_summary(videos)[0]['status'], 'INSUFFICIENT')
        for role in ('latest', 'weak_contrast', 'other', None):
            videos[0]['role'] = role
            groups = nm.group_summary(videos)
            self.assertTrue(any(g['role'] == role for g in groups))
        self.assertEqual(nm.group_summary([]), [])


class FileTests(unittest.TestCase):
    def test_missing_input_directories_do_not_succeed_silently(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for profiles, structure in ((root / 'missing', root), (root, root / 'missing')):
                with self.assertRaisesRegex(ValueError, 'input directory does not exist'):
                    nm.measure(profiles, root / 'ledger', root / 'measured', structure)

    def test_ledger_missing_profiles_and_duplicate_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pd, sd = root / 'p', root / 's'
            pd.mkdir(); sd.mkdir()
            ledger, metadata = root / 'ledger.json', root / 'measured.json'
            ledger.write_text(json.dumps({'claims': [{'video_id': 'missing', 'start_seconds': 0, 'end_seconds': 60}]}))
            metadata.write_text(json.dumps({'videos': []}))
            path = pd / 'acq-v-0-60-v1.json'
            path.write_text(json.dumps({'profiles': []}))
            result = nm.measure(pd, ledger, metadata, sd)
            self.assertFalse(result['windows'][0]['ledger_recorded'])
            self.assertIn('ledger_recorded', result['windows'][0]['reasons'])
            self.assertTrue(any(n.get('video_id') == 'missing' for n in result['notes']))
            for key in nm.METRICS:
                self.assertIsNone(result['windows'][0][key])
                self.assertIn(key, result['windows'][0]['reasons'])
            (pd / 'acq-v-0-60-v2.json').write_text(path.read_text())
            with self.assertRaisesRegex(ValueError, 'duplicate native window'):
                nm.measure(pd, ledger, metadata, sd)

    def test_isolated_cli_known_answer_with_real_comparator(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pd, sd = root / 'profiles', root / 'structure'
            pd.mkdir(); sd.mkdir()
            claims = []
            for start in (0, 120, 240):
                claims.append({'video_id': 'v', 'start_seconds': start, 'end_seconds': start + 60})
                (pd / f'acq-v-{start}-{start+60}-v1.json').write_text(json.dumps({'profiles': [profile()]}))
            (sd / 'structure-v.json').write_text(json.dumps({'video': {'video_id': 'v'},
                'windows': sum([mined(s, s+60) for s in (0, 120, 240)], [])}))
            (root / 'ledger.json').write_text(json.dumps({'claims': claims}))
            (root / 'measured.json').write_text(json.dumps({'videos': [{'video_id': 'v', 'role': 'winner', 'format': 'prayer'}]}))
            out = root / 'out.json'
            command = [sys.executable, '-I', '-B', str(Path(nm.__file__).resolve()), str(pd),
                       str(root / 'ledger.json'), str(root / 'measured.json'), str(sd), str(out)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            first = out.read_bytes()
            result = json.loads(first)
            self.assertEqual(result['version'], 'native-metrics-v1')
            self.assertEqual(len(result['windows']), 3)
            self.assertTrue(result['videos'][0]['validated'])
            self.assertEqual(result['videos'][0]['wpm'], 40)
            self.assertEqual(result['by_format_and_role'][0]['status'], 'INSUFFICIENT')
            self.assertTrue(all(r['ledger_recorded'] for r in result['windows']))
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(out.read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
