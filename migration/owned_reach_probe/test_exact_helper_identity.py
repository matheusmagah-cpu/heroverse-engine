import hashlib
import os
import unittest
from pathlib import Path
import run_existing_reach_probe as wrapper

class Tests(unittest.TestCase):
    def test_pins_match_exact_repository_bytes_not_staged_newlines(self):
        root=Path(os.environ.get('HERO_PROBE_HELPER_ROOT','.'))
        blobs={'oauth_health.py':'757c12001b4ea6336d1a3f958cd33dd339024b55','verify_worker_oauth.py':'6be04fedb6204b8e4bd3cc623494970ee93c0a06'}
        for name,expected in wrapper.HELPER_HASHES.items():
            raw=(root/'migration'/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),expected)
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),blobs[name])
    def test_extra_newline_and_modified_content_are_not_accepted(self):
        root=Path(os.environ.get('HERO_PROBE_HELPER_ROOT','.'))
        for name,expected in wrapper.HELPER_HASHES.items():
            raw=(root/'migration'/name).read_bytes()
            for altered in [raw+b'\n',raw+b' ',raw.replace(b'\n',b'\r\n')]:
                self.assertNotEqual(hashlib.sha256(altered).hexdigest(),expected)

if __name__=='__main__':unittest.main(verbosity=2)
