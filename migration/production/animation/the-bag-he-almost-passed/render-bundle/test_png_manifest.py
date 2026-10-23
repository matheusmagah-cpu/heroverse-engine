#!/usr/bin/env python3
import importlib.util,struct,unittest,zlib
from pathlib import Path
spec=importlib.util.spec_from_file_location('png_manifest',Path(__file__).with_name('png_manifest.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)


class CanonicalTests(unittest.TestCase):
    def test_metadata_independent_and_pixels_preserved(self):
        pixels=chunk(b'IDAT',b'pixel-compression-bytes');end=chunk(b'IEND',b'');header=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
        left=header+chunk(b'tEXt',b'Date\0Monday')+pixels+end;right=header+chunk(b'tEXt',b'Date\0Tuesday')+pixels+end
        self.assertEqual(p.canonical_png(left),p.canonical_png(right));self.assertEqual(p.canonical_png(left),header+pixels+end)
        self.assertEqual(p.canonical_png(p.canonical_png(left)),p.canonical_png(left))
    def test_corruption_fails(self):
        for content in [b'garbage',b'\x89PNG\r\n\x1a\n',b'\x89PNG\r\n\x1a\n'+chunk(b'IEND',b'')[:-1]]:
            with self.assertRaises(ValueError):p.canonical_png(content)


if __name__=='__main__':unittest.main(verbosity=2)
