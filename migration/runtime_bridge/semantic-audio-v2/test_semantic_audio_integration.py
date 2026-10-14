"""Synthetic wiring tests; gold schema reused, no market/quality/rights approval."""
import copy,hashlib,json,os,shutil,sys,tempfile,types,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(os.environ['HEROVERSE_SEMANTIC_ROOT']).resolve()
sys.path.insert(0,str(ROOT))
# Pure-contract scope: do not initialize native ASR/download packages.
namespace=types.ModuleType('hero_engine.observatory');namespace.__path__=[str(ROOT/'hero_engine/observatory')]
sys.modules['hero_engine.observatory']=namespace
if 'yt_dlp' not in sys.modules:
    unavailable=types.ModuleType('yt_dlp')
    def forbidden(*a,**k):raise AssertionError('Network/media acquisition forbidden in wiring tests')
    unavailable.YoutubeDL=forbidden
    unavailable.version=types.SimpleNamespace(__version__="fixture-no-network")
    sys.modules['yt_dlp']=unavailable
from hero_engine import phase6_audio_production as production
from hero_engine.creative_direction import build_christian_rest_music_recipe,read_christian_rest_music_inputs,rest_delivery_format
from tests import test_observatory_format_cohorts as cohort

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')
def pin(root,path):return {'path':path.relative_to(root).as_posix(),'sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}

class Integration(unittest.TestCase):
    def setUp(self):
        class Frozen(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.fromisoformat(cohort.CUTOFF)
        clock=patch.object(production._semantic_module(),'datetime',Frozen)
        clock.start();self.addCleanup(clock.stop)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name).resolve()
        self.owner=types.SimpleNamespace(root=self.root,relative=Path('output/production/fixture'))
        self.owner.package=self.root/self.owner.relative
        model=self.root/'output/modeling/phase4/channel-model-v1/channel_model.json'
        bible=self.owner.package/'channel_style_bible.json'
        write(model,{'model_id':'fixture-model'})
        write(bible,{'channel_id':'heroverse74','channel_dna_version':'fixture-model'})
        self.owner.recipe=build_christian_rest_music_recipe(duration_ms=180000,
            channel_model_hash='sha256:'+hashlib.sha256(model.read_bytes()).hexdigest(),
            style_bible_hash='sha256:'+hashlib.sha256(bible.read_bytes()).hexdigest(),
            recipe_version='heroverse-christian-rest-editorial-v4')
        self.owner.recipe_path=self.owner.package/'music_recipe.json' 
        for name in ('config/current_audio_research.json','schemas/video_mining.schema.json'):
            dest=self.root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        with zipfile.ZipFile(os.environ['HEROVERSE_GOLD_ARCHIVE']) as z:
            name=next(n for n in z.namelist() if 'hkf6nDyUfAM' in n and n.endswith('video_mining.json'))
            gold=json.loads(z.read(name))
        subtopics=gold['narrative_segments'][0]['information'][:2]
        self.rows=[]; records=[]; refs=[]
        ids=['UCTdc_zl40D9wa0_LH9yaGZA','UCsDKqJJISkMyvjFowNT_Sdg','UC0JWi59lgJMCapfqr6_P15g']
        for c,cid in enumerate(ids):
            self.rows.append(cohort._channel(cid,cid,'FORMAT_REFERENCE'))
            for n in range(4):
                video=f'fixture{c}{n:03}'
                row=cohort._video(cid,cid,'FORMAT_REFERENCE',video,view_count=[1000,100,90,10][n])
                row['payload']['duration_seconds']=gold['source']['duration_ms']/1000
                row['payload']['title']='Not prayer, gratitude or a preselected family'
                self.rows.append(row);sid=row['snapshot_id']
                mining=copy.deepcopy(gold);mining['source'].update(video_id=video,channel_id=cid,
                    published_at=datetime.fromtimestamp(row['payload']['timestamp'],timezone.utc).isoformat())
                artifact=self.root/f'output/market/test/{video}/observations.txt'
                artifact.parent.mkdir(parents=True,exist_ok=True)
                artifact.write_text('Synthetic transcript fixture: distinct evidence only.',encoding='utf-8')
                artifact_binding=pin(self.root,artifact)
                mining['transcript']['reviewed_artifact']='fixture-transcript'
                def fixture_artifacts(value):
                    if isinstance(value,dict):
                        if 'evidence_id' in value:value['artifact']='fixture-transcript'
                        for child in value.values():fixture_artifacts(child)
                    elif isinstance(value,list):
                        for child in value:fixture_artifacts(child)
                fixture_artifacts(mining)
                path=artifact.parent/'mining.json';write(path,mining)
                first=mining['narrative_segments'][0]
                refs.append(sid+':'+first['segment_id'])
                records.append({'snapshot_id':sid,'mining_binding':pin(self.root,path),
                    'artifact_bindings':{'fixture-transcript':artifact_binding},'transcript_binding':artifact_binding,
                    'subtopic_evidence':{s:mining['content_analysis']['topic']['evidence_refs'] for s in subtopics},
                    'segment_ids':[first['segment_id']]})
        self.source=self.root/'output/market/test/snapshots.json'
        write(self.source,{'schema_version':'1.0.0','operation_id':cohort.OPERATION,'captured_at':cohort.CUTOFF,'snapshots':self.rows})
        self.env={'version':'heroverse-semantic-handoff-v1','channel_id':production.CHANNEL_ID,
            'snapshot_binding':pin(self.root,self.source),'topic':'COURAGE_AFTER_A_SETBACK','subtopics':subtopics,'records':records,
            'editorial_draft':{'authorship':'ORIGINAL_HEROVERSE','language':'en-US','speech_placement':'ONCE_AT_START',
                'title':'A Small Step After Disappointment','angle':'Respond with an honest small step after disappointment',
                'sections':[{'role':role,'text':t,'original_contribution':'An original everyday example and perspective',
                    'retention_function':'Resolve the opening question without guaranteeing an outcome',
                    'mechanism_refs':[refs[i]],'subtopics':subtopics} for i,(role,t) in enumerate([
                        ('STAKE','A disappointment can make the next step feel much larger than it is.'),
                        ('EXAMPLE','You can choose a thoughtful conversation tomorrow without deciding the whole future tonight.'),
                        ('RESOLUTION','Let this music leave space to consider one response that fits your actual responsibilities.')])]}}
        self.handoff=self.source.parent/'handoff.json'
        self.baseline={'topic':'OLD_THEME','editorial_angle':'Old angle'}
    def binding(self):write(self.handoff,self.env);return pin(self.root,self.handoff)
    def build(self):return production.build_current_audio_research(self.root,self.source,baseline=self.baseline,semantic_binding=self.binding())
    def test_new_theme_and_original_sections_flow_to_native_recipe(self):
        m=self.build();self.assertEqual(m['topic'],'COURAGE_AFTER_A_SETBACK')
        self.assertEqual(len(m['supporting_channels']),3)
        modelpath=self.source.parent/'model.json';write(modelpath,m);binding=pin(self.root,modelpath)
        self.assertEqual(production.read_current_audio_research(self.root,binding),m)
        recipe=build_christian_rest_music_recipe(duration_ms=180000,
            channel_model_hash=self.owner.recipe['channel_model_hash'],style_bible_hash=self.owner.recipe['style_bible_hash'],
            recipe_version='heroverse-christian-rest-editorial-v6',research={'binding':binding,'model':m})
        self.assertIn('disappointment',recipe['editorial']['full_text']);self.assertEqual(len(recipe['editorial']['sections']),3)
        self.assertEqual(rest_delivery_format(recipe)['format_pack_id'],'fp-christian-reflection-rest-static')
        write(self.owner.recipe_path,recipe);rp={'path':str(self.owner.recipe_path),'sha256':'sha256:'+hashlib.sha256(self.owner.recipe_path.read_bytes()).hexdigest()}
        protocol=self.owner.package/'protocol.json';write(protocol,{'status':'READY_TO_PREREGISTER','treatment':{'variable':'TOPIC_ANGLE'}})
        write(self.source.parent/'preregistration.json',{'research':binding,'recipe':rp,'variable':'TOPIC_ANGLE',
            'protocol':protocol.relative_to(self.root).as_posix(),'protocol_hash':pin(self.root,protocol)['sha256'],
            'created_at':datetime.now(timezone.utc).isoformat()})
        actual=read_christian_rest_music_inputs(self.root,package_relative=self.owner.relative,recipe_binding=rp)
        self.assertEqual(actual['recipe']['editorial']['sections'],self.env['editorial_draft']['sections'])
    def test_missing_semantics_blocks_before_manager_queue_or_collection(self):
        with patch('hero_engine.phase6_intelligence.materialize_current',side_effect=AssertionError('effect')):
            result=production.run_current_audio_research_production(self.root,package_relative=self.owner.relative,
                current_bindings={},expected_release_hash='fixture',snapshot_reference='fixture')
        self.assertEqual(result['status'],'WAITING_FOR_REVIEWED_SEMANTIC_HANDOFF')
    def test_no_negative_examples_is_rejected(self):
        self.env['records']=self.env['records'][::4]
        with self.assertRaisesRegex(PermissionError,'COUNTEREVIDENCE'):self.build()
    def test_missing_subtopic_application_rejected(self):
        for s in self.env['editorial_draft']['sections']:s['subtopics']=self.env['subtopics'][:1]
        with self.assertRaisesRegex(PermissionError,'NOT_APPLIED'):self.build()
    def test_unknown_narrative_reference_rejected(self):
        self.env['editorial_draft']['sections'][0]['mechanism_refs']=['invented']
        with self.assertRaisesRegex(PermissionError,'LINEAGE'):self.build()
    def test_artifact_tampering_rejected(self):
        path=self.root/self.env['records'][0]['transcript_binding']['path'];path.write_text('tampered')
        with self.assertRaisesRegex(PermissionError,'HASH_CHANGED'):self.build()
    def test_unreviewed_mining_rejected(self):
        r=self.env['records'][0];p=self.root/r['mining_binding']['path'];m=json.loads(p.read_bytes())
        m['quality']['manual_review_status']='NOT_REVIEWED';write(p,m);r['mining_binding']=pin(self.root,p)
        with self.assertRaisesRegex(PermissionError,'REVIEWED'):self.build()
    def test_copied_source_text_is_rejected(self):
        t='This is a deliberately copied sequence of more than twelve words from the source transcript for the test'
        for r in self.env['records']:
            p=self.root/r['transcript_binding']['path'];p.write_text(t);b=pin(self.root,p)
            r['transcript_binding']=b;r['artifact_bindings']['fixture-transcript']=b
        self.env['editorial_draft']['sections'][0]['text']=t
        with self.assertRaisesRegex(PermissionError,'VERBATIM'):self.build()
    def test_current_manager_consumes_pointer_without_recollecting(self):
        binding=self.binding()
        pointer=self.root/'output/market/current-audio/semantic-handoff.binding.json';write(pointer,binding)
        with patch.object(production,'_run_current_audio_research_production_v1',return_value={'status':'ADMITTED_FIXTURE'}) as native_lane:
            result=production.run_current_audio_research_production(self.root,package_relative=self.owner.relative,
                current_bindings={},expected_release_hash='fixture',snapshot_reference='fixture')
        self.assertEqual(result['status'],'ADMITTED_FIXTURE')
        self.assertEqual(native_lane.call_args.kwargs['semantic_binding'],binding)
        self.assertEqual(production._semantic_module().handoff_source(self.root,binding),self.source)
    def test_stale_observations_rejected(self):
        bundle=json.loads(self.source.read_bytes());bundle['captured_at']='2026-08-01T12:00:00+00:00';write(self.source,bundle)
        self.env['snapshot_binding']=pin(self.root,self.source)
        with self.assertRaisesRegex(PermissionError,'FRESH'):self.build()
    def test_invalid_semantic_pointer_blocks_before_native_lane(self):
        binding=self.binding();self.handoff.write_bytes(b'altered')
        with patch.object(production,'_run_current_audio_research_production_v1',side_effect=AssertionError('effect')):
            with self.assertRaisesRegex(PermissionError,'HASH_CHANGED'):
                production.run_current_audio_research_production(self.root,package_relative=self.owner.relative,
                    current_bindings={},expected_release_hash='fixture',snapshot_reference='fixture',semantic_binding=binding)
    def test_legacy_historical_recipe_reproduces(self):
        verify=__import__('hero_engine.creative_direction',fromlist=['verify_christian_rest_music_recipe'])
        raw=json.dumps(self.owner.recipe,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        verify.verify_christian_rest_music_recipe(self.owner.recipe,expected_hash='sha256:'+hashlib.sha256(raw).hexdigest())
if __name__=='__main__':unittest.main()
