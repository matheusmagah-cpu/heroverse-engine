"""Exact existing GOP300 transport adoption, never a new render attestation.

No subprocess, inference, approval, publication or original-source mutation.
All known evidence identities are external historical pins. Unknown transports
continue through the original native reader or fail closed.
"""
import hashlib, json
from pathlib import Path

VERSION='heroverse-gop300-native-bridge-v1'
MASTER='55c2a047e107ce42469261978ab34353e58622ec436e40876f6a8fc71c882c46'
RASTER='bbd6aaf2c37caf9f47dc7b41880e4bce244afe7dc8e3b831a7829e3565c83a95'
PINS={
 'controls':'8ea5bf876957b112e1575118be68f610329052f45c5a60a9a0a3ac104993d13e',
 'policy':'ddbf013c9bc5a9cc11797793a90add7e7a738bdbff1f3964fdfd02964422d377',
 'producer':'0ae71a26087ae2f631073a85dde0d61323dbc695e37156d5f42e8356dc02294a',
 'master_review':'425f06f5e157a08a32e330c9498acf3d46f44e12817e4bbe2dd4b4a19d047289',
 'cycle_metrics':'de600d5c7eeb6c3eed3722229b31b6cf17e6e730bb5d63b211209029a9adbcec',
 'recipe':'320178e2364078f7364e6d9ea57a828f0d8a85ad9500cc4559ed458b7feab0c3',
 'transport':'6719c68a80b019d6fece9a48ec9335c59ea4841fec430339420589def3c1d7c1',
 'original_source':'dee8a969ae1be4e77d8eb983936083653938e902b919b98074159e685e567ac7',
 'helper':'b1bd4fed0038b7fa7d704cdd29d6672a851e382799fe6fe2bd60ac4b93dd159a',
 'verifier':'722daaaa98a57d5aa2f7f28fa44cc85dd6fdade8c72be9b45d93f1cb84785daf',
}

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def offered(binding):
    # Dispatch is version-specific. Malformed/missing unknown bindings are left
    # to the unchanged original reader, never admitted by this predicate.
    try:return read(binding['path']).get('version')==VERSION
    except (KeyError,TypeError,ValueError,OSError):return False

def _capture(root,package,binding,expected_bridge_sha256):
    root=Path(root).resolve();package=Path(package).resolve();path=Path(binding['path']).resolve()
    if (sha(__file__)!=expected_bridge_sha256
            or Path(__file__).resolve()!=root/'hero_engine/native_gop300_bridge.py'):
        raise PermissionError('NATIVE_GOP300_BRIDGE_IDENTITY')
    if (set(binding)!={'path','sha256'} or not package.is_relative_to(root/'output/production')
            or not path.is_relative_to(root/'output/runtime/gestor-central/maintenance-runs')
            or binding['sha256']!='sha256:'+sha(path)):
        raise PermissionError('NATIVE_GOP300_EXTERNAL_ANCHOR')
    descriptor=read(path)
    if (descriptor.get('version')!=VERSION or descriptor.get('authority')!=
            {'quality':False,'publication':False,'operational_activation':False}
            or descriptor.get('package')!=str(package.relative_to(root))
            or set(descriptor.get('evidence',{}))!=set(PINS)):
        raise PermissionError('NATIVE_GOP300_DESCRIPTOR')
    captured={path:sha(path)}; paths={}
    for key,pin in PINS.items():
        item=descriptor['evidence'][key]
        target=(path.parent/item['path']).resolve()
        if (not target.is_relative_to(path.parent) or item['sha256']!=pin or sha(target)!=pin):
            raise PermissionError('NATIVE_GOP300_EVIDENCE_'+key)
        captured[target]=pin;paths[key]=target
    for key in ('take_plan.json','asset_manifest.json','channel_style_bible.json'):
        current=package/key;captured[current]=sha(current)
    plan=read(package/'take_plan.json');assets=read(package/'asset_manifest.json')['assets']
    if (plan.get('render_profile')!='phase6-static-gop300-qp1-transport-v1'
            or plan.get('format_pack_id')!='fp-narrated-reflection-static'
            or plan.get('duration_ms')!=10800000 or len(assets)!=1):
        raise PermissionError('NATIVE_GOP300_PACKAGE_DOMAIN')
    asset=assets[0];raster=Path(asset['uri']).resolve();rights=Path(asset['rights_evidence_uri']).resolve()
    if (not raster.is_relative_to(package) or not rights.is_relative_to(package)
            or asset.get('content_hash')!='sha256:'+RASTER or sha(raster)!=RASTER):
        raise PermissionError('NATIVE_GOP300_SOURCE_RASTER')
    evidence=read(rights);ref=evidence['composition_manifest']
    from .procedural_infographics_phase5 import read_audio_static_source
    source=read_audio_static_source(root,Path(ref['path']),expected_sha256=ref['sha256'])
    if (source['layout']!=read(paths['original_source'])['layout']
            or source['layout']['style_bible']!=read(package/'channel_style_bible.json')
            or source['produced']['raster']!=str(raster)
            or source['produced']['raster_hash']!='sha256:'+RASTER):
        raise PermissionError('NATIVE_GOP300_SOURCE_GEOMETRY_OR_BIBLE')
    for current in (raster,rights,Path(ref['path']),Path(source['source_svg']),
                    Path(source['generator']['path']),Path(source['layout']['font']['path'])):
        captured[current]=sha(current)
    media=(package/descriptor['media']).resolve()
    if (not media.is_relative_to(package) or media.stat().st_size!=391733890 or sha(media)!=MASTER):
        raise PermissionError('NATIVE_GOP300_CURRENT_MASTER')
    captured[media]=MASTER
    review=read(paths['master_review']);cycle=read(paths['cycle_metrics']);transport=read(paths['transport'])
    if (review['master_sha256']!=MASTER or review['decoded_frames']!=324000
            or review['decode_errors']!=0 or review['distinct_frame_count']!=1
            or review['decoded_rgb_pixel_sha256'] not in cycle['measurements']
            or transport['candidate']!={'sha256':MASTER,'size_bytes':391733890}
            or transport['audio']['all_payloads_identical'] is not True
            or transport['video']['all_output_packet_payloads_match_generated_cycle'] is not True
            or transport['video']['cycle_packets']!=300 or transport['video']['output_packets']!=324000):
        raise PermissionError('NATIVE_GOP300_PRESERVED_LINEAGE')
    return descriptor,paths,captured,source,media

