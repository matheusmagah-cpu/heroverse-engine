"""Isolated cloud voice/render diagnostic; never grants production authority."""
import hashlib, importlib.metadata, json, os, shutil, sys, tempfile, time, urllib.request, wave
from pathlib import Path
from verify_public_voice_asset import ASSETS
from linux_bounded_worker import run_bounded

def preflight():
    observations=[]
    for _ in range(3):
        mem=dict((k,int(v.split()[0])*1024) for k,v in
                 (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()))
        item={'available_memory':mem['MemAvailable'],'disk_free':shutil.disk_usage('.').free}
        observations.append(item)
        if item['available_memory']<2*1024**3 or item['disk_free']<15*1024**3:
            raise RuntimeError('resource preflight below preserved floor: '+json.dumps(item))
        time.sleep(1)
    return observations

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(1024**2): h.update(block)
    return h.hexdigest()

def synth(root):
    import numpy as np
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    options=ort.SessionOptions()
    options.intra_op_num_threads=2
    options.inter_op_num_threads=1
    session=ort.InferenceSession(str(root/'kokoro-v1.0.fp16.onnx'),
                sess_options=options,providers=['CPUExecutionProvider'])
    # Kokoro 0.4.9 accepts an existing session through from_session.
    kokoro=Kokoro.from_session(session,str(root/'voices-v1.0.bin'))
    samples, rate=kokoro.create('This is an isolated technical test of the HeroVerse cloud voice.',
                voice='af_sarah',speed=1.0,lang='en-us')
    samples=np.asarray(samples,dtype=np.float32)
    if samples.ndim!=1 or not np.isfinite(samples).all():raise RuntimeError('invalid samples')
    duration=len(samples)/rate
    rms=float(np.sqrt(np.mean(samples*samples)))
    if rate!=24000 or not 1<duration<30 or rms<0.001:raise RuntimeError('invalid audio properties')
    pcm=(np.clip(samples,-1,1)*32767).astype('<i2')
    with wave.open(str(root/'diagnostic.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
    print(json.dumps({'status':'VOICE_INFERENCE_PASS','duration':duration,'sample_rate':rate,
        'rms':rms,'samples':len(samples),'wav_sha256':digest(root/'diagnostic.wav'),
        'versions':{n:importlib.metadata.version(n) for n in
                    ['kokoro-onnx','onnxruntime','numpy','espeakng-loader','phonemizer-fork']}}),flush=True)

def main():
    pre=preflight()
    results=[]
    with tempfile.TemporaryDirectory(prefix='heroverse-cloud-diagnostic-') as tmp:
        root=Path(tmp)
        for a in ASSETS:
            size=0;h=hashlib.sha256()
            with urllib.request.urlopen(a['url'],timeout=30) as response,(root/a['name']).open('xb') as out:
                while block:=response.read(1024**2):
                    size+=len(block)
                    if size>a['size']:raise RuntimeError('asset exceeds pinned size')
                    h.update(block);out.write(block)
            if size!=a['size'] or h.hexdigest()!=a['sha256']:raise RuntimeError('asset identity mismatch')
            results.append({'name':a['name'],'bytes':size,'sha256':h.hexdigest()})
        env={'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}
        os.environ.update(env)
        voice=run_bounded([sys.executable,str(Path(__file__).resolve()),'synth',str(root)],
                    cwd=Path.cwd(),timeout_seconds=120,memory_bytes=3*1024**3,max_log_bytes=1024**2)
        print(json.dumps({'voice_worker':voice}),flush=True)
        if voice['status']!='SUCCEEDED':raise RuntimeError('voice worker failed')
        voice_receipt=json.loads(next(line for line in reversed(voice['stdout'].splitlines()) if line.startswith('{') and 'VOICE_INFERENCE_PASS' in line))
        ffmpeg=shutil.which('ffmpeg'); ffprobe=shutil.which('ffprobe')
        if not ffmpeg or not ffprobe:raise RuntimeError('video tools missing')
        render=run_bounded([ffmpeg,'-hide_banner','-loglevel','error','-nostdin',
           '-f','lavfi','-i','color=c=black:s=640x360:r=25',
           '-i',str(root/'diagnostic.wav'),'-shortest','-threads','2',
           '-c:v','libx264','-preset','ultrafast','-c:a','aac',str(root/'diagnostic.mp4')],
           cwd=Path.cwd(),timeout_seconds=60,memory_bytes=512*1024**2,max_log_bytes=1024**2)
        if render['status']!='SUCCEEDED':raise RuntimeError('render failed: '+json.dumps(render))
        decode=run_bounded([ffmpeg,'-hide_banner','-loglevel','error','-nostdin',
           '-i',str(root/'diagnostic.mp4'),'-f','null','-'],
           cwd=Path.cwd(),timeout_seconds=60,memory_bytes=512*1024**2,max_log_bytes=1024**2)
        if decode['status']!='SUCCEEDED':raise RuntimeError('decode failed: '+json.dumps(decode))
        probe=run_bounded([ffprobe,'-v','error','-show_streams','-show_format','-of','json',
              str(root/'diagnostic.mp4')],cwd=Path.cwd(),timeout_seconds=20,
              memory_bytes=128*1024**2,max_log_bytes=1024**2)
        if probe['status']!='SUCCEEDED':raise RuntimeError('probe failed')
        props=json.loads(probe['stdout'])
        kinds={s['codec_type'] for s in props['streams']}
        if kinds!={'audio','video'} or abs(float(props['format']['duration'])-voice_receipt['duration'])>0.5:
            raise RuntimeError('render stream/duration mismatch')
        receipt={'status':'CLOUD_VOICE_RENDER_DIAGNOSTIC_PASS','assets':results,'preflight':pre,
          'voice':voice_receipt,'render_sha256':digest(root/'diagnostic.mp4'),
          'render':render,'decode':decode,'windows_contact':False,
          'full_phase_pipeline_validated':False,'perceptual_quality_approved':False,
          'production_ready':False,'publication_performed':False,'release_authority':False}
        path=Path('migration/diagnostics/cloud-voice-render.json');path.parent.mkdir(exist_ok=True)
        with path.open('x') as out:json.dump(receipt,out,indent=2)
        print(json.dumps(receipt),flush=True)
if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='synth':synth(Path(sys.argv[2]))
    else:main()
