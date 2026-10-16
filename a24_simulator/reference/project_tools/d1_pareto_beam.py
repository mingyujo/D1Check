"""Causal queue-calendar beam: unchanged plant, conditional model-only guard."""
import copy
import time
from tools import d1_industrial_scheduling as x
p=x.p
POLICY=p.RECEDING_POLICIES[0]


class Controller(p.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,p.profile(frozen),POLICY)
        self.long=p.Controller(frozen,initial,p.profile(frozen,'long_context'),'EFT_REFERENCE')
        self.records=[];self.callback_times=[]

    def __call__(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        began=time.perf_counter()
        try:return self.decide(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        finally:self.callback_times.append(time.perf_counter()-began)

    def finish_plan(self,sequence,queue,active,now,forecaster):
        jobs=copy.deepcopy(active);by_id={q['id']:q for q in queue};first=None;used=set()
        for rid,b,delay in sequence:
            q=by_id[rid]
            job=forecaster.place(q,b,now+delay if first is None else first['start'],jobs)
            jobs.append(job);used.add(rid)
            if first is None:first=job
        for q in queue:
            if q['id'] in used:continue
            job=min((forecaster.place(q,b,first['start'],jobs) for b in p.backends(q)),key=lambda j:(j['response'],j['backend']!='CPU'))
            jobs.append(job)
        return jobs,first

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        # Preserve original validation and the EFT action even when search fails.
        ref=super().__call__(config,queue,lanes,now_ns,settings,thermal_model,current_ap)
        if not queue or 'chosen_backend' not in ref:return ref
        now=now_ns/1e9;qs=x.ordered(queue,now_ns,settings)
        active=self.active_jobs(lanes,now);running=self.long.active_jobs(lanes,now)
        if active is None or running is None:return dict(ref,reason='beam_unknown_overrun_EFT')
        reference=((qs[0]['id'],ref['chosen_backend'],0.),)
        refjobs,_=self.finish_plan(reference,qs,active,now,self);refscore=self.score(refjobs,now)
        longjobs,_=self.finish_plan(reference,qs,running,now,self.long);ref_lateness=x.lateness(longjobs)
        if refscore is None:return dict(ref,reason='beam_reference_window_unavailable_EFT')
        pool=qs[:4];aged=[q for q in qs if now_ns-q['arrival_ns']>=settings['aging_ns']]
        first_pool=(aged[:4] if aged else pool)
        nodes=[tuple()];accepted=[];expanded=0;guard_veto=0;joint_veto=0
        for depth in range(min(4,len(pool))):
            candidates=[]
            for sequence in nodes:
                used={rid for rid,_,_ in sequence}
                for q in (first_pool if depth==0 else pool):
                    if q['id'] in used:continue
                    for b in p.backends(q):
                        delays=(0.,min(.25,max(0.,2.-(now-q['arrival_ns']/1e9)))) if depth==0 else (0.,)
                        for delay in sorted(set(delays)):
                            if expanded>=64:break
                            proposed=sequence+((q['id'],b,delay),);expanded+=1
                            jobs,first=self.finish_plan(proposed,qs,active,now,self)
                            # A forecast cannot release an actual lane, and no
                            # artificial callback is allowed before the first action.
                            if first['start']>now+2.+1e-9:continue
                            score=self.score(jobs,now)
                            if score is None:continue
                            guardjobs,_=self.finish_plan(proposed,qs,running,now,self.long)
                            veto=x.guard_worsens(x.lateness(guardjobs),ref_lateness)
                            if veto:guard_veto+=1;continue
                            # This is a conditional arrived-queue prediction,
                            # never a guarantee about unobserved future requests.
                            if (score['remaining_energy_j']>refscore['remaining_energy_j']+1e-9 or
                                    score['predicted_peak_ap_c']>refscore['predicted_peak_ap_c']+1e-9):
                                joint_veto+=1;continue
                            rank=(round(score['remaining_energy_j'],9),round(score['predicted_peak_ap_c'],9),first['response'],proposed)
                            candidates.append((rank,proposed,first,score));accepted.append((rank,proposed,first,score))
                        if expanded>=64:break
                    if expanded>=64:break
                if expanded>=64:break
            if not candidates or expanded>=64:break
            nodes=[entry[1] for entry in sorted(candidates,key=lambda a:a[0])[:8]]
        log=dict(now_ns=now_ns,arrived_ids=[q['id'] for q in qs],expanded=expanded,
            guard_veto=guard_veto,joint_veto=joint_veto,reference=refscore,accepted=len(accepted))
        self.records.append(log)
        if not accepted:return dict(ref,reason='beam_no_joint_admitted_calendar_EFT')
        _,sequence,first,score=min(accepted,key=lambda a:a[0]);rid,b,delay=sequence[0]
        log.update(selected_sequence=sequence,prediction=score)
        out=dict(now_ns=now_ns,selected=None,reason=POLICY,chosen_request_id=rid,chosen_backend=b,
            chosen_explicit_delay_s=delay,planned_start_s=first['start'],modeled_ap_c=self.t,
            local_deviation=(rid,b,delay)!=reference[0])
        if first['start']<=now+1e-9:out['selected']=dict(request_id=rid,backend=b)
        else:out['wait_until_ns']=max(now_ns+1.,first['start']*1e9)
        return out


def simulate(frozen,initial,tickets,scenario):
    c=Controller(frozen,initial)
    vectors=dict(cells={k:[dict(source_request_id='fixed_context_'+scenario,durations_ns=v) for _ in range(4)]
        for k,v in p.profile(frozen,scenario).items()})
    rr=x.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=POLICY,settings=x.settings(),seed=201,decision_provider=c)
    row,ss,cost=x.outcome(rr,initial,frozen)
    row.update(decision_host_total_s=sum(c.callback_times),decision_host_max_ms=1000*max(c.callback_times,default=0),
        expanded_calendars=sum(v['expanded'] for v in c.records),
        local_deviations=sum(d.get('local_deviation',False) for d in rr['decisions']),
        wait_actions=sum(d.get('chosen_explicit_delay_s',0)>0 and d['selected'] is None for d in rr['decisions']))
    return row,rr,c,ss,cost
