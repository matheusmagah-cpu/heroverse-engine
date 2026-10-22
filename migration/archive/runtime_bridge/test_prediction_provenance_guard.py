import copy, importlib.util, sys, tempfile, unittest, os, zipfile, hashlib
from pathlib import Path
from prediction_provenance_guard import require_prediction_basis
HERE=Path(__file__).resolve().parent
def source():
    return {'channel_id':'UCuMF6pJQkyMzaVoAxFL86yA','video_id':'iK_5edYQtx8',
            'snapshot_id':'SYNTHETIC_TEST_ONLY','captured_at':'2026-10-14T08:00:00Z',
            'content_format':'LONG','quality_profile':'STANDARD',
            'format_pack_id':'fp-broll-cinematic-narration','format_pack_version':'1.1.0'}
class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from apply_prediction_provenance_overlay import apply
        archive=Path(os.environ.get('HEROVERSE_SOURCE_ARCHIVE',
                     str(HERE.parents[1]/'HeroVerse_Linux_Source_Ready_20261013_v2.zip')))
        assert archive.is_file(), 'Immutable source archive required; set HEROVERSE_SOURCE_ARCHIVE'
        with archive.open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest() == 'fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'
        cls.temporary=tempfile.TemporaryDirectory();base=Path(cls.temporary.name)
        (base/'source/hero_engine').mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            for name in ['phase6_intelligence.py','__init__.py']:
                (base/'source/hero_engine'/name).write_bytes(z.read('project/hero_engine/'+name))
        apply(base/'source',base/'shadow',HERE/'prediction_provenance_guard.py')
        sys.path.insert(0,str(base/'shadow'))
        from hero_engine.phase6_intelligence import build_prediction
        cls.native_predict=staticmethod(build_prediction)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()
    def test_naked_numbers_do_not_prove_calibration(self):
        with self.assertRaisesRegex(PermissionError,'CALIBRATION_REQUIRED'):
            require_prediction_basis(source(),[10,100,1000])
    def test_nan_and_infinity_do_not_enter_forecast(self):
        for value in [float('nan'),float('inf'),True,'100']:
            with self.subTest(value=value), self.assertRaises(PermissionError):
                require_prediction_basis(source(),[value,100,1000])
    def test_no_cross_format_or_missing_cohort(self):
        for value in ['fp-christian-reflection-rest-static',None]:
            x=source();x['format_pack_id']=value
            with self.assertRaisesRegex(PermissionError,'COHORT_PROVENANCE'):
                require_prediction_basis(x,None)
    def test_no_forecast_is_not_a_zero_view_prediction(self):
        self.assertFalse(require_prediction_basis(source(),[])['publication_authorized'])
    def test_native_shadow_blocks_previously_misleading_label(self):
        with self.assertRaisesRegex(PermissionError,'CALIBRATION_REQUIRED'):
            self.native_predict(source(),comparable_outcomes=[10,100,1000],created_at='2026-10-14T08:01:00Z')
        result=self.native_predict(source(),created_at='2026-10-14T08:01:00Z')
        self.assertIsNone(result['forecast'])
        self.assertEqual('WITHHELD_INSUFFICIENT_CALIBRATION',result['status'])
    def test_changed_frozen_source_rejected(self):
        from apply_prediction_provenance_overlay import apply, MODULE
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary);(p/'source/hero_engine').mkdir(parents=True)
            (p/'source'/MODULE).write_text('changed')
            with self.assertRaisesRegex(PermissionError,'SOURCE_IDENTITY_CHANGED'):
                apply(p/'source',p/'shadow',HERE/'prediction_provenance_guard.py')
if __name__=='__main__':unittest.main()
