"""Posthoc completed-ledger service loss diagnosis, zero new environments."""
import gzip,json
from collections import Counter
from tools import d1_service_envelope_v2_run as d
def readraw(role,j):return json.loads(gzip.decompress((d.LOCAL/'items'/f'confirmation_{role}_{j:02d}.json.gz').read_bytes()))
def dispatches(raw):
    out={}
    for q in raw['result']['ledger']:out.setdefault(q['dispatch_ns'],set()).add((q['id'],q['backend']))
    return out
def run():
    d.check();data=d.read(d.LOCAL/'inputs.json');rows=[];first=[];groups={};counts=Counter()
    for case in data['confirmation']:
        j=case['condition'];b=readraw('Band',j);n=readraw('CostV2',j);bb={q['id']:q for q in b['result']['ledger']};nn={q['id']:q for q in n['result']['ledger']}
        extra=[q for q in nn.values() if q['priority']=='normal' and q['late_success'] and not bb[q['id']]['late_success']]
        recovered=[q for q in nn.values() if q['priority']=='normal' and not q['late_success'] and bb[q['id']]['late_success']]
        for q in extra:rows.append(dict(condition=j,seed=case['seed'],family=case['family'],context=case['context'],request_id=q['id'],Band_response_ms=bb[q['id']]['response_ns']/1e6,CostV2_response_ms=q['response_ns']/1e6,deadline_ms=q['deadline_offset_ns']/1e6,Band_dispatch_ns=bb[q['id']]['dispatch_ns'],CostV2_dispatch_ns=q['dispatch_ns'],backend=q['backend'],case_cooling_count=n['cooling_count'],case_extra_cooling_seconds=n['total_extra_wait']))
        counts['extra_normal_late']+=len(extra);counts['recovered_normal_late']+=len(recovered)
        bd=dispatches(b);nd=dispatches(n);times=sorted(set(bd)|set(nd));t=next((t for t in times if bd.get(t,set())!=nd.get(t,set())),None)
        if t is None:continue
        sn=next((q for q in n['snapshots'] if abs(q['now_ns']-t)<1),None)
        observedD=sorted(q['arrival_ns'] for q in case['tickets'] if q['task']=='detection' and q['arrival_ns']<=t)
        gaps=[(z-a)/1e9 for a,z in zip(observedD,observedD[1:])]
        frozen,_,_=d.x.x.r.h.load();long=d.x.x.r.p.profile(frozen,'long_context')['detection_CPU_normal'];available=sum(long)/1e9
        record=dict(condition=j,seed=case['seed'],family=case['family'],context=case['context'],time_ns=t,common_dispatch_prefix=all(bd.get(a,set())==nd.get(a,set()) for a in times if a<t),Band_first_jobs=sorted(bd.get(t,set())),CostV2_first_jobs=sorted(nd.get(t,set())),observed_D_arrivals=len(observedD),observed_D_min_gap_s=min(gaps) if gaps else None,declared_long_profile_D_available_s=available,long_profile_is_not_WCET=True,minimum_gap_below_available_plus_max_wait=(min(gaps)<available+.25 if gaps else None),extra_normal_late_count=len(extra),whole_case_cooling=n['cooling_count'],future_unarrived_requests=sum(q['arrival_ns']>t for q in case['tickets']))
        if sn:
            record.update(chosen=sn['actions'][sn['chosen']],performance_reasons=sn['admissions'],risk=sn['risk'],current_reference_predicted_P95_ms=[f.get('urgent_p95_ms') for f in sn['forecasts'][0]],state=sn['state'],actions=sn['actions'],physical_mask=sn['physical_mask'],performance_mask=sn['mask'])
        first.append(record)
    result=dict(status='completed_stored_ledger_diagnosis',extra_late_requests=rows,counts=counts,first_dispatch_divergences=first,
        interpretation='observed-D minimum gap is absent at a one-D initial prefix, so cannot prove separation of future burst; this is a future development hypothesis, not a verified congestion guard',
        current_long_context_not_WCET=True,original_V2_FAIL_preserved=True,model_fit_calls=0,new_learning=0,native_starts=0,device_commands=0)
    d.write(d.PUBLIC/'service_loss_diagnosis.json',result)
    return dict(counts=counts,first_divergences=len(first),extra_rows=rows,native_starts=0)
if __name__=='__main__':print(json.dumps(d.serial(run()),ensure_ascii=False),flush=True)
