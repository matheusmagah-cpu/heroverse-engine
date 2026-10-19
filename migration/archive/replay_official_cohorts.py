"""Correct availability projection only from preserved official raw responses.

Never recollect, overwrite the observed artifact, or loosen original exclusions.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from collect_official_evidence import public_projection

def main():
    folder=Path(sys.argv[1]);root=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve()
    raw=(folder/'evidence.json').read_bytes();value=json.loads(raw);origin=[];videos={}
    for path in sorted((folder/'raw').glob('*-videos-*.json')):
        content=path.read_bytes();origin.append({'name':path.name,'sha256':hashlib.sha256(content).hexdigest()})
        for v in json.loads(content)['items']:
            if v['id'] in videos:raise PermissionError('RAW_VIDEO_DUPLICATE')
            videos[v['id']]=v
    rows=copy.deepcopy(value['market_snapshots'])
    for row in rows:
        if row['entity_type']!='VIDEO':continue
        v=videos[row['entity_id']]
        if (v['snippet']['channelId']!=row['channel_id'] or v['snippet']['title']!=row['payload']['title']
                or int(v['statistics']['viewCount'])!=row['payload']['view_count']):
            raise PermissionError('RAW_OBSERVATION_BINDING_DIVERGED')
        row['payload'].update(public_projection(v))
    sys.path.insert(0,str(root))
    spec=importlib.util.spec_from_file_location('heroverse_original_format_cohorts',root/'hero_engine/observatory/format_cohorts.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    out.mkdir(parents=True,exist_ok=False);cohorts={}
    for bucket in sorted({r['payload']['duration_stratum'] for r in rows if r['entity_type']=='VIDEO'}):
        subset=[r for r in rows if r['entity_type']=='CHANNEL' or r['payload']['duration_stratum']==bucket]
        path=out/(bucket+'.json');path.write_text(json.dumps({'schema_version':'1.0.0','operation_id':value['operation_id'],'captured_at':value['captured_at'],'snapshots':subset}))
        cohorts[bucket]=module.compile_format_cohorts(path)
    corrected=copy.deepcopy(value);corrected['market_snapshots']=rows;corrected['cohorts_by_duration']=cohorts
    corrected['projection_correction']={'kind':'RAW_PUBLIC_FIELDS_MAPPING_ONLY','observed_at':value['captured_at'],
        'original_evidence_sha256':hashlib.sha256(raw).hexdigest(),'raw_video_response_origins':origin,
        'original_cohort_module_sha256':hashlib.sha256((root/'hero_engine/observatory/format_cohorts.py').read_bytes()).hexdigest(),
        'network_calls':0,'observations_repeated':False,'original_exclusions_unchanged':True}
    (out/'evidence-normalized.json').write_text(json.dumps(corrected,sort_keys=True,ensure_ascii=False,allow_nan=False))
    print(json.dumps({k:[{'channel':g['channel_id'],'age_band':g['age_band'],'status':g['status'],'n':len(g['members'])} for g in v['groups']] for k,v in cohorts.items()}))

if __name__=='__main__':main()
