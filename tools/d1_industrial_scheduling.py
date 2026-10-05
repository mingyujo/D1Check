"""Bounded industrial-scheduling adaptations in the unchanged empirical PC plant.

Online callbacks see only arrived tickets/public lane phases. Offline beam search
explicitly knows arrivals and the scenario durations; it is not an oracle bound,
production policy, independent validation, or reproduction of original DBR/ATC.
"""
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

ROOT = p.ROOT / 'docs/results/industrial_scheduling_01'
SOURCE = p.ROOT / 'docs/results/supervised_selector_01/run_v1/local_ledgers.jsonl'
ATC, BOTTLENECK, REPLAY = p.INDUSTRIAL_POLICIES
ONLINE = ('EFT_REFERENCE', ATC, BOTTLENECK)
CASES = ('g1.2_c0.5_b1', 'g0.45_c0.5_b4', 'g0.15_c0.5_b8')
TICKET_FIELDS = ('id', 'ordinal', 'task', 'priority', 'arrival_ns', 'deadline_offset_ns')


def specification():
    return dict(version='industrial-scheduling-pc-v1', envelopes=list(CASES), source_seed=123001,
        prefix_requests=8, scenarios=list(old.SCENARIOS), online_policies=list(ONLINE),
        atc=dict(k=2., urgent_weight=4., normal_weight=1.,
            weight_reason='deadline ratio 6/1.5; heuristic, not measured delay cost'),
        online_rule='immediate legal dispatch only; aging4s; mean service forecast; per-request long-context lateness may not increase vs EFT continuation',
        bottleneck='minimum projected mandatory CPU lateness then mandatory clearance, J, peak, first response; no extra intentional wait',
        beam_width=32, offline_wait_grid_s=[0., .25], reference_case_timeout_s=20., max_wall_s=900.,
        offline='future arrivals and scenario durations known; two half-beams for service-then-J/peak; retain online incumbents; no optimality/lower-bound claim',
        accounting=dict(energy_window_s=[0,120], ap_window_s=[35,180], full_denominator=8,
            controller_incremental_time_energy_zero_assumption=True),
        online_runs=27, offline_replays=18, fitting=False, strict_supported=False,
        independent_device_validation=False, experiment_ready=False, device_commands=0,
        scope='post-hoc method exploration on prefixes of already-seen stored inputs; no policy selection or tuning')


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT/'contract.json').exists() or (ROOT/'inputs.json').exists():
        raise FileExistsError('do not overwrite prepared contract/inputs')
    found = {}
    with SOURCE.open(encoding='utf8') as stream:
        for line in stream:
            d = json.loads(line); m = d['meta']
            if (m['envelope'] in CASES and int(m['seed']) == 123001
                    and m['scenario'] == 'mean' and m['policy'] == 'EFT_REFERENCE'):
                qs = [{k:r[k] for k in TICKET_FIELDS} for r in d['ledger'][:8]]
                if m['envelope'] in found: raise ValueError('ambiguous stored source')
                found[m['envelope']] = dict(source_meta=m, tickets=qs, original_planned=len(d['ledger']))
    if set(found) != set(CASES): raise ValueError('missing source input')
    for v in found.values():
        if len(v['tickets']) != 8 or {q['task'] for q in v['tickets']} != {'classification','detection'}:
            raise ValueError('bounded mixed prefix required')
    p.write(ROOT/'inputs.json', dict(source=SOURCE.relative_to(p.ROOT).as_posix(),
        source_sha256=p.digest(SOURCE), cases=found))
    p.write(ROOT/'contract.json', specification())


def ordered(queue, now_ns, settings):
    return sorted(queue, key=lambda q:(0 if now_ns-q['arrival_ns'] >= settings['aging_ns'] else
        1 if q['priority']=='urgent' else 2, q['arrival_ns']+q['deadline_offset_ns'], q['ordinal'], q['id']))


def project(fc, queue, active, choice, now):
    """Same per-request EFT continuation boundary as the existing PAIR guard."""
    rid, backend = choice
    q = next(q for q in queue if q['id']==rid)
    first = fc.place(q, backend, now, active)
    jobs = copy.deepcopy(active)+[first]
    for other in queue:
        if other['id']==rid: continue
        jobs.append(min((fc.place(other,b,first['start'],jobs) for b in p.backends(other)),
                        key=lambda j:(j['response'],j['backend']!='CPU')))
    return jobs, first


