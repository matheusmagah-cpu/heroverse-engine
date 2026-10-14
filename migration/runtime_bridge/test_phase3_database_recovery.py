import tempfile,unittest
from pathlib import Path
from recover_phase3_database_evidence import recover
class HistoricalRecoveryTests(unittest.TestCase):
    def test_changed_archive_cannot_supply_historical_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'changed.zip';source.write_bytes(b'changed')
            with self.assertRaises(PermissionError):recover(source,Path(tmp)/'out')
            self.assertFalse((Path(tmp)/'out').exists())
    def test_real_frozen_catalog_rows_and_payload_hashes(self):
        source=Path('HeroVerse_operational_snapshot.zip')
        if not source.exists():source=Path('oauth-inventory/HeroVerse_operational_snapshot.zip')
        with tempfile.TemporaryDirectory() as tmp:
            result=recover(source,Path(tmp)/'out')
            self.assertEqual(result['outputs']['observatory_public_snapshots']['row_count'],130)
            self.assertEqual(result['outputs']['observatory_coverage']['row_count'],143)
            self.assertEqual(result['outputs']['observatory_cohorts']['row_count'],5)
            self.assertEqual(result['payload_hashes_verified'],260)
            self.assertFalse(result['canonical_channel_model_recovered'])
if __name__=='__main__':unittest.main()
