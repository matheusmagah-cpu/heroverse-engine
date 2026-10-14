import json,os,sqlite3,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from observe_public_av import ExistingObserverLedger,main

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.before=Path.cwd();os.chdir(self.tmp.name)
        Path('migration/evidence').mkdir(parents=True)
        self.claim=Path('migration/evidence/observer-claim.json')
        self.claim.write_text(json.dumps({'run_id':'fixture'}))
        self.sql=Path('migration/evidence/observer-ledger.sql')
        self.db=Path('quota.sqlite3')
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE general_quota_debits (key TEXT PRIMARY KEY, units INTEGER)')
            c.execute("INSERT INTO general_quota_debits VALUES('historical',15)")
        self.messages=[]
        self.mod=types.SimpleNamespace(CLAIM=self.claim,SQL=self.sql,commit=self.messages.append)
        self.p=patch.dict(sys.modules,{'durable_evidence_checkpoint':self.mod});self.p.start()
        self.l=ExistingObserverLedger(self.db,'fixture')
    def tearDown(self): self.p.stop();os.chdir(self.before);self.tmp.cleanup()
    def test_reservation_dump_preserves_native_debits(self):
        self.assertEqual(self.l.reserve('public-av:a','h',1178,28800)['status'],'NEW')
        c=sqlite3.connect(':memory:');c.executescript(self.sql.read_text())
        self.assertEqual(c.execute('SELECT units FROM general_quota_debits').fetchone()[0],15)
        self.assertEqual(c.execute('SELECT state FROM public_av_reservations').fetchone()[0],'CLAIMED')
        self.assertEqual(len(self.messages),1)
    def test_unresolved_effect_blocks_other_work(self):
        self.l.reserve('public-av:a','h',1178,28800)
        self.assertEqual(self.l.reserve('public-av:b','h2',1178,28800)['status'],'BLOCKED')
    def test_receipt_replays_and_tampering_blocks(self):
        self.l.reserve('public-av:a','h',1178,28800)
        receipt={'key':'public-av:a','request_hash':'h','publication_authorized':False}
        self.l.persist(receipt)
        self.assertEqual(self.l.reserve('public-av:a','h',1178,28800)['receipt'],receipt)
        Path('migration/evidence/public-av-a.json').write_text('{}')
        with self.assertRaises(PermissionError):self.l.reserve('public-av:a','h',1178,28800)
    def test_push_failure_does_not_authorize_network(self):
        def broken(message):raise OSError('fixture push failed')
        self.mod.commit=broken
        with self.assertRaises(OSError):self.l.reserve('public-av:a','h',1178,28800)
        self.assertEqual(self.l.reserve('public-av:a','h',1178,28800)['status'],'BLOCKED')
    def test_recovery_consumed_durably_before_effect(self):
        recovery=Path('migration/evidence/av-recovery-pending.json')
        recovery.write_text(json.dumps({'status':'PENDING','attempts':0}))
        self.l.recovery_path=recovery
        claim=self.l.reserve('public-av:recovery','hash',1178,28800)
        self.assertTrue(claim['durable'])
        saved=json.loads(recovery.read_text())
        self.assertEqual(saved['status'],'ATTEMPT_CLAIMED')
        self.assertEqual(saved['attempts'],1)
        self.assertEqual(saved['run_id'],'fixture')
        self.assertEqual(len(self.messages),1)
    def test_expired_scheduled_recovery_makes_no_provider_call(self):
        recovery=Path('migration/evidence/av-recovery-pending.json')
        recovery.write_text(json.dumps({'status':'PENDING','attempts':0,'utc_date':'1999-01-01'}))
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'matheusmagah-cpu/heroverse-engine',
                                   'GITHUB_EVENT_NAME':'schedule'},clear=False):
            self.assertEqual(main(),0)
        self.assertEqual(json.loads(recovery.read_text())['attempts'],0)
    def test_daily_limit_counts_completed_attempts(self):
        self.l.reserve('public-av:a','h',1178,28800)
        self.l.persist({'key':'public-av:a','request_hash':'h'})
        self.assertEqual(self.l.reserve('public-av:b','h2',28000,28800)['status'],'BLOCKED')

if __name__=='__main__':unittest.main()
