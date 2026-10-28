#!/usr/bin/env python3
"""extract_model of second_opening_asr.py: ci/render_pilot.sh unpacks the frozen QA's ASR model with it, so a zip
with an unsafe path, a link, a duplicate or missing model file, a split directory, a wrong hash or an oversize entry
is refused before anything is written outside the destination. The module's other parts served the one-off
2026-10-15 measurement of a preserved opening (its workflow is retired); their tests left with it (slim audit
2026-10-28)."""
import hashlib
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python3 -I does not add the script's own directory
import second_opening_asr as a  # noqa: E402


class ExtractModel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, names=None):
        p = self.root/'model.zip'
        data = {name: ('fixture '+name).encode() for name in a.FILES}
        with zipfile.ZipFile(p, 'w') as z:
            for name in names or ['snapshot/'+n for n in data]:
                z.writestr(name, data.get(Path(name).name,b'bad'))
        return p, {name: hashlib.sha256(raw).hexdigest() for name,raw in data.items()}

    def test_exact_model_files_extract(self):
        p,h = self.archive(); dest=a.extract_model(p,self.root/'output',h)
        self.assertEqual(set(x.name for x in dest.iterdir()),set(a.FILES))

    def test_unsafe_paths_block(self):
        for path in ['../evil','/absolute','C:/drive','snapshot\\bad']:
            p,h=self.archive(['snapshot/'+n for n in a.FILES]+[path])
            with self.subTest(path=path),self.assertRaises(a.ScopeError):
                a.extract_model(p,self.root/('out'+str(len(path))),h)

    def test_duplicate_model_basename_block(self):
        p,h=self.archive(['snapshot/'+n for n in a.FILES]+['other/model.bin'])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_missing_model_file_block(self):
        p,h=self.archive(['snapshot/model.bin'])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_split_directory_block(self):
        p,h=self.archive(['other/'+n if n=='model.bin' else 'snapshot/'+n for n in a.FILES])
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_hash_mismatch_block(self):
        p,h=self.archive(); h['model.bin']='0'*64
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_symlink_block(self):
        p,h=self.archive()
        with zipfile.ZipFile(p,'a') as z:
            i=zipfile.ZipInfo('link'); i.create_system=3;i.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(i,'outside')
        with self.assertRaises(a.ScopeError):a.extract_model(p,self.root/'out',h)

    def test_extract_cap_block(self):
        p,h=self.archive()
        with patch.object(a,'EXTRACT_CAP',1), self.assertRaises(a.ScopeError):
            a.extract_model(p,self.root/'out',h)


if __name__ == "__main__":
    unittest.main()
