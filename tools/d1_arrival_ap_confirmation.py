"""PC-only single-session arrival/AP confirmation preparation and identity check.

Run is a separate, explicitly approved action through the existing arrival runner.
"""
from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_energy_collection as old
from tools import d1_apk_identity as apk

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'ENERGY-AP-ARRIVAL-CONFIRM-01'
FOLDER = 'energy_ap_arrival_confirm_plan_v1'
RUN_FOLDER = 'energy_ap_arrival_confirm_run_v1'
BUNDLE = ROOT/'docs/results/energy_ap_arrival_confirmation_01/input_manifest.json'
READOUT = ROOT/'docs/results/energy_ap_arrival_confirmation_01/analysis_contract.json'
FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
# Per-session reservation is stage/gate 120 + poll 485 + recovery 50 + cleanup 45.
# Installation preflight/deployment has its own existing 600-second bound.
BUDGET = dict(sessions=1,requests=24,warmup=8,eligibility_inferences=0,
              explicit_inference=32,runtime_creations=4,staging=1,staging_files=7,
              installed_host_pulls=1,apk_transfers=1,installs=1,
              retry=0,replacement=0,additional=0,common_window_seconds=120,
              resident_baseline_seconds=30,start_ap_wait_seconds=30,
              app_cooling_seconds=60,app_drain_seconds=30,
              installation_seconds=600,stage_gate_seconds=120,host_poll_seconds=485,
              recovery_seconds=50,cleanup_seconds=45,session_seconds=700,
              total_seconds=1300,adb_commands=3000,apk_push_timeout_seconds=120)


def identity():
    return old.identity() | {'tools/d1_arrival_ap_confirmation.py':p.digest(__file__)}


def expected_manifest(source, candidate_sha):
    design=p.read(BUNDLE)
    template=p.read(Path(source['source_plan']['path']).parent/
                    p.read(source['source_plan']['path'])['entries'][0]['manifest'])
    sid=str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT+'/queue/FIXED_SPLIT'))
    m=dict(protocol=old.PROTOCOL,experiment_id=EXPERIMENT,session_id=sid,
           phase='protocol_transfer_confirmation',scenario='queue',policy='FIXED_SPLIT',
           models=copy.deepcopy(template['models']),images=copy.deepcopy(template['images']),
           cpu_threads=1,experiment_ready=False,apk_sha256=candidate_sha,
           device_fingerprint=source['device_fingerprint'],maximum_duration_ms=480000,
           maximum_concurrency=2,memory_contract='android-low-memory-resident-v1',
           thermal_gate=0,common_window_seconds=120,resident_baseline_seconds=30,
           cooling_seconds=60,start_ap_gate='numeric-ap-once-v1',
           requests=copy.deepcopy(design['requests']))
    for spec in m['models'].values():
        spec['identity']['session_id']=sid
        spec['target']['apk_sha256']=candidate_sha
    return m


def budget_check(b):
    old.require(b==BUDGET and b['session_seconds']==sum(b[k] for k in
        ('stage_gate_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds')) and
        b['total_seconds']==b['installation_seconds']+b['session_seconds'] and
        b['explicit_inference']==b['warmup']+b['eligibility_inferences']+b['requests'] and
        b['staging_files']==7 and b['retry']==b['replacement']==b['additional']==0,
        'single session budget')


def script_text(plan):
    return """param(
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
  python -B -m tools.d1_arrival_ap_confirmation check --plan $planFile
 } else {
  if (-not $Approved -or -not $Serial -or $ExpectedPlanSha256 -notmatch '^[a-f0-9]{64}$') {
   throw 'Separate approval, selected transport and exact plan hash required'
  }
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $planFile).Hash.ToLowerInvariant() -ne $ExpectedPlanSha256) { throw 'plan changed' }
  python -B -m tools.d1_arrival_ap_confirmation run --plan $planFile --adb $Adb --serial $Serial --expected-sha $ExpectedPlanSha256 --approved
 }
 if ($LASTEXITCODE -ne 0) { throw "tool exited $LASTEXITCODE" }
} finally { Pop-Location }
""".replace('__REPO__',str(ROOT).replace('\\','/'))


