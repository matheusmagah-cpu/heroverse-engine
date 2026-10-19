"""Install a versioned successor in a new root; never alter frozen source."""
import hashlib,json,shutil
from pathlib import Path
EXPECTED = {'hero_engine/phase6_audio_production.py':'2617ff0bfccdf56c2b8ece577515fa859666aa8adbd09bccc0f0141fb6490afe',
 'hero_engine/creative_direction.py':'127cce3fd58a0739790312957387b6dcd975b6a1407b0a84e22766e099465f43'}
def apply(source,destination,module):
    source,destination,module=map(lambda p:Path(p).resolve(),(source,destination,module))
    if destination.exists() or source == destination or source in destination.parents:
        raise PermissionError('NEW_SEPARATE_ROOT_REQUIRED')
    originals={p:(source/p).read_bytes() for p in EXPECTED}
    if any(hashlib.sha256(raw).hexdigest()!=EXPECTED[p] for p,raw in originals.items()):
        raise PermissionError('SEMANTIC_FROZEN_SOURCE_CHANGED')
    helper=module.read_bytes();helper_hash=hashlib.sha256(helper).hexdigest()
    p=originals['hero_engine/phase6_audio_production.py'].decode()
    def replace(old,new):
        nonlocal p
        if p.count(old)!=1:raise PermissionError('SEMANTIC_EXACT_ANCHOR_REQUIRED')
        p=p.replace(old,new)
    replace('def build_current_audio_research(root: Path, source: Path, *, baseline: dict[str, Any]) -> dict[str, Any]:',
        'def build_current_audio_research(root: Path, source: Path, *, baseline: dict[str, Any], semantic_binding=None) -> dict[str, Any]:')
    replace('    from .observatory.format_cohorts import compile_format_cohorts\n',
        '    if semantic_binding is not None:\n        return _semantic_module().build_semantic_audio_research(root,source,baseline=baseline,semantic_binding=semantic_binding)\n    from .observatory.format_cohorts import compile_format_cohorts\n')
    replace("expected = build_current_audio_research(root,source,baseline=model['baseline'])",
        "expected = build_current_audio_research(root,source,baseline=model['baseline'],semantic_binding=model.get('semantic_binding'))")
    replace('    from .creative_direction import build_christian_rest_editorial\n',
        "    if model.get('version') == 'heroverse-semantic-audio-research-v2':\n        return _semantic_module().verify_editorial(model)\n    from .creative_direction import build_christian_rest_editorial\n")
    replace('def run_current_audio_research_production(root: Path, *, package_relative: Path,',
        'def _run_current_audio_research_production_v1(root: Path, *, package_relative: Path,')
    replace('        snapshot_reference: str | None) -> dict[str, Any]:',
        '        snapshot_reference: str | None, semantic_binding=None) -> dict[str, Any]:')
    replace("'editorial_angle':previous['recipe']['editorial']['angle']})",
        "'editorial_angle':previous['recipe']['editorial']['angle']}, semantic_binding=semantic_binding)")
    replace("recipe_version='heroverse-christian-rest-editorial-v5',",
        "recipe_version=('heroverse-christian-rest-editorial-v6' if semantic_binding is not None else 'heroverse-christian-rest-editorial-v5'),")
    replace("        source=directory/'snapshots.json'",
        "        source=(_semantic_module().handoff_source(root,semantic_binding) if semantic_binding is not None else directory/'snapshots.json')")
    replace('''key=f"audio-researched-next:{publication['channel_id']}:{publication['video_id']}:{receipt_hash}"''',
        "key=f\"audio-researched-next:{publication['channel_id']}:{publication['video_id']}:{receipt_hash}\" + (':' + semantic_binding['sha256'] if semantic_binding is not None else '')")
    p += f'''\n\ndef _semantic_module():
    from . import semantic_audio_research
    if hashlib.sha256(Path(semantic_audio_research.__file__).read_bytes()).hexdigest() != {helper_hash!r}:
        raise PermissionError('SEMANTIC_HELPER_IDENTITY_CHANGED')
    return semantic_audio_research


def run_current_audio_research_production(root: Path, *, package_relative: Path,
        current_bindings: dict[str, Any], expected_release_hash: str,
        snapshot_reference: str | None, semantic_binding=None) -> dict[str, Any]:
    """New work requires semantic evidence; historical v1 readers stay reproducible."""
    _semantic_module()
    pointer = Path(root)/'output/market/current-audio/semantic-handoff.binding.json'
    if semantic_binding is None and pointer.is_file():
        semantic_binding = json.loads(pointer.read_bytes())
    if semantic_binding is None:
        return {{'status':'WAITING_FOR_REVIEWED_SEMANTIC_HANDOFF',
                'render_authorized':False,'publication_authorized':False}}
    source = _semantic_module().handoff_source(root,semantic_binding)
    build_current_audio_research(root,source,baseline={{}},semantic_binding=semantic_binding)
    return _run_current_audio_research_production_v1(root,package_relative=package_relative,
        current_bindings=current_bindings,expected_release_hash=expected_release_hash,
        snapshot_reference=snapshot_reference,semantic_binding=semantic_binding)
'''
    c=originals['hero_engine/creative_direction.py'].decode()
    c=c.replace("'heroverse-christian-rest-editorial-v5')", "'heroverse-christian-rest-editorial-v5','heroverse-christian-rest-editorial-v6')")
    c=c.replace("(recipe_version == 'heroverse-christian-rest-editorial-v5','heroverse-christian-rest-editorial-v6')", "(recipe_version in ('heroverse-christian-rest-editorial-v5','heroverse-christian-rest-editorial-v6'))")
    c=c.replace("('-v2', '-v3', '-v4', '-v5')", "('-v2', '-v3', '-v4', '-v5', '-v6')")
    # A v6 recipe cannot smuggle legacy two-topic research into a new version.
    anchor='    recipe = {\'recipe_version\': \'heroverse-christian-rest-instrumental-v1\','
    assert c.count(anchor)==1
    c=c.replace(anchor,"    if recipe_version == 'heroverse-christian-rest-editorial-v6' and research.get('model',{}).get('version') != 'heroverse-semantic-audio-research-v2':\n        raise PermissionError('SEMANTIC_V6_MODEL_REQUIRED')\n"+anchor)
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
    (destination/'hero_engine/semantic_audio_research.py').write_bytes(helper)
    for name,content in [('hero_engine/phase6_audio_production.py',p),('hero_engine/creative_direction.py',c)]:
        (destination/name).write_text(content,encoding='utf-8')
    receipt={'status':'INTEGRATED_SHADOW_NOT_LIVE','original_hashes':EXPECTED,'helper_sha256':helper_hash,
        'successor_hashes':{n:hashlib.sha256((destination/n).read_bytes()).hexdigest() for n in EXPECTED},
        'old_source_preserved':True,'new_jobs_require_semantic_handoff':True,'publication_authorized':False}
    (destination/'semantic-overlay.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    import sys
    print(json.dumps(apply(*sys.argv[1:]),indent=2))
