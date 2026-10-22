from pathlib import Path
import os,sys,copy,gzip,math
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments/edf_cpu_first_20261016'),str(ROOT/'experiments/competition_cost_20261017')]
import lab_backend as L
from policy import window_heat
import state_cost as Cost
from relative_drain import exclusive
NS=1_000_000_000
def save_binary(p,b):
    with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())

def public_input(case,catalog):
    value=case['input'];base=copy.deepcopy(value);base['requests']=base['requests'][:48]
    public,contexts=L.prepare_public(base,catalog['templates'],catalog['profiles'])
    prototypes={r['ordinal']:r for r in public['requests']}
    sources={r['bank']:contexts[r['request_id']] for r in public['requests']}
    rows=[];newcontexts={}
    for q in value['requests']:
        row=copy.deepcopy(prototypes[q['ordinal']%48])
        row.update(request_id='user-'+str(q['ordinal']).zfill(5),ordinal=q['ordinal'],
                   scheduled_arrival_ns=round(q['arrival_s']*NS),deadline_ns=round(q['deadline_s']*NS),group=q['ordinal']//8)
        rows.append(row);newcontexts[row['request_id']]=sources[row['bank']]
    lookup={q['request_id']:q for q in rows}
    for s in sources.values():s['_requests_by_id']=lookup
    public.update(requests=rows,service_stop_ns=round(case['service_stop_s']*NS),
                  drain_stop_ns=round(case['drain_stop_s']*NS),observation_end_ns=round(case['observation_end_s']*NS))
    public['public_base_sha256']=L.digest(value);public['public_scenario_sha256']=L.digest(value)
    return public,newcontexts

def metrics(summary,prediction,case,costmodel):
    lo,hi=case['work_window'];observed=summary['requests'];answered=[r for r in observed if r['response_ns'] is not None]
    latency=sorted((r['response_ns']-r['scheduled_arrival_ns'])/NS for r in answered)
    heat=window_heat(summary,lo,hi)
    cost=Cost.observe(exclusive(summary['gantt'],0.,case['observation_end_s']),lo,hi,costmodel)
    result=dict(**heat,**cost,planned=len(observed),responded=len(answered),
        on_time=sum(r['response_ns']<=r['deadline_ns'] for r in answered),
        urgent_planned=sum(r['priority']=='U' for r in observed),urgent_on_time=sum(r['priority']=='U' and r['response_ns'] is not None and r['response_ns']<=r['deadline_ns'] for r in observed),
        incomplete=len(observed)-sum(r['available_ns'] is not None for r in observed),
        AVAILABLE_by_window_end=sum(r['available_ns'] is not None and r['available_ns']/NS<=hi for r in observed),
        response_missing=len(observed)-len(answered),P95_completed_response_s=latency[max(0,math.ceil(.95*len(latency))-1)] if latency else None,
        tardiness_lower_bound_s=sum(max(0,r['response_ns']-r['deadline_ns'])/NS for r in answered),
        overlap_s=prediction['metrics']['overlap_ns']/NS,window_s=[lo,hi],duration_s=hi-lo,
        baseline_share_percent=100*cost['baseline_J_proxy']/cost['total_J_proxy'],
        residual_AP_at_plus180_c=summary['AP']['ap_c'][-1],
        route_counts={t+'_'+r:sum(q['task']==t and q['route']==r for q in observed) for t in ('C','D') for r in ('CPU','GPU')})
    return result

