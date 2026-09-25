"""One approved, read-only device diagnostic; no install/activity/inference/retry."""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path
from tools import d1_energy_screen as screen
from tools import d1_recorded_process as rp
from tools import d1_arrival_device as legacy
from tools.d1_adb_observed_client import ObservedDevice

ROOT=Path(__file__).resolve().parents[1]
ID='ENERGY-SCREEN-OBSERVE-01'
FILES=['tools/d1_energy_screen_observe.py','tools/d1_energy_screen.py','tools/d1_recorded_process.py',
       'tools/d1_adb_observed_client.py','tools/d1_arrival_device.py']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def identity():return {f:sha(ROOT/f) for f in FILES}
def prepare(source,output):
    old=json.loads(Path(source).read_text());out=Path(output);out.mkdir(parents=True,exist_ok=False)
    p=dict(id=ID,budget=dict(queries=32,total_seconds=480,query_timeout_seconds=2,gap_after_query_seconds=10,
        readiness_seconds=60,cleanup_reserve_seconds=60,installs=0,app_starts=0,inference=0,retry=0),
        source_hashes=identity(),source_plan_sha256=sha(source),device_fingerprint=old['device_fingerprint'],
        hardware_serial=old['device_hardware_serial'],screen_contract=old['screen_contract'],
        battery_start_percent=20,battery_min_percent=20,require_unplugged=True,battery_max_temperature_tenths_c=350,
        output_root=str(out.parent/'energy_screen_observe_run_v1'),registry=str(out.parent/'energy_screen_observe_registry'/ID))
    rp.write(out/'plan.json',p)
    (out/'RUN_AFTER_APPROVAL.ps1').write_text(f'''param([ValidateSet("Check","Run")][string]$Action="Check",[switch]$Approved,[string]$Serial)
$ErrorActionPreference="Stop"
Set-Location '{ROOT.as_posix()}'
$plan=Join-Path $PSScriptRoot 'plan.json'
if ($Action -eq 'Check') {{ python -B -m tools.d1_energy_screen_observe check --plan $plan }}
else {{
if (!$Approved -or !$Serial) {{ throw 'approval and serial required' }}
python -B -m tools.d1_energy_screen_observe run --plan $plan --expected-sha {sha(out/'plan.json')} --approved --serial $Serial --adb C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe
}}
if ($LASTEXITCODE -ne 0) {{ throw 'stopped, no retry' }}
''',encoding='utf-8-sig')
    return check(out/'plan.json')
def check(file):
    p=json.loads(Path(file).read_text());require(p['id']==ID and p['source_hashes']==identity(),'identity changed')
    require(p['budget']==dict(queries=32,total_seconds=480,query_timeout_seconds=2,gap_after_query_seconds=10,
        readiness_seconds=60,cleanup_reserve_seconds=60,installs=0,app_starts=0,inference=0,retry=0),'budget')
    require(not Path(p['registry']).exists() and not Path(p['output_root']).exists(),'already claimed; no resume')
    return dict(status='PC_READY_DEVICE_UNVERIFIED',plan_sha256=sha(file),device_commands=0)
def environment(d,p,folder,label):
    battery=d.call('shell','dumpsys','battery',timeout=2).stdout
    (folder/(label+'_battery.txt')).write_bytes(battery);legacy.battery_gate(p,battery.decode('utf-8',errors='strict'),True)
    thermal=d.call('shell','dumpsys','thermalservice',timeout=2).stdout
    (folder/(label+'_thermal.txt')).write_bytes(thermal)
    import re
    require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal gate')
def run(file,serial,adb,approved,expected):
    require(approved and sha(file)==expected,'approval/hash');check(file);p=json.loads(Path(file).read_text())
    registry=Path(p['registry']);registry.mkdir(parents=True,exist_ok=False)
    root=Path(p['output_root']);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+480
    rp.write(registry/'claimed.json',dict(utc=rp.utc(),monotonic_start=start,plan_sha256=expected,budget=p['budget']))
    d=ObservedDevice(adb,serial,root/'host_commands');d.deadline=min(start+60,hard-60)
    result=dict(id=ID,status='stopped_no_resume',queries_attempted=0,queries_succeeded=0,installs=0,app_starts=0,
        inference=0,retry=0,experiment_ready=False);rows=[]
    try:
        ident=d.identify(p['device_fingerprint']);require(d.call('shell','getprop','ro.serialno',timeout=2).stdout.decode().strip()==p['hardware_serial'],'hardware')
        legacy.require_stopped(d);rp.write(root/'identity.json',ident)
        next_query=time.monotonic()
        for i in range(32):
            require(time.monotonic()<hard-68,'query/reap/cleanup reserve')
            d.deadline=min(start+60,hard-60) if i==0 else hard-60
            environment(d,p,root,f'{i:02d}')
            wait=max(0,next_query-time.monotonic());require(time.monotonic()+wait+8<hard-60,'remaining gap budget')
            if wait:time.sleep(wait)
            result['queries_attempted']+=1
            rp.write(root/f'{i:02d}_attempt.json',dict(index=i,utc=rp.utc(),monotonic=time.monotonic()))
            row=screen.snapshot(d,root,f'query_{i:02d}',p['screen_contract'],settings=i in (0,31))
            rows.append(row);result['queries_succeeded']+=1
            next_query=row['host_end']+10 # Existing collector uses >=10s since previous snapshot end.
            print(json.dumps(dict(query=i+1,status=row['status'])),flush=True)
        result['status']='completed_observation_only'
    except Exception as exc:result['error']=repr(exc)
    finally:
        # Every client is synchronously reaped by ObservedDevice; no app was started.
        receipts=[json.loads(f.read_text()) for f in (root/'host_commands').glob('*/client/result.json')]
        clients=[r for r in receipts if r['command'][3:6]==['shell','sh','-c']]
        result['client_cleanup_confirmed']=all(r['returncode'] is not None and (r['status']=='returned' or r.get('root_reaped',False)) for r in receipts)
        good=[r for r in clients if r['status']=='returned'];result['query_clients']=clients
        if good:result['completed_client_statistics']=dict(median_seconds=statistics.median(r['elapsed_seconds'] for r in good),max_seconds=max(r['elapsed_seconds'] for r in good),bytes=sorted({r['stdout_bytes'] for r in good}))
        result['elapsed_seconds']=time.monotonic()-start;result['within_480_seconds']=result['elapsed_seconds']<=480
        rp.write(root/'FINAL_RECEIPT.json',result);rp.write(registry/'finished.json',result)
    return result
def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','check','run']);a.add_argument('--source');a.add_argument('--output');a.add_argument('--plan');a.add_argument('--serial');a.add_argument('--adb');a.add_argument('--approved',action='store_true');a.add_argument('--expected-sha');x=a.parse_args()
    r=prepare(x.source,x.output) if x.action=='prepare' else check(x.plan) if x.action=='check' else run(x.plan,x.serial,x.adb,x.approved,x.expected_sha)
    print(json.dumps(r,indent=2))
    if r.get('status')=='stopped_no_resume':raise SystemExit(1)
if __name__=='__main__':main()
