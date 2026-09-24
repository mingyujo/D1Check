"""Integrated development collection preparation/replay. prepare/check/freeze use no ADB."""
from __future__ import annotations
import argparse
import copy
import json
import statistics
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_dev as v
from tools import d1_arrival_timing_calibration as cal
from tools import d1_cal03_connection as pc

PROTOCOL = 'arrival-collection-dev-v1'
POLICY = 'COLLECTION_DISPATCH_DEV_1'
EXPERIMENT = 'ARRIVAL-COLLECT-01'
SEED = 2026092402
CONDITIONS = [
    ('active_cpu_sparse', 'strict_active', 'CPU', 1, False),
    ('shadow_cpu_sparse', 'fixed_shadow', 'CPU', 1, False),
    ('shadow_split_sparse', 'fixed_shadow', 'SPLIT', 1, False),
    ('shadow_cpu_queue', 'fixed_shadow', 'CPU', 1, True),
    ('shadow_split_queue_serial', 'fixed_shadow', 'SPLIT', 1, True),
    ('shadow_split_queue_lanes', 'fixed_shadow', 'SPLIT', 2, True),
]


def identity():
    extra = ['tools/d1_arrival_collection.py', 'tools/d1_arrival_collection_device.py',
             'tools/d1_cal03_connection.py', 'tools/d1_collection_recovery.py', 'tools/d1_recorded_process.py']
    return cal.code_identity() | {name: p.digest(cal.ROOT/name) for name in extra}


def actual_choice(queue, lanes, mode, assignment, concurrency):
    ordered = sorted(queue, key=lambda t: (t['priority'] != 'urgent', t['ordinal'], t['id']))
    busy = any(l['phase'] != 'AVAILABLE' for l in lanes.values())
    selected = None
    if mode == 'strict_active':
        reason = 'wait_empty' if not queue else 'wait_solo_scope_busy' if busy else 'fallback_cpu_missing_adaptive_cost'
        if reason == 'fallback_cpu_missing_adaptive_cost':
            selected = dict(request_id=ordered[0]['id'], backend='CPU')
    else:
        if not (concurrency == 1 and busy):
            for t in ordered:
                b = 'CPU' if assignment == 'CPU' or t['priority'] == 'urgent' else 'GPU'
                if lanes[b]['phase'] == 'AVAILABLE':
                    selected = dict(request_id=t['id'], backend=b); break
        reason = 'collection_fixed_assignment' if selected else 'wait_empty' if not queue else 'wait_collection_busy'
    return dict(selected=selected, reason=reason, candidates=[])


