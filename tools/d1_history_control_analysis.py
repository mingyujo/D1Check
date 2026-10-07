"""Registered-history readout. Raw evidence is read-only; confirmation never fits."""
import copy
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_model_refinement as m
from tools import d1_arrival_energy_collection as c
from tools import d1_energy_thermal as energy
from tools import d1_arrival_recorded_replay_analysis as states

VERSION='registered-history-control-v1'


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]


def power_coverage(power,origin,target,end):
    # Registered J comparisons end at target common+120s; AP cooling uses its own observations.
    common=energy.integrate(power,origin,target+120_000_000_000,1000)
    if common['full_energy_j'] is None:raise ValueError('power gap in registered common/history window')
    cooling=energy.integrate(power,target+120_000_000_000,end,1000)
    return dict(registered_history_common=common,cooling=cooling,
                cooling_full_energy_available=cooling['full_energy_j'] is not None)


def request_gate(rows, expected, origin, policy, plan, artifacts):
    if len(rows)!=len(expected) or {r['request_id'] for r in rows}!={r['request_id'] for r in expected}:
        raise ValueError('history request denominator')
    spec={r['request_id']:r for r in expected}
    for r in rows:
        q=spec[r['request_id']]
        times=[r.get(k) for k in ('scheduled_arrival_ns','actual_arrival_ns','queue_entry_ns','dispatch_ns',
            'execution_start_ns','host_inference_start_ns','host_inference_return_ns','output_ready_ns',
            'persist_complete_ns','worker_release_ns','lane_available_ns')]
        if any(x is None for x in times) or times!=sorted(times) or r['terminal_status']!='succeeded':
            raise ValueError('history unfinished/boundary')
        if times[0]!=origin+q['offset_ms']*1_000_000 or times[-1]>=origin+120_000_000_000:
            raise ValueError('history completion/window')
        backend='CPU' if policy=='CPU_URGENT_ONLINE_V1' or q['task_id']=='detection' else 'GPU'
        if r['task_id']!=q['task_id'] or r['selected_backend']!=backend:raise ValueError('history assignment')
        key=q['task_id']+'_'+backend
        c.old.quality(m.read(plan['references'][key]['path']),m.read(artifacts/(r['request_id']+'.result.json')))
    for backend in ('CPU','GPU'):
        use=sorted([r for r in rows if r['selected_backend']==backend],key=lambda r:r['dispatch_ns'])
        if any(a['lane_available_ns']>b['dispatch_ns'] for a,b in zip(use,use[1:])):raise ValueError('lane overlap')


