"""Owner-requested DRAFT attachment transfer; never creates conversations or media.

The workflow must push the content-addressed claims before calling send. Existing
claims, including unknown outcomes, require reconciliation, not an automatic retry.
OpenAI provenance is retained; neither upload nor hash readback is an approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import PavoError
import images
from video import PavoVideoClient

BASE = Path('migration/evidence/pavo/attachments')
INPUT = Path('migration/production/bible/stills/candidates')
RECEIPTS = BASE / 'receipts'
REPO = Path(__file__).resolve().parents[3]
HOSTS = {'cos-aigc-default.agnes-ai.space', 'aigc-default-1395352844.cos.ap-singapore.myqcloud.com'}


class TransferError(Exception):
    pass


def storage_url(url, signed=False):
    try:
        p = urlsplit(url)
        if (not isinstance(url, str) or len(url) > 4096 or p.scheme != 'https' or p.hostname not in HOSTS
                or p.port not in (None, 443) or p.username or p.password or p.fragment
                or (p.query and not signed)):
            raise ValueError()
    except (TypeError, ValueError):
        raise TransferError('ATTACHMENT_DESTINATION_REFUSED') from None
    return url


class AttachmentClient(PavoVideoClient):
    def _video_json(self, route, body=None, job=None):
        if route not in ('quote', 'upload', 'inspect'):
            raise TransferError('ATTACHMENT_GENERATION_DISABLED')
        data = super()._video_json(route, body, job)
        if route == 'upload':
            if not isinstance(data, dict):
                raise TransferError('ATTACHMENT_UPLOAD_SCHEMA')
            storage_url(data.get('public_url'))
            storage_url(data.get('upload_url'), signed=True)
        return data

    def readback(self, url):
        request = Request(storage_url(url), headers={'User-Agent': 'HeroVerse-draft-attachment/1'}, method='GET')
        # No bearer credential or signed upload URL on this public read.
        with self._opener.open(request, timeout=30) as response:
            if response.status != 200:
                raise TransferError('ATTACHMENT_READBACK_FAILED')
            data = response.read(images.MAX_IMAGE_BYTES + 1)
        if len(data) > images.MAX_IMAGE_BYTES:
            raise TransferError('ATTACHMENT_READBACK_FAILED')
        return data


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def load(manifest, root):
    root = Path(root).resolve()
    manifest = Path(manifest).resolve()
    if manifest.parent != root / BASE or manifest.suffix != '.json':
        raise TransferError('ATTACHMENT_MANIFEST_REFUSED')
    value = json.loads(manifest.read_text())
    if (not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1
            or value.get('source') != 'openai-imagegen' or value.get('status') != 'DRAFT'
            or value.get('approved') is not False or value.get('generation_enabled') is not False):
        raise TransferError('ATTACHMENT_PROVENANCE_REFUSED')
    items = value.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 3:
        raise TransferError('ATTACHMENT_BATCH_REFUSED')
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not re.fullmatch(r's-[a-z0-9-]{1,64}', str(item.get('shot', ''))):
            raise TransferError('ATTACHMENT_ITEM_REFUSED')
        path, sha = item.get('path'), item.get('sha256')
        if not isinstance(path, str) or (root / path).resolve().parent != root / INPUT:
            raise TransferError('ATTACHMENT_PATH_REFUSED')
        if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha) or sha in seen:
            raise TransferError('ATTACHMENT_HASH_REFUSED')
        if item.get('prompt') is not None or item.get('provenance_status') != 'EXACT_GENERATION_PROMPT_NOT_RECOVERED':
            raise TransferError('ATTACHMENT_PROMPT_REFUSED')
        refs = item.get('reference_sha256')
        if not isinstance(refs, list) or any(not isinstance(s, str) or not re.fullmatch('[a-f0-9]{64}', s) for s in refs):
            raise TransferError('ATTACHMENT_REFERENCE_REFUSED')
        media = images.image(path, root)
        if hashlib.sha256(media['data']).hexdigest() != sha:
            raise TransferError('ATTACHMENT_HASH_REFUSED')
        seen.add(sha)
    return value, hashlib.sha256(manifest.read_bytes()).hexdigest()


def identity(run, attempt):
    if not all(isinstance(x, str) and re.fullmatch('[1-9][0-9]{0,24}', x) for x in (run, attempt)):
        raise TransferError('ATTACHMENT_RUN_REFUSED')


def claim(manifest, run, attempt, root=REPO):
    identity(run, attempt)
    value, digest = load(manifest, root)
    target = Path(root) / RECEIPTS
    paths = [target / (i['sha256'] + '.json') for i in value['items']]
    if any(p.exists() for p in paths):
        raise TransferError('ATTACHMENT_ALREADY_CLAIMED_RECONCILE')
    target.mkdir(parents=True, exist_ok=True)
    for item, path in zip(value['items'], paths):
        record = {'state': 'CLAIMED', 'run': run, 'attempt': attempt, 'manifest_sha256': digest,
                  'sha256': item['sha256'], 'shot': item['shot'], 'source': value['source'],
                  'approved': False, 'generation_enabled': False, 'production_qualified': False,
                  'licence_verified': False}
        # Exclusive creation also refuses a concurrent local claim.
        with path.open('x') as stream:
            json.dump(record, stream, indent=2)
            stream.write('\n')
    return len(paths)


def send(manifest, run, attempt, root=REPO, client=None, readback=None):
    identity(run, attempt)
    value, digest = load(manifest, root)
    records = []
    for item in value['items']:
        path = Path(root) / RECEIPTS / (item['sha256'] + '.json')
        record = json.loads(path.read_text())
        if (record.get('state') != 'CLAIMED' or record.get('run') != run or record.get('attempt') != attempt
                or record.get('manifest_sha256') != digest or record.get('sha256') != item['sha256']):
            raise TransferError('ATTACHMENT_CLAIM_MISMATCH_OR_REPLAY')
        records.append((item, path, record))
    client = client or AttachmentClient()
    readback = readback or client.readback
    for item, path, record in records:
        # The durable remote claim already exists. Seal local uncertainty before
        # any provider effect, even the quote; no exception can authorize replay.
        record['state'] = 'OUTCOME_REQUIRES_RECONCILIATION'
        atomic(path, record)
        try:
            quoted = client.quote_video(seconds=5, aspect_ratio='9:16', first_frame=item['path'])
            if quoted.get('zero_cost_confirmed') is not True:
                raise TransferError('ATTACHMENT_ZERO_QUOTE_REQUIRED')
            uploaded = client._upload(images.image(item['path'], root))
            url = storage_url(uploaded.get('url'))
            record.update(state='UPLOADED_NOT_VERIFIED', url=url)
            atomic(path, record)
            if hashlib.sha256(readback(url)).hexdigest() != item['sha256']:
                raise TransferError('ATTACHMENT_READBACK_HASH_MISMATCH')
            record.update(state='UPLOADED_HASH_VERIFIED', quoted_credits=0)
            atomic(path, record)
        except TransferError:
            raise
        except Exception:
            # Never log arbitrary provider exception bodies, bearer or signed URL.
            raise TransferError('ATTACHMENT_OUTCOME_REQUIRES_RECONCILIATION') from None
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('claim', 'send'))
    parser.add_argument('manifest')
    args = parser.parse_args()
    try:
        count = globals()[args.mode](args.manifest, os.environ.get('GITHUB_RUN_ID'), os.environ.get('GITHUB_RUN_ATTEMPT'))
    except (TransferError, PavoError) as exc:
        print(json.dumps({'ok': False, 'code': str(exc).split()[0], 'generation_enabled': False}))
        return 2
    except Exception:
        print('{"ok":false,"code":"ATTACHMENT_INVALID_INPUT_OR_STATE","generation_enabled":false}')
        return 2
    print(json.dumps({'ok': True, 'mode': args.mode, 'count': count, 'generation_enabled': False, 'approved': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
