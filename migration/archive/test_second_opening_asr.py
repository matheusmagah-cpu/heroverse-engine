import hashlib
import io
import json
from pathlib import Path
import stat
import types
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile
import second_opening_asr as a

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, names=None):
        p = self.root/'model.zip'
        data = {name: ('fixture '+name).encode() for name in a.FILES}
        with zipfile.ZipFile(p, 'w') as z:
            for name in names or ['snapshot/'+n for n in data]:
                z.writestr(name, data.get(Path(name).name,b'bad'))
        return p, {name: hashlib.sha256(raw).hexdigest() for name,raw in data.items()}

    def test_gate_permits_exact_scope(self):
        a.gate(dict(GITHUB_REPOSITORY=a.REPO,GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_REF='refs/heads/main',GITHUB_RUN_NUMBER='1',GITHUB_RUN_ATTEMPT='1'))

    def test_gate_blocks_repeats_wrong_repo_event_ref(self):
        env=dict(GITHUB_REPOSITORY=a.REPO,GITHUB_EVENT_NAME='workflow_dispatch',
                 GITHUB_REF='refs/heads/main',GITHUB_RUN_NUMBER='1',GITHUB_RUN_ATTEMPT='1')
        for key,value in [('GITHUB_REPOSITORY','other/repo'),('GITHUB_EVENT_NAME','push'),
                          ('GITHUB_REF','refs/heads/other'),('GITHUB_RUN_NUMBER','2'),('GITHUB_RUN_ATTEMPT','2')]:
            with self.subTest(key=key), self.assertRaises(a.ScopeError):
                a.gate(dict(env, **{key:value}))

    def test_release_is_exact_uploaded_published(self):
        release=dict(id=a.RELEASE,draft=False,assets=[dict(id=x['id'],size=x['bytes'],
                         digest='sha256:'+x['sha256'],state='uploaded') for x in (a.MEDIA,a.MODEL)])
        a.check_release(release)
        for bad in [dict(release,draft=True),dict(release,id=42),dict(release,assets=[])]:
            with self.assertRaises(a.ScopeError): a.check_release(bad)
        release['assets'][0]['digest']='sha256:changed'
        with self.assertRaises(a.ScopeError): a.check_release(release)

    def test_exact_model_files_extract(self):
        p,h = self.archive(); dest=a.extract_model(p,self.root/'output',h)
        self.assertEqual(set(x.name for x in dest.iterdir()),set(a.FILES))

    def test_unsafe_paths_block(self):
        for path in ['../evil','/absolute','C:/drive','snapshot\\bad']:
            p,h=self.archive(['snapshot/'+n for n in a.FILES]+[path])
            with self.subTest(path=path),self.assertRaises(a.ScopeError):
                a.extract_model(p,self.root/('out'+str(len(path))),h)

    def test_duplicate_model_basename_block(self):
        p,h=self.archive(['snapshot/'+n for n in a.FILES]+['other/model.bin'])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_missing_model_file_block(self):
        p,h=self.archive(['snapshot/model.bin'])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_split_directory_block(self):
        p,h=self.archive(['other/'+n if n=='model.bin' else 'snapshot/'+n for n in a.FILES])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_hash_mismatch_block(self):
        p,h=self.archive(); h['model.bin']='0'*64
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_symlink_block(self):
        p,h=self.archive()
        with zipfile.ZipFile(p,'a') as z:
            i=zipfile.ZipInfo('link'); i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(i,'outside')
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_extract_cap_block(self):
        p,h=self.archive()
        with patch.object(a,'EXTRACT_CAP',1), self.assertRaises(a.ScopeError):
            a.extract_model(p,self.root/'out',h)

    def test_size_and_digest_checks(self):
        p=self.root/'data';p.write_bytes(b'x')
        a.verify(p,dict(bytes=1,sha256=hashlib.sha256(b'x').hexdigest()))
        for record in [dict(bytes=2,sha256='0'*64),dict(bytes=1,sha256='0'*64)]:
            with self.assertRaises(a.ScopeError):a.verify(p,record)

    def test_actual_guard_silent_and_nonzero(self):
        for raw,silent in [(b'\0'*80,True),(b'\x01\0'+b'\0'*78,False)]:
            p=self.root/'a.wav'
            with wave.open(str(p),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(raw)
            result,h=a.pcm_guard(p)
            self.assertEqual(result['digital_silence'],silent)
            self.assertEqual(result['allow_model_inference'],not silent)
            self.assertFalse(result['perceptual_quality_approved']);self.assertEqual(len(h),64)

    def test_actual_guard_invalid_pcm(self):
        p=self.root/'bad.wav';p.write_bytes(b'not audio')
        result,_=a.pcm_guard(p)
        self.assertEqual(result['status'],'INVALID_OR_UNSUPPORTED_PCM')
        self.assertFalse(result['allow_model_inference'])

    def test_text_receipt_cap(self):
        with patch.object(a,'OUTPUT_CAP',8),self.assertRaises(a.ScopeError):
            a.write_receipt(self.root/'r.json',{'text':'too long'})

    def test_download_failure_has_no_retry(self):
        with patch.object(a.subprocess,'run') as run:
            run.return_value.returncode=1
            with self.assertRaises(a.ScopeError):a.download_asset(a.MEDIA,self.root/'media')
            self.assertEqual(run.call_count,1)
            self.assertIn('releases/assets/645199434',run.call_args.args[0][2])
            self.assertEqual(run.call_args.kwargs['timeout'],150)

    def test_transcribe_uses_only_explicit_local_model_and_empty_is_not_approval(self):
        fake_np = types.SimpleNamespace(frombuffer=lambda *a,**kw:[0.1,0.2],
                                      isfinite=lambda x:types.SimpleNamespace(all=lambda:True))
        info=types.SimpleNamespace(duration=40.0312,duration_after_vad=0)
        from unittest.mock import Mock
        ctor=Mock();ctor.return_value.transcribe.return_value=(iter([]),info)
        fake_fw=types.SimpleNamespace(WhisperModel=ctor)
        with patch.dict('sys.modules',numpy=fake_np,faster_whisper=fake_fw):
            rows,actual=a.transcribe(self.root/'model',b'fixture')
        self.assertEqual(rows,[]);self.assertIs(actual,info)
        ctor.assert_called_once_with(str(self.root/'model'),device='cpu',compute_type='int8',
                                     cpu_threads=1,num_workers=1,local_files_only=True)
        self.assertEqual(ctor.return_value.transcribe.call_args.kwargs,
                         dict(language='en',beam_size=5,vad_filter=True,
                              word_timestamps=True,condition_on_previous_text=False))

    def test_runtime_termination_is_exception_for_receipt(self):
        with self.assertRaises(TimeoutError):a.terminate(None,None)

    def test_workflow_scope_and_no_media_upload(self):
        s=(Path(__file__).parents[1]/'.github/workflows/second-opening-asr.yml').read_text()
        self.assertIn('contents: read',s);self.assertNotIn('contents: write',s)
        self.assertIn('timeout-minutes: 10',s);self.assertNotIn('schedule:',s)
        self.assertIn('path: second-opening-asr-receipt.json',s)
        self.assertNotIn('HERO_RAPIDAPI_KEY',s)

if __name__=='__main__':unittest.main()
