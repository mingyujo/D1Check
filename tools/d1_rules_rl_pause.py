"""Verified-owner in-memory pause/resume of this study's Windows worker.

No learner code/state/RNG is changed. Disk recovery and process suspension are
different operations: suspension requires keeping the PC/process alive.
"""
import argparse
import ctypes
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
from tools import d1_rules_rl_common as c


class FileTime(ctypes.Structure):
    _fields_=[('low',ctypes.c_uint32),('high',ctypes.c_uint32)]


def filetime(value):return (value.high<<32)|value.low


class Owner:
    def __init__(self):
        if os.name!='nt':raise ValueError('Windows worker only')
        self.meta=c.read(c.OUTPUT/'worker_process.json');self.pid=self.meta['pid']
        if c.digest(c.OUTPUT/'worker.py')!=self.meta['worker_sha256']:raise ValueError('driver source changed')
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.k.OpenProcess.restype=ctypes.c_void_p
        self.k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
        self.k.CloseHandle.argtypes=[ctypes.c_void_p]
        self.k.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.POINTER(FileTime)]*4)]
        self.k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
        self.k.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
        self.n=ctypes.WinDLL('ntdll')
        for name in ('NtSuspendProcess','NtResumeProcess'):
            fn=getattr(self.n,name);fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_long
        self.handle=self.k.OpenProcess(0x1800,False,self.pid)
        if not self.handle:raise OSError(ctypes.get_last_error(),'worker unavailable; no replacement process')
        try:
            self.creation,self.cpu=self.times()
            created=(self.creation-116444736000000000)/10000000
            started=datetime.fromisoformat(self.meta['started_utc']).timestamp()
            if not 0<=started-created<=2:raise ValueError('PID creation identity mismatch')
            text=ctypes.create_unicode_buffer(32768);length=ctypes.c_uint32(len(text))
            if not self.k.QueryFullProcessImageNameW(self.handle,0,text,ctypes.byref(length)):raise OSError(ctypes.get_last_error())
            if os.path.normcase(text.value)!=os.path.normcase(os.path.abspath(self.meta['command'][0])):raise ValueError('worker executable mismatch')
            exit_code=ctypes.c_uint32()
            if not self.k.GetExitCodeProcess(self.handle,ctypes.byref(exit_code)) or exit_code.value!=259:
                raise ValueError('worker already exited; no suspension')
        except BaseException:self.close();raise

    def times(self):
        creation,end,kernel,user=(FileTime() for _ in range(4))
        if not self.k.GetProcessTimes(self.handle,ctypes.byref(creation),ctypes.byref(end),ctypes.byref(kernel),ctypes.byref(user)):
            raise OSError(ctypes.get_last_error())
        return filetime(creation),filetime(kernel)+filetime(user)

    def close(self):
        if self.handle:self.k.CloseHandle(self.handle);self.handle=None


def control(action):
    path=c.OUTPUT/'user_pause.json'
    if action=='Status':
        return c.read(path) if path.exists() else dict(status='not_paused_by_user')
    owner=Owner()
    try:
        prior=c.read(path) if path.exists() else None
        if action=='Pause':
            if prior and prior['status']=='suspended':raise ValueError('already suspended; no nested suspension')
            status=owner.n.NtSuspendProcess(owner.handle)
            if status!=0:raise RuntimeError('suspend refused: '+hex(status&0xffffffff))
            # The in-memory learner is preserved exactly. Do not rewrite its
            # status or call Run/Resume on top of a living suspended owner.
            record=dict(status='suspended',pid=owner.pid,process_creation_filetime=owner.creation,
                mode='in_memory_same_process',paused_utc=c.utc(),driver_sha256=owner.meta['worker_sha256'],
                deadline_utc=c.read(c.OUTPUT/'campaign.json')['deadline_utc'],
                includes_pause_in_wall_budget=True,device_commands=0,new_environment_runs=0,
                pc_shutdown_supported_by_this_mode=False)
            try:c.atomic(path,record)
            except BaseException:
                # Never leave an unrecorded suspended worker if publication fails.
                owner.n.NtResumeProcess(owner.handle)
                raise
            time.sleep(.15);_,first=owner.times();time.sleep(.15);_,second=owner.times()
            record['CPU_time_unchanged_while_suspended']=first==second
            state=c.read(c.OUTPUT/'rl/state.json')
            record['last_disk_checkpoints']={key:dict(update=value['update'],episodes=value['episodes'],
                file=value['file'],sha256=value['sha256'],hash_verified=c.digest(c.OUTPUT/'rl'/value['file'])==value['sha256'])
                for key,value in state['learners'].items()}
            c.atomic(path,record);return record
        if not prior or prior['status']!='suspended' or prior['pid']!=owner.pid or prior['process_creation_filetime']!=owner.creation:
            raise ValueError('no identical suspended owner to resume')
        if datetime.now(timezone.utc)>=datetime.fromisoformat(prior['deadline_utc']):
            raise ValueError('original wall budget expired; no automatic new budget')
        for name,sha in c.read(c.OUTPUT/'rl_contract_before_run.json')['sources'].items():
            if c.digest(c.ROOT/name)!=sha:raise ValueError('numeric source changed while paused: '+name)
        status=owner.n.NtResumeProcess(owner.handle)
        if status!=0:raise RuntimeError('resume refused: '+hex(status&0xffffffff))
        prior.update(status='resumed',resumed_utc=c.utc())
        c.atomic(path,prior);return prior
    finally:owner.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--action',choices=['Status','Pause','Resume'],default='Status');args=p.parse_args()
    print(json.dumps(control(args.action),ensure_ascii=False,indent=2))
