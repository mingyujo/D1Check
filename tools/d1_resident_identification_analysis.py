"""Registered long-profile identification. Post-load data fit development only."""
import copy
import json
import math
from pathlib import Path
import numpy as np
from tools import d1_joint_model_refinement as j
from tools import d1_energy_collection as old
from tools.d1_energy_thermal import integrate


def arrival_case(folder,m):
    # Read only after the existing arrival validator passed. No provisional validated.json is written.
    folder=Path(folder);origin=old.p.read(folder/'common_boundary.json')['start_ns'];rows=old.p.read(folder/'requests.json')
    events,_=old.progress_prefix((folder/'progress.jsonl').read_bytes())
    baseline=[e['mono_ns'] for e in events if (e.get('phase'),e.get('kind'))==('resident_baseline','phase_start')]
    cooling=[e['mono_ns'] for e in events if (e.get('phase'),e.get('kind'))==('resident_cooling','phase_end')]
    if len(baseline)!=1 or len(cooling)!=1:raise ValueError('arrival phase boundaries')
    if len(rows)!=len(m['requests']) or any(not origin+35e9<=r['dispatch_ns']<r['lane_available_ns']<origin+120e9 for r in rows):raise ValueError('arrival full window')
    th=[json.loads(x) for x in (folder.parent/'thermal.jsonl').read_text(encoding='utf8').splitlines()]
    good=[r for r in th if r.get('AP') not in (None,'') and r['thermal_status']=='0']
    if any(not r['before_ns']<=r['mono_ns']<=r['after_ns'] for r in good):raise ValueError('arrival AP bracket')
    pre=[dict(t=(r['mono_ns']-origin)/1e9,ap=float(r['AP']),lo=(r['before_ns']-origin)/1e9,hi=(r['after_ns']-origin)/1e9) for r in good if baseline[0]<=r['before_ns']<=r['after_ns']<origin+35e9]
    post=[r for r in good if origin+35e9<=r['before_ns']<=r['after_ns']<=cooling[0]]
    end=(cooling[0]-origin)/1e9;q=[(r['mono_ns']-origin)/1e9 for r in post]
    if len(q)<20 or q[0]-35>10 or end-q[-1]>10 or any(not 0<b-a<=10 for a,b in zip(q,q[1:])):raise ValueError('arrival AP coverage')
    segments=j.m.base.states.observed_segments(rows,origin)+[dict(start_s=120.,end_s=end,state='idle')]
    samples=sorted([dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in events if e['kind']=='power_sample'],key=lambda r:r['mono_ns'])
    c=dict(id=m['phase'],role='confirmation',policy=m['identification_profile'],pre=pre,q=q,ap=[float(r['AP']) for r in post],actual=segments,
           last_lane_s=max(r['lane_available_ns']-origin for r in rows)/1e9,power_t=[(s['mono_ns']-origin)/1e9 for s in samples],power_w=[j.m.base.energy.discharge_w(s,1000) for s in samples],common_end_s=120)
    c['pre_w']=j.m.integral(c,-20,30)/50
    return c