def validate(folder,manifest,plan):
    folder=Path(folder);art=folder/'artifacts'
    cleanup=m.read(art/'cleanup.json')
    if cleanup['status']!='completed':
        original=m.read(art/'session_failure.json') if (art/'session_failure.json').exists() else cleanup
        raise RuntimeError('history app failure: '+str(original))
    if m.read(art/'manifest.json')!=manifest:raise ValueError('manifest drift')
    h=m.read(art/'history_boundary.json');a=m.read(art/'conditioning_common_boundary.json');b=m.read(art/'common_boundary.json')
    if h['version']!=VERSION or h['runtime_recreated'] or h['additional_warmup']!=0:raise ValueError('history ownership')
    if a['start_ns']!=h['conditioning_start_ns'] or b['start_ns']!=h['target_start_ns']:raise ValueError('two origins')
    if not a['end_ns']<=h['recovery_start_ns'] or h['target_baseline_start_ns']-h['recovery_start_ns']<manifest['history_recovery_seconds']*1e9 or b['start_ns']-h['target_baseline_start_ns']<30e9:
        raise ValueError('history fixed pause/baseline')
    approval=m.read(art/'start_ap.accepted.json')
    if approval['gate_mode']!='numeric-ap-observe-v2' or approval['common_start_ns']!=a['start_ns'] or not math.isfinite(float(approval['ap_c'])) or not approval['read_before_ns']<=approval['read_after_ns']<=a['start_ns'] or a['start_ns']-approval['read_before_ns']>3e9:
        raise ValueError('initial numeric AP gate')
    total=0
    for prefix,boundary,expected,policy in [('',b,manifest['requests'],manifest['policy']),('conditioning_',a,manifest['conditioning_requests'],'CPU_URGENT_ONLINE_V1')]:
        rows=m.read(art/(prefix+'requests.json'))
        if boundary['planned_end_ns']-boundary['start_ns']!=120e9 or boundary['end_ns']<boundary['planned_end_ns'] or boundary['planned']!=len(expected) or len(boundary['rows'])!=len(expected):raise ValueError('history common boundary')
        request_gate(rows,expected,boundary['start_ns'],policy,plan,art);total+=len(rows)
    events,partial=c.old.progress_prefix((art/'progress.jsonl').read_bytes())
    if partial or any(sum(e.get('kind')==k for e in events)!=n for k,n in [('runtime_start',4),('runtime_return',4),('warmup_start',8),('warmup_return',8),('request_start',total),('host_inference_return',total),('lane_available',total)]):raise ValueError('history consumption count')
    if m.read(art/'summary.json')['terminal']!=len(manifest['requests']):raise ValueError('target summary')
    case=load_case(folder,manifest)
    # Validate the same initial-state and time-coverage gates that will be used for prediction.
    basis(case,m.read(m.MODEL))
    return dict(status='eligible_descriptive_only',phase=manifest['phase'],policy=manifest['policy'],
        scenario=manifest['scenario'],requests=len(manifest['requests']),conditioning_requests=96,warmup=8,runtimes=4,
        common_start_ns=b['start_ns'],common_end_ns=b['end_ns'],experiment_ready=False)


