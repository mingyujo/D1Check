"""Whole-request FIFO/EFT controls using only current owners and one ticket."""
import copy
import math
import time
from tools import d1_atc_repair_policy as a

ROLES=("FIFO_FIXED", "FIFO_EFT", "FIFO_READY", "EDD_EFT", "ATC_EFT")

def release(lane, estimates, backend, now):
    if lane['request'] is None:return now
    ds=a.phase_estimate(estimates,lane['request'],backend)
    if ds is None or len(ds)!=5 or any(not math.isfinite(x) or x<0 for x in ds):return None
    phase=a.PHASES.index(lane['phase'])
    end=lane['dispatch']+sum(ds)
    # A prediction never frees a resource, and an observed phase overrun is unknown.
    return end if end>now and lane['dispatch']+sum(ds[:phase+1])>now else None

def eft(q, queue, lanes, now, estimates):
    options=[]
    for b in a.p.backends(q):
        ds=a.durations(estimates,q,b)
        start=release(lanes[b],estimates,b,now)
        other='GPU' if b=='CPU' else 'CPU'
        owner=lanes[other]['request']
        if owner:
            try:a.p.state([q['task']+'_'+b,owner['task']+'_'+other])
            except ValueError:
                other_end=release(lanes[other],estimates,other,now)
                start=max(start,other_end) if start is not None and other_end is not None else None
        j=dict(request_id=q['id'],backend=b)
        options.append(dict(job=j,known=ds is not None and start is not None,
            finish=start+ds[0]*1e9 if ds is not None and start is not None else None,
            available=a.legal(j,queue,lanes)))
    # Unknown is not a zero duration: prefer measured known, then feasible CPU tie.
    return min(options,key=lambda x:(not x['known'],x['finish'] if x['known'] else 0,
        not x['available'],x['job']['backend']!='CPU'))

class Controller(a.Controller):
    def __init__(self,frozen,initial,role):
        if role not in ROLES:raise ValueError('unregistered mobile rule')
        super().__init__(frozen,initial,mode=a.RULE)
        self.role=role;self.public_policy=role;self.rule_log=[]

    def __call__(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        began=time.perf_counter();self.validate_public(queue,lanes,now)
        if any(set(q)!=a.PUBLIC_FIELDS for q in queue):
            raise ValueError('private ticket fields')
        out=dict(now_ns=now,selected=None,reason='resource_event_wait',public_policy=self.public_policy)
        if not queue:return dict(out,reason='empty')
        sig=(tuple(sorted(q['id'] for q in queue)),tuple((b,l['request']['id'] if l['request'] else None) for b,l in lanes.items()))
        if self.hold and self.hold['signature']==sig and (self.hold['until'] is None or now<self.hold['until']):
            return dict(out,reason='resource_hold',**({'wait_until_ns':self.hold['until']} if self.hold['until'] else {}))
        self.hold=None
        key=(now,self.event_seq,sig)
        if key==self.last_key:return dict(out,reason='duplicate_decision_revision')
        self.last_key=key
        atc_start=time.perf_counter()
        scores=a.atc_scores(queue,self.estimates,now,self.settings) if self.role=='ATC_EFT' else {}
        atc_end=time.perf_counter()
        if self.role=='ATC_EFT':
            ordered=sorted(queue,key=lambda q:(scores[q['id']] is None,scores[q['id']] if scores[q['id']] is not None else a.due(q),*a.tie(q)))
        elif self.role=='EDD_EFT':ordered=sorted(queue,key=lambda q:(a.due(q),*a.tie(q)))
        else:ordered=sorted(queue,key=a.tie)
        selected=None
        for q in ordered:
            if self.role in ('FIFO_FIXED','FIFO_READY'):
                j=dict(request_id=q['id'],backend='GPU' if q['task']=='classification' else 'CPU')
                candidate=dict(job=j,available=a.legal(j,queue,lanes),finish=None,known=False)
            else:candidate=eft(q,queue,lanes,now,self.estimates)
            if candidate['available']:selected=candidate['job']
            if selected or self.role!='FIFO_READY':break
        if selected:
            out.update(selected=copy.deepcopy(selected),reason='current_rule_dispatch',action_kind='single')
        else:
            if not any(l['request'] for l in lanes.values()):raise ValueError('idle rule cannot progress')
            ends=[release(l,self.estimates,b,now) for b,l in lanes.items() if l['request']]
            ends=[v for v in ends if v is not None and v>now]
            until=min(ends) if ends else None
            self.hold=dict(signature=sig,until=until);self.stats['wait_selected']+=1
            out.update(action_kind='resource_wait',**({'wait_until_ns':until} if until else {}))
        self.rule_log.append(dict(now_ns=now,head=ordered[0]['id'],selected=selected,queue=len(queue)))
        elapsed=time.perf_counter()-began
        self.times.append(dict(atc_seconds=atc_end-atc_start,candidates_seconds=0.,mask_seconds=0.,
            encode_seconds=0.,inference_seconds=0.,total_seconds=elapsed,queue=len(queue)))
        return out
