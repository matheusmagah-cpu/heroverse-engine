"""E219: real tiny-media checks; no network, provider, or audiovisual approval."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))


def run(args):
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', *args], check=True,
                   capture_output=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class E219DraftRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fixtures = Path(cls.tmp.name)
        cls.source = cls.fixtures / 'source.mp4'
        cls.audio = cls.fixtures / 'voice.m4a'
        run(['-f', 'lavfi', '-i', 'color=c=blue:s=160x288:r=30:d=0.2',
             '-an', '-c:v', 'libx264', '-threads', '1', str(cls.source)])
        run(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=0.4',
             '-c:a', 'aac', str(cls.audio)])
        cls.image = cls.fixtures / 'still.jpg'
        run(['-i', str(cls.source), '-frames:v', '1', '-threads', '1', str(cls.image)])
        cls.long_audio = cls.fixtures / 'long.m4a'
        run(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=0.6',
             '-c:a', 'aac', str(cls.long_audio)])
        cls.truncated = cls.fixtures / 'truncated.mp4'
        run(['-i', str(cls.source), '-i', str(cls.long_audio), '-map', '0:v:0',
             '-map', '1:a:0', '-c', 'copy', str(cls.truncated)])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.manifest = self.root / 'manifest.json'
        self.doc = {'segments': [
            {'source': str(self.source), 'sha256': digest(self.source),
             'kind': 'video', 'seconds': 0.2},
            {'source': str(self.source), 'sha256': digest(self.source),
             'kind': 'video', 'seconds': 0.2}],
            'audio_copy': {'source': str(self.audio), 'sha256': digest(self.audio)}}
        self.manifest.write_text(json.dumps(self.doc))
        self.output = self.root / 'draft.mp4'

    def test_e219_long_audio_cannot_hide_short_video(self):
        # The former ad-hoc check accepted the 0.6-second container. Its video
        # is only 0.2 seconds: no amount of trailing audio completes the picture.
        info = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_format', '-of', 'json', str(self.truncated)]))
        self.assertAlmostEqual(float(info['format']['duration']), 0.6, places=2)
        import draft_render as dr
        with dr.Snapshots() as snapshots:
            snap = snapshots.file(self.truncated, digest(self.truncated))
            with self.assertRaisesRegex(dr.RenderError, 'VIDEO_(FRAMES|DURATION)'):
                dr.validate_video(snap, 18, (160, 288), 30, snapshots)

    def render(self):
        import draft_render as dr
        return dr.render(self.manifest, self.output, geometry=(160, 288))

    def test_e219_real_render_copy_timing_and_idempotent_resume(self):
        import draft_render as dr
        first = self.render()
        self.assertEqual(first['validation']['video_frames'], 12)
        self.assertTrue(first['validation']['audio_packets_identical'])
        with patch.object(dr, 'encode_segment', side_effect=AssertionError('unnecessary render')):
            second = self.render()
        self.assertTrue(second['reused_final'])
        self.assertEqual(first['output_sha256'], second['output_sha256'])

    def test_e219_mutated_cache_is_rebuilt_only_for_affected_segment(self):
        import draft_render as dr
        self.render()
        self.output.unlink()
        self.output.with_suffix('.receipt.json').unlink()
        cache = Path(str(self.output) + '.work') / 'segment-000.mp4'
        cache.write_bytes(b'truncated')
        with patch.object(dr, 'encode_segment', wraps=dr.encode_segment) as encode:
            result = self.render()
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(result['reused_segments'], [1])
        self.assertEqual(result['validation']['video_frames'], 12)

    def test_e219_source_hash_drift_fails_without_touching_output(self):
        import draft_render as dr
        self.render()
        old = self.output.read_bytes()
        self.doc['segments'][0]['sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(dr.RenderError, 'SOURCE_HASH_MISMATCH'):
            self.render()
        self.assertEqual(self.output.read_bytes(), old)

    def test_e219_failed_overlay_preserves_existing_output(self):
        import draft_render as dr
        self.render()
        old = self.output.read_bytes()
        bad = self.root / 'invalid.ass'
        bad.write_text('[Script Info]\n[Events]\nnot a valid subtitle track')
        self.doc['ass'] = str(bad)
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(dr.RenderError, 'COMMAND_FAILED ffmpeg'):
            self.render()
        self.assertEqual(self.output.read_bytes(), old)

    def test_e219_output_lock_and_explicit_still_reuse(self):
        import draft_render as dr
        with dr.output_lock(self.output):
            with self.assertRaisesRegex(dr.RenderError, 'OUTPUT_LOCKED'):
                self.render()
        self.doc['segments'][0]['kind'] = 'image'
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(dr.RenderError, 'EXISTING_STILL_REUSE_REQUIRED'):
            self.render()



    def test_e219_explicit_existing_image_reuses_same_visual_route(self):
        import draft_render as dr
        self.doc['reuse_existing_stills'] = True
        self.doc['segments'][0].update(source=str(self.image), sha256=digest(self.image), kind='image')
        self.manifest.write_text(json.dumps(self.doc))
        result = self.render()
        self.assertEqual(result['validation']['video_frames'], 12)
        self.doc['segments'][0].update(source=str(self.source), sha256=digest(self.source))
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(dr.RenderError, 'STILL_SOURCE_IS_NOT_AN_IMAGE'):
            self.render()

    def test_e219_shared_cache_lock_and_input_protection(self):
        import draft_render as dr
        cache = Path(str(self.output) + '.work')
        cache.mkdir()
        with dr.output_lock(cache / 'cache'):
            with self.assertRaisesRegex(dr.RenderError, 'OUTPUT_LOCKED'):
                self.render()
        with self.assertRaisesRegex(dr.RenderError, 'OUTPUT_OVERLAPS_INPUT'):
            dr.render(self.manifest, self.source, geometry=(160, 288))
        with self.assertRaisesRegex(dr.RenderError, 'CACHE_OVERLAPS'):
            dr.render(self.manifest, self.output, self.root, geometry=(160, 288))

    def test_e219_sealed_bytes_reject_write_and_truncate(self):
        import draft_render as dr
        import errno
        import os
        with dr.Snapshots() as snapshots:
            snap = snapshots.data(b'immutable input')
            for operation in (lambda: os.pwrite(snap.fd, b'x', 0),
                              lambda: os.ftruncate(snap.fd, 1)):
                with self.assertRaises(OSError) as error:
                    operation()
                self.assertEqual(error.exception.errno, errno.EPERM)
            self.assertEqual(dr.read_fd(snap.fd), b'immutable input')

    def test_e219_corrupt_final_receipt_and_unsupported_music(self):
        import draft_render as dr
        self.render()
        self.output.with_suffix('.receipt.json').write_text('{invalid')
        # Uncertain receipt never qualifies for the final reuse shortcut.
        with patch.object(dr, 'encode_segment', side_effect=AssertionError('valid cache discarded')):
            result = self.render()
        self.assertFalse(result['reused_final'])
        self.assertEqual(result['reused_segments'], [0, 1])
        self.doc['music'] = 'do-not-ignore.wav'
        self.manifest.write_text(json.dumps(self.doc))
        with self.assertRaisesRegex(dr.RenderError, 'MUSIC_UNSUPPORTED'):
            self.render()


if __name__ == '__main__':
    unittest.main()
