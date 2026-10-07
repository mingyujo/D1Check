"""Pre-register, run, and audit the bounded source-pinned PC comparison."""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import numpy as np
from tools import d1_external_rules as rules

p, old = rules.p, rules.old
ROOT = p.ROOT
BUNDLE = ROOT / 'docs/results/external_rules_01'
LOCAL = ROOT / 'output/external_rules_20261007_v1'
SEEDS = list(range(610810001, 610810005))


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    temp.replace(path)


def csv_write(path, rows):
    names = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', encoding='utf8', newline='') as f:
        out = csv.DictWriter(f, names)
        out.writeheader()
        out.writerows(rows)


def environments():
    definitions = [('quiet_healthy', []), ('intermittent_activity', [36., 50.]),
                   ('continuous_activity', list(map(float, range(30, 111, 10)))),
                   ('battery_recovers', []), ('battery_low_persistent', []),
                   ('battery_heat_recovers', []), ('os_thermal_recovers', [])]
    result = []
    for name, activity in definitions:
        snapshots = []
        for at in (0., 60., 120.):
            s = dict(observed_s=at, battery_status='available', battery_percent=80,
                     battery_c=30., battery_health='good', thermal_status='available',
                     thermal_state='nominal')
            if name == 'battery_low_persistent' or name == 'battery_recovers' and at < 60:
                s['battery_percent'] = 19
            elif name == 'battery_recovers':
                s['battery_percent'] = 20
            if name == 'battery_heat_recovers':
                s['battery_c'] = 43. if at < 60 else 42.
            if name == 'os_thermal_recovers':
                s['thermal_state'] = 'serious' if at < 60 else 'moderate'
            snapshots.append(s)
        result.append(dict(id=name, synthetic=True, activity_s=activity, snapshots=snapshots))
    return result


def existing_sources():
    modules = [p, p.model, p.memory, old, old.engine, old.batch,
               rules.joint, rules.joint.parent, rules.joint.x]
    from tools import d1_queue_ppo as shared
    modules += [shared, shared.prev]
    files = {Path(m.__file__) for m in modules}
    files |= {p.BUNDLE / 'model.json', p.BUNDLE / 'initial_inputs.json'}
    return {path.relative_to(ROOT).as_posix(): p.digest(path) for path in sorted(files)}


