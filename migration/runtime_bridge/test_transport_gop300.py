"""Tests use copies of the completed observations; no encode/decode/provider."""
import json, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import calibrate_transport_gop300 as c
from verify_transport_gop300 import verify

BASE=Path(__file__).resolve().parent
NATIVE=BASE/'composition-shadow'
sys.path.insert(0,str(NATIVE))
POLICY='ddbf013c9bc5a9cc11797793a90add7e7a738bdbff1f3964fdfd02964422d377'
PRODUCER=BASE/'calibrate_transport_gop300_recovery_v3.py'

class TransportEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'controls'
        shutil.copytree(BASE/'controls-v3',self.root)
        self.binding=c.sha(self.root/'bindings.json')
    def consume(self):return verify(self.root,self.binding,NATIVE,POLICY,PRODUCER)
    def mutate(self,path,change,reseal=False):
        p=self.root/path;data=c.read(p);change(data);p.write_text(json.dumps(data,indent=2)+'\n')
        if reseal:
            anchor=c.read(self.root/'bindings.json')
            for item in anchor['artifacts']:
                if item['path']==path:item.update(sha256=c.sha(p),bytes=p.stat().st_size)
            (self.root/'bindings.json').write_text(json.dumps(anchor,indent=2)+'\n')
            self.binding=c.sha(self.root/'bindings.json')
    def test_real_eight_control_reopen_has_no_effects_and_no_release_authority(self):
        with patch('subprocess.run',side_effect=AssertionError('unexpected subprocess')),patch('subprocess.Popen',side_effect=AssertionError('unexpected subprocess')):
            result=self.consume()
        self.assertTrue(result['separation_passed']);self.assertFalse(result['quality_authorized'])
        self.assertFalse(result['publication_authorized']);self.assertEqual(result['subprocess_calls'],0)
    def test_control_binary_tamper_rejected(self):
        with (self.root/'control-0/control.mp4').open('ab') as stream:stream.write(b'altered')
        with self.assertRaises(PermissionError):self.consume()
    def test_resealed_changed_encoder_rejected(self):
        def change(d):d['argv'][d['argv'].index('-g')+1]='60'
        self.mutate('control-0/command.json',change,True)
        with self.assertRaisesRegex(PermissionError,'ENCODER_DOMAIN'):self.consume()
    def test_resealed_changed_font_geometry_rejected(self):
        self.mutate('control-0/command.json',lambda d:d['layout']['texts'][0].update(font_size=54),True)
        with self.assertRaisesRegex(PermissionError,'SOURCE_DOMAIN'):self.consume()
    def test_resealed_forged_limit_rejected_by_native_numeric_recomputation(self):
        self.mutate('result.json',lambda d:d['calibration']['text_error'].update(maximum_error=1),True)
        with self.assertRaisesRegex(PermissionError,'CALIBRATION_CHANGED'):self.consume()
    def test_resealed_incomplete_population_rejected(self):
        self.mutate('result.json',lambda d:d['rows'].pop(),True)
        with self.assertRaisesRegex(PermissionError,'CONTROL_COUNT'):self.consume()
    def test_resealed_training_holdout_overlap_rejected(self):
        self.mutate('result.json',lambda d:d['rows'][6].update(encoded_sha256=d['rows'][3]['encoded_sha256']),True)
        with self.assertRaisesRegex(PermissionError,'CONTROL_SOURCE_OVERLAP'):self.consume()

if __name__=='__main__':unittest.main(verbosity=2)
