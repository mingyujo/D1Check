"""Opt-in per-request PC exploration using frozen measured J/AP coefficients.

The common service profile is a declared transfer assumption, not a newly
validated profile. No device APIs, fitting, future arrivals or measured feedback.
"""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import html
import json
import math
import statistics
import time
from pathlib import Path

from tools import d1_online_policy_model as model
from tools import d1_ap_preparation_memory as memory

VERSION = 'empirical-request-exploration-v1'
POLICIES = ('CPU_REFERENCE', 'SPLIT_SERIAL_REFERENCE', 'SPLIT_REFERENCE', 'EFT_REFERENCE', 'ENERGY_AP_REQUEST_V1')
RL_POLICY = 'ENERGY_AP_MC_RL_V1'
PPO_POLICY = 'ENERGY_AP_PPO_LAGRANGE_V1'
ALTERNATIVE_POLICIES = ('ECO_EDF_V1', 'LLF_EFT_V1', 'RESERVED_BACKFILL_V1', 'PARETO_MPC_V1', 'THERMAL_MPC_V1')
CONDITION_POLICIES = ('TOKEN_EFT_V1', 'TOKEN_CPU_V1', 'JIT_CPU_V1', 'PAIR_COALESCE_V1')
INDUSTRIAL_POLICIES = ('ATC_QUEUED_GUARD_V1', 'CPU_BOTTLENECK_GUARD_V1', 'INDUSTRIAL_OFFLINE_REPLAY_V1')
CELLS = ('classification_CPU_urgent', 'classification_GPU_urgent', 'detection_CPU_normal')
STATES = set(model.STATES) | {'resident_idle'}
MODEL_SHA = '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
INITIAL_SHA = '42f603120e0f3db18243ef9f3053179039dc6138ce31f37df2c91ac2bf45d18d'
END = 120.
AP_END = 180.
WAIT_STEP = .25
WAIT_LIMIT = 2.
ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/online_policy_study_01/overnight_sustained_run01'
CONTRACT = ROOT / 'docs/results/empirical_request_policy_01/contract.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def profile(frozen, scenario='mean'):
    """Equal context weights; extrema keep whole five-phase context vectors intact."""
    if scenario not in ('mean', 'short_context', 'long_context'):
        raise ValueError('unknown service scenario')
    cells = {}
    for key in CELLS:
        rows = [x['phase_means_ns'][key] for x in frozen['service'].values() if key in x['phase_means_ns']]
        if not rows or any(len(r)!=5 or any(not math.isfinite(v) or v<0 for v in r) for r in rows):
            raise ValueError('missing/invalid measured service')
        cells[key] = ([statistics.mean(col) for col in zip(*rows)] if scenario=='mean'
                      else (min if scenario=='short_context' else max)(rows, key=sum))
    return cells


def key(q, backend):
    return f"{q['task']}_{backend}_{q['priority']}"


def backends(q):
    if (q['task'], q['priority']) == ('classification', 'urgent'): return ('CPU', 'GPU')
    if (q['task'], q['priority']) == ('detection', 'normal'): return ('CPU',)
    raise ValueError('unsupported task/priority; no substituted cost')


def validate_engine(config, vectors, requests, policy, settings, provider):
    if (policy not in (*POLICIES, RL_POLICY, PPO_POLICY, *ALTERNATIVE_POLICIES, *CONDITION_POLICIES, *INDUSTRIAL_POLICIES) or settings['mode']!='explore' or getattr(provider,'protocol',None)!=VERSION
            or not callable(provider) or not callable(getattr(provider,'observe',None))
            or provider.policy != policy or set(config['cells'])!=set(CELLS)
            or set(vectors['cells'])!=set(CELLS)):
        raise ValueError('empirical opt-in contract')
    if any(settings[k]!=1 for k in ('interference','predicted_interference','estimate_factor',
                                   'load_prepare_factor','load_callback_factor')):
        raise ValueError('no invented interference or thermal slowdown')
    if any(settings[k]!=0 for k in ('decision_ns','record_ns','dispatch_ns')):
        raise ValueError('PC zero incremental controller overhead assumption required')
    for q in requests:
        backends(q)
        if not 35e9<=q['arrival_ns']<120e9 or q['deadline_offset_ns']!=(1.5e9 if q['priority']=='urgent' else 6e9):
            raise ValueError('arrival/deadline boundary')
    for cell in vectors['cells'].values():
        if len(cell)!=4 or any(len(r['durations_ns'])!=5 or any(not math.isfinite(v) or v<0 for v in r['durations_ns']) for r in cell):
            raise ValueError('invalid realization vector')


