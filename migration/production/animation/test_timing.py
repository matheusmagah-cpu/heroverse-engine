#!/usr/bin/env python3
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
P = Path(__file__).parent
spec = importlib.util.spec_from_file_location('timing', P/'timing.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class TimingTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads((P/'qa_criteria_animation_v1.json').read_text())
        self.s = {'master': {'fps':24}, 'scenes':[{'id':'S01'}, {'id':'S14'}, {'id':'S15'}],
                  'shorts': {'short1':{'scenes':['S01','S15']}, 'short2':{'scenes':['S14','S15']}}}
        self.t = {'voice_seconds': 80.3,
                  'segments':[{'id':'S01','start':.3,'end':37.3}, {'id':'S14','start':38.3125,'end':74.3}, {'id':'S15','start':75.3,'end':80.3}],
                  'sentences':[{'segment':'S01','text':'First.','start':.3,'end':37.3}, {'segment':'S14','text':'Next.','start':38.3125,'end':74.3}, {'segment':'S15','text':'CTA.','start':75.3,'end':80.3}]}
    def test_contiguous_rounding(self):
        timing, _ = m.build(self.t,self.s,self.c)
        self.assertEqual(timing['fps'],24)
        self.assertEqual(timing['scenes'][0]['first_frame'],0)
        self.assertEqual(timing['scenes'][0]['end_frame'],round(38.3125*24))
        self.assertEqual(timing['frames_total'], round(80.3*24))
        for a,b in zip(timing['scenes'],timing['scenes'][1:]):
            self.assertEqual(a['end_frame'],b['first_frame'])
        self.assertEqual(timing['scenes'][-1]['end_frame'],timing['frames_total'])
    def test_sentence_boundaries(self):
        _, shorts=m.build(self.t,self.s,self.c)
        self.assertEqual(shorts['short1']['total_s'],42)
        for short in shorts.values():
            for span in short['spans']:
                rows=[x for x in self.t['sentences'] if x['segment']==span['scene']]
                self.assertIn(span['master_start_s'],[x['start'] for x in rows])
                self.assertIn(span['master_end_s'],[x['end'] for x in rows])
    def test_duration_fail_no_outputs(self):
        self.t['sentences'][0]['end']=20
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'timeline').write_text(json.dumps(self.t)); (p/'scenes').write_text(json.dumps(self.s))
            r=subprocess.run([sys.executable,'-I','-B',str(P/'timing.py'),str(p/'timeline'),str(p/'scenes'),str(p/'out')],capture_output=True,text=True)
            self.assertEqual(r.returncode,1); self.assertIn('SHORT_DURATION short1',r.stderr); self.assertFalse((p/'out/timing.json').exists())
    def test_invalid_input(self):
        for mutation in ('reverse','nan','missing'):
            t=copy.deepcopy(self.t)
            if mutation=='reverse': t['sentences'][1]['start']=0
            elif mutation=='nan': t['voice_seconds']=float('nan')
            else: t['sentences'].pop()
            with self.assertRaises(ValueError): m.build(t,self.s,self.c)
    def test_declared_s14_trim(self):
        self.t['sentences'][1]['start']=39.3
        self.t['sentences'].insert(1, {'segment':'S14','text':'Earlier.','start':38.3125,'end':39.0})
        self.c['shorts']['duration_seconds']['short2']=[39.9,40.1]
        self.s['shorts']['short2']['note']='S14 trimmed to its last sentence if needed to fit'
        _, short=m.build(self.t,self.s,self.c)
        self.assertEqual(short['short2']['total_s'],40)

if __name__=='__main__': unittest.main()
