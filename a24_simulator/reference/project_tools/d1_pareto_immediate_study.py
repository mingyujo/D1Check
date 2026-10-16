"""Locked single refinement after v1 failure; fresh seeds, no model refitting."""
import argparse
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import time
from tools import d1_method_followup as f
from tools import d1_pareto_beam_immediate as beam
x=f.x


def spec():
    return dict(version='causal-pareto-immediate-v2',cases=list(f.CASES),stored_seeds=[123001,123002],
        new_seeds=[423001,423002],scenarios=list(x.old.SCENARIOS),requests=48,new_runs=72,
        policy=beam.POLICY,parent_failed_policy=beam.parent.POLICY,
        change='same beam/physical coefficients/guard; first action must be legal immediately; no voluntary idle deferral',
        development_used='already seen v1 failures; v2 is post-hoc development, new seeds are software confirmation only',
        branch_requests=4,beam_width=8,expanded_calendars_per_callback=64,max_wall_s=1800,
        local_guard='per-request long-context lateness and conditional mean J/peak vs EFT; not global future-arrival guarantee',
        parameters_locked=True,refit=False,controller_overhead_zero_assumption=True,
        model_sha256=x.p.MODEL_SHA,initial_sha256=x.p.INITIAL_SHA,
        independent_device_validation=False,strict_supported=False,experiment_ready=False,device_commands=0)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();s=spec()
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial'];controls=f.stored_records(x.SOURCE)
    paths=[Path(__file__),Path(beam.__file__),Path(beam.parent.__file__),Path(x.p.__file__),Path(x.__file__),
        Path(x.old.engine.__file__),Path(f.conditions.__file__),x.p.BUNDLE/'model.json',x.p.BUNDLE/'initial_inputs.json']
    hashes={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}
    x.p.write(out/'registered_before_run.json',dict(spec=s,hashes=hashes,utc=datetime.now(timezone.utc).isoformat(),
        base_head='42890f417871c262685bce0e6bb6a85d908d1372',implementation_dirty=True))
    rows=[];records=[];count=0;inputs=[]
    try:
        for stage,seeds in (('stored_regression',s['stored_seeds']),('new_seed_confirmation',s['new_seeds'])):
            for env in f.CASES:
                e=next(e for e in f.conditions.envelopes() if e['id']==env)
                for seed in seeds:
                    qs=f.tickets(controls[env,seed,'mean']) if stage=='stored_regression' else f.conditions.workload(e,seed)
                    inputs.append(dict(stage=stage,envelope=env,seed=seed,tickets=qs))
                    for scenario in x.old.SCENARIOS:
                        if time.monotonic()-began>s['max_wall_s']:raise TimeoutError('bounded immediate candidate')
                        for policy in ('EFT_REFERENCE',beam.POLICY):
                            if stage=='stored_regression' and policy=='EFT_REFERENCE':row,record=f.read_control(controls[env,seed,scenario],frozen,initial)
                            else:
                                row,rr,c,ss,cost=(beam.simulate(frozen,initial,qs,scenario) if policy==beam.POLICY else
                                    x.simulate(frozen,initial,qs,scenario,policy));count+=1
                                if len(rr['ledger'])!=48:raise ValueError('missing denominator')
                                if [r['arrival_ns'] for r in rr['ledger']]!=[q['arrival_ns'] for q in qs]:raise ValueError('arrival moved')
                                if row['completed']==48:x.validate_schedule(x.jobs_from_ledger(rr['ledger']),qs,x.p.profile(frozen,scenario))
                                record=dict(ledger=rr['ledger'],decisions=rr['decisions'],guards=getattr(c,'records',[]),
                                    segments=ss,predicted_ap_path=cost['ap_path'],information='new_PC_calculation')
                            row.update(stage=stage,envelope=env,seed=seed,scenario=scenario,policy=policy)
                            rows.append(row);record['meta']=dict(row);records.append(record)
                    fields=sorted(set().union(*(r.keys() for r in rows)))
                    x.old.csv_write(out/'results.csv',[{k:r.get(k) for k in fields} for r in rows])
                    x.p.write(out/'progress.json',dict(stage=stage,envelope=env,seed=seed,new_runs=count,elapsed_s=time.monotonic()-began))
                    print(stage,env,seed,count,flush=True)
    finally:
        raw=''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in records).encode('utf8')
        (out/'records.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0));x.p.write(out/'inputs.json',inputs)
    if hashes!={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}:raise ValueError('registered source changed')
    pairs=f.compare(rows);x.old.csv_write(out/'comparisons.csv',pairs)
    x.p.write(out/'summary.json',dict(new_runs=count,reused_controls=24,records=len(records),elapsed_s=time.monotonic()-began,
        full_service_cases=sum(r['full_service'] for r in pairs),joint_nonworsening_cases=sum(r['joint_nonworsening'] for r in pairs),
        hashes_unchanged=True,device_commands=0,experiment_ready=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();run(args.output)
