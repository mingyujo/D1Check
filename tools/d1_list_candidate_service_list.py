"""Same-bank service-first, equal-work forecast selector. No RL training."""
from __future__ import annotations
import math
from tools import d1_list_candidate_rl as c

POLICY='LIST_SERVICE_EQUAL_WORK_BOUNDED_D_WAIT_PC_V1'
REQUEST_WAIT_CAP=.25

class ServiceList(c.Controller):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.public_policy=POLICY
        self.request_wait={}
        self.fair_work_records=[]
    def _debit(self,now):
        held=list(self.hold['held']) if self.hold else []
        before=self.deferred_seconds
        super()._debit(now)
        delta=self.deferred_seconds-before
        for rid in held:self.request_wait[rid]=self.request_wait.get(rid,0.)+delta
    def admitted(self,index,encoded,actions,queue):
        forecast=encoded['raw'][index];baseline=encoded['raw'][encoded['base']]
        if not forecast['known'] or not baseline['known']:return False
        action=actions[index];heads=c.heads_of(queue)
        if any(self.request_wait.get(rid,0.)+action['wait']>REQUEST_WAIT_CAP for rid in action['held']):return False
        if heads['classification']:
            cq=heads['classification'];rid=cq['id']
            if rid in action['held']:return False
            if forecast['prediction'][rid]['response']>baseline['prediction'][rid]['response']:return False
        if heads['detection']:
            dq=heads['detection'];rid=dq['id'];due=c.due(dq)/1e9
            new=max(0.,forecast['prediction'][rid]['response']-due)
            old=max(0.,baseline['prediction'][rid]['response']-due)
            if new>old:return False
        return True
    def work_intervals(self,forecast,queue):
        jobs=list(forecast['active'])
        for q in c.heads_of(queue).values():
            if q:
                p=forecast['prediction'][q['id']]
                jobs.append(dict(task=q['task'],backend=p['backend'],start=p['start'],end=p['end']))
        return jobs
    def work_cost(self,jobs,now,end):
        segments=c.p.segments([dict(state=j['task']+'_'+j['backend'],start=j['start'],end=j['end']) for j in jobs],now,end)
        t,h=self.t,self.h
        peak=max([self.t,*self.grid.values()]);energy=self.initial['preload_power_w']*(end-now)
        slopes=self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        for segment in segments:
            label='resident_idle' if segment['state']=='idle' else segment['state']
            if label!='resident_idle' and label not in self.frozen['energy_increment_w']:
                raise c.formula.PredictionUnknown('unsupported equal-work energy state')
            a,b=segment['start_s'],segment['end_s']
            energy+=(b-a)*self.frozen['energy_increment_w'].get(label,0.)
            u=slopes[label]-slopes['resident_idle']
            for point in sorted({b}|{float(x) for x in range(math.ceil(a),math.floor(b)+1) if x>a}):
                peak=max(peak,c.p.thermal_step(t,h,u,self.init['reference_c'],self.frozen['ap'],point-a)[0])
            t,h=c.p.thermal_step(t,h,u,self.init['reference_c'],self.frozen['ap'],b-a)
        return dict(energy=energy,peak_ap=peak,end_ap=t,horizon_end=end,work_count=len(jobs))
    def choose(self,encoded,actions,queue):
        base=encoded['base'];now=encoded['now_ns']/1e9
        if not encoded['raw'][base]['known']:
            self.fallbacks+=1;return base
        eligible=[i for i in range(len(actions)) if self.admitted(i,encoded,actions,queue)]
        if base not in eligible:raise ValueError('service baseline must remain admissible')
        work={i:self.work_intervals(encoded['raw'][i],queue) for i in eligible}
        end=max([now]+[j['end'] for jobs in work.values() for j in jobs])
        if end>120:
            self.fallbacks+=1;return base
        try:costs={i:self.work_cost(jobs,now,end) for i,jobs in work.items()}
        except c.formula.PredictionUnknown:
            self.fallbacks+=1;return base
        counts={v['work_count'] for v in costs.values()}
        if len(counts)!=1:raise ValueError('unequal current-head work compared')
        # Do not buy predicted cooling by worsening predicted equal-work J.
        accepted=[i for i in eligible if costs[i]['energy']<=costs[base]['energy']]
        selected=min(accepted,key=lambda i:(costs[i]['peak_ap'],costs[i]['end_ap'],costs[i]['energy'],i!=base,i))
        self.fair_work_records.append(dict(at_ns=encoded['now_ns'],eligible=eligible,accepted=accepted,
          selected=selected,base=base,common_end=end,costs=costs,request_wait=dict(self.request_wait),
          scope='current owned plus both FIFO heads, frozen mean; no future arrivals/full queue/guarantee'))
        return selected
