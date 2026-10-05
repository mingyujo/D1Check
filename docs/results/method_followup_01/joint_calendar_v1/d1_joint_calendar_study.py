"""Four registered same-input offline references; no online/controller claim."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess
import time
from tools import d1_joint_calendar as solver
from tools import d1_method_workbench as work
from tools import d1_method_followup as followup

P = work.budget.readout.source.f.x.p


def spec():
    return dict(version='joint-calendar-reference-v1', cases=['g0.45_c0.5_b4', 'g0.45_c0.75_b4'],
        seeds=[223001, 223002], scenario='mean', grid_s=.02, solver_time_limit_s=120.,
        maximum_solves=4, overall_pc_limit_s=1200.,
        selection='same four full48 queue references as previous calendar, now adding rectified AP area; no result-selected input',
        objective='minimize modeled J while every original response deadline, EFT peak and EFT rectified AP area hold',
        thermal='original query35..180 1s; same preload; area above effective idle, not measured ambient',
        replay='unchanged engine and original five phases; planning occupancy rounded up',
        freeze='no finer-grid retry, extra cases, changed caps or coefficients after results',
        interpretation='posthoc offline reference knows future arrivals/service; neither causal policy nor physical optimality',
        strict_supported=False, independent_device_validation=False, experiment_ready=False,
        device_commands=0)


def run(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    rule = spec(); hashes = work.verify_resources()
    files = [Path(__file__), Path(solver.__file__), Path(solver.original.__file__),
             Path(followup.x.__file__), Path(P.__file__), Path(followup.x.old.engine.__file__)]
    code = {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in files}
    P.write(out/'registered_before_run.json', dict(spec=rule, resources=hashes, code=code,
        utc=datetime.now(timezone.utc).isoformat(),
        base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_dirty=True))
    for p in (Path(__file__), Path(solver.__file__)):
        (out/p.name).write_bytes(p.read_bytes())
    references = work.budget.readout.source.records(work.budget.ROOT/'run_v1/records.jsonl.gz')
    controls = {(r['meta']['envelope'], r['meta']['seed']): r for r in references
        if r['meta']['stage'] == work.budget.STAGE and r['meta']['scenario'] == rule['scenario'] and
        r['meta']['policy'] == 'EFT_REFERENCE' and r['meta']['envelope'] in rule['cases'] and
        r['meta']['seed'] in rule['seeds']}
    if len(controls) != 4: raise ValueError('complete same-input references required')
    frozen, initial_case = P.inputs(P.BUNDLE); rows = []; records = []; start = time.monotonic()
    try:
        for envelope in rule['cases']:
            for seed in rule['seeds']:
                if time.monotonic()-start >= rule['overall_pc_limit_s']:
                    raise TimeoutError('bounded reference; no automatic restart')
                control = controls[envelope, seed]; ref = control['meta']
                work.audit_record(control, frozen)
                if ref['deadline_met'] != 48: raise ValueError('reference service incomplete')
                result = solver.plan(frozen, initial_case['initial'], followup.tickets(control),
                    ap_cap_c=ref['peak_ap_c'], area_cap_c_s=ref['thermal_degree_seconds'],
                    scenario=rule['scenario'], grid_s=rule['grid_s'], timeout_s=rule['solver_time_limit_s'])
                metric = result.get('metrics')
                row = dict(envelope=envelope, seed=seed, scenario=rule['scenario'], planned=48,
                    status=result['status'], solver_status=result.get('status_code'),
                    solver_gap=result.get('solver_gap'), future_information=True,
                    grid_optimality_only=result.get('grid_optimality_only', False),
                    deadline_met=None if metric is None else metric['deadline_met'],
                    **{f'delta_{k}': None if metric is None else metric[k]-ref[k] for k in
                       ('energy_j', 'peak_ap_c', 'thermal_degree_seconds', 'urgent_p95_ms', 'normal_mean_ms')},
                    exact_replay_joint_nonworsening=bool(metric and metric['deadline_met'] == 48 and
                        all(metric[k] <= ref[k]+1e-8 for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds')) and
                        any(metric[k] < ref[k]-1e-8 for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds'))),
                    accuracy_pass=None, device_policy_winner=None, experiment_ready=False)
                rows.append(row); records.append(dict(meta=row, reference=ref, result=result))
                followup.x.old.csv_write(out/'results.csv', rows)
                raw = ''.join(json.dumps(z, allow_nan=False)+'\n' for z in records).encode('utf8')
                (out/'records.jsonl.gz').write_bytes(gzip.compress(raw, mtime=0))
                P.write(out/'progress.json', dict(solves=len(rows), elapsed_s=time.monotonic()-start,
                    replayed=sum(r['deadline_met'] is not None for r in rows)))
                print(envelope, seed, row['status'], row['solver_gap'], row['delta_energy_j'],
                      row['delta_peak_ap_c'], row['delta_thermal_degree_seconds'], flush=True)
    except BaseException as error:
        import traceback
        P.write(out/'PC_FAILURE.json', dict(error_type=type(error).__name__, message=str(error),
            stack=traceback.format_exc(), completed_solves=len(rows), original_error_preserved=True))
        raise
    if code != {p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in files} or hashes != work.verify_resources():
        raise ValueError('registered evidence changed')
    P.write(out/'summary.json', dict(solves=len(rows), elapsed_s=time.monotonic()-start,
        new_offline_replays=sum(r['deadline_met'] is not None for r in rows),
        joint_nonworsening=sum(r['exact_replay_joint_nonworsening'] for r in rows),
        physical_optimality_proved=False, online_policy=False, device_commands=0, experiment_ready=False))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
