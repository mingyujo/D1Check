"""Independent ledger accounting and finite-tail sensitivity; no new scheduling."""
import argparse
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
from tools import d1_scheduler_conditions as s
from tools.d1_scheduler_conditions_report import read
from tools import d1_request_ppo as rl
p=s.p


def verify(folder):
    folder=Path(folder);rows=read(folder/'results.csv')
    reg=json.loads((folder/'preregistered.json').read_text());freeze=json.loads((folder/'freeze_before_test.json').read_text())
    assert reg['utc']<freeze['utc']
    for path,sha in reg['hashes'].items():assert p.digest(p.ROOT/path)==sha,path
    key=lambda r:tuple(r[k] for k in ('stage','envelope','seed','scenario','policy'))
    index={key(r):r for r in rows};expected={(stage,e['id'],seed,c,pol) for stage in ('development','test')
        for e in s.envelopes() for seed in reg['spec'][stage+'_seeds'] for c in s.a.old.SCENARIOS for pol in s.POLICIES}
    assert set(index)==expected and len(rows)==len(expected)==3240
    assert s.select([r for r in rows if r['stage']=='development'])==freeze['selected']
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];seen=set();count=0;maxdiff=0.;tails=[];reps=[]
    for line in (folder/'local_ledgers.jsonl').open(encoding='utf8'):
        item=json.loads(line);row=item['meta'];k=key(row);assert k not in seen;seen.add(k)
        ledger=item['ledger'];count+=len(ledger);saved=index[k]
        e=next(e for e in s.envelopes() if e['id']==row['envelope'])
        tickets=s.workload(e,int(row['seed']))
        assert len(ledger)==len(tickets)==48
        for q,r in zip(tickets,ledger):
            assert all(q[f]==r[f] for f in ('id','ordinal','arrival_ns','task','priority','deadline_offset_ns'))
            ts=[r[f] for f in ('dispatch_ns',*s.a.old.engine.FIELDS) if f in r]
            assert ts==sorted(ts) and (not ts or ts[0]>=q['arrival_ns'])
        urgent=sorted(r['response_ns']/1e6 for r in ledger if r['priority']=='urgent' and 'response_ns' in r)
        normal=[r['response_ns']/1e6 for r in ledger if r['priority']=='normal' and 'response_ns' in r]
        metrics=dict(urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,normal_mean_ms=statistics.mean(normal) if normal else None)
        rr,(segments,_,_,end)=rl.outcome(dict(ledger=ledger,metrics=metrics),initial,frozen)
        for field,v in rr.items():
            if field in ('actions','controllable_decisions'):continue
            w=saved[field];assert (v is None and w is None) or (v is not None and w is not None and abs(v-w)<1e-8),(k,field)
        joules=120*initial['preload_power_w']+sum(max(0,min(120,x['end_s'])-x['start_s'])*frozen['energy_increment_w'][x['state']]
            for x in segments if x['state']!='idle')
        maxdiff=max(maxdiff,abs(joules-saved['energy_j']))
        if row['stage']=='test' and end==180:
            # Post-hoc boundary sensitivity, NOT used for development selection.
            ext=segments+[dict(start_s=180.,end_s=330.,state='idle')]
            costs=p.model.costs(ext,initial,list(range(35,331)),frozen,330.)
            path=costs['ap_path'];reference=p.memory.initialize(initial['preload'],frozen['ap']['beta'],30.)['reference_c']
            area=sum((max(0,x-reference)+max(0,y-reference))*.5 for x,y in zip(path,path[1:]))
            tails.append(dict(envelope=row['envelope'],seed=row['seed'],scenario=row['scenario'],policy=row['policy'],
                last_lane_s=max(r.get('lane_available_ns',120e9) for r in ledger)/1e9,
                ap180_c=path[145],ap330_c=path[-1],area_35_330_c_s=area,
                original_area_35_180_c_s=rr['thermal_degree_seconds']))
            if row['seed']==91001 and row['scenario']=='mean' and e['id'] in ('g0.45_c0.5_b4','g1.2_c0.75_b1'):
                reps.append(dict(envelope=e['id'],policy=row['policy'],ledger=ledger,
                    ap_35_180_c=path[:146],energy_path=costs['energy_path']))
    assert seen==expected and maxdiff<1e-8
    s.save_rows(folder/'tail_sensitivity.csv',tails)
    p.write(folder/'representative_curves.json',reps)
    out=dict(result='PASS',utc=datetime.now(timezone.utc).isoformat(),base_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        uncommitted=True,cases=len(rows),requests=count,max_independent_energy_difference_j=maxdiff,
        model_sha=p.MODEL_SHA,initial_sha=p.INITIAL_SHA,source_hashes_unchanged=True,
        frozen_development_selection_reproduced=True,simulation_reruns=0,device_commands=0,
        raw=dict(path=(folder/'local_ledgers.jsonl').as_posix(),sha256=p.digest(folder/'local_ledgers.jsonl')),
        tail_note='posthoc same-equation idle tail to330s; not new ground truth, not selection/accuracy threshold')
    p.write(folder/'verification.json',out);print(json.dumps(out,indent=2))


