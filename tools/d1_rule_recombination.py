"""Immediate, arrived-three-request recombination of the existing beam rules."""
from __future__ import annotations
import copy
import itertools
import json
from pathlib import Path
import time
from tools import d1_joint_queue_area as area
from tools import d1_queue_ppo_v2 as v
from tools import d1_rules_rl_common as common

P = v.q.p
PREFIX = 'PREFIX3_IMMEDIATE'
COMPLETE = 'COMPLETE3_IMMEDIATE'


class Controller(area.Controller):
    """Same forecasts, continuation, service/J/peak/area guard; no added WAIT.

    Prefix A applies the existing veto before keeping the best eight prefixes.
    Complete B evaluates all complete permutations/backend assignments before
    applying the identical veto. The reference continuation is retained by both.
    The old four-request/WAIT-enabled source is intentionally not modified.
    """
    def __init__(self, frozen, initial, mode):
        super().__init__(frozen, initial)
        if mode not in (PREFIX, COMPLETE): raise ValueError('mode')
        self.mode=mode

    def search(self, qs, active, running, now, ref_backend, settings):
        self.reference_area=None
        reference=((qs[0]['id'],ref_backend,0.),)
        refjobs,ref_first=self.finish_plan(reference,qs,active,now,self)
        refscore=self.score(refjobs,now)
        if refscore is None: return reference,ref_first,dict(unavailable=True)
        ref_long,_=self.finish_plan(reference,qs,running,now,self.long)
        ref_lateness=area.x.lateness(ref_long)
        pool=qs[:3]
        aged=[q for q in qs if now-q['arrival_ns']/1e9>=settings['aging_ns']/1e9]
        first_ids={q['id'] for q in (aged[:3] if aged else pool)}
        outcomes={}; projections=0

        def evaluate(sequence):
            nonlocal projections
            if sequence in outcomes:return outcomes[sequence]
            projections+=1
            jobs,first=self.finish_plan(sequence,qs,active,now,self)
            guardjobs,_=self.finish_plan(sequence,qs,running,now,self.long)
            score=self.score(jobs,now)
            reasons=[]
            if first['start']>now+1e-9:reasons.append('not_immediate')
            if sequence[0][0] not in first_ids:reasons.append('aging')
            if area.x.guard_worsens(area.x.lateness(guardjobs),ref_lateness):reasons.append('service')
            if score is None:reasons.append('window_or_AP_area')
            elif (score['remaining_energy_j']>refscore['remaining_energy_j']+1e-9 or
                  score['predicted_peak_ap_c']>refscore['predicted_peak_ap_c']+1e-9):reasons.append('J_or_peak')
            rank=((round(score['remaining_energy_j'],9),round(score['predicted_peak_ap_c'],9),
                   first['response'],sequence) if score else (float('inf'),float('inf'),first['response'],sequence))
            outcomes[sequence]=(not reasons,rank,first,score,reasons)
            return outcomes[sequence]

        # A and B share this exact candidate space; an accepted reference is
        # always an incumbent, including when its first action must await a lane.
        nodes=[tuple()]; prefix_accepted=[]; reached_leaves=set(); expanded=0
        for depth in range(len(pool)):
            admitted=[]
            for sequence in nodes:
                used={x[0] for x in sequence}
                for q in pool:
                    if q['id'] in used:continue
                    for backend in P.backends(q):
                        if expanded>=64:break
                        candidate=sequence+((q['id'],backend,0.),);expanded+=1
                        ok,rank,first,score,_=evaluate(candidate)
                        if ok:
                            admitted.append((rank,candidate,first,score));prefix_accepted.append((rank,candidate,first,score))
                            if depth==len(pool)-1:reached_leaves.add(candidate)
            if not admitted:break
            nodes=[x[1] for x in sorted(admitted,key=lambda x:x[0])[:8]]
        all_complete=[]
        for ordering in itertools.permutations(pool):
            for assignments in itertools.product(*(P.backends(q) for q in ordering)):
                sequence=tuple((q['id'],backend,0.) for q,backend in zip(ordering,assignments))
                all_complete.append(sequence)
        eligible_complete=[]
        for sequence in all_complete:
            ok,rank,first,score,_=evaluate(sequence)
            if ok:eligible_complete.append((rank,sequence,first,score))
        candidates=prefix_accepted if self.mode==PREFIX else eligible_complete
        candidates.append(((round(refscore['remaining_energy_j'],9),round(refscore['predicted_peak_ap_c'],9),
                            ref_first['response'],reference),reference,ref_first,refscore))
        _,selected,first,score=min(candidates,key=lambda x:x[0])
        missed=[sequence for _,sequence,_,_ in eligible_complete if sequence not in reached_leaves]
        log=dict(arrived_ids=[q['id'] for q in qs],pool_ids=[q['id'] for q in pool],
            complete_candidates=len(all_complete),legal_complete=sum('not_immediate' not in outcomes[s][4] and 'aging' not in outcomes[s][4] for s in all_complete),
            projections=projections,prefix_expanded=expanded,prefix_eligible=len(prefix_accepted),
            complete_eligible=len(eligible_complete),missed_eligible_complete=len(missed),
            missed_sequences=missed,selected_sequence=selected,reference_sequence=reference,
            prediction=score,reference_prediction=refscore,
            missed_first_actions=sorted({sequence[0][:2] for sequence in missed}),
            completed_evaluation_before_veto=True,added_WAIT=False)
        return selected,first,log

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        # Invoke the original EFT boundary, including public-lane validation and
        # observation updates. No trace family/seed/scenario reaches this method.
        ref=P.Controller.__call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or 'chosen_backend' not in ref:return ref
        now=now_ns/1e9;qs=area.x.ordered(queue,now_ns,settings)
        active=self.active_jobs(lanes,now);running=self.long.active_jobs(lanes,now)
        if active is None or running is None:return dict(ref,reason='recombination_unknown_overrun_EFT')
        sequence,first,log=self.search(qs,active,running,now,ref['chosen_backend'],settings)
        log.update(now_ns=now_ns,mode=self.mode);self.records.append(log)
        rid,backend,_=sequence[0]
        out=dict(now_ns=now_ns,selected=None,reason=self.mode,chosen_request_id=rid,chosen_backend=backend,
            chosen_explicit_delay_s=0.,planned_start_s=first['start'],modeled_ap_c=self.t,
            local_deviation=(rid,backend)!=(qs[0]['id'],ref['chosen_backend']))
        if first['start']<=now+1e-9:out['selected']=dict(request_id=rid,backend=backend)
        else:out['wait_until_ns']=max(now_ns+1,round(first['start']*1e9))
        return out


