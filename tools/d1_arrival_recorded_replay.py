"""PC-only preparation/Check for one recorded B2 dispatch-gate device replay.

Run is available only with a separate later approval and the exact plan hash.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import uuid
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_apk_identity as apk
from tools import d1_arrival_policy_screen as screen

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'ENERGY-AP-RECORDED-B2-DIAG-04'
FOLDER = 'energy_ap_recorded_b2_diag_plan_v6'
RUN_FOLDER = 'energy_ap_recorded_b2_diag_run_v6'
BUNDLE = ROOT/'docs/results/energy_ap_recorded_b2_01/source_schedule.json'
CONTRACT = ROOT/'docs/results/energy_ap_recorded_b2_01/diagnostic_analysis_contract_v2.json'
TIMELINE = ROOT/'docs/results/arrival_visualization_01/timeline.csv'
OCCUPANCY = ROOT/'docs/results/arrival_policy_screen_01/repro_bundle/occupancy_segments.csv'
FROZEN_SHA = prior.FROZEN_SHA
POLICY = 'RECORDED_B2_REPLAY_V1'
MEASUREMENT_CHANGE = ('numeric-ap-observe-v2 separates fresh HAL AP/execution admission from '
                      'frozen-model development support; same recorded workload and environmental gates; '
                      'new signed APK and protocol, not a completed same-protocol comparison')

CONFIRM_EXPERIMENT = 'ENERGY-AP-RECORDED-B2-INRANGE-01'
CONFIRM_FOLDER = 'energy_ap_recorded_b2_inrange_plan_v1'
CONFIRM_RUN_FOLDER = 'energy_ap_recorded_b2_inrange_run_v1'
CONFIRM_CONTRACT = ROOT/'docs/results/energy_ap_recorded_b2_01/analysis_contract.json'
CONFIRM_CHANGE = ('same signed observe-v2-capable APK and saved B2 input; select its existing '
                  'numeric-ap-once-v1 start admission at 32.5..34 C for a new held-out session; '
                  'no heating, refit, online-policy claim or automatic strict promotion')


def configuration(experiment=EXPERIMENT):
    if experiment == EXPERIMENT:
        return FOLDER, RUN_FOLDER, CONTRACT, MEASUREMENT_CHANGE, 'numeric-ap-observe-v2'
    old.require(experiment == CONFIRM_EXPERIMENT, 'unknown replay experiment')
    return (CONFIRM_FOLDER, CONFIRM_RUN_FOLDER, CONFIRM_CONTRACT,
            CONFIRM_CHANGE, 'numeric-ap-once-v1')

# Same one-session runner bounds, derived from its four stages and 24+8 calls.
REQUESTS, WARMUP, RUNTIMES, STAGED = 24, 8, 4, 7
STAGE_GATE, POLL, RECOVERY, CLEANUP, INSTALLATION = 120, 485, 50, 45, 600
SESSION = STAGE_GATE+POLL+RECOVERY+CLEANUP
# 485/.25 listing + 3*ceil(485/2) thermal + ceil(485/10) screen,
# plus bounded preflight, gates, staging, recovery and cleanup reserve.
ADB_CAP = 3200
BUDGET = dict(sessions=1,requests=REQUESTS,warmup=WARMUP,eligibility_inferences=0,
              explicit_inference=REQUESTS+WARMUP,runtime_creations=RUNTIMES,
              staging=1,staging_files=STAGED,installed_host_pulls=1,
              apk_transfers=1,installs=1,retry=0,replacement=0,additional=0,
              common_window_seconds=120,resident_baseline_seconds=30,start_ap_wait_seconds=30,
              app_cooling_seconds=60,app_drain_seconds=30,
              installation_seconds=INSTALLATION,stage_gate_seconds=STAGE_GATE,
              host_poll_seconds=POLL,recovery_seconds=RECOVERY,cleanup_seconds=CLEANUP,
              session_seconds=SESSION,total_seconds=INSTALLATION+SESSION,
              adb_commands=ADB_CAP,apk_push_timeout_seconds=120)


def source_check():
    b=p.read(BUNDLE)
    old.require(b['version']=='recorded-b2-dispatch-gate-v1' and
                (b['source_mode'],b['scenario'],b['policy'],b['seed'])==
                ('explore','queue','B2_PC',201) and
                (b['predicted_interference'],b['realized_interference'])==(1.5,1.5) and
                b['source_timeline_sha256']==p.digest(TIMELINE) and
                b['source_occupancy_sha256']==p.digest(OCCUPANCY), 'source identity')
    with TIMELINE.open(encoding='utf-8-sig',newline='') as f:
        rows=[r for r in csv.DictReader(f) if (r['mode'],r['scenario'],r['policy'],r['seed'])==
              ('explore','queue','B2_PC','201')]
    old.require(len(rows)==REQUESTS==len(b['requests']),'source request count')
    old.require(len({q['request_id'] for q in b['requests']})==REQUESTS and
                all(str(uuid.UUID(q['request_id']))==q['request_id'] for q in b['requests']),
                'device request identity')
    for i,(row,entry) in enumerate(zip(rows,b['requests'])):
        old.require(entry['ordinal']==i and entry['source_request_id']==row['id'] and
                    entry['offset_ms']*1_000_000==int(row['arrival_ns']) and
                    entry['release_offset_ns']==int(row['dispatch_ns']) and
                    entry['recorded_backend']==row['backend'] and
                    entry['task_id']==row['task'] and entry['priority']==row['priority'] and
                    entry['deadline_ms']*1_000_000==int(row['deadline_offset_ns']) and
                    entry['release_offset_ns']>=int(row['arrival_ns']) and
                    entry['release_offset_ns']<120_000_000_000 and
                    all(entry[field]==int(row[source_field]) for field,source_field in (
                        ('pc_execution_start_ns','execution_start_ns'),
                        ('pc_output_ready_ns','output_ready_ns'),
                        ('pc_persist_complete_ns','persist_complete_ns'),
                        ('pc_worker_release_ns','worker_release_ns'),
                        ('pc_lane_available_ns','lane_available_ns'))) and
                    entry['recorded_backend']==('GPU' if row['task']=='classification' else 'CPU'),
                    'source request/release mismatch')
    with OCCUPANCY.open(encoding='utf-8',newline='') as f:
        stored=[q for q in csv.DictReader(f) if (q['scenario'],q['realized'],q['seed'],q['policy'])==
                ('queue','1.5','201','B2_PC')]
    ledger=[]
    for r in rows:
        q=dict(r)
        for field in ('arrival_ns','dispatch_ns','execution_start_ns','output_ready_ns',
                      'persist_complete_ns','worker_release_ns','lane_available_ns'):
            q[field]=int(q[field])
        ledger.append(q)
    reconstructed=screen.occupancy({'ledger':ledger},'queue',1.5,201,'B2_PC')
    old.require(len(reconstructed)==len(stored) and all(
        a['state']==q['state'] and abs(a['start_s']-float(q['start_s']))<1e-9 and
        abs(a['end_s']-float(q['end_s']))<1e-9 for a,q in zip(reconstructed,stored)),
        'stored occupancy/source ledger mismatch')
    durations=defaultdict(float)
    for q in reconstructed:durations[q['state']]+=q['end_s']-q['start_s']
    old.require(set(durations)=={'idle','detection:CPU','classification:GPU',
                'classification:GPU+detection:CPU'} and all(
                abs(durations[k]-v)<1e-6 for k,v in b['occupancy_seconds'].items()),
                'source occupancy durations')
    return b


def identity(experiment=EXPERIMENT):
    contract=configuration(experiment)[2]
    return old.identity() | {
        'tools/d1_arrival_recorded_replay.py':p.digest(__file__),
        'tools/d1_arrival_recorded_replay_analysis.py':p.digest(ROOT/'tools/d1_arrival_recorded_replay_analysis.py'),
        'docs/results/energy_ap_recorded_b2_01/source_schedule.json':p.digest(BUNDLE),
        contract.relative_to(ROOT).as_posix():p.digest(contract)}


def expected_manifest(source, candidate_sha):
    experiment=source.get('experiment_id',EXPERIMENT)
    mode=configuration(experiment)[4]
    b=source_check()
    previous=p.read(source['source_plan']['path'])
    template=p.read(Path(source['source_plan']['path']).parent/previous['entries'][0]['manifest'])
    sid=str(uuid.uuid5(uuid.NAMESPACE_URL, experiment+'/queue/B2_PC'))
    requests=[{k:v for k,v in q.items() if k not in ('pc_execution_start_ns','pc_output_ready_ns',
        'pc_persist_complete_ns','pc_worker_release_ns','pc_lane_available_ns')}
        for q in b['requests']]
    m=dict(protocol=old.PROTOCOL,experiment_id=experiment,session_id=sid,
           phase='recorded_dispatch_transition_confirmation',scenario='queue',policy=POLICY,
           replay_version=b['version'],replay_source_sha256=p.digest(BUNDLE),
           source_policy='B2_PC',source_mode='explore',source_seed=201,
           source_predicted_interference=1.5,source_realized_interference=1.5,
           models=copy.deepcopy(template['models']),images=copy.deepcopy(template['images']),
           cpu_threads=1,experiment_ready=False,apk_sha256=candidate_sha,
           device_fingerprint=source['device_fingerprint'],maximum_duration_ms=480000,
           maximum_concurrency=2,memory_contract='android-low-memory-resident-v1',
           thermal_gate=0,common_window_seconds=120,resident_baseline_seconds=30,
           cooling_seconds=60,start_ap_gate=mode,requests=requests)
    for spec in m['models'].values():
        spec['identity']['session_id']=sid
        spec['target']['apk_sha256']=candidate_sha
    return m


def script_text():
    # Reuse the exact PowerShell -> Python run boundary; this new module has its own Check.
    return prior.script_text({}).replace('d1_arrival_ap_confirmation','d1_arrival_recorded_replay')


def prepare(source_file,build_file,frozen_file,output):
    source_file,build_file,frozen_file,output=map(Path,(source_file,build_file,frozen_file,output))
    experiment=CONFIRM_EXPERIMENT if output.name==CONFIRM_FOLDER else EXPERIMENT
    folder,run_folder,contract,change,mode=configuration(experiment)
    old.require(not output.exists() and output.name==folder,'fresh replay plan folder only')
    source=p.read(source_file);build=p.read(build_file);source_check()
    old.require(p.digest(frozen_file)==FROZEN_SHA,'frozen model changed')
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
                p.digest(build['apk_path'])==build['apk_sha256'],'APK/source changed')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],
                'project signer mismatch')
    old.require(len(source['source_files'])==6 and len(source['references'])==4,
                'four runtimes, six staging sources')
    output.mkdir();(output/'manifests').mkdir()
    plan=dict(protocol=old.PROTOCOL,experiment_id=experiment,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',approval='not_approved',
        experiment_ready=False,recorded_replay_confirmation=True,budget=BUDGET,
        source_code=identity(experiment),build_receipt=str(build_file.resolve()),
        build_receipt_sha256=p.digest(build_file),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        input_bundle=dict(path=str(BUNDLE.resolve()),sha256=p.digest(BUNDLE)),
        analysis_contract=dict(path=str(contract.resolve()),sha256=p.digest(contract)),
        frozen_model=dict(path=str(frozen_file.resolve()),sha256=FROZEN_SHA),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        device_fingerprint=source['device_fingerprint'],
        device_hardware_serial=source['device_hardware_serial'],
        output_root=str(output.parent/run_folder),
        registry=str(output.parent/'arrival_recorded_b2_registry'/experiment),
        battery_start_percent=source['battery_start_percent'],
        battery_min_percent=source['battery_min_percent'],
        battery_max_temperature_tenths_c=source['battery_max_temperature_tenths_c'],
        require_unplugged=source['require_unplugged'],screen_contract=source['screen_contract'],
        source_files=source['source_files'],references=source['references'],
        selection='prespecified saved queue/seed201/B2_PC/realized1.5; one recorded dispatch gate',
        measurement_protocol_change=change,
        analysis_scope='observed schedule/current/AP; out-of-range model arithmetic only as extrapolation diagnostic; not online B2 or strict arrival support',
        entries=[])
    m=expected_manifest(plan,build['apk_sha256'])
    rel=f"manifests/{m['session_id']}.json";cal.write_new(output/rel,m)
    plan['entries']=[dict(index=0,phase=m['phase'],scenario='queue',policy=POLICY,
        session_id=m['session_id'],manifest=rel,manifest_sha256=p.digest(output/rel),
        requests=REQUESTS,warmup=WARMUP,runtime_creations=RUNTIMES)]
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file);source_check()
    experiment=plan['experiment_id']
    folder,run_folder,contract,change,mode=configuration(experiment)
    old.require(file.name=='collection_plan.json' and file.parent.name==folder and
                plan['protocol']==old.PROTOCOL and
                plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
                plan['approval']=='not_approved' and not plan['experiment_ready'] and
                plan['recorded_replay_confirmation'] and len(plan['entries'])==1 and
                plan['measurement_protocol_change']==change and
                plan['budget']==BUDGET,'plan identity/budget')
    old.require(Path(plan['output_root'])==file.parent.parent/run_folder and
                Path(plan['registry'])==file.parent.parent/'arrival_recorded_b2_registry'/experiment and
                not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
                'fresh output/consumption registry')
    old.require(plan['source_code']==identity(experiment) and
                p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'] and
                p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
                p.digest(plan['source_plan']['path'])==plan['source_plan']['sha256'] and
                p.digest(plan['input_bundle']['path'])==plan['input_bundle']['sha256'] and
                Path(plan['analysis_contract']['path'])==contract.resolve() and
                p.digest(plan['analysis_contract']['path'])==plan['analysis_contract']['sha256'] and
                p.digest(plan['frozen_model']['path'])==FROZEN_SHA,'source/frozen identity')
    build=p.read(plan['build_receipt'])
    for name,sha in plan['apk_preflight']['tool_sha256'].items():
        old.require(p.digest(plan['apk_preflight']['toolchain'][name])==sha,'inspection tool changed')
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
                p.digest(plan['apk_path'])==plan['apk_sha256'] and
                apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'],
                'APK/source/signer identity')
    source=p.read(plan['source_plan']['path'])
    old.require(source['apk_preflight']['candidate']['signer_sha256']==
                plan['apk_preflight']['candidate']['signer_sha256'],'project signer')
    for item in [*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'staging/reference changed')
    entry=plan['entries'][0];m=p.read(file.parent/entry['manifest'])
    old.require(entry['index']==0 and entry['policy']==POLICY and
                p.digest(file.parent/entry['manifest'])==entry['manifest_sha256'] and
                m==expected_manifest(plan,plan['apk_sha256']),'recorded manifest changed')
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
