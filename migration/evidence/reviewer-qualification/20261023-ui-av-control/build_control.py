from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
import subprocess, wave, hashlib, json

root = Path(__file__).resolve().parent
speech = 'Seven copper lanterns beside the river.'
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'flite=text={speech}:voice=kal',
                '-ac','1','-ar','16000','-y',str(root/'speech.wav')],check=True)
with wave.open(str(root/'speech.wav')) as w:
    assert w.getsampwidth()==2 and w.getnchannels()==1 and w.getframerate()==16000
    spoken=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
audio=np.zeros(9*16000)
audio[16000:16000+len(spoken)]=spoken*0.85
for start,freq in [(6.25,440),(7.10,880)]:
    t=np.arange(4000)/16000
    tone=.20*np.sin(2*np.pi*freq*t)*np.sin(np.linspace(0,np.pi,4000))**2
    audio[round(start*16000):round(start*16000)+4000]+=tone
with wave.open(str(root/'control.wav'),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
    w.writeframes(np.round(audio*32767).astype('<i2').tobytes())
for index in range(3):
    im=Image.new('RGB',(320,180),(28,28,28));d=ImageDraw.Draw(im)
    if index==0:d.ellipse((25,55,95,125),fill=(35,135,255))
    elif index==1:d.rectangle((125,55,195,125),fill=(255,145,30))
    else:d.polygon([(245,50),(205,130),(285,130)],fill=(40,230,95))
    im.save(root/f'{index}.png')
(root/'frames.txt').write_text("file '0.png'\nduration 3\nfile '1.png'\nduration 3\nfile '2.png'\nduration 3\nfile '2.png'\n")
out=root/'media-control.mp4'
subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(root/'frames.txt'),
    '-i',str(root/'control.wav'),'-t','9','-vf','fps=12','-c:v','libx264','-preset','veryfast',
    '-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','32k','-map_metadata','-1',
    '-movflags','+faststart','-y',str(out)],check=True)
expected={'version':'ui-av-control-v1','purpose':'Blind independent modality and silence control; not a master quality review',
    'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'duration_seconds':9,
    'video':[{'start':0,'end':3,'shape':'blue circle','position':'left'},
             {'start':3,'end':6,'shape':'orange square','position':'center'},
             {'start':6,'end':9,'shape':'green triangle','position':'right'}],
    'audio':{'speech':speech,'speech_start_seconds':1,'speech_end_seconds':1+len(spoken)/16000,
             'tone_events':[{'start_seconds':6.25,'duration_seconds':.25,'frequency_hz':440},
                            {'start_seconds':7.10,'duration_seconds':.25,'frequency_hz':880}],
             'music':False,'speech_after_6_seconds':False},
    'caption_text':None,'expected_answer_was_not_sent_to_model':True,
    'acceptance':'Exact sentence, all three shapes/colors/positions in order, two later tones, no invented later speech or music; rounded timing allowed up to 1 s.'}
(root/'expected.json').write_text(json.dumps(expected,indent=2)+'\n')
print(json.dumps({'sha256':expected['sha256'],'bytes':expected['bytes'],'duration_seconds':9}))
