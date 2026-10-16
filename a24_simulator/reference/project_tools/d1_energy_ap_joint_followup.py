"""One energy candidate; AP remains fixed. Existing measured sessions only."""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import traceback
import numpy as np

from tools import d1_ap_tail_scope as scope_api
from tools import d1_resident_identification_analysis as analysis
from tools import d1_ap_tail_observation_results as observed

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/energy_ap_joint_followup_01'


def validate_sources():
    reg = analysis.j.m.read(BUNDLE / 'registration.json')
    for path, expected in reg['sources'].items():
        if scope_api.sha(ROOT / path) != expected:
            raise ValueError('registered source changed: ' + path)
    return reg


def train(cases, original, registered_ids):
    if len(cases) < 3 or len({c['id'] for c in cases}) != len(cases) or \
            any(c['id'] not in registered_ids or c['role'] != 'development' or
                c['policy'] not in ('DEV_A', 'DEV_B') for c in cases):
        raise ValueError('only registered macro development sessions may fit')
    value = analysis.energy_fit(cases, original)
    return dict(version='resident-energy-offset-state-v1', **value,
                development_ids=[c['id'] for c in cases], default=False, strict_support=False,
                accuracy_pass=None, experiment_ready=False, coefficient_count=5)


def prediction(case, model, lo, hi):
    """Only pre-load power and actual lane times; no target sensor fields."""
    pre = case['pre_w']
    bias = model['idle_bias_w']
    gains = np.array([model['increments'][k] for k in analysis.j.m.base.STATES])
    if not all(math.isfinite(x) for x in (pre, bias, lo, hi)) or pre <= 0 or pre+bias <= 0 or \
            not np.isfinite(gains).all() or np.any(gains < 0) or not 0 <= lo < hi:
        raise ValueError('invalid or nonpositive power/window; no clipping')
    if hi > case['actual'][-1]['end_s']:
        raise ValueError('prediction extends beyond actual schedule')
    exposure = analysis.j.m.base.exposure(case['actual'], lo, hi)
    return pre*(hi-lo) + (max(0., hi-35)-max(0., lo-35))*bias + float(exposure @ gains)


def fit(output):
    reg = validate_sources()
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    cases = analysis.j.m.read(scope_api.tail.s.INPUTS)
    if [c['id'] for c in cases] != reg['training_ids']:
        raise ValueError('development roster drift')
    original = analysis.j.m.read(analysis.j.m.MODEL)
    fits = []
    for excluded in cases:
        model = train([c for c in cases if c['id'] != excluded['id']], original, reg['training_ids'])
        row = dict(excluded=excluded['id'], model=model)
        analysis.j.m.write(out / ('fold_' + excluded['id'] + '.json'), row)
        fits.append(row)
    final = train(cases, original, reg['training_ids'])
    analysis.j.m.write(out / 'candidate.json', final)
    analysis.j.m.write(out / 'fit_receipt.json', dict(status='energy_frozen_for_posthoc_evaluation',
        family_count=1, energy_fit_calls=5, AP_fit_calls=0,
        candidate_sha256=scope_api.sha(out / 'candidate.json'),
        registration_sha256=scope_api.sha(BUNDLE / 'registration.json'),
        two_long_targets_seen_before_family_selection=True,
        default_changed=False, strict_support=False, experiment_ready=False))
    return final


def table(path):
    with Path(path).open(encoding='utf8', newline='') as f:
        return list(csv.DictReader(f))


