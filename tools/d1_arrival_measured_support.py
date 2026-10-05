"""Audit saved arrival occupancy against the frozen A24 regimen support contract.

This is a support audit, not an energy/AP calculator. No event simulation, fitting,
new coefficients, or device commands are performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import itertools
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/arrival_policy_screen_01/repro_bundle'
OUTPUT = ROOT / 'docs/results/arrival_policy_screen_01/measured_support_01'
FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
HORIZON = 120.0
POLICIES = {'CPU_URGENT', 'B2_PC', 'B3_SOLO_EFT_PC'}
KEYS = ('scenario', 'realized', 'seed', 'policy')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_digest(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def load_support(output: Path, frozen: Path | None) -> dict:
    if frozen is None:
        support = json.loads((output / 'frozen_support.json').read_text(encoding='utf-8'))
        if support['frozen_sha256'] != FROZEN_SHA:
            raise ValueError('wrong support contract hash')
        return support
    if digest(frozen) != FROZEN_SHA:
        raise ValueError('frozen byte SHA changed')
    source = json.loads(frozen.read_text(encoding='utf-8'))
    if source['version'] != 'energy-ap-state-regimen-fit-v1' or source['experiment_ready'] is not False:
        raise ValueError('wrong frozen model version/status')
    support = dict(frozen_sha256=FROZEN_SHA, version=source['version'],
                   states=source['states'],
                   initial_ap_development_range_c=source['initial_ap_development_range_c'],
                   ap_development_observed_range_c=source['ap_development_observed_range_c'],
                   source_role='development_3_regimen_sessions; not an arrival confirmation',
                   power_and_ap_coefficients='intentionally omitted; this audit computes neither J nor AP')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'frozen_support.json').write_text(json.dumps(support, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return support


def measured_state(saved_state: str) -> str:
    return 'resident_idle' if saved_state == 'idle' else saved_state.replace(':', '_')


def keys(row: dict) -> tuple[str, str, str, str]:
    return tuple(row[k] for k in KEYS)


def verify_partition(rows: list[dict]) -> None:
    if not rows or abs(float(rows[0]['start_s'])) > 1e-9 or abs(float(rows[-1]['end_s'])-HORIZON) > 1e-6:
        raise ValueError('not a common 120-second window')
    prior = 0.0
    for row in rows:
        start, end = float(row['start_s']), float(row['end_s'])
        if abs(start-prior) > 1e-6 or end <= start or end > HORIZON+1e-6:
            raise ValueError('gap, overlap, or invalid occupancy segment')
        prior = end


def svg(rows_by_key: dict, path: Path) -> None:
    # Fixed representative chosen from the existing documented queue/seed201/1.5 contrast.
    selected = [('queue', '1.5', '201', policy) for policy in
                ('CPU_URGENT', 'B2_PC', 'B3_SOLO_EFT_PC')]
    x0, scale, stop = 190, 59, 13.0
    colors = {'idle': '#dce5e9', 'solo': '#4886bc', 'pair': '#f0ad4e', 'missing': '#c55252'}
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="305" viewBox="0 0 1000 305">',
           '<rect width="1000" height="305" fill="white"/>',
           '<style>text{font-family:Malgun Gothic,Arial,sans-serif;fill:#203747;font-size:13px}</style>',
           '<text x="20" y="28" font-size="17">저장된 PC 일정: queue · seed 201 · 실현 간섭 1.5</text>',
           '<text x="20" y="49">파랑 단독 · 주황 병행 · 회색 유휴 · 빨간 경계 = 동결 모형의 임의 전환 미검증</text>']
    for index, key in enumerate(selected):
        y = 86 + index*57
        out.append(f'<text x="20" y="{y+17}">{escape(key[3])}</text>')
        for row in rows_by_key[key]:
            start, end = float(row['start_s']), float(row['end_s'])
            if start >= stop:
                break
            end = min(end, stop)
            state = row['state']
            kind = 'idle' if state == 'idle' else 'pair' if '+' in state else 'solo'
            if state == 'classification:CPU+classification:GPU':
                kind = 'missing'
            x, width = x0 + start*scale, max((end-start)*scale, 0.35)
            out.append(f'<rect x="{x:.3f}" y="{y}" width="{width:.3f}" height="23" fill="{colors[kind]}"/>')
            if start > 0:
                out.append(f'<line x1="{x:.3f}" x2="{x:.3f}" y1="{y-3}" y2="{y+26}" stroke="#9d3040" stroke-width="0.65"/>')
    for second in range(14):
        x = x0 + second*scale
        out.append(f'<line x1="{x}" x2="{x}" y1="76" y2="254" stroke="#e9edef" stroke-width="0.5"/>')
        out.append(f'<text x="{x-5}" y="272">{second}</text>')
    out.append('<text x="20" y="296">표시 0–13초 / 원래 공통창 120초. 색은 계측 지원·J·AP 예측값이 아님.</text></svg>')
    path.write_text('\n'.join(out) + '\n', encoding='utf-8')


def generate(bundle: Path, output: Path, frozen: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    support = load_support(output, frozen)
    allowed = set(support['states'])
    expected = json.loads((bundle / 'SOURCE_HASHES.json').read_text(encoding='utf-8'))['bundle_files']
    for filename in ('occupancy_segments.csv', 'service_metrics.csv', 'assumptions.json'):
        if text_digest(bundle / filename) != expected[filename]:
            raise ValueError(f'saved bundle source hash mismatch: {filename}')
    assumptions = json.loads((bundle / 'assumptions.json').read_text(encoding='utf-8'))
    if assumptions['horizon_s'] != HORIZON or set(assumptions['policies']) != POLICIES:
        raise ValueError('saved experiment contract changed')
    source = read_csv(bundle / 'occupancy_segments.csv')
    service_rows = [row for row in read_csv(bundle / 'service_metrics.csv') if row['policy'] in POLICIES]
    service = {keys(row): row for row in service_rows}
    rows_by_key = defaultdict(list)
    for row in source:
        rows_by_key[keys(row)].append(row)
    expected_keys = set(itertools.product(('low', 'queue', 'burst'), ('1.0', '1.5', '2.0'),
                                          tuple(map(str, assumptions['seeds'])), POLICIES))
    if (set(rows_by_key) != expected_keys or set(service) != expected_keys
            or len(service_rows) != len(expected_keys)):
        raise ValueError('incomplete or duplicate saved comparison')
    support_rows, first_rows, blockers = [], [], []
    for key in sorted(rows_by_key):
        rows = rows_by_key[key]
        verify_partition(rows)
        metric = service[key]
        if metric['planned'] != '24':
            raise ValueError('planned denominator changed')
        base = dict(zip(KEYS, key))
        missing = sorted({r['state'] for r in rows if measured_state(r['state']) not in allowed})
        transition = rows[1]
        first_time = float(transition['start_s'])
        durations = defaultdict(float)
        for row in rows:
            durations[row['state']] += float(row['end_s']) - float(row['start_s'])
        support_rows.append(dict(**base, horizon_s='120', planned='24',
                                 predicted_interference='not_used_by_CPU_B2_B3',
                                 unfinished=metric['unfinished'], segment_count=len(rows),
                                 transition_count=len(rows)-1, states_used='|'.join(sorted(durations)),
                                 state_durations_s=json.dumps(dict(sorted(durations.items())), sort_keys=True),
                                 coefficient_missing_states='|'.join(missing),
                                 coefficient_missing_s=round(sum(durations[s] for s in missing), 9),
                                 first_transition_s=transition['start_s'],
                                 first_transition=f"{rows[0]['state']} -> {transition['state']}",
                                 initial_ap_source='unmeasured_PC_assumption_29C_outside_frozen_start_range',
                                 resident_support='PC_idle_name_only_no_measured_resident_event',
                                 thermal_history='PC_state_sequence_only_no_observed_prior_heat',
                                 schedule_response='PC_SAVED_MODEL_ONLY',
                                 energy='UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS',
                                 ap='UNSUPPORTED_INITIAL_AP_AND_ARRIVAL_TRANSITIONS',
                                 thermal_runtime='UNVERIFIED_NOT_REQUIRED_FOR_FIXED_DURATION_EXPLORATION',
                                 independent_prediction='NO', policy_choice='NOT_DISTINGUISHABLE'))
        blockers.append(dict(**base, start_s='0', end_s='120', previous_state='', current_state='',
                             output='energy|AP', rule='REGIMEN_ONLY_PROFILE',
                             evidence='MODEL_GUARD', resolution='R3_ARRIVAL_CONFIRMATION'))
        blockers.append(dict(**base, start_s='0', end_s='0', previous_state='', current_state='idle',
                             output='AP', rule='INITIAL_AP_NOT_OBSERVED',
                             evidence='INITIAL_29_ASSUMPTION', resolution='R3_OBSERVED_START_AP'))
        for old, current in zip(rows, rows[1:]):
            blockers.append(dict(**base, start_s=current['start_s'], end_s=current['end_s'],
                                 previous_state=old['state'], current_state=current['state'],
                                 output='energy|AP', rule='UNVALIDATED_ARRIVAL_TRANSITION',
                                 evidence='REGIMEN_ONLY', resolution='R3_ARRIVAL_CONFIRMATION'))
        for index, row in enumerate(rows):
            if row['state'] in missing:
                blockers.append(dict(**base, start_s=row['start_s'], end_s=row['end_s'],
                                     previous_state=rows[index-1]['state'] if index else '',
                                     current_state=row['state'],
                                     output='energy|AP', rule='STATE_COEFFICIENT_ABSENT',
                                     evidence='FROZEN_STATE_LIST', resolution='R4_EXCLUDE_OR_R3_IDENTIFY'))
        first_rows.extend([
            dict(**base, output='energy', first_blocker_s='0', rule='REGIMEN_ONLY_PROFILE',
                 first_concrete_transition_s=f'{first_time:.9f}',
                 previous_state=rows[0]['state'], current_state=transition['state']),
            dict(**base, output='AP', first_blocker_s='0', rule='INITIAL_AP_NOT_OBSERVED',
                 first_concrete_transition_s=f'{first_time:.9f}',
                 previous_state=rows[0]['state'], current_state=transition['state'])])
    write_csv(output / 'support_status.csv', support_rows, tuple(support_rows[0]))
    write_csv(output / 'first_blockers.csv', first_rows, tuple(first_rows[0]))
    write_csv(output / 'all_blockers.csv', blockers, tuple(blockers[0]))
    svg(rows_by_key, output / 'representative_schedule.svg')
    report = dict(version='arrival-frozen-support-audit-v1', case_count=len(rows_by_key),
                  complete_measured_energy_ap_cases=0, independent_prediction_cases=0,
                  missing_state_cases=sum(bool(r['coefficient_missing_states']) for r in support_rows),
                  blocker_rows=len(blockers), frozen_sha256=support['frozen_sha256'],
                  frozen_bytes_checked=frozen is not None,
                  input_sha256={name:text_digest(bundle / name) for name in
                                ('occupancy_segments.csv','service_metrics.csv','assumptions.json')},
                  initial_ap_assumption_c=assumptions['initial_ap_c'],
                  model_code_rule='UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS',
                  numerical_energy_j=None, numerical_ap_c=None,
                  representative='queue/seed201/realized1.5; selected before this audit from existing comparison')
    (output / 'audit_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=BUNDLE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--frozen', type=Path, help='exact external development_freeze.json; checks bytes')
    args = parser.parse_args()
    print(json.dumps(generate(args.bundle, args.output, args.frozen), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
