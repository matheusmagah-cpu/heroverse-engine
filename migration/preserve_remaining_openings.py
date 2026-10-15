"""Narrow configuration wrapper around the qualified second-opening transfer.

Each invocation handles one fixed source. No acquisition or retry authority.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ALLOWLIST = ('VA3qvxoZr4Q', 'EkT0XMVln3s', 'ksMAEHpzkZo')
BASE_SHA256 = '431dfbe7064f5d7e8c6507e824e258765f3ac11e93459bbd59c9d433dc682acc'
CONFIG = Path(__file__).with_name('remaining-opening-preservation.json')
FIELDS = {'video_id', 'window_seconds', 'artifact_id', 'source_run_id',
          'archive_bytes', 'archive_sha256', 'native_bytes', 'native_sha256'}


def load_config(path=CONFIG):
    value = json.loads(path.read_bytes())
    if set(value) != {'version', 'status', 'sources'} or value['version'] != 'remaining-opening-preservation-v1':
        raise ValueError('CONFIG_IDENTITY_MISMATCH')
    if value['status'] != 'VERIFIED_IDENTITIES_READY':
        raise ValueError('VERIFIED_SOURCE_IDENTITIES_REQUIRED')
    rows = value['sources']
    if not isinstance(rows, list) or len(rows) != 3 or [r.get('video_id') for r in rows] != list(ALLOWLIST):
        raise ValueError('EXACT_ORDERED_ALLOWLIST_REQUIRED')
    for row in rows:
        if set(row) != FIELDS or row['window_seconds'] != [0, 40]:
            raise ValueError('EXACT_SOURCE_FIELDS_REQUIRED')
        for key in ('artifact_id', 'source_run_id', 'archive_bytes', 'native_bytes'):
            if type(row[key]) is not int or row[key] <= 0:
                raise ValueError('POSITIVE_SOURCE_IDENTITY_REQUIRED')
        if row['archive_bytes'] >= 96*1024*1024 or row['native_bytes'] >= 96*1024*1024:
            raise ValueError('SOURCE_SIZE_BOUND_EXCEEDED')
        for key in ('archive_sha256', 'native_sha256'):
            if not isinstance(row[key], str) or not re.fullmatch('[0-9a-f]{64}', row[key]):
                raise ValueError('EXACT_SHA256_REQUIRED')
    for key in ('artifact_id', 'native_sha256'):
        if len({r[key] for r in rows}) != 3:
            raise ValueError('DUPLICATE_SOURCE_IDENTITY')
    return {row['video_id']: row for row in rows}


def bind_base(row, module_path=None):
    path = module_path or Path(__file__).with_name('preserve_second_opening_release.py')
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASE_SHA256:
        raise ValueError('QUALIFIED_BASE_IDENTITY_CHANGED')
    spec = importlib.util.spec_from_file_location('qualified_preservation_base', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ARTIFACT_ID = row['artifact_id']
    module.SOURCE_RUN = row['source_run_id']
    module.ARCHIVE_BYTES = row['archive_bytes']
    module.ARCHIVE_SHA = row['archive_sha256']
    module.NATIVE_BYTES = row['native_bytes']
    module.NATIVE_SHA = row['native_sha256']
    module.NAME = f"native-{row['video_id']}-0-40s-sha256-{row['native_sha256']}.mp4"
    original_receipt = module.receipt
    def receipt(*args, **kwargs):
        result = original_receipt(*args, **kwargs)
        folder = Path('remaining-opening-receipts')
        folder.mkdir(exist_ok=True)
        Path('second-opening-preservation-receipt.json').replace(folder / (row['video_id']+'.json'))
        return result
    module.receipt = receipt
    return module


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('preflight', 'transfer') or sys.argv[2] not in ALLOWLIST:
        raise ValueError('EXACT_MODE_AND_SOURCE_REQUIRED')
    row = load_config()[sys.argv[2]]
    module = bind_base(row)
    module.environment()
    if sys.argv[1] == 'preflight':
        module.preflight()
    else:
        module.transfer(Path(os.environ['OPENING_RESTORE_ROOT']))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','exception_type':type(error).__name__,
                          'details_redacted':True,'retry':False,
                          'reconcile_existing_asset_before_any_new_execution':True}))
        raise SystemExit(2)
