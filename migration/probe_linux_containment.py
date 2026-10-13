"""Probe an owned transient systemd unit; never run a HeroVerse worker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

def main():
    unit='heroverse-probe-'+uuid.uuid4().hex
    code = '''import json,os,pathlib
cg=next(line.split(':',2)[2] for line in pathlib.Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
p=pathlib.Path('/sys/fs/cgroup')/cg.lstrip('/')
keys=('memory.max','memory.swap.max','memory.oom.group','pids.max')
print(json.dumps({'cgroup':cg,'uid':os.getuid(),'limits':{k:(p/k).read_text().strip() for k in keys}}))
'''
    argv=['sudo','-n','systemd-run','--quiet','--wait','--pipe','--collect',
          '--unit='+unit,'--property=User='+str(os.getuid()),
          '--property=MemoryMax=67108864','--property=MemorySwapMax=0',
          '--property=TasksMax=16','--property=RuntimeMaxSec=10',
          '--property=KillMode=control-group','--property=OOMPolicy=kill',
          '--property=NoNewPrivileges=yes','--property=ProtectControlGroups=yes',
          sys.executable,'-c',code]
    result=subprocess.run(argv,capture_output=True,text=True,timeout=20)
    if result.returncode:
        raise RuntimeError('CONTAINMENT_UNAVAILABLE: '+result.stderr[-1200:])
    observation=json.loads(result.stdout)
    assert observation['limits']['memory.max']=='67108864'
    assert observation['limits']['memory.swap.max']=='0'
    assert observation['limits']['pids.max']=='16'
    assert unit in observation['cgroup']
    print(json.dumps({'status':'TRANSIENT_CGROUP_CAPABILITY_PASS','observation':observation,
      'worker_started':False,'kill_on_parent_close_qualified':False,
      'production_ready':False,'release_authority':False}))

if __name__=='__main__': main()
