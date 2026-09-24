"""Measured-only boundary replay and descriptive cost bridge. No counterfactual fit.

Exact recorded request/backend/order only. Does not grant parallel policy support.
"""
import argparse
import json
from pathlib import Path
import statistics
from tools import d1_arrival_plan as io
from tools import d1_cal03_connection as base


def replay(rows):
    events=[];responses=[];reuse=0
    for r in rows:
        fields=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
        base.require(all(r[a]<=r[b] for a,b in zip(fields,fields[1:])), 'recorded boundary order')
        complete=r['output_ready_ns'] if r['priority']=='urgent' else r['persist_complete_ns']
        base.require(r['completion_ns']==complete, 'recorded priority response boundary')
        ds=[r[b]-r[a] for a,b in zip(fields,fields[1:])]
        base.require(sum(ds)==r['lane_available_ns']-r['dispatch_ns'], 'disjoint interval sum')
        responses.append(dict(request_id=r['request_id'],backend=r['selected_backend'],
            response_ns=complete-r['scheduled_arrival_ns'],durations_ns=ds,
            admission='recorded execution only; counterfactual assignment unsupported'))
        events.extend([(r['dispatch_ns'],1,r['selected_backend'],r['request_id']),
                       (r['lane_available_ns'],0,r['selected_backend'],r['request_id'])])
    busy={};previous={}
    for at,kind,b,rid in sorted(events):
        if kind==1:
            base.require(b not in busy,'recorded busy lane reused before release')
            if b in previous:reuse+=1
            busy[b]=rid
        else:
            base.require(busy.pop(b,None)==rid,'wrong release request');previous[b]=at
    base.require(not busy,'unreleased observed lanes')
    return dict(requests=responses,lane_reuse_pairs=reuse,scope='measured-only exact recorded trace; not prediction validation')


def build(plan_path,output):
    path=Path(plan_path);plan=io.read(path);out=Path(output)
    base.require(not out.exists(),'preserve previous bridge')
    root=Path(plan['output_root'])/'confirmation'
    base.require((root/'complete.json').is_file() and not (Path(plan['registry'])/'stopped.json').exists(),'complete followup required')
    base.require(io.digest(plan['frozen_development'])==plan['frozen_development_sha256'],'freeze changed')
    results={};hashes={}
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        base.require(io.read(folder/'host_cleanup.json')['status']=='completed','cleanup')
        validated=io.read(folder/'validated.json');base.require(validated['status']=='valid','collection validity')
        rows=io.read(folder/'artifacts/requests.json');trace=io.read(folder/'artifacts/collection_trace.json')
        selected={x['actual_selected']['request_id']:x for x in trace['records'] if x.get('actual_selected')}
        intervals=[]
        for row in rows:
            d=selected[row['request_id']]
            points=[d['snapshot_ns'],d['compute_start_ns'],d['compute_end_ns'],d['selection_end_ns'],d['record_end_ns'],row['dispatch_ns']]
            base.require(all(a<=b for a,b in zip(points,points[1:])),'decision/record boundary')
            intervals.append(dict(request_id=row['request_id'],parts_ns=[b-a for a,b in zip(points,points[1:])],total_ns=points[-1]-points[0]))
        results[entry['condition']]=dict(session_id=entry['session_id'],independent_sessions=1,correlated_requests=4,
            replay=replay(rows),decision_cost_vectors=intervals,
            joint_snapshot_dispatch_median_ns=statistics.median(x['total_ns'] for x in intervals),
            component_order=['snapshot_prepare','policy_compute','selection','record','record_to_dispatch'],
            host_api_overlap=validated['collection']['observed_overlaps'])
        for name in ('manifest.json','requests.json','collection_trace.json'):
            f=folder/'artifacts'/name;hashes[str(f)]=io.digest(f)
    result=dict(version='arrival-observed-bridge-v1',conditions=results,input_hashes=hashes,
        plan_sha256=io.digest(path),frozen_development_sha256=plan['frozen_development_sha256'],
        experiment_ready=False,adaptive_gpu_admission=False,arbitrary_parallel_admission=False,
        applicability='recorded B/A/F only; after-unblinding descriptive observations, no refit or accuracy PASS',
        supported_operation='exact measured trace replay and per-condition cost lookup only')
    out.mkdir(parents=True);(out/'observed_bridge.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return dict(output=str(out),sessions=3,requests=12,lane_reuse_pairs=sum(x['replay']['lane_reuse_pairs'] for x in results.values()))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(build(a.plan,a.output),indent=2))

if __name__=='__main__':main()
