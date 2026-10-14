"""Materialize the exact current transport capsule; adopt, never render media."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
from apply_gop300_native_overlay import apply

def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
    with Path(p).open('x') as stream:json.dump(v,stream,indent=2);stream.write('\n')

def prepare(stage,source,old_proof,master,root):
    receipt=apply(source,root,stage/'native_gop300_bridge.py')
    package=root/'output/production/current-gop300-transport-v1';package.mkdir(parents=True)
    target=package/'source';target.mkdir()
    # Rebind existing source paths, preserving exact PNG/SVG bytes and layout.
    for name in ('composition.png','composition.svg'):
        shutil.copy2(old_proof/'static-source'/name,target/name)
    manifest=read(old_proof/'static-source/source-manifest.json')
    manifest['generator']['path']=str(root/'hero_engine/procedural_infographics_phase5.py')
    manifest['produced']['raster']=str(target/'composition.png')
    manifest['source_svg']=str(target/'composition.svg')
    write(target/'source-manifest.json',manifest)
    rights=read(old_proof/'static-source/rights-evidence.json')
    rights.update(source_svg=str(target/'composition.svg'),raster=str(target/'composition.png'),
        composition_manifest={'path':str(target/'source-manifest.json'),'sha256':'sha256:'+sha(target/'source-manifest.json')})
    write(target/'rights-evidence.json',rights)
    write(package/'asset_manifest.json',{'assets':[{'uri':str(target/'composition.png'),
        'content_hash':'sha256:'+sha(target/'composition.png'),'rights_evidence_uri':str(target/'rights-evidence.json')}]})
    write(package/'channel_style_bible.json',manifest['layout']['style_bible'])
    write(package/'take_plan.json',{'format_pack_id':'fp-narrated-reflection-static',
        'render_profile':'phase6-static-gop300-qp1-transport-v1','duration_ms':10800000,
        'scope':'Existing exact transport capsule, not complete native release package',
        'production_approved':False,'publication_authorized':False})
    media=package/'HeroVerse_Rest_Corrected_3h_Metricool.mp4'
    os.link(master,media) # No media copy, encoding, decode or source overwrite.
    directory=root/'output/runtime/gestor-central/maintenance-runs/gop300-native-v1'
    directory.mkdir(parents=True);proof=directory/'evidence';proof.mkdir()
    shutil.copytree(stage/'controls-v3',proof/'controls-v3')
    files={'controls':proof/'controls-v3/bindings.json','policy':proof/'controls-v3/policy.json'}
    for key,name in [('producer','calibrate_transport_gop300_recovery_v3.py'),
                     ('helper','calibrate_transport_gop300.py'),('verifier','verify_transport_gop300.py'),
                     ('master_review','reused-native-master-review.json'),('cycle_metrics','reused-cycle-metrics.json')]:
        shutil.copy2(stage/name,proof/name);files[key]=proof/name
    for key,name in [('recipe','transport-recipe.json'),('transport','transport-verification.json'),
                     ('original_source','static-source/source-manifest.json')]:
        output=proof/Path(name).name;shutil.copy2(old_proof/name,output);files[key]=output
    descriptor={'version':'heroverse-gop300-native-bridge-v1','package':str(package.relative_to(root)),
        'media':media.name,'authority':{'quality':False,'publication':False,'operational_activation':False},
        'evidence':{k:{'path':str(p.relative_to(directory)),'sha256':sha(p)} for k,p in files.items()}}
    write(directory/'native-binding.json',descriptor)
    binding={'path':str(directory/'native-binding.json'),'sha256':'sha256:'+sha(directory/'native-binding.json')}
    write(root/'native-binding-offer.json',binding)
    return package,media,binding,receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('stage','source','old-proof','master','root'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--resume-prepared',action='store_true')
    args=parser.parse_args();args.root=args.root.resolve()
    if args.resume_prepared:
        binding=read(args.root/'native-binding-offer.json');descriptor=read(binding['path'])
        package=args.root/descriptor['package'];media=package/descriptor['media']
        overlay=read(args.root/'gop300-native-overlay.json')
    else:
        package,media,binding,overlay=prepare(args.stage.resolve(),args.source.resolve(),args.old_proof.resolve(),args.master.resolve(),args.root)
    sys.path.insert(0,str(args.root))
    from hero_engine.standard_qualification_phase5 import read_audio_static_codec_controls,verify_audio_static_execution
    controls=read_audio_static_codec_controls(args.root,package,binding=binding)
    execution=verify_audio_static_execution(args.root,package,media,binding=binding)
    result={'status':'NATIVE_GOP300_CONTROL_READER_AND_EXISTING_TRANSPORT_ADOPTION_PASS',
        'overlay':overlay,'binding':binding,'controls':controls,'execution':execution,
        'master_decode_repeated':False,'master_audio_measurement_repeated':False,
        'full_native_release_package_complete':False,'production_approved':False,'publication_authorized':False}
    write(args.stage/'native-gop300-integration-result.json',result)
    print(json.dumps({'status':result['status'],'limits':controls['limits'],'native_module_sha256':overlay['new_standard_sha256'],
        'legacy_preserved':True,'production_approved':False},indent=2))
