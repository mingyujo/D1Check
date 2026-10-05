"""Re-account saved schedules without simulation, learning or device commands."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
from tools import d1_scheduler_alternatives as a
from tools import d1_request_ppo as rl
from tools import d1_request_ppo_report as csvtool


def verify(folder):
    folder=Path(folder);rows=csvtool.read_csv(folder/'results.csv')
    reg=json.loads((folder/'preregistered.json').read_text());freeze=json.loads((folder/'freeze_before_test.json').read_text())
    assert len(rows)==1440 and reg['utc']<freeze['utc'] and freeze['test_started'] is False
    assert reg['spec']==a.specification()
    for path,sha in reg['sources'].items():assert a.p.digest(a.p.ROOT/path)==sha,path
    for seed,sha in freeze['ppo_hashes'].items():
        assert rl.model_hash(rl.load_actor(a.p.ROOT/f'docs/results/request_ppo_01/run_v2/seed{seed}/selected_actor.json'))==sha
    key=lambda r:tuple(r[k] for k in ('stage','trace_seed','family','scenario','policy'))
    index={key(r):r for r in rows};assert len(index)==len(rows)
    expected=set()
    for stage,seeds,policies in [('development',reg['spec']['development_seeds'],a.POLICIES),
        ('test',reg['spec']['test_seeds'],[*a.POLICIES,*[f'PPO_seed{s}' for s in reg['spec']['ppo_seeds']]])]:
        expected|={(stage,s,f,c,p) for s in seeds for f in a.old.FAMILIES for c in a.old.SCENARIOS for p in policies}
    assert set(index)==expected
    frozen,case=a.p.inputs(a.p.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    seen=set();requests=0;max_j_difference=0.;minimum_bound_gap=math.inf;representatives=[]
    for line in (folder/'local_ledgers.jsonl').open(encoding='utf8'):
        record=json.loads(line);k=key(record);assert k not in seen;seen.add(k);row=index[k];ledger=record['ledger'];requests+=len(ledger)
        expected_requests=a.old.workload(row['family'],row['trace_seed'])
        assert [q['arrival_ns'] for q in expected_requests]==[q['arrival_ns'] for q in ledger]
        for backend in ('CPU','GPU'):
            jobs=sorted([q for q in ledger if q.get('backend')==backend and 'dispatch_ns' in q],key=lambda q:q['dispatch_ns'])
            assert all(q['lane_available_ns']<=n['dispatch_ns'] for q,n in zip(jobs,jobs[1:]))
        for q in ledger:
            times=[q[f] for f in ('dispatch_ns',*a.old.engine.FIELDS) if f in q]
            assert times==sorted(times) and (not times or times[0]>=q['arrival_ns'])
        urgent=sorted(q['response_ns']/1e6 for q in ledger if q['priority']=='urgent' and 'response_ns' in q)
        normal=[q['response_ns']/1e6 for q in ledger if q['priority']=='normal' and 'response_ns' in q]
        metrics=dict(urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,
            normal_mean_ms=statistics.mean(normal) if normal else None)
        outcome,(segments,_,_,_)=rl.outcome(dict(ledger=ledger,metrics=metrics),initial,frozen)
        for field,value in outcome.items():
            if field in ('actions','controllable_decisions'):continue
            assert (value is None and row[field] is None) or (value is not None and row[field] is not None and abs(value-row[field])<1e-8),(k,field)
        energy=120*initial['preload_power_w']+sum(max(0,min(120,s['end_s'])-s['start_s'])*frozen['energy_increment_w'][s['state']] for s in segments if s['state']!='idle')
        max_j_difference=max(max_j_difference,abs(energy-row['energy_j']))
        bound=a.energy_lower_bound(expected_requests,frozen,initial,row['scenario'])['lower_bound_j']
        assert abs(bound-row['energy_lower_bound_j'])<1e-8
        if row['planned']==row['completed']:minimum_bound_gap=min(minimum_bound_gap,energy-bound)
        if row['stage']=='test' and row['trace_seed']==70001 and row['scenario']=='mean' and row['policy'] in ('EFT_REFERENCE','LLF_EFT_V1','PARETO_MPC_V1'):
            fields=('id','ordinal','task','priority','arrival_ns','deadline_offset_ns','backend','dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns','response_ns','status')
            representatives.append(dict(family=row['family'],policy=row['policy'],ledger=[{f:q.get(f) for f in fields} for q in ledger]))
    assert seen==expected and max_j_difference<1e-8 and minimum_bound_gap>=-1e-7
    a.p.write(folder/'representative_schedules.json',representatives)
    result=dict(utc=datetime.now(timezone.utc).isoformat(),base_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),uncommitted=True,
        command=f'python -B -m tools.d1_scheduler_alternatives_verify --folder {folder.as_posix()}',
        result='PASS',cases=len(rows),requests=requests,source_hashes_unchanged=True,physical_model_sha256=a.p.MODEL_SHA,
        original_ppo_actors_unchanged=True,max_independent_energy_difference_j=max_j_difference,
        minimum_gap_to_relaxed_energy_bound_j=minimum_bound_gap,device_commands=0,simulation_reruns=0,
        local_raw=dict(path=(folder/'local_ledgers.jsonl').as_posix(),sha256=a.p.digest(folder/'local_ledgers.jsonl')))
    a.p.write(folder/'verification.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();print(verify(args.folder))
