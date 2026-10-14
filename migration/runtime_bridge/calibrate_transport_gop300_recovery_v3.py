"""Bounded independent controls for the existing GOP300 transport derivative.

Never rerenders the master. A disjoint holdout failure is retained, never tuned.
This is an instrument qualification, not editorial/native release approval.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')

def read(path):
    return json.loads(Path(path).read_text())

def bind(path, root):
    return {'path':str(Path(path).relative_to(root)), 'sha256':sha(path),
            'bytes':Path(path).stat().st_size}

def domain(layout):
    return {key:layout[key] for key in ('font','palette','canvas')} | {
        'font_size':layout['texts'][0]['font_size'], 'text_color':layout['texts'][0]['color']}

def measure(reference, decoded, bounds):
    from hero_engine.phase6_visual_metrics import spatial_measurements, colour_measurements
    left, top, right, bottom=bounds
    region=(slice(max(0,top-6),min(1080,bottom+6)),slice(max(0,left-6),min(1920,right+6)))
    text=spatial_measurements(reference[region],decoded[region])
    colour=colour_measurements(reference,decoded)
    return {'text_error':1-text['minimum_local_ssim'],
            'colour_error':colour['maximum_delta_e']}

def calibrate(rows, candidate_hash):
    from hero_engine.phase6_visual_metrics import calibrate_error_limit
    return {metric:calibrate_error_limit(candidate_hash=candidate_hash,**{
        group:[{'source_sha256':row['encoded_sha256'],'value':row['measurements'][metric]}
               for row in rows if row['group']==group]
        for group in ('positive','negative','holdout_positive','holdout_negative')})
        for metric in ('text_error','colour_error')}

def reopen(directory, binding_sha, native_root):
    """Zero subprocess/provider reopening; recompute numeric metrics and holdout."""
    import numpy as np
    from PIL import Image
    directory=Path(directory).resolve()
    anchor=directory/'bindings.json'
    if sha(anchor)!=binding_sha:raise PermissionError('EXTERNAL_BINDING_MISMATCH')
    bundle=read(anchor)
    for item in bundle['artifacts']:
        target=(directory/item['path']).resolve()
        if (not target.is_relative_to(directory) or target.stat().st_size!=item['bytes']
                or sha(target)!=item['sha256']):raise PermissionError('ARTIFACT_CHANGED')
    for name, expected in bundle['implementations'].items():
        if sha(Path(native_root)/name)!=expected:raise PermissionError('IMPLEMENTATION_CHANGED')
    result=read(directory/'result.json'); policy=read(directory/'policy.json')
    if len(result['rows'])!=8:raise PermissionError('CONTROL_POPULATION_CHANGED')
    groups=[x['group'] for x in result['rows']]
    if [groups.count(g) for g in ('positive','negative','holdout_positive','holdout_negative')]!=[3,2,1,2]:
        raise PermissionError('CONTROL_SPLITS_CHANGED')
    for index,row in enumerate(result['rows']):
        if row['group']!=policy['controls'][index]['group'] or row['title']!=policy['controls'][index]['title']:
            raise PermissionError('PREREGISTERED_CONTROLS_CHANGED')
        reference=np.asarray(Image.open(directory/row['reference']).convert('RGB'))
        observed=[]
        for item in row['distinct_frames']:
            decoded=np.asarray(Image.open(directory/item['path']).convert('RGB'))
            if hashlib.sha256(decoded.tobytes()).hexdigest()!=item['rgb_sha256']:
                raise PermissionError('DECODED_PIXEL_IDENTITY_CHANGED')
            observed.append(measure(reference,decoded,row['ink_bounds']))
        maximum={m:max(value[m] for value in observed) for m in ('text_error','colour_error')}
        if maximum!=row['measurements'] or row['decoded_frames']!=300:
            raise PermissionError('NUMERIC_OBSERVATION_CHANGED')
    if calibrate(result['rows'],policy['candidate_reference_sha256'])!=result['calibration']:
        raise PermissionError('CALIBRATION_CHANGED')
    return {'status':'AUTHENTICATED_GOP300_INSTRUMENT_OBSERVATIONS',
            'separation_passed':all(x['status']=='CALIBRATED_NUMERIC_SCOPE' for x in result['calibration'].values()),
            'quality_authorized':False,'publication_authorized':False,
            'provider_calls':0,'subprocess_calls':0}

def run(args):
    import numpy as np
    from PIL import Image, ImageDraw
    from hero_engine.procedural_infographics_phase5 import compile_audio_static_composition, _audio_static_pixels
    policy=read(args.policy)
    if sha(args.policy)!=args.policy_sha:raise PermissionError('PREREGISTRATION_CHANGED')
    if policy['encoder_sha256']!=sha('/usr/bin/ffmpeg'):raise PermissionError('ENCODER_CHANGED')
    if shutil.disk_usage(args.out.parent).free<15*1024**3:raise PermissionError('DISK_PREFLIGHT')
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
    if available<2*1024**3:raise PermissionError('MEMORY_PREFLIGHT')
    source=read(args.source)
    if sha(args.source)!=policy['source_manifest_sha256']:raise PermissionError('SOURCE_MANIFEST_CHANGED')
    layout=source['layout']; expected_domain=domain(layout)
    if sha(layout['font']['path'])!=layout['font']['sha256'].removeprefix('sha256:'):
        raise PermissionError('FONT_CHANGED')
    recipe=read(args.recipe)
    if sha(args.recipe)!=policy['recipe_sha256']:raise PermissionError('RECIPE_CHANGED')
    args.out.mkdir(exist_ok=False)
    shutil.copy2(args.policy,args.out/'policy.json')
    shutil.copy2(args.source,args.out/'target-source-manifest.json')
    shutil.copy2(args.recipe,args.out/'transport-recipe.json')
    started=datetime.now(timezone.utc).isoformat(); rows=[]
    reused=policy['reused_positive_artifacts']
    previous=Path(args.policy).parent/'controls'
    for item in reused:
        p=previous/item['path']
        if p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
            raise PermissionError('PREVIOUS_POSITIVE_ARTIFACT_CHANGED')
    for index in (0,1,2,5):
        shutil.copytree(previous/f'control-{index}',args.out/f'control-{index}')
    for index,spec in enumerate(policy['controls']):
        if spec['group'] in ('positive','holdout_positive'):
            row=read(args.out/f'control-{index}/measurement.json')
            if row['group']!=spec['group'] or row['title']!=spec['title']:
                raise PermissionError('REUSED_POSITIVE_POLICY_CHANGED')
            rows.append(row)
            print(json.dumps({'control_reused_without_encode_or_decode':index+1}),flush=True)
            continue
        directory=args.out/f'control-{index}';directory.mkdir()
        control=compile_audio_static_composition(title=spec['title'],bible=layout['style_bible'],
            format_pack=layout['format_pack'],font=Path(layout['font']['path']))
        if domain(control)!=expected_domain:raise PermissionError('CONTROL_DOMAIN_CHANGED')
        image,bounds=_audio_static_pixels(control);image.save(directory/'reference.png')
        damaged=image.copy()
        if 'negative' in spec['group']:
            # Fixed known corruption in both independent metrics, not target fitting.
            ImageDraw.Draw(damaged).rectangle((180,390,960,630),fill='#101820')
            array=np.asarray(damaged).copy();array[:,:,0]=np.minimum(array[:,:,0].astype('int16')+70,255)
            damaged=Image.fromarray(array.astype('uint8'))
        damaged.save(directory/'input.png')
        argv=['/usr/bin/ffmpeg','-nostdin','-hide_banner','-loglevel','error','-loop','1',
            '-framerate','30','-i',str(directory/'input.png'),'-an','-vf',recipe['video_profile']['native_filter'],
            '-frames:v','300','-c:v','libx264','-profile:v','high','-level:v','4.0','-preset','medium',
            '-qp','1','-g','300','-keyint_min','300','-sc_threshold','0','-threads','1',
            '-n',str(directory/'control.mp4')]
        before=time.monotonic();process=subprocess.run(argv,capture_output=True,timeout=90)
        (directory/'encode.stderr.txt').write_bytes(process.stderr)
        write(directory/'command.json',{'argv':argv,'layout':control,'source_reference_sha256':sha(directory/'reference.png')})
        write(directory/'process-result.json',{'exit_code':process.returncode,'elapsed_seconds':time.monotonic()-before})
        if process.returncode:raise RuntimeError('CONTROL_ENCODE_FAILED')
        decode=['/usr/bin/ffmpeg','-v','error','-threads','1','-i',str(directory/'control.mp4'),
                '-map','0:v:0','-an','-pix_fmt','rgb24','-threads','1','-fps_mode','passthrough','-f','rawvideo','-']
        frame_bytes=1920*1080*3;cache={};count=0;last=None;last_digest=None;chain=hashlib.sha256()
        with (directory/'decode.stderr.txt').open('wb') as errors:
            proc=subprocess.Popen(decode,stdout=subprocess.PIPE,stderr=errors)
            try:
                while True:
                    raw=proc.stdout.read(frame_bytes)
                    if not raw:break
                    if len(raw)!=frame_bytes or count>=300:raise PermissionError('CONTROL_DECODE_POPULATION')
                    digest=last_digest if raw==last else hashlib.sha256(raw).hexdigest()
                    if digest not in cache:
                        if len(cache)>=16:raise PermissionError('CONTROL_DISTINCT_FRAME_BOUND')
                        array=np.frombuffer(raw,np.uint8).reshape(1080,1920,3)
                        file=directory/f'decoded-{len(cache)}.png';Image.fromarray(array).save(file)
                        cache[digest]={'path':str(file.relative_to(args.out)),'rgb_sha256':digest,
                            'measurements':measure(np.asarray(image),array,bounds),'count':0}
                    cache[digest]['count']+=1;chain.update(bytes.fromhex(digest))
                    count+=1;last=raw;last_digest=digest
                code=proc.wait(timeout=15)
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        if code or count!=300 or (directory/'decode.stderr.txt').stat().st_size:
            raise PermissionError('CONTROL_DECODE_FAILED')
        row={'group':spec['group'],'title':spec['title'],'ink_bounds':bounds,
             'reference':str((directory/'reference.png').relative_to(args.out)),
             'reference_sha256':sha(directory/'reference.png'),'encoded_sha256':sha(directory/'control.mp4'),
             'decoded_frames':count,'decoded_rgb_chain_sha256':chain.hexdigest(),'distinct_frames':list(cache.values()),
             'measurements':{m:max(x['measurements'][m] for x in cache.values()) for m in ('text_error','colour_error')}}
        rows.append(row);write(directory/'measurement.json',row)
        print(json.dumps({'control_completed':index+1,'total':8,'group':spec['group'],'measurements':row['measurements']}),flush=True)
    calibration=calibrate(rows,policy['candidate_reference_sha256'])
    result={'version':'heroverse-gop300-independent-controls-v1','started_at':started,
        'completed_at':datetime.now(timezone.utc).isoformat(),'policy_sha256':args.policy_sha,
        'status':'CONTROL_SEPARATION_PASSED' if all(x['status']=='CALIBRATED_NUMERIC_SCOPE' for x in calibration.values()) else 'FAILED_CONTROL_SEPARATION',
        'domain':expected_domain,'rows':rows,'calibration':calibration,
        'master_rerendered':False,'master_decode_repeated':False,'provider_calls':0,
        'production_approved':False,'publication_authorized':False,
        'native_validator_integration':'NOT_INSTALLED'}
    write(args.out/'result.json',result)
    implementations={str(p.relative_to(args.native_root)):sha(p) for p in [
        args.native_root/'hero_engine/phase6_visual_metrics.py',args.native_root/'hero_engine/procedural_infographics_phase5.py']}
    write(args.out/'bindings.json',{'version':'heroverse-gop300-controls-bindings-v1',
        'producer_sha256':sha(__file__),'implementations':implementations,
        'artifacts':[bind(p,args.out) for p in sorted(args.out.rglob('*')) if p.is_file()],
        'quality_authorized':False,'publication_authorized':False})
    print(json.dumps({'status':result['status'],'binding_sha256':sha(args.out/'bindings.json'),'calibration':calibration}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('policy','source','recipe','out','native-root'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--policy-sha',required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.native_root));run(args)
