import ast
import copy
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
import native_probe as n
import next_window as w


class DeliveryStateTests(unittest.TestCase):
    def test_terminal_failure_with_or_without_stale_url(self):
        for url in (None, 'https://cdn.example/stale.mp4'):
            with self.subTest(url=url), self.assertRaisesRegex(n.ProbeError, 'TERMINAL_FAILURE'):
                n.ready_delivery_url({'success':0,'progress':1000,'download_url':url})

    def test_pending_zero_success_is_not_failure_or_delivery(self):
        for progress in (0, 1, 999, None):
            self.assertIsNone(n.ready_delivery_url({'success':0,'progress':progress,'download_url':'https://cdn.example/pending'}))

    def test_explicit_error_overrides_url_and_success(self):
        for err in ({'status':'failed'}, {'error':'timeout'}):
            with self.assertRaisesRegex(n.ProbeError, 'JOB_FAILED'):
                n.ready_delivery_url(dict(success=1,progress=1000,download_url='https://cdn.example/clip',**err))

    def test_success_without_delivery_never_passes(self):
        for url in (None, '', ' ', 42):
            with self.assertRaisesRegex(n.ProbeError, 'WITHOUT_DELIVERY_URL'):
                n.ready_delivery_url({'success':1,'progress':1000,'download_url':url})

    def test_incomplete_or_unknown_state_does_not_release_url(self):
        for state in ({'success':1,'progress':999},{'progress':1000},{'success':1}):
            self.assertIsNone(n.ready_delivery_url(dict(state,download_url='https://cdn.example/clip')))

    def test_ready_url_only_allows_fetch_not_decode_approval(self):
        for key in ('download_url','downloadUrl','file_url'):
            self.assertEqual(n.ready_delivery_url(dict(success=1,progress=1000,**{key:'https://cdn.example/clip'})), 'https://cdn.example/clip')

    def test_string_boolean_and_invalid_state_values_never_release_url(self):
        for state in ({'success':'0','progress':1000}, {'success':'1','progress':1000},
                      {'success':0,'progress':'1000'}, {'success':True,'progress':1000},
                      {'success':1,'progress':1000.0}, {'success':2,'progress':1000},
                      {'success':1,'progress':-1}, {'success':1,'progress':1001}):
            with self.subTest(state=state), self.assertRaisesRegex(n.ProbeError,'INVALID_PROVIDER_PROGRESS_STATE'):
                n.ready_delivery_url(dict(state,download_url='https://cdn.example/clip'))

    def test_recovery_http_status_retained_without_sensitive_error_fields(self):
        tree = ast.parse((CODE/'recover_midpoint_delivery.py').read_text())
        attempt = next(x for x in tree.body if isinstance(x, ast.Try))
        minimal = ast.Module(body=[copy.deepcopy(attempt)],type_ignores=[])
        error = n.HTTPError('https://cdn.example/private-token',503,'private reason',{},None)
        receipt = {}; out = MagicMock()
        ns = dict(n=n,out=out,receipt=receipt,url='unused',inspect=Mock(),time=Mock(),started=0,json=__import__('json'))
        ns['time'].monotonic.return_value=0
        with patch.object(n,'fetch_media',side_effect=error), patch('builtins.print'):
            exec(compile(ast.fix_missing_locations(minimal),'recovery-test','exec'),ns)
        self.assertEqual(receipt['failure_code'],'HTTP_503')
        self.assertEqual(receipt['delivery_http_status'],503)
        self.assertEqual(receipt['status'],'DELIVERY_RECOVERY_FAILED_NO_AUTOMATIC_RETRY')
        self.assertNotIn('private',str(receipt))
        ns['inspect'].assert_not_called()

    def test_invalid_body_is_rejected(self):
        with self.assertRaisesRegex(n.ProbeError,'INVALID_PROGRESS_BODY'):
            n.ready_delivery_url([])


def extracted_loop(path, namespace):
    # Exercise the actual production polling loop, excluding effectful startup.
    tree = ast.parse(path.read_text())
    run = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'run')
    loop = next(x for x in run.body if isinstance(x, ast.For))
    function = ast.FunctionDef(name='poll_only',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]), body=[copy.deepcopy(loop)],decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    exec(compile(module,str(path),'exec'),namespace)
    return namespace['poll_only']


class ActualPollingLoopTests(unittest.TestCase):
    def execute(self, filename, states, fetch_error=None):
        fetch = Mock(side_effect=fetch_error)
        inspect = Mock()
        progress = Mock(side_effect=states)
        e = {}
        fake_time = Mock(); fake_time.monotonic.return_value=0
        ns = dict(n=n,time=fake_time,MAX_POLLS=24,MAX_CONTROL_BYTES=262144,
            poll_deadline=270,deadline=270,job_id='existing',job='existing',key='unused',out=Path('/unused'),
            evidence=e,e=e,progress=progress,fetch_media=fetch,inspect_media=inspect,
            ready_delivery_url=n.ready_delivery_url,ProbeError=n.ProbeError,hashlib=n.hashlib,
            require=w.require,inspect=inspect)
        with patch.object(n,'progress',progress), patch.object(n,'fetch_media',fetch), patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            fn=extracted_loop(CODE/filename,ns)
            try:
                fn()
                error=None
            except n.ProbeError as ex:
                error=str(ex)
        return progress,fetch,inspect,e,error

    def test_both_real_loops_stop_terminal_and_never_get_media(self):
        for f in ('native_probe.py','next_window.py'):
            for url in (None,'https://cdn.example/stale'):
                with self.subTest(file=f,url=url):
                    p,fetch,i,e,error=self.execute(f,[{'success':0,'progress':1000,'download_url':url}])
                    self.assertIn('TERMINAL_FAILURE',error);self.assertEqual(p.call_count,1)
                    fetch.assert_not_called();i.assert_not_called();self.assertNotIn('status',e)

    def test_both_real_loops_wait_pending_then_inspect_delivered_media(self):
        for f in ('native_probe.py','next_window.py'):
            p,fetch,i,e,error=self.execute(f,[{'success':0,'progress':250},{'success':1,'progress':1000,'download_url':'https://cdn.example/clip'}])
            self.assertIsNone(error);self.assertEqual(p.call_count,2)
            fetch.assert_called_once();i.assert_called_once()

    def test_success_without_url_never_fetches_or_inspects(self):
        for f in ('native_probe.py','next_window.py'):
            p,fetch,i,e,error=self.execute(f,[{'success':1,'progress':1000,'download_url':None}])
            self.assertIn('WITHOUT_DELIVERY_URL',error)
            fetch.assert_not_called();i.assert_not_called();self.assertNotIn('status',e)

    def test_fetch_failure_cannot_set_success_or_run_inspection(self):
        for f in ('native_probe.py','next_window.py'):
            p,fetch,i,e,error=self.execute(f,[{'success':1,'progress':1000,'download_url':'https://cdn.example/clip'}],n.ProbeError('NO_BYTES'))
            self.assertEqual(error,'NO_BYTES');i.assert_not_called();self.assertNotIn('status',e)

if __name__=='__main__':
    unittest.main(verbosity=2)