def _stable(captured):
    if any(sha(path)!=digest for path,digest in captured.items()):
        raise PermissionError('NATIVE_GOP300_INPUT_CHANGED')

def read_controls(root,package,*,binding,music_bindings,expected_bridge_sha256):
    if music_bindings is not None and (not isinstance(music_bindings, dict) or set(music_bindings) != {'recipe','source','asset'}):
        raise PermissionError('instrumental render needs three exact input bindings')
    descriptor,paths,captured,source,media=_capture(root,package,binding,expected_bridge_sha256)
    # Reuse the already qualified reader, but load exact pinned code bytes under
    # a private module name. Neither file can select an arbitrary implementation.
    import importlib.util,sys
    helper_spec=importlib.util.spec_from_file_location('_hv_gop300_controls_pinned',paths['helper'])
    helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
    verifier_raw=paths['verifier'].read_text()
    # Only import resolution is rebased; verify bytes before this deterministic
    # in-memory module wiring. No metric/threshold/validation code is rewritten.
    verifier_raw=verifier_raw.replace('import calibrate_transport_gop300 as controls','controls = _pinned_controls')
    namespace={'__name__':'_hv_gop300_verifier_pinned','_pinned_controls':helper}
    exec(compile(verifier_raw,str(paths['verifier']),'exec'),namespace)
    observed=namespace['verify'](paths['controls'].parent,PINS['controls'],root,PINS['policy'],paths['producer'])
    if music_bindings is not None:
        # Original current music/asset/source guards are still mandatory. Missing
        # source contracts fail; a transport calibration cannot stand in for them.
        from .render_phase5 import _rest_render_inputs
        _,asset,music_inputs=_rest_render_inputs(Path(root).resolve(),Path(package).resolve(),music_bindings)
        if asset['content_hash']!='sha256:'+RASTER:raise PermissionError('NATIVE_GOP300_MUSIC_VISUAL')
        captured.update({Path(p):str(v).removeprefix('sha256:') for p,v in music_inputs.items()})
    _stable(captured)
    return {'status':'AUTHENTICATED_STATIC_CODEC_LIMITS','binding':dict(binding),
        'limits':observed['limits'],'domain':observed['domain'],
        'authenticated_inputs':[{'path':str(p),'sha256':'sha256:'+v} for p,v in captured.items()],
        'transport_profile':'phase6-static-gop300-qp1-transport-v1',
        'quality_authorized':False,'publication_authorized':False}

def read_execution(root,package,media,*,binding,expected_bridge_sha256):
    _,paths,captured,source,expected=_capture(root,package,binding,expected_bridge_sha256)
    if Path(media).resolve()!=expected:raise PermissionError('NATIVE_GOP300_EXECUTION_MEDIA')
    _stable(captured)
    return {'status':'AUTHENTICATED_EXISTING_GOP300_TRANSPORT_LINEAGE_NOT_NEW_EXECUTION',
        'binding':dict(binding),'media_sha256':'sha256:'+MASTER,'observed_segments':1,
        'prior_full_native_frames':324000,'prior_packet_lineage_verified':True,
        'new_render_executed':False,'historical_command_timestamps_unavailable':True,
        'quality_authorized':False,'publication_authorized':False,
        'authenticated_inputs':[{'path':str(p),'sha256':'sha256:'+v} for p,v in captured.items()]}