def load_case(folder,manifest):
    folder=Path(folder);art=folder/'artifacts';h=m.read(art/'history_boundary.json')
    origin=h['conditioning_start_ns'];target=h['target_start_ns'];ev=lines(art/'progress.jsonl')
    start=[e['mono_ns'] for e in ev if e.get('kind')=='phase_start' and e.get('phase')=='resident_baseline']
    end=[e['mono_ns'] for e in ev if e.get('kind')=='phase_end' and e.get('phase')=='resident_cooling']
    if len(start)!=1 or len(end)!=1:raise ValueError('history phase markers')
    th=lines(folder/'thermal.jsonl')
    if any(r['thermal_status']!='0' for r in th):raise ValueError('thermal gate')
    good=[r for r in th if r.get('AP') not in ('',None)]
    full=[r for r in good if start[0]<=r['before_ns']<=r['mono_ns']<=r['after_ns']<=end[0]]
    if any(not math.isfinite(float(r['AP'])) for r in full) or len(full)<2 or any(not 0<b['mono_ns']-a['mono_ns']<=10e9 for a,b in zip(full,full[1:])):
        raise ValueError('registered history AP coverage')
    def preload(s,o,cut):
        return [dict(t=(r['mono_ns']-o)/1e9,lo=(r['before_ns']-o)/1e9,hi=(r['after_ns']-o)/1e9,ap=float(r['AP'])) for r in good if s<=r['before_ns']<=r['mono_ns']<=r['after_ns']<cut]
    pre=preload(start[0],origin,origin+35_000_000_000)
    localpre=preload(h['target_baseline_start_ns'],target,target+35_000_000_000)
    post=[r for r in good if target+35e9<=r['before_ns']<=r['mono_ns']<=r['after_ns']<=end[0]]
    q=[(r['mono_ns']-origin)/1e9 for r in post];offset=(target-origin)/1e9
    if len(q)<20 or q[0]-offset-35>10 or (end[0]-origin)/1e9-q[-1]>10 or any(not 0<b-a<=10 for a,b in zip(q,q[1:])):raise ValueError('history AP gap')
    rows=m.read(art/'conditioning_requests.json');targetrows=m.read(art/'requests.json')
    seg=states.observed_segments(rows,origin)
    seg.append(dict(start_s=120.,end_s=offset,state='idle'))
    local=states.observed_segments(targetrows,target)
    seg.extend(dict(start_s=s['start_s']+offset,end_s=s['end_s']+offset,state=s['state']) for s in local)
    end_s=(end[0]-origin)/1e9
    seg.append(dict(start_s=offset+120,end_s=end_s,state='idle'))
    local.append(dict(start_s=120,end_s=end_s-offset,state='idle'))
    power=[]
    for e in ev:
        if e.get('kind')!='power_sample':continue
        if not e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns'] or e['sensor_read_end_ns']-e['snapshot_start_ns']>2e9:raise ValueError('sensor clock')
        if set(e.get('resident_keys',[]))!=set(c.old.KEYS) and origin<=e['mono_ns']<=end[0]:raise ValueError('resident changed')
        power.append(dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2))
    def integrate(a,b):
        v=energy.integrate(power,a,b,1000)['full_energy_j']
        if v is None:raise ValueError('power gap')
        return v
    # Coverage includes conditioning and recovery; no hidden gap is zero-filled.
    coverage=power_coverage(power,origin,target,end[0])
    registered=[r for r in full if r['before_ns']>=origin+35e9]
    return dict(id=manifest['session_id'],role=manifest['history_role'],gap=manifest['history_recovery_seconds'],
        target_policy=manifest['history_target_policy'],inputs=dict(preload=pre,query_s=q,segments=seg),
        fit_inputs=dict(preload=pre,query_s=[(r['mono_ns']-origin)/1e9 for r in registered],segments=seg),
        fit_observed_ap_c=[float(r['AP']) for r in registered],
        local_inputs=dict(preload=localpre,query_s=[t-offset for t in q],segments=local),
        observed_ap_c=[float(r['AP']) for r in post],target_offset_s=offset,
        observed_j=integrate(target,target+120_000_000_000),pre_w=integrate(target-20_000_000_000,target+30_000_000_000)/50,
        last_lane_s=max([35.]+[(r['lane_available_ns']-target)/1e9 for r in targetrows]),
        power_t=[(r['mono_ns']-target)/1e9 for r in power],power_w=[energy.discharge_w(r,1000) for r in power],
        power_coverage=coverage,source_sha256={x.name:m.sha(x) for x in [art/'progress.jsonl',art/'history_boundary.json',folder/'thermal.jsonl',art/'requests.json',art/'conditioning_requests.json']})


def basis(case,frozen):
    # Existing gate assumes predictions begin >=35, and permits long contiguous schedules.
    allowed={'resident_idle',*frozen['energy_increment_w']}
    if any(states.state_key(s['state']) not in allowed for s in case['inputs']['segments']):
        raise ValueError('unsupported state for registered-history campaign')
    a,x,init=m.thermal.basis(case,frozen['ap']['parameters'],frozen['ap']['beta'])
    if init['scaled_condition']>1e8:raise ValueError('numerically unstable initial state')
    return a+frozen['ap']['k']*x[:,0],x[:,1],init


def fit(cases,frozen):
    if not cases or any(x['role']!='development' for x in cases):raise ValueError('development only')
    xx=[];yy=[]
    for case in cases:
        training=dict(case,inputs=case.get('fit_inputs',case['inputs']))
        targets=case.get('fit_observed_ap_c',case['observed_ap_c'])
        a,x,_=basis(training,frozen);w=1/math.sqrt(len(x)*len(cases))
        if len(targets)!=len(x) or not np.isfinite(targets).all():raise ValueError('development target invalid')
        xx.extend(x*w);yy.extend((np.array(targets)-a)*w)
    x=np.array(xx);y=np.array(yy);info=float(x@x)
    if info<=1e-12:raise ValueError('g unidentified')
    return dict(g=max(0.,float(x@y/info)),unconstrained_g=float(x@y/info),information=info)


