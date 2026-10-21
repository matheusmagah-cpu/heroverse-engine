#!/usr/bin/env python3
"""One pinned, previously unreviewed Short; no general retry or approval API."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

PILOT = 'pilot-006'
FILE = 'short-00.mp4'
OUTPUT_SHA256 = '9c0f2aed36ab0d1af07bcf1123355c9b44afd1df0911a799aa09cdebb98f9707'
SOURCE_SHA256 = '37465008e0b73a51f3d394d283500eab1426fdd679d36b571ed241d20689e402'
TARGET_SLOT = '2026-10-21T14:00:00Z'
RELEASE_DEADLINE = '2026-10-21T13:15:00Z'
ORIGINAL_STATUS = 'NOT_REVIEWED_ProviderFailure'
VERSION = 'single-short-review-recovery-v1'
SELECTION = dict(version=VERSION, pilot=PILOT, file=FILE, output_sha256=OUTPUT_SHA256,
                 source_manifest_sha256=SOURCE_SHA256, original_review_status=ORIGINAL_STATUS,
                 target_slot=TARGET_SLOT, release_deadline=RELEASE_DEADLINE)
MUTABLE = {'qa', 'qa_output_sha256', 'review', 'publish', 'owner_quality_policy'}


def utc_now():
    return datetime.now(timezone.utc)


def instant(value):
    if type(value) is not str:
        raise ValueError('RECOVERY_TIMESTAMP_INVALID')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('RECOVERY_TIMESTAMP_INVALID')
    return result


def within_deadline(now=None):
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError('RECOVERY_TIMESTAMP_INVALID')
    return now <= instant(RELEASE_DEADLINE)


def _expected_binding():
    return {k: v for k, v in SELECTION.items() if k != 'original_review_status'} | {
        'previous_review_status': ORIGINAL_STATUS, 'status': 'REVIEW_RECORDED'}


def _records(spec):
    if type(spec) is not dict or spec.get('source_pilot') != PILOT:
        raise ValueError('RECOVERY_PILOT_INVALID')
    records = spec.get('shorts')
    if (type(records) is not list or len(records) != 3 or
            any(type(r) is not dict for r in records) or
            [r.get('file') for r in records] != ['short-00.mp4', 'short-01.mp4', 'short-02.mp4']):
        raise ValueError('RECOVERY_RECORDS_INVALID')
    selected = records[0]
    if selected.get('sha256') != OUTPUT_SHA256:
        raise ValueError('RECOVERY_OUTPUT_HASH_INVALID')
    if any(r.get('publish') is not False for r in records[1:]):
        raise ValueError('RECOVERY_MULTIPLE_SELECTED')
    return selected


def binding(spec):
    """Pure provenance/shape validation, not a QA or editorial PASS."""
    selected = _records(spec)
    value = spec.get('review_recovery')
    expected = _expected_binding()
    if type(value) is not dict or value != expected or any(type(v) is not str for v in value.values()):
        raise ValueError('RECOVERY_BINDING_INVALID')
    execution = spec.get('review_recovery_execution')
    if type(execution) is not dict or set(execution) != {
            'reviewed_at', 'github_run_id', 'github_run_attempt', 'output_sha256'}:
        raise ValueError('RECOVERY_EXECUTION_INVALID')
    for key in ('github_run_id', 'github_run_attempt'):
        if type(execution[key]) is not str or not re.fullmatch(r'[1-9][0-9]*', execution[key]):
            raise ValueError('RECOVERY_EXECUTION_INVALID')
    instant(execution['reviewed_at'])
    if execution['output_sha256'] != OUTPUT_SHA256 or type(selected.get('publish')) is not bool:
        raise ValueError('RECOVERY_EXECUTION_INVALID')
    if selected.get('previous_review') != {'status': ORIGINAL_STATUS}:
        raise ValueError('RECOVERY_PREVIOUS_REVIEW_INVALID')
    return dict(value)


def _regular(path, directory=False):
    path = Path(path)
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('RECOVERY_PATH_INVALID')
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError('RECOVERY_PATH_INVALID')
    return path


def digest(path):
    h = hashlib.sha256()
    with _regular(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(pilot_dir, selection_path):
    d = _regular(pilot_dir, directory=True)
    if d.name != PILOT or d.parent.name != 'production' or d.parent.parent.name != 'migration':
        raise ValueError('RECOVERY_PATH_INVALID')
    selection = json.loads(_regular(selection_path).read_bytes())
    if type(selection) is not dict or selection != SELECTION or any(type(v) is not str for v in selection.values()):
        raise ValueError('RECOVERY_SELECTION_INVALID')
    manifest = _regular(d / 'shorts' / 'shorts.json')
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('RECOVERY_SOURCE_CHANGED')
    spec = json.loads(raw)
    selected = _records(spec)
    if selected.get('review') != {'status': ORIGINAL_STATUS} or selected.get('publish') is not False:
        raise ValueError('RECOVERY_SOURCE_NOT_UNREVIEWED')
    return dict(pilot_dir=d, manifest_path=manifest, raw=raw, spec=spec, selected=selected)


def _execution():
    value = dict(reviewed_at=utc_now().isoformat(), github_run_id=os.environ.get('GITHUB_RUN_ID'),
                 github_run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'), output_sha256=OUTPUT_SHA256)
    for key in ('github_run_id', 'github_run_attempt'):
        if type(value[key]) is not str or not re.fullmatch(r'[1-9][0-9]*', value[key]):
            raise ValueError('RECOVERY_EXECUTION_INVALID')
    return value


def _atomic(path, spec):
    fd, name = tempfile.mkstemp(prefix='.recovery-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(spec, f, indent=1, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def review_selected(pilot_dir, selection_path):
    data = prepare(pilot_dir, selection_path)
    execution = _execution()  # validate run provenance before any provider usage
    media = data['pilot_dir'] / 'shorts' / FILE
    if digest(media) != OUTPUT_SHA256:
        raise ValueError('RECOVERY_MEDIA_HASH_INVALID')
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import shorts_prerequisite
    if shorts_prerequisite.problems(data['pilot_dir']):
        raise ValueError('RECOVERY_LONG_NOT_QUALIFIED')
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'production'))
    import shorts_review  # lazy: pure validators never initialize provider code
    with tempfile.TemporaryDirectory(prefix='heroverse-review-') as temporary:
        temp = Path(temporary)
        isolated = copy.deepcopy(data['spec'])
        isolated['shorts'] = [copy.deepcopy(data['selected'])]
        (temp / 'shorts.json').write_text(json.dumps(isolated))
        shutil.copyfile(media, temp / FILE)
        if digest(temp / FILE) != OUTPUT_SHA256:
            raise ValueError('RECOVERY_COPY_HASH_INVALID')
        shorts_review.main(temp, '1')
        result = json.loads((temp / 'shorts.json').read_bytes())
        if type(result) is not dict or type(result.get('shorts')) is not list or len(result['shorts']) != 1:
            raise ValueError('RECOVERY_RESULT_INVALID')
        rec = result['shorts'][0]
        original = data['selected']
        if type(rec) is not dict or {k: v for k, v in rec.items() if k not in MUTABLE} != {
                k: v for k, v in original.items() if k not in MUTABLE}:
            raise ValueError('RECOVERY_SOURCE_FIELDS_CHANGED')
        if (not MUTABLE.issubset(rec) or type(rec['qa']) is not dict or type(rec['review']) is not dict or
                type(rec['publish']) is not bool or type(rec['owner_quality_policy']) is not dict or
                rec['qa_output_sha256'] != OUTPUT_SHA256 or type(rec['review'].get('status')) is not str):
            raise ValueError('RECOVERY_RESULT_INVALID')
        status = rec['review']['status']
        if status not in ('PASS', 'FAIL') and not re.fullmatch(r'NOT_REVIEWED_[A-Za-z0-9_]+', status):
            raise ValueError('RECOVERY_RESULT_INVALID')
        if (digest(media) != OUTPUT_SHA256 or digest(temp / FILE) != OUTPUT_SHA256 or
                data['manifest_path'].read_bytes() != data['raw']):
            raise ValueError('RECOVERY_INPUT_CHANGED_DURING_REVIEW')
        import owner_quality_policy
        eligible = (rec['qa'].get('status') == 'PASS' and
                    not owner_quality_policy.check(rec['review'], OUTPUT_SHA256))
        if rec['publish'] and not eligible:
            raise ValueError('RECOVERY_UNJUSTIFIED_PUBLISH')
        output = copy.deepcopy(data['spec'])
        updated = output['shorts'][0]
        updated['previous_review'] = copy.deepcopy(original['review'])
        for key in MUTABLE:
            updated[key] = copy.deepcopy(rec[key])
        if not within_deadline():
            updated['publish'] = False
            updated['release_status'] = 'TARGET_SLOT_LEAD_MISSED'
        output['review_recovery'] = _expected_binding()
        execution['reviewed_at'] = utc_now().isoformat()
        output['review_recovery_execution'] = execution
        binding(output)
        _atomic(data['manifest_path'], output)
        return output


def main(mode, pilot_dir, selection_path):
    if mode == '--list':
        prepare(pilot_dir, selection_path)
        print(FILE, OUTPUT_SHA256)
    elif mode == '--review':
        output = review_selected(pilot_dir, selection_path)
        print(json.dumps({'status': 'REVIEW_RECORDED', 'publish': output['shorts'][0]['publish']}))
    else:
        raise ValueError('RECOVERY_MODE_INVALID')


if __name__ == '__main__':
    try:
        main(*sys.argv[1:])
    except (ValueError, OSError, TypeError) as error:
        print('REVIEW_RECOVERY_BLOCKED', type(error).__name__, file=sys.stderr)
        sys.exit(1)
