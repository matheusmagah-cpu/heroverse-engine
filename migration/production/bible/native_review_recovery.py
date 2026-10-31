#!/usr/bin/env python3
"""Recover native review evidence; optionally retry one proven transient no-output failure.

The existing workflow uses a temporary runner-owned CMS key to receive an encrypted
receipt via its existing request area. Only public certificates and fixed status
codes enter logs. Full provider replies remain in the private encrypted receipt.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError

MODEL = 'gemini-3.8-flash'
API = 'https://generativelanguage.googleapis.com'
RUBRIC = ('opening_and_promise', 'picture_quality', 'figure_and_background_integrity',
          'captions_readable_and_synced', 'audio_clarity_and_mix', 'pacing_and_visual_variety',
          'scripture_on_screen', 'policy_safe')
SOURCE_STEPS = ('Await exact-byte upload and read back provider hash',
                'Submit native audio and video review once',
                'Persist interaction ID before polling')
TERMINAL = {'failed', 'cancelled', 'incomplete', 'requires_action'}
RETRY_STEP = 'Submit one qualified transient-error retry'


class Blocked(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Blocked(code)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.chmod(0o600)
    temp.replace(path)


def subject_title(i):
    return f"native-review: plan={i['plan']} sha256={i['sha256']}"


def check_source(i, run, jobs):
    need(str(run.get('id')) == i.get('recover_submitted_run') and
         run.get('display_title') == subject_title(i) and
         run.get('path') == '.github/workflows/native-review.yml' and
         run.get('head_branch') == 'main' and run.get('run_attempt') == 1 and
         run.get('status') == 'completed' and run.get('conclusion') == 'failure',
         'RECOVERY_SOURCE_INVALID')
    need(len(jobs) == 1 and jobs[0].get('name') == 'review', 'RECOVERY_JOBS_INVALID')
    steps = {s['name']: s for s in jobs[0].get('steps', [])}
    for name in SOURCE_STEPS:
        need(steps.get(name, {}).get('status') == 'completed' and
             steps[name].get('conclusion') == 'success', 'RECOVERY_SUBMISSION_NOT_PROVEN')


def check_receipt(i, r):
    need(isinstance(r, dict) and r.get('version') == 'native-av-evidence-v1' and
         str(r.get('run_id')) == i['recover_submitted_run'] and
         r.get('plan') == i['plan'] and r.get('model') == MODEL and
         r.get('output_sha256') == i['sha256'] == r.get('provider_sha256') and
         type(r.get('byte_size')) is int and r['byte_size'] == int(i['byte_size']) and
         r.get('status') == 'SUBMITTED' and r.get('production_approved') is False,
         'RECOVERY_RECEIPT_BINDING')
    need(re.fullmatch(r'[A-Za-z0-9_-]{1,2048}', r.get('interaction_id', '')) is not None,
         'RECOVERY_INTERACTION_INVALID')
    need(re.fullmatch(r'files/[A-Za-z0-9_-]+', r.get('file_name', '')) is not None and
         r.get('file_uri') == API + '/v1beta/' + r['file_name'], 'RECOVERY_FILE_INVALID')
    need(re.fullmatch(r'[0-9a-f]{64}', r.get('prompt_sha256', '')) is not None and
         r.get('coverage') == {'video_sampling_fps':4, 'native_audio':True, 'full_input':True},
         'RECOVERY_COVERAGE_INVALID')
    # E236: the measured duration of the original submission's file, never a constant.
    need(type(r.get('duration_seconds')) in (int, float) and 0 < r['duration_seconds'] <= 3600,
         'RECOVERY_DURATION_INVALID')


def check_lease(i, legacy):
    ref = legacy.github_read('/git/ref/heads/claude/shared-executor-control')
    commit = legacy.github_read('/git/commits/' + ref['object']['sha'])
    marker = 'HEROVERSE_EXECUTOR_LEASE_V1\n'
    message = commit.get('message', '')
    need(message.startswith(marker), 'LEASE_INVALID')
    lease = json.loads(message[len(marker):])
    need(lease.get('schema') == 'heroverse-executor-lease-v1' and
         lease.get('state') == 'active' and lease.get('owner') in ('codex', 'claude') and
         lease.get('run_id') == i.get('lease_run_id') and bool(i.get('lease_run_id')) and
         datetime.fromisoformat(lease['expires_at'].replace('Z','+00:00')) > datetime.now(timezone.utc),
         'LEASE_REQUIRED')


def make_transport_key(root):
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    key, cert = root/'ingress.key', root/'ingress.pem'
    need(not key.exists() and not cert.exists(), 'INGRESS_ALREADY_EXISTS')
    subprocess.run(['openssl','req','-x509','-newkey','rsa:3072','-nodes',
                    '-keyout',str(key),'-out',str(cert),'-days','1',
                    '-subj','/CN=HeroVerse-ephemeral-native-readback'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    key.chmod(0o600)


def decrypt_receipt(root, cipher):
    need(0 < len(cipher) <= 32768, 'ENVELOPE_SIZE_INVALID')
    result = subprocess.run(['openssl','cms','-decrypt','-binary','-inform','DER',
                             '-recip',str(root/'ingress.pem'),'-inkey',str(root/'ingress.key')],
                            input=cipher, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    need(result.returncode == 0 and 0 < len(result.stdout) <= 16384, 'ENVELOPE_DECRYPT_FAILED')
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise Blocked('ENVELOPE_JSON_INVALID') from None


def prepare(i, root, legacy):
    need(os.environ.get('GITHUB_REPOSITORY') == 'matheusmagah-cpu/heroverse-engine' and
         os.environ.get('GITHUB_REF') == 'refs/heads/main' and
         os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and
         os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'RECOVERY_MAIN_FIRST_ATTEMPT_ONLY')
    need(re.fullmatch(r'[1-9][0-9]{0,24}', i.get('recover_submitted_run', '')) and
         not i.get('resume_before_inference'), 'RECOVERY_MODE_INVALID')
    check_lease(i, legacy)
    source = i['recover_submitted_run']
    run = legacy.github_read('/actions/runs/' + source)
    jobs = legacy.github_read('/actions/runs/' + source + '/jobs')['jobs']
    check_source(i, run, jobs)
    legacy.recipient_check(i)
    make_transport_key(root)
    save(root/'recovery.json', {'source_run_id':source, 'current_run_id':os.environ['GITHUB_RUN_ID'],
                               'source_head_sha':run['head_sha'], 'plan':i['plan'], 'sha256':i['sha256']})
    # This certificate is public; its matching private key never leaves runner.temp.
    print('RECOVERY_CERTIFICATE ' + ' '.join((root/'ingress.pem').read_text().splitlines()), flush=True)
    print('RECOVERY_ENVELOPE_PATH migration/requests/inflight/native-review-recovery-' +
          os.environ['GITHUB_RUN_ID'] + '.cms.b64', flush=True)


def receive(i, root, receipt, legacy):
    proof = json.loads((root/'recovery.json').read_text())
    need(proof['current_run_id'] == os.environ['GITHUB_RUN_ID'] and
         proof['source_run_id'] == i['recover_submitted_run'] and
         proof['plan'] == i['plan'] and proof['sha256'] == i['sha256'], 'RECOVERY_PROOF_INVALID')
    path = '/contents/migration/requests/inflight/native-review-recovery-' + os.environ['GITHUB_RUN_ID'] + '.cms.b64?ref=main'
    try:
        for _ in range(120):
            check_lease(i, legacy)
            try:
                obj = legacy.github_read(path)
            except HTTPError as exc:
                if exc.code != 404:
                    raise Blocked('RECOVERY_INGRESS_READ_FAILED') from None
                time.sleep(5)
                continue
            need(obj.get('type') == 'file' and obj.get('encoding') == 'base64' and
                 type(obj.get('size')) is int and 0 < obj['size'] <= 45000, 'ENVELOPE_FILE_INVALID')
            encoded = base64.b64decode(obj['content'].replace('\n',''), validate=True)
            cipher = base64.b64decode(encoded.strip(), validate=True)
            r = decrypt_receipt(root, cipher)
            check_receipt(i, r)
            need(r['prompt_sha256'] == hashlib.sha256(legacy.prompt(r['duration_seconds']).encode()).hexdigest(),
                 'RECOVERY_PROMPT_CHANGED')
            # Import only known fields; no caller-supplied score, response or approval survives.
            keys = ('version','run_id','plan','model','output_sha256','provider_sha256','byte_size',
                    'status','interaction_id','file_name','file_uri','prompt_sha256','coverage',
                    'duration_seconds')
            record = {k:r[k] for k in keys}
            record.update(recovery_run_id=os.environ['GITHUB_RUN_ID'], production_approved=False,
                          publication_ready=False)
            save(receipt, record)
            return
        raise Blocked('RECOVERY_ENVELOPE_NOT_RECEIVED')
    finally:
        (root/'ingress.key').unlink(missing_ok=True)


def record_readback(receipt, body, validator):
    r = json.loads(Path(receipt).read_text())
    need(len(body) <= 2_000_000, 'READBACK_TOO_LARGE')
    r.update(response_body_base64=base64.b64encode(body).decode(),
             response_sha256=hashlib.sha256(body).hexdigest(),
             readback_at=datetime.now(timezone.utc).isoformat(),
             production_approved=False, publication_ready=False)
    r.pop('owner_floor_met', None)
    r.pop('report', None)
    save(receipt, r)  # Preserve every provider reply BEFORE parsing, identity checks or validation.
    try:
        response = json.loads(body)
    except (ValueError, UnicodeError):
        raise Blocked('READBACK_JSON_INVALID') from None
    need(isinstance(response, dict), 'READBACK_JSON_INVALID')
    r.update(provider_response=response, provider_status=response.get('status'))
    save(receipt, r)
    need(response.get('id') == r['interaction_id'] and response.get('model') == MODEL,
         'READBACK_IDENTITY_MISMATCH')
    state = response.get('status')
    if state == 'in_progress':
        r['status'] = 'SUBMITTED'
    elif state in TERMINAL:
        r['status'] = 'PROVIDER_' + state.upper()
    elif state == 'completed':
        text = '\n'.join(c.get('text','') for s in response.get('steps',[]) if s.get('type')=='model_output'
                         for c in s.get('content',[]) if c.get('type')=='text')
        r.update(status='COMPLETE_UNVALIDATED', response_text=text, reviewed_at=r['readback_at'])
        save(receipt, r)
        try:
            report = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip()))
        except (ValueError, TypeError):
            raise Blocked('REPORT_JSON_INVALID') from None
        try:
            validator(report)
        except Exception as exc:
            r.update(validation_error_type=type(exc).__name__, validation_error=str(exc)[:2000])
            save(receipt, r)
            raise Blocked('REPORT_VALIDATION_FAILED') from None
        r.update(status='EVIDENCE_COMPLETE', report=report,
                 owner_floor_met=report['overall'] >= 9.5 and all(report['scores'][k] >= 7 for k in RUBRIC))
    else:
        r['status'] = 'PROVIDER_STATUS_UNKNOWN'
    save(receipt, r)
    return r['status']


def check_remote_binding(r, response, i, key, legacy):
    # A restored receipt must match the provider's stored user input, not just caller metadata.
    parts = [c for s in response.get('steps',[]) if s.get('type')=='user_input' for c in s.get('content',[])]
    videos = [c for c in parts if c.get('type')=='video']
    texts = [c for c in parts if c.get('type')=='text']
    need(len(videos)==1 and videos[0].get('uri')==r['file_uri'] and
         len(texts)==1 and hashlib.sha256(texts[0].get('text','').encode()).hexdigest()==r['prompt_sha256'],
         'RECOVERY_PROVIDER_INPUT_MISMATCH')
    _, raw = legacy.request(API+'/v1beta/'+r['file_name'], key)
    f = json.loads(raw)
    need(f.get('name')==r['file_name'] and f.get('uri')==r['file_uri'] and
         f.get('displayName')=='review-master-'+i['sha256']+'-'+i['recover_submitted_run'] and
         legacy.provider_sha256(f.get('sha256Hash',''))==i['sha256'] and
         int(f.get('sizeBytes',0))==int(i['byte_size']), 'RECOVERY_PROVIDER_FILE_MISMATCH')
    need(legacy.provider_duration(f)==r['duration_seconds'], 'RECOVERY_PROVIDER_DURATION_MISMATCH')


def poll_saved(i, receipt, key, legacy, attempts=120):
    r = json.loads(Path(receipt).read_text())
    need(r.get('status')=='SUBMITTED' and r.get('output_sha256')==i['sha256'] and
         re.fullmatch(r'[A-Za-z0-9_-]{1,2048}',r.get('interaction_id','')), 'POLL_STATE_INVALID')
    for _ in range(attempts):
        try:
            _, body = legacy.request(API+'/v1beta/interactions/'+r['interaction_id'], key)
        except HTTPError as exc:
            raw = exc.read(2_000_001)
            need(len(raw)<=2_000_000, 'READBACK_TOO_LARGE')
            r.update(status='READBACK_HTTP_ERROR', provider_http_status=exc.code,
                     response_body_base64=base64.b64encode(raw).decode(),
                     response_sha256=hashlib.sha256(raw).hexdigest(), production_approved=False,
                     publication_ready=False)
            save(receipt,r)
            raise Blocked('RECOVERY_HTTP_ERROR') from None
        # Binding is required before a completed recovered answer can be validated, not before storing it.
        def validate(report):
            if i.get('recover_submitted_run'):
                check_remote_binding(r,json.loads(body),i,key,legacy)
            legacy.validate_report(report, r['duration_seconds'])
        status = record_readback(receipt,body,validate)
        if status != 'SUBMITTED':
            return status
        time.sleep(10)
    return 'SUBMITTED'


def check_modes(i):
    flag = i.get('retry_transient_once', 'false')
    need(flag in ('true', 'false', ''), 'RETRY_FLAG_INVALID')
    need(not (i.get('recover_submitted_run') and i.get('resume_before_inference')),
         'RECOVERY_MODE_INVALID')
    need(flag != 'true' or (i.get('recover_submitted_run') and not i.get('resume_before_inference')),
         'RETRY_REQUIRES_SUBMITTED_RECOVERY')


def retry_eligible(i, r):
    response = r.get('provider_response', {})
    errors = response.get('errors', []) if isinstance(response, dict) else []
    need(r.get('status') == 'PROVIDER_FAILED' and r.get('provider_status') == 'failed' and
         response.get('status') == 'failed' and response.get('id') == r.get('interaction_id') and
         response.get('model') == MODEL and r.get('output_sha256') == i['sha256'] and
         str(r.get('run_id')) == i['recover_submitted_run'] and
         not r.get('retry_count') and not r.get('prior_failure') and 'report' not in r and
         'response_text' not in r, 'RETRY_NOT_ELIGIBLE')
    need(isinstance(errors, list) and bool(errors) and
         all(isinstance(e, dict) and e.get('code') in ('INTERNAL', 'UNAVAILABLE') for e in errors),
         'RETRY_NOT_TRANSIENT')
    steps = response.get('steps')
    need(isinstance(steps, list) and bool(steps) and
         all(isinstance(step, dict) and step.get('type') == 'user_input' for step in steps),
         'RETRY_OUTPUT_OR_UNKNOWN_STEPS')


def check_retry_history(i, runs, current, jobs_for):
    for run in runs:
        if run.get('display_title') != subject_title(i) or str(run['id']) in (
                str(current), i['recover_submitted_run']):
            continue
        need(run.get('path') == '.github/workflows/native-review.yml' and
             run.get('status') == 'completed', 'RETRY_OTHER_RUN_UNRESOLVED')
        jobs = jobs_for(str(run['id']))
        need(len(jobs) == 1 and jobs[0].get('name') == 'review', 'RETRY_HISTORY_AMBIGUOUS')
        steps = {step['name']: step for step in jobs[0].get('steps', [])}
        original = steps.get('Submit native audio and video review once', {})
        retry = steps.get(RETRY_STEP)
        need(original.get('status') == 'completed' and original.get('conclusion') == 'skipped' and
             (retry is None or (retry.get('status') == 'completed' and retry.get('conclusion') == 'skipped')),
             'RETRY_ALREADY_ATTEMPTED_OR_UNKNOWN')


def qualify_retry(i, receipt, legacy):
    check_modes(i)
    need(i.get('retry_transient_once') == 'true', 'RETRY_NOT_REQUESTED')
    check_lease(i, legacy)
    r = json.loads(Path(receipt).read_text())
    retry_eligible(i, r)
    key = legacy.free_key(i)  # Existing fresh cost proof; historical GET binding is insufficient for a POST.
    check_remote_binding(r, r['provider_response'], i, key, legacy)
    page = 1
    while True:
        runs = legacy.github_read('/actions/workflows/native-review.yml/runs?per_page=100&page=' + str(page))['workflow_runs']
        check_retry_history(i, runs, os.environ['GITHUB_RUN_ID'],
                            lambda rid: legacy.github_read('/actions/runs/' + rid + '/jobs')['jobs'])
        if len(runs) < 100:
            break
        page += 1
    r['retry_qualification'] = {'run_id': os.environ['GITHUB_RUN_ID'],
                                'response_sha256': r['response_sha256'],
                                'at_unix': time.time()}
    save(receipt, r)


def submit_retry(i, receipt, legacy):
    check_modes(i)
    need(i.get('retry_transient_once') == 'true' and os.environ.get('GITHUB_RUN_ATTEMPT') == '1',
         'RETRY_NOT_FIRST_ATTEMPT')
    check_lease(i, legacy)
    legacy.free_key(i)  # Recheck immediately before the one provider mutation.
    r = json.loads(Path(receipt).read_text())
    retry_eligible(i, r)
    proof = r.get('retry_qualification', {})
    need(proof.get('run_id') == os.environ['GITHUB_RUN_ID'] and
         proof.get('response_sha256') == r.get('response_sha256') and
         0 <= time.time() - proof.get('at_unix', 0) <= 300, 'RETRY_QUALIFICATION_REQUIRED')
    r['prior_failure'] = {key: r[key] for key in (
        'interaction_id', 'provider_response', 'response_body_base64', 'response_sha256', 'readback_at')}
    r.update(status='FILE_READY', retry_count=1, retry_run_id=os.environ['GITHUB_RUN_ID'],
             production_approved=False, publication_ready=False)
    for key in ('provider_response', 'provider_status', 'response_body_base64', 'response_sha256',
                'readback_at', 'retry_qualification'):
        r.pop(key, None)
    save(receipt, r)
    # submit() writes SUBMIT_UNCERTAIN before exactly one POST and saves the returned identity.
    # No upload, different file, model, prompt, score or exception-driven retry is introduced.
    legacy.submit(i, receipt)


def main():
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import native_review as legacy
    phase = sys.argv[1] if len(sys.argv)>1 else ''
    root = Path(os.environ['RUNNER_TEMP'])/'native-review'
    receipt = root/'receipt.json'
    try:
        i = legacy.inputs()
        check_modes(i)
        if phase=='options':
            pass
        elif phase=='qualify-retry':
            qualify_retry(i,receipt,legacy)
        elif phase=='retry-submit':
            submit_retry(i,receipt,legacy)
        elif phase=='prepare':
            prepare(i,root,legacy)
        elif phase=='receive':
            receive(i,root,receipt,legacy)
        elif phase=='poll':
            if i.get('recover_submitted_run'):
                check_lease(i,legacy)
                key = os.environ.get('GEMINI_API_KEY','')
                proof = json.loads(i['free_tier_evidence'])
                need(key and proof.get('model')==MODEL and proof.get('tier')=='Free' and
                     proof.get('billing_account_linked') is False and
                     proof.get('api_key_sha256')==hashlib.sha256(key.encode()).hexdigest(), 'RECOVERY_KEY_BINDING')
            else:
                key = legacy.free_key(i)
            status = poll_saved(i,receipt,key,legacy)
            print('NATIVE_READBACK_'+status)
            return 0 if status=='EVIDENCE_COMPLETE' else 1
        else:
            raise Blocked('RECOVERY_PHASE_INVALID')
        print('NATIVE_RECOVERY_'+phase.upper()+'_COMPLETE')
        return 0
    except Exception as exc:
        print(str(exc) if isinstance(exc,Blocked) else 'NATIVE_RECOVERY_FAILED')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
