"""Create a reviewed Linux production shadow; preserve immutable archive and origin."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

EXPECTED={
 'hero_engine/render_creative_v2_phase5.py':'b94eb3a928ade12658b2a07686e508338653f9fedc5a6f30bb72132fee2c9cc4',
 'tests/test_oauth_scope_requirements.py':'5267dc87659923bff523e2c0edc8f99880d9ae58f6e5bde5cc770053a7aa8a64',
}
def apply(source, destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists() or destination==source or source in destination.parents:
        raise ValueError('shadow must be new and outside source')
    originals={}
    for relative,digest in EXPECTED.items():
        raw=(source/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('unexpected source: '+relative)
        originals[relative]=raw
    renderer=originals['hero_engine/render_creative_v2_phase5.py'].decode()
    anchor='FONT_CANDIDATES = [Path(r"C:\\Windows\\Fonts\\bahnschrift.ttf"), Path(r"C:\\Windows\\Fonts\\arialbd.ttf")]'
    replacement=anchor+' + [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]'
    if renderer.count(anchor)!=1:raise ValueError('font anchor mismatch')
    renderer=renderer.replace(anchor,replacement).replace('Bahnschrift/Arial Bold missing','No supported bold font found (Windows or Linux DejaVu)')
    scope=originals['tests/test_oauth_scope_requirements.py'].decode()
    anchor='self.assertEqual(["ffmpeg.exe", "ffprobe.exe", "ffprobe.exe"], [item["tool"] for item in processes])'
    replacement='self.assertEqual(["ffmpeg", "ffprobe", "ffprobe"], [item["tool"].removesuffix(".exe") for item in processes])'
    if scope.count(anchor)!=1:raise ValueError('scope anchor mismatch')
    scope=scope.replace(anchor,replacement)
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
    patched={'hero_engine/render_creative_v2_phase5.py':renderer,'tests/test_oauth_scope_requirements.py':scope}
    receipts=[]
    for relative,text in patched.items():
        raw=text.encode();(destination/relative).write_bytes(raw)
        receipts.append({'path':relative,'original_sha256':EXPECTED[relative],
                         'shadow_sha256':hashlib.sha256(raw).hexdigest()})
    receipt={'policy':'LINUX_PRODUCTION_SHADOW_V1','changes':receipts,
             'original_preserved':True,'production_qualified':False}
    (destination/'linux-overlay-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args()
    print(json.dumps(apply(a.source,a.destination),indent=2))
