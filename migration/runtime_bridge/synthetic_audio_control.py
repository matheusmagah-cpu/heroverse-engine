"""One explicitly selected inline-audio c01 diagnostic; original manager/guards.

Only the derived WAV and frozen neutral question reach Google. No media/base64
is logged, checkpointed, committed, or uploaded as an Actions artifact.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import wave

from gemini_public_av import canonical, digest, ProviderFailure, transport
from observe_public_av import ExistingObserverLedger
import synthetic_files_av as av

MODEL = 'gemini-3.5-flash-lite'
MODE = 'AUDIO_ONLY'
WAV = Path('synthetic-audio-control-output/control.wav')
PROOF = Path('synthetic-audio-control-output/proof.json')
PROMPT = Path('migration/diagnostics/synthetic-audio-c01/evaluator-prompt.txt')
PROMPT_SHA256 = '11a0e3ef81950db83c3a6229a8a48e0b57865b30e4f2f1c5494eb48074f8c30d'
WAV_SHA256 = 'ed00a94f25785cd763f1dc23f33447c317d0bea9cf8f0a11232d8d00f619a45b'
PCM16_SHA256 = '6434c16155d75c81933f30efabb4aea450718027f42db376119287b8dcf7f0f4'
DECODED_F32_SHA256 = '5efda979496abfda7a03ae21f255319f24524f58b4726f21666fa905bf5beae0'
# No expected answer, event count, timing reference or duration enters this schema.
RESPONSE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'status': {'type': 'string', 'enum': ['complete', 'partial', 'unknown'],
            'description': 'complete: contagem, rótulos e inícios determinados; caso contrário partial ou unknown.'},
        'count': {'type': ['integer', 'null'], 'minimum': 0,
            'description': 'Total de eventos sonoros discretos; null se não for possível determinar o total. Não estime para preencher.'},
        'events': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'label': {'type': ['string', 'null'],
                    'description': 'Som identificado pela evidência auditiva; null se não identificável.'},
                'start_seconds': {'type': ['number', 'null'], 'minimum': 0},
                'end_seconds': {'type': ['number', 'null'], 'minimum': 0}},
            'required': ['label', 'start_seconds', 'end_seconds']}},
        'uncertainty': {'type': ['string', 'null'],
            'description': 'Informação não determinável, inclusive finais desconhecidos; null quando não houver ressalva.'}},
    'required': ['status', 'count', 'events', 'uncertainty']}
GENERATION_CONFIG = {'candidateCount': 1, 'maxOutputTokens': 4096,
    'responseFormat': {'text': {'mimeType': 'application/json', 'schema': RESPONSE_SCHEMA}}}
SOURCE = {'kind':'SYNTHETIC_AUDIO_CONTROL','mode':MODE,'parent_mp4_sha256':av.CONTENT_SHA256,
    'content_sha256':WAV_SHA256,'pcm16_sha256':PCM16_SHA256,'duration_seconds':6,
    'mime_type':'audio/wav','size_bytes':576044,'sample_rate_hz':48000,'channels':1,'pcm_bits':16}
PRIOR = (
    ('synthetic-av:27ef45f42c98789a4a30b043669c2973bf3c1c8b7e45484f3e15ca99bafe9d27',
     '8b8bf5e574a2ea0ef2a5532c9887d0a6239670c5a18a638b01a4f6c83571aac3'),
    ('synthetic-av:7e431b2811680333a574d970c68b74d073421105b805234d7721be3af9fe04ba',
     '4f93d6556c3aeb90c3fdd38e8e7aae3b85919ad059a8c0d1bd3e1b32ef7f9edb'),
    ('synthetic-audio:7fe5d21cea9ccc07ac4d064ef371351b428b9d0ee4fc9ff617985d6de09f5a7a',
     'b6cb78f9767b38754888a4ad8e8d748e839065f37c5d84a1397ae6ed5598c7e5'))


def validate_media(wav, prompt):
    av.require(type(wav) is bytes and len(wav)==576044
        and hashlib.sha256(wav).hexdigest()==WAV_SHA256, 'EXACT_DERIVED_C01_WAV_REQUIRED')
    with wave.open(io.BytesIO(wav),'rb') as f:
        av.require((f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes(),f.getcomptype())
            ==(1,2,48000,288000,'NONE'), 'EXACT_SIX_SECOND_PCM_WAV_REQUIRED')
        pcm=f.readframes(288000)
    av.require(hashlib.sha256(pcm).hexdigest()==PCM16_SHA256, 'EXACT_C01_PCM16_REQUIRED')
    av.require(type(prompt) is bytes and hashlib.sha256(prompt).hexdigest()==PROMPT_SHA256,
        'EXACT_NEUTRAL_AUDIO_PROMPT_REQUIRED')
    return prompt.decode('utf-8')


def validate_prior_results():
    # Preserve all three earlier receipts and their eighteen seconds of debits.
    with sqlite3.connect(':memory:') as c:
        c.executescript(av.SQL.read_text())
        for key, expected_sha in PRIOR:
            request_hash=key.split(':',1)[1]
            path='migration/evidence/public-av-'+request_hash+'.json'
            raw=Path(path).read_bytes()
            av.require(hashlib.sha256(raw).hexdigest()==expected_sha,'PRIOR_AV_RECEIPT_CHANGED')
            row=c.execute('SELECT request_hash,day,seconds,state,receipt_path,receipt_hash '
                'FROM public_av_reservations WHERE key=?',(key,)).fetchone()
            av.require(row==(request_hash,'2026-10-16',6,'COMPLETED',path,expected_sha),
                'PRIOR_AV_DEBITS_MUST_REMAIN')


def prepare():
    # Reuse the exact manual/private boundary, current free-policy/fingerprint gate,
    # original neutral-prompt/capture provenance, historical ledger and claim checks.
    policy, _original_prompt_not_sent, api_key=av.prepare_runtime()
    av.require(policy['model']==MODEL,'EXACT_AUDIO_MODEL_REQUIRED')
    validate_prior_results()
    wav=WAV.read_bytes();prompt=PROMPT.read_bytes();validate_media(wav,prompt)
    proof=json.loads(PROOF.read_text())
    av.require(proof.get('operator_only') is True and proof.get('do_not_send_to_provider') is True
        and proof.get('source',{}).get('sha256')==av.CONTENT_SHA256
        and proof.get('source',{}).get('decoded_f32le_sha256')==DECODED_F32_SHA256
        and proof.get('output',{}).get('sha256')==WAV_SHA256
        and proof.get('output',{}).get('pcm_s16le_sha256')==PCM16_SHA256
        and proof.get('all_checks_passed') is True,
        'LOCAL_AUDIO_DERIVATION_PROOF_REQUIRED')
    return policy,prompt,api_key,wav,hashlib.sha256(PROOF.read_bytes()).hexdigest()


def request_identity(prompt):
    identity={'version':'synthetic-inline-audio-request-v1','mode':MODE,'source':SOURCE,
        'model':MODEL,'prompt_sha256':hashlib.sha256(prompt).hexdigest(),
        'generation_config':copy.deepcopy(GENERATION_CONFIG)}
    h=digest(identity)
    return 'synthetic-audio:'+h,h,identity


def build_request(wav,prompt):
    text=validate_media(wav,prompt)
    # This is the ONLY media encoding site. Never return/log/persist this body.
    return {'contents':[{'role':'user','parts':[
        {'inlineData':{'mimeType':'audio/wav','data':base64.b64encode(wav).decode('ascii')}},
        {'text':text}]}],'generationConfig':copy.deepcopy(GENERATION_CONFIG)}



def validate_structured_output(text):
    """Strict shape/completeness only. Never adjudicate perceptual correctness.

    Complete refers to count, labels and onsets. Unknown ends are permitted,
    but must be disclosed. No coercion, ordering repair, rounding or guessing.
    """
    def reject_constant(_value):
        raise PermissionError('STRUCTURED_NONFINITE_NUMBER')
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            av.require(key not in result,'STRUCTURED_DUPLICATE_KEY')
            result[key]=value
        return result
    try:
        report=json.loads(text,parse_constant=reject_constant,object_pairs_hook=unique_object)
    except (json.JSONDecodeError,TypeError,RecursionError):
        raise PermissionError('STRUCTURED_JSON_REQUIRED') from None
    av.require(type(report) is dict and set(report)=={'status','count','events','uncertainty'},
        'STRUCTURED_EXACT_FIELDS_REQUIRED')
    status,count,events,uncertainty=(report[k] for k in ('status','count','events','uncertainty'))
    av.require(type(status) is str and status in ('complete','partial','unknown'),
        'STRUCTURED_STATUS_REQUIRED')
    av.require(count is None or type(count) is int and count>=0,'STRUCTURED_COUNT_REQUIRED')
    av.require(type(events) is list,'STRUCTURED_EVENTS_REQUIRED')
    av.require(uncertainty is None or type(uncertainty) is str and bool(uncertainty.strip()),
        'STRUCTURED_UNCERTAINTY_REQUIRED')
    unknown_end=False;previous_start=None
    for event in events:
        av.require(type(event) is dict and set(event)=={'label','start_seconds','end_seconds'},
            'STRUCTURED_EVENT_FIELDS_REQUIRED')
        label,start,end=(event[k] for k in ('label','start_seconds','end_seconds'))
        av.require(label is None or type(label) is str and bool(label.strip()),
            'STRUCTURED_LABEL_REQUIRED')
        for value in (start,end):
            av.require(value is None or type(value) in (int,float) and 0<=value<=SOURCE['duration_seconds']
                and math.isfinite(value),'STRUCTURED_TIME_REQUIRED')
        av.require(start is None or end is None or start<=end,'STRUCTURED_TIME_ORDER_REQUIRED')
        av.require(start is None or previous_start is None or start>=previous_start,
            'STRUCTURED_EVENT_ORDER_REQUIRED')
        if start is not None:previous_start=start
        unknown_end=unknown_end or end is None
        if status=='complete':
            av.require(label is not None and start is not None,'STRUCTURED_COMPLETE_DATA_REQUIRED')
    if status=='complete':
        av.require(type(count) is int and count==len(events),'STRUCTURED_COMPLETE_COUNT_REQUIRED')
        av.require(not unknown_end or uncertainty is not None,'STRUCTURED_UNKNOWN_END_DISCLOSURE_REQUIRED')
        classification='COMPLETE_UNREVIEWED'
    else:
        av.require(uncertainty is not None,'STRUCTURED_ABSTENTION_REASON_REQUIRED')
        av.require(count is None or count>=len(events),'STRUCTURED_PARTIAL_COUNT_REQUIRED')
        classification='ABSTAINED'
    return report,classification


def analyze_audio(wav,prompt,*,api_key,policy,reserve,persist,proof_sha256,send=transport,clock=av.utcnow):
    now=clock();av.validate_policy(api_key,policy,now)
    av.require(callable(reserve) and callable(persist),'EXISTING_DURABLE_MANAGER_REQUIRED')
    validate_media(wav,prompt)
    av.require(re.fullmatch(r'[a-f0-9]{64}',proof_sha256) is not None,'AUDIO_PROOF_HASH_REQUIRED')
    key,h,identity=request_identity(prompt)
    claim=reserve(key,h,6,28800)
    av.require(claim.get('key')==key and claim.get('request_hash')==h,'MANAGER_CLAIM_BINDING_REQUIRED')
    if claim.get('status')=='REPLAY':
        receipt=claim.get('receipt',{})
        av.require(receipt.get('key')==key and receipt.get('request_hash')==h
            and receipt.get('request_identity')==identity and receipt.get('source')==SOURCE
            and receipt.get('review_status')=='NOT_REVIEWED'
            and all(receipt.get(k) is False for k in av.FALSE_AUTHORITY),'MANAGER_REPLAY_BINDING_REQUIRED')
        return receipt
    av.require(claim.get('status')=='NEW' and claim.get('durable') is True,
        'AUDIO_QUOTA_OR_UNRESOLVED_CLAIM_BLOCKED')
    receipt={'version':'heroverse-synthetic-inline-audio-v1','mode':MODE,'key':key,
        'request_hash':h,'request_identity':identity,'source':dict(SOURCE),'model':MODEL,
        'local_budget_seconds':6,'local_budget_cap_seconds':28800,'local_budget_timezone':'UTC',
        'google_rpd_reset_timezone':'America/Los_Angeles',
        'local_budget_basis':'REQUESTED_INTERVAL_NOT_PROVIDER_QUOTA_ASSERTION',
        'review_status':'NOT_REVIEWED','precision_verdict':'NOT_ADJUDICATED',
        'response_contract_status':'NOT_EVALUATED',
        'evidence_class':'MODEL_OUTPUT_NOT_INDEPENDENTLY_VERIFIED','automatic_retry':False,
        'generate_content_calls':0,'metadata_get_calls':0,'upload_calls':0,'count_tokens_calls':0,
        'media_or_base64_persisted':False,'local_derivation_proof_sha256':proof_sha256,
        'owner_request_message_id':av.OWNER_REQUEST,
        'key_binding':{'status':'MATCH','checked_at':now.isoformat()},**av.FALSE_AUTHORITY}
    try:
        av.validate_policy(api_key,policy,clock())
        payload=build_request(wav,prompt)
        receipt['wire_payload_sha256']=digest(payload)
        receipt['generate_content_calls']=1
        with av.wall_deadline(av.DEADLINE_SECONDS):response=send(payload,api_key,model=MODEL)
        av.require(type(response) is dict,'PROVIDER_RESPONSE_SHAPE_REJECTED')
        raw=canonical(response)
        av.require(api_key not in raw.decode(),'CREDENTIAL_ECHO_REJECTED')
        # A provider echo of the input media must never enter the evidence ledger.
        av.require(payload['contents'][0]['parts'][0]['inlineData']['data'][:64] not in raw.decode(),
            'MEDIA_ECHO_REJECTED')
        def has_media(value):
            if isinstance(value,dict):return any(k in ('inlineData','fileData') or has_media(v) for k,v in value.items())
            return isinstance(value,list) and any(has_media(v) for v in value)
        av.require(not has_media(response),'UNEXPECTED_MEDIA_OUTPUT')
        receipt.update(response_sha256=hashlib.sha256(raw).hexdigest(),provider_response=response)
        candidates=response.get('candidates',[])
        receipt['finish_reasons']=[c.get('finishReason') for c in candidates]
        av.require(len(candidates)==1 and candidates[0].get('finishReason')=='STOP','PROVIDER_BLOCKED_OR_TRUNCATED')
        parts=candidates[0].get('content',{}).get('parts',[])
        av.require(all(not any(k in p for k in ('toolCall','toolResponse','functionCall','executableCode','inlineData','fileData')) for p in parts),
            'UNEXPECTED_TOOL_OR_MEDIA_OUTPUT')
        output=''.join(p.get('text','') for p in parts if not p.get('thought',False))
        av.require(output.strip()!='','EMPTY_EVALUATOR_RESPONSE')
        details=response.get('usageMetadata',{}).get('promptTokensDetails',[])
        audio_tokens=[d['tokenCount'] for d in details if d.get('modality')=='AUDIO'
            and type(d.get('tokenCount')) is int and d['tokenCount']>=0]
        receipt.update(evaluator_response=output,
            reported_audio_input_tokens=sum(audio_tokens) if audio_tokens else None,
            audio_token_evidence='REPORTED_POSITIVE' if sum(audio_tokens)>0 else 'NOT_REPORTED_OR_ZERO_INCONCLUSIVE')
        receipt['response_contract_status']='INVALID'
        report,contract_status=validate_structured_output(output)
        receipt.update(status='SYNTHETIC_AUDIO_RESPONSE_AWAITING_REVIEW',
            response_contract_status=contract_status,structured_response=report)
    except Exception as error:
        receipt.update(status='FAILED_NO_AUTOMATIC_RETRY',failure_code=av.safe_failure_code(error))
    receipt['finished_at']=clock().isoformat();persist(receipt)
    return receipt


def preflight():
    try:prepare()
    except Exception as error:
        print(json.dumps(av.save_local_preflight_failure(error)));return 2
    print(json.dumps({'status':'AUDIO_ONLY_PREFLIGHT_PASSED','key_binding':'MATCH','provider_calls':0,
        'review_status':'NOT_REVIEWED',**av.FALSE_AUTHORITY}));return 0


def run_control(*,send=transport):
    try:policy,prompt,api_key,wav,proof_sha=prepare()
    except Exception as error:
        print(json.dumps(av.save_local_preflight_failure(error)));return 2
    ledger=ExistingObserverLedger(av.DB,os.environ['GITHUB_RUN_ID'])
    receipt=analyze_audio(wav,prompt,api_key=api_key,policy=policy,reserve=ledger.reserve,
        persist=ledger.persist,proof_sha256=proof_sha,send=send)
    print(json.dumps({'status':receipt['status'],'mode':MODE,'review_status':'NOT_REVIEWED',
        'generate_content_calls_in_receipt':receipt['generate_content_calls'],**av.FALSE_AUTHORITY}))
    return 0 if receipt['status']=='SYNTHETIC_AUDIO_RESPONSE_AWAITING_REVIEW' else 2


if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)==2 else ''
    if mode=='preflight':raise SystemExit(preflight())
    if mode=='run':raise SystemExit(run_control())
    if mode=='finalize':raise SystemExit(av.finalize_control())
    raise SystemExit('EXPLICIT_AUDIO_DIAGNOSTIC_MODE_REQUIRED')