def validate_artifacts(root, config):
    root = Path(root)
    m = p.read(root/'manifest.json')
    pc.validate_config(config)
    v.require(m['protocol'] == PROTOCOL and m['policy'] == POLICY, 'collection namespace')
    v.require(m['collection_mode'] in ('strict_active', 'fixed_shadow') and m['collection_assignment'] in ('CPU','SPLIT')
              and m['maximum_concurrency'] in (1,2), 'collection mode')
    hook = lambda q,l,n: actual_choice(q,l,m['collection_mode'],m['collection_assignment'],m['maximum_concurrency'])
    timing = v.validate_artifacts(root, (PROTOCOL, POLICY, hook))
    rows, trace, observed = (p.read(root/n) for n in ('requests.json','decision_trace.json','collection_trace.json'))
    v.require(observed['complete'] and not observed['overflow'] and observed['config_sha256'] == m['collection_estimates_sha256'], 'collection trace loss/identity')
    v.require((observed['mode'],observed['assignment'],observed['maximum_concurrency']) ==
              (m['collection_mode'],m['collection_assignment'],m['maximum_concurrency']), 'collection trace mode')
    decisions = [d for d in trace['records'] if d['kind'] == 'decision']
    by_id = {r['request_id']:r for r in rows}
    tickets = {q['request_id']:q for q in m['requests']}
    v.require(len(observed['records']) == len(decisions) and len(rows) == 4, 'decision/request counts')
    intervals=[]
    for i,(o,d) in enumerate(zip(observed['records'], decisions)):
        times = [o[k] for k in ('snapshot_ns','compute_start_ns','compute_end_ns','selection_end_ns','record_end_ns')]
        v.require(o['seq']==i and times==sorted(times) and times[0]==d['mono_ns'] and times[-1]<=d['decision_end_ns'], 'cost order')
        queue = [dict(t, arrival_ns=by_id[t['id']]['actual_arrival_ns']) for t in d['queue']]
        lanes = {b:{k:val for k,val in lane.items() if k not in ('remaining_ns','remaining_state')}
                 for b,lane in d['lanes'].items()}
        for lane in lanes.values():
            lane['priority'] = tickets[lane['request_id']]['priority'] if lane['request_id'] else None
        expected = pc.decide(config, queue, lanes, times[0])
        v.require(o['shadow'] == expected, 'Android vs PC strict policy mismatch')
        v.require(o['actual_selected'] == d['selected'] and o['actual_reason'] == d['reason'], 'active/shadow dispatch mismatch')
        if m['collection_mode']=='strict_active':
            v.require(d['selected']==expected['selected'], 'active strict dispatch')
    for r in rows:
        q=tickets[r['request_id']]
        summary=p.read(root/'summary.json')
        v.require(r['scheduled_arrival_ns']==summary['workload_start_ns']+q['offset_ms']*1_000_000 and
                  r['deadline_ns']==r['scheduled_arrival_ns']+q['deadline_ms']*1_000_000 and
                  r['arrival_lag_ns']==r['actual_arrival_ns']-r['scheduled_arrival_ns'], 'arrival/deadline')
        intervals.append((r['dispatch_ns'],1)); intervals.append((r['lane_available_ns'],-1))
    count=0
    for _,delta in sorted(intervals):
        count+=delta;v.require(0<=count<=m['maximum_concurrency'], 'global concurrency')
    warm=p.read(root/'warmup_trace.json')
    v.require(len(warm)==16, 'warmup denominator')
    for i,q in enumerate(m['warmup_requests']):
        a,b=warm[2*i:2*i+2]
        v.require(a['kind']=='start' and b['kind']=='end' and b['status']=='succeeded' and
                  a['request_id']==b['request_id']==q['request_id'] and a['model_key']==b['model_key']==q['model_key'] and
                  a['mono_ns']<=b['mono_ns']<=min(r['actual_arrival_ns'] for r in rows) and
                  (i==0 or warm[2*i-1]['mono_ns']<=a['mono_ns']), 'warmup boundary/order')
    # Verify actual overlap, not just two lane assignments or planned offset.
    overlaps=[]
    for a in rows:
        for b in rows:
            if a['selected_backend']=='GPU' and b['selected_backend']=='CPU':
                overlap=min(a['inference_end_ns'],b['inference_end_ns'])-max(a['inference_start_ns'],b['inference_start_ns'])
                if overlap>0: overlaps.append(dict(gpu=a['request_id'],cpu=b['request_id'],host_api_overlap_ns=overlap))
    queued=sum(r['dispatch_ns']>r['queue_entry_ns'] and any(o['phase']=='AVAILABLE' and
               r['queue_entry_ns']<o['mono_ns']<=r['dispatch_ns'] for o in trace['records'] if o['kind']=='phase') for r in rows)
    if m['collection_condition'].endswith('lanes'): v.require(len(overlaps)==2, 'two planned pairs must actually overlap; no replacement')
    elif 'queue' in m['collection_condition']: v.require(queued>=2, 'queued handoff not observed; no replacement')
    return dict(timing=timing, requests=4, warmup_calls=8, decisions=len(decisions), observed_overlaps=overlaps,
                queued_handoffs=queued, experiment_ready=False)