def verify_selector(folder):
    from tools import d1_scheduler_condition_selector as selector
    folder=Path(folder);freeze=json.loads((folder/'freeze_before_confirmation.json').read_text())
    archived_source=[]
    for path,sha in freeze['hashes'].items():
        if p.digest(p.ROOT/path)==sha:continue
        if path=='tools/d1_scheduler_condition_selector.py' and p.digest(folder/'source_snapshot.py')==sha:
            archived_source.append(path)
        else:raise AssertionError(path)
    original=read(p.ROOT/'docs/results/scheduler_conditions_01/run_v2/results.csv')
    assert selector.fit(original)==freeze['spec']['selection']
    rows=read(folder/'results.csv');key=lambda r:tuple(r[k] for k in ('envelope','seed','scenario','policy'))
    index={key(r):r for r in rows};expected=set()
    for e in s.envelopes():
        policies=set(['EFT_REFERENCE','SPLIT_REFERENCE']+[v for v in freeze['spec']['selection'][e['id']].values() if v])
        expected|={(e['id'],seed,c,pol) for seed in freeze['spec']['seeds'] for c in s.a.old.SCENARIOS for pol in policies}
    assert set(index)==expected and len(rows)==len(expected)
    frozen,case=p.inputs(p.BUNDLE);initial=case['initial'];seen=set();requests=0;maxdiff=0.
    for line in (folder/'local_ledgers.jsonl').open(encoding='utf8'):
        item=json.loads(line);k=key(item['meta']);assert k not in seen;seen.add(k)
        ledger=item['ledger'];row=index[k];requests+=len(ledger)
        e=next(e for e in s.envelopes() if e['id']==row['envelope']);tickets=s.workload(e,int(row['seed']))
        assert len(ledger)==48
        for q,r in zip(tickets,ledger):
            assert all(q[f]==r[f] for f in ('id','arrival_ns','task','priority','deadline_offset_ns'))
            ts=[r[f] for f in ('dispatch_ns',*s.a.old.engine.FIELDS) if f in r]
            assert ts==sorted(ts) and (not ts or ts[0]>=q['arrival_ns'])
        for backend in ('CPU','GPU'):
            jobs=sorted([r for r in ledger if r.get('backend')==backend],key=lambda r:r.get('dispatch_ns',math.inf))
            assert all(x.get('lane_available_ns',120e9)<=y.get('dispatch_ns',120e9) for x,y in zip(jobs,jobs[1:]))
        urgent=sorted(r['response_ns']/1e6 for r in ledger if r['priority']=='urgent' and 'response_ns' in r)
        normal=[r['response_ns']/1e6 for r in ledger if r['priority']=='normal' and 'response_ns' in r]
        metrics=dict(urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,normal_mean_ms=statistics.mean(normal) if normal else None)
        rr,(segments,_,_,_)=rl.outcome(dict(ledger=ledger,metrics=metrics),initial,frozen)
        for f,v in rr.items():
            if f in ('actions','controllable_decisions'):continue
            assert (v is None and row[f] is None) or (v is not None and row[f] is not None and abs(v-row[f])<1e-8),(k,f)
        j=120*initial['preload_power_w']+sum(max(0,min(120,x['end_s'])-x['start_s'])*frozen['energy_increment_w'][x['state']] for x in segments if x['state']!='idle')
        maxdiff=max(maxdiff,abs(j-row['energy_j']))
    assert seen==expected and maxdiff<1e-8
    p.write(folder/'verification.json',dict(result='PASS',utc=datetime.now(timezone.utc).isoformat(),cases=len(rows),requests=requests,
        max_independent_energy_difference_j=maxdiff,physical_hashes_unchanged=True,execution_sources_verified=True,
        archived_execution_sources=archived_source,development_selection_reproduced=True,
        simulation_reruns=0,device_commands=0,raw_sha256=p.digest(folder/'local_ledgers.jsonl')))
    print('selector verification PASS',len(rows),requests)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);parser.add_argument('--selector',action='store_true')
    args=parser.parse_args();(verify_selector if args.selector else verify)(args.folder)