def read_case(folder,manifest,plan):
    folder=Path(folder);m=old.p.read(manifest)
    if old.p.digest(folder/'manifest.json')!=old.p.digest(manifest):raise ValueError('executed manifest identity')
    cleanup=old.p.read(folder/'cleanup.json')
    if cleanup['status']!='completed' or any((folder/n).exists() for n in ['sampler_failure.json','session_failure.json']):
        raise ValueError('app failure; preserve original failure/stack')
    events,partial=old.progress_prefix((folder/'progress.jsonl').read_bytes())
    if partial or [x['sequence'] for x in events]!=list(range(len(events))):raise ValueError('journal missing/partial')
    if any(x['session_id']!=m['session_id'] for x in events):raise ValueError('session ownership')
    for kind,count in [('runtime_return',4),('warmup_return',8)]:
        if sum(e['kind']==kind for e in events)!=count:raise ValueError('runtime/warmup denominator')
    eligibility=[e for e in events if e['kind']=='lane_available' and e['phase'].startswith('eligibility_')]
    rows=[e for e in events if e['kind']=='lane_available' and e['phase']=='load']
    if len(eligibility)!=4 or not rows or len(rows)>m['work_call_cap'] or len({r['id'] for r in rows})!=len(rows):raise ValueError('work/quality denominator')
    starts={e['id'] for e in events if e['kind']=='request_start' and e['phase']=='load'}
    if starts!={r['id'] for r in rows}:raise ValueError('unconfirmed request completion')
    for r in rows+eligibility:
        fields=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
        if [r[k] for k in fields]!=sorted(r[k] for k in fields):raise ValueError('lane release order')
        old.quality(old.p.read(plan['references'][r['key']]['path']),old.p.read(folder/(r['id']+'.result.json')))
    begin=next(e for e in events if e['kind']=='identification_common_start')
    end=next(e for e in events if e['kind']=='identification_common_end')
    if end['planned_end_ns']-begin['start_ns']!=m['common_work_seconds']*10**9 or end['end_ns']<end['planned_end_ns']:raise ValueError('fixed common window')
    keys=old.KEYS;offset=0
    for spec in m['blocks']:
        bs=[e for e in events if e['kind']=='block_start' and e.get('block')==spec['id']]
        be=[e for e in events if e['kind']=='block_end' and e.get('block')==spec['id']]
        if len(bs)!=1 or len(be)!=1:raise ValueError('missing registered block')
        bs,be=bs[0],be[0];expected_keys=[keys[i] for i in spec['lane_indices']]
        planned=begin['start_ns']+offset*10**9;planned_end=planned+spec['seconds']*10**9
        if bs['keys']!=expected_keys or bs['target_seconds']!=spec['seconds'] or bs['nominal_offset_ns']!=offset*10**9:
            raise ValueError('block identity/timeline')
        if not planned<=bs['mono_ns']<planned_end or not bs['mono_ns']<be['mono_ns']<=planned_end+30*10**9:
            raise ValueError('block time boundary')
        use=[r for r in rows if r['block']==spec['id']]
        if any(r['key'] not in expected_keys or not bs['mono_ns']<=r['dispatch_ns']<planned_end or r['lane_available_ns']>be['mono_ns'] for r in use):
            raise ValueError('wrong block/lane or late start')
        for key in expected_keys:
            if not 0<sum(r['key']==key for r in use)<=spec['seconds']*4:raise ValueError('per-lane budget/empty state')
        offset+=spec['seconds']
    approval=old.p.read(folder/'start_ap.accepted.json')
    if not math.isfinite(approval['ap_c']) or not approval['read_before_ns']<=approval['read_after_ns']<=begin['start_ns'] or begin['start_ns']-approval['read_before_ns']>3e9:
        raise ValueError('start AP invalid/stale')
    origin=begin['start_ns']-35*10**9
    samples=[e for e in events if e['kind']=='power_sample']
    for e in samples:
        if e.get('sample_period_ms')!=900:raise ValueError('sampling protocol mismatch')
        if e['plugged']!=0 or e['thermal_status']!=0 or not e['interactive'] or e['admission_reason']!='admit':raise ValueError('device environment violation')
        if not e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns']:raise ValueError('snapshot clock')
        e['mono_ns']=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2
    in_common=[e for e in samples if begin['start_ns']<=e['mono_ns']<=end['planned_end_ns']]
    if not in_common or any(set(e.get('resident_keys',[]))!=set(old.KEYS) for e in in_common):raise ValueError('resident composition')
    thermal=[json.loads(line) for line in (folder.parent/'thermal.jsonl').read_text(encoding='utf8').splitlines()]
    if any(x.get('AP') in (None,'') or x['thermal_status']!='0' or x['sampling_uncertainty_ns']>2e9 for x in thermal):raise ValueError('host AP missing/uncertain')
    # Remove exact duplicate clock points only when the value is also identical.
    unique={}
    for r in thermal:
        t=r['mono_ns'];v=float(r['AP'])
        if t in unique and unique[t]['ap']!=v:raise ValueError('duplicate AP clock conflict')
        unique[t]=dict(t=(t-origin)/1e9,ap=v,lo=(r['before_ns']-origin)/1e9,hi=(r['after_ns']-origin)/1e9)
    pre=[r for _,r in sorted(unique.items()) if -30<=r['t'] and r['hi']<35]
    after=[r for _,r in sorted(unique.items()) if r['t']>=35]
    if len(pre)<20 or pre[-1]['t']-pre[0]['t']<55 or len(after)<30:raise ValueError('AP coverage')
    cooling_end=next(e['mono_ns'] for e in events if e['kind']=='phase_end' and e['phase']=='resident_cooling')
    after=[r for r in after if r['hi']<=cooling_end/1e9-origin/1e9]
    if any(b['t']-a['t']>10 for a,b in zip(after,after[1:])):raise ValueError('AP gap')
    ledger=[dict(task=r['key'].rsplit('_',1)[0],backend=r['key'].rsplit('_',1)[1],priority='normal',arrival_ns=r['dispatch_ns']-origin,
                 **{k:r[k]-origin for k in ('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')}) for r in rows]
    state=old.state_intervals(rows,origin,cooling_end)
    seg=[dict(start_s=(s['start_ns']-origin)/1e9,end_s=(s['end_ns']-origin)/1e9,state='idle' if s['state']=='resident_idle' else s['state']) for s in state]
    # old state intervals retain full coverage, including resident idle before first dispatch.
    common_end=(end['planned_end_ns']-origin)/1e9
    if integrate(samples,origin,end['planned_end_ns'],1000)['full_energy_j'] is None:raise ValueError('whole registered energy coverage')
    c=dict(id=m['phase'],role=m['identification_role'],study_phase=m['identification_role'],policy=m['identification_profile'],
           pre=pre,q=[r['t'] for r in after],ap=[r['ap'] for r in after],actual=seg,last_lane_s=max(r['lane_available_ns'] for r in ledger)/1e9,
           power_t=[(r['mono_ns']-origin)/1e9 for r in samples],power_w=[j.m.base.energy.discharge_w(r,1000) for r in samples],common_end_s=common_end)
    c['pre_w']=j.m.integral(c,-20,30)/50
    j.m.base.exposure(seg,0,common_end)
    if m['identification_role']=='development':
        gpu=j.m.base.exposure(seg,35,common_end)[2]
        if gpu<10:raise ValueError('GPU solo measured exposure insufficient; no replacement calls')
    return c,dict(status='eligible_identification_only',condition=m['phase'],phase=m['phase'],profile=m['identification_profile'],work_calls=len(rows),
                  eligibility_calls=4,warmup_calls=8,runtimes=4,common_start_ns=origin,common_end_ns=end['planned_end_ns'],
                  analysis_case=c,accuracy_pass=None,experiment_ready=False)