def prepare(parent_path, config_path, build_path, output):
    from tools import d1_apk_identity as apk
    parent_path,config_path,build_path,output=map(Path,(parent_path,config_path,build_path,output))
    v.require(not output.exists(), 'new plan directory required')
    parent=p.read(parent_path);config=p.read(config_path);pc.validate_config(config)
    build=p.read(build_path);v.require(cal.apk_sources(build['source_code'])==cal.apk_sources(identity()),'build/source mismatch')
    tools=parent['apk_preflight']['toolchain'];candidate=apk.inspect(build['apk_path'],tools)
    apk.compatible(candidate,parent['apk_preflight']['candidate'],candidate)
    template=p.read(parent_path.parent/parent['entries'][0]['manifest'])
    output.mkdir(parents=True);(output/'manifests').mkdir()
    entries=[]
    for phase,conditions in [('development',CONDITIONS),('confirmation',list(reversed(CONDITIONS[:-1]))+[CONDITIONS[-1]])]:
        for condition,mode,assignment,concurrency,queued in conditions:
            index=len(entries);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{EXPERIMENT}/{SEED}/{phase}/{condition}'))
            m=copy.deepcopy(template);m.pop('calibration_backend',None)
            m.update(protocol=PROTOCOL,policy=POLICY,session_id=sid,experiment_id=EXPERIMENT,collection_phase=phase,
                collection_condition=condition,collection_mode=mode,collection_assignment=assignment,
                maximum_concurrency=concurrency,execution_purpose='integrated_development_collection',
                apk_sha256=candidate['apk_sha256'],collection_estimates_sha256=p.digest(config_path),
                collection_estimates_bytes=config_path.stat().st_size)
            for spec in m['models'].values():
                spec['identity']['session_id']=sid;spec['target']['apk_sha256']=candidate['apk_sha256']
            offsets=[0,100,5000,5100] if queued else [0,5000,10000,15000]
            m['requests']=[dict(request_id=str(uuid.uuid5(uuid.UUID(sid),f'request/{i}')),ordinal=i,
                task_id='detection' if i%2==0 else 'classification',priority='normal' if i%2==0 else 'urgent',
                sample_id=template['images'][0]['sample_id'],offset_ms=offset,deadline_ms=5000) for i,offset in enumerate(offsets)]
            for i,q in enumerate(m['warmup_requests']):q['request_id']=str(uuid.uuid5(uuid.UUID(sid),f'warmup/{i}'))
            file=output/'manifests'/f'{sid}.json';cal.write_new(file,m)
            entries.append(dict(index=index,session_id=sid,phase=phase,condition=condition,manifest=f'manifests/{sid}.json',manifest_sha256=p.digest(file)))
    sources=copy.deepcopy(parent['source_files'])
    sources['collection_estimates.json']=dict(path=str(config_path.resolve()),bytes=config_path.stat().st_size,sha256=p.digest(config_path))
    plan={k:copy.deepcopy(parent[k]) for k in ('device_fingerprint','battery_max_temperature_tenths_c','battery_min_percent',
           'battery_start_percent','require_unplugged','initial_cool_seconds','cool_down_seconds','screen_contract')}
    plan['screen_contract']['version']='collection-screen-v1'
    for key in ('parent_prepared_plan','parent_prepared_plan_sha256','confirmation_rule'):plan['screen_contract'].pop(key,None)
    plan.update(protocol='arrival-collection-plan-v1',experiment_id=EXPERIMENT,status='PREPARED_NOT_APPROVED',experiment_ready=False,
        seed=SEED,entries=entries,session_cap=12,request_cap=48,warmup_cap=96,install_cap=2,retry_cap=0,replacement_cap=0,additional_cap=0,
        host_phase_wall_seconds=2700,cleanup_seconds=45,maximum_active_seconds=5490,
        source_files=sources,source_code=identity(),apk_path=build['apk_path'],apk_sha256=candidate['apk_sha256'],
        build_receipt=str(build_path.resolve()),build_receipt_sha256=p.digest(build_path),
        apk_preflight=dict(candidate=candidate,toolchain=tools,tool_sha256=parent['apk_preflight']['tool_sha256']),
        parent_plan_sha256=p.digest(parent_path),config_sha256=p.digest(config_path),
        registry=str(output.parent/'collection_execution_registry'/EXPERIMENT),
        output_root=str(output.parent/'integrated_collection_run_v1'),
        analysis_contract='one independent session/condition/phase; two correlated task-pair repetitions; descriptive median/range/difference only; no tail/accuracy/superiority PASS',
        parallel_gate='same phase prior 5 sessions validated+cleanup; current admission+environment; two actual host-API overlaps required',
        stop_rule='any technical/quality/environment/coverage failure closes entire plan; no restart/retry/replacement',
        freeze_rule='all development 6 valid; freeze descriptive condition cost medians+source hashes; confirmation never refits; performance_pass=null')
    cal.write_new(output/'collection_plan.json',plan)
    return plan


