"""Saved matched request comparisons and concrete harm examples; no engine."""
import collections,gc,gzip,json
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[2];O=R/'a24_simulator/results/A24_BC_S26_REQUESTS_20261021_01'
def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def records(row):
    d=read(R/row['raw']['path']);out={}
    for q in d['result']['requests']:
        fields=('request_id','task','priority','scheduled_arrival_ns','deadline_ns','queue_entry_ns','dispatch_ns','response_ns','available_ns','route')
        v={k:q[k] for k in fields}
        v['on_time']=q['response_ns'] is not None and q['response_ns']<=q['deadline_ns']
        v['latency_s']=(q['response_ns']-q['scheduled_arrival_ns'])/1e9 if q['response_ns'] is not None else None
        v['admission_s']=(q['queue_entry_ns']-q['scheduled_arrival_ns'])/1e9
        v['queue_s']=(q['dispatch_ns']-q['queue_entry_ns'])/1e9 if q['dispatch_ns'] is not None else None
        v['service_s']=(q['response_ns']-q['dispatch_ns'])/1e9 if q['response_ns'] is not None else None
        if q['route'] is not None:
            v['immutable_solo_response_work_s']=sum(q['timing']['stages_ns'][:2 if q['task']=='C' else 3])/1e9
            v['modeled_service_slowdown_s']=v['service_s']-v['immutable_solo_response_work_s'] if v['service_s'] is not None else None
        out[q['request_id']]=v
    del d;gc.collect();return out
def main():
    result=read(O/'RESULT.json');summaries=[]
    cases=sorted({x['case'] for x in result['rows']})
    for case in cases:
        bc=next(x for x in result['rows'] if x['case']==case and x['policy']=='BC_RECOVERED')
        if bc['status']!='COMPLETE':continue
        ours=records(bc)
        for ref in (x for x in result['rows'] if x['case']==case and x['policy']!='BC_RECOVERED' and x['status']=='COMPLETE'):
            other=records(ref);assert ours.keys()==other.keys();groups={};changed=0
            for rid in ours:
                x,y=ours[rid],other[rid]
                assert all(x[k]==y[k] for k in ('task','priority','scheduled_arrival_ns','deadline_ns','queue_entry_ns'))
                changed+=x['route']!=y['route']
            for group in ('ALL','U','N'):
                ids=[k for k,v in ours.items() if group=='ALL' or v['priority']==group]
                lost=[k for k in ids if other[k]['on_time'] and not ours[k]['on_time']]
                gained=[k for k in ids if ours[k]['on_time'] and not other[k]['on_time']]
                def excess(k):return ours[k]['latency_s']-other[k]['latency_s'] if ours[k]['latency_s'] is not None and other[k]['latency_s'] is not None else 1e30
                examples=[]
                for rid in sorted(lost,key=excess,reverse=True)[:5]:
                    examples.append(dict(request_id=rid,BC=ours[rid],reference=other[rid],response_delay_change_s=excess(rid),
                        queue_change_s=ours[rid]['queue_s']-other[rid]['queue_s'] if ours[rid]['queue_s'] is not None and other[rid]['queue_s'] is not None else None,
                        service_change_s=ours[rid]['service_s']-other[rid]['service_s'] if ours[rid]['service_s'] is not None and other[rid]['service_s'] is not None else None))
                groups[group]=dict(n=len(ids),BC_on=sum(ours[k]['on_time'] for k in ids),reference_on=sum(other[k]['on_time'] for k in ids),
                    BC_newly_late=len(lost),BC_newly_on=len(gained),newly_late_by_task=dict(collections.Counter(ours[k]['task'] for k in lost)),
                    newly_late_request_ids=lost,newly_on_request_ids=gained,worst5_newly_late_examples=examples)
            summaries.append(dict(case=case,rate=bc['condition']['requests_per_second'],pattern=bc['condition']['pattern'],reference=ref['policy'],route_changes=changed,groups=groups))
        print('MATCHED_REQUESTS',case,flush=True)
    with (O/'MATCHED_REQUESTS.json').open('x',encoding='utf8') as f:
        json.dump(dict(status='PASS',rows=summaries,scope='Same frozen requests and potentials, descriptive policy-outcome comparison; no causal ablation',new_environment=0,new_fit=0),f,ensure_ascii=False,indent=2)
if __name__=='__main__':main()
