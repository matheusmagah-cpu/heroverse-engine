"""One bounded public-native acquisition on the existing Linux observer host."""
import hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from durable_evidence_checkpoint import CLAIM
from observe_public_av import ExistingObserverLedger

VIDEO='j2rk8ycXe3c';CHANNEL='UCTdc_zl40D9wa0_LH9yaGZA'
OUT=Path('cloud-evidence/native-market-probe')

def safe_code(log):
    value=log.lower()
    if 'sign in' in value or 'not a bot' in value:return 'PUBLIC_SOURCE_SIGN_IN_WALL'
    if '403' in value or 'forbidden' in value:return 'PUBLIC_MEDIA_ACCESS_DENIED'
    if 'requested format' in value:return 'PUBLIC_FORMAT_UNAVAILABLE'
    if 'no m3u' in value:return 'PUBLIC_MEDIA_MANIFEST_INVALID'
    return 'PUBLIC_MEDIA_TRANSFER_UNAVAILABLE'

def main():
    run=os.environ['GITHUB_RUN_ID']
    if (os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine'
            or json.loads(CLAIM.read_bytes()).get('run_id')!=run):
        raise PermissionError('EXISTING_EXACT_OBSERVER_CLAIM_REQUIRED')
    OUT.mkdir(parents=True,exist_ok=False)
    work=Path(os.environ['RUNNER_TEMP'])/('native-market-'+run);work.mkdir()
    receipt={'video_id':VIDEO,'channel_id':CHANNEL,'status':'STARTED',
        'method':'NATIVE_PUBLIC_TRANSFER_THROUGH_LINUX_RUNNER_HTTP_DOWNLOADER',
        'attempts':1,'cookies_used':False,'credentials_used':False,'proxy_fallback_used':False,
        'signed_urls_persisted':False,'source_rights':'UNKNOWN_PRIVATE_ANALYSIS_ONLY',
        'native_av_acquired':False,'quality_authorized':False,'publication_authorized':False}
    try:
        if shutil.disk_usage(work).free<3*1024**3:raise PermissionError('NATIVE_ACQUISITION_DISK_FLOOR')
        source=work/'source.mp4'
        args=[sys.executable,'-m','yt_dlp','--no-playlist','--retries','0','--fragment-retries','0',
            '--extractor-retries','0','--socket-timeout','10','--no-progress','--js-runtimes','node',
            '--downloader','native','--max-filesize','900M','-f','134+139','--merge-output-format','mp4',
            '-o',str(source),'https://www.youtube.com/watch?v='+VIDEO]
        p=subprocess.run(args,capture_output=True,text=True,timeout=180)
        if p.returncode or not source.is_file():
            receipt.update(status='BLOCKED_NATIVE_ACQUISITION',failure_code=safe_code(p.stderr+'\n'+p.stdout))
        else:
            probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(source)],
                capture_output=True,text=True,timeout=20,check=True)
            data=json.loads(probe.stdout);duration=float(data['format']['duration'])
            streams=data['streams']
            if not {'audio','video'}<={s['codec_type'] for s in streams} or abs(duration-12708)>3:
                raise PermissionError('FULL_NATIVE_AUDIOVISUAL_IDENTITY_REQUIRED')
            # Actual media bytes and codec validation required; HTML masquerading as 206 cannot pass.
            clip=OUT/'opening-40s.mp4'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(source),'-t','40','-c:v','libx264',
                '-preset','veryfast','-crf','22','-c:a','aac','-b:a','96k',str(clip)],
                capture_output=True,text=True,timeout=60,check=True)
            frames=OUT/'frames';frames.mkdir()
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(clip),'-vf','fps=1',
                '-q:v','2',str(frames/'frame-%03d.jpg')],capture_output=True,text=True,timeout=30,check=True)
            receipt.update(status='FULL_NATIVE_AV_ACQUIRED_OPENING_FRAMES_NOT_YET_REVIEWED',native_av_acquired=True,
                full_source_duration_seconds=duration,full_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                full_source_bytes=source.stat().st_size,clip_duration_seconds=40,
                clip_sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),clip_bytes=clip.stat().st_size,
                frame_count=len(list(frames.glob('*.jpg'))),frame_sample_fps=1,
                streams=[{k:s.get(k) for k in ('codec_type','codec_name','width','height','r_frame_rate','sample_rate','channels')}
                    for s in streams],full_source_uploaded=False)
    except subprocess.TimeoutExpired:receipt.update(status='BLOCKED_NATIVE_ACQUISITION',failure_code='NATIVE_TRANSFER_TIME_BOUND')
    except Exception as e:receipt.update(status='BLOCKED_NATIVE_ACQUISITION',failure_code=str(e) if
        isinstance(e,PermissionError) else 'NATIVE_MEDIA_VALIDATION_FAILED_REDACTED')
    raw=json.dumps(receipt,sort_keys=True)+'\n'
    (OUT/'receipt.json').write_text(raw)
    (Path('migration/evidence')/('native-market-probe-'+run+'.json')).write_text(raw)
    ledger=ExistingObserverLedger('cloud-evidence/quota-ledger.sqlite3',run)
    ledger.checkpoint('Checkpoint exact public native acquisition diagnostic without production approval')
    print(json.dumps(receipt))
    return 0 if receipt['native_av_acquired'] else 2

if __name__=='__main__':sys.exit(main())