def check(plan_path):
    plan_path=Path(plan_path);plan=p.read(plan_path)
    recovered = plan.get('installation_contract') == 'recovery-verified-only-v1'
    v.require(plan['protocol']=='arrival-collection-plan-v1' and plan['experiment_id'] in (('ARRIVAL-COLLECT-02','ARRIVAL-COLLECT-03') if recovered else (EXPERIMENT,)) and
              not plan['experiment_ready'] and plan['source_code']==identity(), 'plan/source identity')
    v.require((plan['session_cap'],plan['request_cap'],plan['warmup_cap'],plan['install_cap'],plan['maximum_active_seconds'])==(12,48,96,0 if recovered else 2,5490), 'budget')
    v.require(all(plan[k]==0 for k in ('retry_cap','replacement_cap','additional_cap')), 'no retries')
    v.require((plan['host_phase_wall_seconds'],plan['cleanup_seconds'])==(2700,45), 'time allocation')
    expected_order=[('development',c[0]) for c in CONDITIONS]+[('confirmation',c[0]) for c in list(reversed(CONDITIONS[:-1]))+[CONDITIONS[-1]]]
    v.require([(e['phase'],e['condition']) for e in plan['entries']]==expected_order, 'paired order/parallel gate')
    build=p.read(plan['build_receipt'])
    v.require(p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
              cal.apk_sources(build['source_code'])==cal.apk_sources(plan['source_code']) and
              p.digest(plan['apk_path'])==plan['apk_sha256']==build['apk_sha256'], 'APK binding')
    for info in plan['source_files'].values():
        v.require(Path(info['path']).stat().st_size==info['bytes'] and p.digest(info['path'])==info['sha256'], 'input identity')
    config=p.read(plan['source_files']['collection_estimates.json']['path']);pc.validate_config(config)
    ids=set();request_ids=set();requests=warmups=0
    for e in plan['entries']:
        file=plan_path.parent/e['manifest'];m=p.read(file)
        v.require(p.digest(file)==e['manifest_sha256'] and m['protocol']==PROTOCOL and m['session_id']==e['session_id'] and m['experiment_id']==plan['experiment_id'] and
                  m['apk_sha256']==plan['apk_sha256'] and not m['experiment_ready'], 'manifest identity')
        v.require(e['session_id'] not in ids,'duplicate session');ids.add(e['session_id'])
        condition=next(c for c in CONDITIONS if c[0]==e['condition'])
        v.require((m['collection_mode'],m['collection_assignment'],m['maximum_concurrency'])==condition[1:4], 'condition semantics')
        v.require([q['offset_ms'] for q in m['requests']]==([0,100,5000,5100] if condition[4] else [0,5000,10000,15000]), 'trace')
        v.require(m['collection_estimates_sha256']==plan['config_sha256']==plan['source_files']['collection_estimates.json']['sha256'] and
                  m['collection_phase']==e['phase'] and m['collection_condition']==e['condition'] and
                  m['cpu_threads']==1 and m['maximum_duration_ms']==120000 and m['storage_mode']=='persist_all' and
                  m['images']==config['scope']['images'], 'collection scope')
        for key,spec in m['models'].items():
            v.require(spec['identity']['session_id']==e['session_id'] and spec['target']['apk_sha256']==plan['apk_sha256'] and
                      all(spec[field]==config['scope']['models'][key][field] for field in ('model','runtime','tensor')), 'model/runtime/tensor identity')
        v.require([q['model_key'] for q in m['warmup_requests']]==['classification_CPU']*2+['classification_GPU']*2+['detection_CPU']*2+['detection_GPU']*2, 'warmup order')
        for i,q in enumerate(m['requests']):
            v.require((q['task_id'],q['priority'],q['ordinal'],q['deadline_ms'])==
                      ('detection' if i%2==0 else 'classification','normal' if i%2==0 else 'urgent',i,5000), 'role/deadline')
        for q in m['requests']+m['warmup_requests']:
            v.require(q['request_id'] not in request_ids and q['sample_id']==m['images'][0]['sample_id'], 'request identity/input')
            request_ids.add(q['request_id'])
        requests+=len(m['requests']);warmups+=len(m['warmup_requests'])
    v.require((len(ids),requests,warmups)==(12,48,96), 'aggregate count')
    return dict(status='PC_DRY_RUN_PASS_NOT_DEVICE_READY',plan_sha256=p.digest(plan_path),sessions=12,requests=48,warmup=96,
                adb_calls=0,install_attempts=0,session_attempts=0,experiment_ready=False)


def verify_recovery(folder):
    """Bind a later development freeze to the bytes validated on collection day."""
    folder = Path(folder)
    validated = p.read(folder/'validated.json')
    recovery = validated['recovery']
    v.require(validated['status'] == 'valid' and recovery['status'] == 'recovered', 'recovery not validated')
    expected = {item['name']: item for item in recovery['files']}
    actual = {f.name for f in (folder/'artifacts').iterdir() if f.is_file()}
    v.require(len(expected) == len(recovery['files']) and set(expected) == actual, 'recovered file set changed')
    for name, item in expected.items():
        file = folder/'artifacts'/name
        v.require(file.stat().st_size == item['bytes'] and p.digest(file) == item['sha256'], 'recovered artifact changed')


