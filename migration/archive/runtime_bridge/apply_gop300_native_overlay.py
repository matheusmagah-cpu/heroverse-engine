"""Append an exact transport-only reader branch in a NEW native shadow."""
import hashlib,json,shutil
from pathlib import Path

ORIGINAL='ffd78d7097dcad8432f0a3b9ce6c9ae864246439fe09d96926f70132b2875911'

def apply(source,destination,bridge):
    source=Path(source).resolve();destination=Path(destination).resolve();bridge=Path(bridge).resolve()
    module=Path('hero_engine/standard_qualification_phase5.py')
    raw=(source/module).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL:raise PermissionError('NATIVE_STANDARD_SOURCE_CHANGED')
    if destination.exists() or destination==source or source in destination.parents:
        raise PermissionError('NEW_SEPARATE_NATIVE_SHADOW_REQUIRED')
    bridge_sha=hashlib.sha256(bridge.read_bytes()).hexdigest()
    text=raw.decode()
    anchor='    from .phase6_visual_metrics import calibrate_error_limit\n'
    branch=("    from .native_gop300_bridge import offered as _gop300_offered\n"
        "    if _gop300_offered(binding):\n"
        "        from .native_gop300_bridge import read_controls as _gop300_read\n"
        f"        return _gop300_read(root, package, binding=binding, music_bindings=music_bindings, expected_bridge_sha256='{bridge_sha}')\n")
    if text.count(anchor)!=1:raise PermissionError('CONTROL_READER_ANCHOR_CHANGED')
    text=text.replace(anchor,branch+anchor)
    anchor2='    """Consume the producer\'s existing native execution observations, not a label."""\n'
    branch2=("    from .native_gop300_bridge import offered as _gop300_offered\n"
        "    if _gop300_offered(binding):\n"
        "        from .native_gop300_bridge import read_execution as _gop300_execution\n"
        f"        return _gop300_execution(root, package, media, binding=binding, expected_bridge_sha256='{bridge_sha}')\n")
    if text.count(anchor2)!=1:raise PermissionError('EXECUTION_READER_ANCHOR_CHANGED')
    text=text.replace(anchor2,anchor2+branch2)
    # Exact reverse comparison preserves every original guard and legacy path.
    if text.replace(branch,'').replace(branch2,'').encode()!=raw:
        raise PermissionError('LEGACY_READER_BODY_CHANGED')
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
    history=destination/'migration-history/gop300-native-v1';history.mkdir(parents=True)
    with (history/'standard_qualification_phase5.py').open('xb') as stream:stream.write(raw)
    (destination/module).write_text(text)
    shutil.copy2(bridge,destination/'hero_engine/native_gop300_bridge.py')
    receipt={'version':'native-gop300-reader-overlay-v1','original_sha256':ORIGINAL,
        'original_preserved':True,'new_standard_sha256':hashlib.sha256(text.encode()).hexdigest(),
        'bridge_sha256':bridge_sha,'legacy_reader_body_byte_identical_after_removing_new_dispatch':True,
        'native_quality_and_music_gates_unchanged':True,'production_approved':False,'publication_authorized':False}
    (destination/'gop300-native-overlay.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
