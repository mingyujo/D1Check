"""Recorded-observation 10s replay; no fitting, device commands or policy simulation."""
import argparse
import csv
import gzip
import json
import math
import time
from pathlib import Path
import numpy as np
from tools import d1_history_model_refinement as h
from tools import d1_ap_preparation_memory as memory

BUNDLE=h.m.ROOT/'docs/results/rolling_forecast_01'
METHODS=('FROZEN_OPEN_LOOP','OBSERVATION_PERSISTENCE','ROLLING_OFFSET')


def export(external):
    if (BUNDLE/'inputs.json.gz').exists():raise FileExistsError('export already exists')
    cases=h.m.read(h.BUNDLE/'inputs.json.gz');portable=[];source={};mapping_deltas=[]
    roots={}
    for block,name in [('history','energy_ap_history_recovery_run_v7/primary'),('sustained','sustained_confirmation_run_v1')]:
        root=Path(external)/name;roots[block]=(root,h.m.read(root/'frozen_collection_plan.json'))
    def match(records,key,t):
        # Stored history subtraction may differ by floating-point ULP at half-ns.
        row=min(records,key=lambda x:abs(x[key]-t));delta=abs(row[key]-t)
        if delta>1e-7:raise ValueError('metadata clock mismatch')
        mapping_deltas.append(delta);return row
    for c in cases:
        root,plan=roots[c['block']]
        entry=next(e for e in plan['entries'] if (e['phase']==c['id'] if c['block']=='history' else e['index']==c['index']))
        folder=root/f"{entry['index']:02d}_{entry['session_id']}";art=folder/'artifacts'
        boundary=h.m.read(art/('history_boundary.json' if c['block']=='history' else 'common_boundary.json'))
        origin=boundary['target_start_ns'] if c['block']=='history' else boundary['start_ns']
        th=[json.loads(x) for x in (folder/'thermal.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        events=[json.loads(x) for x in (art/'progress.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        thermal=[dict(t=(x['mono_ns']-origin)/1e9,available=(x['after_ns']-origin)/1e9,lo=(x['before_ns']-origin)/1e9,value=float(x['AP'])) for x in th if x.get('AP') not in ('',None)]
        power=[dict(t=(((x['snapshot_start_ns']+x['sensor_read_end_ns'])//2)-origin)/1e9,
                    available=(x['mono_ns']-origin)/1e9,value=h.m.base.energy.discharge_w(x,1000))
               for x in events if x.get('kind')=='power_sample']
        ap=[];watts=[]
        for t,y in [(p['t'],p['ap']) for p in c['pre']]+list(zip(c['q'],c['ap'])):
            row=match(thermal,'t',t)
            if row['value']!=y:raise ValueError('AP value mismatch')
            ap.append(row)
        for t,w in zip(c['power_t'],c['power_w']):
            row=match(power,'t',t)
            if row['value']!=w:raise ValueError('power value mismatch')
            watts.append(row)
        clean={k:c[k] for k in ('id','block','role','policy','pre','actual','pre_w','last_lane_s')}
        clean.update(ap_observations=ap,power_observations=watts,gap=c.get('gap'));portable.append(clean)
        for path in (folder/'thermal.jsonl',art/'progress.jsonl'):source[c['id']+'/'+path.name]=h.m.sha(path)
    (BUNDLE/'inputs.json.gz').write_bytes(gzip.compress(json.dumps(portable,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    h.m.write(BUNDLE/'source_inventory.json',dict(required_original_files=source,source_portable_inputs_sha256=h.m.sha(h.BUNDLE/'inputs.json.gz'),
        model_sha256=h.m.sha(h.m.MODEL),cases=20,max_metadata_mapping_delta_s=max(mapping_deltas),
        availability='device upper query bracket/event record proxy; host delivery and physical sensor refresh unknown',
        raw_root_aliases=['energy_ap_history_recovery_run_v7/primary','sustained_confirmation_run_v1']))


def frozen_ap(c,frozen,times):
    ap=frozen['ap'];beta=ap['beta'];slopes=ap['parameters']['ap_slope_at_30_c_per_s']
    init=memory.initialize(c['pre'],beta,30.)
    times=[init['anchor_s'] if abs(t-init['anchor_s'])<=1e-7 else t for t in times]
    if any(t<init['anchor_s'] or t>c['actual'][-1]['end_s'] for t in times):raise ValueError('AP prediction coverage')
    segments=[dict(s,end_s=min(s['end_s'],max(times))) for s in c['actual'] if s['start_s']<max(times) and s['end_s']>0]
    zero={k:slopes['resident_idle'] for k in slopes}
    indices=[i for i,t in enumerate(times) if t>init['anchor_s']]
    query=[times[i] for i in indices]
    def propagate(parameters):
        values=np.full(len(times),init['anchor_ap_c'])
        if query:values[indices]=memory._propagate(segments,query,parameters,beta,30.,0.,init)
        return values
    a=propagate(zero);b=propagate(slopes)
    return a+ap['k']*(b-a)


def state_energy(c,frozen,a,b):
    segments=[dict(s,end_s=min(s['end_s'],b)) for s in c['actual'] if s['start_s']<b and s['end_s']>0]
    return h.load_basis(segments,frozen,b)-h.load_basis(segments,frozen,a)


def available(observations,now):
    # Availability, not observation midpoint, determines the prefix.
    result=[x for x in observations if x['available']<=now]
    if any(x['t']>x['available'] or not math.isfinite(x['available']) for x in result):raise ValueError('invalid availability')
    return result


def snapshot(c,now,frozen,contract):
    if now<35 or any(p['hi']>now for p in c['pre']):raise ValueError('future preload')
    aps=available(c['ap_observations'],now);powers=available(c['power_observations'],now)
    status=dict(cutoff_s=now,ap_status='unavailable',power_status='unavailable')
    if aps:
        last=max(aps,key=lambda x:x['t']);status['ap_age_s']=now-last['t']
        if status['ap_age_s']<=contract['ap_max_age_s']:
            if not math.isfinite(last['value']):raise ValueError('missing AP input')
            pred=float(frozen_ap(c,frozen,[last['t']])[0])
            status.update(ap_status='available',ap_t=last['t'],ap_available=last['available'],ap_value=last['value'],ap_delta=last['value']-pred)
    if powers:
        last=max(powers,key=lambda x:x['t']);status['power_age_s']=now-last['t']
        end=last['t'];start=now-10
        if status['power_age_s']<=contract['power_max_age_s'] and end-start>=contract['minimum_power_history_s']:
            data=dict(power_t=[x['t'] for x in powers],power_w=[x['value'] for x in powers])
            try:observed=h.m.integral(data,start,end)
            except ValueError:status['power_status']='past_gap_or_missing'
            else:
                duration=end-start;expected=c['pre_w']*duration+state_energy(c,frozen,start,end)
                status.update(power_status='available',power_available=max(x['available'] for x in powers),
                              history_start_s=start,history_end_s=end,power_mean_w=observed/duration,power_delta_w=(observed-expected)/duration)
    return status


def forecast_ap(c,frozen,snap,method,times):
    if method=='OBSERVATION_PERSISTENCE':
        if snap['ap_status']!='available':raise ValueError('AP unavailable')
        return np.full(len(times),snap['ap_value'])
    original=frozen_ap(c,frozen,times)
    if method=='FROZEN_OPEN_LOOP':return original
    if snap['ap_status']!='available':raise ValueError('AP unavailable')
    if method!='ROLLING_OFFSET':raise ValueError('method')
    return original+snap['ap_delta']*np.exp(-frozen['ap']['beta']*(np.array(times)-snap['ap_t']))


def forecast_energy(c,frozen,snap,method,end):
    start=snap['cutoff_s'];duration=end-start
    if method=='OBSERVATION_PERSISTENCE':
        if snap['power_status']!='available':raise ValueError('power unavailable')
        return snap['power_mean_w']*duration
    original=c['pre_w']*duration+state_energy(c,frozen,start,end)
    if method=='FROZEN_OPEN_LOOP':return original
    if snap['power_status']!='available':raise ValueError('power unavailable')
    if method!='ROLLING_OFFSET':raise ValueError('method')
    predicted=original+snap['power_delta_w']*duration
    if predicted<=0:raise ValueError('nonpositive forecast; not clipped')
    return predicted


def classify(c,start,end):
    relevant=[s for s in c['actual'] if min(end,s['end_s'])>max(start,s['start_s'])]
    names=set(s['state'] for s in relevant)
    if names=={'idle'}:return 'resident_idle'
    return 'transition_or_mixed' if len(names)>1 else 'single_state_load'


def run(output):
    output=Path(output)
    if output.exists():raise FileExistsError('new output required')
    output.mkdir(parents=True);started=time.monotonic()
    cases=h.m.read(BUNDLE/'inputs.json.gz');frozen=h.m.read(h.m.MODEL);contract=h.m.read(BUNDLE/'contract.json')
    if len(cases)!=20 or len({c['id'] for c in cases})!=20 or h.m.sha(h.m.MODEL)!=h.m.MODEL_SHA:raise ValueError('identity')
    results=[];paths=[];snapshots=[]
    for c in cases:
        for start in contract['starts_s']:
            end=start+contract['horizon_s'];snap=snapshot(c,start,frozen,contract)
            snapshots.append(dict(id=c['id'],block=c['block'],role=c['role'],**snap))
            # Evaluation values are inspected only after the available prefix is fixed.
            aps=[x for x in c['ap_observations'] if start<x['lo']<=x['t']<=x['available']<=end]
            q=[x['t'] for x in aps];obs=np.array([x['value'] for x in aps])
            if any(not math.isfinite(v) for v in obs):raise ValueError('missing AP target')
            energy_ok=end<=120 and snap['power_status']=='available'
            ap_ok=bool(q) and snap['ap_status']=='available' and end<=c['actual'][-1]['end_s']
            observed_j=h.m.integral(dict(power_t=[x['t'] for x in c['power_observations']],power_w=[x['value'] for x in c['power_observations']]),start,end) if energy_ok else None
            for method in METHODS:
                row=dict(id=c['id'],block=c['block'],role=c['role'],policy=c['policy'],method=method,start_s=start,end_s=end,
                         segment_type=classify(c,start,end),energy_status='complete_10s' if energy_ok else 'outside_120s_or_input_unavailable',
                         ap_status='scored' if ap_ok else 'unavailable',ap_samples=len(q) if ap_ok else 0,
                         observed_j=None,predicted_j=None,signed_j=None,abs_j=None,relative_j=None,
                         ap_mae_c=None,ap_max_absolute_c=None,peak_signed_error_c=None,direction_opposite=None,
                         schedule_information='none' if method=='OBSERVATION_PERSISTENCE' else 'actual future schedule conditional',
                         future_observation_input=False)
                if energy_ok:
                    predj=forecast_energy(c,frozen,snap,method,end)
                    row.update(observed_j=observed_j,predicted_j=predj,signed_j=predj-observed_j,abs_j=abs(predj-observed_j),relative_j=(predj-observed_j)/observed_j)
                if ap_ok:
                    pred=forecast_ap(c,frozen,snap,method,q);errors=pred-obs
                    change=obs[-1]-obs[0];pd=pred[-1]-pred[0]
                    row.update(ap_mae_c=float(np.mean(abs(errors))),ap_max_absolute_c=float(max(abs(errors))),
                               peak_signed_error_c=float(max(pred)-max(obs)),direction_opposite=bool(len(q)>1 and abs(change)>.100000001 and change*pd< -1e-12))
                    paths.extend(dict(id=c['id'],block=c['block'],role=c['role'],method=method,window_start_s=start,t_s=x['t'],observed=x['value'],predicted=float(y)) for x,y in zip(aps,pred))
                results.append(row)
    h.m.table(output/'window_errors.csv',results);h.m.table(output/'snapshots.csv',snapshots)
    h.m.table(output/'ap_paths.csv',paths)
    sessions=[]
    for c in cases:
        for method in METHODS:
            use=[x for x in results if x['id']==c['id'] and x['method']==method]
            ej=[x['abs_j'] for x in use if x['abs_j'] is not None];ap=[x['ap_mae_c'] for x in use if x['ap_mae_c'] is not None]
            sessions.append(dict(id=c['id'],block=c['block'],role=c['role'],policy=c['policy'],method=method,
                                 energy_windows=len(ej),ap_windows=len(ap),energy_mae_10s_j=float(np.mean(ej)) if ej else None,
                                 energy_max_absolute_10s_j=max(ej) if ej else None,ap_mae_10s_c=float(np.mean(ap)) if ap else None,
                                 ap_max_absolute_c=max((x['ap_max_absolute_c'] for x in use if x['ap_max_absolute_c'] is not None),default=None),
                                 opposite_windows=sum(x['direction_opposite'] is True for x in use)))
    h.m.table(output/'session_errors.csv',sessions)
    groups=[]
    for block,role in [('history','development'),('history','confirmation'),('sustained','evaluation')]:
        baseline={x['id']:x for x in sessions if x['block']==block and x['role']==role and x['method']=='FROZEN_OPEN_LOOP'}
        for method in METHODS:
            use=[x for x in sessions if x['block']==block and x['role']==role and x['method']==method]
            groups.append(dict(block=block,role=role,method=method,n=len(use),energy_mae_10s_j=float(np.mean([x['energy_mae_10s_j'] for x in use])),
                               ap_mae_10s_c=float(np.mean([x['ap_mae_10s_c'] for x in use])),
                               energy_worse_sessions=sum(x['energy_mae_10s_j']>baseline[x['id']]['energy_mae_10s_j']+1e-10 for x in use),
                               ap_worse_sessions=sum(x['ap_mae_10s_c']>baseline[x['id']]['ap_mae_10s_c']+1e-10 for x in use),
                               energy_max_10s_j=max(x['energy_max_absolute_10s_j'] for x in use),ap_max_absolute_c=max(x['ap_max_absolute_c'] for x in use)))
    h.m.table(output/'comparison.csv',groups)
    summary=dict(sessions=20,forecast_origins=len(snapshots),rows=len(results),energy_observed_union_s=[35,115],common_120s_forecast_error=None,
                 horizon_s=10,fit_calls=0,device_commands=0,policy_simulations=0,training=0,posthoc=True,accuracy_pass=None,policy_winner=None,
                 experiment_ready=False,active_seconds=time.monotonic()-started,model_sha256=h.m.sha(h.m.MODEL),
                 inputs_sha256=h.m.sha(BUNDLE/'inputs.json.gz'),contract_sha256=h.m.sha(BUNDLE/'contract.json'))
    h.m.write(output/'summary.json',summary);print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    e=s.add_parser('export');e.add_argument('--external',required=True)
    r=s.add_parser('run');r.add_argument('--output',required=True)
    args=p.parse_args()
    export(args.external) if args.action=='export' else run(args.output)