def prepare(source_file,build_file,frozen_file,output):
    source_file,build_file,frozen_file,output=map(Path,(source_file,build_file,frozen_file,output))
    old.require(not output.exists() and output.name==FOLDER,'fresh plan folder only')
    source=p.read(source_file);build=p.read(build_file);budget_check(BUDGET)
    old.require(source['protocol']==old.PROTOCOL and len(source['source_files'])==6,
                'arrival source/staging contract')
    old.require(p.digest(frozen_file)==FROZEN_SHA,'frozen model changed')
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
                p.digest(build['apk_path'])==build['apk_sha256'],'APK/source changed')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],
                'project signer mismatch')
    output.mkdir();(output/'manifests').mkdir()
    plan=dict(protocol=old.PROTOCOL,experiment_id=EXPERIMENT,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',approval='not_approved',
        experiment_ready=False,single_arrival_confirmation=True,budget=BUDGET,
        source_code=identity(),build_receipt=str(build_file.resolve()),
        build_receipt_sha256=p.digest(build_file),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        input_bundle=dict(path=str(BUNDLE.resolve()),sha256=p.digest(BUNDLE)),
        analysis_contract=dict(path=str(READOUT.resolve()),sha256=p.digest(READOUT)),
        frozen_model=dict(path=str(frozen_file.resolve()),sha256=FROZEN_SHA),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        device_fingerprint=source['device_fingerprint'],
        device_hardware_serial=source['device_hardware_serial'],
        output_root=str(output.parent/RUN_FOLDER),
        registry=str(output.parent/'arrival_energy_confirm_registry'/EXPERIMENT),
        battery_start_percent=source['battery_start_percent'],
        battery_min_percent=source['battery_min_percent'],
        battery_max_temperature_tenths_c=source['battery_max_temperature_tenths_c'],
        require_unplugged=source['require_unplugged'],screen_contract=source['screen_contract'],
        source_files=source['source_files'],references=source['references'],
        selection='one prespecified queue24 FIXED_SPLIT; no post-result selection',
        analysis_scope='protocol transfer; conditional A if mapped, end-to-end B separately; pair coefficients untested',
        entries=[])
    m=expected_manifest(plan,build['apk_sha256'])
    rel=f"manifests/{m['session_id']}.json";cal.write_new(output/rel,m)
    plan['entries']=[dict(index=0,phase=m['phase'],scenario='queue',policy='FIXED_SPLIT',
        session_id=m['session_id'],manifest=rel,manifest_sha256=p.digest(output/rel),
        requests=24,warmup=8,runtime_creations=4)]
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(plan),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file);budget_check(plan['budget'])
    old.require(file.name=='collection_plan.json' and file.parent.name==FOLDER and
                plan['protocol']==old.PROTOCOL and plan['experiment_id']==EXPERIMENT and
                plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
                plan['approval']=='not_approved' and not plan['experiment_ready'] and
                plan['single_arrival_confirmation'] and len(plan['entries'])==1,
                'plan identity')
    old.require(Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
                Path(plan['registry'])==file.parent.parent/'arrival_energy_confirm_registry'/EXPERIMENT,
                'dedicated output/consumption registry')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
                'consumed or output exists; no resume')
    old.require(plan['source_code']==identity() and
                p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'] and
                p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
                p.digest(plan['source_plan']['path'])==plan['source_plan']['sha256'] and
                p.digest(plan['input_bundle']['path'])==plan['input_bundle']['sha256'] and
                p.digest(plan['analysis_contract']['path'])==plan['analysis_contract']['sha256'] and
                p.digest(plan['frozen_model']['path'])==FROZEN_SHA,
                'frozen input/source identity')
    build=p.read(plan['build_receipt'])
    for name,sha in plan['apk_preflight']['tool_sha256'].items():
        old.require(p.digest(plan['apk_preflight']['toolchain'][name])==sha,'APK inspection tool changed')
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
                p.digest(plan['apk_path'])==plan['apk_sha256'] and
                apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'],
                'APK build/signer identity')
    source=p.read(plan['source_plan']['path'])
    old.require(plan['apk_preflight']['candidate']['signer_sha256']==
                source['apk_preflight']['candidate']['signer_sha256'] and
                len(plan['source_files'])==6 and len(plan['references'])==4,
                'signer/source set')
    for item in [*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'staging/reference changed')
    entry=plan['entries'][0];m=p.read(file.parent/entry['manifest'])
    old.require(entry['index']==0 and entry['phase']=='protocol_transfer_confirmation' and
                entry['scenario']=='queue' and entry['policy']=='FIXED_SPLIT' and
                p.digest(file.parent/entry['manifest'])==entry['manifest_sha256'] and
                m==expected_manifest(plan,plan['apk_sha256']), 'fixed request/AP gate manifest')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for x in ('source-plan','build-receipt','frozen','output'):q.add_argument('--'+x,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for x in ('plan','adb','serial','expected-sha'):q.add_argument('--'+x,required=True)
    q.add_argument('--approved',action='store_true')
    a=cli.parse_args()
    if a.action=='prepare':r=prepare(a.source_plan,a.build_receipt,a.frozen,a.output)
    elif a.action=='check':r=check(a.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
