"""Actual native entry points, exact preserved evidence, isolated test capsules."""
import ast,hashlib,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parent/'heroverse-native-gop300'
sys.path.insert(0,str(ROOT))
from hero_engine.standard_qualification_phase5 import read_audio_static_codec_controls,verify_audio_static_execution

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def replace_tree(value,old,new):
    if isinstance(value,dict):return {k:replace_tree(v,old,new) for k,v in value.items()}
    if isinstance(value,list):return [replace_tree(v,old,new) for v in value]
    return value.replace(old,new) if isinstance(value,str) else value

class NativeTransportBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'output/runtime/gestor-central/maintenance-runs')
        self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.package=ROOT/'output/production'/('test-'+self.directory.name)
        self.addCleanup(shutil.rmtree,self.package)
        original=ROOT/'output/production/current-gop300-transport-v1'
        shutil.copytree(original,self.package,ignore=shutil.ignore_patterns('*.mp4'))
        for p in self.package.rglob('*.json'):
            p.write_text(json.dumps(replace_tree(read(p),str(original),str(self.package)),indent=2)+'\n')
        rights=self.package/'source/rights-evidence.json';v=read(rights)
        v['composition_manifest']['sha256']='sha256:'+sha(self.package/'source/source-manifest.json')
        rights.write_text(json.dumps(v,indent=2)+'\n')
        self.media=self.package/'HeroVerse_Rest_Corrected_3h_Metricool.mp4'
        os.link(original/self.media.name,self.media)
        old=ROOT/'output/runtime/gestor-central/maintenance-runs/gop300-native-v1'
        shutil.copytree(old/'evidence',self.directory/'evidence')
        self.descriptor=read(old/'native-binding.json');self.descriptor['package']=str(self.package.relative_to(ROOT))
        self.seal()
    def seal(self):
        path=self.directory/'native-binding.json';path.write_text(json.dumps(self.descriptor,indent=2)+'\n')
        self.binding={'path':str(path),'sha256':'sha256:'+sha(path)}
    def consume(self,**kwargs):return read_audio_static_codec_controls(ROOT,self.package,binding=self.binding,**kwargs)
    def test_actual_native_reader_and_transport_lineage_adoption_without_effects(self):
        with patch('subprocess.run',side_effect=AssertionError('unexpected media/provider effect')),patch('subprocess.Popen',side_effect=AssertionError('unexpected media/provider effect')):
            controls=self.consume();execution=verify_audio_static_execution(ROOT,self.package,self.media,binding=self.binding)
        self.assertEqual(controls['status'],'AUTHENTICATED_STATIC_CODEC_LIMITS')
        self.assertFalse(controls['quality_authorized']);self.assertFalse(controls['publication_authorized'])
        self.assertFalse(execution['new_render_executed']);self.assertFalse(execution['quality_authorized'])
    def test_changed_current_profile_is_not_admitted(self):
        path=self.package/'take_plan.json';v=read(path);v['render_profile']='arbitrary';path.write_text(json.dumps(v))
        with self.assertRaisesRegex(PermissionError,'PACKAGE_DOMAIN'):self.consume()
    def test_evidence_mutation_is_not_admitted(self):
        with (self.directory/'evidence/transport-verification.json').open('a') as stream:stream.write(' ')
        with self.assertRaisesRegex(PermissionError,'EVIDENCE_transport'):self.consume()
    def test_wrong_master_is_not_admitted(self):
        wrong=self.package/'wrong.mp4';wrong.write_bytes(b'NOT_CANONICAL_MASTER')
        self.descriptor['media']='wrong.mp4';self.seal()
        with self.assertRaisesRegex(PermissionError,'CURRENT_MASTER'):self.consume()
    def test_changed_channel_bible_is_not_admitted(self):
        path=self.package/'channel_style_bible.json';v=read(path);v['channel_id']='wrong-channel';path.write_text(json.dumps(v))
        with self.assertRaisesRegex(PermissionError,'BIBLE'):self.consume()
    def test_absent_music_inputs_cannot_borrow_transport_approval(self):
        with self.assertRaisesRegex(PermissionError,'three exact input bindings'):self.consume(music_bindings={})
    def test_original_legacy_reader_ast_is_preserved_after_new_dispatch(self):
        old=ast.parse((ROOT/'migration-history/gop300-native-v1/standard_qualification_phase5.py').read_text())
        new=ast.parse((ROOT/'hero_engine/standard_qualification_phase5.py').read_text())
        for name in ('read_audio_static_codec_controls','verify_audio_static_execution'):
            before=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
            after=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
            after.body=[n for n in after.body if not (
                isinstance(n,ast.ImportFrom) and n.module=='native_gop300_bridge'
                or isinstance(n,ast.If) and isinstance(n.test,ast.Call) and isinstance(n.test.func,ast.Name) and n.test.func.id=='_gop300_offered')]
            self.assertEqual(ast.dump(before),ast.dump(after))

if __name__=='__main__':unittest.main(verbosity=2)
