"""Bounded validation of the private archive; no production or external APIs."""
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

ARCHIVE = 'HeroVerse_Linux_Source_Ready_20261013_v2.zip'
DIGEST = 'fa5467541b90f1209244acfdde974a3f6a6f114eec5afa8b99e3e288deaebb10'

def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else ARCHIVE)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == DIGEST
    with tempfile.TemporaryDirectory(prefix='heroverse-validation-') as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(source) as archive:
            assert archive.testzip() is None
            for member in archive.infolist():
                path = PurePosixPath(member.filename)
                assert not path.is_absolute() and '..' not in path.parts
                assert ((member.external_attr >> 16) & 0o170000) != 0o120000
            archive.extractall(root)
        report = json.loads((root / 'SOURCE_TRANSFER_REPORT.json').read_text())
        parsed = 0
        for item in report['files']:
            data = (root / 'project' / item['path']).read_bytes()
            assert len(data) == item['bytes']
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            if item['path'].endswith('.py'):
                ast.parse(data, filename=item['path'])
                parsed += 1
        assert len(report['files']) == 830 and parsed == 470
        lock_path = root / 'validation.lock'
        with lock_path.open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            child = subprocess.run([sys.executable, '-c',
                'import fcntl,sys; f=open(sys.argv[1]); '
                'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)', str(lock_path)],
                capture_output=True, timeout=5)
            assert child.returncode != 0 and b'BlockingIOError' in child.stderr
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg, 'ffmpeg unavailable'
        video = root / 'probe.mp4'
        subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
            'color=c=black:s=320x180:r=24', '-f', 'lavfi', '-i',
            'sine=frequency=440:sample_rate=48000', '-t', '2', '-c:v',
            'libx264', '-threads', '1', '-pix_fmt', 'yuv420p', '-c:a',
            'aac', str(video)], check=True, timeout=30)
        subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(video),
            '-f', 'null', os.devnull], check=True, timeout=20)
        receipt = {'status': 'SOURCE_AND_INFRASTRUCTURE_PASS',
            'archive_sha256': DIGEST, 'hashes_pass': 830, 'asts_pass': parsed,
            'posix_lock_pass': True, 'synthetic_render_decode_pass': True,
            'windows_contact': False, 'production_ready': False,
            'publication_performed': False, 'full_pipeline_validated': False}
        print(json.dumps(receipt, sort_keys=True))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write('```json\n' + json.dumps(receipt, indent=2) + '\n```\n')

if __name__ == '__main__':
    main()