def summarize(plan_path, phase):
    plan_path=Path(plan_path);plan=p.read(plan_path)
    root=Path(plan['output_root'])/phase
    v.require((root/'complete.json').is_file() and not (Path(plan['registry'])/'stopped.json').exists(), 'phase incomplete/stopped')
    results={};hashes={}
    for e in plan['entries']:
        if e['phase']!=phase:continue
        folder=root/f"{e['index']:02d}_{e['session_id']}"
        v.require(p.read(folder/'host_cleanup.json')['status']=='completed' and (folder/'validated.json').is_file(),'validation/cleanup missing')
        verify_recovery(folder)
        trace=p.read(folder/'artifacts/collection_trace.json');rows=p.read(folder/'artifacts/requests.json')
        selected={o['actual_selected']['request_id']:o for o in trace['records'] if o['actual_selected']}
        values={'policy_compute_ns':[o['compute_end_ns']-o['compute_start_ns'] for o in trace['records']],
                'record_ns':[o['record_end_ns']-o['selection_end_ns'] for o in trace['records']],
                'decision_to_dispatch_ns':[r['dispatch_ns']-selected[r['request_id']]['snapshot_ns'] for r in rows]}
        for name,a,b in [('dispatch_to_start_ns','dispatch_ns','execution_start_ns'),('persist_to_lane_ns','persist_complete_ns','lane_available_ns'),
                         ('start_to_output_ns','execution_start_ns','output_ready_ns')]:
            for cell in sorted({f"{r['task_id']}_{r['selected_backend']}_{r['priority']}" for r in rows}):
                values[cell+'.'+name]=[r[b]-r[a] for r in rows if f"{r['task_id']}_{r['selected_backend']}_{r['priority']}"==cell]
        results[e['condition']]=dict(independent_sessions=1,requests=4,metrics={k:dict(median=statistics.median(vs),min=min(vs),max=max(vs),n=len(vs)) for k,vs in values.items()})
        for f in folder.rglob('*'):
            if f.is_file():hashes[str(f.resolve())]=p.digest(f)
    v.require(len(results)==6,'six complete conditions required')
    return dict(protocol='arrival-collection-descriptive-freeze-v1',plan_sha256=p.digest(plan_path),phase=phase,
                conditions=results,input_hashes=hashes,experiment_ready=False,performance_pass=None,
                scope='condition-specific diagnostic summaries, not replacement for CAL03 estimates or causal kernel interference')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for a in ('parent','config','build','output'):prep.add_argument('--'+a,type=Path,required=True)
    for name in ('check','freeze','confirm','run'):
        s=sub.add_parser(name);s.add_argument('--plan',type=Path,required=True)
        if name in ('freeze','confirm'):s.add_argument('--output',type=Path,required=True)
        if name=='confirm':s.add_argument('--freeze',type=Path,required=True)
        if name=='run':
            s.add_argument('--phase',choices=['development','confirmation'],required=True);s.add_argument('--adb',required=True)
            s.add_argument('--serial',required=True);s.add_argument('--approved-total-cap',type=int,required=True)
            s.add_argument('--expected-plan-sha256',required=True);s.add_argument('--freeze',type=Path)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.parent,args.config,args.build,args.output);result={'plan':str(args.output/'collection_plan.json')}
    elif args.command=='check':result=check(args.plan)
    elif args.command in ('freeze','confirm'):
        result=summarize(args.plan,'development' if args.command=='freeze' else 'confirmation')
        if args.command=='confirm':
            frozen=p.read(args.freeze);v.require(frozen['plan_sha256']==p.digest(args.plan),'freeze identity')
            claim=p.read(Path(p.read(args.plan)['registry'])/'confirmation_consumed.json')
            v.require(claim['freeze_sha256']==p.digest(args.freeze),'confirmation did not bind this freeze')
            result['freeze_sha256']=p.digest(args.freeze)
            result['median_errors']={c:{k:val['median']-frozen['conditions'][c]['metrics'][k]['median'] for k,val in row['metrics'].items()} for c,row in result['conditions'].items()}
        cal.write_new(args.output,result)
    else:
        from tools import d1_arrival_collection_device as device
        result=device.run(args.plan,args.phase,args.adb,args.serial,args.approved_total_cap,args.expected_plan_sha256,args.freeze)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
