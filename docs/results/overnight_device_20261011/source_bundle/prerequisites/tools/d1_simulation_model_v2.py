"""Separate empirical simulator v2. Development fit, causal initialization, no device API."""
from __future__ import annotations
import copy
import hashlib
import heapq
import json
import math
import statistics
from pathlib import Path
import numpy as np
from tools import d1_model_refinement as prior
from tools import d1_ap_preparation_memory as memory

VERSION = 'empirical-simulation-model-v2'
STATES = tuple(prior.base.STATES)
PHASES = ('dispatch_to_execution','execution_to_output','output_to_persist','persist_to_worker_release','worker_release_to_lane')
FIELDS = ('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
ROOT = Path(__file__).resolve().parents[1]


def state(label):
    return 'resident_idle' if label in ('idle','resident_idle') else label.replace(':','_')


def validate_segments(segments):
    if not segments:
        raise ValueError('empty schedule')
    cursor = segments[0]['start_s']
    for s in segments:
        if not all(math.isfinite(s[k]) for k in ('start_s','end_s')) or abs(s['start_s']-cursor)>1e-6 or s['end_s']<cursor:
            raise ValueError('incomplete/nonfinite schedule')
        if state(s['state']) not in ('resident_idle',)+STATES:
            raise ValueError('unmeasured state')
        cursor=s['end_s']


def occupancy(rows,start_ns,end_ns):
    cuts=sorted({start_ns,end_ns}|{max(start_ns,min(end_ns,r[k])) for r in rows for k in ('dispatch_ns','lane_available_ns')})
    result=[]
    for a,b in zip(cuts,cuts[1:]):
        members=[]
        for r in rows:
            if r['dispatch_ns']<(a+b)/2<r['lane_available_ns']:
                members.append(r.get('key') or (r.get('task',r.get('task_id'))+'_'+r.get('backend',r.get('selected_backend'))))
        label='+'.join(sorted(members)) if members else 'idle'
        if state(label) not in ('resident_idle',)+STATES:raise ValueError('unmeasured occupied combination')
        result.append(dict(start_s=a/1e9,end_s=b/1e9,state=label))
    return result


def kernel(segments, queries, rate, inputs):
    """Exact exponential convolution over actual occupied intervals; no target values."""
    if not math.isfinite(rate) or rate<=0:
        raise ValueError('invalid decay')
    active=[s for s in segments if inputs.get(state(s['state']),0.)!=0]
    if not active:return np.zeros(len(queries))
    starts=np.array([s['start_s'] for s in active]);ends=np.array([s['end_s'] for s in active]);u=np.array([inputs[state(s['state'])] for s in active])
    values=[]
    for first in range(0,len(queries),64):
        t=np.array(queries[first:first+64],dtype=float)[:,None];b=np.minimum(t,ends)
        values.extend((np.exp(-rate*(t-b))*(-np.expm1(-rate*np.maximum(0,b-starts)))/rate@u).tolist())
    return np.array(values)


def predictive_schedule(c):
    future=copy.deepcopy(c['actual']);history=copy.deepcopy(c.get('history',[]))
    validate_segments(future)
    if history:
        validate_segments(history)
        if history[-1]['end_s']>future[0]['start_s']+1e-6 or history[-1]['end_s']>35:
            raise ValueError('future/overlapping history')
    return history+future


def ap_prediction(c, model):
    """Fit local R/H from pre-issue AP only, after removing known history forcing."""
    pre=c['pre'];q=c['q'];ap=model['ap'];theta=np.array(ap['coefficients'],dtype=float)
    if len(pre)<8 or len(theta)!=5 or not np.all(np.isfinite(theta)) or np.any(theta<0):
        raise ValueError('invalid AP inputs/coefficients')
    if any(not r['lo']<=r['t']<=r['hi']<35 or not math.isfinite(r['ap']) for r in pre):
        raise ValueError('future or invalid initial AP')
    times=np.array([r['t'] for r in pre]);observed=np.array([r['ap'] for r in pre]);queries=np.array(q,dtype=float)
    if np.any(np.diff(times)<=0) or times[-1]-times[0]<20 or np.any(np.diff(times)>10) or not len(q) or q[0]<35 or not np.all(np.isfinite(queries)) or np.any(np.diff(queries)<=0):
        raise ValueError('initial/target time coverage')
    ss=predictive_schedule(c)
    if queries[-1]>ss[-1]['end_s']+1e-6:
        raise ValueError('query outside covered schedule')
    beta,tau=ap['beta'],ap['slow_tau_s'];energy=ap['slow_input_w']
    forcing=lambda ts: kernel(ss,ts,beta,dict(zip(STATES,theta[:4])))+theta[4]*kernel(ss,ts,1/tau,energy)
    corrected=observed-forcing(times)
    dt=times-times[0];eb=np.exp(-beta*dt)
    X=np.column_stack((1-eb,[memory.convolution(beta,30.,float(t)) for t in dt]))
    norms=np.linalg.norm(X,axis=0)
    if min(norms)<=0 or np.linalg.matrix_rank(X)<2:
        raise ValueError('unidentified R/H')
    reference,h0=np.linalg.lstsq(X/norms,corrected-corrected[0]*eb,rcond=None)[0]/norms
    anchor=times[-1];h=h0*math.exp(-(anchor-times[0])/30.)
    elapsed=queries-anchor
    values=reference+(corrected[-1]-reference)*np.exp(-beta*elapsed)+h*np.array([memory.convolution(beta,30.,float(t)) for t in elapsed])+forcing(queries)
    if not np.all(np.isfinite(values)):
        raise ValueError('nonfinite AP')
    return values.tolist(),dict(anchor_s=float(anchor),input_end_s=float(max(r['hi'] for r in pre)),reference_c=float(reference),h_last=float(h),
        history_intervals=len(c.get('history',[])),pre_condition=float(np.linalg.cond(X/norms)),
        reference_is_ambient=False,slow_initial_zero_before_recorded_history_is_assumption=True)


def nnls(X,y):
    return prior.base.nnls(X,y)


def fit(cases, original):
    if len(cases)<3 or any(c['role']!='development' for c in cases) or len({c['id'] for c in cases})!=len(cases):
        raise ValueError('unique development sessions only; confirmation fit forbidden')
    energy_x=[];energy_y=[];ap_x=[];ap_y=[]
    empty=dict(ap=dict(beta=original['ap']['beta'],slow_tau_s=1920.,slow_input_w=copy.deepcopy(original['energy_increment_w']),coefficients=[0.]*5))
    for c in cases:
        validate_segments(c['actual'])
        windows=list(range(35,int(c.get('common_end_s',120.))-4,5));w=1/math.sqrt(len(windows)*len(cases))
        for t in windows:
            energy_x.append(prior.base.exposure(c['actual'],t,t+5)*w)
            energy_y.append((prior.integral(c,t,t+5)-c['pre_w']*5)*w)
        base=np.array(ap_prediction(c,empty)[0]);columns=[]
        for i in range(5):
            unit=copy.deepcopy(empty);unit['ap']['coefficients'][i]=1.
            columns.append(np.array(ap_prediction(c,unit)[0])-base)
        weight=1/math.sqrt(len(base)*len(cases));ap_x.append(np.column_stack(columns)*weight);ap_y.append((np.array(c['ap'])-base)*weight)
    X=np.array(energy_x);Y=np.array(energy_y);A=np.vstack(ap_x);B=np.concatenate(ap_y)
    if np.linalg.matrix_rank(X)!=4 or np.linalg.matrix_rank(A)!=5:
        raise ValueError('state inputs not numerically identified')
    powers=nnls(X,Y);thermal=nnls(A,B)
    return dict(version=VERSION,energy_increment_w=dict(zip(STATES,powers.tolist())),ap=dict(empty['ap'],coefficients=thermal.tolist()),
        development_ids=[c['id'] for c in cases],energy_rank=4,ap_rank=5,
        ap_scaled_condition=float(np.linalg.cond(A/np.linalg.norm(A,axis=0))),
        slow_tau_identified=False,thermal_service_feedback=None,stochastic_failure_probability=None,
        default=False,strict_support=False,experiment_ready=False,accuracy_pass=None,
        evidence='development fit; empirical fixed decay family, not physically identified thermal parameters')


def energy_at(c, model, t, segments=None):
    if not math.isfinite(c['pre_w']) or c['pre_w']<=0:
        raise ValueError('invalid prior power')
    ss=c['actual'] if segments is None else segments
    return c['pre_w']*t+float(prior.base.exposure(ss,0,t)@np.array([model['energy_increment_w'][k] for k in STATES]))


def assess(c, model, original):
    predicted,initial=ap_prediction(c,model)
    original_ap=prior.thermal.predict(prior.case_input(c,c['actual']),original['ap'])[0]
    scores={}
    for name,values in [('v2',predicted),('original',original_ap)]:
        row=prior.base.common.score(c['ap'],values)
        for label,end in [('120s',120),('registered',c.get('common_end_s',120.))]:
            pred=energy_at(c,model,end) if name=='v2' else c['pre_w']*end+float(prior.base.exposure(c['actual'],0,end)@np.array([original['energy_increment_w'][k] for k in STATES]))
            row[label+'_energy_signed_j']=pred-prior.integral(c,0,end)
        scores[name]=row
    return dict(scores=scores,initial=initial,AP_query_s=c['q'],observed_AP_c=c['ap'],predicted_AP_c=predicted,
        scope='actual schedule conditional; future AP/power are targets only',accuracy_pass=None)


def archive_service():
    file=ROOT/'docs/results/recovery_service_01/run_v1/inputs.json'
    data=json.loads(file.read_text(encoding='utf8'));buckets={}
    for r in data['requests']:
        if r['stage']!='target' or r['role']!='development':continue
        key=r['task']+'_'+r['backend'];context='PAR' if r['policy']=='PAR' else 'CPU'
        buckets.setdefault(context+'/'+key,{}).setdefault(r['session'],[]).append([r[k]*1e6 for k in PHASES])
    if set(buckets)!={'CPU/classification_CPU','CPU/detection_CPU','PAR/classification_GPU','PAR/detection_CPU'}:
        raise ValueError('unmeasured service cells')
    return dict(source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),buckets=buckets,
        selection='whole development session per context; ordered intact 5phase vectors; not independent request draws',
        overhead_ns=1_563_000,overhead_evidence='rounded archived existing-rule D->A median; not new controller/PPO cost')


