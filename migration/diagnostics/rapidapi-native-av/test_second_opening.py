import copy
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request
import second_opening as s

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / 'migration/evidence/cloud-video-player-20261015'

class Guards(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((EVIDENCE / 'second-opening-plan.json').read_text())
        self.ledger = json.loads((EVIDENCE / 'native-av-reservations.json').read_text())
        self.billing = json.loads((EVIDENCE / 'second-opening-billing-admission.json').read_text())
        self.now = dt.datetime.fromisoformat(self.billing['observed_at'])

    def admit(self):
        return s.admit(self.plan, self.ledger, self.billing, self.now)

    def test_admission_preserves_prior_claims_and_planned_state(self):
        before = copy.deepcopy((self.plan, self.ledger))
        claim = self.admit()
        self.assertEqual(claim['status'], 'RESERVED_BEFORE_EFFECT')
        self.assertEqual((self.plan, self.ledger), before)
        self.assertEqual(len(self.ledger['claims']), 2)

    def test_no_repeat_claim(self):
        self.ledger['claims'].append(self.admit())
        with self.assertRaisesRegex(s.n.ProbeError, 'PRIOR_CLAIM_EXISTS'):
            self.admit()

    def test_source_and_bounds_exact(self):
        self.assertEqual(s.PARAMS['url'], 'https://www.youtube.com/watch?v=BeFOHnncaeQ')
        self.assertEqual((s.PARAMS['start_time'], s.PARAMS['end_time'], s.PARAMS['format']), (0, 40, '1080'))
        self.assertNotIn('no_merge', s.PARAMS)
        self.plan['parameters']['url'] = 'https://www.youtube.com/watch?v=j2rk8ycXe3c'
        with self.assertRaisesRegex(s.n.ProbeError, 'PLAN_OR_RESERVATION_CHANGED'):
            self.admit()

    def test_expired_billing_stops(self):
        self.now += dt.timedelta(seconds=3601)
        with self.assertRaisesRegex(s.n.ProbeError, 'EXPIRED'):
            self.admit()

    def test_missing_zero_budget_stops(self):
        self.billing['github_actions_budget_usd'] = 1
        with self.assertRaisesRegex(s.n.ProbeError, 'ZERO_SPEND_STOP'):
            self.admit()

    def test_changed_bandwidth_stops(self):
        self.billing['rapidapi_bandwidth_display'] = 'N/A'
        with self.assertRaisesRegex(s.n.ProbeError, 'HEADROOM'):
            self.admit()

    def test_no_precise_byte_claim_from_rounded_ui(self):
        self.assertTrue(self.billing['storage_display_is_rounded_not_exact_bytes'])
        self.assertNotIn('github_account_storage_headroom_bytes', self.billing)
        self.assertEqual(self.billing['bandwidth_headroom_basis'], 'PRACTICAL_DISPLAY_INFERENCE_NOT_HARD_STOP_PROOF')

    def test_daily_cap(self):
        extra = copy.deepcopy(self.ledger['claims'][0]); extra['request_id'] = 'other'
        self.ledger['claims'].append(extra)
        with self.assertRaisesRegex(s.n.ProbeError, 'DAILY_JOB_CAP'):
            self.admit()

    def test_fresh_quota_not_stale_exact_assumption(self):
        q={'x-ratelimit-units-limit':'500','x-ratelimit-units-remaining':'474'}
        for p in ('x-ratelimit-requests','x-ratelimit-rapid-free-plans-hard-limit'):
            q[p+'-limit']='500000';q[p+'-remaining']='499970'
        s.fresh_quota(q)
        q['x-ratelimit-units-remaining']='13'
        with self.assertRaisesRegex(s.n.ProbeError,'UNIT_HEADROOM'):
            s.fresh_quota(q)

    def test_all_gateway_attempts_counted_no_41st(self):
        inner=Mock(); e={}; opener=s.CountedOpener(inner,e)
        for i in range(40):
            host='mcp.rapidapi.com' if i%2 else s.n.HOST
            opener.open(Request('https://'+host+'/api/progress'))
        with self.assertRaisesRegex(s.n.ProbeError,'CONTROL_REQUEST_CAP'):
            opener.open(Request('https://mcp.rapidapi.com'))
        self.assertEqual(inner.open.call_count,40)

    def test_external_media_not_counted_as_gateway(self):
        inner=Mock();e={};s.CountedOpener(inner,e).open(Request('https://pamela88.savenow.to/media'))
        self.assertNotIn('gateway_request_attempts',e)

    def test_outgoing_control_cap(self):
        inner=Mock();e={}
        with self.assertRaisesRegex(s.n.ProbeError,'OUTGOING_CONTROL_CAP'):
            s.CountedOpener(inner,e).open(Request('https://mcp.rapidapi.com',data=b'a'*32769))
        inner.open.assert_not_called()

    def test_terminal_never_becomes_delivery(self):
        with self.assertRaisesRegex(s.n.ProbeError,'TERMINAL_FAILURE'):
            s.n.ready_delivery_url({'success':0,'progress':1000,'download_url':'https://pamela88.savenow.to/media'})

    def test_media_byte_budget(self):
        class Response(io.BytesIO):
            headers={'Content-Length':str(s.n.MAX_MEDIA_BYTES+1)}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(s.n.ProbeError,'BYTE_BUDGET'):
                s.n.bounded_file(Response(b''),Path(temp)/'x.mp4')

    def test_rerun_refused_before_network(self):
        with patch.dict(s.os.environ, {'GITHUB_REPOSITORY':s.REPO,'GITHUB_RUN_NUMBER':'2','GITHUB_RUN_ATTEMPT':'1'}):
            with patch.object(s.n,'progress') as progress:
                with self.assertRaisesRegex(s.n.ProbeError,'REPEAT_RUN'):
                    s.run(Path('/unused'),{},'dummy-test')
                progress.assert_not_called()

    def test_nonconforming_duration_and_streams_rejected(self):
        for streams,duration in [([{'codec_type':'video','height':1080}],40),
            ([{'codec_type':'video','height':1080},{'codec_type':'audio'}],41),
            ([{'codec_type':'video','height':720},{'codec_type':'audio'}],40)]:
            data={'streams':streams,'format':{'duration':str(duration)}}
            with patch.object(s.n,'command',return_value=json.dumps(data).encode()):
                with self.assertRaises(s.n.ProbeError):
                    s.n.inspect_media(Path('/unused'),{})

    def _mocked_flow(self, outcome):
        from contextlib import ExitStack
        fake_response=Mock()
        fake_response.read.return_value=b'{"private":true}'
        fake_response.__enter__=Mock(return_value=fake_response)
        fake_response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=fake_response
        q={'x-ratelimit-units-limit':'500','x-ratelimit-units-remaining':'474'}
        for prefix in ('x-ratelimit-requests','x-ratelimit-rapid-free-plans-hard-limit'):
            q[prefix+'-limit']='500000';q[prefix+'-remaining']='499970'
        def progress(job,key,e,out,index):
            e['last_quota_headers']=q
            if index==99: return {'success':1,'progress':1000}
            if outcome=='success': return {'success':1,'progress':1000,'download_url':'https://pamela88.savenow.to/media'}
            if outcome=='terminal': return {'success':0,'progress':1000,'download_url':'https://pamela88.savenow.to/media'}
            return {'success':0,'progress':100}
        original_read=Path.read_text
        def read(path,*args,**kwargs):
            if path.name=='rapidapi-native-first-result.json':
                return json.dumps({'complete_clip_decode_passed':True,'last_quota_headers':q,'provider_job_id':'successful-existing-opening'})
            return original_read(path,*args,**kwargs)
        env={'GITHUB_REPOSITORY':s.REPO,'GITHUB_RUN_NUMBER':'1','GITHUB_RUN_ATTEMPT':'1',
             'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main','GH_ARTIFACT_TOKEN':'dummy'}
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            clock = stack.enter_context(patch.object(s.dt,'datetime',wraps=dt.datetime))
            clock.now.return_value = self.now
            stack.enter_context(patch.dict(s.os.environ,env))
            stack.enter_context(patch.object(s,'EVIDENCE',EVIDENCE))
            stack.enter_context(patch.object(Path,'read_text',read))
            stack.enter_context(patch.object(s,'artifact_preflight',return_value={}))
            stack.enter_context(patch.object(s.n,'command',return_value=b''))
            stack.enter_context(patch('urllib.request.build_opener',return_value=opener))
            stack.enter_context(patch.object(s.n,'build_opener',return_value=opener))
            stack.enter_context(patch.object(s.n,'Client',return_value=Mock()))
            stack.enter_context(patch.object(s.n,'progress',side_effect=progress))
            start=stack.enter_context(patch.object(s.n,'start_download',return_value={'id':'one-new-job'}))
            fetch=stack.enter_context(patch.object(s.n,'fetch_media'))
            def inspect(out,e):
                e['native_probe']={'streams':[{'codec_type':'video'},{'codec_type':'audio'}]}
                for t in (0,10,20,30,39): (out/('frame-%02d.jpg'%t)).write_bytes(b'mocked frame')
            stack.enter_context(patch.object(s.n,'inspect_media',side_effect=inspect))
            stack.enter_context(patch.object(s.time,'sleep'))
            stack.enter_context(patch.object(s.n,'PARAMS',s.n.PARAMS.copy()))
            stack.enter_context(patch.object(s.n,'REQUEST_ID',s.n.REQUEST_ID))
            e={'progress_polls':0,'control_response_bytes':0}
            if outcome=='success':
                s.run(Path(temp),e,'dummy-key')
                self.assertEqual(e['status'],'NATIVE_OPENING_DECODED_AWAITING_REVIEW')
                fetch.assert_called_once()
            else:
                code='TERMINAL_FAILURE' if outcome=='terminal' else 'PENDING_STOP_NO_AUTOMATIC_RECOVERY'
                with self.assertRaisesRegex(s.n.ProbeError,code):
                    s.run(Path(temp),e,'dummy-key')
                fetch.assert_not_called()
            start.assert_called_once()
            self.assertEqual(e['provider_job_id'],'one-new-job')
            self.assertTrue((Path(temp)/'reservation.json').exists())
            self.assertEqual(json.loads((Path(temp)/'job.json').read_text())['parameters']['url'],s.PARAMS['url'])

    def test_mocked_pending_flow_starts_once_no_fetch_or_restart(self):
        self._mocked_flow('pending')

    def test_mocked_terminal_url_never_fetched(self):
        self._mocked_flow('terminal')

    def test_mocked_success_single_job_and_one_download(self):
        self._mocked_flow('success')

    def test_workflow_single_manual_ten_minutes_short_retention(self):
        text=(ROOT/'.github/workflows/rapidapi-second-opening-once.yml').read_text()
        for expected in ('workflow_dispatch:', 'timeout-minutes: 10', 'retention-days: 1',
                         'github.run_number == 1', 'github.run_attempt == 1', 'contents: read'):
            self.assertIn(expected,text)
        self.assertNotIn('${{ runner.temp }}',text)
        self.assertNotIn('schedule:',text)
        self.assertNotIn('contents: write',text)

if __name__=='__main__':unittest.main()
