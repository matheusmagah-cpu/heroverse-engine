"""Optional AV phase of the existing bounded observer and its existing ledger."""
import hashlib,json,os,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gemini_public_av import analyze,digest

SOURCE={'video_id':'7GvhWbXDWHQ','duration_seconds':1178,'visibility':'PUBLIC'}
POLICY=Path('migration/evidence/gemini-free-runtime-policy.json')

class ExistingObserverLedger:
    def __init__(self,db,run):
        self.db,self.run=Path(db),run
        from durable_evidence_checkpoint import CLAIM
        if (not CLAIM.is_file() or json.loads(CLAIM.read_text()).get('run_id')!=run
                or not self.db.is_file()):
            raise PermissionError('EXISTING_OBSERVER_CLAIM_AND_LEDGER_REQUIRED')
        with sqlite3.connect(self.db) as c:
            if c.execute('pragma integrity_check').fetchone()[0]!='ok':
                raise PermissionError('EXISTING_LEDGER_INTEGRITY_REQUIRED')
            c.execute('''CREATE TABLE IF NOT EXISTS public_av_reservations(
                key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                day TEXT NOT NULL, seconds INTEGER NOT NULL,
                state TEXT NOT NULL, receipt_path TEXT, receipt_hash TEXT)''')
    def checkpoint(self,message):
        from durable_evidence_checkpoint import SQL,commit
        with sqlite3.connect(self.db) as c:
            SQL.write_text('\n'.join(c.iterdump())+'\n')
        commit(message)
    def reserve(self,key,request_hash,seconds,cap):
        day=datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db) as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT request_hash,state,receipt_path,receipt_hash FROM public_av_reservations WHERE key=?',(key,)).fetchone()
            base={'key':key,'request_hash':request_hash}
            if row:
                if row[0]!=request_hash: raise PermissionError('AV_REQUEST_CHANGED')
                if row[1]=='COMPLETED':
                    raw=Path(row[2]).read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=row[3]:
                        raise PermissionError('AV_RECEIPT_HASH_CHANGED')
                    return {**base,'status':'REPLAY','receipt':json.loads(raw)}
                return {**base,'status':'BLOCKED'}
            unresolved=c.execute("SELECT COUNT(*) FROM public_av_reservations WHERE state='CLAIMED'").fetchone()[0]
            used=c.execute('SELECT COALESCE(SUM(seconds),0) FROM public_av_reservations WHERE day=?',(day,)).fetchone()[0]
            if unresolved or used+seconds>cap: return {**base,'status':'BLOCKED'}
            c.execute('INSERT INTO public_av_reservations VALUES(?,?,?,?,?,?,?)',
                (key,request_hash,day,seconds,'CLAIMED',None,None))
        # Successful push is required BEFORE provider receives the request.
        self.checkpoint('Reserve bounded AV effect in existing observer ledger')
        return {**base,'status':'NEW','durable':True}
    def persist(self,receipt):
        path=Path('migration/evidence')/('public-av-'+receipt['key'].split(':')[1]+'.json')
        raw=json.dumps(receipt,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
        with path.open('xb') as f:f.write(raw)
        with sqlite3.connect(self.db) as c:
            c.execute('BEGIN IMMEDIATE')
            result=c.execute("UPDATE public_av_reservations SET state='COMPLETED',receipt_path=?,receipt_hash=? WHERE key=? AND request_hash=? AND state='CLAIMED'",
                (str(path),hashlib.sha256(raw).hexdigest(),receipt['key'],receipt['request_hash']))
            if result.rowcount!=1: raise PermissionError('AV_RESERVATION_MISMATCH')
        self.checkpoint('Checkpoint unreviewed AV receipt and preserve provider debit')

def main():
    if os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine':
        raise PermissionError('REPOSITORY_MISMATCH')
    key=os.environ.get('HERO_GEMINI_API_KEY','')
    if not key or not POLICY.is_file():
        print(json.dumps({'status':'AV_SECURE_PROVISIONING_REQUIRED','provider_called':False,
                          'publication_authorized':False}))
        return 2
    ledger=ExistingObserverLedger('cloud-evidence/quota-ledger.sqlite3',os.environ['GITHUB_RUN_ID'])
    receipt=analyze(SOURCE,api_key=key,policy=json.loads(POLICY.read_text()),
        reserve=ledger.reserve,persist=ledger.persist)
    print(json.dumps({'status':receipt['status'],'review_status':receipt['review_status'],
                      'publication_authorized':False}))
    return 0 if receipt['status']=='AWAITING_AV_REVIEW' else 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        print(json.dumps({'status':'AV_BLOCKED','details_redacted':True,'publication_authorized':False}))
        sys.exit(2)