def evaluate(output):
    reg = validate_sources()
    out = Path(output)
    receipt = analysis.j.m.read(out / 'fit_receipt.json')
    if receipt['candidate_sha256'] != scope_api.sha(out / 'candidate.json'):
        raise ValueError('candidate drift')
    final = analysis.j.m.read(out / 'candidate.json')
    original = analysis.j.m.read(analysis.j.m.MODEL)
    macro = analysis.j.m.read(scope_api.tail.s.INPUTS)
    archive, _ = analysis.j.panel()
    long = analysis.j.m.read(ROOT / 'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
    old_AP = table(ROOT / 'docs/results/ap_tail_identification_01/run_v2/metrics.csv')
    new_AP = table(ROOT / 'docs/results/ap_tail_observation_run_05/run_v6/metrics.csv')
    pairs = [(c, 'development_loso') for c in macro] + [(c, 'archive_posthoc') for c in archive] + \
            [(c, 'seen_long_posthoc_energy') for c in long]
    energy_rows, joint, paths = [], [], []
    for case, stage in pairs:
        model = analysis.j.m.read(out / ('fold_' + case['id'] + '.json'))['model'] if stage == 'development_loso' else final
        last = case.get('last_lane_s')
        end = case['actual'][-1]['end_s']
        windows = [('reference120', 0., 120.)]
        if stage != 'archive_posthoc':
            windows.append(('registered600', 35., 635.))
            windows.append(('registered_recovery_full', 635., end))
            if min(end, case['power_t'][-1]) > 635.:
                windows.append(('registered_recovery_covered_prefix', 635., min(end, case['power_t'][-1])))
            windows.append(('registered_and_recovery_covered_prefix', 35., min(end, case['power_t'][-1])))
        if last is not None and last > 35:
            windows.append(('work_present_span', 35., last))
        windows.append(('post_lane_idle', max(35., last or 35.), end))
        covered_end = min(end, case['power_t'][-1])
        if covered_end > max(35., last or 35.):
            windows.append(('post_lane_idle_covered_prefix', max(35., last or 35.), covered_end))
        for phase, lo, hi in windows:
            coverage = observed.measured_energy(case, lo, hi)
            measured = coverage['full_energy_j']
            old = analysis.j.m.energy_prediction(case, case['actual'], original, dict(name='FROZEN'), hi) - \
                  analysis.j.m.energy_prediction(case, case['actual'], original, dict(name='FROZEN'), lo)
            new = prediction(dict(pre_w=case['pre_w'], actual=case['actual']), model, lo, hi)
            energy_rows.append(dict(session=case['id'], stage=stage, policy=case['policy'], phase=phase,
                lo_s=lo, hi_s=hi, **coverage, observed_j=measured, frozen_j=old, candidate_j=new,
                frozen_signed_j=old-measured if measured is not None else None,
                candidate_signed_j=new-measured if measured is not None else None,
                frozen_abs_j=abs(old-measured) if measured is not None else None,
                candidate_abs_j=abs(new-measured) if measured is not None else None,
                frozen_relative=(old-measured)/measured if measured else None,
                candidate_relative=(new-measured)/measured if measured else None,
                candidate_nonworse=abs(new-measured)<=abs(old-measured)+1e-9 if measured is not None else None))
        if stage == 'seen_long_posthoc_energy':
            metric = lambda name: next(r for r in new_AP if r['session'] == case['policy']
                                     and r['model'] == name and r['phase'] == 'full_AP')
        else:
            metric = lambda name: next(r for r in old_AP if r['session'] == case['id']
                                     and r['stage'] == stage and r['model'] == name)
        a, b = metric('FROZEN'), metric('LOAD_SLOW')
        er = next(r for r in energy_rows if r['session'] == case['id'] and r['phase'] == 'reference120')
        joint.append(dict(session=case['id'], stage=stage, policy=case['policy'],
            AP_evidence_stage='pre_frozen_independent_long_transfer' if stage=='seen_long_posthoc_energy' else stage,
            energy_window='reference0..120;AP full available recorded path',
            frozen_abs_J=er['frozen_abs_j'], candidate_abs_J=er['candidate_abs_j'],
            frozen_AP_MAE_c=a['mae_c'], candidate_AP_MAE_c=b['mae_c'],
            AP_worse=float(b['mae_c'])>float(a['mae_c'])+1e-10,
            energy_worse=not er['candidate_nonworse'] if er['candidate_nonworse'] is not None else None,
            both_nonworse=bool(er['candidate_nonworse'] and float(b['mae_c'])<=float(a['mae_c'])+1e-10),
            AP_basis_uses_original_energy_proxy=True, policy_difference_certified=False))
        # Cumulative curves end at the measured power prefix; never fill the missing endpoint.
        hi = min(end, case['power_t'][-1])
        for t in np.linspace(0., hi, 201)[1:]:
            cov = observed.measured_energy(case, 0., float(t))
            paths.append(dict(session=case['id'], stage=stage, t_s=float(t), observed_j=cov['full_energy_j'],
                frozen_j=analysis.j.m.energy_prediction(case, case['actual'], original, dict(name='FROZEN'), float(t)),
                candidate_j=prediction(dict(pre_w=case['pre_w'], actual=case['actual']), model, 0., float(t))))
    scope_api.tail.s.csv_write(out / 'energy_errors.csv', energy_rows)
    scope_api.tail.s.csv_write(out / 'joint_errors.csv', joint)
    with gzip.open(out / 'energy_curves.csv.gz', 'wt', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paths[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(paths)
    groups = []
    for stage in dict.fromkeys(r['stage'] for r in energy_rows):
        for phase in ('reference120', 'registered600'):
            use = [r for r in energy_rows if r['stage']==stage and r['phase']==phase and r['observed_j'] is not None]
            if use:
                groups.append(dict(stage=stage, phase=phase, sessions=len(use),
                    frozen_mean_abs_J=float(np.mean([r['frozen_abs_j'] for r in use])),
                    candidate_mean_abs_J=float(np.mean([r['candidate_abs_j'] for r in use])),
                    energy_worse=sum(not r['candidate_nonworse'] for r in use)))
    scope_api.tail.s.csv_write(out / 'summary.csv', groups)
    result = dict(status='posthoc_energy_and_fixed_AP_evaluated', sessions=35,
        energy_candidates=1, energy_fit_calls=5, AP_fit_calls=0, old_AP_worsening_preserved=13,
        numerical_prediction_layer='actual_schedule_conditional', end_to_end_B_evaluated=False,
        policy_difference_certified=False, strict_support=False, accuracy_pass=None,
        default_changed=False, rl_changed=False, experiment_ready=False, device_commands=0,
        AP_uses_frozen_old_energy_proxy='new energy coefficients are never injected into existing AP equation')
    result['adoption'] = 'not_adopted: archive and covered post-lane regressions retained'
    analysis.j.m.write(out / 'combined_bundle.json', dict(energy_candidate='candidate.json',
        energy_candidate_sha256=receipt['candidate_sha256'],
        AP_candidate_file='docs/results/ap_tail_identification_01/run_v2/candidates.json',
        AP_candidate_file_sha256='aa28410d701c9810001a4e6c176823e7d2b446f46f980ebeab3ff14f4540cc84',
        AP_head='LOAD_SLOW', AP_drive_proxy_remains_original=True,
        heads_are_empirical_not_new_physical_coupling=True, default=False, strict_support=False,
        accuracy_pass=None, experiment_ready=False))
    analysis.j.m.write(out / 'receipt.json', result)
    return groups


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--action', choices=('fit', 'evaluate'), required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        result = fit(args.output) if args.action == 'fit' else evaluate(args.output)
    except Exception:
        path = Path(args.output)
        if path.exists():
            with (path / ('FAIL_' + args.action + '.json')).open('x', encoding='utf8') as f:
                json.dump(dict(action=args.action, original_stack=traceback.format_exc(),
                               default_changed=False, device_commands=0), f, indent=2)
        raise
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
