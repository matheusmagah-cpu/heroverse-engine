"""Read the exact current transport calibration; no encoder or master decode.

Native release readers are unchanged. This reader authenticates the new scoped
calibration evidence and preserves explicit lack of release authority.
"""
import argparse, hashlib, json, sys
from pathlib import Path
from datetime import datetime
import calibrate_transport_gop300 as controls

def verify(directory, binding_sha, native_root, policy_sha, producer):
    directory=Path(directory).resolve(); native_root=Path(native_root).resolve()
    anchor=directory/'bindings.json'
    if controls.sha(anchor)!=binding_sha:raise PermissionError('BINDING_CHANGED')
    policy=controls.read(directory/'policy.json');bundle=controls.read(anchor)
    if (controls.sha(directory/'policy.json')!=policy_sha
            or controls.sha(producer)!=policy['producer_sha256']
            or bundle['producer_sha256']!=policy['producer_sha256']):
        raise PermissionError('PREREGISTERED_POLICY_OR_PRODUCER_CHANGED')
    if policy['version']!='heroverse-gop300-calibration-policy-v2':raise PermissionError('POLICY_VERSION')
    result=controls.read(directory/'result.json')
    if not (datetime.fromisoformat(policy['registered_at'])<=datetime.fromisoformat(result['started_at'])
            <=datetime.fromisoformat(result['completed_at'])):raise PermissionError('POLICY_TIME_ORDER')
    if result['policy_sha256']!=policy_sha:raise PermissionError('RESULT_POLICY_CHANGED')
    recipe=controls.read(directory/'transport-recipe.json')
    if controls.sha(directory/'transport-recipe.json')!=policy['recipe_sha256']:
        raise PermissionError('TRANSPORT_RECIPE_CHANGED')
    source=controls.read(directory/'target-source-manifest.json')
    if controls.sha(directory/'target-source-manifest.json')!=policy['source_manifest_sha256']:
        raise PermissionError('TARGET_DOMAIN_CHANGED')
    target_domain=controls.domain(source['layout'])
    if result['domain']!=target_domain:raise PermissionError('RESULT_DOMAIN_CHANGED')
    rows=result['rows']
    if len(rows)!=8:raise PermissionError('CONTROL_COUNT')
    if len({row['encoded_sha256'] for row in rows})!=8:raise PermissionError('CONTROL_SOURCE_OVERLAP')
    if len({row['reference_sha256'] for row in rows})!=8:raise PermissionError('REFERENCE_SOURCE_OVERLAP')
    for index,row in enumerate(rows):
        sub=directory/f'control-{index}'
        command=controls.read(sub/'command.json');process=controls.read(sub/'process-result.json')
        if (controls.domain(command['layout'])!=target_domain
                or command['layout']['title']!=policy['controls'][index]['title']
                or row['reference_sha256']==policy['candidate_reference_sha256']):
            raise PermissionError('INDEPENDENT_SOURCE_DOMAIN_CHANGED')
        if (controls.sha(sub/'control.mp4')!=row['encoded_sha256']
                or controls.sha(sub/'reference.png')!=row['reference_sha256']
                or row['reference']!=f'control-{index}/reference.png'
                or command['source_reference_sha256']!=row['reference_sha256']
                or process['exit_code']!=0):raise PermissionError('ENCODE_OBSERVATION_CHANGED')
        argv=command['argv']
        start=argv.index('-c:v')
        if argv[start:-2]!=['-c:v','libx264','-profile:v','high','-level:v','4.0','-preset','medium',
                          '-qp','1','-g','300','-keyint_min','300','-sc_threshold','0','-threads','1']:
            raise PermissionError('ENCODER_DOMAIN_CHANGED')
        if (argv[argv.index('-vf')+1]!=recipe['video_profile']['native_filter']
                or argv[argv.index('-frames:v')+1]!='300'
                or argv[argv.index('-framerate')+1]!='30'
                or Path(argv[argv.index('-i')+1]).name!='input.png'
                or Path(argv[-1]).name!='control.mp4'):
            raise PermissionError('CODEC_FILTER_OR_POPULATION_CHANGED')
        if (sum(item['count'] for item in row['distinct_frames'])!=300
                or row['decoded_frames']!=300):raise PermissionError('DECODE_COVERAGE_CHANGED')
    opened=controls.reopen(directory,binding_sha,native_root)
    if not opened['separation_passed']:raise PermissionError('FAILED_CONTROL_SEPARATION')
    return opened | {'limits':{key:value['maximum_error'] for key,value in result['calibration'].items()},
        'domain':target_domain,'native_validator_approval_emitted':False,
        'native_validator_integration':'NOT_INSTALLED'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('directory','native-root','producer'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--binding-sha',required=True);parser.add_argument('--policy-sha',required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.native_root))
    print(json.dumps(verify(args.directory,args.binding_sha,args.native_root,args.policy_sha,args.producer),indent=2))