def lateness(jobs):
    return {j['id']:max(0.,j['response']-j['deadline']) for j in jobs if not j['already_responded']}


def guard_worsens(proposed, reference):
    if set(proposed)!=set(reference): raise ValueError('guard denominator mismatch')
    return [rid for rid in proposed if proposed[rid]>reference[rid]+1e-9]


class Controller(p.Controller):
    def __init__(self, frozen, initial, policy):
        if policy not in (ATC,BOTTLENECK): raise ValueError('unknown online adaptation')
        super().__init__(frozen,initial,p.profile(frozen),policy)
        self.long=p.Controller(frozen,initial,p.profile(frozen,'long_context'),'EFT_REFERENCE')
        self.records=[]; self.callback_times=[]

    def __call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        began=time.perf_counter()
        try: return self.decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        finally: self.callback_times.append(time.perf_counter()-began)

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        ref=super().__call__(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or 'chosen_backend' not in ref: return ref
        now=now_ns/1e9; qs=ordered(queue,now_ns,settings)
        active=self.active_jobs(lanes,now); running=self.long.active_jobs(lanes,now)
        if active is None or running is None: return dict(ref,reason='industrial_unknown_overrun_EFT')
        refchoice=(qs[0]['id'],ref['chosen_backend'])
        refjobs,_=project(self.long,qs,running,refchoice,now)
        ref_lateness=lateness(refjobs)
        options=[]; details=[]
        aged=[q for q in qs if now_ns-q['arrival_ns']>=settings['aging_ns']]
        pool=aged or qs
        mean_hold=statistics.mean(sum(self.estimates[p.key(q,b)])/1e9 for q in pool for b in p.backends(q))
        cpu_work=sum(sum(self.estimates[p.key(q,'CPU')])/1e9 for q in qs if q['task']=='detection')
        for q in pool:
            for b in p.backends(q):
                first=self.place(q,b,now,active)
                if first['start']>now+1e-9: continue
                guardjobs,_=project(self.long,qs,running,(q['id'],b),now)
                worse=guard_worsens(lateness(guardjobs),ref_lateness)
                jobs,_=project(self,qs,active,(q['id'],b),now)
                score=self.score(jobs,now)
                hold=first['end']-first['start']; slack=max(0.,first['deadline']-first['response'])
                weight=4. if q['priority']=='urgent' else 1.
                atc=weight/hold*math.exp(-slack/(2.*mean_hold))
                mandatory=[j for j in jobs if j['state']=='detection_CPU' and not j['already_responded']]
                ml=[max(0.,j['response']-j['deadline']) for j in mandatory]
                clearance=max((j['end'] for j in mandatory),default=now)
                details.append(dict(request_id=q['id'],backend=b,atc_index=atc,
                    mandatory_clearance_s=clearance,mandatory_max_lateness_s=max(ml,default=0.),
                    guard_veto=bool(worse),worsened_ids=worse))
                if worse or score is None: continue
                tie=(first['response'],q['ordinal'],b!='CPU')
                if self.policy==ATC:
                    rank=(-atc,*tie)
                elif cpu_work>0:
                    rank=(max(ml,default=0.),sum(ml),clearance,
                        round(score['remaining_energy_j'],9),round(score['predicted_peak_ap_c'],9),*tie)
                else:
                    # No mandatory bottleneck work: do not invent a reason to deviate.
                    continue
                options.append((rank,q,b,first))
        self.records.append(dict(now_ns=now_ns,policy=self.policy,mandatory_cpu_work_s=cpu_work,
            reference_choice=refchoice,reference_lateness_s=ref_lateness,candidates=details))
        if not options: return dict(ref,reason='industrial_no_admitted_choice_EFT')
        _,q,b,first=min(options,key=lambda x:x[0])
        return dict(now_ns=now_ns,selected=dict(request_id=q['id'],backend=b),reason=self.policy,
            chosen_request_id=q['id'],chosen_backend=b,chosen_explicit_delay_s=0.,planned_start_s=first['start'],
            modeled_ap_c=self.t,local_deviation=(q['id'],b)!=refchoice)


def settings():
    s=old.batch.defaults('explore')
    s.update(decision_ns=0,record_ns=0,dispatch_ns=0,interference=1.,predicted_interference=1.)
    return s


def outcome(rr,initial,frozen):
    ss,costs,end=p.account(rr,initial,frozen)
    rows=rr['ledger']; ref=p.memory.initialize(initial['preload'],frozen['ap']['beta'],30.)['reference_c']
    path=costs['ap_path']; rise=[max(0.,v-ref) for v in path]
    area=sum((a+b)*.5 for a,b in zip(rise,rise[1:])) if end==180 else None
    counts={pr:sum(r['status']!='succeeded' or 'response_ns' not in r or
                    r['response_ns']>r['deadline_offset_ns'] for r in rows if r['priority']==pr)
            for pr in ('urgent','normal')}
    row=dict(planned=len(rows),completed=sum(r['status']=='succeeded' for r in rows),
        urgent_failure=counts['urgent'],normal_failure=counts['normal'],
        deadline_met=sum('response_ns' in r and r['response_ns']<=r['deadline_offset_ns'] for r in rows),
        energy_j=costs['whole_120s_j'],peak_ap_c=max(path) if end==180 else None,
        thermal_degree_seconds=area,urgent_p95_ms=rr['metrics']['urgent_p95_ms'],
        normal_mean_ms=rr['metrics']['normal_mean_ms'],
        overlap_s=sum(s['end_s']-s['start_s'] for s in ss if '+' in s['state']))
    return row,ss,costs


def simulate(frozen,initial,tickets,scenario,policy,plan=None):
    c=(p.Controller(frozen,initial,p.profile(frozen),policy) if policy=='EFT_REFERENCE' else
       Replay(frozen,initial,plan) if policy==REPLAY else Controller(frozen,initial,policy))
    vectors=dict(cells={k:[dict(source_request_id='development_context_'+scenario,durations_ns=v) for _ in range(4)]
                        for k,v in p.profile(frozen,scenario).items()})
    rr=old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=policy,settings=settings(),seed=201,decision_provider=c)
    row,ss,costs=outcome(rr,initial,frozen)
    row.update(decision_calls=len(rr['decisions']),
        decision_host_total_s=sum(getattr(c,'callback_times',[])),
        decision_host_max_ms=1000*max(getattr(c,'callback_times',[]),default=0.),
        local_deviations=sum(d.get('local_deviation',False) for d in rr['decisions']))
    return row,rr,c,ss,costs


