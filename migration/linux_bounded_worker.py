"""Linux candidate containment. No publication or gate authority.

systemd assigns limits before exec. The service's only stdin writer is the
supervisor: closing/dying causes keeper exit and KillMode=control-group cleanup.
Workers cannot write cgroups, gain privilege or contact the host service bus.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import threading
import time
import uuid

def limits(timeout, memory, logs):
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=600:
        raise ValueError('invalid timeout')
    if type(memory) is not int or not 64*1024**2<=memory<=4*1024**3:
        raise ValueError('invalid memory ceiling')
    if type(logs) is not int or not 1024<=logs<=16*1024**2:
        raise ValueError('invalid log ceiling')

def current_cgroup():
    raw=Path('/proc/self/cgroup').read_text()
    name=next(line.split(':',2)[2] for line in raw.splitlines() if line.startswith('0::'))
    return name,Path('/sys/fs/cgroup')/name.lstrip('/')

def keeper(unit, memory, argv):
    name,cg=current_cgroup()
    if name!='/system.slice/'+unit+'.service':raise RuntimeError('wrong service membership')
    for key,value in {'memory.max':str(memory),'memory.swap.max':'0','memory.oom.group':'1','pids.max':'128'}.items():
        if (cg/key).read_text().strip()!=value:raise RuntimeError('wrong enforced '+key)
    if os.getuid()==0 or os.access(cg/'cgroup.procs',os.W_OK):
        raise RuntimeError('worker must be unprivileged with read-only cgroups')
    def owner_lifetime():
        # EOF cannot be forged by a worker: child stdin is DEVNULL and this fd
        # is never inherited by measurement children.
        while os.read(0,1): pass
        os._exit(75)
    threading.Thread(target=owner_lifetime,daemon=True).start()
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,close_fds=True)
    # No buffered-I/O finalization while the lifeline reader is blocked.
    os._exit(child.wait())

def run_bounded(argv,*,cwd,timeout_seconds=30,memory_bytes=256*1024**2,max_log_bytes=1024**2):
    limits(timeout_seconds,memory_bytes,max_log_bytes)
    if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and '\x00' not in x for x in argv):
        raise ValueError('trusted argument list required')
    cwd=Path(cwd).resolve(strict=True)
    unit='heroverse-worker-'+uuid.uuid4().hex
    module=Path(__file__).resolve(strict=True)
    command=['sudo','-n','systemd-run','--quiet','--wait','--pipe','--collect',
      '--service-type=exec','--unit='+unit,
      '--property=User='+str(os.getuid()),'--property=WorkingDirectory='+str(cwd),
      '--property=MemoryMax='+str(memory_bytes),'--property=MemorySwapMax=0',
      '--property=TasksMax=128','--property=RuntimeMaxSec='+str(timeout_seconds+2),
      '--property=KillMode=control-group','--property=TimeoutStopSec=1',
      '--property=OOMPolicy=kill','--property=NoNewPrivileges=yes',
      '--property=ProtectControlGroups=yes','--property=ProtectSystem=full',
      '--property=InaccessiblePaths=/run/dbus/system_bus_socket /run/user',
      '--property=BindReadOnlyPaths='+str(module),
      sys.executable,str(module),'keeper',unit,str(memory_bytes),*argv]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,close_fds=True)
    output=bytearray(); status=None; started=time.monotonic(); exceeded=False
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ)
    try:
        while True:
            if time.monotonic()-started>timeout_seconds and not exceeded:
                status='TIMEOUT'; exceeded=True;process.stdin.close()
            for key,_ in selector.select(.025):
                chunk=os.read(key.fileobj.fileno(),4096)
                if not chunk: selector.unregister(key.fileobj); continue
                available=max_log_bytes-len(output)
                output.extend(chunk[:max(available,0)])
                if len(chunk)>available and not exceeded:
                    status='LOG_LIMIT';exceeded=True;process.stdin.close()
            if process.poll() is not None and not selector.get_map():break
            if exceeded and time.monotonic()-started>timeout_seconds+10:
                raise RuntimeError('owned service cleanup not confirmed')
        status=status or ('SUCCEEDED' if process.returncode==0 else 'FAILED')
    finally:
        if not process.stdin.closed:process.stdin.close()
        selector.close()
        process.stdout.close()
        try:process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            # Never promote incomplete cleanup; no unbounded fallback/host kill.
            raise RuntimeError('owned launcher did not settle')
    return {'status':status,'returncode':process.returncode,'unit':unit,
       'stdout':output.decode('utf-8',errors='replace'),'log_bytes':len(output),
       'elapsed_seconds':time.monotonic()-started,'memory_limit_kind':'LINUX_CGROUP_RESIDENT_ACCOUNTING',
       'memory_limit_bytes':memory_bytes,'release_authority':False,'production_ready':False}

if __name__=='__main__':
    if len(sys.argv)<5 or sys.argv[1]!='keeper':raise SystemExit('internal keeper only')
    raise SystemExit(keeper(sys.argv[2],int(sys.argv[3]),sys.argv[4:]))
