import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import unittest
from native_probe import OneStart, ProbeError, bounded_file, media_url, unpack_mcp, validate_preflight

class Body(io.BytesIO):
    def __init__(self,b,headers=None):
        super().__init__(b);self.headers=headers or {}

class NativeTests(unittest.TestCase):
    def test_a_start_permit_cannot_be_reused(self):
        guard=OneStart();guard.take()
        with self.assertRaisesRegex(ProbeError,'DUPLICATE_START_REFUSED'):guard.take()
        self.assertEqual(guard.attempts,1)

    def test_delivery_url_rejects_internal_source_and_credential_destinations(self):
        def resolver(host,*a,**kw):return [(2,1,6,'',('127.0.0.1',443))]
        for url in ['http://cdn.example/video','https://user:private@cdn.example/video','https://youtube-info-download-api.p.rapidapi.com/file','https://www.youtube.com/file','https://cdn.example/file']:
            with self.subTest(url=url):
                with self.assertRaises(ProbeError):media_url(url,resolver)

    def test_file_cap_handles_both_declared_and_streamed_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n,body in enumerate([Body(b'abc',{'Content-Length':'1000'}),Body(b'x'*33)]):
                with self.assertRaisesRegex(ProbeError,'DELIVERY_EXCEEDS_BYTE_BUDGET'):
                    bounded_file(body,Path(tmp)/str(n),cap=32)

    def test_json_metadata_is_not_accepted_as_an_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProbeError,'NOT_AN_MP4_FILE'):
                bounded_file(Body(b'{"download":"metadata only"}'),Path(tmp)/'file')

    def test_mcp_errors_and_unexpected_text_stop_before_media_parsing(self):
        for result in [{'isError':True,'content':[]},{'content':[{'type':'image','data':'fake'}]}]:
            with self.assertRaises(ProbeError):unpack_mcp(result)

    def test_expired_or_unbound_preflight_cannot_start_a_job(self):
        with self.assertRaisesRegex(ProbeError,'QUOTA_PREFLIGHT_NOT_ACCEPTED'):
            validate_preflight({},dt.datetime.now(dt.timezone.utc))
        with self.assertRaisesRegex(ProbeError,'QUOTA_PREFLIGHT_EXPIRED'):
            validate_preflight({'observed_at':'2020-01-01T00:00:00Z','result':{'status':'CONTRACT_AND_QUOTA_RESPONSE_RECEIVED'}},dt.datetime.now(dt.timezone.utc))

if __name__=='__main__':unittest.main()