def evaluate(case,frozen,candidate):
    a,x,init=basis(case,frozen);pred=a+candidate['g']*x
    baseline,_=m.thermal.predict(dict(inputs=case['local_inputs']),frozen['ap'])
    obs=case['observed_ap_c'];q=case['local_inputs']['query_s']
    r=dict(id=case['id'],gap=case['gap'],target_policy=case['target_policy'],
        frozen=m.base.common.score(obs,baseline),candidate=m.base.common.score(obs,pred.tolist()),
        candidate_initial=init,future_observed_inputs=False)
    for name,values in [('frozen',baseline),('candidate',pred)]:
        # Both deltas use the first common evaluation sample, not an invented t=0 observation.
        r[name]['delta_mae_c']=float(np.mean(np.abs((np.array(values)-values[0])-(np.array(obs)-obs[0]))))
        for label,left,right in [('load',35,case['last_lane_s']),('cooling',case['last_lane_s'],q[-1])]:
            ids=[i for i,t in enumerate(q) if left<=t<=right]
            if len(ids)<2:r[name][label+'_opposite']=None;continue
            d=obs[ids[-1]]-obs[ids[0]];pd=values[ids[-1]]-values[ids[0]]
            r[name][label+'_opposite']=bool(abs(d)>.100000001 and d*pd<0)
            r[name][label+'_mae_c']=float(np.mean(np.abs(np.array(values)[ids]-np.array(obs)[ids])))
    fake=dict(pre_w=case['pre_w'],power_t=case['power_t'],power_w=case['power_w'])
    seg=case['local_inputs']['segments'];predj=m.energy_prediction(fake,seg,frozen,dict(name='FROZEN'),120)
    r.update(observed_j=case['observed_j'],predicted_j=predj,signed_j=predj-case['observed_j'],
        absolute_j=abs(predj-case['observed_j']),
        relative_j=(predj-case['observed_j'])/case['observed_j'])
    for name,left,right in [('pre',0,35),('load',35,case['last_lane_s']),('post',case['last_lane_s'],120)]:
        r[name+'_signed_j']=m.energy_prediction(fake,seg,frozen,dict(name='FROZEN'),right)-m.energy_prediction(fake,seg,frozen,dict(name='FROZEN'),left)-m.integral(fake,left,right)
    r['paths']=dict(q=q,observed=obs,frozen=baseline,candidate=pred.tolist())
    return r


def develop(cases,frozen):
    expected={(g,p) for g in (30,180) for p in ('C0','CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1')}
    if len(cases)!=6 or {(c['gap'],c['target_policy']) for c in cases}!=expected or len({c['id'] for c in cases})!=6:raise ValueError('six development cells')
    fitted=fit(cases,frozen);folds=[];eligible=fitted['g']>0
    for gap in (30,180):
        local=fit([c for c in cases if c['gap']!=gap],frozen)
        rows=[evaluate(c,frozen,local) for c in cases if c['gap']==gap]
        # No accuracy PASS threshold. Prespecified nonworsening selection on each history block.
        accepted=local['g']>0 and np.mean([r['candidate']['mae_c'] for r in rows])<=np.mean([r['frozen']['mae_c'] for r in rows])+1e-12 and not any(r['candidate'].get(k) is True for r in rows for k in ('load_opposite','cooling_opposite'))
        folds.append(dict(held_out_gap=gap,fit=local,eligible=bool(accepted),rows=rows));eligible=eligible and accepted
    return dict(status='ready_to_freeze' if eligible else 'development_gate_stop',candidate=fitted,folds=folds,
        development_ids=[c['id'] for c in cases],frozen_sha256=m.MODEL_SHA,accuracy_pass=None,experiment_ready=False)
