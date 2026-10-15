"""Add authenticated cloud reference dispatch; retain exact historical reference branch."""
from pathlib import Path
import hashlib, shutil

ORIGINAL='1b3dfca6e86e7153c98a6779687bd9048a22e78dcac2dbd76f59191f6ba489dc'

def apply(root:Path,bridge:Path):
    target=root/'hero_engine/qa_phase5.py';raw=target.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL:raise PermissionError('native QA origin differs')
    backup=root/'migration-history/cloud-music-reference/qa_phase5.py'
    backup.parent.mkdir(parents=True,exist_ok=True)
    with backup.open('xb') as stream:stream.write(raw)
    text=raw.decode()
    helper='''\n\ndef _read_selected_rest_music_reference(root: Path, binding: dict, *, failure_message: str) -> dict:
    from .cloud_music_reference import OBSERVATION_SHA, read_cloud_music_reference
    if binding.get('sha256') == OBSERVATION_SHA:
        return read_cloud_music_reference(root, binding=binding)
    path=Path(binding['path']).resolve()
    if (not path.is_relative_to(root/'output/runtime/gestor-central/maintenance-runs')
            or binding['sha256']!=REST_MUSIC_REFERENCE_SHA256
            or _sha256(path)!=REST_MUSIC_REFERENCE_SHA256):
        raise PermissionError(failure_message)
    return _read_json(path)
'''
    marker='\ndef qualify_rest_music_delivery('
    if text.count(marker)!=1:raise PermissionError('native entry differs')
    text=text.replace(marker,helper+marker)
    for message in ['selected music reference is not the independently anchored observation','musical qualification reference differs']:
        block="""    if (not reference_path.is_relative_to(root/'output/runtime/gestor-central/maintenance-runs')
            or aesthetic_reference_binding['sha256']!=REST_MUSIC_REFERENCE_SHA256
            or _sha256(reference_path)!=REST_MUSIC_REFERENCE_SHA256):
        raise PermissionError('MESSAGE')
    reference=_read_json(reference_path)""".replace('MESSAGE',message)
        if text.count(block)!=1:raise PermissionError('native reference guard differs')
        text=text.replace(block,"    reference=_read_selected_rest_music_reference(root,aesthetic_reference_binding,\n        failure_message="+repr(message)+")")
    old="            or _sha256(reference_path)!=REST_MUSIC_REFERENCE_SHA256 or _sha256(profile_path)!=profile_hash):"
    if text.count(old)!=1:raise PermissionError('native TOCTOU guard differs')
    text=text.replace(old,"            or _read_selected_rest_music_reference(root,aesthetic_reference_binding, failure_message='reference changed')!=reference\n            or _sha256(profile_path)!=profile_hash):")
    old="    floors={axis:min(row['scores'][axis] for row in reference['windows']) for axis in ('CE','PQ')}"
    if text.count(old)!=1:raise PermissionError('native minima rule differs')
    text=text.replace(old,"    from .cloud_music_reference import reference_floors\n    floors=reference_floors(reference)")
    target.write_text(text);shutil.copy2(bridge,root/'hero_engine/cloud_music_reference.py')
    return {'original_sha256':ORIGINAL,'native_qa_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'bridge_sha256':hashlib.sha256(bridge.read_bytes()).hexdigest(),'historical_constant_changed':False}

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('bridge',type=Path);a=p.parse_args()
    print(json.dumps(apply(a.root,a.bridge),indent=2))
