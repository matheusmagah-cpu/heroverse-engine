"""Measure original mixed opening; never approves historical source or full release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

MASTER='3ff0806ab4d7d18548a072b35eb66491ba4a82bb7f59617d9a953d88a411bda6'
VOICE='9eebe0329a6069f7491e1310a085605da8dcf0f94c4d67d66c76b7bb1eecd0da'
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--voice',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.root.resolve();package=root/'output/production/audio-christian-rest-editorial-v4'
    media=package/'renders/christian-rest.phase5-draft.mp4'
    if digest(media)!=MASTER or digest(args.voice)!=VOICE:raise PermissionError('PRESERVED_MEDIA_ANCHOR_CHANGED')
    receipt=json.loads(args.receipt.read_text());recipe=json.loads((package/'music_recipe.json').read_text())
    if receipt['editorial']!=recipe['editorial'] or receipt['voice']['samples']!=1574912:
        raise PermissionError('ORIGINAL_OPENING_SCRIPT_CLOCK_CHANGED')
    sys.path.insert(0,str(root))
    from hero_engine.phase5_autonomous_quality import measure_rest_opening_intelligibility,_words,_edit_distance
    source={'opening':{'voice':receipt['voice'],'editorial':receipt['editorial'],
        'binding':{'path':str(args.receipt.resolve()),'sha256':'sha256:'+digest(args.receipt)}}}
    measured=measure_rest_opening_intelligibility(root,package,media,source=source)
    reference=_words(recipe['editorial']['full_text']);errors=_edit_distance(reference,_words(measured['transcript']['text']))
    result={'status':'MEASURED_ORIGINAL_MIX_OPENING','measurement':measured,
        'speech_comparison':{'reference_words':len(reference),'word_errors':errors,
        'word_error_rate':errors/len(reference),'native_threshold':0.08,'within_native_threshold':errors/len(reference)<=0.08},
        'source_provenance_scope':'Received historical WAV and receipt; Windows phonemizer origins are not claimed as current Linux generation',
        'quality_authorized':False,'publication_authorized':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'speech_comparison':result['speech_comparison'],'quality_authorized':False}))
if __name__=='__main__':main()