def jobs_from_ledger(rows):
    if any(r['status']!='succeeded' for r in rows): raise ValueError('incomplete reference schedule')
    return [dict(id=r['id'],state=r['task']+'_'+r['backend'],backend=r['backend'],
        start=r['dispatch_ns']/1e9,end=r['lane_available_ns']/1e9,
        response=(r['arrival_ns']+r['response_ns'])/1e9,
        deadline=(r['arrival_ns']+r['deadline_offset_ns'])/1e9,already_responded=False) for r in rows]


def validate_schedule(jobs,tickets,profile):
    if len(jobs)!=len(tickets) or {j['id'] for j in jobs}!={q['id'] for q in tickets}:
        raise ValueError('schedule denominator mismatch')
    qs={q['id']:q for q in tickets}
    for j in jobs:
        q=qs[j['id']]
        if j['backend'] not in p.backends(q) or j['state']!=q['task']+'_'+j['backend']:
            raise ValueError('unsupported calendar cell')
        d=profile[p.key(q,j['backend'])]
        if (j['start']<q['arrival_ns']/1e9-2e-9 or j['end']>120+2e-9 or
            abs(j['end']-j['start']-sum(d)/1e9)>2e-9 or
            abs(j['response']-j['start']-sum(d[:2 if q['priority']=='urgent' else 3])/1e9)>2e-9):
            raise ValueError('calendar phase/release boundary')
    for i,j in enumerate(jobs):
        for other in jobs[i+1:]:
            if min(j['end'],other['end'])-max(j['start'],other['start'])>2e-9:
                if j['backend']==other['backend']: raise ValueError('calendar lane overlap')
                p.state([j['state'],other['state']])


