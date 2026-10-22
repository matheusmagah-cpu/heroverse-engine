#!/usr/bin/env python3
"""One isolated native review; reuse the exact Short, QA and editorial rubric.

No canonical writes, approval or publication. prepare -> durable STARTED artifact
-> infer -> result artifact. Default workflow mode remains a no-provider check.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shorts_review as sr
from shorts_006_plan import _qa_verdict, _review_verdict
from structure_mining import _strict_json, ReviewHTTPPolicy, ProviderFailure, canonical

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'gemini-3.8-flash'
ENDPOINT = sr.BASE + '/v1beta/interactions'
QUALIFICATION = 'short006-20261022-interactions-v1'
START_ARTIFACT = 'reviewer-qualification-start-' + QUALIFICATION
OBSERVATION = 'migration/evidence/reviewer-qualification/20261022-project-binding.json'
CREDENTIAL_POLICY = 'migration/evidence/gemini-free-runtime-policy.json'
MANIFEST = 'migration/production/pilot-006/shorts/shorts.json'
MANIFEST_SHA = 'cc8daa14d106a4e09fd9cede224a8edf2e9c6a903a13e9d5e02f909709a4a701'
MEDIA_SHA = 'd6a7dc7024f6660c87a93d87db6a55d4073048e05f4728c043b1fc70229566b4'
MEDIA_BYTES = 15369406
ASSET_ID = 662430977
MEDIA_NAME = 'pilot-006-short-00-sha256-' + MEDIA_SHA + '.mp4'
REPO = 'matheusmagah-cpu/heroverse-engine'
MEDIA_URL = 'https://github.com/' + REPO + '/releases/download/v0.0.0-cloud-assets-20261013/' + MEDIA_NAME


def require(value, reason):
    if not value:
        raise ValueError(reason)


def now():
    return datetime.now(timezone.utc)


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'UTC_REQUIRED')
    return result


def write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def validate_inputs(root, key, clock):
    raw = (root / OBSERVATION).read_bytes()
    observation = _strict_json(raw)
    require(observation['qualification_id'] == QUALIFICATION, 'QUALIFICATION_CHANGED')
    require(observation['credential_policy'] == CREDENTIAL_POLICY
            and observation['key_project_binding_verified'] is True, 'PROJECT_UNBOUND')
    require(observation['model'] == MODEL and observation['tier'] == 'FREE'
            and observation['billing_account_present'] is False, 'FREE_TIER_REQUIRED')
    start, expiry = utc(observation['observed_at']), utc(observation['expires_at'])
    require(start <= clock < expiry and expiry - start <= timedelta(hours=24), 'OBSERVATION_STALE')
    credential_policy = _strict_json((root / CREDENTIAL_POLICY).read_bytes())
    require(bool(key) and hashlib.sha256(key.encode()).hexdigest() == credential_policy['key_sha256'], 'KEY_MISMATCH')
    require(observation['qualification_budget'] == {'max_inference_requests': 1,
            'max_elapsed_seconds': 600, 'max_output_tokens': 4096}, 'BUDGET_CHANGED')
    manifest_raw = (root / MANIFEST).read_bytes()
    require(hashlib.sha256(manifest_raw).hexdigest() == MANIFEST_SHA, 'MANIFEST_CHANGED')
    manifest = _strict_json(manifest_raw)
    record = next(s for s in manifest['shorts'] if s['file'] == 'short-00.mp4')
    require(record['sha256'] == record['qa_output_sha256'] == MEDIA_SHA, 'QA_UNBOUND')
    require(_qa_verdict(record['qa'], 42.0) == 'PASS', 'RECORDED_QA_NOT_PASS')
    return observation, record, hashlib.sha256(raw).hexdigest()


def github_json(path, token):
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
          headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        return _strict_json(response.read(2_000_001))


def require_unused_reservation(token):
    data = github_json('/actions/artifacts?name=' + START_ARTIFACT + '&per_page=1', token)
    require(type(data.get('total_count')) is int and data['total_count'] == 0
            and data.get('artifacts') == [], 'QUALIFICATION_ALREADY_RESERVED')


def prepare(output, mode, environ=os.environ):
    require(mode in ('check', 'review'), 'INVALID_MODE')
    require(environ.get('GITHUB_REPOSITORY') == REPO and environ.get('GITHUB_REF') == 'refs/heads/main', 'MAIN_ONLY')
    require(environ.get('GITHUB_RUN_ATTEMPT') == '1', 'REPLAY_BLOCKED')
    require(re.fullmatch(r'[1-9][0-9]*', environ.get('GITHUB_RUN_ID', '')) is not None, 'RUN_ID_REQUIRED')
    require(re.fullmatch(r'[0-9a-f]{40}', environ.get('GITHUB_SHA', '')) is not None, 'CODE_SHA_REQUIRED')
    observation, record, observation_sha = validate_inputs(ROOT, environ.get('HERO_GEMINI_API_KEY', ''), now())
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / 'receipt.json').exists(), 'LOCAL_REPLAY_BLOCKED')
    receipt = {'qualification_id': QUALIFICATION, 'state': 'CHECKED', 'mode': mode,
               'started_at': now().isoformat(), 'run_id': environ['GITHUB_RUN_ID'],
               'run_attempt': 1, 'repository_sha': environ['GITHUB_SHA'],
               'project_observation_sha256': observation_sha, 'runtime_fingerprint_match': 'MATCH',
               'output_sha256': MEDIA_SHA, 'expected_bytes': MEDIA_BYTES, 'asset_id': ASSET_ID,
               'recorded_qa_reused': True, 'qa_reexecuted': False, 'renders': 0,
               'endpoint': ENDPOINT, 'model': MODEL, 'inference_requests': 0,
               'canonical_writes': 0, 'publish': False, 'production_route_activated': False}
    if mode == 'review':
        require_unused_reservation(environ.get('GH_TOKEN', ''))
        asset = github_json('/releases/assets/' + str(ASSET_ID), environ.get('GH_TOKEN', ''))
        require(asset.get('id') == ASSET_ID and asset.get('name') == MEDIA_NAME
                and asset.get('size') == MEDIA_BYTES and asset.get('state') == 'uploaded'
                and asset.get('digest') == 'sha256:' + MEDIA_SHA
                and asset.get('browser_download_url') == MEDIA_URL, 'ASSET_CHANGED')
        media = output / 'short-00.mp4'
        # Public release URL: never forward the GitHub token to download redirects.
        with urllib.request.urlopen(MEDIA_URL, timeout=60) as response:
            data = response.read(MEDIA_BYTES + 1)
        require(len(data) == MEDIA_BYTES and hashlib.sha256(data).hexdigest() == MEDIA_SHA, 'MEDIA_CHANGED')
        media.write_bytes(data)
        receipt['state'] = 'STARTED'
    write(output / 'receipt.json', receipt)
    print('Reviewer qualification prepared: ' + receipt['state'] + '; publish=false')
    return receipt


def json_schema(value):
    if isinstance(value, list):
        return [json_schema(x) for x in value]
    if isinstance(value, dict):
        return {k: v.lower() if k == 'type' and isinstance(v, str) else json_schema(v) for k, v in value.items()}
    return value


class InteractionInference:
    """Exactly one synchronous call. No fallback, retry, tools or stored interaction."""
    def __init__(self):
        self.response_evidence = None

    def __call__(self, payload, key, models, *, http_policy):
        policy = http_policy
        require(tuple(models) == (MODEL,) and not policy._trace, 'INFERENCE_REPLAY_OR_MODEL')
        parts = payload['contents'][0]['parts']
        require(len(parts) == 2 and parts[0]['fileData']['mimeType'] == 'video/mp4', 'FULL_VIDEO_REQUIRED')
        body = {'model': MODEL, 'input': [
            {'type': 'video', 'uri': parts[0]['fileData']['fileUri'], 'mime_type': 'video/mp4',
             'processing': {'type': 'static', 'fps': 1}},
            {'type': 'text', 'text': parts[1]['text']}],
            'generation_config': {'max_output_tokens': payload['generationConfig']['maxOutputTokens']},
            'response_format': {'type': 'text', 'mime_type': 'application/json',
                                'schema': json_schema(payload['generationConfig']['responseSchema'])},
            'store': False, 'background': False, 'stream': False}
        policy.stage('INTERACTIONS')
        entry = {'attempt': 1, 'started_at': now().isoformat(), 'http_status': None,
                 'outcome': 'TRANSPORT_ERROR', 'decision': 'STOP_FINAL', 'slept_seconds': 0.0}
        policy._trace.append(entry)
        req = urllib.request.Request(ENDPOINT, data=canonical(body), method='POST',
              headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
        try:
            with urllib.request.urlopen(req, timeout=policy.timeout()) as response:
                entry['http_status'] = response.status
                raw = response.read(4_000_001)
            policy.check()
            require(entry['http_status'] == 200 and len(raw) <= 4_000_000, 'HTTP_RESPONSE_INVALID')
            response = _strict_json(raw)
            require(response.get('model') == MODEL and response.get('status') == 'completed', 'RESPONSE_NOT_COMPLETED_OR_MODEL')
            blocks = [block for step in response.get('steps', []) if step.get('type') == 'model_output'
                      for block in step.get('content', []) if block.get('type') == 'text']
            require(len(blocks) == 1 and type(blocks[0].get('text')) is str, 'OUTPUT_SCHEMA')
            report = _strict_json(blocks[0]['text'])
            require(type(report) is dict and report.keys() == set(sr.RUBRIC) | {'overall', 'issues', 'strongest_moment'}, 'REPORT_SCHEMA')
            candidate = {**report, 'model': MODEL, 'output_sha256': MEDIA_SHA,
                         'status': 'PASS' if all(report[k] >= 7 for k in sr.RUBRIC) and report['overall'] >= 8 else 'FAIL'}
            _review_verdict(candidate, MEDIA_SHA)  # finite numbers, item gates, shape, model, exact hash
            usage = response.get('usage', {})
            require(type(usage) is dict, 'USAGE_SCHEMA')
            safe_usage = {k: v for k, v in usage.items() if k.startswith('total_') and type(v) is int and v >= 0}
            modalities = usage.get('input_tokens_by_modality', [])
            safe_usage['input_tokens_by_modality'] = [dict(modality=x['modality'], tokens=x['tokens'])
                for x in modalities if type(x) is dict and x.get('modality') in ('text', 'audio', 'video', 'image')
                and type(x.get('tokens')) is int and x['tokens'] >= 0]
            self.response_evidence = {'response_sha256': hashlib.sha256(raw).hexdigest(),
                                     'status': 'completed', 'model': MODEL, 'usage': safe_usage}
            entry.update(outcome='SUCCESS', decision='RETURN')
            return MODEL, report
        except urllib.error.HTTPError as error:
            entry.update(http_status=error.code, outcome='HTTP_ERROR')
            failure, _ = sr.review_provider_failure(error, key)
            raise failure from None
        except ProviderFailure:
            raise
        except Exception:
            if entry['http_status'] == 200:
                entry['outcome'] = 'UNPARSEABLE_MODEL_OUTPUT'
            raise ProviderFailure('UNPARSEABLE_MODEL_OUTPUT' if entry['http_status'] == 200 else 'PROVIDER_CALL_FAILED') from None
        finally:
            policy.observe()
            entry['elapsed_end_seconds'] = policy._elapsed


def infer(output, environ=os.environ):
    require(environ.get('GITHUB_REPOSITORY') == REPO and environ.get('GITHUB_REF') == 'refs/heads/main', 'MAIN_ONLY')
    receipt_path = output / 'receipt.json'
    receipt = _strict_json(receipt_path.read_bytes())
    require(receipt['state'] == 'STARTED' and receipt['mode'] == 'review'
            and receipt['qualification_id'] == QUALIFICATION
            and receipt['run_id'] == environ.get('GITHUB_RUN_ID')
            and receipt['repository_sha'] == environ.get('GITHUB_SHA')
            and environ.get('GITHUB_RUN_ATTEMPT') == '1', 'ATTEMPT_UNBOUND')
    # Atomic process claim. The workflow serializes runs and preserves STARTED
    # remotely BEFORE this phase; a new run sees the reservation and cannot call.
    fd = os.open(output / 'inference-started', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    key = environ.get('HERO_GEMINI_API_KEY', '')
    observation, record, observation_sha = validate_inputs(ROOT, key, now())
    require(observation_sha == receipt['project_observation_sha256'], 'OBSERVATION_CHANGED')
    media = output / 'short-00.mp4'
    require(media.stat().st_size == MEDIA_BYTES and sr.output_digest(media) == MEDIA_SHA, 'MEDIA_CHANGED')
    policy = ReviewHTTPPolicy(cutoff_utc=min(now() + timedelta(seconds=600), utc(observation['expires_at'])))
    inference = InteractionInference()
    try:
        review = sr.review(media, deepcopy(record), key, http_policy=policy, inference=inference)
        verdict = _review_verdict(review, MEDIA_SHA)
        require(verdict in ('PASS', 'FAIL'), 'REVIEW_INCOMPLETE')
        audit = policy.audit()
        require(audit['http_completion'] == 'COMPLETED' and audit['transport_attempts'][-1]['http_status'] == 200
                and audit['transport_attempts'][-1]['outcome'] == 'SUCCESS', 'HTTP_EVIDENCE_REQUIRED')
        receipt['review'] = review
        receipt['owner_floor_problems'] = sr.owner_quality_policy.check(review, MEDIA_SHA)
        receipt['state'] = 'REVIEWED'
        receipt['qualification_result'] = ('PASS_FOR_ISOLATED_MASTER' if not receipt['owner_floor_problems']
                                           else 'REJECTED_MASTER')
        if audit['cleanup_status'] != 'SUCCESS':
            receipt['qualification_result'] = 'CLEANUP_UNCONFIRMED'
    except Exception as error:
        receipt['review'] = sr.failure_record(error, media)
        receipt['state'] = 'NOT_REVIEWED'
    finally:
        receipt['http'] = policy.audit() if policy._started is not None else None
        receipt['inference_requests'] = len(policy._trace)
        receipt['response_evidence'] = inference.response_evidence
        receipt['completed_at'] = now().isoformat()
        receipt['publish'] = False
        if sr.output_digest(ROOT / MANIFEST) != MANIFEST_SHA or sr.output_digest(media) != MEDIA_SHA:
            receipt['state'] = 'INTEGRITY_ERROR'
            receipt.pop('review', None)
        write(receipt_path, receipt)
    print('Reviewer qualification: ' + receipt['state'] + '; publish=false')
    return receipt


if __name__ == '__main__':
    try:
        phase, output = sys.argv[1], Path(sys.argv[2])
        result = prepare(output, sys.argv[3]) if phase == 'prepare' else infer(output) if phase == 'infer' else None
        require(result is not None, 'INVALID_PHASE')
        sys.exit(0 if result['state'] == 'STARTED' or result.get('qualification_result') == 'PASS_FOR_ISOLATED_MASTER' else 1)
    except Exception as error:
        # No provider, credential or URL exception text in public runner logs.
        reason = str(error) if type(error) is ValueError and re.fullmatch(r'[A-Z_]+', str(error)) else type(error).__name__
        print('Reviewer qualification blocked: ' + reason)
        sys.exit(1)
