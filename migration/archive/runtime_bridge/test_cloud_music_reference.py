import ast, copy, importlib, json, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path('/workspace/scratch/f2180567de8e/heroverse-native-gop300')
import sys
sys.path.insert(0,str(ROOT))
from hero_engine import qa_phase5 as qa
from hero_engine import cloud_music_reference as bridge

class CloudMusicReferenceTests(unittest.TestCase):
    def binding(self,root=ROOT):return {'path':str(root/bridge.DIRECTORY/'observation.json'),'sha256':bridge.OBSERVATION_SHA}
    def test_native_reader_authenticates_actual_source_without_inference(self):
        with patch('subprocess.run',side_effect=AssertionError('no repeated inference or decode')):
            reference=qa._read_selected_rest_music_reference(ROOT,self.binding(),failure_message='denied')
        self.assertTrue(reference['full_duration_observed']);self.assertEqual(len(reference['windows']),20)
        self.assertEqual(bridge.reference_floors(reference),bridge.HISTORICAL_FLOORS)
        self.assertFalse(reference['cloud_independent_reference']['historical_reference_restored'])
    def test_unknown_rehashed_observation_cannot_select_successor(self):
        wrong=self.binding();wrong['sha256']='sha256:'+'1'*64
        with self.assertRaises(PermissionError):qa._read_selected_rest_music_reference(ROOT,wrong,failure_message='denied')
    def fixture(self,base):
        directory=base/bridge.DIRECTORY;directory.mkdir(parents=True)
        for name in bridge.PINS:shutil.copy2(ROOT/bridge.DIRECTORY/name,directory/name)
        return directory
    def test_modified_observation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=self.fixture(root);p=directory/'observation.json'
            d=json.loads(p.read_text());d['windows'][0]['scores']['PQ']=10;p.write_text(json.dumps(d))
            with self.assertRaises(PermissionError):bridge.read_cloud_music_reference(root,binding=self.binding(root))
    def test_modified_policy_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=self.fixture(root)
            with (directory/'policy-v2.json').open('a') as stream:stream.write(' ')
            with self.assertRaises(PermissionError):bridge.read_cloud_music_reference(root,binding=self.binding(root))
    def test_missing_reference_audio_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            with self.assertRaises(FileNotFoundError):bridge.read_cloud_music_reference(root,binding=self.binding(root))
    def test_native_minima_preserved_and_historical_floor_never_reduced(self):
        reference={'windows':[{'scores':{'CE':3,'PQ':4}},{'scores':{'CE':6,'PQ':7}}]}
        self.assertEqual(bridge.reference_floors(reference),{'CE':3,'PQ':4})
        reference['cloud_independent_reference']={'version':'cloud-owned-v2-native-minima-v1','observation_sha256':bridge.OBSERVATION_SHA}
        self.assertEqual(bridge.reference_floors(reference),bridge.HISTORICAL_FLOORS)
        reference['windows'][0]['scores']={'CE':7,'PQ':8}
        self.assertEqual(bridge.reference_floors(reference),{'CE':6,'PQ':7.4419801340579985})
    def test_saved_target_complete_population_against_native_successor_floors(self):
        reference=bridge.read_cloud_music_reference(ROOT,binding=self.binding());floors=bridge.reference_floors(reference)
        source=Path('/workspace/scratch/19a457603cc9/production-review/preserved-music-observation.json')
        self.assertEqual(bridge.digest(source),'sha256:3ae00830fa072d30cfffa26ab5254bf83c724786e9cd7396e760f874039de5d3')
        target=json.loads(source.read_text());self.assertEqual(len(target['windows']),1074)
        self.assertTrue(all(r['scores'][k]>=floors[k] for r in target['windows'] for k in floors))
        negative=copy.deepcopy(target);negative['windows'][0]['scores']['PQ']=floors['PQ']-0.000001
        self.assertFalse(all(r['scores'][k]>=floors[k] for r in negative['windows'] for k in floors))
    def test_historical_anchor_constant_unchanged(self):
        self.assertEqual(qa.REST_MUSIC_REFERENCE_SHA256,'sha256:5fe54921933654a9dc264846a949868516438a66c278e77f0abd56ef5859d133')

if __name__=='__main__':unittest.main(verbosity=2)
