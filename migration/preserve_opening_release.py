"""One-shot identity-preserving transfer to an existing private GitHub release.

Only GitHub metadata and one MP4 upload are permitted; no retries or AV re-review.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

REPO = 'matheusmagah-cpu/heroverse-engine'
RELEASE_ID = 411926125
TAG = 'v0.0.0-cloud-assets-20261013'
ARTIFACT_ID = 11983614696
SOURCE_RUN = 38758415623
ARCHIVE_BYTES = 33909351
ARCHIVE_SHA = '5cdb19d9a62715f5ea4192a8a004f7dbdf59c3942a14d01713bfc788a4611904'
NATIVE_BYTES = 26121679
NATIVE_SHA = '5dca962757c952c8048c746f23f96a325cf15258f429e1e79e7b5ddf72fb0fb5'
NAME = f'native-j2rk8ycXe3c-0-40s-sha256-{NATIVE_SHA}.mp4'
LIMIT = 96 * 1024 * 1024
BASE = f'repos/{REPO}'
UPLOAD = f'https://uploads.github.com/{BASE}/releases/{RELEASE_ID}/assets'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def api(endpoint, upload=None):
    """Official preinstalled gh, ephemeral GH_TOKEN; never log stderr or tokens."""
    require(endpoint.startswith(BASE + '/') or endpoint == BASE or
            endpoint == UPLOAD + '?name=' + NAME, 'API_DESTINATION_BLOCKED')
    args = ['gh', 'api', endpoint, '--method', 'POST' if upload else 'GET',
            '-H', 'Accept: application/vnd.github+json',
            '-H', 'X-GitHub-Api-Version: 2022-11-28']
    if upload:
        args += ['-H', 'Content-Type: video/mp4', '--input', str(upload)]
    result = subprocess.run(args, capture_output=True, timeout=60 if upload else 15)
    require(result.returncode == 0, 'GITHUB_REQUEST_FAILED_RECONCILE_BEFORE_RETRY')
    require(len(result.stdout) < 2 * 1024 * 1024, 'METADATA_RESPONSE_TOO_LARGE')
    return json.loads(result.stdout)


def environment():
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'REPOSITORY_MISMATCH')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'MANUAL_ONLY')
    require(os.environ.get('GITHUB_RUN_NUMBER') == '1', 'ONE_RUN_ONLY')
    require(os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'ONE_ATTEMPT_ONLY')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/main', 'MAIN_ONLY')
    require(os.environ.get('GH_TOKEN'), 'EPHEMERAL_TOKEN_REQUIRED')


def destination():
    repo = api(BASE)
    require(repo.get('full_name') == REPO and repo.get('private') is True,
            'PRIVATE_REPOSITORY_REQUIRED')
    release = api(f'{BASE}/releases/{RELEASE_ID}')
    require(release.get('id') == RELEASE_ID and release.get('tag_name') == TAG,
            'RELEASE_IDENTITY_MISMATCH')
    require(release.get('upload_url') == UPLOAD + '{?name,label}', 'UPLOAD_URL_MISMATCH')
    require(release.get('draft') is False, 'RELEASE_STATE_MISMATCH')
    assets = []
    for page in range(1, 11):
        batch = api(f'{BASE}/releases/{RELEASE_ID}/assets?per_page=100&page={page}')
        require(isinstance(batch, list), 'ASSET_LIST_INVALID')
        assets.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError('ASSET_PAGINATION_LIMIT')
    matching = [a for a in assets if a.get('name') == NAME]
    require(len(matching) <= 1, 'DUPLICATE_ASSET_NAME')
    if matching:
        verify_asset(matching[0])
        return matching[0]
    return None


def verify_asset(asset):
    require(asset.get('name') == NAME and asset.get('size') == NATIVE_BYTES and
            asset.get('digest') == 'sha256:' + NATIVE_SHA and
            asset.get('state') == 'uploaded' and
            type(asset.get('id')) is int and asset['id'] > 0,
            'ASSET_CONFLICT_OR_UNVERIFIED_DIGEST_NO_OVERWRITE')
    return asset


def source_metadata():
    source = api(f'{BASE}/actions/artifacts/{ARTIFACT_ID}')
    require(source.get('id') == ARTIFACT_ID and source.get('expired') is False,
            'SOURCE_EXPIRED_OR_MISMATCH')
    require(source.get('workflow_run', {}).get('id') == SOURCE_RUN, 'SOURCE_RUN_MISMATCH')
    require(source.get('size_in_bytes') == ARCHIVE_BYTES and ARCHIVE_BYTES < LIMIT,
            'ARCHIVE_SIZE_MISMATCH')
    require(source.get('digest') == 'sha256:' + ARCHIVE_SHA, 'ARCHIVE_DIGEST_MISMATCH')
    return source


def discover_native(root):
    """Do not guess an archive prefix; resolve, inventory and hash exact candidate."""
    require(not root.is_symlink() and root.is_dir(), 'RESTORE_ROOT_INVALID')
    root = root.resolve(strict=True)
    files, total, candidates = [], 0, []
    for path in root.rglob('*'):
        st = path.lstat()
        require(not stat.S_ISLNK(st.st_mode), 'SYMLINK_BLOCKED')
        require(stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode), 'SPECIAL_FILE_BLOCKED')
        require(path.resolve(strict=True).is_relative_to(root), 'PATH_ESCAPE')
        if stat.S_ISREG(st.st_mode):
            total += st.st_size
            files.append(path)
            require(total < LIMIT and len(files) <= 64, 'RESTORED_OUTPUT_BOUND_EXCEEDED')
            if path.suffix.lower() == '.mp4' and st.st_size == NATIVE_BYTES:
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest == NATIVE_SHA:
                    candidates.append(path)
    require(len(candidates) == 1, 'EXACT_NATIVE_NOT_UNIQUE_OR_MISSING')
    path = candidates[0]
    return path, {'restored_root_realpath': str(root),
                  'native_realpath': str(path.resolve(strict=True)),
                  'native_relative_path': path.relative_to(root).as_posix(),
                  'restored_bytes': total, 'restored_files': len(files)}


def receipt(status, asset=None, audit=None):
    value = {'schema': 'native-opening-private-release-v1', 'status': status,
             'repository': REPO, 'release_id': RELEASE_ID, 'release_tag': TAG,
             'asset_name': NAME, 'native_bytes': NATIVE_BYTES, 'native_sha256': NATIVE_SHA,
             'source_artifact_id': ARTIFACT_ID, 'source_run_id': SOURCE_RUN,
             'source_archive_bytes': ARCHIVE_BYTES, 'source_archive_sha256': ARCHIVE_SHA,
             'preservation_run_id': os.environ.get('GITHUB_RUN_ID'),
             'preservation_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
             'commit_sha': os.environ.get('GITHUB_SHA'), 'provider_calls': 0,
             'production': False, 'publication': False, 'supervisor': False,
             'full_av_qa_repeated': False, 'binary_through_chat': False,
             'git_media_blob_created': False, 'upload_retry_allowed': False}
    if asset:
        value['github_asset_id'] = asset['id']
        value['verified_github_asset_digest'] = asset['digest']
        value['verified_github_asset_bytes'] = asset['size']
    if audit:
        value.update(audit)
    out = Path('opening-preservation-receipt.json')
    out.write_text(json.dumps(value, indent=2) + '\n')
    print('HEROVERSE_OPENING_PRESERVATION=' + json.dumps(value))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            stream.write('## Native opening preservation\n\n```json\n' +
                         json.dumps(value, indent=2) + '\n```\n')
    return value


def preflight():
    existing = destination()
    if existing:
        receipt('reused', existing)
        result = 'false'
    else:
        source_metadata()
        result = 'true'
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write('needs_transfer=' + result + '\n')


def transfer(root):
    # Reconcile before mutating, including a possible concurrent exact upload.
    existing = destination()
    if existing:
        return receipt('reused', existing)
    source_metadata()
    path, audit = discover_native(root)
    # Capture intent BEFORE the single POST. An interrupted/failed run must be
    # reconciled against release assets; it never proves that nothing uploaded.
    receipt('upload_pending_reconcile_if_interrupted', audit=audit)
    try:
        uploaded = verify_asset(api(UPLOAD + '?name=' + NAME, upload=path))
        verified = destination()
        require(verified is not None and verified['id'] == uploaded['id'],
                'POST_UPLOAD_RECONCILIATION_MISMATCH')
    except Exception:
        receipt('upload_outcome_ambiguous_reconcile_do_not_repeat', audit=audit)
        raise
    return receipt('stored', verified, audit)


def main():
    environment()
    if sys.argv[1:] == ['preflight']:
        preflight()
    elif sys.argv[1:] == ['transfer']:
        transfer(Path(os.environ['OPENING_RESTORE_ROOT']))
    else:
        raise ValueError('INVALID_MODE')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never echo API output, auth values, command environment or exception text.
        print(json.dumps({'status': 'BLOCKED', 'exception_type': type(error).__name__,
                          'details_redacted': True, 'retry': False,
                          'reconcile_existing_asset_before_any_new_execution': True}))
        raise SystemExit(2)
