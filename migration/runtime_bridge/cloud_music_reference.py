"""Authenticated independent reference; historical anchor remains unchanged."""
from __future__ import annotations
import copy, hashlib, json, math
from pathlib import Path

DIRECTORY=Path('output/runtime/gestor-central/maintenance-runs/cloud-independent-music-reference-20261015')
OBSERVATION_SHA='sha256:fc77d3ad0cbb17a9b530a3b029fb8f7b83fc095daaa4460970e20860c78fc205'
MEDIA_SHA='sha256:518c3f9533105a7308e169e4d3616ba245c7554fb7bd805e3e4522cc281da4de'
MODEL_SHA='sha256:a5a3c2412649cc2384ec525ffd5180ce6c4778f43bed6108e0a1303de04d014e'
HISTORICAL_FLOORS={'CE':5.388515023542345,'PQ':7.4419801340579985}
PINS={'observation.json':OBSERVATION_SHA,
 'generation.json':'sha256:14d5124efda88410915eacd62a196a4cf9e1ea66795c2ff3bb78b4abebd8b12b',
 'recipe.json':'sha256:e4df04d72036a9c7a35bfabd7f56db17e788ee3255e9585cf8d554b3398a3e64',
 'policy-v2.json':'sha256:3563cc85f2f92ee59917ce32a783700db088e9651c15daca3629cea85831a5c8'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return 'sha256:'+h.hexdigest()

def read_cloud_music_reference(root:Path,*,binding:dict)->dict:
    root=root.resolve();directory=root/DIRECTORY;path=directory/'observation.json'
    if set(binding)!={'path','sha256'} or Path(binding['path']).resolve()!=path or binding['sha256']!=OBSERVATION_SHA:
        raise PermissionError('independent reference identity differs')
    if not directory.resolve().is_relative_to(root):raise PermissionError('independent reference escaped root')
    for name,pin in PINS.items():
        if digest(directory/name)!=pin:raise PermissionError('independent reference evidence changed: '+name)
    reference=json.loads(path.read_text());generation=json.loads((directory/'generation.json').read_text())
    recipe=json.loads((directory/'recipe.json').read_text());policy=json.loads((directory/'policy-v2.json').read_text())
    media=directory/'independent-v2-reference.wav'
    if digest(media)!=MEDIA_SHA or reference['media_hash']!=MEDIA_SHA or generation['observation']['content_hash']!=MEDIA_SHA:
        raise PermissionError('independent reference media differs')
    if recipe['recipe_version']!='heroverse-christian-rest-instrumental-v2' or recipe['duration_ms']!=192000:
        raise PermissionError('reference is not independent v2 sound design')
    if generation['target_media_read'] is not False or generation['target_media_samples_used']!=0:
        raise PermissionError('reference depends on final target')
    if (reference['status']!='MEASURED_MUSIC_AESTHETICS' or reference['full_duration_observed'] is not True
            or reference['duration_ms']!=192000 or reference['observed_frames']!=9216000
            or reference['model']['weights_sha256']!=MODEL_SHA or reference['publication_authorized'] is not False):
        raise PermissionError('independent reference measurement incomplete')
    model_dir=root/'models/audiobox-aesthetics/9b1dd8e5df9af7216e836a98974fe3b82c56ded6'
    for name,key in [('model.safetensors','weights'),('config.json','config')]:
        local=model_dir/name
        if digest(local)!=reference['model'][key+'_sha256']:raise PermissionError('independent reference model changed')
    if reference['model']['versions']!=policy['measurement']['versions']:raise PermissionError('reference evaluator versions differ')
    cursor=0
    for row in reference['windows']:
        end=min(cursor+480000,9216000);context=cursor if end-cursor==480000 else end-480000
        if (row['start_frame']!=cursor or row['end_frame']!=end or row['context_start_frame']!=context
                or row['context_end_frame']!=end or set(row['scores'])!={'CE','CU','PC','PQ'}
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in row['scores'].values())):
            raise PermissionError('independent reference clock or scores changed')
        cursor=end
    if cursor!=9216000 or len(reference['windows'])!=20:raise PermissionError('independent reference coverage incomplete')
    means={a:sum(r['scores'][a]*(r['end_frame']-r['start_frame']) for r in reference['windows'])/cursor for a in ('CE','CU','PC','PQ')}
    if means!=reference['axis_mean']:raise PermissionError('reference aggregation differs')
    result=copy.deepcopy(reference)
    result['cloud_independent_reference']={'version':'cloud-owned-v2-native-minima-v1',
        'observation_sha256':OBSERVATION_SHA,'historical_reference_restored':False,
        'scope':'NATIVE_REST_MUSIC_NONREGRESSION_REFERENCE_NOT_MARKET_OR_FULL_RELEASE_APPROVAL'}
    return result

def reference_floors(reference:dict)->dict:
    floors={a:min(row['scores'][a] for row in reference['windows']) for a in ('CE','PQ')}
    marker=reference.get('cloud_independent_reference')
    if marker is not None:
        if marker.get('version')!='cloud-owned-v2-native-minima-v1' or marker.get('observation_sha256')!=OBSERVATION_SHA:
            raise PermissionError('unknown successor reference')
        floors={a:max(HISTORICAL_FLOORS[a],v) for a,v in floors.items()}
    return floors
