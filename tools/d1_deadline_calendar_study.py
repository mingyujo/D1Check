"""Registered bounded offline reference study; not an online policy."""
import argparse
from datetime import datetime,timezone
import gzip
import json
from pathlib import Path
import time
from tools import d1_deadline_calendar as optimizer
from tools import d1_method_followup as followup
x=followup.x


def spec():
    return dict(version='offline-calendar-reference-v1',
        source='docs/results/method_followup_01/run_v1/records.jsonl.gz',
        cases=['g0.45_c0.5_b4','g0.45_c0.75_b4'],seeds=[223001,223002],scenario='mean',
        modes=['min_J','min_J_under_EFT_peak'],grid_s=.02,solver_time_limit_s=45.,
        max_wall_s=900.,maximum_solves=8,
        service='every scheduled request must meet its original response deadline; preserve original five-phase replay',
        thermal='same 1s AP query grid 35..180; modeled EFT peak cap is comparison, not safety certification',
        objective='minimize same-work modeled J on rounded nonpreemptive grid; evaluate incumbent with unrounded engine',
        cutoff='solver incumbent/timeouts/infeasibility retained; no finer grid or parameter retuning in this run',
        scope='future input and actual scenario known; offline reference not deployable policy; grid optimum not original continuum optimum',
        model_sha256=x.p.MODEL_SHA,initial_sha256=x.p.INITIAL_SHA,
        strict_supported=False,independent_device_validation=False,experiment_ready=False,device_commands=0)


def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);s=spec();began=time.monotonic()
    source=x.p.ROOT/s['source'];raw=gzip.decompress(source.read_bytes())
    controls={}
    for line in raw.decode('utf8').splitlines():
        r=json.loads(line);m=r['meta']
        if (m['stage']=='new_seed_confirmation' and m['envelope'] in s['cases'] and m['seed'] in s['seeds']
                and m['scenario']==s['scenario'] and m['policy']=='EFT_REFERENCE'):
            controls[m['envelope'],m['seed']]=r
    if len(controls)!=4:raise ValueError('missing exact reference inputs')
    frozen,case=x.p.inputs(x.p.BUNDLE);initial=case['initial']
    paths=[Path(__file__),Path(optimizer.__file__),Path(x.__file__),Path(x.p.__file__),
        x.p.BUNDLE/'model.json',x.p.BUNDLE/'initial_inputs.json',source]
    hashes={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}
    x.p.write(out/'registered_before_run.json',dict(spec=s,hashes=hashes,utc=datetime.now(timezone.utc).isoformat(),
        base_head='42890f417871c262685bce0e6bb6a85d908d1372',implementation_dirty=True))
    rows=[];records=[]
    try:
        for env in s['cases']:
            for seed in s['seeds']:
                c=controls[env,seed];qs=followup.tickets(c);ref=c['meta']
                for mode in s['modes']:
                    if time.monotonic()-began>s['max_wall_s']:raise TimeoutError('bounded offline reference')
                    result=optimizer.plan(frozen,initial,qs,scenario=s['scenario'],grid_s=s['grid_s'],
                        timeout_s=s['solver_time_limit_s'],ap_cap_c=ref['peak_ap_c'] if mode.endswith('peak') else None)
                    row={k:v for k,v in result.items() if k not in ('jobs','ledger','segments','predicted_ap_path','metrics')}
                    row.update(envelope=env,seed=seed,mode=mode,planned=len(qs),scenario=s['scenario'],
                        EFT_j=ref['energy_j'],EFT_peak_ap_c=ref['peak_ap_c'],
                        EFT_urgent_p95_ms=ref['urgent_p95_ms'],EFT_normal_mean_ms=ref['normal_mean_ms'])
                    m=result.get('metrics')
                    for k in ('energy_j','peak_ap_c','thermal_degree_seconds','urgent_p95_ms','normal_mean_ms','deadline_met'):
                        row['replay_'+k]=m[k] if m else None
                        row['delta_'+k]=m[k]-ref[k] if m else None
                    row['joint_nonworsening_in_replay']=bool(m and m['deadline_met']==len(qs) and all(
                        m[k]<=ref[k]+1e-8 for k in ('energy_j','peak_ap_c','thermal_degree_seconds')) and any(
                        m[k]<ref[k]-1e-8 for k in ('energy_j','peak_ap_c','thermal_degree_seconds')))
                    rows.append(row);records.append(dict(meta=row,**result))
                    fields=sorted(set().union(*(r.keys() for r in rows)))
                    x.old.csv_write(out/'results.csv',[{k:r.get(k) for k in fields} for r in rows])
                    x.p.write(out/'progress.json',dict(solves=len(rows),elapsed_s=time.monotonic()-began))
                    print(env,seed,mode,result['status'],result.get('solver_gap'),row['delta_energy_j'],row['delta_peak_ap_c'],flush=True)
    finally:
        raw=''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in records).encode('utf8')
        (out/'records.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    if hashes!={p.relative_to(x.p.ROOT).as_posix():x.p.digest(p) for p in paths}:raise ValueError('registered source changed')
    x.p.write(out/'summary.json',dict(solves=len(rows),elapsed_s=time.monotonic()-began,
        replayed=sum(r['status']=='replayed_incumbent' for r in rows),
        joint_nonworsening_in_replay=sum(r['joint_nonworsening_in_replay'] for r in rows),
        no_incumbent=sum(r['status']=='no_incumbent' for r in rows),hashes_unchanged=True,
        device_commands=0,experiment_ready=False))
    return rows


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();run(args.output)
