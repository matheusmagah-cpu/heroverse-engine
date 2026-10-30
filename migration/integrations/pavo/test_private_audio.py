#!/usr/bin/env python3
"""Private-input bridge: exact bytes, bounded authority and no ambiguous replay."""
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent))
import private_audio as bridge


def wav(seconds=10):
    b = io.BytesIO()
    with wave.open(b, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000)
        f.writeframes(b'\0\0' * 24000 * seconds)
    return b.getvalue()


class PrivateAudio(unittest.TestCase):
    def setUp(self):
        self.audio = wav()
        self.m = {'version': 'pavo-private-audio-v1', 'episode': 'genesis-09-short',
                  'shot': 'k-close', 'prompt': 'Use the exact attached recording.', 'seconds': 10,
                  'audio_sha256': hashlib.sha256(self.audio).hexdigest(), 'audio_bytes': len(self.audio),
                  'audio_seconds': 10, 'speech_seconds': 9.745375,
                  'reference': bridge.REFERENCE, 'reference_sha256': bridge.REFERENCE_SHA,
                  'sound': False, 'aspect_ratio': '9:16', 'production_approved': False}

    def hook(self):
        return {'version': 'pavo-private-hook-v1', 'episode': 'genesis-09-short', 'shot': 's-voice',
                'prompt': 'Animate the approved first frame. Both voices remain offscreen.', 'seconds': 10,
                'first_frame': 'migration/production/bible/stills/genesis-09-s-voice.jpg',
                'first_frame_sha256': '8c3ef26c79c19d7b7d0acb2b825809fab104790d49dfa452e597cbf5b6711e19',
                'sound': False, 'aspect_ratio': '9:16', 'production_approved': False}

    def test_hook_accepts_only_approved_exact_first_frame_without_audio(self):
        m = self.hook()
        try:
            accepted = bridge.validate(m)
        except bridge.Blocked as exc:
            self.fail('approved silent hook refused: ' + str(exc))
        self.assertEqual(accepted['shot'], 's-voice')
        for change in ({'shot': 'k-close'}, {'seconds': 9}, {'seconds': True}, {'sound': True},
                       {'first_frame': bridge.REFERENCE}, {'first_frame_sha256': '0'*64},
                       {'audio_sha256': '0'*64}, {'nonce': 'another-generation'}, {'references': [bridge.REFERENCE]}):
            with self.subTest(change=change), self.assertRaises(bridge.Blocked):
                bridge.validate({**m, **change})
        record = bridge.ROOT/'migration/production/bible/stills/genesis-09-s-voice.json'
        original = Path.read_text
        for change in ({'status': 'DRAFT'}, {'approved': {'score': 9.4}}, {'sha256': '0'*64}):
            def changed(p, *a, **kw):
                raw = original(p, *a, **kw)
                return json.dumps({**json.loads(raw), **change}) if p == record else raw
            with self.subTest(record=change), patch.object(Path, 'read_text', changed), self.assertRaises(bridge.Blocked):
                bridge.validate(m)

    def test_hook_cannot_replay_by_changing_prompt_or_retry_input(self):
        m = self.hook()
        r = bridge.public_record(bridge.initial_record(m, '1234567890'))
        for state in ('CLAIMED', 'SUBMITTING', 'UNKNOWN', 'COMPLETE', 'FAILED'):
            with self.subTest(state=state), self.assertRaises(bridge.Blocked):
                bridge.require_new([{**r, 'state': state}], '0'*64, manifest=m)
        with self.assertRaises(bridge.Blocked):
            bridge.require_new([], bridge.digest(m), retry_run='1234567890', manifest=m)

    def test_hook_cli_claim_refuses_changed_digest_for_existing_slot(self):
        m = self.hook()
        old = bridge.public_record(bridge.initial_record({**m, 'prompt': 'A different earlier hook prompt.'}, '1234567890'))
        old['state'] = 'COMPLETE'
        self.assertNotEqual(old['request_sha256'], bridge.digest(m))
        with tempfile.TemporaryDirectory() as d:
            persisted = []
            history = [old]
            env = {'RUNNER_TEMP': d, 'GITHUB_RUN_ID': '1234567891', 'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
                   'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ATTEMPT': '1'}
            with patch.dict(os.environ, env), patch.object(bridge, 'inputs', return_value=({}, m)), \
                 patch.object(bridge, 'lease'), patch.object(bridge.native_review, 'recipient_check'), \
                 patch.object(bridge, 'history_records', side_effect=lambda: history), \
                 patch.object(bridge, 'persist', side_effect=lambda r, p: persisted.append(copy.deepcopy(r))), \
                 patch.object(bridge, 'PrivateVideoClient', side_effect=AssertionError('provider used during claim')):
                with self.assertRaisesRegex(bridge.Blocked, 'HOOK_EXISTING_CLAIM_RECONCILE'):
                    bridge.cli('claim')
                self.assertEqual(persisted, [])
                history.clear()
                bridge.cli('claim')
                self.assertEqual(len(persisted), 1)
                self.assertEqual((persisted[0]['shot'], persisted[0]['state'], persisted[0]['conversation_id']),
                                 ('s-voice', 'CLAIMED', None))

    def test_hook_cli_uses_frames_only_and_zero_quote_before_any_mutation(self):
        m = self.hook()
        with tempfile.TemporaryDirectory() as d:
            private = Path(d)/'pavo-private-audio'; receipt = private/'receipt.json'
            r = bridge.initial_record(m, '1234567890')
            bridge.atomic(receipt, r)
            events = []
            class Client(bridge.PrivateVideoClient):
                def __init__(self, *args, **kw): super().__init__(token='fake', *args, **kw)
                def _quote(self, seconds, ratio, mode, images, audios=(), sound=False):
                    events.append(('quote', seconds, ratio, mode, images, len(audios), sound))
                    return {'zero_cost_confirmed': allowed[0]}
                def _upload(self, item):
                    self.assert_no_audio(item)
                    events.append(('upload', item['path'])); return {'url': 'https://example.invalid/image.jpg'}
                def assert_no_audio(self, item):
                    assert item['mime'] == 'image/jpeg'
                def _video_json(self, route, body=None, job=None):
                    assert route == 'create'
                    events.append(('create',)); return {'conversation_id': '373800000000000004'}
                def _start_stream(self, job, prompt, seconds, ratio, mode, uploaded, voiced, sound):
                    events.append(('stream', mode, len(uploaded), len(voiced), sound))
                    assert json.loads(receipt.read_text())['conversation_id'] == job
                    return True
            env = {'RUNNER_TEMP': d, 'GITHUB_RUN_ID': '1234567890', 'GITHUB_REPOSITORY': 'matheusmagah-cpu/heroverse-engine',
                   'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ATTEMPT': '1',
                   'PAVO_IMAGE_LEDGER': str(Path(d)/'fresh-quota.json')}
            allowed = [False]
            import dispatch_guard
            with patch.dict(os.environ, env), patch.object(bridge, 'inputs', return_value=({}, m)), \
                 patch.object(bridge, 'lease'), patch.object(bridge, 'persist', side_effect=lambda state, dest: bridge.atomic(dest, state)), \
                 patch.object(bridge, 'PrivateVideoClient', Client), patch.object(dispatch_guard, 'pavo_budget', return_value=0):
                with self.assertRaisesRegex(bridge.Blocked, 'ZERO_CREDIT'):
                    bridge.cli('prepare')
                self.assertEqual(events, [('quote', 10, '9:16', 'frames_to_video', 1, 0, False)])
                self.assertEqual(json.loads(receipt.read_text())['state'], 'CLAIMED')
                events.clear(); allowed[0] = True
                bridge.cli('prepare'); bridge.cli('ready')
                self.assertEqual(json.loads(receipt.read_text())['state'], 'INPUT_VERIFIED')
                self.assertFalse((bridge.ROOT/'.episode'/'private-audio-1234567890'/'input.wav').exists())
                bridge.cli('submit')
                self.assertEqual([e[0] for e in events], ['quote', 'quote', 'upload', 'create', 'stream'])
                self.assertEqual(events[-1], ('stream', 'frames_to_video', 1, 0, False))
                self.assertEqual(json.loads(receipt.read_text())['state'], 'UNKNOWN')
                with self.assertRaisesRegex(bridge.Blocked, 'EXISTING_SUBMISSION'):
                    bridge.cli('submit')

    def test_exact_wav_and_timing_required(self):
        bridge.validate(self.m, reference_check=False)
        bridge.check_audio(self.m, self.audio)
        for field, value in [('audio_bytes', True), ('speech_seconds', float('nan')),
                             ('reference', '../../outside.jpg'), ('production_approved', True),
                             ('sound', True), ('seconds', 13), ('audio_sha256', 'bad')]:
            m = dict(self.m, **{field: value})
            with self.subTest(field=field), self.assertRaises(bridge.Blocked):
                bridge.validate(m, reference_check=False)
        with self.assertRaises(bridge.Blocked): bridge.check_audio(self.m, self.audio[:-2])
        with self.assertRaises(bridge.Blocked): bridge.check_audio(self.m, wav(9))
        m = dict(self.m, seconds=6, audio_seconds=6, speech_seconds=5.7529166667)
        with self.assertRaisesRegex(bridge.Blocked, 'SPEECH_PADDING'): bridge.validate(m, reference_check=False)

    def test_storage_authority_and_headers(self):
        valid = {'public_url': 'https://cos-aigc-default.agnes-ai.space/test.wav',
                 'upload_url': 'https://aigc-default-1395352844.cos.ap-singapore.myqcloud.com/test.wav?sig=x',
                 'required_headers': {'Content-Type': 'audio/wav'}}
        bridge.upload_record(valid)
        for bad in ({**valid, 'public_url': 'https://evil.invalid/test.wav'},
                    {**valid, 'upload_url': 'https://cos-aigc-default.agnes-ai.space:444/test.wav'},
                    {**valid, 'required_headers': {'Authorization': 'Bearer secret'}},
                    {**valid, 'required_headers': {'Cookie': 'secret'}},
                    {**valid, 'required_headers': {'Host': 'evil.invalid'}}):
            with self.assertRaises(bridge.Blocked): bridge.upload_record(bad)

    def test_quote_refusal_precedes_attachment(self):
        class Client:
            def _quote(self, *a): return {'zero_cost_confirmed': False}
            def _video_json(self, *a): raise AssertionError('provider mutation')
        with self.assertRaisesRegex(bridge.Blocked, 'ZERO_CREDIT'):
            bridge.prepare_upload(self.m, Client())

    def test_receipt_identity_and_replay(self):
        r = bridge.initial_record(self.m, '1234567890')
        self.assertFalse(r['production_approved'])
        self.assertNotIn('prompt', json.dumps(bridge.public_record(r)))
        for state in ('CLAIMED', 'UPLOAD_PENDING', 'SUBMITTING', 'UNKNOWN', 'COMPLETE'):
            with self.subTest(state=state), self.assertRaises(bridge.Blocked):
                bridge.require_new([dict(r, state=state)], r['request_sha256'])

    def test_submission_callback_persists_before_stream(self):
        with tempfile.TemporaryDirectory() as d:
            events = []
            r = bridge.initial_record(self.m, '1234567890')
            g = bridge.RecordingGuard(Path(d)/'quota.json', r, lambda: events.append(copy.deepcopy(r)))
            g.submitted('373800000000000001', 2)
            self.assertEqual(events[0]['conversation_id'], '373800000000000001')
            self.assertEqual(events[0]['state'], 'SUBMITTING')
            self.assertEqual(events[0]['submitted_at'], bridge.public_record(r)['submitted_at'])
            self.assertEqual(bridge.public_record(r)['shots']['k-close']['clips'][0]['generations'][0]['conversation_id'],
                             '373800000000000001')

    def test_unknown_is_never_resubmitted(self):
        class Client:
            def job(self, cid): return {'conversation_id':cid,'status':'incomplete','videos':[]}
            def generate_video(self, *a, **kw): raise AssertionError('duplicate generation')
        r = bridge.initial_record(self.m, '1234567890')
        r.update(state='UNKNOWN', conversation_id='373800000000000001')
        bridge.poll_once(r, Client())
        self.assertEqual(r['state'], 'UNKNOWN')
        self.assertEqual(r['conversation_id'], '373800000000000001')

    def test_terminal_retry_requires_same_last_failed_job_and_cooldown(self):
        r=bridge.public_record(bridge.initial_record(self.m,'1234567890'))
        r.update(state='FAILED',conversation_id='373800000000000001',
                 terminal_at=(datetime.now(timezone.utc)-timedelta(hours=4)).isoformat())
        self.assertEqual(bridge.require_new([r],r['request_sha256'],retry_run=r['run_id']),r)
        for change in ({'state':'UNKNOWN'},{'state':'COMPLETE'},{'conversation_id':None},
                       {'terminal_at':datetime.now(timezone.utc).isoformat()}):
            with self.subTest(change=change), self.assertRaises(bridge.Blocked):
                bridge.require_new([{**r,**change}],r['request_sha256'],retry_run=r['run_id'])
        with self.assertRaises(bridge.Blocked):
            bridge.require_new([r],r['request_sha256'],retry_run='1234567891')
        class C:
            def __init__(self,status,videos): self.status,self.videos=status,videos
            def job(self,cid): return {'status':self.status,'videos':self.videos,'conversation_id':cid}
        bridge.verify_retry(r,C('failed',[]))
        for status,videos in [('incomplete',[]),('completed',[{'url':'redacted'}]),('blocked',[])]:
            with self.assertRaises(bridge.Blocked): bridge.verify_retry(r,C(status,videos))

    def test_retry_requires_all_history_failed_and_the_latest_source(self):
        now = datetime.now(timezone.utc)
        records = []
        for i, hours in enumerate((20, 12, 4)):
            r = bridge.public_record(bridge.initial_record(self.m, str(1234567890 + i)))
            created = now - timedelta(hours=hours)
            r.update(state='FAILED', conversation_id=str(373800000000000001 + i),
                     created_at=created.isoformat(), terminal_at=(created + timedelta(minutes=1)).isoformat())
            records.append(r)
        digest = records[-1]['request_sha256']
        latest = records[-1]['run_id']
        self.assertEqual(bridge.require_new(records, digest, retry_run=latest), records[-1])
        for old in records[:-1]:
            with self.subTest(old=old['run_id']), self.assertRaisesRegex(bridge.Blocked, 'RETRY_SOURCE_NOT_LATEST'):
                bridge.require_new(records, digest, retry_run=old['run_id'])
        for index in (0, 1):
            for state in ('UNKNOWN', 'COMPLETE', 'SUBMITTING'):
                history = copy.deepcopy(records)
                history[index]['state'] = state
                with self.subTest(index=index, state=state), self.assertRaises(bridge.Blocked):
                    bridge.require_new(history, digest, retry_run=latest)

    def test_e227_history_reads_do_not_move_usage_or_clear_newer_failures(self):
        now=datetime(2030,1,2,12,tzinfo=timezone.utc);old=now-timedelta(days=1)
        r=bridge.public_record(bridge.initial_record(self.m,'1234567890'))
        r.update(state='COMPLETE',submitted_at=old.isoformat(),conversation_id='900001',
                 shots={'k-close':{'clips':[{'generations':[{'conversation_id':'900001','flags':[]}]}]}})
        recent={'shots':{'x':{'clips':[{'generations':[
            {'conversation_id':'900002','flags':['NO_VIDEO']},{'conversation_id':'900003','flags':['NO_VIDEO']}]}]}}}
        used=bridge.quota.combine([(now,r),(now-timedelta(minutes=1),recent)],'2030-01-02')
        self.assertEqual((used['units'],used['failed_tail']),(4,2))
        r.update(state='UNKNOWN',submitted_at=now.isoformat())
        self.assertEqual(bridge.quota.combine([(now,r),(now-timedelta(minutes=1),recent)],'2030-01-02')['failed_tail'],2)
        r.pop('submitted_at')
        with self.assertRaises(bridge.PavoError): bridge.quota.combine([(now,r)],'2030-01-02')

    def test_e226_private_bridge_persists_only_public_record(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'repo'; root.mkdir()
            bare = Path(d)/'origin.git'
            def run(*args):
                return subprocess.run(args, cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            run('git','init','-q','--bare',str(bare)); run('git','init','-q')
            run('git','config','user.name','Test'); run('git','config','user.email','test@example.invalid')
            (root/'safe.txt').write_text('base')
            run('git','add','safe.txt'); run('git','commit','-qm','base')
            run('git','remote','add','origin',str(bare))
            (root/'PRIVATE.wav').write_bytes(self.audio)
            run('git','add','PRIVATE.wav')  # Even an unrelated staged file must not leak.
            private = Path(d)/'private'; private.mkdir()
            receipt = private/'receipt.json'
            r = bridge.initial_record(self.m,'1234567890')
            r['upload'] = {'upload_url':'https://example.invalid/PRIVATE?signature=SECRET'}
            with patch.object(bridge,'ROOT',root):
                bridge.persist(r,receipt)
                r.update(state='SUBMITTING',conversation_id='373800000000000001')
                bridge.persist(r,receipt)
            branch='refs/heads/claude/shot-probe-genesis-09-short-1234567890'
            files=run('git','--git-dir',str(bare),'ls-tree','-r','--name-only',branch)
            self.assertNotIn('PRIVATE.wav',files)
            saved=run('git','--git-dir',str(bare),'show',branch+':migration/evidence/shots/genesis-09-short/1234567890.json')
            self.assertNotIn('SECRET',saved); self.assertNotIn('upload_url',saved)
            self.assertEqual(json.loads(saved)['conversation_id'],'373800000000000001')

    def test_persist_failure_stops_stream_after_create(self):
        class Fake(bridge.PrivateVideoClient):
            def _plan(self,*a): return ('omni_to_video', [], [],)
            def _quote(self,*a): return {'zero_cost_confirmed':True}
            def _video_json(self,route,body=None,job=None):
                assert route=='create'; return {'conversation_id':'373800000000000001'}
            def _start_stream(self,*a): raise AssertionError('stream happened after lost ID persistence')
        with tempfile.TemporaryDirectory() as d:
            r=bridge.initial_record(self.m,'1234567890')
            def fail(): raise bridge.Blocked('PUBLIC_RECORD_PERSIST_FAILED')
            g=bridge.RecordingGuard(Path(d)/'q.json',r,fail)
            with self.assertRaisesRegex(bridge.Blocked,'PERSIST'):
                Fake(token='fake',guard=g).generate_video('Use the attached recording',seconds=10)
            self.assertEqual(r['conversation_id'],'373800000000000001')

    def test_dispatch_consumer_binds_manifest_and_recovery_is_zero_units(self):
        import dispatch_guard as g
        m=json.loads((bridge.ROOT/bridge.MANIFESTS/'genesis-09-k-close-20261030.json').read_text())
        i={'plan':'migration/production/bible/plans/genesis-09-short.json',
           'manifest':bridge.MANIFESTS+'genesis-09-k-close-20261030.json',
           'sha256':bridge.digest(m),'lease_run_id':'offline-test'}
        self.assertEqual(g.private_audio(i)['pavo_units'],2)
        self.assertEqual(g.private_audio(dict(i,reconcile_run='1234567890'))['pavo_units'],0)
        with self.assertRaises(g.Refusal): g.private_audio(dict(i,sha256='0'*64))

    def test_hook_dispatch_binds_real_first_frame_and_refuses_retry(self):
        import dispatch_guard as g
        path = bridge.MANIFESTS+'genesis-09-s-voice-20261030.json'
        m = json.loads((bridge.ROOT/path).read_text())
        i = {'plan':'migration/production/bible/plans/genesis-09-short.json', 'manifest':path,
             'sha256':bridge.digest(m), 'lease_run_id':'offline-test'}
        facts = g.private_audio(i)
        self.assertEqual(facts['pavo_units'], 2)
        self.assertIn('migration/production/bible/stills/genesis-09-s-voice.jpg', facts['deps'])
        self.assertNotIn(bridge.REFERENCE, facts['deps'])
        self.assertEqual(g.private_audio(dict(i,reconcile_run='1234567890'))['pavo_units'], 0)
        with self.assertRaises(g.Refusal): g.private_audio(dict(i,sha256='0'*64))
        with self.assertRaises(g.Refusal): g.private_audio(dict(i,retry_run='1234567890'))

    def test_get_only_recovery_after_failed_poll_never_unblocks_generation(self):
        import dispatch_guard as g
        m=json.loads((bridge.ROOT/bridge.MANIFESTS/'genesis-09-k-close-20261030.json').read_text())
        i={'plan':'migration/production/bible/plans/genesis-09-short.json',
           'manifest':bridge.MANIFESTS+'genesis-09-k-close-20261030.json',
           'sha256':bridge.digest(m),'lease_run_id':'offline-test','reconcile_run':'1234567890'}
        facts=g.private_audio(i);facts['subject']=i['plan']
        previous={'id':1234567890,'conclusion':'failure','head_sha':'a'*40,
                  'display_title':g.run_name(bridge.WORKFLOW,i)}
        def api(path):
            if path.startswith('actions/workflows/'): return {'workflow_runs':[previous]}
            if path.startswith('compare/'): return {'status':'identical','files':[]}
            raise AssertionError(path)
        with patch.object(g,'failed_in_guard',return_value=False), patch.object(g,'recorded_retry',return_value=False), \
             patch.object(g,'depends_on',return_value=[i['manifest']]):
            g.rerun(bridge.WORKFLOW,facts,i,api,'1234567891',1,'a'*40)
            with self.assertRaises(g.Refusal):
                g.rerun(bridge.WORKFLOW,facts,dict(i,reconcile_run=''),api,'1234567891',1,'a'*40)


if __name__ == '__main__': unittest.main()
