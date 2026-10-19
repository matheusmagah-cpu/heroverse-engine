#!/usr/bin/env python3
"""Offline, report-only normalization of preserved audiovisual evidence.
No client imports, network, model execution, gate changes or inferred approvals.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

SECTIONS = ('opening','promise','script_beats','visuals','on_screen_text','audio','ending','packaging')
AUDIT_FIELDS = {
    'person_or_figure':'visuals','caption_box':'on_screen_text','persistent_cta':'on_screen_text',
    'cuts_per_min':'visuals','continuous_camera_motion':'visuals','viewer_directed_hook_5s':'opening',
    'scripture_ref_on_screen':'on_screen_text','spoken_outro_amen_cta':'ending',
    'recurring_refrain':'script_beats','gratitude_block':'script_beats',
}
THUMB_MEASURES = ('width','height','mean_luminance_0_255','mean_saturation_0_255','brightness','dominant_colours')


def read_source(path):
    """Hash exact source bytes, never a JSON reserialization."""
    raw=Path(path).read_bytes()
    data=json.loads(raw)
    return data, {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),
                  'source_date':data.get('date') if isinstance(data,dict) else None}


def canonical(data):
    return json.dumps(data,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n'


def coverage(start=None,end=None,scope='unknown',limitations=None):
    return {'start_seconds':start,'end_seconds':end,'scope':scope,
            'independently_verified':False,'limitations':limitations or []}


def source_ref(sources,kind,pointer,model=None,image_sha256=None):
    desc=copy.deepcopy((sources or {}).get(kind,{}))
    return {'source_kind':kind,'path':desc.get('path'),'sha256':desc.get('sha256'),
            'json_pointer':pointer,'source_date':desc.get('source_date'),'model':model,
            'image_sha256':image_sha256}


def observation(field,value,status,method,ref=None,span=None):
    unknown=value is None or (isinstance(value,str) and (not value.strip() or value.upper().startswith(('UNKNOWN','NOT VISIBLE','NOT_VISIBLE'))))
    return {'field':field,'value':None if unknown else copy.deepcopy(value),
            'status':'UNKNOWN' if unknown else status,'method':method,
            'evidence':[] if ref is None else [ref],'coverage':span or coverage()}


def conflicts(observations):
    grouped={}
    for row in observations:
        if row['status']!='UNKNOWN':grouped.setdefault(row['field'],[]).append(row)
    return [{'field':field,'values':[copy.deepcopy(r['value']) for r in rows],
             'evidence':[copy.deepcopy(r['evidence']) for r in rows],
             'resolution':'UNRESOLVED_SOURCE_DISAGREEMENT'}
            for field,rows in grouped.items() if len({canonical(r['value']) for r in rows})>1]


def thumbnail_observations(row,index,sources):
    output=[];base=f'/rows/{index}';image_hash=row.get('image_sha256')
    if row.get('status')!='measured':
        return [observation('thumbnail',None,'UNKNOWN','SOURCE_UNAVAILABLE',source_ref(sources,'thumbnails',base))]
    for field in THUMB_MEASURES:
        output.append(observation('thumbnail.'+field,row.get(field),'MEASURED','IMAGE_INSTRUMENT_REPORTED',
            source_ref(sources,'thumbnails',base+'/'+field,image_sha256=image_hash),coverage(scope='thumbnail_image')))
    facts=row.get('facts')
    if isinstance(facts,dict):
        for field,value in sorted(facts.items()):
            output.append(observation('thumbnail.'+field,value,'MODEL_REPORTED','MODEL_IMAGE_REPORT',
                source_ref(sources,'thumbnails',base+'/facts/'+field,row.get('facts_model'),image_hash),coverage(scope='thumbnail_image')))
        if isinstance(facts.get('main_text'),str) and facts['main_text'].strip():
            # This counts the reported string, not words independently observed in pixels.
            output.append(observation('thumbnail.text_words',len(facts['main_text'].split()),'MEASURED','REPORTED_TEXT_WHITESPACE_COUNT',
                source_ref(sources,'thumbnails',base+'/facts/main_text',row.get('facts_model'),image_hash),
                coverage(scope='reported_text_only',limitations=['Not an independent OCR or image-word verification.'])))
    else:
        output.append(observation('thumbnail.facts',None,'UNKNOWN','UNAVAILABLE',source_ref(sources,'thumbnails',base+'/facts')))
    return output


def build_card(structure,structure_audit,thumbnails,*,video_id,own_review=None,legacy_structure=None,sources=None):
    members=[(i,r) for i,r in enumerate(structure.get('evidence',[])) if r.get('video')==video_id]
    if len(members)!=1:raise ValueError('VIDEO_NOT_UNIQUELY_IN_COHORT')
    member_index,member=members[0]
    sections={name:[] for name in SECTIONS};limitations=[]
    def add(section,field,value,status,method,kind,pointer,span=None,model=None):
        sections[section].append(observation(field,value,status,method,source_ref(sources,kind,pointer,model),span))
    for i,row in enumerate(structure_audit.get('videos',[])):
        if row.get('id')!=video_id:continue
        for field,section in AUDIT_FIELDS.items():
            estimated=field=='cuts_per_min'
            add(section,field,row.get(field),'ESTIMATED' if estimated else 'OBSERVED',
                'MODEL_ESTIMATE_REPORTED' if estimated else 'VIDIQ_OBSERVATION_REPORTED',
                'structure_audit',f'/videos/{i}/{field}',coverage(limitations=['Source does not declare exact watched temporal coverage.']))
    for i,row in enumerate(thumbnails.get('rows',[])):
        if row.get('id')==video_id:sections['packaging'].extend(thumbnail_observations(row,i,sources))
    if own_review is not None:
        audit=own_review.get('audit')
        if own_review.get('video_id',own_review.get('pilot_id')) not in (None,video_id):
            limitations.append('OWN_REVIEW_IDENTITY_MISMATCH; no observations imported.')
        elif not isinstance(audit,dict) or audit.get('status')=='ERROR':
            limitations.append('OWN_REVIEW_AUDIT_MISSING_OR_ERROR; review PASS is not audit evidence.')
        elif own_review.get('video_id',own_review.get('pilot_id')) is None:
            limitations.append('OWN_REVIEW_IDENTITY_UNPROVEN; no audit attached to this video.')
        else:
            mapping={'first_30s':'opening','visuals':'visuals','on_screen_text':'on_screen_text','audio':'audio','structure':'script_beats','ending':'ending'}
            for field,section in mapping.items():
                span=coverage(0,30,'requested_window_not_verified',['Audit request samples image at0.5fps; coverage is not independently verified.']) if field=='first_30s' else coverage(scope='model_claimed_whole_video',limitations=['Requested whole-file report, not measured coverage.'])
                add(section,field,audit.get(field),'MODEL_REPORTED','PRODUCTION_AUDIT_MODEL_REPORT','own_review','/audit/'+field,span,audit.get('model'))
    if legacy_structure is not None:
        video=legacy_structure.get('video',{})
        if video.get('video_id')!=video_id:
            limitations.append('LEGACY_VIDEO_ID_MISMATCH; no observations imported.')
        else:
            for i,window in enumerate(legacy_structure.get('windows',[])):
                start,end=window.get('window_start_seconds'),window.get('window_end_seconds')
                span=coverage(start,end,'source_declared_window',['Model-reported coverage; no transcript copied.'])
                for field,section,modality in [('picture','visuals','visual_received'),('sound','audio','audio_received')]:
                    value=window.get(field) if window.get(modality) is True else None
                    if isinstance(value,dict):
                        for key,item in sorted(value.items()):
                            add(section,field+'.'+key,item,'MODEL_REPORTED','LEGACY_MODEL_WINDOW','legacy_structure',f'/windows/{i}/{field}/'+key,span,window.get('model'))
                    else:add(section,field,None,'UNKNOWN','LEGACY_MODEL_WINDOW','legacy_structure',f'/windows/{i}/{field}',span,window.get('model'))
                # Structural summaries only; never transcript or opening_words_verbatim.
                beats=[{k:b.get(k) for k in ('start_seconds','end_seconds','beat','content','device','emotion')} for b in window.get('beats',[])] if window.get('audio_received') is True else []
                add('script_beats','beats',beats or None,'MODEL_REPORTED','LEGACY_MODEL_WINDOW','legacy_structure',f'/windows/{i}/beats',span,window.get('model'))
            limitations.append('Legacy windows do not establish whole-video ending or fulfilled title promise.')
    for name,rows in sections.items():
        if not rows:rows.append(observation(name,None,'UNKNOWN','NO_SUPPORTED_SOURCE'))
    all_rows=[r for rows in sections.values() for r in rows]
    return {'version':'video-analysis-card-v1','report_only':True,'video_id':video_id,
            'structure_id':structure.get('id'),'structure_version':structure.get('version'),
            'cohort_role':member.get('role'),'channel':member.get('channel'),'breakout':member.get('breakout'),
            'identity_source':source_ref(sources,'structure',f'/evidence/{member_index}'),
            'sections':sections,'conflicts':conflicts(all_rows),'limitations':limitations,
            'complete':all(any(r['status']!='UNKNOWN' for r in rows) for rows in sections.values())}


def build_report(structure,structure_audit,thumbnails,sources=None):
    ids=[r['video'] for r in structure.get('evidence',[])]
    if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_COHORT_ID')
    cards=[build_card(structure,structure_audit,thumbnails,video_id=v,sources=sources) for v in ids]
    thumb_rows=[]
    for i,row in enumerate(thumbnails.get('rows',[])):
        observations=thumbnail_observations(row,i,sources)
        thumb_rows.append({'video_id':row.get('id'),'in_structure_cohort':row.get('id') in ids,
                           'observations':observations,'conflicts':conflicts(observations)})
    return {'version':'video-analysis-report-v1','report_only':True,'sources':copy.deepcopy(sources or {}),
            'cohort_counts':{role:sum(c['cohort_role']==role for c in cards) for role in ('winner','weak')},
            'cards':cards,'thumbnail_reconciliation':{'sample_size':len(thumb_rows),'rows':thumb_rows,
                'cohort_matched':sum(r['in_structure_cohort'] for r in thumb_rows),
                'conflict_rows':sum(bool(r['conflicts']) for r in thumb_rows),
                'unknown_observations':sum(o['status']=='UNKNOWN' for r in thumb_rows for o in r['observations']),
                'structure_thumbnail_label':structure.get('attributes',{}).get('thumbnail',{}).get('label'),
                'stale_unmeasured_label':structure.get('attributes',{}).get('thumbnail',{}).get('label')=='unmeasured' and any(row.get('status')=='measured' for row in thumbnails.get('rows',[])),
                'interpretation':'Descriptive reported sample only; no causal rule, CTR prediction or cohort promotion.'}}


def main():
    parser=argparse.ArgumentParser()
    for arg in ('structure','structure_audit','thumbnails','output'):parser.add_argument(arg)
    args=parser.parse_args();data={};sources={}
    for kind in ('structure','structure_audit','thumbnails'):data[kind],sources[kind]=read_source(getattr(args,kind))
    result=build_report(**data,sources=sources)
    if Path(args.output).resolve() in {Path(getattr(args,k)).resolve() for k in ('structure','structure_audit','thumbnails')}:
        raise ValueError('SOURCE_OVERWRITE_FORBIDDEN')
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(canonical(result))
    print(json.dumps({'cards':len(result['cards']),'cohort_counts':result['cohort_counts'],'thumbnail_sample':len(result['thumbnail_reconciliation']['rows'])}))


if __name__=='__main__':main()
