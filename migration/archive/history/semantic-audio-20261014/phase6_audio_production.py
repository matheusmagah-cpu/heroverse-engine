from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .phase6_production import CHANNEL_ID, _read


def build_current_audio_research(root: Path, source: Path, *, baseline: dict[str, Any]) -> dict[str, Any]:
    """Model public title demand, not private audience, sound quality or rights.

    Reuse the observatory's exact channel/format/age cohorts. A title supplies
    a topic hypothesis only; neither its recording nor its words are reused.
    """
    from .observatory.format_cohorts import compile_format_cohorts
    root = root.resolve(); source = source.resolve()
    if not source.is_relative_to(root / 'output/market'):
        raise PermissionError('current audio research must be confined to market evidence')
    raw = source.read_bytes(); bundle = json.loads(raw)
    config_path=root/'config/current_audio_research.json';config_raw=config_path.read_bytes()
    config=json.loads(config_raw)
    references=config.get('references',[])
    expected_ids={r['channel_id'] for r in references}
    if (config.get('channel_id')!=CHANNEL_ID or config.get('media_downloaded') is not False
            or len(expected_ids)!=3 or len(references)!=3):
        raise PermissionError('current research catalog identity differs')
    for row in bundle['snapshots']:
        if row['channel_id'] not in expected_ids:
            raise PermissionError('research snapshot belongs to a foreign reference')
        if row.get('payload') is not None and row['payload'].get('channel_id_public')!=row['channel_id']:
            raise PermissionError('research public channel differs from requested identity')
    cohorts = compile_format_cohorts(source)
    evidence = {row['snapshot_id']: row for row in bundle['snapshots']}
    groups = [g for g in cohorts['groups'] if g['population_scope'] == 'MARKET'
        and g['content_format'] == 'LONG' and g['age_band'] in ('0_7D', '8_30D')
        and g['status'] == 'SUFFICIENT']
    # Existing minimum=4 within each exact cohort; three independent channels
    # are corroboration for triage, NOT statistical power or a causal finding.
    candidates = []
    for topic, words in (('PRAYER_AND_CONTROL', {'prayer','pray','worry','anxiety'}),
                         ('GRATITUDE_WITHOUT_DENIAL', {'gratitude','grateful','thankful','thanks'})):
        favorable = []; contrary = []; channels = set()
        for group in groups:
            matches = [m for m in group['members'] if set(re.findall(r'[a-z]+',
                str(evidence[m['snapshot_id']]['payload'].get('title', '')).lower())) & words]
            winners = [m for m in matches if m['kind'] == 'WINNER']
            if winners:
                channels.add(group['channel_id']); favorable.extend(winners)
            contrary.extend(m for m in matches if m['kind'] != 'WINNER')
        if len(channels) >= 3:
            # Relative ranking stays within each channel/age, never pool views.
            score = sum(m['relative_velocity'] or 0 for m in favorable) / len(favorable)
            candidates.append((score, topic, favorable, contrary, sorted(channels)))
    if not candidates:
        raise PermissionError('CURRENT_AUDIO_RESEARCH_INSUFFICIENT_COMPARABLE_CHANNELS')
    _, topic, favorable, contrary, channels = sorted(candidates, key=lambda x:(-x[0],x[1]))[0]
    if topic == baseline.get('topic'):
        raise PermissionError('CURRENT_AUDIO_RESEARCH_NO_NEW_SUBSTANTIVE_TOPIC')
    if source.read_bytes() != raw or config_path.read_bytes()!=config_raw:
        raise PermissionError('current audio research changed during modeling')
    result = {'version':'heroverse-current-audio-research-v1', 'topic':topic,
        'channel_id':CHANNEL_ID, 'language':'en-US', 'baseline':baseline,
        'inputs':[{'path':source.relative_to(root).as_posix(),
                   'sha256':'sha256:'+hashlib.sha256(raw).hexdigest()},
                  {'path':'config/current_audio_research.json',
                   'sha256':'sha256:'+hashlib.sha256(config_raw).hexdigest()}],
        'cohorts':cohorts, 'supporting_channels':channels,
        'favorable':favorable, 'contrary':contrary,
        'evidence_class':'CALCULATED_PUBLIC_TITLE_DEMAND_HYPOTHESIS',
        'limitations':['Public titles do not measure audio fidelity, actual audience country or RPM.',
            'Cross-channel corroboration is triage, not learned causal performance.',
            'The original musical bed is held constant; this does not certify catalogue authenticity.'],
        'authority':{'quality':False,'render':False,'publication':False}}
    result['model_id'] = 'audio-research-' + hashlib.sha256(
        json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    return result


def read_current_audio_research(root: Path, binding: dict[str, str]) -> dict[str, Any]:
    root = root.resolve()
    if not isinstance(binding,dict) or set(binding) != {'path','sha256'}:
        raise PermissionError('exact current research binding required')
    path = (root / binding['path']).resolve()
    if not path.is_relative_to(root / 'output/market'):
        raise PermissionError('research binding escaped market root')
    raw = path.read_bytes()
    if 'sha256:'+hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise PermissionError('current research external anchor diverged')
    model = json.loads(raw)
    source = root / model['inputs'][0]['path']
    expected = build_current_audio_research(root,source,baseline=model['baseline'])
    if model != expected or path.read_bytes() != raw:
        raise PermissionError('current research cannot reproduce its exact source/cohorts')
    return model


def build_researched_rest_editorial(model: dict[str, Any]) -> dict[str, Any]:
    """Original bounded editorial treatments, never a copied competitor script.

    Exhaustion requires a new evidenced treatment, not an endless template lane.
    Qualification is still performed on the real spoken/composed result.
    """
    from .creative_direction import build_christian_rest_editorial
    treatments = {
        'PRAYER_AND_CONTROL': (
            'Prayer Is Not Control | A Christian Reflection + Quiet Piano',
            'Prayer can make room for a responsible response without promising control over outcomes',
            ["Prayer is not a way to control tomorrow. From this Christian perspective, it is a way to face what matters without pretending every outcome belongs to us.",
             "Think of one uncertainty you keep trying to settle tonight. Naming it honestly is different from rehearsing it until you are exhausted. You can care deeply without claiming the power to guarantee what happens.",
             "For example, you can prepare a difficult conversation, but you cannot choose another person's response. You can ask for help and make a plan; prayer does not replace those actions. These are invitations to reflection, not advice about a diagnosis.",
             "Trust is not indifference. Sometimes the next faithful response is practical help, a boundary, or an apology. Sometimes it is admitting that tonight is not the time to solve the problem. Neither response needs a promise of a miracle to be meaningful.",
             "Our invitation is to release the demand for certainty, not the responsibility to care. After this reflection, the words stop and the original quiet piano leaves room for your own prayer. You are free to leave when you need to."]),
        'GRATITUDE_WITHOUT_DENIAL': (
            'Gratitude Without Pretending | A Christian Reflection + Quiet Piano',
            'Gratitude can notice what is good without denying what still hurts',
            ["Gratitude does not require pretending everything is fine. A Christian reflection can make room for thankfulness and grief in the same evening, without treating either as a failure of faith.",
             "Consider a kindness you received today, however small. You can name it without using it to dismiss a disappointment. You do not owe anyone a cheerful performance before you are allowed to rest.",
             "A friend might bring a meal while a difficult problem remains unresolved. The meal matters; the problem still matters. Being thankful for the care is not a claim that the pain was necessary or good. This is an example, not a judgment of your circumstances.",
             "Gratitude can also lead to a response: offering thanks, asking for support, or sharing what you have. It is not an obligation to accept mistreatment. An honest boundary and a thankful heart need not compete.",
             "The perspective we offer is simple: notice a gift without erasing a wound. These opening words will now give way to original quiet piano for your own prayer and reflection. You do not need to stay for the whole session to take part."])}
    if model.get('version') != 'heroverse-current-audio-research-v1' or model.get('topic') not in treatments:
        raise PermissionError('researched editorial requires a compatible topic model')
    title, angle, texts = treatments[model['topic']]
    value = build_christian_rest_editorial()
    value.update(version='heroverse-researched-rest-editorial-v1',title=title,angle=angle,
        evidence_class='ORIGINAL_INTERPRETATION_WITH_PUBLIC_DEMAND_HYPOTHESIS',
        research_model_id=model['model_id'])
    value['sections'] = [{'role':s['role'],'text':text} for s,text in zip(value['sections'],texts)]
    value['full_text'] = ' '.join(texts)
    return value


def read_audio_preregistration(root: Path, research: dict[str,str], recipe: dict[str,str]) -> dict[Path,bytes]:
    """Reopen the sealed proposal/recipe links before native preparation or QA."""
    root=root.resolve();model_path=(root/research['path']).resolve()
    path=model_path.parent/'preregistration.json';raw=path.read_bytes();value=json.loads(raw)
    if value.get('research')!=research or value.get('recipe')!=recipe or value.get('variable')!='TOPIC_ANGLE':
        raise PermissionError('researched audio preregistration bindings diverged')
    protocol=(root/value['protocol']).resolve()
    if not protocol.is_relative_to(root/'output/production'):
        raise PermissionError('researched protocol escaped current production evidence')
    protocol_raw=protocol.read_bytes();proposal=json.loads(protocol_raw)
    if ('sha256:'+hashlib.sha256(protocol_raw).hexdigest()!=value['protocol_hash']
            or proposal.get('status')!='READY_TO_PREREGISTER'
            or proposal.get('treatment',{}).get('variable')!='TOPIC_ANGLE'):
        raise PermissionError('researched audio preregistered proposal changed')
    captured=datetime.fromisoformat(json.loads(model_path.read_bytes())['cohorts']['cutoff_at'].replace('Z','+00:00'))
    registered=datetime.fromisoformat(value['created_at'].replace('Z','+00:00'))
    if registered.tzinfo is None or registered<captured:
        raise PermissionError('researched audio preregistration predates its evidence')
    if path.read_bytes()!=raw or protocol.read_bytes()!=protocol_raw:
        raise PermissionError('researched audio preregistration changed during capture')
    return {path:raw,protocol:protocol_raw}


def run_current_audio_research_production(root: Path, *, package_relative: Path,
        current_bindings: dict[str, Any], expected_release_hash: str,
        snapshot_reference: str | None) -> dict[str, Any]:
    """Current manager's research -> modeling -> native audio preparation lane.

    One exact transactional job per released baseline. No upload/render/release
    is called here. Partial work is preserved and never blindly regenerated.
    """
    from .phase6_intelligence import materialize_current
    from .phase6_asset_residency import _write_immutable
    from .queue_phase6 import TransactionalQueue
    from .creative_direction import read_christian_rest_music_inputs, build_christian_rest_music_recipe
    from .render_creative_v3_phase5 import prepare_christian_rest_music
    from .observatory.collectors import PublicChannel, collect_channel
    from .production_capacity import ResourceWait
    root=root.resolve(); relative=Path(package_relative)
    if (root/'output/runtime/gestor-central/PAUSE').exists():
        return {'status':'PAUSED','render_authorized':False,'publication_authorized':False}
    if not snapshot_reference:
        return {'status':'WAITING_FOR_CURRENT_OWNED_OBSERVATION'}
    if 'music_inputs' not in current_bindings:
        return {'status':'WAITING_FOR_COMPATIBLE_RESEARCHED_AUDIO_FORMAT'}
    _, diagnosis_path, protocol_path = materialize_current(root,package_relative=relative,
        current_bindings=current_bindings,expected_release_hash=expected_release_hash,
        snapshot_reference=snapshot_reference)
    diagnosis=_read(diagnosis_path); protocol=_read(protocol_path)
    if diagnosis['status'] != 'DIAGNOSED' or protocol['status'] != 'READY_TO_PREREGISTER':
        return {'status':'WAITING_FOR_ELIGIBLE_BASELINE'}
    if protocol['treatment']['variable'] != 'TOPIC_ANGLE':
        return {'status':'WAITING_FOR_JUSTIFIED_TOPIC_CHANGE','variable':protocol['treatment']['variable']}
    previous=read_christian_rest_music_inputs(root,package_relative=relative,
        recipe_binding=current_bindings['music_inputs']['recipe'])
    if 'editorial' not in previous['recipe']:
        return {'status':'WAITING_FOR_COMPATIBLE_RESEARCHED_AUDIO_FORMAT'}
    receipt=root/relative/'youtube-publication-receipt.json'
    receipt_hash='sha256:'+hashlib.sha256(receipt.read_bytes()).hexdigest()
    publication=_read(receipt)
    key=f"audio-researched-next:{publication['channel_id']}:{publication['video_id']}:{receipt_hash}"
    queue=TransactionalQueue(root)
    existing=[j for j in queue.snapshot()['jobs'] if j['idempotency_key']==key]
    if existing:
        job=existing[0]
    else:
        # Exact PCM allocation plus the existing reserve. Insufficient capacity
        # must not create a failed queue attempt or an endless resource retry.
        from .production_capacity import measure_local_resources
        samples=[measure_local_resources(root),measure_local_resources(root)]
        required=12*1024**3 + math.ceil(previous['recipe']['duration_ms']*48*4*1.25+44)
        if any(s['available_ram_bytes']<1536*1024**2 or s['output_free_bytes']<required for s in samples):
            return {'status':'RESOURCE_WAIT','required_disk_bytes':required,'samples':samples}
        payload={'baseline_package':relative.as_posix(),'publication_receipt_hash':receipt_hash,
                 'snapshot_reference':snapshot_reference,'diagnosis':diagnosis_path.relative_to(root).as_posix(),
                 'diagnosis_hash':'sha256:'+hashlib.sha256(diagnosis_path.read_bytes()).hexdigest(),
                 'protocol':protocol_path.relative_to(root).as_posix(),
                 'protocol_hash':'sha256:'+hashlib.sha256(protocol_path.read_bytes()).hexdigest()}
        job=queue.enqueue(idempotency_key=key,operation_id='heroverse-audio-static-longform-v1',
            channel_id=CHANNEL_ID,task_type='PREPARE_CURRENT_RESEARCHED_AUDIO',payload=payload,max_attempts=1)
    payload=job['payload']
    def unchanged():
        for label in ('diagnosis','protocol'):
            if 'sha256:'+hashlib.sha256((root/payload[label]).read_bytes()).hexdigest()!=payload[label+'_hash']:
                raise PermissionError('preregistered audio baseline changed')
        if 'sha256:'+hashlib.sha256(receipt.read_bytes()).hexdigest()!=payload['publication_receipt_hash']:
            raise PermissionError('researched audio publication baseline changed')
    unchanged()
    if job['state']=='SUCCEEDED':
        cp=job['checkpoint']; model=read_current_audio_research(root,cp['research_binding'])
        from .qa_phase5 import verify_rest_music_source
        verify_rest_music_source(root,package_relative=Path(cp['package_relative']),
            recipe_binding=cp['recipe_binding'],source_binding=cp['source_binding'])
        return {'status':'PREPARED_AWAITING_NATIVE_QUALITY_AND_RIGHTS','job_id':job['job_id'],**cp,
                'render_authorized':False,'publication_authorized':False}
    if job['state']!='PENDING':
        return {'status':'BLOCKED_EXISTING_PREPARATION','job_id':job['job_id'],'state':job['state']}
    claimed=queue.claim_job(job['job_id'],worker_id='current-audio-research',
        expected_task_type='PREPARE_CURRENT_RESEARCHED_AUDIO',lease_seconds=1800)
    if claimed is None:
        return {'status':'PREPARATION_ALREADY_ACTIVE','job_id':job['job_id']}
    cp=dict(claimed['checkpoint'])
    directory=root/'output/market/current-audio'/job['job_id']
    try:
        source=directory/'snapshots.json'
        if not source.exists():
            if cp.get('collection_started'):
                raise PermissionError('research outcome unknown; no blind repeat')
            cp['collection_started']=True
            queue.checkpoint(job['job_id'],worker_id=claimed['lease_owner'],value=cp)
            config=_read(root/'config/current_audio_research.json')
            if config.get('channel_id')!=CHANNEL_ID or config.get('media_downloaded') is not False:
                raise PermissionError('current audio research policy/identity diverged')
            ids=[item['channel_id'] for item in config['references']]
            if len(ids)!=len(set(ids)) or len(ids)!=3:
                raise PermissionError('current audio research requires three distinct references')
            for item in config['references']:
                if (item['source_uri']!='https://www.youtube.com/channel/'+item['channel_id']
                        or item['role']!='FORMAT_REFERENCE' or type(item['max_videos']) is not int
                        or not 4<=item['max_videos']<=20):
                    raise PermissionError('current research source/limit differs from public metadata scope')
            captured=datetime.now(timezone.utc).isoformat()
            rows=[]
            for item in config['references']:
                if (root/'output/runtime/gestor-central/PAUSE').exists():
                    raise PermissionError('owner paused before research collection')
                rows.extend(collect_channel(job['job_id'],PublicChannel(**item),captured))
            _write_immutable(source,{'schema_version':'1.0.0','operation_id':job['job_id'],
                                     'captured_at':captured,'snapshots':rows})
        model=build_current_audio_research(root,source,baseline={'video_id':publication['video_id'],
            'publication_receipt_hash':receipt_hash,'topic':previous['recipe'].get('research',{}).get('model',{}).get('topic'),
            'editorial_angle':previous['recipe']['editorial']['angle']})
        model_path=directory/'model.json';_write_immutable(model_path,model)
        research_binding={'path':model_path.relative_to(root).as_posix(),
            'sha256':'sha256:'+hashlib.sha256(model_path.read_bytes()).hexdigest()}
        next_relative=Path('output/production')/('audio-researched-'+job['job_id'])
        package=root/next_relative
        for previous_path in (root/'output/production').glob('audio-researched-job-*/music_recipe.json'):
            if previous_path.parent != package and _read(previous_path).get('research',{}).get('model',{}).get('topic')==model['topic']:
                raise PermissionError('researched treatment already exists; no serial template production')
        bible_raw=(root/relative/'channel_style_bible.json').read_bytes()
        bible=package/'channel_style_bible.json';bible.parent.mkdir(parents=True,exist_ok=True)
        if bible.exists():
            if bible.read_bytes()!=bible_raw:raise PermissionError('researched style collision')
        else:
            with bible.open('xb') as stream:stream.write(bible_raw)
        recipe=build_christian_rest_music_recipe(duration_ms=previous['recipe']['duration_ms'],
            channel_model_hash=previous['recipe']['channel_model_hash'],
            style_bible_hash='sha256:'+hashlib.sha256(bible_raw).hexdigest(),
            recipe_version='heroverse-christian-rest-editorial-v5',
            research={'binding':research_binding,'model':model})
        recipe_path=package/'music_recipe.json';_write_immutable(recipe_path,recipe)
        recipe_binding={'path':str(recipe_path),'sha256':'sha256:'+hashlib.sha256(recipe_path.read_bytes()).hexdigest()}
        # Seal the actual hypothesis before invoking voice/music. Keep quality,
        # rights, render and publication authority separate from preparation.
        preregistration=directory/'preregistration.json'
        registration={'protocol':payload['protocol'],
            'protocol_hash':payload['protocol_hash'],'research':research_binding,
            'recipe':recipe_binding,'variable':'TOPIC_ANGLE',
            'created_at':datetime.now(timezone.utc).isoformat(), 'causality':'EXPLORATORY_NOT_LEARNED_RULE'}
        if preregistration.exists():
            registration['created_at']=_read(preregistration)['created_at']
        _write_immutable(preregistration,registration)
        unchanged()
        prepare_christian_rest_music(root,package_relative=next_relative,recipe_binding=recipe_binding)
        unchanged();read_current_audio_research(root,research_binding)
        source_path=package/'audio/rest_music_receipt.json'
        cp.update(package_relative=next_relative.as_posix(),research_binding=research_binding,
            recipe_binding=recipe_binding,source_binding={'path':str(source_path),
                'sha256':'sha256:'+hashlib.sha256(source_path.read_bytes()).hexdigest()})
        queue.succeed(job['job_id'],worker_id=claimed['lease_owner'],checkpoint=cp)
        return {'status':'PREPARED_AWAITING_NATIVE_QUALITY_AND_RIGHTS','job_id':job['job_id'],**cp,
                'render_authorized':False,'publication_authorized':False}
    except Exception as exc:
        queue.fail(job['job_id'],worker_id=claimed['lease_owner'],error=f'{type(exc).__name__}:{exc}',checkpoint=cp)
        if isinstance(exc,ResourceWait):
            return {'status':'RESOURCE_WAIT','job_id':job['job_id'],'detail':str(exc)}
        return {'status':'BLOCKED_RESEARCHED_PREPARATION','job_id':job['job_id'],
                'cause':f'{type(exc).__name__}:{exc}','render_authorized':False,'publication_authorized':False}
