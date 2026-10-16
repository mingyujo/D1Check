"""Five bounded causal schedulers; same frozen plant, separate PC exploration."""
import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time
from tools import d1_empirical_request_policy as p
from tools import d1_request_rl as old

VERSION='scheduler-alternatives-v1'
ROOT=p.ROOT/'docs/results/scheduler_alternatives_01'
BASELINES=('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE')
POLICIES=(*BASELINES,*p.ALTERNATIVE_POLICIES)


def order(queue,now,settings):
    return sorted(queue,key=lambda q:(0 if now-q['arrival_ns']>=settings['aging_ns'] else
        1 if q['priority']=='urgent' else 2,q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id']))


def service_vector(jobs,priorities):
    pending=[j for j in jobs if not j['already_responded']]
    return tuple(sum(j['response']>j['deadline']+1e-9 for j in pending if priorities[j['id']]==pr)
                 for pr in ('urgent','normal'))+tuple(sum(max(0.,j['response']-j['deadline']) for j in pending
                    if priorities[j['id']]==pr) for pr in ('urgent','normal'))


class Controller(p.Controller):
    def __init__(self,frozen,initial,policy):
        super().__init__(frozen,initial,p.profile(frozen),policy)
        self.forecasters=[p.Controller(frozen,initial,p.profile(frozen,s),'EFT_REFERENCE') for s in old.SCENARIOS]
        self.callback_wall_seconds=[];self.forecast_count=0

    def project(self,fc,ordered,active,choice,now,priorities,thermal=True):
        rid,b,delay=choice;q=next(q for q in ordered if q['id']==rid)
        first=fc.place(q,b,now+delay,active);jobs=copy.deepcopy(active)+[first]
        for other in ordered:
            if other['id']==rid:continue
            jobs.append(min((fc.place(other,x,first['start'],jobs) for x in p.backends(other)),
                            key=lambda j:(j['response'],j['backend']!='CPU')))
        self.forecast_count+=1
        if not thermal:return jobs,first,None
        if max(j['end'] for j in jobs)>120+1e-9:return jobs,first,None
        ss=p.segments(jobs,now,180);ap=self.frozen['ap'];slopes=ap['parameters']['ap_slope_at_30_c_per_s']
        t,h=self.t,self.h;ref=self.init['reference_c'];peak=t;area=0.;energy=0.
        for s in ss:
            label='resident_idle' if s['state']=='idle' else s['state'];a,z=s['start_s'],s['end_s']
            if label!='resident_idle':energy+=max(0,min(120,z)-a)*self.frozen['energy_increment_w'][label]
            u=slopes[label]-slopes['resident_idle'];prev=a;last=t
            for end in sorted({z}|{float(x) for x in range(math.ceil(a),math.floor(z)+1) if x>a}):
                value=p.thermal_step(t,h,u,ref,ap,end-a)[0]
                area+=(max(0.,last-ref)+max(0.,value-ref))*.5*(end-prev)
                peak=max(peak,value);prev=end;last=value
            t,h=p.thermal_step(t,h,u,ref,ap,z-a)
        return jobs,first,dict(service=service_vector(jobs,priorities),energy=energy,peak=peak,area=area)

    def __call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        began=time.perf_counter()
        try:return self.decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        finally:self.callback_wall_seconds.append(time.perf_counter()-began)

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        # Inherited callback validates public information and produces unchanged EFT fallback.
        fallback=super().__call__(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or fallback['reason']=='unknown_overrun_wait_for_event':return fallback
        now=now_ns/1e9;ordered=order(queue,now_ns,settings);active=self.active_jobs(lanes,now)
        head=ordered[0];refchoice=(head['id'],fallback['chosen_backend'],0.)
        priorities={q['id']:q['priority'] for q in ordered}
        priorities.update({l['request']['id']:l['request']['priority'] for l in lanes.values() if l['request']})
        choice=refchoice;details=[]
        if self.policy=='ECO_EDF_V1':
            options=[self.place(head,b,now,active) for b in p.backends(head)]
            feasible=[j for j in options if j['response']<=j['deadline']+1e-9]
            if feasible:
                j=min(feasible,key=lambda j:(self.frozen['energy_increment_w'][j['state']]*(j['end']-j['start']),j['response']))
                choice=(head['id'],j['backend'],0.)
        elif self.policy=='LLF_EFT_V1':
            q=min(ordered,key=lambda q:(0 if now_ns-q['arrival_ns']>=settings['aging_ns'] else 1,
                (q['arrival_ns']+q['deadline_offset_ns'])/1e9-now-min(sum(self.estimates[p.key(q,b)][:2 if q['priority']=='urgent' else 3])/1e9 for b in p.backends(q)),
                q['ordinal']))
            j=min((self.place(q,b,now,active) for b in p.backends(q)),key=lambda j:(j['response'],j['backend']!='CPU'))
            choice=(q['id'],j['backend'],0.)
        elif self.policy=='RESERVED_BACKFILL_V1':
            if fallback['selected'] is None:
                jobs,_,_=self.project(self,ordered,active,refchoice,now,priorities,False)
                reservations={j['id']:j['start'] for j in jobs}
                for q in ordered[1:]:
                    candidates=[]
                    for b in p.backends(q):
                        c=(q['id'],b,0.);other,first,_=self.project(self,ordered,active,c,now,priorities,False)
                        # Preserve every already-arrived request's forecast start, not only head.
                        if first['start']<=now+1e-9 and all(j['start']<=reservations[j['id']]+1e-9 for j in other):
                            candidates.append((first['response'],b,c))
                    if candidates:choice=min(candidates)[2];break
        elif self.policy in ('PARETO_MPC_V1','THERMAL_MPC_V1'):
            contexts=[]
            for fc in self.forecasters:
                fc.t,fc.h=self.t,self.h
                running=fc.active_jobs(lanes,now)
                if running is None:return dict(fallback,reason='MPC_unknown_context_overrun_EFT')
                _,_,score=self.project(fc,ordered,running,refchoice,now,priorities)
                if score is None:return dict(fallback,reason='MPC_reference_incomplete_EFT')
                contexts.append((fc,running,score))
            choices={refchoice}
            for q in ordered[:4]:
                for b in p.backends(q):
                    if self.place(q,b,now,active)['start']<=now+1e-9:choices.add((q['id'],b,0.))
            delay=min(.25,max(0.,2.-(now-head['arrival_ns']/1e9)))
            if delay>1e-9:
                for b in p.backends(head):
                    j=self.place(head,b,now+delay,active)
                    if j['response']<=j['deadline']+1e-9:choices.add((head['id'],b,delay))
            safe=[]
            for candidate in sorted(choices):
                predictions=[];valid=True
                for fc,running,refscore in contexts:
                    _,first,score=self.project(fc,ordered,running,candidate,now,priorities)
                    if score is None or any(x>y+1e-9 for x,y in zip(score['service'],refscore['service'])) or any(
                        score[k]>refscore[k]+1e-9 for k in ('energy','peak','area')):valid=False;break
                    predictions.append(score)
                details.append(dict(request_id=candidate[0],backend=candidate[1],delay_s=candidate[2],admitted=valid))
                if valid:
                    primary='energy' if self.policy=='PARETO_MPC_V1' else 'area'
                    secondary='area' if primary=='energy' else 'energy'
                    scorekey=(round(statistics.mean(s[primary] for s in predictions),9),
                              round(statistics.mean(s[secondary] for s in predictions),9),candidate!=refchoice,candidate)
                    safe.append((scorekey,candidate))
            if safe:choice=min(safe)[1]
        else:raise ValueError('unknown alternative')
        q=next(q for q in ordered if q['id']==choice[0]);first=self.place(q,choice[1],now+choice[2],active)
        out=dict(now_ns=now_ns,selected=None,reason=self.policy,head_request_id=head['id'],
            chosen_request_id=q['id'],chosen_backend=choice[1],chosen_explicit_delay_s=choice[2],
            planned_start_s=first['start'],modeled_ap_c=self.t,candidates=details,
            local_deviation=choice!=refchoice)
        if first['start']<=now+1e-9:out['selected']=dict(request_id=q['id'],backend=choice[1])
        else:out['wait_until_ns']=max(now_ns+1.,first['start']*1e9)
        return out


def energy_lower_bound(tickets,frozen,initial,scenario):
    """Relax deadlines, arrivals, ordering and partial-overlap realizability.

    No sleep/power state is invented. Valid only for equal work entirely before120s.
    Enumerate number of identical classification requests mapped to GPU; allow any overlap.
    This is an optimistic bound, never an executable policy or a heat bound.
    """
    for q in tickets:p.backends(q)
    ds={k:sum(v)/1e9 for k,v in p.profile(frozen,scenario).items()};w=frozen['energy_increment_w']
    nc=sum(q['task']=='classification' for q in tickets);nd=len(tickets)-nc
    dtime=nd*ds['detection_CPU_normal'];discount=w['classification_GPU']+w['detection_CPU']-w['classification_GPU+detection_CPU']
    choices=[]
    for ng in range(nc+1):
        ctime=(nc-ng)*ds['classification_CPU_urgent'];gtime=ng*ds['classification_GPU_urgent']
        energy=120*initial['preload_power_w']+w['detection_CPU']*dtime+w['classification_CPU']*ctime+w['classification_GPU']*gtime-max(0.,discount)*min(dtime,gtime)
        choices.append((energy,ng))
    value,ng=min(choices)
    return dict(lower_bound_j=value,relaxed_gpu_classifications=ng,not_necessarily_attainable=True)


def simulate(frozen,initial,tickets,scenario,policy):
    from tools import d1_request_ppo as rl
    if policy in BASELINES:return rl.simulate(frozen,initial,tickets,scenario,policy=policy)
    c=Controller(frozen,initial,policy)
    actual=p.profile(frozen,scenario);vectors=dict(cells={k:[dict(source_request_id='common_context_'+scenario,durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    result=old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=policy,settings=rl.settings(),seed=201,decision_provider=c)
    row,extra=rl.outcome(result,initial,frozen)
    row.update(decision_host_total_s=sum(c.callback_wall_seconds),decision_host_max_ms=1000*max(c.callback_wall_seconds,default=0.),
        decision_host_p95_ms=1000*sorted(c.callback_wall_seconds)[math.ceil(.95*len(c.callback_wall_seconds))-1] if c.callback_wall_seconds else 0.,
        decision_calls=len(c.callback_wall_seconds),forecasts=c.forecast_count,
        local_deviations=sum(d.get('local_deviation',False) for d in result['decisions']),
        wait_actions=sum(d.get('chosen_explicit_delay_s',0)>0 and not d['selected'] for d in result['decisions']))
    return row,result,c,extra


def specification():
    return dict(version=VERSION,new_policies=list(p.ALTERNATIVE_POLICIES),baselines=list(BASELINES),
        development_seeds=list(range(60001,60005)),test_seeds=list(range(70001,70009)),families=list(old.FAMILIES),
        scenarios=list(old.SCENARIOS),development_runs=384,final_runs=1056,ppo_seeds=[11,23,37],
        causal='arrived tickets/public phases/preload initial/fixed development service estimates; no future arrivals/realizations',
        mpc='top4 first-request alternatives + head wait<=250ms/age2s; full arrived-queue EFT rollout; all3 contexts no predicted priority service/lateness, J, peak, AP-area worsening vs EFT; execute first action only',
        selection='development: lex service-worse cases, heat-worse cases, energy-worse cases, mean J, mean AP burden; choose one for follow-up but publish every candidate; not a PASS',
        final_rule='no tuning after opening test; report pairwise constraints, deadlines, P95, J, peak, AP burden; no default/device adoption',
        analytical_bound='optimistic full-work-before120 J lower bound; no heat or deadline optimality guarantee',
        max_wall_s=3600,physical_model_sha256=p.MODEL_SHA,initial_sha256=p.INITIAL_SHA,
        device_commands=0,experiment_ready=False)


def run(output):
    from tools import d1_request_ppo as rl
    spec=specification();assert json.loads((ROOT/'contract.json').read_text(encoding='utf8'))==spec
    output=Path(output);output.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    paths=[Path(__file__),Path(p.__file__),Path(old.engine.__file__),Path(old.__file__),Path(rl.__file__),ROOT/'contract.json',p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']
    sources={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in paths}
    p.write(output/'preregistered.json',dict(spec=spec,sources=sources,utc=datetime.now(timezone.utc).isoformat()))
    frozen,case=p.inputs(p.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    rows=[];raw=(output/'local_ledgers.jsonl').open('w',encoding='utf8');selected=None
    ppos={seed:rl.load_actor(p.ROOT/f'docs/results/request_ppo_01/run_v2/seed{seed}/selected_actor.json') for seed in spec['ppo_seeds']}
    ppo_hashes={seed:rl.model_hash(net) for seed,net in ppos.items()}
    try:
        for stage,seeds in [('development',spec['development_seeds']),('test',spec['test_seeds'])]:
            if stage=='test':
                dev=[r for r in rows if r['stage']=='development'];refs={(r['trace_seed'],r['family'],r['scenario']):r for r in dev if r['policy']=='EFT_REFERENCE'}
                rankings=[]
                for policy in p.ALTERNATIVE_POLICIES:
                    rs=[r for r in dev if r['policy']==policy];bs=[refs[(r['trace_seed'],r['family'],r['scenario'])] for r in rs]
                    service=sum(any(r[x]>b[x] for x in ('urgent_service_failure','normal_service_failure','unfinished')) for r,b in zip(rs,bs))
                    heat=sum(r['thermal_degree_seconds'] is None or r['peak_ap_c'] is None or r['thermal_degree_seconds']>b['thermal_degree_seconds']+1e-8 or r['peak_ap_c']>b['peak_ap_c']+1e-8 for r,b in zip(rs,bs))
                    energy=sum(r['energy_j']>b['energy_j']+1e-8 for r,b in zip(rs,bs))
                    rankings.append(dict(policy=policy,key=[service,heat,energy,statistics.mean(r['energy_j'] for r in rs),statistics.mean(r['thermal_degree_seconds'] if r['thermal_degree_seconds'] is not None else 1e9 for r in rs)]))
                selected=min(rankings,key=lambda x:x['key'])['policy']
                assert sources=={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in paths}
                p.write(output/'freeze_before_test.json',dict(utc=datetime.now(timezone.utc).isoformat(),rankings=rankings,selected=selected,ppo_hashes=ppo_hashes,test_started=False))
            policies=list(POLICIES)+([f'PPO_seed{s}' for s in spec['ppo_seeds']] if stage=='test' else [])
            for seed in seeds:
                for family in old.FAMILIES:
                    tickets=old.workload(family,seed)
                    for scenario in old.SCENARIOS:
                        bound=energy_lower_bound(tickets,frozen,initial,scenario)
                        for policy in policies:
                            if time.monotonic()-began>spec['max_wall_s']:raise TimeoutError('bounded PC alternatives; partial results preserved')
                            if policy.startswith('PPO_seed'):row,result,_,_=rl.simulate(frozen,initial,tickets,scenario,ppos[int(policy.split('seed')[1])])
                            else:row,result,_,_=simulate(frozen,initial,tickets,scenario,policy)
                            row.update(stage=stage,trace_seed=seed,family=family,scenario=scenario,policy=policy,
                                unfinished=row['planned']-row['completed'],energy_lower_bound_j=bound['lower_bound_j'],
                                gap_to_relaxed_bound_j=row['energy_j']-bound['lower_bound_j'] if row['completed']==row['planned'] else None)
                            if row['completed']==row['planned'] and row['energy_j']<bound['lower_bound_j']-1e-7:raise ValueError('energy below relaxation bound')
                            rows.append(row);raw.write(json.dumps(dict(stage=stage,trace_seed=seed,family=family,scenario=scenario,policy=policy,ledger=result['ledger'],decisions=result['decisions']),ensure_ascii=False)+'\n')
                    old.csv_write(output/'results.csv',[{k:r.get(k) for k in sorted(set().union(*(x.keys() for x in rows)))} for r in rows])
                    raw.flush();p.write(output/'progress.json',dict(stage=stage,seed=seed,family=family,runs=len(rows),elapsed_s=time.monotonic()-began))
                    print(stage,seed,family,len(rows),round(time.monotonic()-began,2),flush=True)
    finally:raw.close()
    assert sources=={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in paths}
    assert ppo_hashes=={seed:rl.model_hash(net) for seed,net in ppos.items()}
    p.write(output/'summary.json',dict(selected_for_followup=selected,runs=len(rows),elapsed_s=time.monotonic()-began,
        device_commands=0,independent_device_validation=False,experiment_ready=False))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();print(run(args.output))