def state(members):
    label = '+'.join(sorted(members)) if members else 'resident_idle'
    if label not in STATES: raise ValueError('unsupported joint state: '+label)
    return label


def segments(jobs, start, end):
    cuts = sorted({start,end} | {max(start,min(end,j[k])) for j in jobs for k in ('start','end')})
    result=[]
    for a,b in zip(cuts,cuts[1:]):
        if b<=a: continue
        label=state([j['state'] for j in jobs if j['start']<(a+b)/2<j['end']])
        result.append(dict(start_s=a,end_s=b,state='idle' if label=='resident_idle' else label))
    return result


def thermal_step(t, h, u, reference, ap, dt):
    beta=ap['beta']; target=ap['g']*u
    eb=math.exp(-beta*dt); eh=math.exp(-dt/30.)
    return (reference+(t-reference)*eb+(ap['k']*u+target)*(1-eb)/beta+
            (h-target)*memory.convolution(beta,30.,dt), target+(h-target)*eh)


class Controller:
    protocol = VERSION
    def __init__(self, frozen, initial, estimates, policy):
        self.frozen=frozen; self.estimates=copy.deepcopy(estimates); self.policy=policy
        self.initial=copy.deepcopy(initial)
        ap=frozen['ap']; self.init=memory.initialize(initial['preload'],ap['beta'],30.)
        if not 0<=self.init['anchor_s']<35 or any(r['hi']>=35 for r in initial['preload']):
            raise ValueError('preload must precede first arrival')
        self.t=self.init['anchor_ap_c']; self.h=self.init['h_last_c_per_s']
        self.now=0.; self.label='resident_idle'; self.history=[]

    def observe(self, now_ns, lanes):
        now=now_ns/1e9
        if now<self.now-1e-8: raise ValueError('time reversal')
        if now>self.now:
            self.history.append(dict(start_s=self.now,end_s=now,state='idle' if self.label=='resident_idle' else self.label))
            start=max(self.now,self.init['anchor_s'])
            if now>start:
                slopes=self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
                self.t,self.h=thermal_step(self.t,self.h,slopes[self.label]-slopes['resident_idle'],
                    self.init['reference_c'],self.frozen['ap'],now-start)
        self.now=now
        self.label=state([r['request']['task']+'_'+b for b,r in lanes.items() if r['request'] is not None])

    def active_jobs(self, lanes, now):
        jobs=[]
        for b,lane in lanes.items():
            if lane['request'] is None: continue
            q=lane['request']; d=self.estimates[key(q,b)]; dispatch=lane['dispatch']/1e9
            end=dispatch+sum(d)/1e9
            if end<=now+1e-9: return None  # unknown overrun; wait for actual event, not zero residual
            response=dispatch+sum(d[:2 if q['priority']=='urgent' else 3])/1e9
            # Already observed output/persistence cannot be treated as a future miss.
            ready=lane['phase'] in (('OUTPUT_READY','PERSISTED','WORKER_RELEASED') if q['priority']=='urgent' else ('PERSISTED','WORKER_RELEASED'))
            jobs.append(dict(id=q['id'],state=q['task']+'_'+b,backend=b,start=now,end=end,
                response=max(now,response),deadline=q['arrival_ns']/1e9+q['deadline_offset_ns']/1e9,
                already_responded=ready))
        return jobs

    def place(self, q, b, earliest, jobs):
        d=self.estimates[key(q,b)]; length=sum(d)/1e9; start=earliest; label=q['task']+'_'+b
        # Preserve lane ownership through lane_available, including persistence/callbacks.
        while True:
            conflicts=[j for j in jobs if start<j['end']-1e-9 and start+length>j['start']+1e-9
                       and (j['backend']==b or '+'.join(sorted((label,j['state']))) not in STATES)]
            if not conflicts: break
            start=max(j['end'] for j in conflicts)
        return dict(id=q['id'],state=label,backend=b,start=start,end=start+length,
            response=start+sum(d[:2 if q['priority']=='urgent' else 3])/1e9,
            deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9,already_responded=False)

    def rollout(self, queue, active, b, delay, now):
        jobs=copy.deepcopy(active); first=self.place(queue[0],b,now+delay,jobs); jobs.append(first)
        for q in queue[1:]:
            jobs.append(min((self.place(q,x,first['start'],jobs) for x in backends(q)),key=lambda j:(j['response'],j['backend']!='CPU')))
        return jobs,first

    def score(self, jobs, now):
        if max(j['end'] for j in jobs)>END+1e-9: return None
        ss=segments(jobs,now,AP_END); ap=self.frozen['ap']; slopes=ap['parameters']['ap_slope_at_30_c_per_s']
        t,h=self.t,self.h; peak=t; watts=self.initial['preload_power_w']; joules=watts*(END-now)
        for s in ss:
            label='resident_idle' if s['state']=='idle' else s['state']; a,b=s['start_s'],s['end_s']
            joules+=max(0,min(END,b)-a)*self.frozen['energy_increment_w'].get(label,0.)
            u=slopes[label]-slopes['resident_idle']
            # Declared 1 s grid plus transition boundaries; not a continuous peak guarantee.
            for q in sorted({b} | {float(x) for x in range(math.ceil(a),math.floor(b)+1) if x>a}):
                peak=max(peak,thermal_step(t,h,u,self.init['reference_c'],ap,q-a)[0])
            t,h=thermal_step(t,h,u,self.init['reference_c'],ap,b-a)
        pending=[j for j in jobs if not j['already_responded']]
        return dict(remaining_energy_j=joules,predicted_peak_ap_c=peak,
            deadline_misses=sum(j['response']>j['deadline']+1e-9 for j in pending),
            total_lateness_s=sum(max(0,j['response']-j['deadline']) for j in pending))

    def __call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        if any(q['arrival_ns']>now_ns for q in queue): raise ValueError('future ticket')
        if any(set(v)!= {'request','phase','since','dispatch'} for v in lanes.values()): raise ValueError('private lane data')
        now=now_ns/1e9
        ordered=sorted(queue,key=lambda q:(0 if now_ns-q['arrival_ns']>=settings['aging_ns'] else 1 if q['priority']=='urgent' else 2,
            q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id']))
        out=dict(now_ns=now_ns,selected=None,reason='busy_or_empty',candidates=[],modeled_ap_c=self.t)
        if not ordered: return out
        q=ordered[0]
        out['head_request_id']=q['id']
        if self.policy=='CPU_REFERENCE':
            if any(l['request'] for l in lanes.values()): return out
            return dict(out,selected=dict(request_id=q['id'],backend='CPU'),reason='cpu_reference')
        if self.policy=='SPLIT_SERIAL_REFERENCE' and any(l['request'] for l in lanes.values()): return out
        active=self.active_jobs(lanes,now)
        if active is None: return dict(out,reason='unknown_overrun_wait_for_event')
        allowed=backends(q)
        if self.policy in ('SPLIT_REFERENCE','SPLIT_SERIAL_REFERENCE'): allowed=('GPU' if q['task']=='classification' else 'CPU',)
        immediate=[(self.rollout(ordered,active,b,0.,now),b,0.) for b in allowed]
        ref=min(immediate,key=lambda x:(x[0][1]['response'],x[1]!='CPU'))
        chosen=ref
        if self.policy=='ENERGY_AP_REQUEST_V1':
            refscore=self.score(ref[0][0],now)
            delay=min(WAIT_STEP,max(0.,WAIT_LIMIT-(now-q['arrival_ns']/1e9)))
            candidates=immediate+([(self.rollout(ordered,active,b,delay,now),b,delay) for b in allowed] if delay>1e-9 else [])
            scored=[]
            for (jobs,first),b,w in candidates:
                score=self.score(jobs,now)
                if score is None: continue
                item=dict(backend=b,delay_s=w,start_s=first['start'],**score)
                out['candidates'].append(item)
                # Relative local constraint, not a chosen safety threshold or global guarantee.
                if (refscore is not None and score['deadline_misses']==0 and
                        score['predicted_peak_ap_c']<=refscore['predicted_peak_ap_c']+1e-9):
                    scored.append((item,((jobs,first),b,w)))
            if scored:
                chosen=min(scored,key=lambda x:(round(x[0]['remaining_energy_j'],9),
                    round(x[0]['predicted_peak_ap_c'],9),x[0]['start_s'],x[0]['backend']!='CPU'))[1]
                out['reason']='local_min_J_without_peak_increase_vs_EFT'
            else: out['reason']='EFT_fallback_no_feasible_local_prediction'
            out['reference_prediction']=refscore
        else: out['reason']='fixed_split' if self.policy=='SPLIT_REFERENCE' else 'earliest_response'
        first=chosen[0][1]
        out.update(chosen_backend=chosen[1],chosen_explicit_delay_s=chosen[2],planned_start_s=first['start'])
        if first['start']<=now+1e-9:
            out['selected']=dict(request_id=q['id'],backend=chosen[1])
        else:
            # New arrival/phase events still re-evaluate; a forecast never releases a lane.
            out['wait_until_ns']=max(now_ns+1.,first['start']*1e9)
        return out


def inputs(bundle):
    if digest(bundle/'model.json')!=MODEL_SHA: raise ValueError('frozen model hash')
    if digest(bundle/'initial_inputs.json')!=INITIAL_SHA: raise ValueError('initial inputs hash')
    cases=json.loads((bundle/'initial_inputs.json').read_text(encoding='utf8'))
    return json.loads((bundle/'model.json').read_text(encoding='utf8')),cases[0]


def account(result, initial, frozen):
    """Full common120 accounting; never invent post120 cleanup for unfinished work."""
    complete=all(r['status']=='succeeded' for r in result['ledger'])
    ap_end=180 if complete else 120
    ss=segments([dict(state=r['task']+'_'+r['backend'],start=r['dispatch_ns']/1e9,
        end=r.get('lane_available_ns',120e9)/1e9) for r in result['ledger'] if 'dispatch_ns' in r],0,ap_end)
    costs=model.costs(ss,initial,list(range(35,ap_end+1)),frozen,float(ap_end))
    return ss,costs,ap_end


def run(output):
    from tools import d1_arrival_explore as engine, d1_arrival_explore_batch as batch
    contract=json.loads(CONTRACT.read_text(encoding='utf8'))
    if contract['version']!=VERSION or tuple(contract['policies'])!=POLICIES or contract['maximum_runs']!=60:
        raise ValueError('contract mismatch')
    started=time.monotonic(); contract_hash=digest(CONTRACT)
    frozen,case=inputs(BUNDLE); initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    estimates=profile(frozen); config=dict(protocol=VERSION,cells=estimates)
    workloads={name:[dict(q,arrival_ns=q['arrival_ns']+35_000_000_000) for q in batch.workload(name,'evaluation')]
               for name in ('low','queue','burst')}
    workloads['sustained']=[dict(id=q['request_id'],task=q['task_id'],priority=q['priority'],ordinal=q['ordinal'],
        arrival_ns=q['offset_ms']*1_000_000,deadline_offset_ns=q['deadline_ms']*1_000_000) for q in case['manifest_requests']]
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    write(output/'contract_before_run.json',dict(contract,source_hashes={str(x.relative_to(ROOT)):digest(x) for x in
        (CONTRACT,BUNDLE/'model.json',BUNDLE/'initial_inputs.json',Path(__file__),Path(engine.__file__))}))
    write(output/'inputs.json',dict(initial=initial,workloads=workloads,estimated_service_ns=estimates))
    settings=batch.defaults('explore'); settings.update(decision_ns=0,record_ns=0,dispatch_ns=0,
        interference=1.,predicted_interference=1.)
    rows=[]; curves=[]; compact=[]
    for scenario in ('mean','short_context','long_context'):
        actual=profile(frozen,scenario)
        vectors=dict(cells={k:[dict(source_request_id='development_context_transfer_'+scenario,durations_ns=v) for _ in range(4)] for k,v in actual.items()})
        for name,tickets in workloads.items():
            for policy in POLICIES:
                if time.monotonic()-started>600: raise TimeoutError('bounded PC comparison; preserve partial directory')
                controller=Controller(frozen,initial,estimates,policy)
                result=engine.simulate(config,vectors,tickets,policy=policy,settings=settings,seed=201,decision_provider=controller)
                ss,costs,ap_end=account(result,initial,frozen)
                m=result['metrics']; dec=result['decisions']
                row=dict(workload=name,service_scenario=scenario,policy=policy,planned=len(tickets),
                    completed=sum(r['status']=='succeeded' for r in result['ledger']),
                    deadline_met=sum('response_ns' in r and r['response_ns']<=r['deadline_offset_ns'] for r in result['ledger']),
                    urgent_p95_ms=m['urgent_p95_ms'],normal_mean_ms=m['normal_mean_ms'],
                    energy_120s_j=costs['whole_120s_j'],equal_work_completed=m['completion']==1,
                    peak_ap_35_180_c=max(costs['ap_path']) if ap_end==180 else None,
                    peak_ap_35_120_c=max(costs['ap_path'][:86]),ap_end_s=ap_end,
                    classification_cpu=sum(r.get('backend')=='CPU' and r['task']=='classification' for r in result['ledger']),
                    voluntary_wait_decisions=sum(d['selected'] is None and d.get('chosen_explicit_delay_s',0)>0 for d in dec),
                    fallback_decisions=sum(d.get('reason')=='EFT_fallback_no_feasible_local_prediction' for d in dec),
                    overlap_s=sum(s['end_s']-s['start_s'] for s in ss if '+' in s['state']),
                    independent_validation=False)
                rows.append(row)
                if scenario=='mean':
                    compact.append(dict(workload=name,policy=policy,ledger=result['ledger'],segments=ss,decisions=dec))
                    curves.extend(dict(workload=name,policy=policy,t_s=q,predicted_ap_c=v) for q,v in zip(range(35,ap_end+1),costs['ap_path']))
    if digest(CONTRACT)!=contract_hash: raise ValueError('contract changed during run')
    write(output/'summary.json',dict(version=VERSION,runs=len(rows),elapsed_seconds=time.monotonic()-started,results=rows,fitting=False,
        device_commands=0,strict_supported=False,experiment_ready=False,policy_winner=None,
        evidence='measured coefficients + context-transfer service assumptions; no independent policy validation'))
    # Full decision evidence stays local; compact tables and deterministic reproduction are shared.
    write(output/'local_decisions.json',compact)
    for filename,records in (('comparison.csv',rows),('predicted_ap.csv',curves)):
        with (output/filename).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    table='<table><tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in rows[0])+'</tr>'
    table+=''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r.values())+'</tr>' for r in rows)+'</table>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>요청별 실측 모형 PC 비교</title><style>body{font:14px system-ui;margin:24px}td,th{border:1px solid #bbb;padding:5px}table{border-collapse:collapse}</style><h1>요청별 배정·대기: PC 전이 탐색</h1><p>실측 계수 유지 · 동일 공통 처리시간 가정 · 새 실기기 결과 아님 · 독립 검증/정책 우월성 미판정. 3개 문맥 민감도는 신뢰구간/미래 오차 한도가 아님.</p><p><a href="../README.md">설계·범위·판독</a> · <a href="comparison.csv">표</a></p>'+table,encoding='utf8')
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args(); print(json.dumps(run(args.output),ensure_ascii=False,indent=2))
