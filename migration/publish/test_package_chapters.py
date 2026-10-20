import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('package_pilot',Path(__file__).resolve().parents[1]/'production/package_pilot.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)
class Tests(unittest.TestCase):
    def test_greetings(self):
        for text,label in [('Good morning. Let us pray.','Good morning'),('Good evening. Tonight...','Good evening'),
                           (' good EVENING!','Good evening'),('Let us pray tonight.','Opening prayer'),
                           ('Good morningstar','Opening prayer'),('','Opening prayer')]:
            script={'segments':[{'id':'hook','text':text}]}
            self.assertEqual(pkg.chapters_from_script(script,[{'id':'hook','start':2}]),['0:00 '+label])
    def test_explicit_and_other_chapters(self):
        script={'segments':[{'id':'hook','text':'Good evening.','chapter':'Gratitude'}, {'id':'a','chapter':'Mercy'}]}
        self.assertEqual(pkg.chapters_from_script(script,[{'id':'hook','start':0},{'id':'a','start':39.9}]),['0:00 Gratitude','0:39 Mercy'])
    def test_missing_hook_and_legacy(self):
        self.assertEqual(pkg.opening_chapter({'segments':[]}), 'Opening prayer')
        self.assertEqual(pkg.chapters([{'id':'hook','start':0}]),['0:00 Opening prayer'])
    def test_real_night_package_and_script_unchanged(self):
        import json,hashlib
        d=Path(__file__).resolve().parents[1]/'production/pilot-012'
        script=json.loads((d/'script.json').read_bytes());manifest=json.loads((d/'out/manifest.json').read_bytes())
        package=json.loads((d/'out/package.json').read_bytes())
        self.assertEqual(pkg.chapters_from_script(script,manifest['timeline'])[0],'0:00 Good evening')
        self.assertIn('\n0:00 Good evening\n',package['description'])
        self.assertNotIn('0:00 Good morning',package['description'])
        self.assertEqual(hashlib.sha256((d/'script.json').read_bytes()).hexdigest(),manifest['script_sha256'])
if __name__=='__main__':unittest.main()
