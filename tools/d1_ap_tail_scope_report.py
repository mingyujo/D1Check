"""Reuse 33 stored session scores and two fixed confirmation scores; no fit/device."""
import argparse
import csv
import json
from pathlib import Path

from tools import d1_ap_tail_scope as api


def rows(path):
    with Path(path).open(encoding='utf8', newline='') as stream:
        return list(csv.DictReader(stream))


def model_contract_digest(manifest):
    import hashlib
    payload = {key: {k: value[k] for k in ('model', 'input', 'runtime', 'tensor', 'comparator')}
               | {'backend': value['execution']['backend']} for key, value in manifest['models'].items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def context_from_recorded(folder, scope, variant, inventory, label):
    manifest_path = folder / 'input_manifest.json'
    if api.sha(manifest_path) != inventory[label + '/input_manifest.json']:
        raise ValueError('recorded manifest changed')
    m = api.tail.s.j.m.read(manifest_path)
    identity = api.tail.s.j.m.read(folder / 'before_session_identity.json')
    if identity['model'].replace('-', '_') != scope['expected_context']['device_model'] or \
            identity['fingerprint'] != m['device_fingerprint']:
        raise ValueError('recorded device identity differs')
    if api.sha(folder / 'validated.json') != inventory[label + '/validated.json']:
        raise ValueError('recorded validation changed')
    stats = api.tail.s.j.m.read(folder / 'validated.json')
    cleanup = api.tail.s.j.m.read(folder / 'artifacts/cleanup.json')
    if (stats['runtimes'], stats['warmup_calls'], stats['eligibility_calls']) != (4, 8, 4) or \
            cleanup['status'] != 'completed' or cleanup.get('error') is not None:
        raise ValueError('recorded preparation/cleanup incomplete')
    c = dict(scope['expected_context'])
    c.update(protocol=m['protocol'], apk_sha256=m['apk_sha256'],
             sample_period_ms=m['power_sample_period_ms'], cpu_threads=m['cpu_threads'],
             resident_keys=sorted(m['models']), model_contract_sha256=model_contract_digest(m),
             screen_observation=scope['variants'][variant]['screen_observation'],
             warmup_count=m['warmup_count'], probe_counts=m['probe_counts'],
             baseline_seconds=m['baseline_seconds'], cadence_ms=m['cadence_ms'],
             preparation_fixed_seconds=m['temperature_preparation']['fixed_seconds'])
    # The portable context is an assertion for this recorded case, not a live-device gate.
    return c


def run(output, external_root):
    scope, _, _ = api.read_assets()
    root = api.ROOT
    original_scores = rows(root / 'docs/results/ap_tail_identification_01/run_v2/metrics.csv')
    long_scores = rows(root / 'docs/results/ap_tail_observation_run_05/run_v6/metrics.csv')
    new = api.tail.s.j.m.read(api.tail.s.INPUTS)
    archive, _ = api.tail.s.j.panel()
    long = api.tail.s.j.m.read(root / 'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    inputs = [(c, 'development_loso') for c in new] + \
        [(c, 'archive_posthoc') for c in archive] + [(c, 'independent_long_transfer') for c in long]
    contexts = {}
    short_inventory = api.tail.s.j.m.read(root / 'docs/results/resident_identification_run_01/recorded_v3/inventory.json')
    long_inventory = api.tail.s.j.m.read(root / 'docs/results/ap_tail_observation_run_05/run_v6/inventory.json')['raw_files']
    folders = sorted((external_root / 'energy_ap_resident_identification_run_v3').glob('0*_*'))
    if len(folders) != len(new):
        raise ValueError('recorded four development manifests unavailable')
    for c, folder in zip(new, folders):
        contexts[c['id']] = context_from_recorded(folder, scope, 'resident_short', short_inventory, c['id'])
    folders = sorted((external_root / 'energy_ap_tail_observation_run_v6').glob('0*_*'))
    if len(folders) != len(long):
        raise ValueError('recorded two confirmation manifests unavailable')
    for c, folder in zip(long, folders):
        contexts[c['id']] = context_from_recorded(folder, scope, 'tail_long', long_inventory, c['policy'])
    audits, comparisons = [], []
    curves = rows(root / 'docs/results/ap_tail_observation_run_05/run_v6/curves.csv')
    for c, stage in inputs:
        reasons = api.schedule_reasons(c, scope)
        result = dict(status='blocked', reasons=reasons, prediction_ap_c=None)
        if not reasons:
            result = api.forecast(c, contexts[c['id']], opt_in=True)
            if result['status'] != 'diagnostic_AP_only':
                raise ValueError('recorded macro context unexpectedly blocked: ' + str(result['reasons']))
        if stage == 'independent_long_transfer':
            saved = [r for r in curves if r['session'] == c['policy']]
            if len(saved) != len(c['q']) or any(abs(float(r['LOAD_SLOW']) - y) > 1e-12
                                                for r, y in zip(saved, result['prediction_ap_c'])):
                raise ValueError('guarded path differs from fixed confirmation prediction')
            metric = lambda name: next(r for r in long_scores if r['session'] == c['policy']
                                     and r['model'] == name and r['phase'] == 'full_AP')
        else:
            metric = lambda name: next(r for r in original_scores if r['session'] == c['id']
                                     and r['stage'] == stage and r['model'] == name)
        f, candidate = metric('FROZEN'), metric('LOAD_SLOW')
        # Historical scores are retained even when the new guard denies calculation.
        diff = float(candidate['mae_c']) - float(f['mae_c'])
        comparisons.append(dict(session=c['id'], policy=c['policy'], block=c.get('block', 'resident_new'),
            evidence_stage=stage, frozen_mae_c=f['mae_c'], load_slow_mae_c=candidate['mae_c'],
            mae_change_c=diff, worse_than_frozen=diff > 1e-10,
            frozen_max_c=f['max_absolute_error_c'], candidate_max_c=candidate['max_absolute_error_c'],
            frozen_peak_signed_c=f['peak_signed_error_c'], candidate_peak_signed_c=candidate['peak_signed_error_c']))
        audits.append(dict(session=c['id'], policy=c['policy'], evidence_stage=stage,
            code_numeric_available_in_prior_analysis=True, diagnostic_status=result['status'],
            reasons=';'.join(result['reasons']), context_checked=c['id'] in contexts,
            pre_last_ap_c=c['pre'][-1]['ap'], query_end_s=c['q'][-1],
            schedule_end_s=c['actual'][-1]['end_s'], empirical_strict_support=False,
            independent_confirmation=stage == 'independent_long_transfer', accuracy_pass=None,
            policy_difference_certified=False, energy_candidate_output=False))
    api.tail.s.csv_write(out / 'scope_audit.csv', audits)
    api.tail.s.csv_write(out / 'retained_errors.csv', comparisons)
    api.tail.s.csv_write(out / 'retained_worsening.csv', [r for r in comparisons if r['worse_than_frozen']])
    api.tail.s.write(out / 'recorded_contexts.json', contexts)
    result = dict(sessions=len(audits), registered_diagnostic_contexts=sum(r['diagnostic_status']=='diagnostic_AP_only' for r in audits),
        blocked=sum(r['diagnostic_status']=='blocked' for r in audits),
        archive_worsening_preserved=sum(r['evidence_stage']=='archive_posthoc' and r['worse_than_frozen'] for r in comparisons),
        new_confirmed_conditions=2, candidate_refits=0, environment_simulations=0, device_commands=0,
        strict_support=False, accuracy_pass=None, default_changed=False, rl_changed=False, experiment_ready=False,
        metrics_reused=True, full_confirmed_curve_equal=True, scope_sha256=api.sha(api.SCOPE))
    api.tail.s.write(out / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--external-root', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, Path(args.external_root))))


if __name__ == '__main__':
    main()