def source_inventory():
    versions = {x: read(LOCAL / (x + '_version.json')) for x in ('ente', 'band', 'litert')}
    needed = dict(ente=['mobile/apps/photos/lib/services/machine_learning/compute_controller.dart',
                       'mobile/apps/photos/lib/services/machine_learning/device_health_policy.dart',
                       'mobile/apps/photos/plugins/ente_photos_platform/lib/src/device_health.dart',
                       'mobile/apps/photos/lib/services/machine_learning/ml_service.dart',
                       'mobile/apps/photos/lib/services/machine_learning/ml_indexing_isolate.dart',
                       'mobile/apps/photos/lib/utils/isolate/super_isolate.dart',
                       'mobile/apps/photos/lib/settings/local_settings.dart'],
                  band=['band/scheduler/heterogeneous_earliest_finish_time_scheduler.cc',
                        'band/scheduler/least_slack_first_scheduler.cc', 'band/planner.cc',
                        'band/engine.cc', 'band/latency_estimator.cc', 'band/config.h',
                        'band/config_builder.cc'],
                  litert=['litert/runtime/compiled_model.cc'])
    files = []
    for system, names in needed.items():
        v = versions[system]
        repo = 'ente/ente' if system == 'ente' else v['repo']
        for name in names:
            path = LOCAL / 'sources' / system / name
            lines = path.read_text(encoding='utf8').splitlines()
            symbols = ['shouldRunCompute', 'requestCompute', 'onUserInteraction',
                       'minimumBatteryLevel', 'maximumAndroidBatteryTemperature', 'isFreshAt',
                       'Schedule(', 'GetSlackTime', 'IsSLOViolated', 'UpdateLatency',
                       'GetShortestSubgraphKey', 'smoothing_factor', 'GetDefaultConfig',
                       'ValidateSchedulingInfo', 'ApplySchedulingInfoOverrides']
            locations = {s: [i + 1 for i, line in enumerate(lines) if s in line] for s in symbols}
            files.append(dict(system=system, commit=v['sha'], path=name, sha256=p.digest(path),
                              url=f'https://github.com/{repo}/blob/{v["sha"]}/{name}',
                              locations={k: x for k, x in locations.items() if x}))
    return dict(checked_utc=utc(), versions=versions, files=files,
                active_rules=[dict(system='Ente Android start gate', level='predicate A / task schedule B',
                    observations=['past activity', 'fresh battery and OS thermal snapshot', 'override', 'compute blocks'],
                    decision='compute request, signal change, activity timer expiry, periodic health refresh',
                    thresholds={'min_battery_percent':20, 'max_battery_c':42, 'max_observation_age_s':120,
                                'Android_interaction_s':15, 'iOS_interaction_s_not_used':5,
                                'health_refresh_s':60, 'health_request_timeout_s':5},
                    comparison='BG normal request start only; common EFT allocation',
                    actions=['allow next BG start', 'retain pending BG work and wait'],
                    queue='source image ordering not imported; same fixed lower EFT on both sides',
                    deadlines='no original request deadline guarantee or explicit expiry',
                    preemption='cooperative pause before next image analysis; no mid-request preemption mapped',
                    costs='gate does not predict request latency/energy', resources='foreground mobile ML image indexing'),
                    dict(system='Band default HEFT reserve=false', level='B',
                    observations=['FIFO arrived JobQueue', 'model/progress', 'expected subgraph latency', 'worker wait/idle'],
                    decision='planner wake and worker availability/request updates',
                    thresholds={'window':'INT_MAX default / configurable >0', 'reserve':False,
                                'EMA_alpha':.1, 'EMA_range':[0,1]},
                    actions=['largest shortest-latency job to best idle worker', 'yield busy-best job and scan others'],
                    queue='first FIFO model/progress representative; first job tie; last enumerated worker tie',
                    deadlines='SLO optional; our HEFT comparison leaves upstream SLO unset and evaluates D1Check deadlines externally',
                    preemption='no scheduler-level interruption in this HEFT source',
                    costs='profiled Invoke latency, then EMA; adapted to observed full lane duration',
                    resources='original CPU/GPU/DSP/NPU subgraphs; this adapter CPU/GPU whole requests')],
                excluded=[dict(system='Band least slack first', reason='predicted SLO violation early-drop changes full-work requirement',
                    source='band/scheduler/least_slack_first_scheduler.cc and band/planner.cc', level='C',
                    ordering='deadline-now-shortest_expected_plan; slack std::sort tie not specified'),
                    dict(system='MediaPipe Tasks LIVE_STREAM', level='C',
                    url='https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/python',
                    version='official documentation inspected 2026-10-07; documentation not immutable release',
                    reason='actual busy-frame ignore is stream freshness control, incompatible with full normal work'),
                    dict(system='LiteRT SchedulingInfo', level='C', commit=versions['litert']['sha'],
                    reason='metadata validation/propagation is present; independent CPU/GPU request rule not established'),
                    dict(system='Android NPU Manager', level='C',
                    url='https://source.android.google.cn/docs/core/perf/npu-manager?hl=en',
                    version='Android17+ official documentation inspected 2026-10-07; concrete implementation commit not verified',
                    reason='load/unload, priority and vendor preemption exist; our model has no NPU load/memory/preempt costs or inputs',
                    access='some web opens failed; indexed official document available; no access bypass')],
                paper='Band MobiSys2022 DOI10.1145/3498361.3538948; current code pinned separately; paper PDF not used as detailed rule authority')


