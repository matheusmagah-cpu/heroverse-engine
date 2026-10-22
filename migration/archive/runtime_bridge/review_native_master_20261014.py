"""Inspect every decoded native YUV frame of the pinned static delivery.

Exact byte equality reuses an already computed SHA, never approximate image
similarity. This proves frame population/content identity, not release approval.
"""
import hashlib,json,subprocess,time
from pathlib import Path

VIDEO=Path('output/HeroVerse_Rest_Corrected_3h_Metricool.mp4')
OUT=Path('production-review');OUT.mkdir(exist_ok=True)
EXPECTED_SHA='55c2a047e107ce42469261978ab34353e58622ec436e40876f6a8fc71c882c46'
EXPECTED_BYTES=391733890
EXPECTED_FRAMES=324000

def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def run():
    if VIDEO.stat().st_size!=EXPECTED_BYTES or file_sha(VIDEO)!=EXPECTED_SHA:
        raise PermissionError('CANONICAL_MASTER_IDENTITY_REQUIRED')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(VIDEO)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    if (video['width'],video['height'],video['pix_fmt'],video['r_frame_rate'])!=(1920,1080,'yuv420p','30/1'):
        raise PermissionError('EXACT_NATIVE_FRAME_CONTRACT_REQUIRED')
    if int(video['nb_frames'])!=EXPECTED_FRAMES or float(probe['format']['duration'])!=10800:
        raise PermissionError('EXPECTED_POPULATION_CHANGED')
    frame_size=1920*1080*3//2
    command=['ffmpeg','-v','error','-threads','4','-i',str(VIDEO),'-map','0:v:0','-an',
        '-pix_fmt','yuv420p','-fps_mode','passthrough','-f','rawvideo','-']
    started=time.monotonic();last_update=started;count=0;first=None;last=None
    first_digest=None;last_digest=None;chain=hashlib.sha256();distinct={}
    errors=OUT/'native-decode.stderr.txt'
    with errors.open('wb') as log:
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=log)
        try:
            while True:
                frame=proc.stdout.read(frame_size)
                if not frame:break
                if len(frame)!=frame_size:raise PermissionError('INCOMPLETE_NATIVE_FRAME')
                if first is None:
                    first=frame;first_digest=hashlib.sha256(frame).digest()
                if frame==first:digest=first_digest
                elif last is not None and frame==last:digest=last_digest
                else:digest=hashlib.sha256(frame).digest()
                key=digest.hex()
                if key not in distinct:
                    item={'native_yuv_sha256':key,'first_frame_index':count,'first_timestamp_seconds':count/30,'frame_count':0}
                    if len(distinct)<16:
                        name='native-distinct-'+str(len(distinct)).zfill(3)+'.yuv'
                        (OUT/name).write_bytes(frame);item['native_yuv_path']=str(OUT/name)
                    distinct[key]=item
                distinct[key]['frame_count']+=1
                chain.update(digest);count+=1;last=frame;last_digest=digest
                if count>EXPECTED_FRAMES:raise PermissionError('EXTRA_NATIVE_FRAMES')
                now=time.monotonic()
                if now-last_update>=20:
                    progress={'frames':count,'expected_frames':EXPECTED_FRAMES,'percent':round(100*count/EXPECTED_FRAMES,2),
                        'unique_frames':len(distinct),'elapsed_seconds':round(now-started,2)}
                    (OUT/'progress.json').write_text(json.dumps(progress)+'\n');print(json.dumps(progress),flush=True);last_update=now
                if now-started>10800:raise TimeoutError('NATIVE_REVIEW_MEDIA_TIME_BUDGET_EXCEEDED')
            code=proc.wait(timeout=30)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    if code!=0 or count!=EXPECTED_FRAMES or errors.stat().st_size:
        raise PermissionError('FULL_NATIVE_POPULATION_OR_DECODE_FAILED')
    if file_sha(VIDEO)!=EXPECTED_SHA:raise PermissionError('MASTER_CHANGED_DURING_REVIEW')
    report={'status':'ALL_NATIVE_MASTER_FRAMES_DECODED_AND_INVENTORIED',
        'master_sha256':EXPECTED_SHA,'master_bytes':EXPECTED_BYTES,'native_width':1920,'native_height':1080,
        'native_pixel_format':'yuv420p','fps':30,'expected_frames':EXPECTED_FRAMES,'decoded_frames':count,
        'distinct_frame_count':len(distinct),'distinct_frames':list(distinct.values()),
        'ordered_native_frame_sha256_chain':chain.hexdigest(),'decode_errors':0,
        'comparison':'EXACT_FULL_NATIVE_FRAME_BYTES_NO_SCALING_NO_SAMPLING',
        'elapsed_seconds':round(time.monotonic()-started,3),'visual_inspection_status':'PENDING_DISTINCT_FRAME_REVIEW',
        'reference_video_frames_reviewed':False,'final_production_approved':False,'publication_authorized':False}
    (OUT/'native-frame-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='distinct_frames'}),flush=True)

if __name__=='__main__':run()
