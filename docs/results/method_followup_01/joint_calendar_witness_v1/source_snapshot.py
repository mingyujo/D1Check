"""One deterministic grid CPU witness, not a policy search or MIP restart.

Distinguishes failure to find an integer incumbent from infeasible model caps.
Same original cases/grid; no changed limits, fitted coefficients or retries.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from tools import d1_joint_calendar_study as study

P = study.P


def calendar(tickets, profile, grid_s=.02):
    pending = sorted(copy.deepcopy(tickets), key=lambda r: (r['arrival_ns'], r['ordinal']))
    queue = []; jobs = []; now = 35.; pos = 0
    while pos < len(pending) or queue:
        if not queue and pending[pos]['arrival_ns']/1e9 > now:
            now = 35.+math.ceil((pending[pos]['arrival_ns']/1e9-35.)/grid_s-1e-8)*grid_s
        while pos < len(pending) and pending[pos]['arrival_ns']/1e9 <= now+1e-9:
            queue.append(pending[pos]); pos += 1
        if not queue: raise ValueError('witness clock moved arrival backwards')
        q = min(queue, key=lambda r: (r['arrival_ns']+r['deadline_offset_ns'], r['ordinal']))
        queue.remove(q); phases = profile[P.key(q, 'CPU')]
        hold = sum(phases)/1e9; response = sum(phases[:2 if q['priority'] == 'urgent' else 3])/1e9
        jobs.append(dict(id=q['id'], state=q['task']+'_CPU', backend='CPU', start=now, end=now+hold,
            response=now+response, deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9,
            already_responded=False))
        now += math.ceil(hold/grid_s-1e-8)*grid_s
    return jobs


def evaluate(control, frozen, initial):
    meta = control['meta']; tickets = study.followup.tickets(control)
    phases = P.profile(frozen, 'mean'); jobs = calendar(tickets, phases)
    study.followup.x.validate_schedule(jobs, tickets, phases)
    rounded = copy.deepcopy(jobs)
    for j in rounded:
        q = next(q for q in tickets if q['id'] == j['id'])
        j['end'] = j['start']+math.ceil(sum(phases[P.key(q, j['backend'])])/1e9/.02-1e-8)*.02
    segments = P.segments(rounded, 0., 180.)
    planning = P.model.costs(segments, initial, list(range(35, 181)), frozen, 180.)
    reference = P.memory.initialize(initial['preload'], frozen['ap']['beta'], 30.)['reference_c']
    rise = [max(0., t-reference) for t in planning['ap_path']]
    area = sum((a+b)*.5 for a, b in zip(rise, rise[1:])); peak = max(planning['ap_path'])
    planning_service = all(j['response'] <= j['deadline']+1e-9 for j in jobs)
    row, result, _, actual_segments, cost = study.followup.x.simulate(
        frozen, initial, tickets, 'mean', study.followup.x.REPLAY, jobs)
    proof = dict(envelope=meta['envelope'], seed=meta['seed'], planned=48,
        planning_response_deadlines=planning_service, rounded_peak_cap=peak <= meta['peak_ap_c']+1e-8,
        rounded_area_cap=area <= meta['thermal_degree_seconds']+1e-8,
        planning_peak_c=peak, planning_area_c_s=area,
        same_grid_feasible_witness=planning_service and peak <= meta['peak_ap_c']+1e-8 and area <= meta['thermal_degree_seconds']+1e-8,
        actual_deadline_met=row['deadline_met'],
        delta_energy_j=row['energy_j']-meta['energy_j'], delta_peak_ap_c=row['peak_ap_c']-meta['peak_ap_c'],
        delta_AP_area_c_s=row['thermal_degree_seconds']-meta['thermal_degree_seconds'],
        physical_or_optimality_claim=False, device_commands=0, experiment_ready=False)
    return dict(proof=proof, jobs=jobs, ledger=result['ledger'], segments=actual_segments,
                predicted_ap_path=cost['ap_path'])


def run(output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    rule = study.spec(); hashes = study.work.verify_resources()
    P.write(out/'registered_before_analysis.json', dict(timestamp=datetime.now(timezone.utc).isoformat(),
        selection='all four current joint-calendar inputs, no new input selection',
        algorithm='CPU only, arrived earliest absolute response deadline, ordinal tie; same20ms grid',
        purpose='constructive feasibility witness, not energy optimizer, policy search or native solver rerun',
        maximum_calendars=4, maximum_PC_replays=4, grid_s=.02, resources=hashes,
        source_sha256=P.digest(Path(__file__)), device_commands=0, experiment_ready=False))
    (out/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    frozen, case = P.inputs(P.BUNDLE); records = []; rows = []
    for r in study.work.budget.readout.source.records(study.work.budget.ROOT/'run_v1/records.jsonl.gz'):
        m = r['meta']
        if (m['stage'] == study.work.budget.STAGE and m['policy'] == 'EFT_REFERENCE' and
                m['scenario'] == 'mean' and m['envelope'] in rule['cases'] and m['seed'] in rule['seeds']):
            result = evaluate(r, frozen, case['initial']); records.append(result); rows.append(result['proof'])
    if len(rows) != 4: raise ValueError('complete witness denominator required')
    P.write(out/'result.json', dict(records=records, native_MIP_restarts=0, PC_replays=4,
        device_commands=0, experiment_ready=False))
    study.followup.x.old.csv_write(out/'witnesses.csv', rows)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    print(json.dumps(run(parser.parse_args().output)))
