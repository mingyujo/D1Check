"""Necessary joint-cost bounds for the *existing* frozen PC model.

Positive heat impulses relax real jobs, arrivals, lanes and power limits. A
positive saving upper bound is NOT a realizable schedule or a device benefit.
No fitting, invented thermal coefficients, simulator batch, or device commands.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import numpy as np
from scipy.optimize import linprog
from tools import d1_method_workbench as work

P = work.budget.readout.source.f.x.p
Q = np.arange(35., 181.)
WEIGHTS = np.ones(len(Q)); WEIGHTS[[0, -1]] = .5
NUMERIC_PAD = 1e-6  # Numerical relaxation only; never a device accuracy criterion.


def identity(frozen, context):
    a = frozen['ap']; w = frozen['energy_increment_w']
    if a['g'] != 0 or not a['beta'] > 0 or not a['k'] > 0:
        raise ValueError('bound supports only registered positive beta/k and g=0')
    phases = P.profile(frozen, context)
    c, g, d = (sum(phases[x])/1e9 for x in P.CELLS)
    slopes = a['parameters']['ap_slope_at_30_c_per_s']
    drive = {x: slopes[x]-slopes['resident_idle'] for x in w}
    lam = w['classification_GPU']+w['detection_CPU']-w['classification_GPU+detection_CPU']
    coupling = drive['classification_GPU+detection_CPU']-drive['classification_GPU']-drive['detection_CPU']
    if min(drive.values()) < 0 or lam <= 0 or coupling <= 0:
        raise ValueError('positive-input/overlap identity unsupported; no guessed replacement')
    return phases, (c, g, d), drive, lam, coupling


def heat_capacity(base, reference, beta, gain, latest, area_cap, peak_cap=None):
    """Upper bound on integrated input H under the same sampled AP caps.

    Moving input within [j,j+1) to j+ reduces its effect at every future integer
    query. Positive impulses and freely allocated input are a superset of real
    lane schedules. The max-H LP therefore bounds *all* feasible real schedules.
    Repair its dual to satisfy y>=0, y_heat<=y_area*w, K' y>=1 before reporting.
    """
    if (not 35 <= latest < 180 or not math.isfinite(area_cap) or area_cap < 0 or
            not np.all(np.isfinite(base)) or len(base) != len(Q)):
        raise ValueError('invalid registered AP boundary')
    times = np.arange(35., math.floor(latest)+1)
    kernel = gain*np.exp(-beta*np.maximum(Q[:, None]-times[None, :], 0))*(Q[:, None] > times[None, :])
    n, m = len(times), len(Q)
    matrix = np.vstack((np.hstack((kernel, -np.eye(m))), np.r_[np.zeros(n), WEIGHTS][None, :]))
    rhs = np.r_[reference-base, area_cap]
    if peak_cap is not None:
        if not math.isfinite(peak_cap): raise ValueError('missing peak cap')
        matrix = np.vstack((matrix, np.hstack((kernel, np.zeros((m, m))))))
        rhs = np.r_[rhs, peak_cap-base]
    sol = linprog(np.r_[-np.ones(n), np.zeros(m)], A_ub=matrix, b_ub=rhs,
                  bounds=(0, None), method='highs', options={'time_limit': 5.})
    if not sol.success:
        return dict(status='unresolved', solver_status=int(sol.status), heat_upper_c=None,
                    solver_message=sol.message)
    y = np.maximum(0., -sol.ineqlin.marginals)
    y[:m] = np.minimum(y[:m], y[m]*WEIGHTS)
    extra = y[m+1:] if peak_cap is not None else np.zeros(m)
    rate = float(min(kernel.T@(y[:m]+extra)))
    if not math.isfinite(rate) or rate <= 0:
        return dict(status='unresolved', solver_status=int(sol.status), heat_upper_c=None,
                    solver_message='cannot repair positive dual coverage')
    y *= (1.+1e-10)/rate
    # A'x dual constraints: -A' y <= c. The repaired vector provides a bound,
    # independently of whether the solver's feasible schedule is realizable.
    feasibility = float(min(matrix.T@y-np.r_[np.ones(n), np.zeros(m)]))
    if feasibility < -1e-8 or not np.all(np.isfinite(y)):
        raise ValueError('dual bound must be feasible; no success from solver flag alone')
    upper = float(rhs@y)+NUMERIC_PAD
    primal = -float(sol.fun)
    if upper < primal-1e-8:
        raise ValueError('dual below primal')
    return dict(status='relaxed_numerical_bound', solver_status=0, heat_upper_c=upper,
        primal_heat_c=primal, primal_dual_gap_c=upper-primal,
        dual_min_slack=feasibility, relaxed_impulse_times_s=times.tolist(),
        dual_nonnegative=y.tolist(), realizable_schedule=False)


def case_bound(record, frozen, initial):
    meta = record['meta']
    work.audit_record(record, frozen)
    if meta['deadline_met'] != 48:
        return dict(status='reference_deadlines_failed', energy_gain_upper_j=None,
                    heat_upper_c=None, skipped=True)
    phases, (c, g, d), drive, lam, coupling = identity(frozen, meta['scenario'])
    for r in record['ledger']:
        durations = phases[P.key(r, r['backend'])]
        actual = [r[b]-r[a] for a, b in zip(
            ('dispatch_ns', 'execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns'),
            ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns'))]
        if any(abs(x-y) > 2 for x, y in zip(actual, durations)):
            raise ValueError('bound cannot transfer changed service durations')
    latest = max(r['arrival_ns']/1e9+r['deadline_offset_ns']/1e9+
        max(sum(phases[P.key(r, b)][2 if r['priority'] == 'urgent' else 3:])/1e9
            for b in P.backends(r))+2e-9 for r in record['ledger'])
    ap = frozen['ap']
    base = np.array(P.model.costs([dict(start_s=0., end_s=180., state='idle')],
        initial, Q.tolist(), frozen, 180.)['ap_path'])
    reference = P.memory.initialize(initial['preload'], ap['beta'], 30.)['reference_c']
    bound = heat_capacity(base, reference, ap['beta'], ap['k'], latest,
                          meta['thermal_degree_seconds'], meta['peak_ap_c'])
    if bound['heat_upper_c'] is None:
        return dict(bound, energy_gain_upper_j=None, skipped=False)
    nc = sum(q['task'] == 'classification' for q in record['ledger']); nd = 48-nc
    w = frozen['energy_increment_w']; options = []
    # Independent endpoint ns rounding: each full lane duration differs by <1ns.
    # Conservative total errors allow endpoint/intersection rounding; not sensor error.
    e_pad = 48*(max(w.values())+lam)*2e-9
    h_pad = 48*(max(drive.values())+coupling)*2e-9
    for ng in range(nc+1):
        heat = (nc-ng)*c*drive['classification_CPU']+ng*g*drive['classification_GPU']+nd*d*drive['detection_CPU']
        if heat > bound['heat_upper_c']+h_pad: continue
        overlap = min(ng*(g+1e-9), nd*(d+1e-9), (bound['heat_upper_c']-heat+h_pad)/coupling)
        energy = (120*initial['preload_power_w']+(nc-ng)*c*w['classification_CPU']+
                  ng*g*w['classification_GPU']+nd*d*w['detection_CPU']-lam*overlap-e_pad)
        options.append(dict(energy_gain_upper_j=meta['energy_j']-energy,
                            relaxed_gpu_count=ng, relaxed_overlap_s=overlap))
    if not options: raise ValueError('reference must remain in relaxation')
    best = max(options, key=lambda r: r['energy_gain_upper_j'])
    return dict(bound, **best, latest_lane_bound_s=latest, skipped=False,
        ns_rounding_energy_pad_j=e_pad, ns_rounding_drive_pad_c=h_pad,
        joint_gain_proven_possible=False, impossibility_ruled_out=False,
        note='positive upper bound proves neither feasibility nor impossibility; never a policy proposal')


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    hashes = work.verify_resources()
    frozen, initial_case = P.inputs(P.BUNDLE)
    P.write(output/'registered_before_analysis.json', dict(version='method-joint-bound-v1',
        timestamp_utc=datetime.now(timezone.utc).isoformat(), data_role='posthoc necessary bound only',
        sources=hashes, code_sha256=P.digest(Path(__file__)), maximum_cases=24,
        LP_time_limit_s=5., overall_limit_s=300., numeric_pad=NUMERIC_PAD,
        caps='each full-service stored EFT peak and rectified AP area; no new physical threshold',
        scope='fixed three development service contexts and same initial history; no new slowdown',
        bound_role='necessary optimistic upper limit, not a realizable schedule or device effect',
        new_simulations=0, device_commands=0, experiment_ready=False))
    started = time.monotonic(); rows = []; certificates = []
    records = work.budget.readout.source.records(work.budget.ROOT/'run_v1/records.jsonl.gz')
    for r in records:
        m = r['meta']
        if m['stage'] != work.budget.STAGE or m['policy'] != 'EFT_REFERENCE': continue
        if time.monotonic()-started >= 300: raise TimeoutError('bounded PC analysis; preserve partial output')
        values = case_bound(r, frozen, initial_case['initial'])
        key = dict(envelope=m['envelope'], seed=m['seed'], scenario=m['scenario'])
        certificates.append(dict(key, **values))
        rows.append(dict(key, planned=48, reference_deadline_met=m['deadline_met'],
            reference_energy_j=m['energy_j'], reference_peak_ap_c=m['peak_ap_c'],
            reference_AP_area_c_s=m['thermal_degree_seconds'], status=values['status'],
            modeled_joint_saving_upper_j=values['energy_gain_upper_j'],
            modeled_drive_upper_c=values['heat_upper_c'],
            realizable_schedule=False, device_policy_winner=None, accuracy_pass=None))
    if len(rows) != 24: raise ValueError('all reference cases, including failures, required')
    P.write(output/'result.json', dict(rows=rows, certificates=certificates, new_simulations=0,
        device_commands=0, experiment_ready=False, physical_advantage_proven=False,
        interpretation='upper bound only; relaxed heat pulses are not jobs, policies or physical heat measurements'))
    work.budget.readout.source.f.x.old.csv_write(output/'bounds.csv', rows)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    print(json.dumps(dict(cases=len(run(parser.parse_args().output)), device_commands=0)))
