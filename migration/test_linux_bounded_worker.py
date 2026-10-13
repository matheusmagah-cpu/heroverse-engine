"""Real kernel qualification on the dedicated cloud runner, not mocked APIs."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from linux_bounded_worker import run_bounded

def alive(pid):
    path=Path('/proc')/str(pid)/'stat'
    if not path.exists():return False
    return path.read_text().split(') ',1)[1].split()[0]!='Z'

class KernelTests(unittest.TestCase):
    def test_kernel_memory_ceiling_refuses_excess_allocation(self):
        result=run_bounded([sys.executable,'-c','import time;value=bytearray(200*1024**2);time.sleep(10)'],
            cwd=Path.cwd(),memory_bytes=64*1024**2,timeout_seconds=4)
        self.assertEqual(result['status'],'FAILED',result)

    def test_success_and_log_limit(self):
        good=run_bounded([sys.executable,'-c','print("worker-ok")'],cwd=Path.cwd())
        self.assertEqual(good['status'],'SUCCEEDED',good)
        self.assertIn('worker-ok',good['stdout'])
        noisy=run_bounded([sys.executable,'-c','import time;print("x"*100000,flush=True);time.sleep(20)'],
            cwd=Path.cwd(),max_log_bytes=4096,timeout_seconds=4)
        self.assertEqual(noisy['status'],'LOG_LIMIT',noisy)
        self.assertLessEqual(noisy['log_bytes'],4096)

    def test_timeout_cleans_session_detached_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'child.pid'
            child='import os,time,pathlib;os.setsid();pathlib.Path('+repr(str(path))+').write_text(str(os.getpid()));time.sleep(60)'
            parent='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(60)'
            result=run_bounded([sys.executable,'-c',parent],cwd=Path.cwd(),timeout_seconds=2)
            self.assertEqual(result['status'],'TIMEOUT',result)
            self.assertTrue(path.exists(),result)
            self.assertFalse(alive(int(path.read_text())),result)

    def test_supervisor_death_cleans_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'worker.pid'
            worker='import os,time,pathlib;pathlib.Path('+repr(str(path))+').write_text(str(os.getpid()));time.sleep(60)'
            supervisor='from linux_bounded_worker import run_bounded;import sys,pathlib;run_bounded([sys.executable,"-c",'+repr(worker)+'],cwd=pathlib.Path.cwd(),timeout_seconds=20)'
            parent=subprocess.Popen([sys.executable,'-c',supervisor],cwd=Path(__file__).resolve().parent)
            deadline=time.monotonic()+8
            try:
                while not path.exists() and time.monotonic()<deadline:time.sleep(.025)
                self.assertTrue(path.exists())
                pid=int(path.read_text());parent.kill();parent.wait(timeout=5)
                deadline=time.monotonic()+5
                while alive(pid) and time.monotonic()<deadline:time.sleep(.025)
                self.assertFalse(alive(pid))
            finally:
                if parent.poll() is None:parent.kill();parent.wait(timeout=5)

if __name__=='__main__':unittest.main()
