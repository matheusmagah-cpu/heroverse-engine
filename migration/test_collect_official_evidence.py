import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from collect_official_evidence import CHANNEL,duration,stratum,exact_owned,exportable,restore,sha,report_rows,public_projection

class EvidenceBoundaryTests(unittest.TestCase):
    def test_wrong_owned_channel_cannot_admit_collection(self):
        for data in [{'items':[]},{'items':[{'id':'foreign'}]},{'items':[{'id':CHANNEL},{'id':CHANNEL}]}]:
            with self.assertRaises(PermissionError):exact_owned(data)
        self.assertEqual(exact_owned({'items':[{'id':CHANNEL}]})['id'],CHANNEL)
    def test_unconfirmed_format_is_not_a_short(self):
        for seconds in [None,0,179,180]:self.assertEqual(stratum(seconds),'FORMAT_UNCONFIRMED')
    def test_duration_strata_prevent_three_hour_and_spoken_prayer_pooling(self):
        self.assertNotEqual(stratum(duration('PT3H')),stratum(duration('PT30M')))
        self.assertEqual(duration('P1DT2H3M4S'),93784)
        self.assertIsNone(duration('unknown'))
    def test_credentials_and_signed_download_links_never_export(self):
        data={'jobs':[{'downloadUrl':'private','nextPageToken':'cursor','refresh_token':'secret','status':'ready'}],'client_secret':'secret'}
        self.assertEqual(exportable(data),{'jobs':[{'status':'ready'}]})
    def test_archive_path_escape_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'evil.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../outside','no')
            with self.assertRaises(PermissionError):restore(p,sha(p.read_bytes()),Path(t)/'out')
            self.assertFalse((Path(t)/'outside').exists())
    def test_report_column_mismatch_is_not_silently_truncated(self):
        with self.assertRaises(ValueError):report_rows({'columnHeaders':[{'name':'views'}],'rows':[[1,2]]})
    def test_missing_analytics_rows_remain_empty_not_zero(self):
        self.assertEqual(report_rows({'columnHeaders':[{'name':'views'}]}),[])
    def test_public_cohort_fields_require_observed_public_privacy(self):
        for status in ['private','unlisted',None]:
            row=public_projection({'id':'example','status':{'privacyStatus':status}})
            self.assertFalse(row['public_fields_only']);self.assertNotEqual(row['availability'],'public')
        row=public_projection({'id':'example','status':{'privacyStatus':'public'}})
        self.assertTrue(row['public_fields_only']);self.assertEqual(row['webpage_url'],'https://www.youtube.com/watch?v=example')

if __name__=='__main__':unittest.main()
