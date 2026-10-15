import copy
import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import preserve_remaining_openings as p


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'config.json'
        self.config = {'version':'remaining-opening-preservation-v1','status':'VERIFIED_IDENTITIES_READY',
            'sources':[{'video_id':vid,'window_seconds':[0,40],'artifact_id':i+1,'source_run_id':9,
            'archive_bytes':100,'archive_sha256':hashlib.sha256(f'zip{i}'.encode()).hexdigest(),
            'native_bytes':50,'native_sha256':hashlib.sha256(f'mp4{i}'.encode()).hexdigest()}
            for i,vid in enumerate(p.ALLOWLIST)]}

    def load(self,config):
        self.path.write_text(json.dumps(config))
        return p.load_config(self.path)

    def test_pending_config_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'VERIFIED_SOURCE'):
            self.load({'version':'remaining-opening-preservation-v1',
                       'status':'WAITING_FOR_VERIFIED_IDENTITIES','sources':[]})

    def test_exact_allowlist_accepts_shared_run(self):
        self.assertEqual(list(self.load(self.config)),list(p.ALLOWLIST))

    def test_invalid_identity_is_rejected(self):
        for field,value in [('artifact_id',True),('native_bytes',0),('archive_bytes',96*1024*1024),
                            ('native_sha256','guess'),('window_seconds',[0,30]),('video_id','other')]:
            c=copy.deepcopy(self.config);c['sources'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.load(c)

    def test_duplicate_artifact_is_rejected(self):
        c=copy.deepcopy(self.config);c['sources'][1]['artifact_id']=1
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):self.load(c)

    def test_bind_pins_base_and_changes_only_source_identity(self):
        row=self.config['sources'][0];m=p.bind_base(row)
        self.assertEqual(m.ARTIFACT_ID,1);self.assertEqual(m.RELEASE_ID,411926125)
        self.assertEqual(m.REPO,'matheusmagah-cpu/heroverse-engine')
        self.assertEqual(m.NATIVE_SHA,row['native_sha256'])
        self.assertIn(row['video_id'],m.NAME)
        self.assertEqual(m.readback.__module__,'qualified_preservation_base')

    def test_changed_base_blocked_before_import(self):
        path=Path(self.tmp.name)/'bad.py';path.write_text('raise RuntimeError("executed")')
        with self.assertRaisesRegex(ValueError,'QUALIFIED_BASE'):p.bind_base(self.config['sources'][0],path)

    def test_reuse_uses_independent_readback_no_post(self):
        m=p.bind_base(self.config['sources'][0]);asset={'id':123}
        with patch.object(m,'destination',return_value=asset),patch.object(m,'readback',return_value={}) as readback,patch.object(m,'receipt',return_value='reused'),patch.object(m,'api') as api:
            self.assertEqual(m.transfer(Path('.')),'reused')
        readback.assert_called_once_with(asset);api.assert_not_called()

    def test_same_module_keeps_one_post_and_ambiguous_stop(self):
        m=p.bind_base(self.config['sources'][0])
        with patch.object(m,'destination',return_value=None),patch.object(m,'source_metadata'),patch.object(m,'discover_native',return_value=(Path('synthetic.mp4'),{})),patch.object(m,'receipt'),patch.object(m,'api',side_effect=TimeoutError) as api:
            with self.assertRaises(TimeoutError):m.transfer(Path('.'))
        self.assertEqual(api.call_count,1)

    def test_real_config_and_workflow_are_exact_and_sequential(self):
        rows=p.load_config()
        workflow=(Path(__file__).parents[1]/'.github/workflows/preserve-remaining-openings-release.yml').read_text()
        self.assertIn('test "$NUMBER" = 1',workflow)
        self.assertIn('test "$ATTEMPT" = 1',workflow)
        self.assertNotIn('continue-on-error',workflow)
        self.assertNotIn('matrix:',workflow)
        self.assertNotIn('push:',workflow)
        self.assertEqual(workflow.count('if: always()'),1)
        prefix,steps=workflow.split('    steps:\n',1)
        self.assertNotIn('runner.',prefix)
        self.assertNotIn('env.',prefix)
        order=[]
        for i,(vid,row) in enumerate(rows.items()):
            self.assertIn(f"artifact-ids: '{row['artifact_id']}'",workflow)
            self.assertIn(f"run-id: '{row['source_run_id']}'",workflow)
            pre=workflow.index('preflight '+vid);post=workflow.index('transfer '+vid)
            self.assertLess(pre,post)
            order.extend([pre,post])
        self.assertEqual(order,sorted(order))


if __name__=='__main__':unittest.main()
