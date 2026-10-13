"""Qualify the existing authorized-user token with the original refresh proof."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

CLIENT_ID='663335615694-gs2ivqgl5iaaed44cv3fpvpcfcamnnch.apps.googleusercontent.com'
SCOPES={'https://www.googleapis.com/auth/'+s for s in
        ('youtube.readonly','yt-analytics.readonly','youtube.upload','youtube.force-ssl')}
DIGEST='fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'

def check_token(value):
    if not value:return 'CLOUD_TOKEN_NOT_PROVISIONED'
    try:token=json.loads(value)
    except (ValueError,TypeError):return 'INVALID_TOKEN_JSON'
    if not isinstance(token,dict):return 'INVALID_TOKEN_JSON'
    if token.get('type','authorized_user')!='authorized_user':return 'AUTHORIZED_USER_REQUIRED'
    if token.get('client_id')!=CLIENT_ID:return 'EXISTING_CLIENT_ID_MISMATCH'
    if token.get('token_uri','https://oauth2.googleapis.com/token')!='https://oauth2.googleapis.com/token':
        return 'UNAPPROVED_TOKEN_ENDPOINT'
    if not all(isinstance(token.get(k),str) and token[k] for k in ('refresh_token','client_secret')):
        return 'INCOMPLETE_AUTHORIZED_USER_TOKEN'
    scopes=token.get('scopes')
    if not isinstance(scopes,list) or not all(isinstance(s,str) for s in scopes) or not SCOPES.issubset(scopes):
        return 'REQUIRED_SCOPES_MISSING'
    return None

def emit(receipt):
    print(json.dumps(receipt,sort_keys=True))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as out:out.write('```json\n'+json.dumps(receipt,indent=2)+'\n```\n')

def main():
    value=os.environ.get('HERO_YT_AUTHORIZED_USER_JSON','')
    reason=check_token(value)
    if reason:
        emit({'status':'BLOCKED','failure_code':reason,'secret_values_logged':False,
              'publication_performed':False,'production_ready':False})
        return 2
    source=Path('HeroVerse_Linux_Source_Ready_20261013_v2.zip')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=DIGEST:raise ValueError('source identity mismatch')
    # Ephemeral and private, outside checkout. No token is written into source/artifacts.
    with tempfile.TemporaryDirectory(prefix='heroverse-oauth-',dir=os.environ.get('RUNNER_TEMP')) as temp:
        root=Path(temp);root.chmod(0o700)
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                p=PurePosixPath(member.filename)
                if p.is_absolute() or '..' in p.parts or ((member.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError('unsafe archive member')
            archive.extractall(root/'source')
        manifest=json.loads((root/'source/SOURCE_TRANSFER_REPORT.json').read_text())
        project=root/'source/project'
        for entry in manifest['files']:
            raw=(project/entry['path']).read_bytes()
            if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
                raise ValueError('restored source identity mismatch')
        token=root/'authorized-user.json'
        fd=os.open(token,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:out.write(value)
        value=None
        sys.path.insert(0,str(project))
        from hero_engine.oauth_refresh_proof import prove_noninteractive_refresh
        result=prove_noninteractive_refresh(token,root/'refresh-receipt.json',root=project)
        result['production_ready']=False;result['publication_performed']=False
        result['qualification']='ORIGINAL_REFRESH_AND_CHANNEL_IDENTITY_ONLY'
        emit(result)
        return 0 if result['status']=='PASS' else 2

if __name__=='__main__':
    try:code=main()
    except Exception:
        # Never serialize third-party exception payloads that may contain credentials.
        emit({'status':'BLOCKED','failure_code':'WORKER_QUALIFICATION_ERROR',
              'secret_values_logged':False,'publication_performed':False,'production_ready':False})
        code=2
    sys.exit(code)
