"""Restore private snapshots read-only; never merge queues or change ledger."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import tempfile
import zipfile

DIGEST='bbd5b7b9daa76b5ac1754eba6dc135e75f15bbeb4e72a79a0a8891c9fd64d790'

def main():
    archive=Path('HeroVerse_operational_snapshot.zip')
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==DIGEST
    with tempfile.TemporaryDirectory(prefix='heroverse-snapshot-') as tmp:
        root=Path(tmp)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for item in z.infolist():
                path=PurePosixPath(item.filename)
                assert not path.is_absolute() and '..' not in path.parts
                assert ((item.external_attr >> 16) & 0o170000)!=0o120000
            z.extractall(root)
        manifest=json.loads((root/'OPERATIONAL_SNAPSHOT_MANIFEST.json').read_text())
        checks=[]
        for item in manifest['databases']:
            path=root/item['snapshot_path']; raw=path.read_bytes()
            assert len(raw)==item['bytes']
            assert hashlib.sha256(raw).hexdigest()==item['sha256']
            with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
                for table, count in item['rows_by_table'].items():
                    identifier='"'+table.replace('"','""')+'"'
                    assert db.execute('SELECT COUNT(*) FROM '+identifier).fetchone()[0]==count
            assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
            checks.append({'path':item['source'],'sha256':item['sha256'],'integrity':'PASS','writes':0})
        assert len(checks)==3
        print(json.dumps({'status':'PRIVATE_SNAPSHOT_READONLY_RESTORE_PASS','databases':checks,
           'active_queue_restored':False,'ledger_changed':False,'publication_authority':False}))

if __name__=='__main__':main()
