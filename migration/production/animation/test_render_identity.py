#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
P=Path(__file__).parent
spec=importlib.util.spec_from_file_location('identity',P/'render_identity.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class IdentityTests(unittest.TestCase):
    def test_exact_canonical(self):
        self.assertEqual(m.render_id({'z':2,'a':'é'}),hashlib.sha256(json.dumps({'z':2,'a':'é'},sort_keys=True,separators=(',',':')).encode()).hexdigest())
        self.assertEqual(m.render_id({'z':2,'a':1}),m.render_id({'a':1,'z':2}))
    def test_file_fields_and_each_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'bundle').mkdir(); (p/'bundle/a.py').write_text('original')
            for name in ('script','scenes','voice','music','srt'): (p/name).write_text(name)
            args=argparse.Namespace(**{n:str(p/n) for n in ('script','scenes','voice','music','srt','bundle')},criteria=str(P/'qa_criteria_animation_v1.json'),blender_version='4.3.2',engine='BLENDER_EEVEE_NEXT',samples=16,fps=24,resolution=[1920,1080])
            fields=m.build_fields(args); original=m.render_id(fields)
            for key in fields:
                changed=dict(fields); changed[key]='changed'; self.assertNotEqual(m.render_id(changed),original,key)
            (p/'bundle/a.py').write_text('changed'); self.assertNotEqual(m.render_id(m.build_fields(args)),original)
            (p/'bundle/link').symlink_to(p/'voice')
            with self.assertRaisesRegex(ValueError,'SYMLINK'): m.build_fields(args)
    def test_missing_input(self):
        with self.assertRaises(FileNotFoundError): m.file_sha256('/nonexistent/render-identity-input')
if __name__=='__main__': unittest.main()
