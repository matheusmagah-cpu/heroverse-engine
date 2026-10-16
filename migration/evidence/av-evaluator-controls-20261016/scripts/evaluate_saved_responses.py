#!/usr/bin/env python3
"""Offline, source-bound adjudication of five saved responses. Never invokes a model.
AI-assistant-authored semantic annotations are transparent data, not human review; this program checks their quoted evidence,
locks them to response hashes, compares explicit claims and aggregates conservatively.
"""
import argparse, hashlib, json
from pathlib import Path


def load(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok: raise AssertionError(message)
def compare(expected,observed): return 'MATCH' if expected==observed else 'CONTRADICTION'
def emit(path,data,check):
    if check:
        require(load(path)==data,f'Receipt mismatch: {path.name}')
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def evaluate(root,check=False):
    freeze=load(root/'operator-only/pre-evaluation-freeze.json')
    frozen_checks=[]
    for name,expected in freeze['files'].items():
        actual=sha(root/name)
        require(actual==expected,f'Frozen input changed: {name}')
        frozen_checks.append({'file':name,'sha256':actual,'matches_frozen_hash':True})
    require(freeze['model_responses_received_at_recording'] is False,'Freeze must predate response collection')
    manifest=load(root/'operator-only/manifest.json')
    obs=load(root/'observations/ai-studio-observations.json')
    reviews=load(root/'operator-only/manual-adjudications.json')
    require(obs['trial_count']==obs['completed_response_count']==5,'Exactly five responses are required')
    require(obs['repeat_inference_count']==0,'Run must contain no repeated inference')
    require(obs['backend_ingestion_confirmed'] is False,'This receipt is for the unverified-ingestion run')
    require(len(list((root/'responses').glob('c??-response.json')))==5,'Unexpected response file count')
    require(len(reviews)==5,'Five factual annotations are required')
    require(freeze['recorded_at']<obs['completed_at_utc'],'Invalid timestamp ordering')
    cases=[]
    diagnostic_path=root/'observations/token-count-diagnostic.json'
    diagnostic=load(diagnostic_path)
    require(diagnostic['drive_access_granted'] is False,'No new Drive permission is part of this record')
    require(diagnostic['concrete_token_error_cause_exposed'] is False,'Diagnostic must not imply a known token error cause')
    for f in manifest['files']:
        case=Path(f['filename']).stem
        review=reviews[case]
        require(review.get('author_type')=='ai_assistant' and review.get('author_name')=='dot',f'{case}: AI authorship must be explicit')
        require(review.get('human_review_performed') is False and review.get('certified_human_review') is False,f'{case}: human review must not be asserted')
        response_path=root/review['response_file']
        require(sha(response_path)==review['response_sha256'],f'{case}: response changed after adjudication')
        response=load(response_path)
        require(response['file']==f['filename'],f'{case}: asset mismatch')
        require(response['model']==obs['model'],f'{case}: route model mismatch')
        require(response['state']=='Response ready',f'{case}: missing completed response')
        require(response['backend_ingestion_confirmed'] is False,f'{case}: ingestion mismatch')
        require(response['upload_warning']=='Token count failed',f'{case}: warning mismatch')
        require(response['local_player']=={'duration':6,'readyState':4,'error':None},f'{case}: local player mismatch')
        for modality in ['visual','audio','synchrony']:
            for quote in review[modality]['quoted_evidence']:
                require(quote in response['response'],f'{case}: missing evidence quote {quote!r}')
        truth_visual_count=len(f['video']['flash_start_seconds'])
        truth_audio_count=len(f['audio']['observed_tone_intervals_seconds'])
        truth_visual_kind='flash' if truth_visual_count else 'constant'
        truth_audio_kind='tone' if truth_audio_count else 'silence'
        visual={
            'expected':{'event_kind':truth_visual_kind,'event_count':truth_visual_count,'flash_start_seconds':f['video']['flash_start_seconds']},
            'reported':review['visual'],
            'change_presence_comparison':compare(truth_visual_count>0,review['visual']['event_count']>0),
            'event_kind_comparison':compare(truth_visual_kind,review['visual']['event_kind']),
            'event_count_comparison':compare(truth_visual_count,review['visual']['event_count'])}
        visual['target_events_comparison']='MATCH' if all(visual[k]=='MATCH' for k in ['event_kind_comparison','event_count_comparison']) else 'CONTRADICTION'
        if case=='c02':visual['scope_note']='Match is only for absence of temporal visual changes; it is not validation of every detail of the scene description.'
        audio={
            'expected':{'event_kind':truth_audio_kind,'event_count':truth_audio_count,'observed_tone_intervals_seconds':f['audio']['observed_tone_intervals_seconds'],
                        'decoded_all_samples_exactly_zero':f['audio']['decoded_all_samples_exactly_zero']},
            'reported':review['audio'],
            'sound_presence_comparison':compare(truth_audio_count>0,review['audio']['event_count']>0),
            'event_kind_comparison':compare(truth_audio_kind,review['audio']['event_kind']),
            'event_count_comparison':compare(truth_audio_count,review['audio']['event_count'])}
        audio['target_events_comparison']='MATCH' if all(audio[k]=='MATCH' for k in ['event_kind_comparison','event_count_comparison']) else 'CONTRADICTION'
        expected_relation='not_applicable'
        if truth_audio_count and truth_visual_count:
            shift=f['audio']['nominal_audio_shift_seconds']
            expected_relation='audio_late' if shift>0 else 'audio_early' if shift<0 else 'aligned'
        sync={'expected_relation':expected_relation,'reported':review['synchrony'],
              'literal_relation_label_comparison':compare(expected_relation,review['synchrony']['label']),
              'reference_audio_minus_flash_seconds':f['audio']['tone_onset_minus_flash_seconds']}
        if expected_relation=='not_applicable':
            sync['capability_result']='NOT_APPLICABLE'
            sync['scope_note']='No positive synchrony credit is possible: this control lacks paired transient audio/visual events.'
            if case=='c02':sync['scope_note']+=' Its stated absence of sound is contradicted by the source.'
        elif sync['literal_relation_label_comparison']=='CONTRADICTION':
            sync['capability_result']='CONTRADICTED'
        elif visual['target_events_comparison']!='MATCH' or audio['target_events_comparison']!='MATCH':
            sync['capability_result']='NOT_ESTABLISHED'
            sync['scope_note']='Matching the relation label is insufficient when the described paired events are absent from the source.'
        else:sync['capability_result']='MATCH_ON_CONTROL'
        ui_path=root/'observations'/f'{case}-ui-evidence.json'
        ui=load(ui_path)
        ui_text='\n'.join(stage['ui_text'] for stage in ui)
        sources={
            'response':{'file':review['response_file'],'sha256':sha(response_path)},
            'ui_evidence':{'file':str(ui_path.relative_to(root)),'sha256':sha(ui_path),
                           'stages':[stage['stage'] for stage in ui],
                           'warning_literal_present_in_saved_ui_excerpt':'Token count failed' in ui_text,
                           'response_ready_literal_present_in_saved_ui_excerpt':'Response ready.' in ui_text},
            'manifest':{'file':'operator-only/manifest.json','sha256':sha(root/'operator-only/manifest.json')},
            'run_observations':{'file':'observations/ai-studio-observations.json','sha256':sha(root/'observations/ai-studio-observations.json')}}
        if case=='c01':sources['ui_evidence']['coverage_note']='The saved c01 UI excerpt does not itself contain the upload warning; that warning is recorded in its response envelope and run observations.'
        if case=='c05':
            extra=root/'observations/c05-ui-result.txt'
            sources['ui_result_text']={'file':str(extra.relative_to(root)),'sha256':sha(extra)}
        receipt={
            'schema_version':1,'case_id':case,'asset_filename':f['filename'],'asset_sha256':f['sha256'],
            'source_interval_seconds':[0,6],'source_kind':'synthetic_control','inference_count_recorded_for_case':1,
            'author_type':review['author_type'],'author_name':review['author_name'],
            'human_review_performed':False,'certified_human_review':False,
            'ground_truth_basis':review['ground_truth_basis'],'adjudication_method':review['adjudication_method'],
            'visual':visual,'audio':audio,'synchrony':sync,
            'access':{'reported':review['reported_access'],'backend_ingestion':'NOT_VERIFIED',
                      'local_player':response['local_player'],'local_player_scope':'Browser playback/load evidence only; not proof of model receipt.',
                      'upload_warning':response['upload_warning'],'warning_causal_explanation':'UNKNOWN'},
            'extra_contradictions':review['extra_contradictions'],'review_note':review['notes'],
            'route_configuration_result':'NOT_QUALIFIED','causal_attribution':'UNDETERMINED',
            'generalization_to_model_family':'NOT_SUPPORTED','sources':sources}
        emit(root/'receipts'/f'{case}-receipt.json',receipt,check)
        cases.append(receipt)
    result={
        'schema_version':1,'route_configuration_result':'NOT_QUALIFIED','display_verdict':'ROTA/CONFIGURAÇÃO NÃO QUALIFICADA',
        'scope':'These five submitted synthetic controls in this UI route and recorded configuration only.',
        'model_label_observed':obs['model'],'interface':obs['interface'],'configuration':obs['fixed_configuration'],
        'backend_ingestion':'NOT_VERIFIED','causal_attribution':'UNDETERMINED','generalization_to_model_family':'NOT_SUPPORTED',
        'inference_count_recorded':5,'completed_response_count_recorded':5,'repeat_inference_count_recorded':0,
        'adjudication_author_type':'ai_assistant','adjudication_author_name':'dot',
        'human_review_performed':False,'certified_human_review':False,
        'semantic_adjudication':'AI-assisted interpretation of saved model outputs by dot; not human review.',
        'ground_truth_basis':'Objective deterministic AV measurements in the frozen synthetic-control manifest.',
        'additional_external_provider_inferences_used_for_adjudication':0,
        'token_count_diagnostic':{'file':'observations/token-count-diagnostic.json','sha256':sha(diagnostic_path),
                                 'cause_exposed':False,'drive_access_granted':False,
                                 'interpretation':'The separate history/Drive access blocker does not establish the cause of token count failure.'},
        'all_trials_warning':'Token count failed','local_player_scope':'duration=6, readyState=4 and error=null establish only local player loading.',
        'pre_evaluation_freeze':{'file':'operator-only/pre-evaluation-freeze.json','sha256':sha(root/'operator-only/pre-evaluation-freeze.json'),
                                 'recorded_at':freeze['recorded_at'],'all_frozen_hashes_match':True,'checks':frozen_checks,
                                 'timestamp_assurance':'Preserved local timestamped record; not an independently notarized timestamp.'},
        'capabilities':{
            'temporal_visual_target_events':{'qualification':'NOT_QUALIFIED','per_case':{r['case_id']:r['visual']['target_events_comparison'] for r in cases}},
            'audio_target_events':{'qualification':'NOT_QUALIFIED','per_case':{r['case_id']:r['audio']['target_events_comparison'] for r in cases}},
            'coarse_audiovisual_relation':{'qualification':'NOT_QUALIFIED','per_case':{r['case_id']:r['synchrony']['capability_result'] for r in cases}},
            'backend_channel_delivery':{'qualification':'NOT_VERIFIED','per_case':{r['case_id']:'NOT_VERIFIED' for r in cases}}},
        'aggregation_policy':'No average, overall accuracy, or compensating score. Every capability and every file remains separate.',
        'interpretation_limits':[
            'Factual comparisons are against the local submitted file, not proof of which media the backend received.',
            'Correct silence or constant-image answers alone do not prove access to their channels.',
            'A matching synchrony word attached to nonexistent events does not validate audiovisual synchronization.',
            'The warning may be relevant but its exact cause and causal role are unverified.',
            'Do not conclude that every Gemini model, API, configuration, or later run shares this result.'
        ],
        'execution_notes':[
            'Exactly five independent chats, one recorded submission and one completed response per file; no inference retries.',
            'The recorded order was c01 through c05; per-run renaming/randomization was recommended in the protocol but is not evidenced in this run.',
            'The c03 typing recovery occurred before submission; it is not recorded as an additional inference.',
            'No durable share URL or backend file-ingestion receipt was verified.',
            'Receipt generation was local only and did not contact the evaluator or reveal the answer key.'
        ],
        'case_receipts':[f'receipts/{r["case_id"]}-receipt.json' for r in cases],
        'run_completed_at_utc':obs['completed_at_utc']}
    emit(root/'receipts/evaluation-receipt.json',result,check)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--check',action='store_true')
    a=p.parse_args();result=evaluate(a.root,a.check)
    print(json.dumps({'receipt_verification':'PASS','route_configuration_result':result['route_configuration_result'],
        'backend_ingestion':result['backend_ingestion'],'inference_count_recorded':result['inference_count_recorded'],
        'repeat_inference_count_recorded':result['repeat_inference_count_recorded']},indent=2))