def simulate(frozen,initial,tickets,context,mode):
    c=Controller(frozen,initial,mode)
    vectors=dict(cells={k:[dict(source_request_id='unchanged_'+context,durations_ns=d) for _ in range(4)]
                       for k,d in P.profile(frozen,context).items()})
    result=v.q.old.engine.simulate(dict(protocol=P.VERSION,cells=P.profile(frozen)),vectors,tickets,
        policy=c.policy,settings=area.x.settings(),seed=201,decision_provider=c)
    row,extra=v.q.prev.outcome(result,initial,frozen)
    row['equal_work']=all(r.get('lane_available_ns',float('inf'))<=120e9 for r in result['ledger'])
    v.add_service_metrics(row,result)
    row.update(decision_host_total_s=sum(c.callback_times),decision_host_max_ms=1000*max(c.callback_times,default=0),
        projections=sum(r.get('projections',0) for r in c.records),
        missed_eligible_complete=sum(r.get('missed_eligible_complete',0) for r in c.records),
        local_deviations=sum(d.get('local_deviation',False) for d in result['decisions']))
    return row,result,c,extra


def small_tickets(pattern,seed):
    # A deliberately simultaneous, arrived-only microcase. Not an altered full
    # workload or a physical arrival measurement. Exact bytes are preregistered.
    tasks=('classification','classification','detection') if pattern=='CCD' else ('classification','detection','detection')
    arrival=v.q.old.workload('low',seed)[2]['arrival_ns']
    return [dict(id=f'micro_{seed}_{i}',ordinal=i,task=task,
        priority='urgent' if task=='classification' else 'normal',arrival_ns=arrival,
        deadline_offset_ns=1500000000 if task=='classification' else 6000000000) for i,task in enumerate(tasks)]


