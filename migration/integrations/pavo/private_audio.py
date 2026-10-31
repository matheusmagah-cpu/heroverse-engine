#!/usr/bin/env python3
"""One private exact-WAV or approved-first-frame DRAFT, with encrypted receipts.

Only hashes, state and conversation IDs enter the existing shot-probe branches.
The caller uploads directly to Pavo; neither media nor storage URLs are public artifacts.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener
import wave

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / 'migration/production/bible'))
sys.path.insert(0, str(ROOT / 'migration/ops'))
import attachments
from client import NoRedirect, PavoError
import native_review
import quota
from video import PavoVideoClient

REFERENCE = 'migration/evidence/pavo/20261026/keeper/storyteller-ref.jpg'
REFERENCE_SHA = '575e726ffb4cb43faaad15bfa2aa7c6e022cb0d03678ace6da7e4c81b0c29c4a'
HOOK_FRAME = 'migration/production/bible/stills/genesis-09-s-voice.jpg'
HOOK_SHA = '8c3ef26c79c19d7b7d0acb2b825809fab104790d49dfa452e597cbf5b6711e19'
MANIFESTS = 'migration/integrations/pavo/private-inputs/'
WORKFLOW = 'pavo-private-audio.yml'
SHA = re.compile(r'[0-9a-f]{64}')
TERMINAL = {'COMPLETE', 'FAILED', 'BLOCKED'}


class Blocked(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Blocked(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate(m, reference_check=True):
    need(isinstance(m, dict) and m.get('version') in ('pavo-private-audio-v1', 'pavo-private-hook-v1'), 'MANIFEST_SCHEMA')
    hook = m['version'] == 'pavo-private-hook-v1'
    need(m.get('episode') == 'genesis-09-short' and
         m.get('shot') in (('s-voice',) if hook else ('k-insight', 'k-question', 'k-close')), 'SUBJECT_REFUSED')
    need(m.get('production_approved') is False and m.get('sound') is False and m.get('aspect_ratio') == '9:16', 'DRAFT_POLICY')
    need(isinstance(m.get('prompt'), str) and 20 <= len(m['prompt']) <= 4000, 'PROMPT_INVALID')
    need(type(m.get('seconds')) is int and 4 <= m['seconds'] <= 12, 'SECONDS_INVALID')
    if hook:
        need(set(m) == {'version', 'episode', 'shot', 'prompt', 'seconds', 'first_frame',
                        'first_frame_sha256', 'sound', 'aspect_ratio', 'production_approved'}, 'HOOK_FIELDS')
        need(m['seconds'] == 10 and m.get('first_frame') == HOOK_FRAME and
             m.get('first_frame_sha256') == HOOK_SHA, 'HOOK_BINDING')
        if reference_check:
            p = ROOT / HOOK_FRAME
            need(p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest() == HOOK_SHA, 'REFERENCE_CHANGED')
            r = json.loads(p.with_suffix('.json').read_text())
            score = (r.get('approved') or {}).get('score')
            need(r.get('repo_path') == HOOK_FRAME and r.get('sha256') == HOOK_SHA and
                 r.get('status') == 'APPROVED' and type(score) in (int, float) and math.isfinite(score) and
                 score >= 9.5, 'HOOK_REFERENCE_NOT_APPROVED')
        return m
    need(m.get('reference') == REFERENCE and m.get('reference_sha256') == REFERENCE_SHA, 'REFERENCE_REFUSED')
    need(type(m.get('audio_bytes')) is int and 44 < m['audio_bytes'] <= 15 * 1024 * 1024, 'AUDIO_SIZE_INVALID')
    need(isinstance(m.get('audio_sha256'), str) and SHA.fullmatch(m['audio_sha256']), 'AUDIO_HASH_INVALID')
    for key in ('audio_seconds', 'speech_seconds'):
        n = m.get(key)
        need(type(n) in (int, float) and math.isfinite(n) and 0 < n <= 12, 'DURATION_INVALID')
    need(2 <= m['audio_seconds'] <= 12 and m['speech_seconds'] <= m['audio_seconds'], 'DURATION_INVALID')
    need(.25 <= m['seconds'] - m['speech_seconds'] <= .65, 'SPEECH_PADDING')
    if reference_check:
        p = ROOT / REFERENCE
        need(p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest() == REFERENCE_SHA, 'REFERENCE_CHANGED')
        r = json.loads((ROOT / 'migration/production/characters/images/ch-keeper-talk.json').read_text())
        need(r.get('repo_path') == REFERENCE and r.get('sha256') == REFERENCE_SHA, 'REFERENCE_RECORD_CHANGED')
    return m


def check_audio(m, data):
    need(len(data) == m['audio_bytes'] and hashlib.sha256(data).hexdigest() == m['audio_sha256'], 'AUDIO_BYTES_CHANGED')
    try:
        with wave.open(io.BytesIO(data), 'rb') as f:
            need((f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getcomptype()) == (1, 2, 24000, 'NONE'), 'PCM_FORMAT')
            need(f.getnframes() / 24000 == m['audio_seconds'], 'PCM_DURATION')
            need(len(f.readframes(f.getnframes())) == f.getnframes() * 2, 'PCM_TRUNCATED')
    except (wave.Error, EOFError):
        raise Blocked('PCM_INVALID') from None


def upload_record(data):
    try:
        need(isinstance(data, dict), 'UPLOAD_SCHEMA')
        attachments.storage_url(data.get('public_url'))
        attachments.storage_url(data.get('upload_url'), signed=True)
        headers = data.get('required_headers') or {}
        need(isinstance(headers, dict), 'UPLOAD_HEADERS')
        for k, v in headers.items():
            need(isinstance(k, str) and k.lower() in ('content-type', 'content-md5', 'x-cos-content-sha1'), 'UPLOAD_HEADERS')
            need(isinstance(v, str) and len(v) <= 1024 and '\r' not in v and '\n' not in v, 'UPLOAD_HEADERS')
        return {'public_url': data['public_url'], 'upload_url': data['upload_url'], 'required_headers': headers}
    except attachments.TransferError:
        raise Blocked('UPLOAD_DESTINATION') from None


def prepare_upload(m, client):
    q = client._quote(m['seconds'], '9:16', 'omni_to_video', 1, [{'seconds': m['audio_seconds']}], False)
    need(q.get('zero_cost_confirmed') is True, 'ZERO_CREDIT_QUOTE_REQUIRED')
    data = client._video_json('upload', {'purpose': 'chat_attachment', 'content_type': 'audio/wav',
                                       'filename': m['shot'] + '-' + m['audio_sha256'][:16] + '.wav'})
    return upload_record(data), q


class PrivateVideoClient(PavoVideoClient):
    """Keep both attachment transfers on the already observed storage hosts."""
    def _video_json(self, route, body=None, job=None):
        data = super()._video_json(route, body, job)
        if route == 'upload':
            upload_record(data)
        return data


def initial_record(m, run_id):
    return {'version': 'pavo-private-audio-receipt-v1', 'request_sha256': digest(m), 'manifest': m,
            'episode': m['episode'], 'shot': m['shot'], 'run_id': str(run_id), 'state': 'CLAIMED',
            'created_at': datetime.now(timezone.utc).isoformat(), 'conversation_id': None,
            'production_approved': False, 'published': False}


def public_record(r):
    cid = r.get('conversation_id')
    gens = [] if cid is None else [{'conversation_id': cid, 'flags': ['NO_VIDEO'] if r['state'] == 'FAILED' else []}]
    return {'version': 'private-audio-probe-v1', 'episode': r['episode'], 'run_id': r['run_id'],
            'request_sha256': r['request_sha256'], 'state': r['state'], 'created_at': r['created_at'],
            'updated_at': datetime.now(timezone.utc).isoformat(), 'conversation_id': cid,
            'terminal_at': r.get('terminal_at'), 'retry_of': r.get('retry_of'),
            'submitted_at': r.get('submitted_at'),
            'production_approved': False, 'published': False,
            'shots': {r['shot']: {'clips': [{'generations': gens}]}}}


def require_new(records, request_sha256, retry_run=None, manifest=None):
    if manifest and manifest.get('version') == 'pavo-private-hook-v1':
        need(not retry_run, 'HOOK_RETRY_REFUSED')
        # The one approved hook slot is not a new request merely because its prompt/digest changes.
        need(not any(r.get('episode') == manifest['episode'] and manifest['shot'] in (r.get('shots') or {})
                     for r in records), 'HOOK_EXISTING_CLAIM_RECONCILE')
    matching = [r for r in records if r.get('request_sha256') == request_sha256]
    retry = None
    if retry_run:
        need(matching and all(r.get('version') == 'private-audio-probe-v1' and r.get('state') == 'FAILED'
                             and re.fullmatch(r'[1-9][0-9]{0,24}', str(r.get('conversation_id') or '')) for r in matching),
             'RETRY_REQUIRES_TERMINAL_FAILED_HISTORY')
        retry = max(matching, key=lambda r: datetime.fromisoformat(r['created_at']))
        need(retry.get('run_id') == retry_run, 'RETRY_SOURCE_NOT_LATEST')
        try:
            at = datetime.fromisoformat(retry['terminal_at'])
            need(at.tzinfo is not None and datetime.now(timezone.utc) - at >= timedelta(hours=3), 'RETRY_COOLDOWN')
        except (KeyError, TypeError, ValueError):
            raise Blocked('RETRY_TERMINAL_TIME_REQUIRED') from None
    for r in records:
        need(r.get('request_sha256') != request_sha256 or retry is not None, 'EXISTING_CLAIM_RECONCILE')
        if r.get('version') != 'private-audio-probe-v1':
            continue
        need(r.get('state') in TERMINAL, 'OTHER_PRIVATE_JOB_UNRESOLVED')
        if r.get('state') in ('FAILED', 'BLOCKED'):
            at = datetime.fromisoformat(r.get('terminal_at') or r['updated_at'])
            need(datetime.now(timezone.utc) - at >= timedelta(hours=3), 'PRIVATE_PROBE_COOLDOWN')
    return retry


def verify_retry(record, client):
    result = client.job(record['conversation_id'])
    need(result.get('conversation_id') == record['conversation_id'] and result.get('status') == 'failed'
         and result.get('videos') == [], 'RETRY_PROVIDER_NOT_TERMINAL_FAILED')


class RecordingGuard(quota.QuotaGuard):
    def __init__(self, path, receipt, persist):
        super().__init__(path, actions=None)
        self.receipt, self.persist = receipt, persist

    def submitted(self, conversation_id, units=quota.VIDEO_UNITS):
        # Existing generate_video invokes this after create and BEFORE its stream POST.
        self.receipt.update(conversation_id=conversation_id, state='SUBMITTING',
                            submitted_at=datetime.now(timezone.utc).isoformat())
        self.persist()  # Must be durable remotely or streaming never begins.
        super().submitted(conversation_id, units)


def poll_once(r, client):
    need(r.get('conversation_id') is not None, 'NO_ID_RECONCILE_CREATE')
    result = client.job(r['conversation_id'])
    r['provider_result'] = result
    status = result.get('status')
    r['state'] = 'COMPLETE' if status == 'completed' and result.get('videos') else (
        'FAILED' if status == 'failed' else 'BLOCKED' if status == 'blocked' else 'UNKNOWN')
    if r['state'] in TERMINAL and not r.get('terminal_at'):
        r['terminal_at'] = datetime.now(timezone.utc).isoformat()
    return r


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(data, f, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def git(*args, env=None):
    p = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, timeout=45, env=env)
    need(p.returncode == 0, 'PUBLIC_RECORD_PERSIST_FAILED')
    return p.stdout.strip()


def inputs():
    i = json.loads(os.environ['PRIVATE_AUDIO_INPUTS'])
    path = i.get('manifest', '')
    need(isinstance(path, str) and re.fullmatch(re.escape(MANIFESTS) + r'[a-z0-9-]+\.json', path), 'MANIFEST_PATH')
    p = ROOT / path
    need(p.is_file() and not p.is_symlink(), 'MANIFEST_PATH')
    m = validate(json.loads(p.read_text()))
    need(i.get('sha256') == digest(m), 'MANIFEST_DIGEST')
    need(i.get('plan') == 'migration/production/bible/plans/genesis-09-short.json', 'PLAN_REFUSED')
    need(not i.get('reconcile_run') or re.fullmatch(r'[1-9][0-9]{5,19}', i['reconcile_run']), 'RECOVERY_RUN_INVALID')
    need(not i.get('retry_run') or re.fullmatch(r'[1-9][0-9]{5,19}', i['retry_run']), 'RETRY_RUN_INVALID')
    need(not (i.get('retry_run') and i.get('reconcile_run')), 'RETRY_RECOVERY_CONFLICT')
    need(not (m['version'] == 'pavo-private-hook-v1' and i.get('retry_run')), 'HOOK_RETRY_REFUSED')
    return i, m


def lease(i):
    c = native_review.github_read('/commits/claude/shared-executor-control')
    msg = c.get('commit', {}).get('message', '')
    prefix = 'HEROVERSE_EXECUTOR_LEASE_V1\n'
    need(msg.startswith(prefix), 'EXECUTOR_LEASE_INVALID')
    r = json.loads(msg[len(prefix):])
    need(r.get('state') == 'active' and r.get('owner') in ('codex', 'claude') and
         r.get('run_id') == i.get('lease_run_id') and
         datetime.fromisoformat(r['expires_at'].replace('Z', '+00:00')) > datetime.now(timezone.utc), 'EXECUTOR_LEASE_REQUIRED')


def history_records():
    import base64
    found = []
    for page in range(1, 11):
        rows = native_review.github_read(f'/branches?per_page=100&page={page}')
        for b in rows:
            path = quota.probe_record_path(b['name'])
            if not path:
                continue
            try:
                item = native_review.github_read('/contents/' + path + '?ref=' + b['commit']['sha'])
            except HTTPError as e:
                if e.code == 404:
                    e.close(); continue
                raise
            r = json.loads(base64.b64decode(item['content']))
            if r.get('version') == 'private-audio-probe-v1':
                found.append(r)
        if len(rows) < 100:
            return found
    raise Blocked('HISTORY_INCOMPLETE')


def persist(r, receipt):
    atomic(receipt, r)
    path = f"migration/evidence/shots/{r['episode']}/{r['run_id']}.json"
    atomic(ROOT / path, public_record(r))
    branch = f"claude/shot-probe-{r['episode']}-{r['run_id']}"
    old = git('ls-remote', '--heads', 'origin', branch).split()
    if old:
        git('fetch', '--depth=1', 'origin', 'refs/heads/' + branch)
        parent = git('rev-parse', 'FETCH_HEAD')
        need(parent == old[0], 'CLAIM_CHANGED')
    else:
        parent = git('rev-parse', 'HEAD')
    # Only the public record enters this tree, even if other files are staged or private.
    env = dict(os.environ, GIT_INDEX_FILE=str(receipt.parent / 'public-record.index'))
    git('read-tree', parent, env=env)
    blob = git('hash-object', '-w', '--', path)
    git('update-index', '--add', '--cacheinfo', '100644,' + blob + ',' + path, env=env)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, '-p', parent, '-m', f"Record private Pavo DRAFT {r['run_id']} {r['state']}")
    git('push', 'origin', commit + ':refs/heads/' + branch)


def read_audio(url, m):
    req = Request(attachments.storage_url(url), method='GET')
    with build_opener(NoRedirect()).open(req, timeout=30) as response:
        need(response.status == 200, 'UPLOAD_NOT_READY')
        data = response.read(m['audio_bytes'] + 1)
    check_audio(m, data)
    return data


def cli(command):
    i, m = inputs()
    private = Path(os.environ['RUNNER_TEMP']) / 'pavo-private-audio'
    receipt = private / 'receipt.json'
    work = ROOT / '.episode' / ('private-audio-' + os.environ['GITHUB_RUN_ID'])
    if command == 'seal':
        if receipt.exists(): native_review.seal(i, receipt)
        return
    need(os.environ['GITHUB_REPOSITORY'] == 'matheusmagah-cpu/heroverse-engine' and
         os.environ['GITHUB_REF'] == 'refs/heads/main' and os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'MAIN_ONCE_ONLY')
    lease(i)
    need(not i.get('reconcile_run') or command in ('recover', 'poll'), 'RECOVERY_READ_ONLY')
    if command == 'claim':
        native_review.recipient_check(i)
        retry = require_new(history_records(), digest(m), i.get('retry_run'), manifest=m)
        if retry:
            verify_retry(retry, PrivateVideoClient())  # GET only, before the new durable claim.
        r = initial_record(m, os.environ['GITHUB_RUN_ID'])
        if retry: r['retry_of'] = retry['run_id']
        persist(r, receipt)
        return
    if command == 'recover':
        import base64
        source = i.get('reconcile_run')
        need(source, 'RECOVERY_RUN_REQUIRED')
        branch = f"claude/shot-probe-{m['episode']}-{source}"
        path = f"migration/evidence/shots/{m['episode']}/{source}.json"
        item = native_review.github_read('/contents/' + path + '?ref=' + branch)
        old = json.loads(base64.b64decode(item['content']))
        need(old.get('version') == 'private-audio-probe-v1' and old.get('request_sha256') == digest(m), 'RECOVERY_IDENTITY')
        need(re.fullmatch(r'[1-9][0-9]{0,24}', str(old.get('conversation_id') or '')), 'NO_ID_RECONCILE_CREATE')
        r = initial_record(m, source)
        r.update(created_at=old['created_at'], conversation_id=old['conversation_id'], state=old['state'],
                 terminal_at=old.get('terminal_at'), retry_of=old.get('retry_of'),
                 submitted_at=old.get('submitted_at'))
        atomic(receipt, r)
        return
    r = json.loads(receipt.read_text())
    need(r['request_sha256'] == digest(m) and r['run_id'] == (i.get('reconcile_run') or os.environ['GITHUB_RUN_ID']), 'RECEIPT_MISMATCH')
    need(not i.get('reconcile_run') or command == 'poll', 'RECOVERY_READ_ONLY')
    client = PrivateVideoClient()
    hook = m['version'] == 'pavo-private-hook-v1'
    if command == 'prepare':
        need(r['state'] == 'CLAIMED', 'EXISTING_UPLOAD_RECONCILE')
        if hook:
            q = client.quote_video(m['seconds'], '9:16', first_frame=HOOK_FRAME, sound=False)
            need(q.get('zero_cost_confirmed') is True, 'ZERO_CREDIT_QUOTE_REQUIRED')
            r.update(initial_quote=q, state='INPUT_VERIFIED'); persist(r, receipt)
            return
        r['state'] = 'UPLOAD_START_UNCERTAIN'; persist(r, receipt)
        r['upload'], r['initial_quote'] = prepare_upload(m, client)
        r['state'] = 'UPLOAD_PENDING'; persist(r, receipt)
    elif command == 'ready':
        if hook:
            need(r['state'] == 'INPUT_VERIFIED', 'HOOK_INPUT_STATE')
            return  # The approved frame is in the checkout; no private WAV transfer exists.
        need(r['state'] == 'UPLOAD_PENDING', 'UPLOAD_STATE')
        until = time.monotonic() + 1200
        while True:
            try:
                data = read_audio(r['upload']['public_url'], m)
                break
            except HTTPError as e:
                pending = e.code in (403, 404); e.close()
                if not pending: raise Blocked('UPLOAD_READBACK_HTTP') from None
            need(time.monotonic() < until, 'UPLOAD_WAIT_EXPIRED')
            time.sleep(10)
        work.mkdir(parents=True, exist_ok=False)
        (work / 'input.wav').write_bytes(data)
        r['state'] = 'AUDIO_VERIFIED'; persist(r, receipt)
    elif command == 'submit':
        need(r['state'] == ('INPUT_VERIFIED' if hook else 'AUDIO_VERIFIED'), 'EXISTING_SUBMISSION_RECONCILE')
        if not hook:
            check_audio(m, (work / 'input.wav').read_bytes())
        import dispatch_guard
        now = datetime.now(timezone.utc)
        api = lambda p: native_review.github_read('/' + p)
        used = dispatch_guard.pavo_budget({'pavo_units': 2, 'short': True}, api, now.strftime('%Y-%m-%d'), now)
        base = quota.QuotaGuard()._load()
        base['days'][now.strftime('%Y-%m-%d')] = {'generated': used}
        qp = private / 'quota.json'; atomic(qp, base)
        r['state'] = 'SUBMITTING'; persist(r, receipt)
        lease(i)
        client = PrivateVideoClient(guard=RecordingGuard(qp, r, lambda: persist(r, receipt)))
        try:
            if hook:
                result = client.generate_video(m['prompt'], m['seconds'], '9:16', first_frame=HOOK_FRAME, sound=False)
            else:
                result = client.generate_video(m['prompt'], m['seconds'], '9:16', references=[REFERENCE],
                                              audios=[str((work / 'input.wav').relative_to(ROOT))], sound=False)
            r['submission'] = result
            r['state'] = 'UNKNOWN'
        finally:
            # Even a lost create acknowledgement leaves a durable non-replayable claim.
            persist(r, receipt)
    elif command == 'poll':
        need(r.get('conversation_id'), 'NO_ID_RECONCILE_CREATE')
        until = time.monotonic() + 900
        while True:
            poll_once(r, client); persist(r, receipt)
            if r['state'] in TERMINAL or time.monotonic() >= until: break
            time.sleep(15)
        need(r['state'] == 'COMPLETE', 'PAVO_' + r['state'])
    else:
        raise Blocked('COMMAND_REFUSED')


if __name__ == '__main__':
    try:
        cli(sys.argv[1])
    except (Blocked, PavoError) as e:
        # PavoError contains local codes only; never expose exception bodies/URLs/credentials.
        print(str(e).split(' ')[0], file=sys.stderr); sys.exit(1)
    except Exception:
        print('PRIVATE_AUDIO_OPERATION_FAILED_RECONCILE', file=sys.stderr); sys.exit(1)
