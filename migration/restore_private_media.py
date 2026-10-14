"""Restore exact own assets from same private repository using ephemeral GH token."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path

def main():
    if os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine':raise PermissionError('REPOSITORY_MISMATCH')
    manifest=json.loads(Path('migration/evidence/cloud-media-manifest.json').read_text())
    dest=Path(os.environ['RUNNER_TEMP'])/'heroverse-original-assets';dest.mkdir(exist_ok=False)
    if shutil.disk_usage(dest).free<15*1024**3:raise PermissionError('DISK_PREFLIGHT_BELOW_15_GIB')
    results=[]
    for asset in manifest['assets']:
        p=subprocess.run(['gh','release','download',manifest['release_tag'],'--repo',os.environ['GITHUB_REPOSITORY'],'--pattern',asset['name'],'--dir',str(dest)],capture_output=True,timeout=150)
        if p.returncode:raise PermissionError('PRIVATE_ASSET_DOWNLOAD_FAILED')
        path=dest/asset['name'];h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if path.stat().st_size!=asset['bytes'] or h.hexdigest()!=asset['sha256']:raise PermissionError('ASSET_HASH_MISMATCH')
        r={k:asset[k] for k in ['name','bytes','sha256','github_asset_id']};r['restored']=True;r['full_decode']=False
        if path.suffix in {'.mp4','.flac'}:
            p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,codec_type,width,height,sample_rate','-of','json',str(path)],capture_output=True,text=True,timeout=30)
            if p.returncode:raise PermissionError('ASSET_STREAM_PROBE_FAILED')
            r['stream_probe']=json.loads(p.stdout)
        results.append(r)
    out=Path('cloud-evidence');out.mkdir(exist_ok=True)
    (out/'private-media-restoration.json').write_text(json.dumps({'status':'EXACT_PRIVATE_MEDIA_RESTORED_IN_FRESH_RUNNER','assets':results,'publication_performed':False,'production_ready':False,'windows_contacted':False,'google_calls':0},indent=2))
    print(f'PASS: {len(results)} private assets restored and hashes verified; no production or publication')
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'BLOCKED','exception_type':type(e).__name__,'details_redacted':True}));raise SystemExit(2)
