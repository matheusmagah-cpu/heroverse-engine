"""Run pinned, unchanged native music functions without loading unrelated voice modules.

This measurement kernel is not an installed production runtime or release approval.
No final master audio is read, sliced, regenerated, or used as the reference.
"""
from __future__ import annotations
import argparse, ast, hashlib, json, math, os, re, shutil, sys, tempfile, threading, time, types, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(os.environ.get('HERO_RECOVERY_BASE','/workspace/scratch/f2180567de8e'))
SOURCE = Path(os.environ.get('HERO_NATIVE_SOURCE_ROOT','/workspace/scratch/19a457603cc9/source-recovered/native/project'))
ROOT = Path(os.environ.get('HERO_NATIVE_ROOT',str(BASE/'heroverse-native-gop300')))
OUT = ROOT/'output/runtime/gestor-central/maintenance-runs/cloud-independent-music-reference-20261015'
POLICY = BASE/'heroverse-stage/cloud-music-reference-policy.json'
POLICY_COMMIT = 'ceffe67af8106ed2524d25e17869fb84dab1a37c'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def functions(module, path, names, globals_):
    """Compile exact source function ASTs; no body edits, stubs or mocked predictions."""
    raw=path.read_text(); tree=ast.parse(raw)
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes}!=set(names):raise PermissionError('native function selection differs')
    module.__dict__.update(globals_)
    selected=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
    ast.fix_missing_locations(selected)
    exec(compile(selected,str(path),'exec'),module.__dict__)
    return {n.name:hashlib.sha256(ast.get_source_segment(raw,n).encode()).hexdigest() for n in nodes}

def kernel(policy):
    import numpy as np
    import soundfile as sf
    package=types.ModuleType('cloud_music_native_kernel');package.__path__=[]
    sys.modules[package.__name__]=package
    common=dict(Path=Path,Any=Any,hashlib=hashlib,json=json,math=math,re=re,os=os,shutil=shutil,
        sys=sys,tempfile=tempfile,time=time,ctypes=__import__('ctypes'),datetime=datetime,timezone=timezone)
    capacity=types.ModuleType(package.__name__+'.production_capacity')
    cap_path=SOURCE/'hero_engine/production_capacity.py'
    caps=functions(capacity,cap_path,['ResourceWait','measure_local_resources'],common)
    capacity._HEAVY_TASK_SLOT=threading.Lock();sys.modules[capacity.__name__]=capacity
    build=types.ModuleType(package.__name__+'.creative_direction')
    recipes=functions(build,SOURCE/'hero_engine/creative_direction.py',['build_christian_rest_music_recipe'],common)
    render=types.ModuleType(package.__name__+'.render')
    renders=functions(render,SOURCE/'hero_engine/render_creative_v3_phase5.py',['_build_continuous_rest_music'],
        dict(common,np=np,sf=sf,_sha256=lambda p:'sha256:'+sha(p)))
    quality=types.ModuleType(package.__name__+'.quality');quality.__package__=package.__name__
    source=SOURCE/'hero_engine/phase5_autonomous_quality.py'
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source.read_text()).body
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id.startswith('MUSIC_MODEL_')}
    qs=functions(quality,source,['_music_aesthetic_predictor','measure_music_aesthetics'],dict(common,**constants,_hash=sha))
    return build,render,quality,{'recipe':recipes,'generator':renders,'measurement':qs,'capacity':caps,
        'capacity_module_sha256':sha(cap_path),'method':'EXACT_NATIVE_AST_FUNCTION_BODIES_NO_MOCKS'}

