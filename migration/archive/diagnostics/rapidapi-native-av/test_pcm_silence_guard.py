import contextlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import shutil
import tempfile
import unittest
from unittest import mock

from run_audio_reviewer import inspect_pcm_wave
import run_audio_reviewer


def wav(pcm, channels=1, bits=16, rate=16000, encoding=1):
    width = bits // 8
    fmt = struct.pack('<HHIIHH', encoding, channels, rate, rate * channels * width, channels * width, bits)
    body = b'WAVEfmt ' + struct.pack('<I', len(fmt)) + fmt
    body += b'data' + struct.pack('<I', len(pcm)) + pcm + (b'\0' if len(pcm) % 2 else b'')
    return b'RIFF' + struct.pack('<I', len(body)) + body


class PcmTests(unittest.TestCase):
    def test_exact_zero_mono_stereo_all_supported_widths(self):
        for channels in (1, 2):
            for bits in (8, 16, 24, 32):
                with self.subTest(channels=channels, bits=bits):
                    pcm = bytes([128 if bits == 8 else 0]) * (bits // 8) * channels * 13
                    result = inspect_pcm_wave(wav(pcm, channels, bits))
                    self.assertEqual(result['description'], 'digital silence')
                    self.assertFalse(result['allow_model_inference'])
                    self.assertFalse(result['perceptual_quality_approved'])
                    self.assertEqual(result['frames'], 13)

    def test_one_lsb_in_either_channel_is_not_digital_silence(self):
        for channels in (1, 2):
            for bits in (8, 16, 24, 32):
                for channel in range(channels):
                    with self.subTest(channels=channels, bits=bits, channel=channel):
                        pcm = bytearray([128 if bits == 8 else 0] * (bits // 8) * channels * 2)
                        pcm[(channels + channel) * (bits // 8)] += 1
                        result = inspect_pcm_wave(wav(pcm, channels, bits))
                        self.assertEqual(result['status'], 'NONZERO_PCM')
                        self.assertFalse(result['digital_silence'])
                        self.assertTrue(result['allow_model_inference'])
                        self.assertFalse(result['perceptual_quality_approved'])
                        self.assertNotIn('description', result)

    def test_unsigned_eight_bit_zero_bytes_are_not_silence(self):
        self.assertFalse(inspect_pcm_wave(wav(b'\0' * 8, bits=8))['digital_silence'])

    def test_invalid_and_unsupported_fail_closed(self):
        valid = wav(b'\0' * 8)
        bad_align = bytearray(valid)
        struct.pack_into('<H', bad_align, 32, 4)
        bad_rate = bytearray(valid)
        struct.pack_into('<I', bad_rate, 28, 0)
        cases = [b'', b'not wave', wav(b''), valid[:-1], valid + b'\0',
                 wav(b'\0', bits=16), wav(b'\0' * 6, channels=2),
                 wav(b'\0' * 8, rate=0), wav(b'\0' * 8, encoding=3),
                 wav(b'\0' * 8, channels=0), bytes(bad_align), bytes(bad_rate)]
        # Every truncated prefix must be invalid, even if it contains some zero frames.
        cases.extend(valid[:i] for i in range(len(valid)))
        for data in cases:
            with self.subTest(length=len(data)):
                result = inspect_pcm_wave(data)
                self.assertEqual(result['status'], 'INVALID_OR_UNSUPPORTED_PCM')
                self.assertIsNone(result['digital_silence'])
                self.assertFalse(result['allow_model_inference'])
                self.assertFalse(result['perceptual_quality_approved'])

    def test_duplicate_data_and_partial_chunk_headers_fail_closed(self):
        base = wav(b'\0' * 8)
        for extra in (b'data\x00\x00\x00\x00', b'x'):
            data = base + extra
            data = data[:4] + struct.pack('<I', len(data)-8) + data[8:]
            self.assertEqual(inspect_pcm_wave(data)['status'], 'INVALID_OR_UNSUPPORTED_PCM')


class ReviewerIntegrationTests(unittest.TestCase):
    def invoke(self, data, model='qwen', case='silence', inference=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'rapidapi-native-av'
            out = root / ('qwen-audio-reviewer-results' if model == 'qwen' else 'audio-reviewer-results')
            out.mkdir(parents=True)
            (out / (case+'.wav')).write_bytes(data)
            (out / (case+'.stdout.txt')).write_text('historical hallucinated tone')
            (out / (case+'.stderr.txt')).write_text('historical log')
            if inference:
                weights = root/'weights'
                projector = root/'projector'
                weights.write_bytes(b'fixture')
                projector.write_bytes(b'fixture')
                manifest = {'files': [{'path':str(p), 'bytes':7} for p in (weights, projector)]}
                (root / ('qwen-reviewer-model-receipt.json' if model=='qwen' else 'reviewer-model-receipt.json')).write_text(json.dumps(manifest))
            with mock.patch.object(run_audio_reviewer, 'Path', side_effect=lambda p: root if p == 'rapidapi-native-av' else Path(p)), \
                 mock.patch('sys.argv', ['run_audio_reviewer.py', '--case', case, '--model', model]), \
                 mock.patch.object(run_audio_reviewer.subprocess, 'run') as execute, \
                 contextlib.redirect_stdout(io.StringIO()):
                execute.return_value.returncode = 0
                code = run_audio_reviewer.main()
            result = json.loads((out/(case+'.json')).read_text())
            if not inference:
                self.assertEqual((out/(case+'.stdout.txt')).read_text(), 'historical hallucinated tone')
                self.assertEqual((out/(case+'.stderr.txt')).read_text(), 'historical log')
                self.assertFalse(result['model_stdout_used_as_evidence'])
                self.assertTrue(result['prior_stdout_stderr_ignored'])
                self.assertIsNone(result['stdout_file'])
                self.assertIsNone(result['stderr_file'])
            return code, result, execute

    def test_standalone_staging_contract_needs_no_sibling_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            staged = Path(temporary)/'run_audio_reviewer.py'
            shutil.copyfile(run_audio_reviewer.__file__, staged)
            # Import only: do not call main, generate media or launch inference.
            check = subprocess.run([sys.executable, '-I', '-c',
                "import runpy; m = runpy.run_path(" + repr(str(staged)) + "); "
                "assert callable(m['inspect_pcm_wave']); assert callable(m['main'])"],
                cwd=temporary, capture_output=True, text=True, timeout=10)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_real_cli_needs_no_weights_or_binary_for_guarded_inputs(self):
        script = Path(run_audio_reviewer.__file__).resolve()
        for data, expected_code, expected_status in (
            (wav(b'\0' * 8), 0, 'SKIPPED_DIGITAL_SILENCE'),
            (b'truncated', 2, 'BLOCKED_INVALID_PCM'),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                staged = Path(temporary)/'run_audio_reviewer.py'
                shutil.copyfile(script, staged)
                out = Path(temporary) / 'rapidapi-native-av/qwen-audio-reviewer-results'
                out.mkdir(parents=True)
                (out/'silence.wav').write_bytes(data)
                # Only invoke the Python CLI; input is cached and all model files are absent.
                run = subprocess.run([sys.executable, str(staged), '--case', 'silence',
                                      '--model', 'qwen'], cwd=temporary,
                                     capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, expected_code, run.stderr)
                result = json.loads(run.stdout)
                self.assertEqual(result['exit_code'], expected_status)
                self.assertFalse(result['model_inference_performed'])
                self.assertFalse((out/'silence.stdout.txt').exists())

    def test_recorded_qwen_hallucination_is_short_circuited(self):
        evidence = Path(__file__).resolve().parents[2] / 'evidence/cloud-video-player-20261015/native-audio-understanding-result.json'
        receipt = json.loads(evidence.read_text())
        control = receipt['controls']['qwen_digital_silence']
        self.assertTrue(control['pcm_verified_all_zero'])
        self.assertEqual(control['result'], 'FAILED_HALLUCINATED_SOUND_ON_DIGITAL_SILENCE')
        self.assertIn('sustained, high-pitched electronic tone', control['model_output'])
        # Reconstruct the documented 10-second, mono 16 kHz digital-zero control;
        # no model rerun and no claim that this synthetic WAV is the original file.
        code, result, execute = self.invoke(wav(b'\0' * 320000))
        execute.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(result['description'], 'digital silence')
        self.assertEqual(result['exit_code'], 'SKIPPED_DIGITAL_SILENCE')
        self.assertFalse(result['model_inference_performed'])
        self.assertTrue(result['candidate_not_adopted'])
        self.assertFalse(result['perceptual_quality_approved'])
        self.assertFalse(result['semantic_approval_from_model_prose'])
        self.assertEqual(receipt['controls']['gemma_e2b']['status'], 'REJECTED_FOR_CURRENT_REVIEW')
        self.assertFalse(any(receipt['approvals'].values()))

    def test_both_reviewers_guard_content_not_case_label(self):
        for model in ('qwen', 'gemma'):
            code, result, execute = self.invoke(wav(b'\0' * 8), model, 'opening-full')
            execute.assert_not_called()
            self.assertEqual(result['description'], 'digital silence')
            self.assertEqual(code, 0)

    def test_invalid_input_blocks_before_missing_model_receipt(self):
        for data in (b'', b'invalid', wav(b'\0' * 8)[:-1]):
            code, result, execute = self.invoke(data)
            execute.assert_not_called()
            self.assertEqual(code, 2)
            self.assertEqual(result['exit_code'], 'BLOCKED_INVALID_PCM')
            self.assertFalse(result['model_inference_performed'])
            self.assertFalse(result['perceptual_quality_approved'])

    def test_nonzero_keeps_candidate_inference_without_approval(self):
        code, result, execute = self.invoke(wav(b'\1\0' + b'\0' * 6), inference=True)
        execute.assert_called_once()
        self.assertFalse(result['pcm_guard']['digital_silence'])
        self.assertTrue(result['model_inference_performed'])
        self.assertFalse(result['semantic_approval_from_model_prose'])
        self.assertFalse(result['perceptual_quality_approved'])
        self.assertTrue(result['candidate_not_adopted'])
        self.assertEqual(result['exit_code'], 0)


if __name__ == '__main__':
    unittest.main()
