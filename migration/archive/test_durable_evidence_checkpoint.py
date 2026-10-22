import sqlite3,tempfile,unittest
from pathlib import Path
from durable_evidence_checkpoint import restore_ledger
class LedgerRestoreTests(unittest.TestCase):
 def test_continuation_preserves_all_historical_rows(self):
  original=Path(__file__).parent/'official-evidence/quota-ledger.sqlite3'
  if not original.exists():self.skipTest('real artifact is only present in local qualification')
  with tempfile.TemporaryDirectory() as t:
   sql=Path(t)/'ledger.sql';dest=Path(t)/'new.sqlite3'
   c=sqlite3.connect(f'file:{original}?mode=ro',uri=True);sql.write_text('\n'.join(c.iterdump()));restore_ledger(sql,dest)
   restored=sqlite3.connect(dest)
   for table in ['general_quota_debits','upload_quota_debits','composed_quota_reservations']:
    self.assertEqual(c.execute(f'select * from {table} order by rowid').fetchall(),restored.execute(f'select * from {table} order by rowid').fetchall())
   c.close();restored.close()
 def test_missing_schema_cannot_be_used_as_empty_ledger(self):
  with tempfile.TemporaryDirectory() as t:
   sql=Path(t)/'missing.sql';sql.write_text('CREATE TABLE fake(a);')
   with self.assertRaises(PermissionError):restore_ledger(sql,Path(t)/'dest')
 def test_existing_ledger_never_overwritten(self):
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'dest';dest.write_bytes(b'original')
   with self.assertRaises(PermissionError):restore_ledger(Path(t)/'absent',dest)
   self.assertEqual(dest.read_bytes(),b'original')
if __name__=='__main__':unittest.main()
