"""Fresh-runner qualification of reviewed Linux overlay; no live OAuth or publication."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
from apply_linux_production_overlay import apply,EXPECTED
ARCHIVE='HeroVerse_Linux_Source_Ready_20261013_v2.zip'
SHA='fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'
def main():
    archive=Path(ARCHIVE)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA:
        raise RuntimeError('immutable archive mismatch')
    with tempfile.TemporaryDirectory(prefix='heroverse-overlay-cloud-') as temporary:
        root=Path(temporary); original=root/'original'; shadow=root/'shadow'
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None: raise RuntimeError('ZIP integrity failure')
            for info in z.infolist():
                name=PurePosixPath(info.filename)
                if name.is_absolute() or '..' in name.parts or ((info.external_attr>>16)&0o170000)==0o120000:
                    raise RuntimeError('unsafe archive entry')
            z.extractall(original)
        source=original/'project'
        overlay=apply(source,shadow)
        for relative,digest in EXPECTED.items():
            if hashlib.sha256((source/relative).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('source changed during overlay')
        env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
        for suite in ('test_oauth_scope_requirements.py','test_phase6_asset_residency.py'):
            subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',suite,'-v'],
                cwd=shadow,env=env,check=True,timeout=40)
        font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        license_path=Path('/usr/share/doc/fonts-dejavu-core/copyright')
        if not font.is_file() or not license_path.is_file(): raise RuntimeError('font or license absent')
        result={'status':'FRESH_CLOUD_LINUX_OVERLAY_TESTS_PASS','archive_sha256':SHA,
            'changes':overlay['changes'],'original_preserved':True,
            'font_sha256':hashlib.sha256(font.read_bytes()).hexdigest(),
            'font_license_sha256':hashlib.sha256(license_path.read_bytes()).hexdigest(),
            'scope_fixture_tests':1,'asset_residency_fixture_tests':7,
            'real_assets_verified':False,'live_oauth_verified':False,
            'production_ready':False,'publication_performed':False,'windows_contact':False}
        print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
