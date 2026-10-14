"""Recover original observatory rows without recollection or database mutation."""
import hashlib,json,sqlite3,tempfile,zipfile
from pathlib import Path
ARCHIVE='bbd5b7b9daa76b5ac1754eba6dc135e75f15bbeb4e72a79a0a8891c9fd64d790'
DATABASE='6d333d6f0c3dc4ac4bea650eaba050d19a2c39fed571fb4519a7a28fb628459d'
OP='phase3-2026-09-02-catalog-v2'
TABLES=['observatory_public_snapshots','observatory_coverage','observatory_cohorts','observatory_cohort_members','observatory_ledger_events']
def sha(raw):return hashlib.sha256(raw).hexdigest()
def recover(archive,destination):
    archive=Path(archive);destination=Path(destination)
    before=archive.read_bytes()
    if sha(before)!=ARCHIVE:raise PermissionError('HISTORICAL_SNAPSHOT_IDENTITY_CHANGED')
    with zipfile.ZipFile(archive) as z:raw=z.read('databases/data/hero_engine.db')
    if sha(raw)!=DATABASE:raise PermissionError('HISTORICAL_DATABASE_IDENTITY_CHANGED')
    destination.mkdir(parents=True,exist_ok=True);outputs={};verified=0
    with tempfile.TemporaryDirectory(prefix='heroverse-phase3-readonly-') as tmp:
        db=Path(tmp)/'source.db';db.write_bytes(raw)
        with sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True) as conn:
            conn.row_factory=sqlite3.Row
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise PermissionError('HISTORICAL_DATABASE_CORRUPT')
            for table in TABLES:
                rows=[dict(row) for row in conn.execute('SELECT * FROM '+table+' WHERE operation_id=? ORDER BY rowid',(OP,))]
                for row in rows:
                    if table in ['observatory_public_snapshots','observatory_ledger_events'] and row.get('payload_json') is not None:
                        if sha(row['payload_json'].encode())!=row['payload_sha256']:raise PermissionError('ORIGINAL_ROW_PAYLOAD_CHANGED')
                        verified+=1
                body=json.dumps({'recovery_version':'LOSSLESS_DATABASE_ROWS_V1','operation_id':OP,'database_sha256':DATABASE,'table':table,'rows':rows,'native_original_export_reconstructed':False},ensure_ascii=False,sort_keys=True,indent=2)+'\n'
                path=destination/(table+'.json');encoded=body.encode()
                if path.exists() and path.read_bytes()!=encoded:raise PermissionError('RECOVERED_HISTORY_COLLISION')
                if not path.exists():path.write_bytes(encoded)
                outputs[table]={'row_count':len(rows),'sha256':sha(encoded),'filename':path.name}
    if archive.read_bytes()!=before:raise PermissionError('SOURCE_CHANGED_DURING_RECOVERY')
    return {'status':'ORIGINAL_PHASE3_ROWS_RECOVERED_READ_ONLY','operation_id':OP,'archive_sha256':ARCHIVE,'database_sha256':DATABASE,'integrity_check':'ok','outputs':outputs,'payload_hashes_verified':verified,'new_market_collection':False,'new_av_analysis':False,'canonical_channel_model_recovered':False,'original_export_byte_identity_claimed':False,'publication_performed':False,'original_archive_unchanged':True}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,default=Path('HeroVerse_operational_snapshot.zip'));parser.add_argument('--destination',type=Path,default=Path('cloud-evidence/recovered-phase3-catalog-v2'));args=parser.parse_args()
    result=recover(args.archive,args.destination)
    (args.destination/'recovery-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
