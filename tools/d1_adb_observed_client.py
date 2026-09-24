"""One-shot ADB client evidence; never explicitly starts/stops/reconnects a server.

The smart-socket read checks an already listening server without spawning ADB.
A race remains between this check and ADB execution: ADB's own internal behavior
is not under our control. No host retry is permitted or hidden by the wrapper.
"""
import os
from pathlib import Path
import socket
import subprocess
import time
from tools import d1_arrival_device as legacy
from tools import d1_recorded_process as rp

ENV_KEYS=('ADB_SERVER_SOCKET','ADB_SERVER_PORT','ANDROID_ADB_SERVER_PORT','ANDROID_ADB_SERVER_ADDRESS')

def host_snapshot(timeout=2):
    """Read-only current Windows processes/listener, never an ADB command."""
    script="Get-CimInstance Win32_Process -Filter \"Name='adb.exe'\" | Select-Object ProcessId,ParentProcessId,ExecutablePath,CreationDate,CommandLine | ConvertTo-Json -Compress; Get-NetTCPConnection -LocalPort 5037 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | ConvertTo-Json -Compress"
    start=time.monotonic()
    try:
        x=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=timeout)
        return dict(utc=rp.utc(),status='captured' if x.returncode==0 else 'query_failed',
            returncode=x.returncode,stdout=x.stdout.decode(errors='replace'),stderr=x.stderr.decode(errors='replace'),elapsed_seconds=time.monotonic()-start)
    except subprocess.TimeoutExpired as exc:
        return dict(utc=rp.utc(),status='query_timeout',stdout=(exc.stdout or b'').decode(errors='replace'),
            stderr=(exc.stderr or b'').decode(errors='replace'),elapsed_seconds=time.monotonic()-start)
    except OSError as exc:
        return dict(utc=rp.utc(),status='query_unavailable',error=repr(exc),elapsed_seconds=time.monotonic()-start)

def server_probe(timeout=1):
    deadline=time.monotonic()+timeout
    def exact(stream,n):
        data=b''
        while len(data)<n:
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('server probe total deadline')
            stream.settimeout(left)
            part=stream.recv(n-len(data))
            if not part:raise RuntimeError('server response incomplete')
            data+=part
        return data
    # All supported plans pin localhost5037. Never silently redirect via environment.
    if any(os.environ.get(k) for k in ENV_KEYS):raise RuntimeError('ADB server environment override; unsupported')
    with socket.create_connection(('127.0.0.1',5037),timeout=timeout) as stream:
        request=b'host:version';stream.sendall(f'{len(request):04x}'.encode()+request)
        if exact(stream,4)!=b'OKAY':raise RuntimeError('ADB server not ready')
        size=int(exact(stream,4),16)
        if not 0<size<=32:raise RuntimeError('invalid ADB server version response')
        version=exact(stream,size).decode('ascii')
        if version!='0029':raise RuntimeError('server protocol mismatch; do not invoke auto-restarting client')
        return dict(address='127.0.0.1',port=5037,protocol_version=version)

class ObservedDevice(legacy.Device):
    def __init__(self,adb,serial,root):
        if not serial:raise ValueError('explicit approved serial required')
        super().__init__(adb,serial);self.root=Path(root);self.sequence=0

    def failure_snapshot(self):
        remaining=min(2,self.deadline-time.monotonic()) if self.deadline else 2
        return host_snapshot(remaining) if remaining>0 else dict(status='skipped_no_remaining_time')

    def call(self,*args,timeout=30,check=True):
        remaining=self.deadline-time.monotonic() if self.deadline else timeout+6
        if remaining<=6:raise TimeoutError('insufficient server/client/reap budget')
        folder=self.root/f'{self.sequence:04d}';self.sequence+=1;folder.mkdir(parents=True,exist_ok=False)
        context=dict(utc=rp.utc(),adb_path=self.adb,serial=self.serial,
            server_environment={k:os.environ.get(k) for k in ENV_KEYS},vendor_keys_env_present='ADB_VENDOR_KEYS' in os.environ,
            phase='before_client',client_launch_intent=False)
        if self.sequence==1:context['current_host_snapshot']=host_snapshot(min(2,max(.1,remaining-6)))
        try:context['server']=server_probe(min(1,remaining-5))
        except Exception as error:
            context.update(status='server_precheck_failed',error=repr(error));rp.write(folder/'context.json',context)
            rp.write(folder/'host_after_failure.json',self.failure_snapshot())
            raise RuntimeError('existing ADB server unavailable; no client launch/restart/retry') from error
        if self.deadline and self.deadline-time.monotonic()<=5:
            context.update(status='client_budget_exhausted',client_launch_intent=False);rp.write(folder/'context.json',context)
            raise TimeoutError('no remaining client/reap budget')
        context.update(status='server_precheck_pass',client_launch_intent=True);rp.write(folder/'context.json',context)
        command=[self.adb,'-s',self.serial,*map(str,args)]
        result=rp.run(command,folder/'client',min(timeout,max(.01,self.deadline-time.monotonic()-5)) if self.deadline else timeout,
                      command,root_only=True)
        stdout=(folder/'client/stdout.bin').read_bytes();stderr=(folder/'client/stderr.bin').read_bytes()
        automatic_server_change=any(x in stderr.lower() for x in (b'daemon not running',b'daemon started',b'killing'))
        if result['status'] not in ('returned','nonzero_exit') or (check and result['returncode']) or automatic_server_change:
            rp.write(folder/'host_after_failure.json',self.failure_snapshot())
            raise RuntimeError(f'ADB client failed: {folder}; status={result["status"]}, exit={result["returncode"]}; no retry')
        return subprocess.CompletedProcess(command,result['returncode'],stdout,stderr)