def restore_model():
    directory=ROOT/'models/audiobox-aesthetics/9b1dd8e5df9af7216e836a98974fe3b82c56ded6'
    directory.mkdir(parents=True,exist_ok=True);weights=directory/'model.safetensors';rows=[]
    if weights.exists():
        if sha(weights)!='a5a3c2412649cc2384ec525ffd5180ce6c4778f43bed6108e0a1303de04d014e':raise PermissionError('existing weights differ')
        return
    with weights.open('xb') as output:
        offset=0
        for i in range(1,14):
            archive=BASE/'cloud-music-model-parts'/f'HeroVerse_AudioBox_20261013_Part{i:03}.zip'
            with zipfile.ZipFile(archive) as z:
                part=json.loads(z.read('PART.json'));payload=z.read('payload.bin')
                if part['part_number']!=i or part['part_index']!=i-1 or part['model_offset']!=offset or part['part_count']!=13:
                    raise PermissionError('model part order differs')
                if len(payload)!=part['payload_bytes'] or hashlib.sha256(payload).hexdigest()!=part['payload_sha256']:
                    raise PermissionError('model payload hash differs')
                output.write(payload);offset+=len(payload)
                rows.append({'part':i,'archive_sha256':sha(archive),'payload_sha256':part['payload_sha256'],'bytes':len(payload)})
                if i==1:
                    config=z.read('config.json')
                    if hashlib.sha1(f'blob {len(config)}\0'.encode()+config).hexdigest()!='e2b5a9ece8c3db1cffec3bef4c63bf678fbcaf4e':raise PermissionError('model config differs')
                    (directory/'config.json').write_bytes(config)
    if weights.stat().st_size!=415472992 or sha(weights)!='a5a3c2412649cc2384ec525ffd5180ce6c4778f43bed6108e0a1303de04d014e':
        raise PermissionError('complete model anchor differs')
    write(OUT/'model-restoration.json',{'status':'EXACT_MODEL_RESTORED','parts':rows,'weights_sha256':sha(weights),'bytes':weights.stat().st_size})

def main():
    action=argparse.ArgumentParser();action.add_argument('stage',choices=['prepare','measure']);args=action.parse_args()
    policy=json.loads(POLICY.read_text());OUT.mkdir(parents=True,exist_ok=True)
    for relative,pin in policy['candidate']['source_modules'].items():
        if sha(SOURCE/relative)!=pin:raise PermissionError('native source anchor differs')
    build,render,quality,bodies=kernel(policy)
    if args.stage=='prepare':
        restore_model()
        recipe=build.build_christian_rest_music_recipe(duration_ms=192000,
            channel_model_hash='sha256:ec3a6ee301d33f44b2c7c967f238dee37600a1fddbd121c33e6f44bf933b15f7',
            style_bible_hash='sha256:8a17766b2f8ed4f3f1be0f45a82cac8a6b4b741c046a3e4c32a540cedfd33930',
            recipe_version='heroverse-christian-rest-instrumental-v2')
        write(OUT/'recipe.json',recipe)
        result=render._build_continuous_rest_music(192000,OUT/'independent-v2-reference.wav',
            created_at=datetime.now(timezone.utc).isoformat(),recipe=recipe,recipe_hash='sha256:'+sha(OUT/'recipe.json'))
        write(OUT/'generation.json',{'policy_commit':POLICY_COMMIT,'policy_sha256':sha(POLICY),'native_kernel':bodies,
            'observation':result,'target_media_read':False,'target_media_samples_used':0,'publication_authorized':False})
        print(json.dumps({'status':'INDEPENDENT_REFERENCE_GENERATED','media_hash':result['content_hash'],'duration_ms':192000}),flush=True)
    else:
        media=OUT/'independent-v2-reference.wav';generation=json.loads((OUT/'generation.json').read_text())
        if generation['native_kernel']!=bodies or generation['observation']['content_hash']!='sha256:'+sha(media):
            raise PermissionError('generated reference changed')
        if generation['policy_sha256']!=sha(POLICY):raise PermissionError('reference policy changed')
        observed=quality.measure_music_aesthetics(ROOT,media,expected_media_hash='sha256:'+sha(media),expected_duration_ms=192000)
        write(OUT/'observation.json',observed)
        print(json.dumps({'status':observed['status'],'full_duration_observed':observed['full_duration_observed'],
            'windows':len(observed['windows']),'axis_mean':observed['axis_mean'],'publication_authorized':False}),flush=True)

if __name__=='__main__':main()