def energy_fit(cases,original):
    if len(cases)<3 or any(c['role']!='development' for c in cases):raise ValueError('development-only fit')
    x=[];y=[]
    for c in cases:
        intervals=list(range(35,int(c['common_end_s'])-4,5));weight=1/math.sqrt(len(intervals)*len(cases))
        for a in intervals:
            x.append(np.r_[5.,j.m.base.exposure(c['actual'],a,a+5)]*weight)
            y.append((j.m.integral(c,a,a+5)-c['pre_w']*5)*weight)
    x=np.array(x);y=np.array(y);norm=np.linalg.norm(x,axis=0);sv=np.linalg.svd(x/np.maximum(norm,1e-30),compute_uv=False)
    if np.linalg.matrix_rank(x)!=5:raise ValueError('idle/state power not identified')
    solutions=[]
    import itertools
    for n in range(5):
        for active in itertools.combinations(range(1,5),n):
            cols=[0]+list(active);v=np.zeros(5);v[cols]=np.linalg.lstsq(x[:,cols],y,rcond=None)[0]
            if np.all(v[1:]>=0):solutions.append(v)
    v=min(solutions,key=lambda z:float(np.sum((x@z-y)**2)))
    if any(c['pre_w']+v[0]<=0 for c in cases):raise ValueError('nonpositive baseline')
    return dict(idle_bias_w=float(v[0]),increments=dict(zip(j.m.base.STATES,map(float,v[1:]))),scaled_singular_values=sv.tolist())


def fitting(cases,original):
    e=energy_fit(cases,original)
    rows=[dict(study_phase='development',inputs=j.m.case_input(c,c['actual'])['inputs'],observed_ap_c=c['ap']) for c in cases]
    ap,profile=j.m.thermal.fit(rows,original['ap']['parameters'])
    if ap['load_rank']!=2 or ap['numerical_rank']!=3 or ap['beta_boundary']:raise ValueError('AP model unidentified; no confirmation')
    return dict(version='resident-identification-model-v1',energy=e,ap=ap,profile=profile,default=False,accuracy_pass=None,experiment_ready=False)


def assess(c,model,original):
    if c['pre_w']+model['energy']['idle_bias_w']<=0:raise ValueError('nonpositive candidate idle power; no clipping')
    ep=lambda t:c['pre_w']*t+max(0,t-35)*model['energy']['idle_bias_w']+float(j.m.base.exposure(c['actual'],0,t)@np.array([model['energy']['increments'][k] for k in j.m.base.STATES]))
    ap=j.m.thermal.predict(j.m.case_input(c,c['actual']),model['ap'])[0]
    baseap=j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]
    # Long-profile energy and the original 120-second boundary are separate metrics.
    out={}
    for name,pred in [('original',baseap),('candidate',ap)]:
        ef=(lambda t:j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),t)) if name=='original' else ep
        out[name]=dict(**j.m.base.common.score(c['ap'],pred),**j.h.direction(c,pred))
        for label,end in [('common120',120),('registered',c['common_end_s'])]:
            signed=ef(end)-j.m.integral(c,0,end);out[name][label+'_signed_j']=signed;out[name][label+'_absolute_j']=abs(signed)
    return out


def freeze(cases,original):
    if len(cases)!=4 or any(c['role']!='development' for c in cases) or len({c['id'] for c in cases})!=4:raise ValueError('complete four development only')
    folds=[]
    for i,c in enumerate(cases):
        fitted=fitting([x for n,x in enumerate(cases) if n!=i],original)
        folds.append(dict(id=c['id'],profile=c['policy'],score=assess(c,fitted,original)))
    metrics=['common120_absolute_j','registered_absolute_j','mae_c','max_absolute_error_c']
    for profile in ('DEV_A','DEV_B'):
        use=[f['score'] for f in folds if f['profile']==profile]
        if any(np.mean([r['candidate'][k] for r in use])>np.mean([r['original'][k] for r in use])+1e-9 for k in metrics):
            raise ValueError('development predictive gate failed; confirmation unattempted')
    model=fitting(cases,original)
    return dict(version='resident-identification-freeze-v1',development_ids=[c['id'] for c in cases],model=model,folds=folds,
                selection_data='development only',confirmation_fit_forbidden=True,default=False,accuracy_pass=None,experiment_ready=False)
