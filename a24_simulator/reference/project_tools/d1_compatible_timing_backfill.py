"""PC-only task-compatible backfill using historical measured timing, no J/AP.

CPU classification; detector on an immediately free compatible CPU/GPU lane.
Same-task parallelism is forbidden until actual lane release, not a time lease.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
from tools import d1_detector_gpu_bridge as b

PROTOCOL='cal03-compatible-timing-backfill-v1'
POLICY='CLASS_CPU_DETECTOR_BACKFILL_PC_V1'
LEGACY_ENGINE_SHA='384a5ab28d289f78a00ab8a4bb5e74c8f7df4e5d2ba8f3059130673ca44a20ac'
ARCHIVE=b.ROOT/'source_snapshots/d1_arrival_explore_before_compatible.py'
INSERT_A="""    compatible = getattr(decision_provider, 'protocol', None) == 'cal03-compatible-timing-backfill-v1'
    if compatible:
        from tools.d1_compatible_timing_backfill import validate_engine
        validate_engine(config, vectors, requests, policy, settings, decision_provider)
        base.require(admission is None and thermal_model is None, 'timing-only compatible provider')
"""


def verify_legacy_engine(expected):
    """Accept only the exact opt-in routing edit; legacy event body is immutable."""
    if expected!=LEGACY_ENGINE_SHA or b.f.x.p.digest(ARCHIVE)!=expected:
        raise ValueError('missing or changed legacy event source')
    original=ARCHIVE.read_text(encoding='utf8')
    target=original.replace("    empirical = config.get('protocol') == 'empirical-request-exploration-v1'\n",
        "    empirical = config.get('protocol') == 'empirical-request-exploration-v1'\n"+INSERT_A)
    target=target.replace('base.require((empirical or policy in POLICIES',
        'base.require((empirical or compatible or policy in POLICIES')
    target=target.replace('if decision_provider is not None and not empirical:',
        'if decision_provider is not None and not (empirical or compatible):')
    if Path(b.batch.engine.__file__).read_text(encoding='utf8')!=target:
        raise ValueError('event source changed beyond opt-in timing routing')
    return 'exact_legacy_archive_plus_timing_only_opt_in_routing'


def validate_engine(config,vectors,requests,policy,settings,provider):
    b.base.validate_config(config)
    if policy!=POLICY or not isinstance(provider,Controller) or settings['mode']!='explore':
        raise ValueError('explicit compatible timing opt-in required')
    if settings.get('load_prepare_factor',1)!=1 or settings.get('load_callback_factor',1)!=1:
        raise ValueError('no unregistered phase scaling')
    if set(vectors['cells'])!=set(config['cells']) or any(len(rows)!=4 or
        any(len(z['durations_ns'])!=5 or any(type(t) is not int or t<0 for t in z['durations_ns']) for z in rows)
        for rows in vectors['cells'].values()):raise ValueError('intact historical five-phase vectors required')
    for q in requests:
        if (q['task'],q['priority']) not in (('classification','urgent'),('detection','normal')):
            raise ValueError('scope is the two fixed task/priority cells')


class Controller:
    protocol=PROTOCOL
    policy=POLICY

    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        if thermal_model is not None or current_ap is not None:raise ValueError('timing only; no fabricated power/temperature')
        allowed={'id','task','priority','ordinal','arrival_ns','deadline_offset_ns'}
        if any(set(q)!=allowed or q['arrival_ns']>now for q in queue):raise ValueError('future/private ticket')
        if any(set(lane)!={'request','phase','since','dispatch'} for lane in lanes.values()):raise ValueError('private phase/vector leak')
        def order(q):
            aged=now-q['arrival_ns']>=settings['aging_ns']
            return (0 if aged else 1 if q['priority']=='urgent' else 2,
                q['arrival_ns'] if aged else q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id'])
        result=dict(now_ns=now,selected=None,reason='wait_actual_compatible_lane_release',candidates=[])
        for q in sorted(queue,key=order):
            options=[]
            for backend in (('CPU',) if q['task']=='classification' else ('CPU','GPU')):
                if lanes[backend]['request'] is not None:continue
                other=lanes['GPU' if backend=='CPU' else 'CPU']
                if other['request'] is not None and other['request']['task']==q['task']:continue
                cell=config['cells'][f"{q['task']}_{backend}_{q['priority']}"]
                response=cell['joint']['dispatch_to_response_ns']['median_ns']*settings['estimate_factor']
                if other['request'] is not None and other['phase']=='EXECUTING':
                    response+=cell['observed_phases']['start_to_output_ready_ns']['median_ns']*(settings['predicted_interference']-1)
                item=dict(request_id=q['id'],backend=backend,point_response_ns=response)
                options.append(item);result['candidates'].append(item)
            if options:
                winner=min(options,key=lambda x:(x['point_response_ns'],x['backend']!='CPU'))
                result.update(selected=dict(request_id=q['id'],backend=winner['backend']),
                    reason='priority_aging_then_available_task_compatible_backfill')
                break
        return result


def study(output,parent):
    from tools import d1_detector_gpu_report as shared
    output=Path(output);output.mkdir(parents=True,exist_ok=False);parent=Path(parent)
    shared.verify(b.ROOT)
    config=b.read(b.BUNDLE/'estimates.json');vectors=b.read(b.BUNDLE/'realizations.json')
    inputs=b.read(parent/'inputs.json');control=shared.load(parent/'timing_ledgers.json')
    control_path=parent/'timing_ledgers.json'
    if not control_path.exists():control_path=Path(str(control_path)+'.gz')
    sources=[Path(__file__),Path(b.batch.engine.__file__),ARCHIVE,Path(b.__file__),
        Path(b.batch.__file__),Path(shared.__file__),b.BUNDLE/'estimates.json',
        b.BUNDLE/'realizations.json',parent/'inputs.json',control_path]
    hashes={p.relative_to(b.f.x.p.ROOT).as_posix():b.f.x.p.digest(p) for p in sources}
    b.f.x.p.write(output/'registered_before_run.json',dict(utc=datetime.now(timezone.utc).isoformat(),
        hashes=hashes,policy=POLICY,controller='CPU classification; detector immediate compatible backfill; actual lane release',
        new_runs=16,reused_static_controls=len(control),requests_per_run=48,seeds=[623001,623002],
        role='posthoc timing-only development using previously seen inputs, not independent validation',
        realized_interference=[1.,1.5],power_model=None,AP_model=None,new_power_assumptions=False,
        energy_j=None,ap_c=None,device_commands=0,experiment_ready=False))
    rows=[];records=[]
    from tools.d1_detector_gpu_reference import occupancy
    for item in inputs:
        for factor in (1.,1.5):
            settings=b.batch.defaults('explore');settings.update(interference=factor,predicted_interference=factor)
            rr=b.batch.engine.simulate(config,vectors,item['tickets'],policy=POLICY,settings=settings,seed=item['seed'],decision_provider=Controller())
            segments=occupancy(rr['ledger'])
            if any(not z['historical_fixed_state_exists'] for z in segments):raise ValueError('unmeasured same-task pair escaped mask')
            if any(q['task']=='classification' and q.get('backend')!='CPU' for q in rr['ledger'] if 'backend' in q):raise ValueError('classification CPU invariant')
            row=dict(envelope=item['envelope'],seed=item['seed'],interference=factor,policy=POLICY,
                planned=48,completed=sum(q['status']=='succeeded' for q in rr['ledger']),
                deadline_met=sum('response_ns' in q and q['response_ns']<=q['deadline_offset_ns'] for q in rr['ledger']),
                urgent_p95_ms=rr['metrics']['urgent_p95_ms'],normal_mean_ms=rr['metrics']['normal_mean_ms'],
                detection_gpu_jobs=sum(q.get('backend')=='GPU' and q['task']=='detection' for q in rr['ledger']),
                overlap_s=sum(z['end_s']-z['start_s'] for z in segments if '+' in z['state']),
                unmeasured_concurrency_s=0.,energy_j=None,ap_peak_c=None,current_profile_supported=False)
            rows.append(row);records.append(dict(meta=row,ledger=rr['ledger'],segments=segments,decisions=rr['decisions']))
    if hashes!={p.relative_to(b.f.x.p.ROOT).as_posix():b.f.x.p.digest(p) for p in sources}:raise ValueError('registered source changed')
    b.f.x.old.csv_write(output/'timing_only.csv',rows);b.f.x.p.write(output/'timing_ledgers.json',records)
    b.f.x.p.write(output/'summary.json',dict(new_runs=16,reused_static_controls=len(control),
        complete_deadline_cases=sum(z['deadline_met']==48 for z in rows),
        detection_gpu_jobs=sum(z['detection_gpu_jobs'] for z in rows),
        new_device_validation=False,current_J_AP_computed=False,classification_GPU_used=False,
        unmeasured_same_task_pair_s=0.,device_commands=0,experiment_ready=False))
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    parser.add_argument('--parent',default=str(b.ROOT/'run_v1'));args=parser.parse_args()
    # Canonical import avoids duplicate Controller classes under python -m (__main__).
    from tools.d1_compatible_timing_backfill import study as canonical_study
    canonical_study(args.output,args.parent)
