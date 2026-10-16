"""Predeclared workload envelope study; no device access or physical-model fit.

Network shaping, latest-start service and online coalescing are adaptations,
not reproductions of production phone policies. All decisions are causal.
"""
import argparse
import copy
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import random
import statistics
import time
from tools import d1_scheduler_alternatives as a
from tools import d1_scheduler_capacity as cap
p=a.p
ROOT=p.ROOT/'docs/results/scheduler_conditions_01'
NEW=p.CONDITION_POLICIES
POLICIES=(*a.BASELINES,'RESERVED_BACKFILL_V1',*NEW)
GAPS=(.15,.45,1.2)
SHARES=(.25,.5,.75)
BURSTS=(1,4,8)


def envelopes():
    return [dict(id=f'g{g}_c{c}_b{b}',gap_s=g,class_share=c,burst=b)
            for g,c,b in itertools.product(GAPS,SHARES,BURSTS)]


def workload(e,seed):
    rng=random.Random(seed);n=48
    tasks=['classification']*int(n*e['class_share'])
    tasks+=['detection']*(n-len(tasks));rng.shuffle(tasks)
    # Mean spacing is controlled independently of clustering. Release times
    # depend only on seed/input; NEVER on completion, cost or chosen policy.
    now=35.;out=[]
    for i,task in enumerate(tasks):
        if i:
            step=(e['gap_s']*e['burst']-.03*(e['burst']-1)) if i%e['burst']==0 else .03
            now+=step*rng.uniform(.95,1.05)
        out.append(dict(id=f'{e["id"]}/{seed}/{i}',ordinal=i,task=task,
            priority='urgent' if task=='classification' else 'normal',
            arrival_ns=round(now*1e9),deadline_offset_ns=int((1.5 if task=='classification' else 6)*1e9)))
    return out


class Controller(p.Controller):
    def __init__(self,frozen,initial,policy):
        super().__init__(frozen,initial,p.profile(frozen),policy)
        self.tokens=.65;self.token_time=35.;self.rate=.65;self.capacity=.65
        self.long=p.Controller(frozen,initial,p.profile(frozen,'long_context'),'EFT_REFERENCE')

    def decide_job(self,q,b,now,active,reason,delay=0.):
        first=self.place(q,b,now+delay,active)
        out=dict(now_ns=round(now*1e9),selected=None,reason=reason,
            chosen_request_id=q['id'],chosen_backend=b,modeled_ap_c=self.t,
            planned_start_s=first['start'],chosen_explicit_delay_s=delay)
        if first['start']<=now+1e-9:
            out['selected']=dict(request_id=q['id'],backend=b)
            if self.policy.startswith('TOKEN_'):
                # Debit only a selected dispatch, never on observation callbacks.
                self.tokens-=sum(self.estimates[p.key(q,b)])/1e9
        else:out['wait_until_ns']=max(now*1e9+1,first['start']*1e9)
        return out

    def __call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        fallback=super().__call__(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or fallback['reason']=='unknown_overrun_wait_for_event':return fallback
        now=now_ns/1e9;ordered=a.order(queue,now_ns,settings);q=ordered[0]
        active=self.active_jobs(lanes,now)
        self.tokens=min(self.capacity,self.tokens+max(0.,now-self.token_time)*self.rate);self.token_time=now
        if self.policy=='PAIR_COALESCE_V1':
            # Coalesce only already-arrived requests, never synthetic extra work.
            det=next((x for x in ordered if x['task']=='detection'),None)
            cg=next((x for x in ordered if x['task']=='classification'),None)
            running_det=any(j['state']=='detection_CPU' for j in active)
            if cg and (running_det or det):
                if not running_det and not active:
                    return self.decide_job(det,'CPU',now,active,'start_arrived_pair_detection')
                if running_det and not lanes['GPU']['request']:
                    return self.decide_job(cg,'GPU',now,active,'overlap_arrived_pair')
            b='CPU'
            # Single bounded batching window; not reset by each callback.
            target=q['arrival_ns']/1e9+.20
            delay=max(0.,target-now) if not active else 0.
            return self.decide_job(q,b,now,active,'bounded_pair_coalescing',delay)
        b='CPU' if self.policy in ('TOKEN_CPU_V1','JIT_CPU_V1') else fallback['chosen_backend']
        running=self.long.active_jobs(lanes,now)
        if running is None:return fallback
        # Estimate a conservative all-arrived continuation before borrowing slack.
        jobs=copy.deepcopy(running);slack=float('inf')
        for other in ordered:
            allowed=('CPU',) if b=='CPU' and self.policy!='TOKEN_EFT_V1' else p.backends(other)
            j=min((self.long.place(other,x,now,jobs) for x in allowed),key=lambda j:j['response'])
            jobs.append(j);slack=min(slack,j['deadline']-j['response'])
        # Reserve 10% of predicted response slack; no future-arrival guarantee.
        slack=max(0.,.9*slack)
        age=now-q['arrival_ns']/1e9
        limit=max(0.,2.-age)
        if self.policy=='JIT_CPU_V1':
            delay=min(limit,slack)
        else:
            work=sum(self.estimates[p.key(q,b)])/1e9
            delay=min(limit,slack,max(0.,(work-self.tokens)/self.rate))
        return self.decide_job(q,b,now,active,'bounded_slack_'+self.policy,delay)


def simulate(frozen,initial,tickets,scenario,policy):
    if policy not in NEW:return a.simulate(frozen,initial,tickets,scenario,policy)
    from tools import d1_request_ppo as rl
    c=Controller(frozen,initial,policy)
    vectors=dict(cells={k:[dict(source_request_id='fixed_'+scenario,durations_ns=v) for _ in range(4)]
                       for k,v in p.profile(frozen,scenario).items()})
    result=a.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=policy,settings=rl.settings(),seed=201,decision_provider=c)
    row,extra=rl.outcome(result,initial,frozen)
    return row,result,c,extra


