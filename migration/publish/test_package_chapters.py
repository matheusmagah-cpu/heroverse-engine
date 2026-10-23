import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('package_pilot',Path(__file__).resolve().parents[1]/'production/package_pilot.py')
pkg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pkg)
class Tests(unittest.TestCase):
    def test_footage_credits_fit_and_keep_required_attributions(self):
        # E52: 85 one-line credits made a 7,577-character description
        cc = [{"licence": "CC BY 4.0", "credit": f'Footage: "W{i}" by A{i}, CC BY 4.0, via Wikimedia Commons (https://x/{i})',
               "source": "commons", "author": f"A{i}"} for i in range(6)]
        pix = [{"licence": "Pixabay Content License", "credit": "Footage: B via Pixabay (https://p)", "source": "pixabay",
                "author": f"B{i % 30}"} for i in range(80)]
        lines = pkg.footage_credits(cc + pix)
        self.assertTrue(all(any(c["credit"] in l for l in lines) for c in cc))
        self.assertIn("80 clips via Pixabay (Pixabay Content License)", "\n".join(lines))
        self.assertLess(len("\n".join(lines)), 1500)
        self.assertNotIn("B1", "\n".join(pkg.footage_credits(cc + pix, with_authors=False)).split("Pixabay")[-1])

    def test_greetings(self):
        for text,label in [('Good morning. Let us pray.','Good morning'),('Good evening. Tonight...','Good evening'),
                           (' good EVENING!','Good evening'),('Let us pray tonight.','Opening prayer'),
                           ('Good morningstar','Opening prayer'),('','Opening prayer')]:
            script={'segments':[{'id':'hook','text':text}]}
            self.assertEqual(pkg.chapters_from_script(script,[{'id':'hook','start':2}]),['0:00 '+label])
    def test_explicit_and_other_chapters(self):
        script={'segments':[{'id':'hook','text':'Good evening.','chapter':'Gratitude'}, {'id':'a','chapter':'Mercy'}]}
        self.assertEqual(pkg.chapters_from_script(script,[{'id':'hook','start':0},{'id':'a','start':39.9}]),['0:00 Gratitude','0:39 Mercy'])
    def test_chapters_never_show_bible_references_r15(self):
        script={'segments':[{'id':'hook','text':'Good evening.'},{'id':'s1','reference':'Psalm 23:1 (KJV)'},
                            {'id':'s2','reference':'Psalm 23:2 (KJV)','chapter':'Permission to lie down (Psalm 23:2)'},
                            {'id':'s3','chapter':'Peace in the house (1 John 4:18 (KJV))'}]}
        rows=pkg.chapters_from_script(script,[{'id':'hook','start':0},{'id':'s1','start':40},{'id':'s2','start':90},{'id':'s3','start':130}])
        self.assertEqual(rows,['0:00 Good evening','1:30 Permission to lie down','2:10 Peace in the house'])
        self.assertFalse(any(pkg.SCRIPTURE_REF.search(r) for r in pkg.chapters([{'id':'scripture-1','start':30}])))
    def test_night_chapters_speak_of_tonight(self):
        tl=[{'id':'hook','start':0},{'id':'declaration','start':700},{'id':'payoff','start':740}]
        night={'working_title':'Before You Sleep 🌙 | Night Prayer for Anxiety','segments':[{'id':'hook','text':'Before you sleep.'}]}
        morning={'working_title':'Wait on the Lord 🌅 | Morning Prayer','segments':[{'id':'hook','text':'Good morning.'}]}
        self.assertEqual(pkg.chapters_from_script(night,tl)[1:],['11:40 Declaration for tonight','12:20 One thing to carry into tomorrow'])
        self.assertEqual(pkg.chapters_from_script(morning,tl)[1:],['11:40 Declaration for today','12:20 One thing to do today'])
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
