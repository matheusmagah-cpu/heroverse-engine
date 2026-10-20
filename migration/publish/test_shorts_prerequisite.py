import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shorts_prerequisite as prerequisite

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'migration/production/pilot-012'


class Tests(unittest.TestCase):
    def fixture(self, root):
        d = Path(root) / 'production/pilot-012'
        for name in (*prerequisite.binding.FILES, 'out/review.json', 'script.json'):
            p = d / name; p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / name, p)
        return d

    def test_actual_qualified_long_and_changed_script(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.fixture(t)
            self.assertTrue(prerequisite.ready(d))
            (d/'script.json').write_bytes((d/'script.json').read_bytes()+b'\n')
            self.assertIn('LONG_SCRIPT_CHANGED', prerequisite.problems(d))

    def test_missing_malformed_documents_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            d = self.fixture(t)
            for name in (*prerequisite.binding.FILES, 'out/review.json'):
                p=d/name; original=p.read_bytes()
                for content in (b'{bad', b'null', b'[]'):
                    p.write_bytes(content); self.assertFalse(prerequisite.ready(d),name)
                p.unlink(); self.assertFalse(prerequisite.ready(d),name);p.write_bytes(original)

    def test_fail_unknown_stale_and_legacy_long(self):
        with tempfile.TemporaryDirectory() as t:
            d=self.fixture(t)
            for name,key,value in [('out/gate.json','decision','UNKNOWN'),('out/gate.json','decision','FAIL'),
                                   ('out/review.json','status','ERROR'),('out/review.json','output_sha256','a'*64),
                                   ('out/qa.json','criteria_version','pilot-qa-criteria-v2'),
                                   ('inspection/APPROVAL.json','approved',False)]:
                p=d/name; original=p.read_bytes();obj=json.loads(original);obj[key]=value;p.write_text(json.dumps(obj))
                self.assertFalse(prerequisite.ready(d),(name,key,value));p.write_bytes(original)

    def test_hold_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            d=self.fixture(t);p=Path(t)/'ops/PUBLICATION_HOLD';p.parent.mkdir();p.write_text('hold')
            self.assertEqual(prerequisite.problems(d),['PUBLICATION_HOLD'])

    def test_workflow_guard_before_quota(self):
        for name in ('shorts.yml','shorts-review.yml'):
            s=(ROOT/'.github/workflows'/name).read_text()
            self.assertLess(s.index('shorts_prerequisite.py'),s.index('HERO_GEMINI_API_KEY'))
        s=(ROOT/'.github/workflows/approve.yml').read_text()
        self.assertLess(s.index('Publication at the schedule.json time'),s.index('gh workflow run shorts.yml'))
        self.assertIn("if: env.SKIP != '1' && env.STATUS == 'PASS'",s[s.index('- name: Shorts only'):])
        s=(ROOT/'migration/ci/render_pilot.sh').read_text()
        for call in ('shorts_select.py','shorts_produce.py','shorts_review.py'):
            self.assertNotIn(call,s)
        self.assertIn('HANDOFF=1',s)

    def test_current_governance_and_frozen_hash(self):
        import hashlib
        s=(ROOT/'migration/SYSTEM.md').read_text()
        self.assertNotIn('5. the owner for the first sample',s)
        self.assertIn('personal first-sample approval is not required',s)
        self.assertEqual(hashlib.sha256((ROOT/'migration/production/qa_criteria_v3.json').read_bytes()).hexdigest(),
                         '4851878674101c7a64816815e9514786a2a7e0576d35b8bdf670ab7053c2e2b3')

if __name__ == '__main__': unittest.main()
