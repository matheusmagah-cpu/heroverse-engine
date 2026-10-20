"""Bounded pilot012 opening chapter repair. No upload or status write."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_video as pv
from copy import deepcopy

VIDEO = '1bT9pEROuhI'
CHANNEL = 'UCuMF6pJQkyMzaVoAxFL86yA'
API = 'https://www.googleapis.com/youtube/v3/videos'
OLD = '0:00 Good morning'
NEW = '0:00 Good evening'
WRITABLE = ('title','description','tags','categoryId','defaultLanguage','defaultAudioLanguage')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def old_description(desired):
    lines=desired.splitlines(keepends=True)
    matches=[i for i,line in enumerate(lines) if line.rstrip('\r\n')==NEW]
    if len(matches)!=1 or any(line.rstrip('\r\n')==OLD for line in lines):
        raise ValueError('EXPECTED_EXACTLY_ONE_CORRECT_OPENING')
    i=matches[0];lines[i]=lines[i].replace(NEW,OLD,1)
    return ''.join(lines)


def prepare(video, desired, title):
    if not isinstance(video,dict) or video.get('id')!=VIDEO: raise ValueError('WRONG_VIDEO')
    snippet=video.get('snippet') or {}
    if not isinstance(snippet, dict) or not isinstance(video.get('status'), dict): raise ValueError('MISSING_METADATA')
    if snippet.get('channelId')!=CHANNEL: raise ValueError('WRONG_CHANNEL')
    if snippet.get('title')!=title or not snippet.get('categoryId'): raise ValueError('SNIPPET_MISMATCH')
    previous=old_description(desired)
    actual=snippet.get('description')
    if actual not in (previous,desired): raise ValueError('REMOTE_DESCRIPTION_CHANGED')
    if actual==desired: return None
    if not isinstance(video.get('etag'),str) or not video['etag']: raise ValueError('MISSING_ETAG')
    payload={key:deepcopy(snippet[key]) for key in WRITABLE if key in snippet}
    payload['description']=desired
    return {'id':VIDEO,'snippet':payload}


def refresh(session, desired, title, check):
    def read():
        body=check(session.get(API,params={'part':'snippet,status','id':VIDEO}),'READ_VIDEO')
        items=body.get('items',[])
        if len(items)!=1: raise ValueError('VIDEO_NOT_FOUND_OR_AMBIGUOUS')
        return items[0]
    before=read(); payload=prepare(before,desired,title)
    if payload is not None:
        # One mutation only. An uncertain network result must be reconciled by a fresh read, never blind retry.
        check(session.put(API,params={'part':'snippet'},json=payload,headers={'If-Match':before['etag']}),'UPDATE_DESCRIPTION')
    after=read()
    if after.get('id')!=VIDEO or after.get('snippet',{}).get('channelId')!=CHANNEL: raise ValueError('VERIFY_IDENTITY')
    if after.get('snippet',{}).get('description')!=desired: raise ValueError('VERIFY_DESCRIPTION')
    for key in WRITABLE:
        if key!='description' and before['snippet'].get(key)!=after['snippet'].get(key): raise ValueError('VERIFY_OTHER_SNIPPET_CHANGED')
    if before.get('status')!=after.get('status'): raise ValueError('VERIFY_STATUS_CHANGED')
    return {'video_id':VIDEO,'channel_id':CHANNEL,'status':'PASS','applied':payload is not None,
            'before_description_sha256':digest(before['snippet']['description']),
            'after_description_sha256':digest(desired),'preserved_status':True}


def inputs(pilot_dir, receipt_path):
    d=Path(pilot_dir)
    package=json.loads((d/'out/package.json').read_bytes())
    receipt=json.loads(Path(receipt_path).read_bytes())
    manifest=json.loads((d/'out/manifest.json').read_bytes())
    if d.name!='pilot-012' or package.get('pilot_id')!='pilot-012': raise ValueError('WRONG_PILOT')
    if receipt.get('video_id')!=VIDEO or receipt.get('channel_id')!=CHANNEL: raise ValueError('RECEIPT_IDENTITY')
    if receipt.get('key')!='pilot-012:'+str(manifest.get('output_sha256')): raise ValueError('RECEIPT_RENDER_MISMATCH')
    if manifest.get('script_sha256')!=hashlib.sha256((d/'script.json').read_bytes()).hexdigest(): raise ValueError('SCRIPT_CHANGED')
    if package.get('title')!=receipt.get('title'): raise ValueError('TITLE_CHANGED')
    old_description(package['description'])
    return package


def main(pilot_dir, receipt_path, output_receipt):
    out=Path(output_receipt)
    try:
        package=inputs(pilot_dir,receipt_path)
        result=refresh(pv.session(),package['description'],package['title'],pv.check)
    except Exception as exc:
        # No HTTP bodies, headers or credentials in this public workflow's logs.
        result={'status':'FAIL','error_type':type(exc).__name__}
    result['checked_at_utc']=datetime.now(timezone.utc).isoformat()
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main(*sys.argv[1:]))
