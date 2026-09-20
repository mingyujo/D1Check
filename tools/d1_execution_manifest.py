"""Atomic bounded execution journal. No ADB and no workload changes.

One host holds an OS-released exclusive lock for the entire run/recovery. A
completed session is immutable and a failed session permanently halts this run.
"""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import uuid
from tools import d1_telemetry_v4 as v

STATES={'pending','running','completed','failed'}


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


def sealed(value):
    value=copy.deepcopy(value);value.pop('manifest_sha256',None)
    value['manifest_sha256']=v.sha(value);return value


def read(path):
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if value!=sealed(value):raise ValueError('partial/corrupt manifest hash')
    states=[s['state'] for s in value['sessions']]
    if len(states)!=30 or set(states)-STATES or states.count('running')>1:raise ValueError('invalid state/count')
    active=False
    for state in states:
        if state!='completed':active=True
        elif active:raise ValueError('non-prefix completion')
    return value


def atomic_write(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
    data=v.canonical(sealed(value))
    with tmp.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    # Windows MoveFileEx-backed replace is atomic on this local filesystem;
    # directory fsync is not provided by Windows Python. File bytes were fsynced.
    return read(path)


class HostLock:
    def __init__(self,root):self.path=Path(root)/'host.lock';self.file=None
    def __enter__(self):
        self.file=self.path.open('a+b');self.file.seek(0)
        if self.path.stat().st_size==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise RuntimeError('live owner; do not duplicate execution')
        return self
    def __exit__(self,*args):self.file.close()


class Journal:
    def __init__(self,root):self.root=Path(root);self.path=self.root/'execution_manifest.json'
    def create(self,plan,binding):
        if self.path.exists():raise ValueError('manifest already exists')
        entries=[]
        for e in plan['entries']:
            m=plan['manifests'][e['session_id']]
            entries.append(dict(**e,state='pending',request_count=len(m['requests'])+len(m['warmup_requests']),
                native_manifest_sha256=v.sha(m),started_utc=None,finished_utc=None,host_process=None,
                device_session=None,validation=None,cleanup=None))
        if len(entries)!=30 or sum(s['request_count'] for s in entries)!=480:raise ValueError('frozen counts')
        return self.save(dict(protocol='bounded-execution-atomic-v1',revision=0,binding=binding,
             sessions=entries,history=[],halt_reason=None,created_utc=utc()),'created')
    def load(self):return read(self.path)
    def save(self,d,reason):
        d=copy.deepcopy(d);d['revision']+=1;d['updated_utc']=utc()
        done=[s['session_id'] for s in d['sessions'] if s['state']=='completed']
        d['last_completed_session']=done[-1] if done else None
        first=next((s for s in d['sessions'] if s['state']!='completed'),None)
        d['next_pending_session']=first['session_id'] if first and first['state']=='pending' and not d['halt_reason'] else None
        d['history'].append(dict(utc=utc(),reason=reason,revision=d['revision']))
        journal=self.root/'manifest_history';journal.mkdir(exist_ok=True)
        archive=journal/f"{d['revision']:05d}.json"
        if archive.exists():raise ValueError('revision replay')
        # The authoritative manifest is replaced first. An interrupted archive
        # write cannot strand a future revision or require replay of a session.
        result=atomic_write(self.path,d)
        atomic_write(archive,result)
        return result
    def start(self,sid,host):
        d=self.load()
        if d['halt_reason'] or d['next_pending_session']!=sid:raise ValueError('not next pending; no retry')
        s=next(s for s in d['sessions'] if s['session_id']==sid)
        s.update(state='running',started_utc=utc(),host_process=host,
                 device_session={'session_id':sid,'pid':None})
        return self.save(d,'running before Activity start '+sid)
    def device_pid(self,sid,pid):
        d=self.load();s=next(s for s in d['sessions'] if s['session_id']==sid)
        if s['state']!='running':raise ValueError('not running')
        s['device_session']['pid']=pid;return self.save(d,'device PID '+sid)
    def complete(self,sid,validation,cleanup,recovered=False):
        required={'terminal','schema','identity','equivalence','provenance','timing','memory','thermal'}
        if any(validation.get(k) is not True for k in required) or cleanup.get('process_absent') is not True:
            raise ValueError('incomplete validation or cleanup')
        d=self.load();s=next(s for s in d['sessions'] if s['session_id']==sid)
        if s['state']!='running':raise ValueError('cannot complete/replay non-running session')
        s.update(state='completed',finished_utc=utc(),validation=validation,cleanup=cleanup)
        return self.save(d,('recovered complete artifact ' if recovered else 'completed ')+sid)
    def fail(self,sid,reason):
        d=self.load();s=next(s for s in d['sessions'] if s['session_id']==sid)
        if s['state']!='running':raise ValueError('only running becomes failed')
        s.update(state='failed',finished_utc=utc());d['halt_reason']=reason
        return self.save(d,'failed; no retry '+sid)
    def halt(self,reason):
        d=self.load();d['halt_reason']=reason;return self.save(d,'preflight halt: '+reason)
