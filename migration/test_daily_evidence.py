import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
import daily_evidence as daily

class DailyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        daily.EVIDENCE.mkdir(parents=True)
        self.claim('1')
        self.now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        self.commit = Mock()

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def claim(self, run):
        (daily.EVIDENCE/'observer-claim.json').write_text(json.dumps({'run_id': run}))

    def evidence(self, run='1', day='15'):
        path = daily.EVIDENCE/('observer-'+run+'.json')
        path.write_text(json.dumps({'schema_version':'cloud-evidence-v1',
            'channel_id':'UCuMF6pJQkyMzaVoAxFL86yA', 'publication_performed':False,
            'production_ready':False, 'candidate_media_downloaded':False,
            'owned_channel':{}, 'market_snapshots':[], 'cohorts_by_duration':{},
            'operation_id':'cloud-evidence-'+run,
            'captured_at':'2026-10-'+day+'T11:00:00+00:00'}))
        return path

    def test_first_attempt_is_durable_before_call(self):
        self.assertIsNone(daily.reserve_or_reuse('1',self.commit,self.now))
        self.commit.assert_called_once()
        record=json.loads(next(daily.EVIDENCE.glob('daily-*')).read_text())
        self.assertEqual(record['status'],'CLAIMED')

    def test_completed_same_day_different_run_reuses_bytes_without_transport(self):
        daily.reserve_or_reuse('1',self.commit,self.now)
        source=self.evidence(); raw=source.read_bytes()
        daily.complete('1',source)
        self.claim('2')
        self.assertEqual(daily.reserve_or_reuse('2',self.commit,self.now),source)
        self.assertEqual(source.read_bytes(),raw)
        self.assertEqual(self.commit.call_count,1)

    def test_adopts_real_today_checkpoint_without_recollection(self):
        source=self.evidence('38749052276')
        self.assertEqual(daily.reserve_or_reuse('1',self.commit,self.now),source)
        self.assertEqual(json.loads(next(daily.EVIDENCE.glob('daily-*')).read_text())['status'],'COMPLETED')

    def test_unknown_or_failed_attempt_blocks_different_run(self):
        daily.reserve_or_reuse('1',self.commit,self.now)
        self.claim('2')
        with self.assertRaisesRegex(PermissionError,'RECONCILIATION'):
            daily.reserve_or_reuse('2',self.commit,self.now)

    def test_push_failure_does_not_admit_effect(self):
        self.commit.side_effect=RuntimeError('push failed')
        with self.assertRaises(RuntimeError):
            daily.reserve_or_reuse('1',self.commit,self.now)
        self.claim('2')
        with self.assertRaises(PermissionError):
            daily.reserve_or_reuse('2',Mock(),self.now)

    def test_new_utc_day_allows_new_attempt_not_old_date(self):
        daily.reserve_or_reuse('1',self.commit,self.now)
        daily.complete('1',self.evidence())
        self.claim('2')
        tomorrow=datetime(2026,10,16,12,tzinfo=timezone.utc)
        self.assertIsNone(daily.reserve_or_reuse('2',self.commit,tomorrow))
        self.assertEqual(len(list(daily.EVIDENCE.glob('daily-*'))),2)

    def test_tampered_receipt_fails_closed(self):
        source=self.evidence()
        daily.reserve_or_reuse('1',self.commit,self.now)
        source.write_text(source.read_text()+' ')
        with self.assertRaisesRegex(PermissionError,'BINDING'):
            daily.reserve_or_reuse('1',self.commit,self.now)

    def test_missing_claim_blocks_before_commit(self):
        (daily.EVIDENCE/'observer-claim.json').unlink()
        with self.assertRaises(PermissionError):
            daily.reserve_or_reuse('1',self.commit,self.now)
        self.commit.assert_not_called()

    def test_health_and_candidate_stages_remain_separate(self):
        self.assertTrue(daily.normal_collection({}))
        for flag in ['HERO_AUTH_HEALTH_ONLY','HERO_CANDIDATE_PROBE_ONLY','HERO_CANDIDATE_CATALOG_ONLY','HERO_REFERENCE_EXTENSION_ONLY']:
            self.assertFalse(daily.normal_collection({flag:'true'}))

    def test_midnight_completion_does_not_consume_next_day(self):
        daily.reserve_or_reuse('1',self.commit,self.now)
        daily.complete('1',self.evidence(day='16'))
        self.claim('2')
        self.assertIsNone(daily.reserve_or_reuse('2',self.commit,
            datetime(2026,10,16,12,tzinfo=timezone.utc)))

    def test_reuse_checkpoint_preserves_original_state_and_capture(self):
        import sqlite3
        from unittest.mock import patch
        import durable_evidence_checkpoint as checkpoint
        source=self.evidence('38749052276')
        Path('cloud-evidence').mkdir()
        Path('cloud-evidence/reused-evidence.json').write_bytes(source.read_bytes())
        Path('cloud-evidence/reuse-source.json').write_text(json.dumps({'source_path':str(source)}))
        with sqlite3.connect('cloud-evidence/quota-ledger.sqlite3') as db:
            db.execute('CREATE TABLE unchanged_quota (value INTEGER)')
            db.execute('INSERT INTO unchanged_quota VALUES (23)')
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine','GITHUB_RUN_ID':'1'}), patch.object(checkpoint,'git'), patch.object(checkpoint,'commit') as commit:
            checkpoint.main('checkpoint')
        state=json.loads(checkpoint.STATE.read_text())
        self.assertEqual(state['last_checkpointed_run'],'38749052276')
        self.assertTrue(state['collection_complete'])
        self.assertEqual(state['last_reuse_run'],'1')
        self.assertEqual(state['reused_observation']['captured_at'],'2026-10-15T11:00:00+00:00')
        self.assertFalse((daily.EVIDENCE/'observer-1.json').exists())
        self.assertFalse(checkpoint.CLAIM.exists())
        commit.assert_called_once()

    def test_changed_reuse_copy_blocks_checkpoint(self):
        source=self.evidence()
        copied=Path('copy.json');copied.write_text(source.read_text()+' ')
        with self.assertRaisesRegex(PermissionError,'COPY_CHANGED'):
            daily.reuse_state('2',source,copied)

if __name__=='__main__':unittest.main()
