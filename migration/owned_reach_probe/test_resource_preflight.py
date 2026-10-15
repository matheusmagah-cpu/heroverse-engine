import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import run_existing_reach_probe as w

HERE=Path(__file__).parent
PRIOR=(HERE/'owned-reach-preflight-failure-38822029275.json' if (HERE/'owned-reach-preflight-failure-38822029275.json').exists() else w.PREVIOUS_FAILURE_PATH)
ENV={'GITHUB_REPOSITORY':w.REPOSITORY,'HERO_REPOSITORY_PRIVATE':'true','GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_NUMBER':'3','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'123'}

def put_prior(root, raw=None):
    path=root/w.PREVIOUS_FAILURE_PATH;path.parent.mkdir(parents=True);path.write_bytes(raw or PRIOR.read_bytes())
    second=root/w.SECOND_FAILURE_PATH
    second.write_bytes(w.SECOND_FAILURE_PATH.read_bytes())

class Tests(unittest.TestCase):
    def test_resource_thresholds_preserved_and_failures_measured(self):
        mib=1024**2
        cases=[(255*mib,600*mib,False,True),(300*mib,511*mib,True,False),(255*mib,511*mib,False,False),(256*mib,512*mib,True,True)]
        for disk,ram,disk_pass,ram_pass in cases:
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);put_prior(root)
                real_read=Path.read_text
                def read(path,*a,**kw):return f'MemAvailable: {ram//1024} kB\n' if str(path)=='/proc/meminfo' else real_read(path,*a,**kw)
                with patch.object(w.shutil,'disk_usage',return_value=SimpleNamespace(free=disk)), patch.object(Path,'read_text',read),patch.object(w.time,'sleep'):
                    if disk_pass and ram_pass:value=w.preflight(root,ENV)
                    else:
                        with self.assertRaises(w.ResourceMarginBlocked) as caught:w.preflight(root,ENV)
                        value=caught.exception.measurements
                        self.assertEqual(str(caught.exception),'RESOURCE_MARGIN_REQUIRED')
                self.assertEqual(value['disk_free_bytes'],disk);self.assertEqual(value['memory_available_bytes'],ram)
                self.assertEqual(value['disk_margin_passed'],disk_pass);self.assertEqual(value['memory_margin_passed'],ram_pass)
                self.assertEqual(value['required_disk_free_bytes'],256*mib);self.assertEqual(value['required_memory_available_bytes'],512*mib)
                self.assertEqual(value['resource_policy'],'BOUNDED_REPORTING_STDLIB_ONLY_V1')
                self.assertEqual(value['memory_samples_bytes'],[ram,ram])
    def test_recovery_exact_prior_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);put_prior(root);path=root/w.PREVIOUS_FAILURE_PATH;before=path.read_bytes()
            self.assertEqual(w.validate_previous_failure(root)['previous_network_operations'],0)
            self.assertEqual(path.read_bytes(),before)
            path.write_bytes(before+b' ')
            with self.assertRaisesRegex(w.core.ProbeBlocked,'HASH_MISMATCH'):w.validate_previous_failure(root)
    def test_first_third_and_second_attempt_rejected(self):
        for number,attempt in [('1','1'),('2','1'),('4','1'),('3','2')]:
            env=dict(ENV,GITHUB_RUN_NUMBER=number,GITHUB_RUN_ATTEMPT=attempt)
            with self.assertRaisesRegex(w.core.ProbeBlocked,'ONE_EXECUTION'):w.preflight(Path('.'),env)
    def test_missing_prior_blocks_before_resource_read(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(w.shutil,'disk_usage',side_effect=AssertionError('must not execute')):
            with self.assertRaises(FileNotFoundError):w.preflight(Path(temp),ENV)
    def test_memory_uses_lowest_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);put_prior(root)
            values=iter(['MemAvailable: 1048576 kB\n','MemAvailable: 524287 kB\n'])
            real_read=Path.read_text
            def read(path,*a,**kw):return next(values) if str(path)=='/proc/meminfo' else real_read(path,*a,**kw)
            with patch.object(Path,'read_text',read),patch.object(w.shutil,'disk_usage',return_value=SimpleNamespace(free=1024**3)),patch.object(w.time,'sleep'):
                with self.assertRaises(w.ResourceMarginBlocked) as caught:w.preflight(root,ENV)
                self.assertEqual(caught.exception.measurements['memory_available_bytes'],524287*1024)

if __name__=='__main__':unittest.main(verbosity=2)
