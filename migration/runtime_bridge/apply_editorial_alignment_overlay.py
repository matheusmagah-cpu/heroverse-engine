"""Hash-pinned semantic guard in the original shared render/QA/package reader."""
import hashlib
from pathlib import Path
PIN='81cc1ccb215962fa9f678853dfd0632524617d0f4f19ce0e38783e8f8fd0f078'
def apply(root):
    root=Path(root).resolve();p=root/'hero_engine/render_phase5.py';raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise PermissionError('EDITORIAL_RENDER_READER_IDENTITY_CHANGED')
    text=raw.decode();start=text.index('def _rest_render_inputs(');end=text.index('\ndef ',start+4);part=text[start:end]
    needle="    bible = _read_json(package/'channel_style_bible.json')"
    if part.count(needle)!=1:raise PermissionError('EDITORIAL_READER_ANCHOR_CHANGED')
    helper=Path(__file__).with_name('editorial_visual_alignment.py').read_bytes();guard_hash='sha256:'+hashlib.sha256(helper).hexdigest()
    insertion=("    from . import editorial_visual_alignment as semantic\n"
        "    semantic_path = Path(semantic.__file__).resolve()\n"
        "    if semantic_path != (root/'hero_engine/editorial_visual_alignment.py').resolve() or _sha256(semantic_path) != "+repr(guard_hash)+":\n"
        "        raise PermissionError('EDITORIAL_GUARD_IDENTITY_CHANGED')\n"
        "    semantic.require_alignment(music, visual)\n"
        "    anchors[semantic_path] = "+repr(guard_hash)+"\n")
    part=part.replace(needle,insertion+needle)
    target=root/'hero_engine/editorial_visual_alignment.py'
    if target.exists():raise PermissionError('EDITORIAL_GUARD_ALREADY_PRESENT')
    target.write_bytes(helper);p.write_text(text[:start]+part+text[end:])
    return {'original_reader_sha256':PIN,'shadow_reader_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'guard_sha256':hashlib.sha256(helper).hexdigest(),'enforcement':'SHARED_NATIVE_PRE_RENDER_QA_AND_PACKAGING_READER',
            'existing_published_media_changed':False,'quality_approval_granted':False,'publication_performed':False}
