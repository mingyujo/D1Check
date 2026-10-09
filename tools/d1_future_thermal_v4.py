"""Observed-history future-task scenarios inside prediction only.

Robust and empirical-score rules share real actions, service/J guards and the
same fixed phase contexts. No virtual request is admitted to the real engine.
"""
import copy,math
from tools import d1_fast_thermal_forecast as fast
old=fast.old;p=fast.p
ROBUST='IE_FUTURE_THERMAL_ROBUST_025_V4'
EMPIRICAL='IE_FUTURE_THERMAL_EMPIRICAL_025_V4'

class Controller(fast.Controller):
    def __init__(self,frozen,initial,policy):
        if policy not in (ROBUST,EMPIRICAL):raise ValueError('unregistered future policy')
        super().__init__(frozen,initial);self.public_policy=policy;self.observations={};self.probe_records=[];self.live_scenarios=[]

    def scenarios(self,now):
        observed=sorted(self.observations.values(),key=lambda q:(q['arrival_ns'],q['id']))[-9:]
        if len(observed)<3:return []
        gaps=[b['arrival_ns']-a['arrival_ns'] for a,b in zip(observed,observed[1:])][-8:]
        if min(gaps)<=0:return []
        endpoints=sorted({min(gaps),max(gaps)});last=observed[-1]['arrival_ns'];recent=observed[-8:]
        total=len(recent)+2;scenario=[dict(name='no_arrival',weight=0.,probes=[])]
        for i,gap in enumerate(endpoints):
            at=last+gap
            if at<=now:return []
            for task,priority,deadline in (('classification','urgent',1500000000),('detection','normal',6000000000)):
                q=dict(id=f'__forecast_v4__/{i}/{task}',ordinal=1000000+i*2+(task=='detection'),task=task,priority=priority,arrival_ns=at,deadline_offset_ns=deadline)
                probability=(sum(r['task']==task for r in recent)+1)/total/len(endpoints)
                scenario.append(dict(name=f'{task}_{i}',weight=probability,probes=[q]))
        return scenario

    def physical_candidates(self,queue,lanes,now,base):
        actions=super().physical_candidates(queue,lanes,now,base)
        # Intentional width ablation: the new intervention is normal idle timing,
        # while native Band chooses the actual request/resource.
        actions=[a for a in actions if a['base'] or a['kind']=='cool_wait']
        self.live_scenarios=self.scenarios(now) if len(actions)>1 else []
        if not self.live_scenarios:return [a for a in actions if a['base']]
        self.probe_records.append(dict(now_ns=now,observed_requests=len(self.observations),scenarios=copy.deepcopy(self.live_scenarios)))
        return actions

    def forecast(self,queue,lanes,now,action,context):
        plain=fast.forecast(self,queue,lanes,now,action,context)
        plain['scenarios']={}
        for scenario in self.live_scenarios:
            value=plain if not scenario['probes'] else fast.forecast(self,queue,lanes,now,action,context,scenario['probes'])
            plain['scenarios'][scenario['name']]=dict(value,weight=scenario['weight']) if scenario['probes'] else {k:v for k,v in plain.items() if k!='scenarios'}|dict(weight=0.)
        return plain

    def select(self,actions):
        base=next(a for a in actions if a['base']);candidate=next((a for a in actions if a['kind']=='cool_wait'),None)
        if candidate is None:return base
        scores=[]
        for context in old.core.CONTEXTS:
            f=candidate['forecasts'][context];r=base['forecasts'][context]
            if not f['valid'] or not r['valid'] or not f['feasible'] or not r['feasible']:return base
            differences=[];weighted=0.
            for name,fc in f['scenarios'].items():
                rc=r['scenarios'][name]
                if not fc['valid'] or not rc['valid'] or not fc['feasible'] or not rc['feasible']:return base
                if fc['urgent_misses']>rc['urgent_misses'] or fc['normal_misses']>rc['normal_misses'] or fc['remaining_increment_j']>rc['remaining_increment_j']+old.EPS:return base
                if fc['urgent_p95_ms'] is not None and rc['urgent_p95_ms'] is not None and fc['urgent_p95_ms']>rc['urgent_p95_ms']+old.EPS:return base
                if any(fc['probe_urgent_ms'][identifier]>ms+old.EPS for identifier,ms in rc['probe_urgent_ms'].items()):return base
                delta=fc['peak_ap_c']-rc['peak_ap_c'];differences.append(delta);weighted+=fc['weight']*delta
                if (name=='no_arrival' or self.public_policy==ROBUST) and fc['global_peak_ap_c']>rc['global_peak_ap_c']+old.EPS:return base
            scores.append(max(differences) if self.public_policy==ROBUST else weighted)
        return candidate if max(scores)<-old.EPS else base

    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]:
            self.observations.setdefault(q['id'],dict(q));self.arrival_history.setdefault(q['id'],q['arrival_ns'])
        # No forecasts are needed when the workload gate removes cooling.
        base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if not queue or not self.response_counters_valid or self.active_jobs(lanes,now/1e9) is None:return dict(base,public_policy=self.public_policy,forced=True)
        actions=self.physical_candidates(queue,lanes,now,base)
        if len(actions)==1:return dict(base,public_policy=self.public_policy)
        for a in actions:a['forecasts']={ctx:self.forecast(queue,lanes,now,a,ctx) for ctx in old.core.CONTEXTS}
        chosen=self.select(actions);out=dict(base,public_policy=self.public_policy) if chosen['base'] else self._reply(chosen,now)
        self.choice_records.append(dict(t_s=now/1e9,kind=chosen['kind'],chosen_base=chosen['base'],credit_s=self.credit,available=len(actions),scenario_count=len(self.live_scenarios)))
        return out