def run(folder=common.OUTPUT):
    folder=Path(folder);out=folder/'recombination';out.mkdir(exist_ok=False)
    frozen,initial_case=P.inputs(P.BUNDLE);initial={k:initial_case['initial'][k] for k in ('preload','preload_power_w')}
    budget=common.Budget(folder)
    contract=dict(version='arrived-three-immediate-recombination-v1',
        methods=['EFT_REFERENCE',PREFIX,COMPLETE],pool=3,prefix_width=8,prefix_node_cap=64,
        guard='unchanged long-context per-request lateness + mean J/peak + rectified future AP area vs EFT',
        rank='J,peak,first response,sequence; numeric equality 1e-9',added_WAIT=False,
        development=[610710001,610710002],confirmation=[610720001,610720002],
        historical_exposure='both seed ranges already registered; synthetic microcases newly composed, not independent device/holdout evidence',
        patterns=['CCD','CDD'],contexts=list(v.q.old.SCENARIOS),
        selection='service-worse cases,heat-worse cases,J-worse cases,meanJ,meanArea,method order EFT/A/B',
        early_stop_expansion='if no distinct legal selected actions on development microcases, no broader workload expansion',
        model_sha256=P.MODEL_SHA,initial_sha256=P.INITIAL_SHA,device_commands=0,experiment_ready=False)
    common.atomic(out/'contract_before_run.json',dict(contract=contract,source_sha256=common.digest(__file__)))
    inputs=[dict(stage=stage,seed=seed,pattern=pattern,tickets=small_tickets(pattern,seed))
        for stage,seeds in [('development',contract['development']),('confirmation',contract['confirmation'])]
        for seed in seeds for pattern in contract['patterns']]
    common.atomic(out/'inputs.json',inputs)
    rows=[];details=[];selection=None
    for stage in ('development','confirmation'):
        if stage=='confirmation':
            refs={(r['seed'],r['pattern'],r['context']):r for r in rows if r['policy']=='EFT_REFERENCE'}
            ranks=[]
            for mode in contract['methods']:
                rs=[r for r in rows if r['policy']==mode]
                pairs=[(r,refs[r['seed'],r['pattern'],r['context']]) for r in rs]
                ranks.append(((sum(r['deadline_met']<b['deadline_met'] or r['completed']<b['completed'] for r,b in pairs),
                    sum(r['peak_ap_c']>b['peak_ap_c']+1e-9 or r['thermal_degree_seconds']>b['thermal_degree_seconds']+1e-9 for r,b in pairs),
                    sum(r['energy_j']>b['energy_j']+1e-9 for r,b in pairs),sum(r['energy_j'] for r in rs)/len(rs),
                    sum(r['thermal_degree_seconds'] for r in rs)/len(rs),contract['methods'].index(mode)),mode))
            selection=min(ranks)[1]
            distinct=sum(d['policy']!= 'EFT_REFERENCE' and d['signature']!=next(
                r['signature'] for r in details if (r['stage'],r['seed'],r['pattern'],r['context'],r['policy'])==
                ('development',d['seed'],d['pattern'],d['context'],'EFT_REFERENCE')) for d in details if d['stage']=='development')
            common.atomic(out/'freeze_before_confirmation.json',dict(selected=selection,ranks=ranks,distinct_development_schedules=distinct,
                input_sha256=common.digest(out/'inputs.json'),source_sha256=common.digest(__file__),frozen_utc=common.utc()))
        for case in [x for x in inputs if x['stage']==stage]:
            for context in contract['contexts']:
                for mode in contract['methods']:
                    fn=(lambda: v.simulate(frozen,initial,case['tickets'],context,'EFT_REFERENCE')) if mode=='EFT_REFERENCE' else (
                        lambda: simulate(frozen,initial,case['tickets'],context,mode))
                    row,result,c,_=budget.execute('recombination',stage,fn,seed=case['seed'],pattern=case['pattern'],context=context,policy=mode)
                    row=dict(stage=stage,seed=case['seed'],pattern=case['pattern'],context=context,policy=mode,**row)
                    signature=[(r['ordinal'],r.get('backend'),r.get('dispatch_ns')) for r in sorted(result['ledger'],key=lambda r:r['ordinal'])]
                    detail=dict(stage=stage,seed=case['seed'],pattern=case['pattern'],context=context,policy=mode,
                        signature=signature,ledger=result['ledger'],decisions=result['decisions'],search=c.records if c else [])
                    rows.append(row);details.append(detail)
                    common.append(out/'rows.jsonl',row);common.append(out/'local_details.jsonl',detail)
                    budget.publish(stage='recombination_'+stage)
    common.atomic(out/'summary.json',dict(status='completed',rows=len(rows),selected=selection,
        distinct_development_schedules=common.read(out/'freeze_before_confirmation.json')['distinct_development_schedules'],
        environment_runs=len(rows),device_commands=0,experiment_ready=False))
    return selection


if __name__=='__main__': print(run())
