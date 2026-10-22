"""One exact owner-requested public teaching reference, no channel library or publishing."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(os.environ.get('GITHUB_WORKSPACE','.')).resolve()
OUT=ROOT/'output/research/dotti-7GvhWbXDWHQ';OUT.mkdir(parents=True,exist_ok=True)
VIDEO='7GvhWbXDWHQ';receipt={'video_id':VIDEO,'status':'STARTED','quality_authorized':False,'publication_authorized':False,'vidIQ_used':False,'external_paid_cost_usd':0}
def save(): (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
def call(args,timeout):
 result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 # No signed media URLs or credential material in durable diagnostics.
 import re
 log=re.sub(r'https?://\S+','[URL]',result.stdout+'\n'+result.stderr)
 (OUT/'process.log').write_text(log)
 if result.returncode: raise RuntimeError('PROCESS_FAILED:'+log[-2000:])
 return result
try:
 free=shutil.disk_usage(ROOT).free
 ram=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
 receipt['resource_preflight']={'free_disk_bytes':free,'available_ram_bytes':ram}
 if free<15*1024**3 or ram<2*1024**3:raise RuntimeError('RESOURCE_FLOOR_NOT_MET')
 save()
 media=OUT/'source.mp4'
 args=[sys.executable,'-m','yt_dlp','--no-playlist','--retries','0','--fragment-retries','0','--socket-timeout','12','--no-progress',
       '--max-filesize','300M','--js-runtimes','node','-f','bv*[height<=720]+ba/b[height<=720]',
       '--merge-output-format','mp4','-o',str(media),'https://www.youtube.com/watch?v='+VIDEO]
 call(args,110)
 probe=call(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(media)],10)
 value=json.loads(probe.stdout); streams=value['streams']
 if not any(s['codec_type']=='audio' for s in streams) or not any(s['codec_type']=='video' for s in streams):raise RuntimeError('AUDIO_AND_VIDEO_REQUIRED')
 if abs(float(value['format']['duration'])-1178)>3:raise RuntimeError('FULL_REFERENCE_DURATION_REQUIRED')
 receipt.update(source_sha256=hashlib.sha256(media.read_bytes()).hexdigest(),source_bytes=media.stat().st_size,streams=streams)
 (OUT/'probe.json').write_text(probe.stdout)
 frames=OUT/'frames';frames.mkdir()
 # Whole stream is decoded; this is dense sampling, not all frames visually reviewed.
 call(['ffmpeg','-nostdin','-v','error','-i',str(media),'-vf','fps=1/3','-q:v','2',str(frames/'frame-%04d.jpg')],60)
 call(['ffmpeg','-nostdin','-v','error','-i',str(media),'-vn','-c:a','libmp3lame','-b:a','96k',str(OUT/'full-audio.mp3')],35)
 receipt.update(status='FULL_AV_ACQUIRED_DENSE_SAMPLES_NOT_YET_REVIEWED',frame_step_seconds=3,frame_count=len(list(frames.glob('*.jpg'))),
                source_rights='PRIVATE_ANALYSIS_ONLY_NOT_PRODUCTION_REUSE',audiovisual_analysis_complete=False)
 save()
except Exception as exc:
 receipt.update(status='BLOCKED_AV_ACQUISITION',error=str(exc)[:2500],audiovisual_analysis_complete=False);save();print(json.dumps(receipt));sys.exit(1)
print(json.dumps({k:v for k,v in receipt.items() if k!='streams'}))