def prepare():
    if (BUNDLE / 'contract.json').exists():
        return read(BUNDLE / 'contract.json')
    BUNDLE.mkdir(parents=True, exist_ok=True)
    frozen, case = p.inputs(p.BUNDLE)
    initial = {k: case['initial'][k] for k in ('preload', 'preload_power_w')}
    inputs = dict(initial=initial, environments=environments(),
                  workloads=[dict(seed=s, family=f, tickets=old.workload(f, s)) for s in SEEDS for f in old.FAMILIES])
    write(BUNDLE / 'inputs.json', inputs)
    write(BUNDLE / 'sources.json', source_inventory())
    original = existing_sources()
    write(LOCAL / 'preserved_sources.json', original)
    # User artifacts and other worktree are kept outside Git/export metadata.
    users = [path for path in ROOT.iterdir() if path.is_file() and path.suffix.lower() in ('.html', '.pdf')]
    users += [path for path in (ROOT / '.vscode').rglob('*') if path.is_file()]
    for folder in ROOT.glob('*_files'):
        users += [path for path in folder.rglob('*') if path.is_file()]
    write(LOCAL / 'preserved_user_files.json', {x.relative_to(ROOT).as_posix():p.digest(x) for x in users})
    contract = dict(version='external-rules-comparison-v1', frozen_utc=utc(),
                    base_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                    dirty=True, mapping_sha256=p.digest(BUNDLE / 'mapping.md'),
                    inputs_sha256=p.digest(BUNDLE / 'inputs.json'), sources_sha256=p.digest(BUNDLE / 'sources.json'),
                    physical_model_sha256=p.MODEL_SHA, initial_source_sha256=p.INITIAL_SHA,
                    resource_policies=list(rules.RESOURCE_POLICIES), gate_policies=[rules.ALWAYS, rules.ENTE],
                    seeds=SEEDS, families=list(old.FAMILIES), contexts=list(old.SCENARIOS),
                    resource_cases=48, resource_rows=384, gate_environment_profiles=7, gate_rows=672,
                    logical_rows=1056, actual_formal_runs=1056, tuning_candidates=0,
                    maximum_batch_wall_s=2400, maximum_batch_environment_runs=1056,
                    completion_boundary='response urgent output_ready / normal persist_complete; lane release after all5 phases',
                    energy_window_s=[0,120], ap_window_s=[35,180], ap_safety_limit_c=None,
                    incomplete='common120 J partial work; AP180 null; AP35..120 explicitly partial',
                    first_pilot='first ordered resource case and first quiet gate pair; published and counted once',
                    representative_resource={'seed':SEEDS[0],'family':'queue','context':'mean'},
                    representative_gate={'seed':SEEDS[0],'family':'low','context':'mean','environment':'intermittent_activity'},
                    common_realization_seed=201, environment_is_synthetic=True,
                    host_overhead='measure callback host time where timer exists; model differential overhead0 assumption, device overhead unknown',
                    old_sources=original, device_commands=0, experiment_ready=False,
                    independent_device_holdout=False)
    write(BUNDLE / 'contract.json', contract)
    return contract


def check_frozen():
    spec = read(BUNDLE / 'contract.json')
    for name, key in [('mapping.md','mapping_sha256'), ('inputs.json','inputs_sha256'), ('sources.json','sources_sha256')]:
        if p.digest(BUNDLE / name) != spec[key]:
            raise ValueError('registered file changed: ' + name)
    for name, sha in spec['old_sources'].items():
        if p.digest(ROOT / name) != sha:
            raise ValueError('old engine/model/policy changed: ' + name)
    return spec


