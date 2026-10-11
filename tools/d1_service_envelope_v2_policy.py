"""Narrow V2: remove CPU-only response equality, rank P95 before ECT.

This partially aligns an internal guard with the actual deadline KPI. It does
not make a current-prefix P95 estimate a full-trace service guarantee. V1 and
its fresh PPO source/weights remain untouched. The shared finite dispatcher
continuation remains a service/ECT approximation, not exact recursive rollout.
"""
import numpy as np
from tools import d1_service_envelope_policy as x
COST='IE_JOINT_SERVICE_ENVELOPE_COST_LIST_V2'
SCHEMA=x.r.c.digest(dict(parent=x.SCHEMA,version=COST,rank='miss/lateness,P95,ECT,AP,J',removed='CPU-only individual response nonworsening',continuation='unchanged shared finite compatible EDD service dispatcher'))

class Controller(x.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,x.COST);self.schema_id=SCHEMA;self.public_policy=COST
    def encode(self,queue,lanes,now,actions,window):
        e=super().encode(queue,lanes,now,actions,window);risk=e['risk'];early=[]
        for i,fs in enumerate(e['forecasts']):
            allowed,reason=x.Controller.admission(self,e['actions'][i],fs,[],queue,now,risk)
            early.append((bool(e['physical_mask'][i]) and allowed,reason))
        valid=[i for i,(ok,_) in enumerate(early) if ok]
        def key(i):
            fs=e['forecasts'][i];ss=[x.service(f,queue,lanes) for f in fs]
            return tuple(max(q[j] for q in ss) for j in range(4))+(max((f['urgent_p95_ms'] or 0) for f in fs),max(f['lane_end_s'] for f in fs),max(f['global_peak_ap_c'] for f in fs),max(f['remaining_increment_j'] for f in fs),i!=0,i)
        reference=min(valid,key=key) if valid else 0;order=[reference]+[i for i in range(len(e['actions'])) if i!=reference]
        for name in ('actions','forecasts','admissions'):e[name]=[e[name][i] for i in order]
        for name in ('candidates','mask','physical_mask'):
            value=e[name].copy();e[name][:len(order)]=value[order]
        early=[early[i] for i in order];refs=e['forecasts'][0]
        e['candidates'][:,x.r.CANDIDATE_NAMES.index('is_L0')]=0.;e['candidates'][0,x.r.CANDIDATE_NAMES.index('is_L0')]=1.
        for i,fs in enumerate(e['forecasts']):
            ok,reason=early[i]
            known=all(f['valid'] and ref['valid'] for f,ref in zip(fs,refs))
            if i and ok and known:
                ok=all(x.service(f,queue,lanes)==x.service(ref,queue,lanes) and (f['urgent_p95_ms'] or 0)<=(ref['urgent_p95_ms'] or 0)+1e-9 for f,ref in zip(fs,refs))
                reason='V2_current_service_P95_envelope' if ok else 'V2_current_service_P95_rejected'
            e['mask'][i]=bool(e['physical_mask'][i]) and (i==0 or ok)
            e['admissions'][i]='JointV2_reference' if i==0 else reason
            if not known:continue
            for name,field,scale in (('worst_delta_J','remaining_increment_j',1),('worst_delta_global_AP','global_peak_ap_c',1),('worst_delta_future_AP','peak_ap_c',1),('worst_delta_urgent_P95_over1500','urgent_p95_ms',1500),('worst_delta_urgent_misses','urgent_misses',1),('worst_delta_normal_misses','normal_misses',1)):
                e['candidates'][i,x.r.CANDIDATE_NAMES.index(name)]=max(((f[field] or 0)-(ref[field] or 0))/scale for f,ref in zip(fs,refs))
            for priority,name,scale in (('normal','worst_normal_response_delta_over6',6),('urgent','worst_urgent_response_delta_over1p5',1.5)):
                e['candidates'][i,x.r.CANDIDATE_NAMES.index(name)]=max([0]+[(f['responses'][q['id']]-ref['responses'][q['id']])/scale for f,ref in zip(fs,refs) for q in queue if q['priority']==priority])
        e.update(schema_id=SCHEMA,base=0,CPU_only_individual_response_guard_removed=True,P95_priority_before_drain=True,prediction_guard_is_service_guarantee=False)
        return e
