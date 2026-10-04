"""Read-only verification of frozen artifacts; no training/simulation/device calls."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import numpy as np
from tools import d1_request_ppo as rl
from tools import d1_request_ppo_report as report


def verify(folder):
    folder=Path(folder);p=rl.p
    load=lambda name:json.loads((folder/name).read_text(encoding='utf8'))
    prereg=load('preregistered.json');freeze=load('freeze_before_test.json');summary=load('summary.json')
    assert prereg['contract']==rl.specification()
    for path,digest in prereg['hashes'].items():assert p.digest(p.ROOT/path)==digest,path
    assert summary['selected']==freeze['selected']
    assert prereg['utc']<freeze['utc'] and freeze['test_started'] is False
    analysis=json.loads((folder.parent/'report_contract.json').read_text(encoding='utf8'))
    assert analysis['registered_utc']<freeze['utc'] and analysis['final_test_not_started']
    assert p.digest(Path(report.__file__))==analysis['code_sha256']
    rows=report.read_csv(folder/'test.csv');train=report.read_csv(folder/'training.csv')
    validation=report.read_csv(folder/'validation.csv')
    assert len(rows)==768 and len(train)==768 and len(validation)==720
    key=lambda r:tuple(r[k] for k in ('trace_seed','family','scenario','policy'))
    index={key(r):r for r in rows};assert len(index)==768
    spec=prereg['contract']
    expected={(s,f,c,pol) for s in spec['test_trace_seeds'] for f in rl.old.FAMILIES
              for c in rl.old.SCENARIOS for pol in spec['test_policies']}
    assert set(index)==expected
    for seed in spec['seeds']:
        tr=[r for r in train if r['learn_seed']==seed]
        assert [r['update'] for r in tr]==list(range(1,257))
        dual=np.array(spec['multiplier_initial'])
        for r in tr:
            dual=np.clip(dual+5*np.array(r['violation']),0,100)
            assert np.allclose(dual,r['multipliers'],rtol=0,atol=1e-12)
            assert r['minibatch_updates']>0
            assert all(np.isfinite(r[k]) for k in ('loss','kl','entropy','clip_fraction'))
    assert sum(r['batch_steps'] for r in train)==summary['training_steps']==649184
    for chosen in freeze['selected']:
        path=folder/f'seed{chosen["seed"]}'/'selected_actor.json'
        assert p.digest(path)==chosen['actor_sha256']
        assert rl.model_hash(rl.load_actor(path))==json.loads(path.read_text())['sha256']
    frozen,case=p.inputs(p.BUNDLE)
    initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
    checked=0;max_j_error=0.;max_ap_error=0.;seen=set();request_count=0
    with (folder/'local_test_ledgers.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            record=json.loads(line);k=key(record);assert k not in seen;seen.add(k)
            r=index[k];ledger=record['ledger'];request_count+=len(ledger)
            for q in ledger:
                fields=('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
                times=[q[f] for f in fields if f in q]
                assert times==sorted(times) and (not times or times[0]>=q['arrival_ns'])
            for backend in ('CPU','GPU'):
                jobs=sorted((q for q in ledger if q.get('backend')==backend and 'dispatch_ns' in q),key=lambda q:q['dispatch_ns'])
                assert all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:]))
            urgent=[q['response_ns']/1e6 for q in ledger if q['priority']=='urgent' and 'response_ns' in q]
            normal=[q['response_ns']/1e6 for q in ledger if q['priority']=='normal' and 'response_ns' in q]
            metrics=dict(urgent_p95_ms=sorted(urgent)[math.ceil(.95*len(urgent))-1] if urgent else None,
                         normal_mean_ms=float(np.mean(normal)) if normal else None)
            result=dict(ledger=ledger,metrics=metrics)
            calculated,(segments,grid,rise,end)=rl.outcome(result,initial,frozen)
            for field in calculated:
                if field in ('actions','controllable_decisions'):continue
                x,y=calculated[field],r[field]
                assert (x is None and y is None) or (x is not None and y is not None and abs(x-y)<1e-8),(k,field,x,y)
            independent_j=120*initial['preload_power_w']
            for segment in segments:
                state=segment['state']
                if state=='idle':continue
                assert state in frozen['energy_increment_w'],state
                independent_j+=max(0,min(120,segment['end_s'])-segment['start_s'])*frozen['energy_increment_w'][state]
            max_j_error=max(max_j_error,abs(independent_j-r['energy_j']))
            if end==180:max_ap_error=max(max_ap_error,abs(float(np.trapezoid(rise,grid))-r['thermal_degree_seconds']))
            checked+=1
    assert seen==expected and max_j_error<1e-8 and max_ap_error<1e-8
    return dict(utc=datetime.now(timezone.utc).isoformat(),base_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        uncommitted=True,command=f'python -B -m tools.d1_request_ppo_verify --folder {folder.as_posix()}',
        verifier_sha256=p.digest(Path(__file__)),result='PASS',ledger_cases=checked,request_records=request_count,
        source_and_frozen_hashes_unchanged=True,model_freeze_before_test=True,training_multiplier_steps=768,
        total_minibatch_updates=sum(r['minibatch_updates'] for r in train),
        max_independent_energy_difference_j=max_j_error,max_thermal_reaccount_difference=max_ap_error,
        device_commands=0,simulation_reruns=0,training_reruns=0,
        local_raw=dict(path=(folder/'local_test_ledgers.jsonl').as_posix(),sha256=p.digest(folder/'local_test_ledgers.jsonl')))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args()
    result=verify(args.folder);rl.p.write(Path(args.folder)/'verification.json',result);print(json.dumps(result,indent=2))
