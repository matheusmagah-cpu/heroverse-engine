#!/usr/bin/env python3
"""Two-second media tests exercise meters, NOT full production qualification.
The frozen 151–153 second master requirement necessarily fails this fixture.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
P=Path(__file__).parent
spec=importlib.util.spec_from_file_location('qa',P/'qa_animation.py'); q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)

class QATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.d=Path(cls.tmp.name)
        cls.c=json.loads((P/'qa_criteria_animation_v1.json').read_text())
        args=['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','testsrc2=size=1920x1080:rate=24:duration=2','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2','-vf','format=yuv420p','-af','aformat=channel_layouts=stereo,loudnorm=I=-15:TP=-1:LRA=7','-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-ar','48000','-ac','2','-t','2',str(cls.d/'master.mp4')]
        subprocess.run(args,check=True,capture_output=True)
        cls.report=q.evaluate(cls.d,cls.c)
        cls.rows={r['id']:r for r in cls.report['rows']}
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def test_real_probe_decode_resolution_pass(self):
        for key in ('width','height','codec','pix_fmt','fps','audio','full_decode_without_errors'):
            self.assertEqual(self.rows['master.'+key]['status'],'PASS',key)
        self.assertEqual(q.probe(self.d/'master.mp4')['streams'][0]['width'],1920)
    def test_resolution_fail_against_measured_clip(self):
        c=copy.deepcopy(self.c); c['master']['width']=1280
        # Meter unit test with a deliberately different expected value in memory;
        # no criteria file changed, no CLI qualification with altered criteria.
        report=q.evaluate(self.d,c)
        self.assertEqual(next(r for r in report['rows'] if r['id']=='master.width')['status'],'FAIL')
    def test_duration_fails_frozen_production_limits(self):
        self.assertEqual(self.rows['master.duration_seconds']['status'],'FAIL')
        self.assertEqual(self.report['status'],'FAIL')
        self.assertTrue(1.99<=self.rows['master.duration_seconds']['value']<=2.01)
        self.assertEqual(self.rows['master.duration_seconds']['limit'],[151.0,153.0])
    def test_real_loudness_measurement(self):
        values=q.loudness(self.d/'master.mp4')
        self.assertIsNotNone(values['integrated_lufs']); self.assertIsNotNone(values['true_peak_dbtp'])
        self.assertTrue(-16<=values['integrated_lufs']<=-14,values)
        self.assertLessEqual(values['true_peak_dbtp'],-1)
        # A clearly incompatible loudness threshold must fail the same meter.
        c=copy.deepcopy(self.c); c['audio']['integrated_lufs']=[-5,-4]
        r=q.evaluate(self.d,c)
        self.assertEqual(next(x for x in r['rows'] if x['id']=='master.integrated_lufs')['status'],'FAIL')
    def test_fluidity_pass_duplicate_fail_missing_fail(self):
        frames={str(i):hashlib.sha256(str(i).encode()).hexdigest() for i in range(48)}
        good=q.frame_metrics(frames,24,48); self.assertEqual(good['ratio'],1); self.assertEqual(good['unique_fps'],24)
        frames['2']=frames['1']; frames['3']=frames['1']
        self.assertLess(q.frame_metrics(frames,24,48)['ratio'],.97)
        held=q.frame_metrics(frames,24,48,[(2,4)]); self.assertEqual(held['ratio'],1)
        frames.pop('10'); self.assertFalse(q.frame_metrics(frames,24,48)['contiguous'])
    def test_srt_exact_text_offsets_pass_fail(self):
        sentences=[{'start':0,'end':1,'text':'First sentence.'},{'start':1,'end':2,'text':self.c['cta']['text']}]
        cues=copy.deepcopy(sentences); good=q.subtitle_metrics(cues,sentences)
        self.assertTrue(good['text']); self.assertEqual(good['start'],0); self.assertEqual(good['end'],0)
        cues[0]['text']='Wrong.'; cues[0]['start']=.2; cues[0]['end']=1.3
        bad=q.subtitle_metrics(cues,sentences); self.assertFalse(bad['text']); self.assertGreater(bad['start'],.15); self.assertGreater(bad['end'],.25)
    def test_scripture_and_cta_exact_text_not_substrings(self):
        # Unit checks for exact text; these do NOT prove narration or card pixels.
        for key in ('scripture','cta'):
            text=self.c[key]['quote' if key=='scripture' else 'text']
            target=[{'text':text,'start':0,'end':2}]
            self.assertTrue(q.subtitle_metrics(copy.deepcopy(target),target)['text'])
            bad=copy.deepcopy(target); bad[0]['text']+=' extra'
            self.assertFalse(q.subtitle_metrics(bad,target)['text'])
        self.assertEqual(self.rows['scripture.card_text_exactly']['status'],'UNKNOWN')
        self.assertEqual(self.rows['cta.on_screen_exactly_in_master_and_each_short']['status'],'UNKNOWN')
    def test_missing_provenance_stays_unknown(self):
        for key in ('master.native_render','audio.voice_model_hash_pinned','audio.wer_vs_script_max','rights.no_third_party_footage_or_characters','perceptual_review_required_before_approval'):
            self.assertEqual(self.rows[key]['status'],'UNKNOWN',key)
    def test_hash_guard_no_report_on_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'criteria').write_text('{}')
            r=subprocess.run([sys.executable,'-I','-B',str(P/'qa_animation.py'),str(p/'out'),str(p/'criteria')],capture_output=True,text=True)
            self.assertEqual(r.returncode,2); self.assertIn('CRITERIA_SHA_MISMATCH',r.stderr); self.assertFalse((p/'out/qa.json').exists())
    def test_cli_frozen_criteria_writes_fail_report(self):
        r=subprocess.run([sys.executable,'-I','-B',str(P/'qa_animation.py'),str(self.d),str(P/'qa_criteria_animation_v1.json')],capture_output=True,text=True)
        self.assertEqual(r.returncode,1)
        data=json.loads((self.d/'qa.json').read_text()); self.assertEqual(data['status'],'FAIL'); self.assertEqual(data['criteria_sha256'],q.FROZEN_SHA256)
        self.assertTrue(all(row['status'] in ('PASS','FAIL','UNKNOWN') for row in data['rows']))
    def test_duplicate_json_frame_index_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'frames.json').write_text('{"0":"'+'a'*64+'","0":"'+'b'*64+'"}')
            report=q.evaluate(p,self.c)
            row=next(r for r in report['rows'] if r['id']=='continuity.frame_set_contiguous_no_missing_no_duplicate_index')
            self.assertEqual(row['status'],'FAIL')
    def test_short_boundaries(self):
        t={'sentences':[{'segment':'S01','start':2,'end':3,'text':'First.'},{'segment':'S15','start':8,'end':9,'text':'CTA.'}]}
        short={'spans':[{'scene':'S01','master_start_s':2,'master_end_s':3},{'scene':'S15','master_start_s':8,'master_end_s':9}],'total_s':2}
        result=q.expected_short(t,short); self.assertEqual(result[-1]['end'],2)
        short['spans'][0]['master_start_s']=2.1
        with self.assertRaises(ValueError): q.expected_short(t,short)

if __name__=='__main__': unittest.main()
