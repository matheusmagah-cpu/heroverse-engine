"""Sweep reproduction: imported receipt bytes must be the bytes rendered.

Synthetic local fixtures only. The interleaving changes captions after imported
verification and immediately before the real renderer reads them.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'migration/production/bible'))
import test_episode_build as fixtures
import existing_edit as importer

ASS = '''[Script Info]
ScriptType: v4.00+
PlayResX: 160
PlayResY: 288
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,12,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,4,4,4,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Original caption.
'''


class BoundRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source, self.work = self.base/'source', self.base/'imported'
        _, binding = fixtures.ExistingEditImport().fixture(self.source)
        image = self.source/'image.png'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i',
                        'color=c=blue:s=160x288:r=30:d=2','-frames:v','1','-threads','1',str(image)],check=True)
        (self.source/'captions.ass').write_text(ASS)
        manifest_path=self.source/'manifest.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['segments'][0]['sha256']=fixtures.eb.sha256(image)
        manifest['segments'][0]['crop']=[0,0,160,288]
        fixtures.eb.save(manifest_path,manifest)
        binding['manifest']['sha256']=fixtures.eb.sha256(manifest_path)
        binding['captions']['sha256']=fixtures.eb.sha256(self.source/'captions.ass')
        fixtures.eb.save(self.source/'binding.json',binding)
        self.receipt=fixtures.eb.import_edit_step(self.source/'binding.json',self.source,self.work)

    def render(self, mutate):
        actual=importer.dr.render
        def interleave(manifest,output,**kwargs):
            if mutate == 'captions':
                (self.work/'captions.ass').write_text(ASS.replace('Original caption.','Altered caption.'))
            if mutate == 'manifest':
                doc=json.loads(Path(manifest).read_text())
                doc['segments'][0]['crop']=[0,0,80,144]
                Path(manifest).write_text(json.dumps(doc))
            return actual(manifest,output,geometry=(160,288),**kwargs)
        with patch.object(importer.dr,'render',side_effect=interleave):
            return importer.render_imported(self.work,self.base/'draft.mp4')

    def test_bound_legitimate_render(self):
        result=self.render(False)
        self.assertEqual(result['subtitle_sha256'],self.receipt['outputs']['captions.ass'])
        self.assertTrue(result['validation']['audio_packets_identical'])
        self.assertEqual(result['validation']['video_frames'],60)
        self.assertFalse(result['publication_approved'])

    def test_caption_change_after_verify_never_becomes_imported_render(self):
        try:
            result=self.render('captions')
        except ValueError:
            return  # Refusing before output is an acceptable closed boundary.
        self.assertEqual(result['subtitle_sha256'],self.receipt['outputs']['captions.ass'],
                         'Renderer consumed changed captions after imported verification')


    def test_manifest_change_after_verify_never_becomes_imported_render(self):
        try:
            result=self.render('manifest')
        except ValueError:
            return
        self.assertEqual(result['manifest_sha256'],self.receipt['outputs']['manifest.json'],
                         'Renderer consumed changed manifest after imported verification')

    def test_nonfinite_segment_is_refused_before_import_writes(self):
        path=self.source/'manifest.json'
        doc=json.loads(path.read_text());doc['segments'][0]['seconds']=float('nan')
        fixtures.eb.save(path,doc)
        binding=json.loads((self.source/'binding.json').read_text())
        binding['manifest']['sha256']=fixtures.eb.sha256(path)
        fixtures.eb.save(self.source/'binding.json',binding)
        destination=self.base/'nonfinite-import'
        with self.assertRaisesRegex(ValueError,'EXISTING_EDIT_SEGMENT_TIMING'):
            fixtures.eb.import_edit_step(self.source/'binding.json',self.source,destination)
        self.assertFalse(destination.exists())


if __name__=='__main__':
    unittest.main()
