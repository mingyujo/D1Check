"""Summarize archived arrival service results without rerunning the scheduler.

The 1.5/6 second deadlines are research inputs, not an adopted service SLA.
Energy and AP remain unsupported for these arrival schedules.
"""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/arrival_policy_screen_01/repro_bundle'
SUPPORT = ROOT / 'docs/results/arrival_policy_screen_01/measured_support_01'
POLICIES = ('CPU_URGENT', 'B2_PC', 'B3_SOLO_EFT_PC')
REPRESENTATIVE = ('queue', '1.5', '201')  # Archived support audit chose this before this readout.


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def count_misses(rate, denominator):
    value = float(rate) * denominator
    count = round(value)
    if count < 0 or count > denominator or abs(value - count) > 1e-7:
        raise ValueError('deadline rate cannot be mapped to planned requests')
    return count


def service_row(row):
    planned, urgent, normal = (int(row[key]) for key in
                               ('planned', 'urgent_planned', 'normal_planned'))
    if (planned, urgent, normal) != (24, 6, 18):
        raise ValueError('archived request denominator changed')
    unfinished = int(row['unfinished'])
    urgent_miss = count_misses(row['urgent_not_timely_rate'], urgent)
    normal_miss = count_misses(row['normal_not_timely_rate'], normal)
    if unfinished < 0 or unfinished > urgent_miss + normal_miss:
        raise ValueError('unfinished requests are not accounted for as not timely')
    return dict(scenario=row['scenario'], realized=row['realized'], seed=row['seed'],
                policy=row['policy'], planned=planned, urgent_planned=urgent,
                normal_planned=normal, unfinished=unfinished,
                urgent_p95_ms=float(row['urgent_p95_ms']),
                normal_mean_ms=float(row['normal_mean_ms']),
                urgent_not_timely=urgent_miss, normal_not_timely=normal_miss,
                timely_all_planned=planned - urgent_miss - normal_miss,
                timely_share_all_planned=(planned - urgent_miss - normal_miss) / planned,
                energy_j=None, ap_peak_c=None)


def write_csv(path, records):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def evaluate(output):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((BUNDLE / 'SOURCE_HASHES.json').read_text(encoding='utf-8'))
    service_path = BUNDLE / 'service_metrics.csv'
    support_path = SUPPORT / 'support_status.csv'
    if digest(service_path) != manifest['bundle_files']['service_metrics.csv']:
        raise ValueError('archived service metrics differ from manifest')
    audit = json.loads((SUPPORT / 'audit_summary.json').read_text(encoding='utf-8'))
    if digest(service_path) != audit['input_sha256']['service_metrics.csv']:
        raise ValueError('support audit used different service metrics')
    service = [service_row(r) for r in rows(service_path) if r['policy'] in POLICIES]
    support = {(r['scenario'], r['realized'], r['seed'], r['policy']): r
               for r in rows(support_path)}
    keys = {(r['scenario'], r['realized'], r['seed'], r['policy']) for r in service}
    expected = {(scenario, realized, str(seed), policy)
                for scenario in ('low', 'queue', 'burst')
                for realized in ('1.0', '1.5', '2.0')
                for seed in range(201, 206) for policy in POLICIES}
    if len(service) != 135 or keys != expected or set(support) != expected:
        raise ValueError('archived 135-case coverage changed')
    if any(r['unfinished'] != 0 for r in service):
        raise ValueError('archived complete-schedule comparison changed')
    if any(support[k]['energy'] != 'UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS'
           or support[k]['ap'] != 'UNSUPPORTED_INITIAL_AP_AND_ARRIVAL_TRANSITIONS'
           for k in expected):
        raise ValueError('measured energy/AP support boundary changed')

    groups = defaultdict(list)
    for r in service:
        groups[r['scenario'], r['realized'], r['policy']].append(r)
    group_rows = []
    for (scenario, realized, policy), block in sorted(groups.items()):
        group_rows.append(dict(scenario=scenario, realized=realized, policy=policy,
            seed_count=len(block), planned=sum(r['planned'] for r in block),
            unfinished=sum(r['unfinished'] for r in block),
            timely_all_planned=sum(r['timely_all_planned'] for r in block),
            urgent_not_timely=sum(r['urgent_not_timely'] for r in block),
            normal_not_timely=sum(r['normal_not_timely'] for r in block),
            urgent_p95_mean_ms=sum(r['urgent_p95_ms'] for r in block)/len(block),
            normal_mean_ms=sum(r['normal_mean_ms'] for r in block)/len(block),
            energy_j=None, ap_peak_c=None))
    rep = [r for r in service if (r['scenario'], r['realized'], r['seed']) == REPRESENTATIVE]
    rep_support = {r['policy']: dict(states_used=support[REPRESENTATIVE + (r['policy'],)]['states_used'].split('|'),
        state_durations_s=json.loads(support[REPRESENTATIVE + (r['policy'],)]['state_durations_s']),
        transition_count=int(support[REPRESENTATIVE + (r['policy'],)]['transition_count']),
        first_transition=support[REPRESENTATIVE + (r['policy'],)]['first_transition'],
        first_transition_s=float(support[REPRESENTATIVE + (r['policy'],)]['first_transition_s']),
        energy=support[REPRESENTATIVE + (r['policy'],)]['energy'],
        ap=support[REPRESENTATIVE + (r['policy'],)]['ap']) for r in rep}
    result = dict(version='arrival-service-choice-v1', evidence='saved PC schedules and responses',
        deadlines='research inputs: urgent 1.5 s, normal 6 s; no adopted service SLA',
        input_sha256={'service_metrics':digest(service_path), 'support_status':digest(support_path)},
        case_count=len(service), representative='queue/seed201/realized1.5',
        representative_service=rep, representative_support=rep_support,
        measured_energy_ap_complete_cases=0, policy_energy_ap_rank=None,
        experiment_ready=False)
    output.mkdir(parents=True)
    write_csv(output / 'service_cases.csv', service)
    write_csv(output / 'service_groups.csv', group_rows)
    (output / 'representative.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    result = evaluate(parser.parse_args().output)
    print(json.dumps({'case_count': result['case_count'],
        'representative': result['representative'],
        'measured_energy_ap_complete_cases': result['measured_energy_ap_complete_cases']}))


if __name__ == '__main__':
    main()
