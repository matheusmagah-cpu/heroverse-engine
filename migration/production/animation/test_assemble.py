#!/usr/bin/env python3
import importlib.util,json,re,subprocess,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('assemble',Path(__file__).with_name('assemble.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)


class AssemblyTests(unittest.TestCase):
    def test_timestamp_rounding(self):
        self.assertEqual(a.timestamp(59.9999),'00:01:00,000')
        with self.assertRaises(ValueError):a.timestamp(-1)
    def test_sentence_boundary(self):
        timeline={'sentences':[{'segment':'S15','text':'A test.','start':0,'end':2}]}
        with self.assertRaises(ValueError):a.short_sentences(timeline,{'spans':[{'scene':'S15','master_start_s':.1,'master_end_s':2}],'total_s':1.9})
    def test_exact_verse_and_phrase_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'captions.ass';quote='Thou shalt love thy neighbour as thyself.'
            scenes={'scenes':[{'id':'S06','overlay':{'verse_card':quote,'reference':'Matthew 22:39 (KJV)'}}]}
            sentences=[{'segment':'S06','text':quote,'start':1.25,'end':3.5}]
            a.write_ass(path,sentences,scenes,False);text=path.read_text()
            self.assertIn(quote,text);self.assertIn('Matthew 22:39 (KJV)',text)
            for event in text.splitlines():
                if event.startswith('Dialogue:'):self.assertIn('0:00:01.25,0:00:03.50',event)
            a.write_ass(path,sentences,{'scenes':[]},True)
            for event in path.read_text().splitlines():
                if event.startswith('Dialogue:'):
                    phrase=event.rsplit('}',1)[-1];self.assertTrue(1<=len(phrase.split())<=5)
                    self.assertIn('0:00:01.25,0:00:03.50',event)
    def test_invalid_caption_markup(self):
        with self.assertRaises(ValueError):a.safe_text(r'{\pos(0,0)}inject')
    def test_real_two_second_assembly(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);work=root/'work';out=root/'out';work.mkdir();(work/'hd-frames').mkdir();(work/'vertical-frames').mkdir()
            text='Subscribe to this channel for more stories of everyday faith.'
            sentences=[{'segment':'S15','text':text,'start':0,'end':2}]
            (work/'timeline.json').write_text(json.dumps({'sentences':sentences,'voice_seconds':2}))
            scenes=root/'scenes.json';scenes.write_text(json.dumps({'scenes':[{'id':'S15','overlay':{'cta_card':text}}]}))
            timing=root/'timing.json';timing.write_text(json.dumps({'fps':24,'frames_total':48}))
            maps=root/'shorts.json';maps.write_text(json.dumps({n:{'spans':[{'scene':'S15','master_start_s':0,'master_end_s':2}],'total_s':2} for n in ['short1','short2']}))
            def run(args):a.run(['ffmpeg','-y','-nostdin','-v','error',*args])
            for name,size in [('master','1920x1080'),('short1','1080x1920'),('short2','1080x1920')]:
                folder=work/('hd-frames' if name=='master' else 'vertical-frames');pattern='%05d.png' if name=='master' else name+'-%05d.png'
                run(['-f','lavfi','-i',f'color=c=navy:s={size}:r=24:d=2','-start_number','0',str(folder/pattern)])
            run(['-f','lavfi','-i','sine=frequency=440:duration=2','-ar','48000','-ac','2',str(work/'voice.wav')])
            music=root/'music.wav';run(['-f','lavfi','-i','sine=frequency=220:duration=2','-ar','48000','-ac','2',str(music)])
            evidence=a.assemble(work,scenes,timing,maps,music,out)
            self.assertEqual(evidence['mean_separation_db'],16)
            for name in ['master','short1','short2']:
                probe=json.loads(a.run(['ffprobe','-v','error','-show_streams','-of','json',str(out/(name+'.mp4'))]).stdout)
                video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
                self.assertEqual((video['width'],video['height']),(1920,1080) if name=='master' else (1080,1920))
                self.assertEqual(video['codec_name'],'h264');self.assertEqual(video['pix_fmt'],'yuv420p');self.assertEqual(video['avg_frame_rate'],'24/1');self.assertEqual(int(video['nb_frames']),48)
                self.assertEqual((audio['codec_name'],audio['sample_rate'],audio['channels']),('aac','48000',2))
                self.assertIn(text,(out/(name+'.srt')).read_text());self.assertIn('00:00:00,000 --> 00:00:02,000',(out/(name+'.srt')).read_text())
                a.run(['ffmpeg','-v','error','-xerror','-i',str(out/(name+'.mp4')),'-f','null','-'])
                levels=a.run(['ffmpeg','-v','info','-i',str(out/(name+'.mp4')),'-af','ebur128=peak=true','-f','null','-']).stderr.rsplit('Summary:',1)[-1]
                integrated=float(re.search(r'I:\s*([-\d.]+) LUFS',levels).group(1));peak=float(re.search(r'Peak:\s*([-\d.]+) dBFS',levels).group(1))
                self.assertTrue(-16<=integrated<=-14,(name,integrated));self.assertLessEqual(peak,-1,(name,peak))


if __name__=='__main__':unittest.main(verbosity=2)