def specification():
    return dict(id='scheduler-conditions-v1',envelopes=envelopes(),policies=POLICIES,
        development_seeds=[81001,81002],test_seeds=[91001,91002,91003],
        scenarios=a.old.SCENARIOS,requests_per_episode=48,runs=3240,max_wall_s=2400,
        unchanged='physical model, initial0, 1.5s/6s deadlines, supported cells, no drops, no DVFS/sleep states',
        horizons=dict(energy_s=[0,120],ap_s=[35,180]),
        shaping=dict(token_capacity_work_s=.65,refill_work_s_per_s=.65,max_age_wait_s=2.,slack_fraction=.9),
        coalescing_window_s=.2,
        selection='per declared envelope: full service in all development contexts; no J/peak/AParea worsening vs EFT in any; at least one strict joint improvement; then min mean J, AParea, peak; otherwise EFT',
        comparisons='report every policy vs CPU, SPLIT, EFT separately; all deadlines required for useful region; P95 cost reported but not required equal',
        conditions='synthetic registered load envelopes, not selected by model score; fresh seeds are not independent device evidence',
        accuracy_threshold=None,device_commands=0,experiment_ready=False)


def useful(r,b):
    full=r['completed']==r['planned']==r['deadline_met']
    costs=('energy_j','peak_ap_c','thermal_degree_seconds')
    valid=full and all(r[k] is not None and b[k] is not None for k in costs)
    return valid and all(r[k]<=b[k]+1e-8 for k in costs) and any(r[k]<b[k]-1e-8 for k in costs)


