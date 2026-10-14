import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('checkpoint',Path(__file__).with_name('durable_evidence_checkpoint.py'))
checkpoint=importlib.util.module_from_spec(spec);spec.loader.exec_module(checkpoint)

def run(cwd,*args):
    return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()

class ConcurrentCheckpointTests(unittest.TestCase):
    def scenario(self,overlap):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);remote=root/'remote.git';worker=root/'worker';editor=root/'editor'
            run(root,'init','--bare','--initial-branch=main',str(remote))
            run(root,'clone',str(remote),str(worker))
            for path in [worker]:
                run(path,'config','user.name','Test');run(path,'config','user.email','test@example.invalid')
            evidence=worker/'migration/evidence';evidence.mkdir(parents=True)
            (evidence/'observer-ledger.sql').write_text('initial\n')
            (worker/'README.md').write_text('initial\n')
            run(worker,'add','.');run(worker,'commit','-m','initial');run(worker,'push','origin','main')
            run(root,'clone',str(remote),str(editor))
            run(editor,'config','user.name','Test');run(editor,'config','user.email','test@example.invalid')
            target='migration/evidence/observer-ledger.sql' if overlap else 'README.md'
            (editor/target).write_text('concurrent change\n')
            run(editor,'add',target);run(editor,'commit','-m','concurrent edit');run(editor,'push','origin','main')
            (evidence/'observer-ledger.sql').write_text('checkpoint preserved\n')
            before=run(editor,'rev-parse','HEAD');cwd=os.getcwd()
            try:
                os.chdir(worker)
                if overlap:
                    with self.assertRaisesRegex(PermissionError,'DURABLE_CONCURRENT_EVIDENCE_CONFLICT'):
                        checkpoint.commit('checkpoint')
                    self.assertEqual(before,run(root,'--git-dir',str(remote),'rev-parse','main'))
                    self.assertEqual('concurrent change',run(root,'--git-dir',str(remote),'show','main:migration/evidence/observer-ledger.sql'))
                else:
                    checkpoint.commit('checkpoint')
                    self.assertEqual('concurrent change',run(root,'--git-dir',str(remote),'show','main:README.md'))
                    self.assertEqual('checkpoint preserved',run(root,'--git-dir',str(remote),'show','main:migration/evidence/observer-ledger.sql'))
            finally:os.chdir(cwd)
    def test_unrelated_edit_preserved_and_checkpoint_committed(self):self.scenario(False)
    def test_competing_ledger_edit_blocks_without_overwrite(self):self.scenario(True)

if __name__=='__main__':unittest.main()
