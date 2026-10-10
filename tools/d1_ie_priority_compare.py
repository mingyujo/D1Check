"""Nonpreemptive response-deadline adaptations of MS, CR and ATC.

All share the existing five-phase ECT routing. PROTECT is our own explicit
MST routing modification, inspired by machine eligibility, not a reproduction
of the preemptive LFJ-FM theorem. No training or device operation on import.
"""
from __future__ import annotations
import math
from tools import d1_external_rules as external

p=external.p
POLICIES={
    'EDD':'IE_EDD_ECT_EQUIVALENT_PC_V2',
    'MST':'IE_MST_RESPONSE_ECT_ADAPT_PC_V1',
    'CR':'IE_CR_RESPONSE_LEAD_ECT_ADAPT_PC_V1',
    'ATC':'IE_ATC_RESPONSE_LANE_ADAPT_PC_V1',
    'PROTECT':'IE_MST_CPU_TARDINESS_PROTECT_PC_V1',
}
ATC_K=2.


def score(rule,request,choice,now,mean_lane_service,service_lane,k=ATC_K):
    due=(request['arrival_ns']+request['deadline_offset_ns'])/1e9
    slack=due-choice['response']
    if rule=='EDD':return due
    if rule in ('MST','PROTECT'):return slack
    if rule=='CR':
        lead=choice['response']-now
        if lead<=0:raise ValueError('unknown/nonpositive response lead')
        return (due-now)/lead
    if rule=='ATC':
        if min(service_lane,mean_lane_service,k)<=0:raise ValueError('invalid ATC observed quantities/config')
        # Larger classical ATC index first; use its negative log to avoid underflow.
        # w_j=1 is prespecified. Urgency uses our response boundary, density lane5.
        return math.log(service_lane)+max(0.,slack)/(k*mean_lane_service)
    raise ValueError('unknown priority rule')


class Controller(external.Timed):
    def __init__(self,frozen,initial,rule):
        if rule not in POLICIES:raise ValueError('unknown IE adaptation')
        super().__init__(frozen,initial)
        self.rule=rule;self.public_policy=POLICIES[rule]
        self.protect_count=0
        self.decision_records=[]

    def detector_projection(self,queue,active,first,now):
        """Same arrived CPU-only detector work; other queued classifiers omitted.

        This is a bounded current-load projection, not a future-load forecast.
        It is used only to distinguish two routes of the same first classifier.
        """
        jobs=[dict(j) for j in active]+[dict(first)]
        projected=[]
        for q in sorted((q for q in queue if q['task']=='detection'),
                        key=lambda q:(q['arrival_ns'],q['ordinal'],q['id'])):
            j=self.place(q,'CPU',now,jobs);jobs.append(j)
            projected.append(dict(request_id=q['id'],start=j['start'],response=j['response'],end=j['end'],
                due=j['deadline'],late=j['response']>j['deadline']))
        return projected

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now_ns)
        now=now_ns/1e9
        out=dict(now_ns=now_ns,selected=None,reason='empty',public_policy=self.public_policy,
            modeled_ap_c=self.t,sequencing_rule=self.rule,candidates=[])
        if not queue:return out
        active=self.active_jobs(lanes,now)
        if active is None:return dict(out,reason='unknown_overrun_wait_for_public_event')
        route={};options={};service={}
        for q in queue:
            choices=[self.place(q,b,now,active) for b in p.backends(q)]
            selected=min(choices,key=lambda j:(j['end'],j['backend']!='CPU'))
            options[q['id']]=choices;route[q['id']]=selected
            service[q['id']]=sum(self.estimates[p.key(q,selected['backend'])])/1e9
        mean_service=sum(service.values())/len(queue)
        scores={q['id']:score(self.rule,q,route[q['id']],now,mean_service,service[q['id']]) for q in queue}
        ordered=sorted(queue,key=lambda q:(scores[q['id']],q['arrival_ns'],q['ordinal'],q['id']))
        q=ordered[0];chosen=route[q['id']];protection=None
        if self.rule=='PROTECT' and q['task']=='classification' and chosen['backend']=='CPU':
            gpu=next(j for j in options[q['id']] if j['backend']=='GPU')
            cpu_D=self.detector_projection(queue,active,chosen,now)
            gpu_D=self.detector_projection(queue,active,gpu,now)
            cpu_misses=sum(j['late'] for j in cpu_D);gpu_misses=sum(j['late'] for j in gpu_D)
            # No invented slack threshold, CPU utilization bound or urgent weight.
            allowed=gpu['response']<=gpu['deadline'] and gpu_misses<cpu_misses
            protection=dict(CPU_route_expected_D_misses=cpu_misses,GPU_route_expected_D_misses=gpu_misses,
                classification_GPU_response=gpu['response'],classification_due=gpu['deadline'],
                GPU_route_allowed=allowed,current_D_work=len(cpu_D),future_arrivals_used=False)
            if allowed:chosen=gpu;self.protect_count+=1
        out.update(head_request_id=q['id'],ordered_ids=[q['id'] for q in ordered],priority_scores=scores,
            ATC_k=ATC_K if self.rule=='ATC' else None,ATC_weights='all1' if self.rule=='ATC' else None,
            candidates=options[q['id']],chosen_backend=chosen['backend'],planned_start_s=chosen['start'],
            predicted_response_s=chosen['response'],predicted_lane_end_s=chosen['end'],CPU_protection=protection,
            predicted_service_guarantee=False)
        self.decision_records.append(dict(out))
        if chosen['start']>now+1e-9:
            return dict(out,reason='ECT_wait_for_best_resource',wait_until_ns=max(now_ns+1.,chosen['start']*1e9))
        if lanes[chosen['backend']]['request'] is not None:
            return dict(out,reason='actual_lane_still_owned_wait_for_public_event')
        members=[j['request']['task']+'_'+b for b,j in lanes.items() if j['request']]
        p.state(members+[q['task']+'_'+chosen['backend']])
        return dict(out,selected=dict(request_id=q['id'],backend=chosen['backend']),reason=self.public_policy)
