import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import video_analysis_card as card
ROOT=Path(__file__).resolve().parents[2]
PATHS={'structure':'migration/structures/guided-prayer-scenic.json',
       'structure_audit':'migration/evidence/vidiq/20261019/structure_audit.json',
       'thumbnails':'migration/evidence/vidiq/20261019/thumbnails.json'}


class Cards(unittest.TestCase):
    def setUp(self):
        self.data={};self.sources={}
        for kind,path in PATHS.items():self.data[kind],self.sources[kind]=card.read_source(ROOT/path)
        self.video='OuqwfEgNavE'
    def build(self,**kwargs):return card.build_card(**self.data,video_id=self.video,sources=self.sources,**kwargs)
    def rows(self,result,section):return {r['field']:r for r in result['sections'][section]}
    def test_real_cohort_preserved_and_thumbnail_sample_separate(self):
        result=card.build_report(**self.data,sources=self.sources)
        self.assertEqual(result['cohort_counts'],{'winner':6,'weak':3})
        self.assertEqual([r['video_id'] for r in result['cards']],[r['video'] for r in self.data['structure']['evidence']])
        self.assertEqual(len(result['thumbnail_reconciliation']['rows']),20)
        self.assertEqual(len(result['cards']),9)
        self.assertEqual(result['thumbnail_reconciliation']['cohort_matched'],6)
    def test_false_zero_and_null_not_conflated(self):
        self.data['structure_audit']['videos'][0]['cuts_per_min']='0'
        result=self.build();visuals=self.rows(result,'visuals')
        self.assertIs(visuals['person_or_figure']['value'],False)
        self.assertEqual(visuals['cuts_per_min']['value'],'0')
        weak=card.build_card(**self.data,video_id='JGj76i7s0XM')
        self.assertIsNone(weak['breakout'])
        self.assertEqual(card.observation('zero',0,'MEASURED','TEST')['value'],0)
    def test_missing_unknown_and_unknown_strings(self):
        self.data['structure_audit']['videos'][0].pop('person_or_figure')
        result=self.build();row=self.rows(result,'visuals')['person_or_figure']
        self.assertIsNone(row['value']);self.assertEqual(row['status'],'UNKNOWN')
        for value in ('UNKNOWN unseen','not visible','',None):
            self.assertIsNone(card.observation('x',value,'MODEL_REPORTED','TEST')['value'])
        self.assertEqual(result['sections']['promise'][0]['status'],'UNKNOWN')
    def test_model_estimate_and_instrument_distinct(self):
        result=self.build();visual=self.rows(result,'visuals')
        self.assertEqual(visual['cuts_per_min']['status'],'ESTIMATED')
        self.assertEqual(visual['cuts_per_min']['value'],'2-3')
        packaging=self.rows(result,'packaging')
        self.assertEqual(packaging['thumbnail.width']['status'],'MEASURED')
        self.assertEqual(packaging['thumbnail.face_realistic']['status'],'MODEL_REPORTED')
    def test_conflict_keeps_both_values_without_pixel_claim(self):
        result=card.build_card(**self.data,video_id='fXhKzleJhxI',sources=self.sources)
        conflict=next(r for r in result['conflicts'] if r['field']=='thumbnail.text_words')
        self.assertEqual(conflict['values'],[15,10])
        rows=[r for r in result['sections']['packaging'] if r['field']=='thumbnail.text_words']
        self.assertEqual(rows[1]['method'],'REPORTED_TEXT_WHITESPACE_COUNT')
        self.assertEqual(rows[1]['coverage']['scope'],'reported_text_only')
    def test_exact_source_bytes_hash_not_reserialization(self):
        raw=b'{ "date" : "2026-10-19", "value": 1 }\n'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input.json';p.write_bytes(raw);value,source=card.read_source(p)
        self.assertEqual(source['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(source['sha256'],hashlib.sha256(card.canonical(value).encode()).hexdigest())
    def test_source_pointer_and_image_hash_are_distinct(self):
        result=self.build();row=self.rows(result,'packaging')['thumbnail.width'];ref=row['evidence'][0]
        self.assertEqual(ref['json_pointer'],'/rows/0/width')
        self.assertEqual(ref['sha256'],self.sources['thumbnails']['sha256'])
        self.assertNotEqual(ref['image_sha256'],ref['sha256'])
        node=self.data['thumbnails']
        for key in ref['json_pointer'].strip('/').split('/'):node=node[int(key)] if isinstance(node,list) else node[key]
        self.assertEqual(node,row['value'])
    def test_determinism_and_no_input_mutation(self):
        before=copy.deepcopy(self.data)
        left=card.canonical(card.build_report(**self.data,sources=self.sources))
        right=card.canonical(card.build_report(**self.data,sources=self.sources))
        self.assertEqual(left,right);self.assertEqual(before,self.data)
    def test_legacy_review_pass_without_audit_and_audit_error(self):
        real=json.loads((ROOT/'migration/production/pilot-012/out/review.json').read_text())
        self.assertNotIn('audit',real)
        for review in ({'status':'PASS'},{'status':'PASS','audit':{'status':'ERROR','error':'failure'}}):
            result=self.build(own_review=review)
            self.assertFalse(result['complete'])
            self.assertTrue(any('MISSING_OR_ERROR' in x for x in result['limitations']))
            self.assertEqual(result['sections']['audio'][0]['status'],'UNKNOWN')
    def test_own_review_identity_must_match(self):
        result=self.build(own_review={'video_id':'wrong','audit':{'audio':'Clear voice'}})
        self.assertEqual(result['sections']['audio'][0]['status'],'UNKNOWN')
        self.assertTrue(any('IDENTITY_MISMATCH' in x for x in result['limitations']))
    def test_requested_window_is_not_verified_coverage(self):
        result=self.build(own_review={'video_id':self.video,'audit':{'first_30s':'Short direct opening','model':'test'}})
        row=self.rows(result,'opening')['first_30s'];self.assertEqual(row['status'],'MODEL_REPORTED')
        self.assertEqual(row['coverage']['end_seconds'],30)
        self.assertFalse(row['coverage']['independently_verified'])
    def test_partial_legacy_window_no_transcript_or_ending_inference(self):
        legacy={'video':{'video_id':self.video,'seconds':100},'windows':[{'window_start_seconds':0,'window_end_seconds':20,
            'audio_received':True,'visual_received':True,'transcript':[{'text':'UNIQUE_FULL_TRANSCRIPT_SECRET_MARKER'}],
            'beats':[{'beat':'hook','content':'Direct invitation','opening_words_verbatim':'UNIQUE_VERBATIM_MARKER'}],
            'picture':{'motion':'UNKNOWN'},'sound':{'voice':'Warm'},'model':'test'}]}
        self.data['structure_audit']={'videos':[]}
        result=self.build(legacy_structure=legacy);encoded=card.canonical(result)
        self.assertNotIn('UNIQUE_',encoded);self.assertNotIn('transcript"',encoded)
        self.assertEqual(result['sections']['ending'][0]['status'],'UNKNOWN')
        self.assertIsNone(self.rows(result,'visuals')['picture.motion']['value'])
        self.assertEqual(self.rows(result,'audio')['sound.voice']['coverage']['end_seconds'],20)
    def test_unreceived_media_cannot_become_observation(self):
        legacy={'video':{'video_id':self.video},'windows':[{'visual_received':False,'audio_received':False,
             'picture':{'motion':'pan'},'sound':{'voice':'warm'},'beats':[{'content':'unreceived'}]}]}
        result=self.build(legacy_structure=legacy)
        self.assertIsNone(self.rows(result,'audio')['sound']['value'])
        self.assertIsNone(self.rows(result,'script_beats')['beats']['value'])
    def test_unavailable_thumbnail_does_not_invent_measurement(self):
        self.data['thumbnails']['rows'][0]['status']='unavailable'
        result=self.build();self.assertEqual(result['sections']['packaging'][0]['status'],'UNKNOWN')
    def test_duplicate_or_missing_identity_rejected(self):
        with self.assertRaises(ValueError):card.build_card(**self.data,video_id='absent')
        self.data['structure']['evidence'].append(self.data['structure']['evidence'][0])
        with self.assertRaises(ValueError):card.build_report(**self.data)
    def test_conflicting_audits_coexist(self):
        other=copy.deepcopy(self.data['structure_audit']['videos'][0])
        other['person_or_figure']=True
        self.data['structure_audit']['videos'].append(other)
        result=self.build()
        conflict=next(c for c in result['conflicts'] if c['field']=='person_or_figure')
        self.assertEqual(conflict['values'],[False,True])
        self.assertNotEqual(conflict['evidence'][0],conflict['evidence'][1])
    def test_disjoint_legacy_windows_are_not_conflicts(self):
        windows=[]
        for start,end,sound in ((0,10,'piano'),(10,20,'strings')):
            windows.append({'window_start_seconds':start,'window_end_seconds':end,'audio_received':True,
                'sound':{'music':sound},'beats':[{'beat':sound,'content':sound}]})
        result=self.build(legacy_structure={'video':{'video_id':self.video},'windows':windows})
        self.assertFalse(any(c['field'] in ('sound.music','beats') for c in result['conflicts']))

    def test_same_legacy_window_disagreement_retained(self):
        windows=[{'window_start_seconds':0,'window_end_seconds':10,'audio_received':True,
                  'sound':{'music':sound}} for sound in ('piano','strings')]
        result=self.build(legacy_structure={'video':{'video_id':self.video},'windows':windows})
        conflict=next(c for c in result['conflicts'] if c['field']=='sound.music')
        self.assertEqual(conflict['values'],['piano','strings'])

    def test_partially_overlapping_windows_not_automatically_conflict(self):
        rows=[card.observation('sound.music',value,'MODEL_REPORTED','test',span=card.coverage(start,end,'source_declared_window'))
              for start,end,value in ((0,15,'piano'),(10,20,'strings'))]
        self.assertEqual(card.conflicts(rows),[])

    def test_cli_refuses_source_overwrite(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for kind,data in self.data.items():
                p=Path(tmp)/(kind+'.json');p.write_text(card.canonical(data));paths.append(p)
            before=paths[0].read_bytes()
            result=subprocess.run([sys.executable,'-I','-B',card.__file__,*[str(p) for p in paths],str(paths[0])],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('SOURCE_OVERWRITE_FORBIDDEN',result.stderr)
            self.assertEqual(paths[0].read_bytes(),before)

    def test_no_operational_fields_or_network_imports(self):
        result=self.build();self.assertTrue(result['report_only']);self.assertNotIn('publish',result);self.assertNotIn('approval',result)
        tree=ast.parse(Path(card.__file__).read_text())
        imports={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import)}
        imports|={n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertLessEqual(imports,{'argparse','copy','hashlib','json','pathlib'})


if __name__=='__main__':unittest.main()