def metrics(result, controller, initial, frozen):
    ss, costs, end = p.account(result, initial, frozen)
    rows = result['ledger']
    complete = sum(r['status']=='succeeded' for r in rows)
    by = {pr:[r for r in rows if r['priority']==pr] for pr in ('urgent','normal')}
    failed = {pr:sum(r['status']!='succeeded' or 'response_ns' not in r or r['response_ns']>r['deadline_offset_ns'] for r in rs)
              for pr,rs in by.items()}
    init = p.memory.initialize(initial['preload'], frozen['ap']['beta'], 30.)
    ap = costs['ap_path']
    rise = [max(0.,t-init['reference_c']) for t in ap]
    timers = getattr(controller,'callback_times',None)
    ds = result['decisions']
    normal_response = [r['response_ns']/1e6 for r in by['normal'] if 'response_ns' in r]
    row = dict(planned=len(rows), completed=complete, incomplete=len(rows)-complete,
               urgent_n=len(by['urgent']), normal_n=len(by['normal']),
               urgent_service_failure=failed['urgent'], normal_service_failure=failed['normal'],
               deadline_met=len(rows)-sum(failed.values()),
               urgent_p95_ms=result['metrics']['urgent_p95_ms'], normal_mean_ms=result['metrics']['normal_mean_ms'],
               normal_p95_ms=sorted(normal_response)[math.ceil(.95*len(normal_response))-1] if normal_response else None,
               energy_j=costs['whole_120s_j'], energy_full_work_eligible=complete==len(rows),
               peak_ap_c=max(ap) if end==180 else None, partial_peak_ap_35_120_c=max(ap[:86]),
               thermal_degree_seconds=float(np.trapezoid(rise,dx=1.)) if end==180 else None,
               ap_safety_limit_c=None, ap_safety_limit_exceed_s=None,
               last_lane_s=max(r['lane_available_ns']/1e9 for r in rows) if complete==len(rows) else None,
               overlap_s=sum(s['end_s']-s['start_s'] for s in ss if '+' in s['state']),
               cpu_occupied_s=sum(r.get('lane_available_ns',120e9)/1e9-r['dispatch_ns']/1e9 for r in rows if r.get('backend')=='CPU'),
               gpu_occupied_s=sum(r.get('lane_available_ns',120e9)/1e9-r['dispatch_ns']/1e9 for r in rows if r.get('backend')=='GPU'),
               classification_gpu=sum(r['task']=='classification' and r.get('backend')=='GPU' for r in rows),
               mean_completed_queue_wait_ms=statistics.mean((r['dispatch_ns']-r['arrival_ns'])/1e6 for r in rows if 'dispatch_ns' in r) if any('dispatch_ns' in r for r in rows) else None,
               unfinished_wait_to_horizon_s=sum((120e9-r['arrival_ns'])/1e9 for r in rows if 'dispatch_ns' not in r),
               decision_calls=len(ds), gate_blocked_calls=sum(bool(d.get('withheld_ids')) for d in ds),
               band_yield_calls=sum(bool(d.get('yielded_ids')) for d in ds),
               ema_updates=len(getattr(controller,'ema_records',[])),
               decision_host_total_s=sum(timers) if timers is not None else None,
               decision_host_max_ms=1000*max(timers,default=0.) if timers is not None else None)
    return row, dict(segments=ss, ap_times_s=list(range(35,end+1)), ap_path=ap,
                     reference_ap_c=init['reference_c'], ap_end_s=end)


def audit(result, tickets):
    rows = result['ledger']
    assert len(rows)==len(tickets)
    for a,b in zip(rows,tickets):
        assert all(a[k]==v for k,v in b.items()), 'request semantics changed'
        if a['status']=='succeeded':
            fields=['dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns']
            assert all(a[x]<=a[y] for x,y in zip(fields,fields[1:])), 'phase inversion'
            boundary='output_ready_ns' if a['priority']=='urgent' else 'persist_complete_ns'
            # Engine separately rounds absolute phase time and relative response.
            # Their integer representations can differ by 1 ns; service/deadline
            # uses the untouched engine response, never this audit tolerance.
            assert abs(a['response_ns']-(a[boundary]-a['arrival_ns']))<=1, 'response boundary representation'
    for b in ('CPU','GPU'):
        jobs=sorted([r for r in rows if r.get('backend')==b],key=lambda r:r['dispatch_ns'])
        assert all(a.get('lane_available_ns',120e9)<=z['dispatch_ns'] for a,z in zip(jobs,jobs[1:])), 'duplicate lane'
    for d in result['decisions']:
        if d.get('selected'):
            q=next(q for q in tickets if q['id']==d['selected']['request_id'])
            assert q['arrival_ns']<=d['now_ns'], 'future request'
    for ss in p.segments([dict(state=r['task']+'_'+r['backend'],start=r['dispatch_ns']/1e9,
                              end=r.get('lane_available_ns',120e9)/1e9) for r in rows if 'dispatch_ns' in r],0.,120.):
        assert ss['state']=='idle' or ss['state'] in p.model.STATES


