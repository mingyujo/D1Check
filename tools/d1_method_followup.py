"""Bounded full-input follow-up. Reuse stored controls; no fit/device access."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import statistics
import time

from tools import d1_industrial_scheduling as x
from tools import d1_scheduler_conditions as conditions
from tools import d1_scheduler_alternatives as alternatives
from tools import d1_scheduler_capacity as capacity

ROOT=x.p.ROOT/'docs/results/method_followup_01'
CASES=(*x.CASES,'g0.45_c0.75_b4')
STORED_SEEDS=(123001,123002)
NEW_SEEDS=(223001,223002)
METHODS=('EFT_REFERENCE',x.ATC,x.BOTTLENECK)


def spec():
    return dict(version='method-followup-v1',cases=list(CASES),requests=48,
        selection_reason='three previous prefix inputs plus previously declared 75% classification queue; no outcome screening',
        stored_seeds=list(STORED_SEEDS),new_seeds=list(NEW_SEEDS),scenarios=list(x.old.SCENARIOS),
        methods=list(METHODS),new_simulations=120,stored_EFT_controls=24,
        max_wall_s=1800,controller_overhead_zero_assumption=True,
        model_sha256=x.p.MODEL_SHA,initial_sha256=x.p.INITIAL_SHA,
        freeze='existing ATC/bottleneck parameters unchanged; no fitting/tuning after evaluation',
        interpretation='stored inputs post-hoc regression; fresh synthetic seeds not device validation',
        selection='publish all; full deadlines separate from J/peak/AParea non-worsening vs EFT; no default adoption',
        device_commands=0,strict_supported=False,experiment_ready=False)


def tickets(record):
    return [{k:q[k] for k in x.TICKET_FIELDS} for q in record['ledger']]


def stored_records(source):
    result={}
    for line in Path(source).open(encoding='utf8'):
        d=json.loads(line);m=d['meta']
        if m['envelope'] in CASES and m['seed'] in STORED_SEEDS and m['policy']=='EFT_REFERENCE':
            key=(m['envelope'],m['seed'],m['scenario'])
            if key in result:raise ValueError('duplicate control')
            result[key]=d
    if len(result)!=24:raise ValueError('missing stored controls')
    return result


def read_control(record,frozen,initial):
    m=record['meta'];qs=tickets(record)
    if len(qs)!=48:raise ValueError('full input required')
    if any(r['status']!='succeeded' for r in record['ledger']):raise ValueError('control cannot be labeled completed')
    ss,costs,end=x.p.account(dict(ledger=record['ledger']),initial,frozen)
    if end!=180 or abs(costs['whole_120s_j']-m['energy_j'])>1e-7:
        raise ValueError('stored energy boundary mismatch')
    if abs(max(costs['ap_path'])-m['peak_ap_c'])>1e-9:raise ValueError('stored AP mismatch')
    x.validate_schedule(x.jobs_from_ledger(record['ledger']),qs,x.p.profile(frozen,m['scenario']))
    return dict(m),dict(meta=dict(m),ledger=record['ledger'],segments=ss,predicted_ap_path=costs['ap_path'],
        information='reused_stored_PC_control')


def compare(rows):
    refs={(r['stage'],r['envelope'],r['seed'],r['scenario']):r for r in rows if r['policy']=='EFT_REFERENCE'}
    pairs=[]
    for r in rows:
        if r['policy']=='EFT_REFERENCE':continue
        b=refs[r['stage'],r['envelope'],r['seed'],r['scenario']]
        full=r['completed']==r['planned']==r['deadline_met']
        deltas={k:r[k]-b[k] if r[k] is not None and b[k] is not None else None
            for k in ('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms','deadline_met')}
        joint=full and all(deltas[k] is not None and deltas[k]<=1e-8
            for k in ('energy_j','peak_ap_c','thermal_degree_seconds')) and any(
            deltas[k]<-1e-8 for k in ('energy_j','peak_ap_c','thermal_degree_seconds'))
        pairs.append(dict(stage=r['stage'],envelope=r['envelope'],seed=r['seed'],scenario=r['scenario'],
            policy=r['policy'],planned=r['planned'],deadline_met=r['deadline_met'],
            full_service=full,joint_nonworsening=joint,
            **{'delta_'+k:v for k,v in deltas.items()}))
    return pairs


def aggregate(pairs):
    result=[]
    for stage in ('stored_regression','new_seed_confirmation'):
        for env in CASES:
            for policy in METHODS[1:]:
                rs=[r for r in pairs if (r['stage'],r['envelope'],r['policy'])==(stage,env,policy)]
                if not rs:continue
                result.append(dict(stage=stage,envelope=env,policy=policy,cases=len(rs),
                    full_service_cases=sum(r['full_service'] for r in rs),
                    planned=sum(r['planned'] for r in rs),deadline_met=sum(r['deadline_met'] for r in rs),
                    joint_nonworsening_cases=sum(r['joint_nonworsening'] for r in rs),
                    **{'mean_'+k:statistics.mean(r[k] for r in rs) if all(r[k] is not None for r in rs) else None
                        for k in ('delta_energy_j','delta_peak_ap_c','delta_thermal_degree_seconds',
                                  'delta_urgent_p95_ms','delta_normal_mean_ms','delta_deadline_met')}))
    return result


def run(output,source=x.SOURCE):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial'];began=time.monotonic()
    controls=stored_records(source)
    paths=[Path(__file__),Path(x.__file__),Path(x.p.__file__),Path(x.old.engine.__file__),
        Path(conditions.__file__),x.p.BUNDLE/'model.json',x.p.BUNDLE/'initial_inputs.json']
    hashes={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}
    x.p.write(out/'registered_before_run.json',dict(spec=spec(),hashes=hashes,
        source=str(Path(source).relative_to(x.p.ROOT)),source_sha256=x.p.digest(source),
        base_head='42890f417871c262685bce0e6bb6a85d908d1372',utc=datetime.now(timezone.utc).isoformat()))
    rows=[];records=[];bounds=[];inputs=[];new_count=0
    try:
        for stage,seeds in (('stored_regression',STORED_SEEDS),('new_seed_confirmation',NEW_SEEDS)):
            for env in CASES:
                e=next(e for e in conditions.envelopes() if e['id']==env)
                for seed in seeds:
                    qs=tickets(controls[env,seed,'mean']) if stage=='stored_regression' else conditions.workload(e,seed)
                    inputs.append(dict(stage=stage,envelope=env,seed=seed,tickets=qs))
                    for scenario in x.old.SCENARIOS:
                        if time.monotonic()-began>spec()['max_wall_s']:raise TimeoutError('bounded follow-up')
                        bound=alternatives.energy_lower_bound(qs,frozen,initial,scenario)
                        demand=capacity.capacity(qs,x.p.profile(frozen,scenario))
                        bounds.append(dict(stage=stage,envelope=env,seed=seed,scenario=scenario,**bound,**demand))
                        for policy in METHODS:
                            if stage=='stored_regression' and policy=='EFT_REFERENCE':
                                row,record=read_control(controls[env,seed,scenario],frozen,initial)
                                if qs!=tickets(controls[env,seed,scenario]):raise ValueError('stored input drift across scenarios')
                            else:
                                row,rr,c,ss,cost=x.simulate(frozen,initial,qs,scenario,policy);new_count+=1
                                if len(rr['ledger'])!=48:raise ValueError('missing denominator')
                                if [r['arrival_ns'] for r in rr['ledger']]!=[q['arrival_ns'] for q in qs]:raise ValueError('arrival moved')
                                if row['completed']==48:x.validate_schedule(x.jobs_from_ledger(rr['ledger']),qs,x.p.profile(frozen,scenario))
                                record=dict(ledger=rr['ledger'],decisions=rr['decisions'],guards=getattr(c,'records',[]),
                                    segments=ss,predicted_ap_path=cost['ap_path'],information='new_PC_calculation')
                            row.update(stage=stage,envelope=env,seed=seed,scenario=scenario,policy=policy,
                                model_lower_bound_j=bound['lower_bound_j'],gap_to_relaxed_bound_j=row['energy_j']-bound['lower_bound_j'])
                            rows.append(row);record['meta']=dict(row);records.append(record)
                    x.old.csv_write(out/'results.csv',[{k:r.get(k) for k in sorted(set().union(*(z.keys() for z in rows)))} for r in rows])
                    x.p.write(out/'progress.json',dict(stage=stage,envelope=env,seed=seed,new_runs=new_count,
                        records=len(records),elapsed_s=time.monotonic()-began))
                    print(stage,env,seed,new_count,flush=True)
    finally:
        raw=''.join(json.dumps(d,ensure_ascii=False,allow_nan=False)+'\n' for d in records).encode('utf8')
        (out/'records.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
        x.p.write(out/'inputs.json',inputs)
    if hashes!={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}:raise ValueError('source/frozen changed')
    pairs=compare(rows);grouped=aggregate(pairs)
    x.old.csv_write(out/'comparisons.csv',pairs);x.old.csv_write(out/'groups.csv',grouped)
    x.old.csv_write(out/'bounds.csv',bounds)
    x.p.write(out/'summary.json',dict(new_runs=new_count,reused_controls=24,records=len(records),
        elapsed_s=time.monotonic()-began,hashes_unchanged=True,device_commands=0,
        independent_device_validation=False,experiment_ready=False))
    return grouped


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    run(args.output)
