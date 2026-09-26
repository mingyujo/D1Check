"""PC-only preparation/check for a single-use synthetic arrival energy collection.

`run` is deliberately in a separate module and requires a later explicit approval.
"""
from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_energy_collection as old
from tools import d1_apk_identity as apk

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'ARRIVAL-ENERGY-SYNTHETIC-COLLECT-01'
PROTOCOL = 'arrival-energy-synthetic-v1'
SCENARIOS = ('low', 'queue', 'burst')
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT')
TRACE = ROOT/'docs/results/arrival_energy_research_01/scenario_manifest.json'
HOST = ('tools/d1_arrival_energy_collection.py', 'tools/d1_arrival_energy_collection_device.py',
        'tools/d1_arrival_energy_analysis.py',
        'tools/d1_adb_observed_client.py', 'tools/d1_energy_collection_device.py',
        'tools/d1_energy_collection.py', 'tools/d1_energy_screen.py',
        'tools/d1_arrival_timing_calibration_device.py', 'tools/d1_collection_recovery.py')
BUDGET = dict(sessions=12, development=6, confirmation=6, requests=288,
              warmup=96, explicit_inference=384, runtime_creations=48,
              staging=12, staging_files=84, apk_transfers=1, installs=1,
              retry=0, replacement=0, additional=0,
              common_window_seconds=120, resident_baseline_seconds=30,
              app_cooling_seconds=60, app_drain_seconds=30,
              intersession_cooling_seconds=120,
              installation_seconds=600, stage_gate_seconds=120,
              host_poll_seconds=485, recovery_seconds=50, cleanup_seconds=45,
              session_seconds=700, freeze_seconds=300, total_seconds=10620)


def require(ok, why):
    if not ok: raise ValueError(why)


def identity():
    app={k:v for k,v in cal.code_identity().items() if not any(t in k for t in
         ('/src/test/','/src/testModelProbe/','/src/androidTest/'))}
    return app | {n: p.digest(ROOT/n) for n in HOST} | {TRACE.relative_to(ROOT).as_posix(): p.digest(TRACE)}


def apk_sources(code):
    return {k:v for k,v in cal.apk_sources(code).items() if '/src/testModelProbe/' not in k}


def layout():
    # Fixed before data inspection; each stage has both arms of each scenario.
    forward = [(s, policy) for s in SCENARIOS for policy in POLICIES]
    return [('development', *x) for x in forward] + [('confirmation', *x) for x in reversed(forward)]


def requests(scenario, sid):
    def offset(i):
        if scenario == 'low': return 1200*i
        if scenario == 'queue': return 200*i
        if scenario == 'burst': return 80*i + (i//6)*1000
        raise ValueError('scenario')
    return [dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f'{sid}/request/{i}')),
                 ordinal=i, task_id='classification' if i%4==1 else 'detection',
                 priority='urgent' if i%4==1 else 'normal', offset_ms=offset(i),
                 deadline_ms=1500 if i%4==1 else 6000) for i in range(24)]