def run(folder, pilot=False):
    spec=check_frozen();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    inputs=read(BUNDLE/'inputs.json');frozen,_=p.inputs(p.BUNDLE)
    sources={name:p.digest(ROOT/name) for name in ('tools/d1_external_rules.py','tools/d1_external_rules_study.py')}
    registration=folder/'registered_before_run.json'
    if registration.exists():
        previous=read(registration)
        if previous['code_sha256']!=sources or previous['contract_sha256']!=p.digest(BUNDLE/'contract.json'):
            repair=folder/'resume_segment_registration.json'
            if not repair.exists():repair=folder/'audit_recovery_registration.json'
            note=read(repair) if repair.exists() else {}
            if (note.get('old_code_sha256')!=previous['code_sha256'] or note.get('new_code_sha256')!=sources
                or note.get('contract_sha256')!=previous['contract_sha256']
                or previous['contract_sha256']!=p.digest(BUNDLE/'contract.json')
                or previous['code_sha256']['tools/d1_external_rules.py']!=sources['tools/d1_external_rules.py']):
                raise ValueError('resume source/contract drift')
    else:
        write(registration,dict(utc=utc(),head=spec['base_head'],dirty=True,code_sha256=sources,
                                contract_sha256=p.digest(BUNDLE/'contract.json')))
    jobs=[]
    for work in inputs['workloads']:
        for context in spec['contexts']:
            for policy in spec['resource_policies']:
                jobs.append((work,context,policy,'resource',None))
            for env in inputs['environments']:
                for policy in spec['gate_policies']:
                    jobs.append((work,context,policy,'gate',env))
    assert len(jobs)==spec['logical_rows']
    folder.joinpath('items').mkdir(exist_ok=True)
    segment=read(folder/'resume_segment_registration.json') if (folder/'resume_segment_registration.json').exists() else None
    if segment:
        if segment['new_code_sha256']!=sources or segment['contract_sha256']!=p.digest(BUNDLE/'contract.json'):
            raise ValueError('resume segment source drift')
        for name,sha in segment['saved_results_sha256'].items():
            if p.digest(folder/'items'/name)!=sha:raise ValueError('saved result drift')
    user_file=folder/'preserved_user_files.json'
    if not user_file.exists():
        prior_users=LOCAL/'preserved_user_files.json'
        if prior_users.exists():write(user_file,read(prior_users))
        else:
            paths=[x for x in ROOT.iterdir() if x.is_file() and x.suffix.lower() in ('.html','.pdf')]
            paths += [x for x in (ROOT/'.vscode').rglob('*') if x.is_file()]
            for directory in ROOT.glob('*_files'):paths += [x for x in directory.rglob('*') if x.is_file()]
            write(user_file,{x.relative_to(ROOT).as_posix():p.digest(x) for x in paths})
    prior_elapsed=read(folder/'progress.json').get('elapsed_s',0.) if (folder/'progress.json').exists() else 0.
    began=time.monotonic();rows=[];actual=0
    lock=folder/'owner.json'
    import os
    with lock.open('x',encoding='utf8') as stream:
        json.dump({'pid':os.getpid(),'utc':utc()},stream)
    try:
        for index,(work,context,policy,scope,env) in enumerate(jobs):
            if pilot and index>=10:
                break
            path=folder/'items'/f'{index:04d}.json.gz'
            if path.exists():
                with gzip.open(path,'rt',encoding='utf8') as f:item=json.load(f)
                identity=dict(scope=scope,seed=work['seed'],family=work['family'],context=context,
                              policy=policy,environment=env['id'] if env else 'immediate_allow')
                if any(item['row'][k]!=v for k,v in identity.items()):raise ValueError('cached case identity mismatch')
            else:
                elapsed=time.monotonic()-began if segment else prior_elapsed+time.monotonic()-began
                wall_cap=segment['maximum_segment_wall_s'] if segment else spec['maximum_batch_wall_s']
                if elapsed>wall_cap:
                    raise TimeoutError('registered batch wall limit')
                if segment and actual>=segment['maximum_new_environment_runs']:
                    raise ValueError('registered remaining execution count exceeded')
                # Start journal before each simulator entry, including errors.
                with (folder/'executions.jsonl').open('a',encoding='utf8') as f:
                    f.write(json.dumps({'index':index,'utc':utc(),'event':'start'})+'\n')
                result,c=rules.simulate(frozen,inputs['initial'],work['tickets'],context,policy,env)
                actual+=1;audit(result,work['tickets']);row,extra=metrics(result,c,inputs['initial'],frozen)
                row=dict(scope=scope,seed=work['seed'],family=work['family'],context=context,
                         policy=policy,environment=env['id'] if env else 'immediate_allow',**row)
                item=dict(row=row,ledger=result['ledger'],decisions=result['decisions'],**extra,
                          ema_records=getattr(c,'ema_records',[]))
                data=json.dumps(item,allow_nan=False,ensure_ascii=False).encode('utf8')
                temp=path.with_name(path.name+'.tmp');temp.write_bytes(gzip.compress(data,mtime=0));temp.replace(path)
                with (folder/'executions.jsonl').open('a',encoding='utf8') as f:
                    f.write(json.dumps({'index':index,'utc':utc(),'event':'finish'})+'\n')
            rows.append(item['row'])
            if len(rows)%22==0:
                write(folder/'progress.json',dict(status='running',rows=len(rows),total=len(jobs),elapsed_s=prior_elapsed+time.monotonic()-began))
                print(f'{len(rows)}/{len(jobs)}',flush=True)
        check_frozen()
        for name,sha in sources.items():
            if p.digest(ROOT/name)!=sha:raise ValueError('adapter changed during run')
        if len(rows)<len(jobs):
            write(folder/'progress.json',dict(status='pilot_completed',rows=len(rows),total=len(jobs),
                                              elapsed_s=prior_elapsed+time.monotonic()-began))
            return rows
        users=read(user_file)
        assert all(p.digest(ROOT/name)==sha for name,sha in users.items()), 'user artifacts changed'
        csv_write(folder/'results.csv',rows)
        journal=[json.loads(line) for line in (folder/'executions.jsonl').read_text(encoding='utf8').splitlines()]
        recovery=read(folder/'audit_recovery_registration.json') if (folder/'audit_recovery_registration.json').exists() else {}
        write(folder/'completion.json',dict(status='completed',utc=utc(),rows=len(rows),
              actual_environment_starts=sum(e['event']=='start' for e in journal),this_process_runs=actual,
              diagnostic_recovery_environment_runs=recovery.get('environment_runs',0),
              total_environment_runs=sum(e['event']=='start' for e in journal)+recovery.get('environment_runs',0),
              total_requests=sum(r['planned'] for r in rows),elapsed_this_process_s=time.monotonic()-began,
              batch_elapsed_s=prior_elapsed+time.monotonic()-began,
              prior_internal_wall_limit_stopped=segment is not None,
              segment_wall_s=time.monotonic()-began,
              active_CPU_time_measured=False,
              source_sha256=sources,old_source_count=len(spec['old_sources']),user_file_count=len(users),
              device_commands=0,training_episodes=0,experiment_ready=False))
    except BaseException as error:
        import traceback
        write(folder/'failure.json',dict(utc=utc(),completed_rows=len(rows),error_type=type(error).__name__,
                                        elapsed_process_wall_s=time.monotonic()-began,
                                        message=str(error),stack=traceback.format_exc()))
        raise
    finally:
        lock.unlink()
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run','check'])
    parser.add_argument('--folder',default=str(LOCAL/'comparison'));parser.add_argument('--pilot',action='store_true');args=parser.parse_args()
    if args.action=='prepare':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
    elif args.action=='check':print(json.dumps(check_frozen(),ensure_ascii=False,indent=2))
    else:run(args.folder,args.pilot)
