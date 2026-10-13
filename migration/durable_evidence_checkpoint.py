"""Claim and checkpoint bounded observations; never modifies production queues."""
import json,os,sqlite3,subprocess,sys
from pathlib import Path
STATE=Path('migration/evidence/observer-state.json')
CLAIM=Path('migration/evidence/observer-claim.json')
SQL=Path('migration/evidence/observer-ledger.sql')
INITIAL=Path('migration/evidence/quota-continuation-38476824992.sql')
def git(*args):
    p=subprocess.run(['git',*args],capture_output=True,text=True,timeout=40)
    if p.returncode:raise RuntimeError('DURABLE_GIT_CHECKPOINT_FAILED')
    return p.stdout.strip()
def restore_ledger(sql,destination):
    if destination.exists():raise PermissionError('LEDGER_DESTINATION_ALREADY_EXISTS')
    c=sqlite3.connect(destination)
    try:
        c.executescript(sql.read_text())
        if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise PermissionError('LEDGER_INTEGRITY_FAILED')
        tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
        if not {'general_quota_debits','upload_quota_debits','composed_quota_reservations'}<=tables:raise PermissionError('LEDGER_SCHEMA_MISSING')
    finally:c.close()
def commit(message):
    git('add','migration/evidence');git('commit','-m',message);git('push','origin','HEAD:main')
def main(mode):
    if os.environ.get('GITHUB_REPOSITORY')!='matheusmagah-cpu/heroverse-engine':raise PermissionError('REPOSITORY_MISMATCH')
    run=os.environ['GITHUB_RUN_ID']
    git('config','user.name','HeroVerse bounded observer');git('config','user.email','heroverse-observer@users.noreply.github.com')
    if mode=='claim':
        git('pull','--ff-only','origin','main')
        if CLAIM.exists():raise PermissionError('PREVIOUS_EXECUTION_REQUIRES_LEDGER_RECONCILIATION')
        if not SQL.exists():SQL.write_text(INITIAL.read_text())
        CLAIM.write_text(json.dumps({'run_id':run,'status':'CLAIMED_BEFORE_REMOTE_CALLS'}))
        commit('Claim bounded observer before remote effects')
    elif mode=='checkpoint':
        if not CLAIM.exists() or json.loads(CLAIM.read_text())['run_id']!=run:raise PermissionError('CLAIM_MISMATCH')
        db=Path('cloud-evidence/quota-ledger.sqlite3')
        if not db.exists():raise PermissionError('LEDGER_EXPORT_MISSING_KEEP_CLAIM')
        c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
        if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise PermissionError('LEDGER_EXPORT_INVALID_KEEP_CLAIM')
        SQL.write_text('\n'.join(c.iterdump())+'\n');c.close()
        observed=Path('cloud-evidence/evidence.json')
        if observed.exists():
            evidence=json.loads(observed.read_text())
            if evidence.get('publication_performed') is not False:
                raise PermissionError('OBSERVATION_EFFECT_BOUNDARY_INVALID')
            immutable=Path('migration/evidence')/('observer-'+run+'.json')
            if immutable.exists():raise PermissionError('OBSERVATION_ALREADY_PERSISTED')
            immutable.write_text(observed.read_text())
        STATE.write_text(json.dumps({'last_checkpointed_run':run,'collection_complete':Path('cloud-evidence/summary.json').exists(),'publication_performed':False}))
        CLAIM.unlink();commit('Checkpoint original observer ledger after bounded run')
    else:raise ValueError('UNKNOWN_CHECKPOINT_MODE')
if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception as e:
        print(json.dumps({'status':'BLOCKED','exception_type':type(e).__name__,'remote_details_redacted':True}));sys.exit(2)