def simulate(tickets, service, policy='CPU', seed=1, mode='mean', horizon_ns=120_000_000_000):
    """Five-phase nonpreemptive queue. All future arrivals remain inside event engine."""
    if policy not in ('CPU','PAR','EFT') or mode not in ('mean','session_replay'):
        raise ValueError('policy/mode unsupported')
    if len({r['id'] for r in tickets})!=len(tickets) or not tickets:
        raise ValueError('request identity')
    for r in tickets:
        if (r['task'],r['priority']) not in (('classification','urgent'),('detection','normal')) or not 35e9<=r['arrival_ns']<horizon_ns or r['deadline_offset_ns']<=0:
            raise ValueError('unsupported request or deadline')
    queue=[];events=[];sequence=0;lanes={'CPU':None,'GPU':None};pending=None;now=0;ledger={r['id']:dict(r,status='not_arrived') for r in tickets};counts={}
    def push(t,kind,payload):
        nonlocal sequence
        sequence+=1;heapq.heappush(events,(t,sequence,kind,payload))
    for r in sorted(tickets,key=lambda r:(r['arrival_ns'],r['ordinal'])):push(r['arrival_ns'],'arrival',r)
    def durations(q,b,draw=False):
        context='PAR' if b=='GPU' or (b=='CPU' and lanes['GPU'] is not None) else 'CPU';key=context+'/'+q['task']+'_'+b
        streams=service['buckets'][key];ordered=sorted(streams)
        if mode=='mean' or not draw:
            return [statistics.mean([statistics.mean(v[i] for v in stream) for stream in streams.values()]) for i in range(5)]
        index=int.from_bytes(hashlib.sha256((str(seed)+'/'+key).encode()).digest()[:4],'big')%len(ordered)
        stream=streams[ordered[index]];n=counts.get(key,0);counts[key]=n+1
        return stream[n%len(stream)]
    while events and events[0][0]<=horizon_ns:
        now=events[0][0]
        while events and events[0][0]==now:
            _,_,kind,payload=heapq.heappop(events)
            if kind=='arrival':queue.append(payload);ledger[payload['id']]['status']='queued'
            elif kind=='dispatch':
                q,b=payload;row=ledger[q['id']];pending=None;row.update(dispatch_ns=now,backend=b,status='executing');d=durations(q,b,True)
                end=now
                for stage,length in enumerate(d):end+=round(length);push(end,'phase',(q['id'],b,stage))
            else:
                rid,b,stage=payload;row=ledger[rid];row[FIELDS[stage]]=now
                if stage==(1 if row['priority']=='urgent' else 2):row['response_ns']=now-row['arrival_ns']
                if stage==4:row['status']='succeeded';lanes[b]=None
        if pending is not None or not queue:continue
        ordered=sorted(queue,key=lambda r:(r['priority']!='urgent',r['arrival_ns']+r['deadline_offset_ns'],r['ordinal']))
        options=[]
        for q in ordered:
            bs=('CPU',) if policy=='CPU' or q['task']=='detection' else ('GPU',) if policy=='PAR' else ('CPU','GPU')
            for b in bs:
                if lanes[b] is not None or (policy=='CPU' and any(x is not None for x in lanes.values())):continue
                members=[q['task']+'_'+b]+[ledger[rid]['task']+'_'+peer for peer,rid in lanes.items() if rid is not None]
                if '+'.join(sorted(members)) not in STATES:continue
                d=durations(q,b);reply=sum(d[:2 if q['priority']=='urgent' else 3])
                options.append((ordered.index(q),reply,b!='CPU',q,b))
            if options:break
        if options:
            _,_,_,q,b=min(options,key=lambda x:x[:3]);queue.remove(q);lanes[b]=q['id'];pending=q['id']
            ledger[q['id']].update(decision_start_ns=now,status='reserved');push(now+service['overhead_ns'],'dispatch',(q,b))
    rows=list(ledger.values())
    for r in rows:
        if r['status']!='succeeded':r['status']='unfinished' if r['status']!='not_arrived' else 'not_arrived'
    metrics={}
    for p in ('urgent','normal'):
        group=[r for r in rows if r['priority']==p];responded=sorted(r['response_ns']/1e6 for r in group if r['status']=='succeeded' and 'response_ns' in r)
        timely=sum(r['status']=='succeeded' and r.get('response_ns',math.inf)<=r['deadline_offset_ns'] for r in group)
        metrics[p]=dict(planned=len(group),timely=timely,service_success_rate=timely/len(group) if group else None,
            response_P95_ms=responded[math.ceil(.95*len(responded))-1] if responded else None,completed=sum(r['status']=='succeeded' for r in group))
    return dict(version=VERSION,ledger=rows,metrics=metrics,policy=policy,mode=mode,seed=seed,
        thermal_service_feedback=None,stochastic_failures_supported=False,experiment_ready=False,
        service_transfer='context-conditioned durations; changing overlap within invocation is not a causal fitted rate model')
