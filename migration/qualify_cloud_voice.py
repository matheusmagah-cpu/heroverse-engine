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
    import soundfile as sf
    sys.path.insert(0,str(root/'source'/'project'))
    from hero_engine.voice_phase5 import build_local_voice, synthesize_voice_sample, KokoroFloatSpeed
    options=ort.SessionOptions()
    options.intra_op_num_threads=2
    options.inter_op_num_threads=1
    def factory(model, voices, *, espeak_config):
        session=ort.InferenceSession(model,sess_options=options,providers=['CPUExecutionProvider'])
        return KokoroFloatSpeed.from_session(session,voices,espeak_config=espeak_config)
    engine=build_local_voice(root,engine_factory=factory)
    native=synthesize_voice_sample(engine,text='This is an isolated technical test of the HeroVerse cloud voice.',
                output_path=root/'diagnostic.wav',voice_id='am_michael',speed=1.0)
    samples,rate=sf.read(root/'diagnostic.wav',dtype='float32')
    if samples.ndim!=1 or not np.isfinite(samples).all():raise RuntimeError('invalid samples')
    duration=len(samples)/rate; rms=float(np.sqrt(np.mean(samples*samples)))
    if rate!=24000 or not 1<duration<30 or rms<0.001:raise RuntimeError('invalid audio properties')
    if native['clipping']:raise RuntimeError('voice clipping')
    print(json.dumps({'status':'ORIGINAL_PHASE5_VOICE_INFERENCE_PASS','duration':duration,
        'sample_rate':rate,'rms':rms,'samples':len(samples),'wav_sha256':digest(root/'diagnostic.wav'),
        'source_adapter':'hero_engine.voice_phase5.KokoroFloatSpeed',
        'source_module_sha256':digest(root/'source'/'project'/'hero_engine'/'voice_phase5.py'),
        'native_receipt':native,'espeak_binding':engine._heroverse_espeak_binding.identity(),
        'versions':{n:importlib.metadata.version(n) for n in
                    ['kokoro-onnx','onnxruntime','numpy','espeakng-loader','phonemizer-fork','soundfile']}}),flush=True)

def main():
    pre=preflight()
    results=[]
    with tempfile.TemporaryDirectory(prefix='heroverse-cloud-diagnostic-') as tmp:
        root=Path(tmp)
        from pathlib import PurePosixPath
        import zipfile
        archive=Path('HeroVerse_Linux_Source_Ready_20261013_v2.zip')
        if digest(archive)!='fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10':
            raise RuntimeError('source archive identity mismatch')
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                path=PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts or ((item.external_attr>>16)&0o170000)==0o120000:
                    raise RuntimeError('unsafe source member')
            z.extractall(root/'source')
        report=json.loads((root/'source'/'SOURCE_TRANSFER_REPORT.json').read_text())
        for item in report['files']:
            path=root/'source'/'project'/item['path']
            if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
                raise RuntimeError('source manifest mismatch')
        model_dir=root/'models'/'kokoro';model_dir.mkdir(parents=True)
        for a in ASSETS:
            size=0;h=hashlib.sha256()
            with urllib.request.urlopen(a['url'],timeout=30) as response,(model_dir/a['name']).open('xb') as out:
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
        voice_receipt=json.loads(next(line for line in reversed(voice['stdout'].splitlines()) if line.startswith('{') and 'ORIGINAL_PHASE5_VOICE_INFERENCE_PASS' in line))
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
        receipt={'status':'ORIGINAL_PHASE5_CLOUD_VOICE_RENDER_PASS','assets':results,'preflight':pre,
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