def select(rows):
    selected={}
    for e in envelopes():
        rs=[r for r in rows if r['envelope']==e['id']]
        ref={(r['seed'],r['scenario']):r for r in rs if r['policy']=='EFT_REFERENCE'}
        candidates=[]
        for policy in POLICIES:
            xs=[r for r in rs if r['policy']==policy]
            if all(x['deadline_met']==x['planned']==x['completed'] and all(
                x[k] is not None and x[k]<=ref[x['seed'],x['scenario']][k]+1e-8
                for k in ('energy_j','peak_ap_c','thermal_degree_seconds')) for x in xs) and any(useful(x,ref[x['seed'],x['scenario']]) for x in xs):
                candidates.append((statistics.mean(x['energy_j'] for x in xs),statistics.mean(x['thermal_degree_seconds'] for x in xs),policy))
        selected[e['id']]=min(candidates)[-1] if candidates else 'EFT_REFERENCE'
    return selected


def save_rows(path,rows):
    fields=sorted(set().union(*(r.keys() for r in rows)))
    a.old.csv_write(path,[{k:r.get(k) for k in fields} for r in rows])


def run(output):
    spec=specification();output=Path(output);output.mkdir(parents=True,exist_ok=False)
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];began=time.monotonic()
    paths=[Path(__file__),Path(p.__file__),Path(a.__file__),Path(a.old.engine.__file__),
        p.ROOT/'tools/d1_request_ppo.py',p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']
    hashes={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    p.write(output/'preregistered.json',dict(spec=spec,hashes=hashes,utc=datetime.now(timezone.utc).isoformat()))
    rows=[];bounds=[];selected=None
    with (output/'local_ledgers.jsonl').open('w',encoding='utf8') as raw:
        for stage in ('development','test'):
            if stage=='test':
                selected=select(rows)
                p.write(output/'freeze_before_test.json',dict(selected=selected,hashes=hashes,utc=datetime.now(timezone.utc).isoformat()))
            for e in envelopes():
                for seed in spec[stage+'_seeds']:
                    tickets=workload(e,seed)
                    for scenario in spec['scenarios']:
                        demand=cap.capacity(tickets,p.profile(frozen,scenario))
                        bounds.append(dict(stage=stage,envelope=e['id'],seed=seed,scenario=scenario,**demand))
                        for policy in POLICIES:
                            if time.monotonic()-began>spec['max_wall_s']:raise TimeoutError('bounded study; preserve partial output')
                            row,result,_,_=simulate(frozen,initial,tickets,scenario,policy)
                            # Verify actual engine invariants before retaining an outcome.
                            assert len(result['ledger'])==48
                            assert [r['arrival_ns'] for r in result['ledger']]==[q['arrival_ns'] for q in tickets]
                            for b in ('CPU','GPU'):
                                jobs=sorted((r for r in result['ledger'] if r.get('backend')==b and 'dispatch_ns' in r),key=lambda r:r['dispatch_ns'])
                                assert all(x.get('lane_available_ns',120e9)<=y['dispatch_ns']+1e-4 for x,y in zip(jobs,jobs[1:]))
                            for r in result['ledger']:
                                ts=[r[k] for k in ('dispatch_ns',*a.old.engine.FIELDS) if k in r]
                                assert ts==sorted(ts)
                            row={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
                            row.update(stage=stage,envelope=e['id'],seed=seed,scenario=scenario,policy=policy,
                                gap_s=e['gap_s'],class_share=e['class_share'],burst=e['burst'])
                            rows.append(row)
                            raw.write(json.dumps(dict(meta=row,ledger=result['ledger']),ensure_ascii=False)+'\n')
                save_rows(output/'results.csv',rows);raw.flush()
                p.write(output/'progress.json',dict(stage=stage,envelope=e['id'],runs=len(rows),elapsed_s=time.monotonic()-began))
                print(stage,e['id'],len(rows),round(time.monotonic()-began,2),flush=True)
    assert hashes=={str(x.relative_to(p.ROOT)):p.digest(x) for x in paths}
    a.old.csv_write(output/'capacity.csv',bounds)
    p.write(output/'summary.json',dict(runs=len(rows),elapsed_s=time.monotonic()-began,selected=selected,
        physical_hash_unchanged=True,source_hash_unchanged=True,device_commands=0,experiment_ready=False))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.output)
