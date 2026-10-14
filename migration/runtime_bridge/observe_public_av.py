"""Optional AV phase of the existing bounded observer and its existing ledger."""
import hashlib,json,os,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gemini_public_av import analyze,digest

RECOVERY=Path('migration/evidence/av-recovery-pending.json')
SOURCE={'video_id':'7GvhWbXDWHQ','duration_seconds':1178,'visibility':'PUBLIC'}
POLICY=Path('migration/evidence/gemini-free-runtime-policy.json')

class ExistingObserverLedger:
    def __init__(self,db,run):
        self.db,self.run=Path(db),run
        self.recovery_path=None
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
        if self.recovery_path is not None:
            recovery=json.loads(self.recovery_path.read_text())
            if recovery.get('status')!='PENDING' or recovery.get('attempts')!=0:
                raise PermissionError('BOUNDED_AV_RECOVERY_ALREADY_CONSUMED')
            recovery.update(status='ATTEMPT_CLAIMED',attempts=1,run_id=self.run)
            self.recovery_path.write_text(json.dumps(recovery,sort_keys=True)+'\n')
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
    scheduled=os.environ.get('GITHUB_EVENT_NAME')=='schedule'
    if scheduled:
        if not RECOVERY.is_file():return 0
        recovery=json.loads(RECOVERY.read_text())
        if (recovery.get('status')!='PENDING' or recovery.get('attempts')!=0
                or recovery.get('utc_date')!=datetime.now(timezone.utc).date().isoformat()):
            print(json.dumps({'status':'NO_AV_RECOVERY_DUE','provider_called':False}))
            return 0
    key=os.environ.get('HERO_GEMINI_API_KEY','')
    if not key or not POLICY.is_file():
        print(json.dumps({'status':'AV_SECURE_PROVISIONING_REQUIRED','provider_called':False,
                          'publication_authorized':False}))
        return 2
    ledger=ExistingObserverLedger('cloud-evidence/quota-ledger.sqlite3',os.environ['GITHUB_RUN_ID'])
    if scheduled:ledger.recovery_path=RECOVERY
    receipt=analyze(SOURCE,api_key=key,policy=json.loads(POLICY.read_text()),
        reserve=ledger.reserve,persist=ledger.persist)
    print(json.dumps({'status':receipt['status'],'review_status':receipt['review_status'],
                      'publication_authorized':False}))
    return 0 if receipt['status']=='AWAITING_AV_REVIEW' else 2


def diagnose():
    import urllib.request,urllib.error
    from durable_evidence_checkpoint import CLAIM
    run=os.environ['GITHUB_RUN_ID']
    if not CLAIM.exists() or json.loads(CLAIM.read_text()).get('run_id')!=run:
        raise PermissionError('EXISTING_OBSERVER_CLAIM_REQUIRED')
    key=os.environ.get('HERO_GEMINI_API_KEY','')
    policy=json.loads(POLICY.read_text())
    if hashlib.sha256(key.encode()).hexdigest()!=policy['key_sha256']:
        raise PermissionError('KEY_BINDING_MISMATCH')
    model=policy['model']
    from gemini_public_av import FREE_MODELS
    if model not in FREE_MODELS:raise PermissionError('VERIFIED_FREE_MODEL_REQUIRED')
    receipt={'status':'UNAVAILABLE','model':model,
        'method':'GET_MODEL_METADATA','video_processed':False,
        'publication_authorized':False,'details_redacted':True}
    request=urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/'+model,
        headers={'x-goog-api-key':key})
    try:
        with urllib.request.urlopen(request,timeout=20) as response:
            data=json.loads(response.read(100000))
        receipt.update(status='MODEL_METADATA_AVAILABLE',
            model_name=data.get('name'),methods=data.get('supportedGenerationMethods',[]))
    except urllib.error.HTTPError as error:
        receipt['http_status']=error.code
        try:
            data=json.loads(error.read(10000))
            status=data.get('error',{}).get('status')
            if status in ('INVALID_ARGUMENT','UNAUTHENTICATED','PERMISSION_DENIED',
                    'NOT_FOUND','RESOURCE_EXHAUSTED','UNAVAILABLE'):
                receipt['provider_status']=status
            reasons=[detail.get('reason') for detail in data.get('error',{}).get('details',[])
                if detail.get('reason') in ('API_KEY_INVALID','API_KEY_EXPIRED',
                'SERVICE_DISABLED','API_KEY_SERVICE_BLOCKED','API_KEY_HTTP_REFERRER_BLOCKED',
                'API_KEY_IP_ADDRESS_BLOCKED','CONSUMER_INVALID','BILLING_DISABLED')]
            receipt['provider_reasons']=reasons
        except Exception:pass
    except Exception:
        receipt['status']='NETWORK_OR_PROVIDER_UNAVAILABLE'
    path=Path('migration/evidence')/('gemini-model-diagnostic-'+run+'.json')
    path.write_text(json.dumps(receipt,sort_keys=True)+'\n')
    print(json.dumps(receipt))
    return 0 if receipt['status']=='MODEL_METADATA_AVAILABLE' else 2

if __name__=='__main__':
    try:sys.exit(diagnose() if len(sys.argv)>1 and sys.argv[1]=='diagnose' else main())
    except Exception:
        print(json.dumps({'status':'AV_BLOCKED','details_redacted':True,'publication_authorized':False}))
        sys.exit(2)