def prepare(source, build, output):
    source, build, output = map(Path, (source, build, output))
    require(not output.exists(), 'new output path only')
    prior = p.read(source); receipt = p.read(build)
    require(apk_sources(receipt['source_code']) == apk_sources(cal.code_identity()), 'APK/source mismatch')
    require(p.digest(receipt['apk_path']) == receipt['apk_sha256'], 'APK changed')
    template = p.read(source.parent/prior['entries'][0]['manifest'])
    candidate = apk.inspect(receipt['apk_path'], prior['apk_preflight']['toolchain'])
    require(candidate['signer_sha256'] == prior['apk_preflight']['candidate']['signer_sha256'], 'project signer mismatch')
    output.mkdir(parents=True); (output/'manifests').mkdir()
    plan = dict(protocol=PROTOCOL, experiment_id=EXPERIMENT, status='PREPARED_NOT_APPROVED',
                experiment_ready=False, budget=BUDGET, source_code=identity(),
                build_receipt=str(build.resolve()), build_receipt_sha256=p.digest(build),
                source_plan=dict(path=str(source.resolve()), sha256=p.digest(source)),
                scenario_source=dict(path=str(TRACE.resolve()),sha256=p.digest(TRACE)),
                apk_path=receipt['apk_path'], apk_sha256=receipt['apk_sha256'],
                apk_preflight=dict(prior['apk_preflight'],candidate=candidate),
                device_fingerprint=prior['device_fingerprint'],
                device_hardware_serial=prior['device_hardware_serial'],
                output_root=str(output.parent/'arrival_energy_synthetic_run_v1'),
                registry=str(output.parent/'arrival_energy_synthetic_registry'/EXPERIMENT),
                battery_start_percent=20,battery_min_percent=20,
                battery_max_temperature_tenths_c=350,require_unplugged=True,
                screen_contract=prior['screen_contract'],
                source_files=prior['source_files'], references=prior['references'],
                selection='fixed CPU_URGENT vs FIXED_SPLIT; no model fit or result-driven policy selection',
                confirmation_rule='all six development sessions eligible, freeze manifest/source/analysis identity before confirmation; report descriptive contrasts only',
                eligibility=dict(requests=24,warmup=8,full_quality=True,thermal_status=0,
                                 complete_common_window=True,app_cleanup=True,host_cleanup=True),entries=[])
    require(len(plan['source_files'])==6, 'six input files; staging count')
    runner = """param(
    [ValidateSet('Check','Run')][string]$Action='Check',
    [switch]$Approved,
    [string]$Serial,
    [string]$ExpectedPlanSha256,
    [string]$Adb='C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$planFile=Join-Path $PSScriptRoot 'collection_plan.json'
Push-Location '__REPO__'
try {
    if ($Action -eq 'Check') {
        python -B -m tools.d1_arrival_energy_collection check --plan $planFile
    } else {
        if (-not $Approved -or -not $Serial -or $ExpectedPlanSha256 -notmatch '^[a-f0-9]{64}$') {
            throw 'A later explicit approval, serial and exact plan SHA-256 are required'
        }
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $planFile).Hash.ToLowerInvariant() -ne $ExpectedPlanSha256) {
            throw 'plan hash changed; stop'
        }
        python -B -m tools.d1_arrival_energy_collection run --plan $planFile --adb $Adb --serial $Serial --expected-sha $ExpectedPlanSha256 --approved
    }
    if ($LASTEXITCODE -ne 0) { throw "tool exited $LASTEXITCODE" }
} finally { Pop-Location }
""".replace('__REPO__',str(ROOT).replace('\\','/'))
    script=output/'RUN_AFTER_APPROVAL.ps1'
    script.write_text(runner,encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    for i,(phase,scenario,policy) in enumerate(layout()):
        sid = str(uuid.uuid5(uuid.NAMESPACE_URL,f'{EXPERIMENT}/{phase}/{scenario}/{policy}'))
        m = dict(protocol=PROTOCOL, experiment_id=EXPERIMENT, session_id=sid,
                 phase=phase,scenario=scenario,policy=policy,models=copy.deepcopy(template['models']),
                 images=copy.deepcopy(template['images']), cpu_threads=1,experiment_ready=False,
                 apk_sha256=plan['apk_sha256'],device_fingerprint=plan['device_fingerprint'],
                 maximum_duration_ms=480000, maximum_concurrency=2, memory_contract='android-low-memory-resident-v1',
                 thermal_gate=0, common_window_seconds=120,resident_baseline_seconds=30,cooling_seconds=60,
                 requests=requests(scenario,sid))
        for spec in m['models'].values():
            spec['identity']['session_id']=sid;spec['target']['apk_sha256']=plan['apk_sha256']
        rel=f'manifests/{sid}.json';cal.write_new(output/rel,m)
        plan['entries'].append(dict(index=i,phase=phase,scenario=scenario,policy=policy,
                                   session_id=sid,manifest=rel,manifest_sha256=p.digest(output/rel),
                                   requests=24,warmup=8,runtime_creations=4))
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file); plan=p.read(file)
    require(plan['protocol']==PROTOCOL and plan['experiment_id']==EXPERIMENT and
            plan['status']=='PREPARED_NOT_APPROVED' and not plan['experiment_ready'], 'plan identity/status')
    require(plan['budget']==BUDGET and len(plan['entries'])==12, 'budget')
    require(BUDGET['session_seconds']==sum(BUDGET[k] for k in
            ('stage_gate_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds')), 'session reservation')
    require(BUDGET['total_seconds']==BUDGET['installation_seconds']+12*BUDGET['session_seconds']+
            11*BUDGET['intersession_cooling_seconds']+BUDGET['freeze_seconds'], 'whole reservation')
    require(plan['source_code']==identity(), 'source changed; create a new plan')
    require(p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'],'run script identity')
    receipt=p.read(plan['build_receipt'])
    require(p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
            apk_sources(receipt['source_code'])==apk_sources(cal.code_identity()), 'build identity')
    require(p.digest(plan['apk_path'])==plan['apk_sha256'], 'APK changed')
    for name,sha in plan['apk_preflight']['tool_sha256'].items():
        require(p.digest(plan['apk_preflight']['toolchain'][name])==sha, 'tool identity')
    require(apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'], 'APK signer')
    for item in [plan['source_plan'],plan['scenario_source'],*plan['source_files'].values(),*plan['references'].values()]:
        require(p.digest(item['path'])==item['sha256'], 'input/reference identity')
    require(len(plan['source_files'])==6 and BUDGET['staging_files']==12*7,'staging')
    for i,(phase,scenario,policy) in enumerate(layout()):
        entry=plan['entries'][i]; m=p.read(file.parent/entry['manifest'])
        require((entry['phase'],entry['scenario'],entry['policy'],entry['index'])==(phase,scenario,policy,i), 'order')
        require(p.digest(file.parent/entry['manifest'])==entry['manifest_sha256'] and
                (m['phase'],m['scenario'],m['policy'],m['session_id'])==(phase,scenario,policy,entry['session_id']), 'manifest')
        require(m['requests']==requests(scenario,entry['session_id']) and
                (m['maximum_duration_ms'],m['common_window_seconds'],m['resident_baseline_seconds'],m['cooling_seconds'])==(480000,120,30,60), 'calls/time')
        require(m['apk_sha256']==plan['apk_sha256'] and m['device_fingerprint']==plan['device_fingerprint'] and
                m['maximum_concurrency']==2 and m['cpu_threads']==1 and not m['experiment_ready'], 'frozen execution')
        require(set(m['models'])==set(old.KEYS) and len(m['images'])==1, 'model/image set')
        for spec in m['models'].values():
            require(spec['identity']['session_id']==entry['session_id'] and spec['target']['apk_sha256']==plan['apk_sha256'], 'model binding')
    require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(), 'consumed plan/output; no resume')
    return dict(status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for name in ('source','build','output'): q.add_argument('--'+name,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for name in ('plan','adb','serial','expected-sha'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true')
    a=cli.parse_args()
    if a.action=='prepare':result=prepare(a.source,a.build,a.output)
    elif a.action=='check':result=check(a.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