class Replay(p.Controller):
    """Offline-only engine check. Future plan is deliberately isolated here."""
    def __init__(self,frozen,initial,jobs):
        super().__init__(frozen,initial,p.profile(frozen),REPLAY)
        self.plan={j['id']:copy.deepcopy(j) for j in jobs}

    def __call__(self,config,queue,lanes,now_ns,cfg,thermal_model,current_ap):
        if any(q['arrival_ns']>now_ns for q in queue): raise ValueError('future queue ticket')
        now=now_ns/1e9
        ready=sorted((self.plan[q['id']] for q in queue),key=lambda j:(j['start'],j['id']))
        for j in ready:
            if j['start']<=now+2e-9 and lanes[j['backend']]['request'] is None:
                # A calendar's ns rounding cannot release an actual lane or
                # create even a sub-ns unsupported co-run. Wait for its event.
                members=[j['state']]+[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
                if '+'.join(sorted(members)) not in p.STATES: continue
                if abs(j['start']-now)>5e-9: raise ValueError('offline replay missed planned start')
                return dict(now_ns=now_ns,selected=dict(request_id=j['id'],backend=j['backend']),reason='offline_reference_replay')
        future=[j['start']*1e9 for j in ready if j['start']*1e9>now_ns+1.]
        out=dict(now_ns=now_ns,selected=None,reason='offline_calendar_wait')
        if future: out['wait_until_ns']=min(future)
        return out


def search(frozen,initial,tickets,scenario,incumbents,width=32,waits=(0.,.25),timeout=20.):
    """Two-objective constructive beam; pruned nodes do NOT prove any bound."""
    fc=p.Controller(frozen,initial,p.profile(frozen,scenario),'EFT_REFERENCE')
    fc.observe(35e9,{b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')})
    began=time.monotonic(); nodes=[[]]; expanded=0; pruned=0; depth_done=0; timed_out=False
    completed=[copy.deepcopy(v) for v in incumbents]
    def rank(jobs,objective):
        v=fc.score(jobs,35.)
        if v is None: return (float('inf'),)*4
        primary,other=('remaining_energy_j','predicted_peak_ap_c') if objective=='energy' else ('predicted_peak_ap_c','remaining_energy_j')
        return (v['deadline_misses'],v['total_lateness_s'],v[primary],v[other])
    for depth in range(len(tickets)):
        candidates={}
        for jobs in nodes:
            used={j['id'] for j in jobs}
            for q in tickets:
                if q['id'] in used: continue
                for b in p.backends(q):
                    for delay in waits:
                        if time.monotonic()-began>timeout:
                            timed_out=True; break
                        first=fc.place(q,b,q['arrival_ns']/1e9+delay,jobs)
                        if first['end']>120: continue
                        candidate=jobs+[first]
                        key=tuple(sorted((j['id'],j['backend'],round(j['start'],9)) for j in candidate))
                        if key not in candidates:
                            expanded+=1
                            candidates[key]=(candidate,rank(candidate,'energy'),rank(candidate,'thermal'))
                    if timed_out: break
                if timed_out: break
            if timed_out: break
        if timed_out: break
        if not candidates: break
        selected={}
        for objective in (1,2):
            for key,value in sorted(candidates.items(),key=lambda kv:(kv[1][objective],kv[0]))[:width//2]:
                selected[key]=value[0]
        nodes=list(selected.values());pruned+=len(candidates)-len(nodes);depth_done=depth+1
        if depth_done==len(tickets): completed.extend(nodes)
    unique={tuple(sorted((j['id'],j['backend'],round(j['start'],9)) for j in jobs)):jobs for jobs in completed}
    for jobs in unique.values(): validate_schedule(jobs,tickets,p.profile(frozen,scenario))
    winners={objective:min(unique.values(),key=lambda jobs:rank(jobs,objective)) for objective in ('energy','thermal')}
    stats=dict(expanded_nodes=expanded,pruned_nodes=pruned,depth_completed=depth_done,
        final_calendars=len(unique),timed_out=timed_out,elapsed_s=time.monotonic()-began,
        optimality_proved=False,lower_bound=False,incumbents_include_online=True,
        ranks={o:list(rank(j,o)) for o,j in winners.items()})
    return winners,stats


def sources():
    return [Path(__file__),Path(p.__file__),Path(old.__file__),Path(old.engine.__file__),
        Path(p.model.__file__),Path(p.memory.__file__),ROOT/'contract.json',ROOT/'inputs.json',
        p.BUNDLE/'model.json',p.BUNDLE/'initial_inputs.json']


def run(output):
    if json.loads((ROOT/'contract.json').read_text(encoding='utf8'))!=specification():
        raise ValueError('contract/code mismatch')
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    hashes={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in sources()}
    data=json.loads((ROOT/'inputs.json').read_text(encoding='utf8'))
    # Shared eight-ticket inputs are sufficient for reproduction. The large
    # parent ledger is provenance, not a hidden runtime input to decisions.
    source_available=SOURCE.exists()
    if source_available and p.digest(SOURCE)!=data['source_sha256']: raise ValueError('stored source changed')
    frozen,case=p.inputs(p.BUNDLE);initial={k:copy.deepcopy(case['initial'][k]) for k in ('preload','preload_power_w')}
    spec=specification();p.write(out/'registered_before_run.json',dict(spec=spec,hashes=hashes,
        base_head='af2dd0aa03a34f0997d30db12b03d80a3e3c8e3a',utc=datetime.now(timezone.utc).isoformat(),
        original_source_available=source_available,original_source_sha256=data['source_sha256']))
    began=time.monotonic(); rows=[]; references=[]; records=[]
    try:
        for envelope in CASES:
            tickets=data['cases'][envelope]['tickets']
            for scenario in old.SCENARIOS:
                if time.monotonic()-began>spec['max_wall_s']: raise TimeoutError('bounded PC study')
                incumbents=[]; reference=None
                for policy in ONLINE:
                    row,rr,c,ss,costs=simulate(frozen,initial,tickets,scenario,policy)
                    row.update(envelope=envelope,scenario=scenario,policy=policy,information='online_arrived_queue')
                    rows.append(row);incumbents.append(jobs_from_ledger(rr['ledger']))
                    records.append(dict(meta=row,ledger=rr['ledger'],decisions=rr['decisions'],
                        guards=getattr(c,'records',[]),segments=ss,predicted_ap_path=costs['ap_path']))
                    if policy=='EFT_REFERENCE': reference=row
                winners,stats=search(frozen,initial,tickets,scenario,incumbents,
                    spec['beam_width'],spec['offline_wait_grid_s'],spec['reference_case_timeout_s'])
                references.append(dict(envelope=envelope,scenario=scenario,**stats))
                for objective,jobs in winners.items():
                    row,rr,c,ss,costs=simulate(frozen,initial,tickets,scenario,REPLAY,jobs)
                    validate_schedule(jobs_from_ledger(rr['ledger']),tickets,p.profile(frozen,scenario))
                    if max(abs(j['start']-next(r['dispatch_ns']/1e9 for r in rr['ledger'] if r['id']==j['id'])) for j in jobs)>5e-9:
                        raise ValueError('reference replay timing mismatch')
                    row.update(envelope=envelope,scenario=scenario,policy='OFFLINE_'+objective.upper()+'_REFERENCE',
                        information='future_arrivals_and_scenario_durations',search_timeout=stats['timed_out'])
                    rows.append(row);records.append(dict(meta=row,ledger=rr['ledger'],decisions=rr['decisions'],
                        segments=ss,predicted_ap_path=costs['ap_path']))
                for row in rows:
                    if (row['envelope'],row['scenario'])==(envelope,scenario):
                        for key in ('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms','deadline_met'):
                            row['delta_'+key+'_vs_EFT']=None if row[key] is None or reference[key] is None else row[key]-reference[key]
                fields=sorted(set().union(*(r.keys() for r in rows)))
                old.csv_write(out/'results.csv',[{k:r.get(k) for k in fields} for r in rows])
                p.write(out/'reference_search.json',references)
                p.write(out/'progress.json',dict(cases_complete=len(references),runs=len(rows),elapsed_s=time.monotonic()-began))
                print(envelope,scenario,'runs',len(rows),'search_nodes',stats['expanded_nodes'],flush=True)
    finally:
        with (out/'records.jsonl').open('w',encoding='utf8') as stream:
            for r in records: stream.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    if hashes!={x.relative_to(p.ROOT).as_posix():p.digest(x) for x in sources()}: raise ValueError('source/frozen hash changed')
    p.write(out/'summary.json',dict(spec=spec,runs=len(rows),cases=len(references),elapsed_s=time.monotonic()-began,
        reference_search_timeouts=sum(x['timed_out'] for x in references),hashes_unchanged=True,
        device_commands=0,policy_winner=None,strict_supported=False,experiment_ready=False))
    return out


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--output')
    args=ap.parse_args()
    if args.prepare: prepare()
    elif args.output: print(run(args.output))
    else: ap.error('--prepare or --output required')
