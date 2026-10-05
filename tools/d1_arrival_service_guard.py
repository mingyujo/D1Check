"""Apply a conservative research service guard to archived PC results.

This is a post hoc readout for the archived cases, not a service SLA or an
independent evaluation. The same rule is recorded for future comparison.
"""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from tools import d1_arrival_service_choice as choice


SOURCE = choice.ROOT / 'docs/results/arrival_service_choice_01/readout/service_cases.csv'
CONTRACT = choice.ROOT / 'docs/results/arrival_service_guard_01/guard_contract.json'
POLICIES = choice.POLICIES


def screen(policy, reference, contract):
    if (policy['scenario'], policy['realized'], policy['seed']) != (
            reference['scenario'], reference['realized'], reference['seed']):
        raise ValueError('different trace or interference')
    if (policy['planned'], policy['urgent_planned'], policy['normal_planned']) != (
            reference['planned'], reference['urgent_planned'], reference['normal_planned']):
        raise ValueError('request denominators differ')
    failures = []
    if contract['require_full_completion'] and (
            int(policy['unfinished']) or int(reference['unfinished'])):
        failures.append('incomplete_requests')
    if (int(policy['urgent_not_timely']) - int(reference['urgent_not_timely']) >
            contract['max_urgent_not_timely_delta_count']):
        failures.append('urgent_deadline_loss')
    if (int(policy['normal_not_timely']) - int(reference['normal_not_timely']) >
            contract['max_normal_not_timely_delta_count']):
        failures.append('normal_deadline_loss')
    if (Decimal(policy['urgent_p95_ms']) - Decimal(reference['urgent_p95_ms']) >
            Decimal(contract['max_urgent_p95_delta_ms'])):
        failures.append('urgent_p95_loss')
    return dict(scenario=policy['scenario'], realized=policy['realized'], seed=policy['seed'],
        policy=policy['policy'], reference='CPU_URGENT', eligible=len(failures) == 0,
        failed_conditions='|'.join(failures),
        urgent_p95_delta_ms=str(Decimal(policy['urgent_p95_ms']) - Decimal(reference['urgent_p95_ms'])),
        normal_mean_delta_ms=str(Decimal(policy['normal_mean_ms']) - Decimal(reference['normal_mean_ms'])),
        urgent_not_timely_delta=int(policy['urgent_not_timely']) - int(reference['urgent_not_timely']),
        normal_not_timely_delta=int(policy['normal_not_timely']) - int(reference['normal_not_timely']),
        completed=int(policy['planned']) - int(policy['unfinished']), planned=int(policy['planned']),
        energy_j=None, ap_peak_c=None, energy_ap_rank=None)


def evaluate(output, source=SOURCE, contract_file=CONTRACT):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    contract = json.loads(Path(contract_file).read_text(encoding='utf-8'))
    if contract['id'] != 'ARRIVAL-SERVICE-GUARD-01' or contract['version'] != 1 or (
            contract['reference_policy'], tuple(contract['candidate_policies'])) != (
                'CPU_URGENT', POLICIES[1:]):
        raise ValueError('service guard contract changed')
    if choice.digest(Path(source)) != contract['archived_service_cases_sha256']:
        raise ValueError('archived service cases changed')
    source_rows = choice.rows(Path(source))
    indexed = {(r['scenario'], r['realized'], r['seed'], r['policy']): r for r in source_rows}
    if len(source_rows) != 135 or len(indexed) != 135:
        raise ValueError('archived service coverage changed')
    if any(r['energy_j'] != '' or r['ap_peak_c'] != '' for r in source_rows):
        raise ValueError('measured energy/AP support changed')
    keys = sorted({k[:3] for k in indexed})
    if len(keys) != 45 or any({policy for policy in POLICIES if k + (policy,) in indexed} !=
                              set(POLICIES) for k in keys):
        raise ValueError('missing paired policy')
    results = [screen(indexed[k + (policy,)], indexed[k + ('CPU_URGENT',)], contract)
               for k in keys for policy in POLICIES]
    selected = [r for r in results if (r['scenario'], r['realized'], r['seed']) ==
                choice.REPRESENTATIVE]
    counts = Counter((r['policy'], r['eligible']) for r in results if r['policy'] != 'CPU_URGENT')
    summary = dict(version='arrival-service-guard-v1',
        interpretation='posthoc on archived PC results; fixed only for future independent use',
        source_sha256=choice.digest(Path(source)), contract_sha256=choice.digest(Path(contract_file)),
        paired_conditions=len(keys), case_count=len(results), representative=selected,
        candidate_eligible_counts={p: counts[p, True] for p in POLICIES[1:]},
        candidate_ineligible_counts={p: counts[p, False] for p in POLICIES[1:]},
        eligible_both_count=sum(all(indexed_result['eligible'] for indexed_result in results
            if (indexed_result['scenario'], indexed_result['realized'], indexed_result['seed']) == k
            and indexed_result['policy'] != 'CPU_URGENT') for k in keys),
        energy_ap_policy_rank=None, experiment_ready=False)
    output.mkdir(parents=True)
    choice.write_csv(output / 'guard_cases.csv', results)
    (output / 'guard_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    result = evaluate(parser.parse_args().output)
    print(json.dumps({key: result[key] for key in
        ('paired_conditions', 'candidate_eligible_counts', 'eligible_both_count')}))


if __name__ == '__main__':
    main()
