"""PC-only evidence closure; no fit, simulator batch, or device execution.

Extract normalized AP query brackets and actual lane-free windows from archived
sessions, then reproduce the readout without personal paths or device identities.
The existing fixed-episode decision interface is reused, not promoted to arrivals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'docs/results/ap_simulation_closure_01'
FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s]


def idle_windows(intervals, end_s, minimum_s=10.):
    """Merge only intersecting occupancy; 10 s filters reporting, not model support."""
    merged = []
    for a, b in sorted(intervals):
        if not all(math.isfinite(v) for v in (a, b)) or b <= a or a < 0 or b > end_s:
            raise ValueError('invalid lane interval')
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [dict(release_s=b, idle_end_s=merged[i+1][0] if i+1 < len(merged) else end_s)
            for i, (_, b) in enumerate(merged)
            if (merged[i+1][0] if i+1 < len(merged) else end_s)-b >= minimum_s]


def validate_samples(samples):
    if len(samples) < 2:
        raise ValueError('AP samples missing')
    for i, p in enumerate(samples):
        if (not all(math.isfinite(p[k]) for k in ('t', 'ap', 'lo', 'hi')) or
                not p['lo'] <= p['t'] <= p['hi'] or
                (i and p['t'] <= samples[i-1]['t'])):
            raise ValueError('invalid AP bracket/order')


def cadence(samples):
    validate_samples(samples)
    gaps = [b['t']-a['t'] for a, b in zip(samples, samples[1:])]
    changes = [b['t'] for a, b in zip(samples, samples[1:]) if b['ap'] != a['ap']]
    change_gaps = [b-a for a, b in zip(changes, changes[1:])]
    return dict(samples=len(samples), query_gap_median_s=statistics.median(gaps),
                query_gap_max_s=max(gaps), query_half_bracket_max_s=max((p['hi']-p['lo'])/2 for p in samples),
                repeated_adjacent=sum(a['ap'] == b['ap'] for a, b in zip(samples, samples[1:])),
                observed_change_gap_median_s=statistics.median(change_gaps) if change_gaps else None,
                hardware_update_period_s=None)


def window_readout(samples, window):
    validate_samples(samples)
    start, end = window['release_s'], window['idle_end_s']
    # Use only query brackets entirely within lane-free time. Boundary samples
    # cannot establish whether a rise happened before or after release.
    chosen = [p for p in samples if p['lo'] >= start and p['hi'] < end]
    base = dict(**window, samples=len(chosen))
    if len(chosen) < 3:
        return dict(**base, status='INSUFFICIENT_AP', interior_rise_then_fall=None)
    gap = max(b['t']-a['t'] for a, b in zip(chosen, chosen[1:]))
    if gap > 10 or chosen[0]['t']-start > 10 or end-chosen[-1]['t'] > 10:
        return dict(**base, status='AP_GAP', interior_rise_then_fall=None)
    peak = max(p['ap'] for p in chosen)
    index = next(i for i, p in enumerate(chosen) if p['ap'] == peak)
    first_peak = chosen[index]
    rise = peak-chosen[0]['ap']
    fall = peak-chosen[-1]['ap']
    return dict(**base, status='DESCRIPTIVE', first_s=chosen[0]['t'], first_ap_c=chosen[0]['ap'],
                last_s=chosen[-1]['t'], last_ap_c=chosen[-1]['ap'], peak_c=peak,
                peak_first_s=first_peak['t'], peak_last_s=max(p['t'] for p in chosen if p['ap'] == peak),
                peak_sample_after_release_s=first_peak['t']-start,
                peak_query_lo_after_release_s=first_peak['lo']-start,
                peak_query_hi_after_release_s=first_peak['hi']-start,
                changed_value_appearance_lo_s=chosen[index-1]['lo'] if index else None,
                changed_value_appearance_hi_s=first_peak['hi'] if index else None,
                rise_after_first_idle_sample_c=rise, fall_to_last_idle_sample_c=fall,
                interior_rise_then_fall=rise > 0 and fall > 0,
                physical_delay_s=None)


def extract(external, output):
    """Save small relative-time inputs, with raw source hashes, never raw identities."""
    from tools import d1_arrival_recorded_replay_analysis as replay
    from tools import d1_arrival_recorded_b2_residual as residual
    from tools import d1_energy_thermal as thermal
    external, output = Path(external), Path(output)
    if output.exists():
        raise FileExistsError(output)
    frozen_file = external/'energy_ap_state_run_v5/development_freeze.json'
    if sha(frozen_file) != FROZEN_SHA:
        raise ValueError('frozen model bytes changed')
    frozen = read(frozen_file)
    sessions = []
    sources = [('energy_ap_idle_response_run_v1', 'idle'),
               ('energy_ap_recorded_b2_diag_run_v6', 'b2'),
               ('energy_ap_state_run_v5', 'regimen'),
               ('energy_ap_device_segment_diag_run_v4', 'transfer')]
    for run, tag in sources:
        for vf in sorted((external/run).glob('0*/validated.json')):
            folder = vf.parent
            valid = read(vf)
            artifacts = folder/'artifacts'
            origin = valid['common_start_ns']
            events = rows(artifacts/'progress.jsonl')
            cooling = [e['mono_ns'] for e in events if e.get('kind') == 'phase_end' and e.get('phase') == 'resident_cooling']
            end = max([valid['common_end_ns'], *cooling])
            ap = [dict(t=(p['mono_ns']-origin)/1e9, ap=float(p['AP']),
                       lo=(p['before_ns']-origin)/1e9, hi=(p['after_ns']-origin)/1e9)
                  for p in rows(folder/'thermal.jsonl')
                  if origin <= p['mono_ns'] <= end and p.get('AP') not in ('', None)]
            provenance = {'validated':sha(vf), 'thermal':sha(folder/'thermal.jsonl'),
                          'progress':sha(artifacts/'progress.jsonl')}
            if (artifacts/'requests.json').exists():
                requests = read(artifacts/'requests.json')
                if len(requests) != 24 or any(p['terminal_status'] != 'succeeded' for p in requests):
                    raise ValueError('request denominator')
                provenance['requests'] = sha(artifacts/'requests.json')
            else:
                requests = [p for p in events if p.get('kind') == 'lane_available' and
                            p.get('dispatch_ns', 0) >= origin and p['lane_available_ns'] <= end]
            busy = [((p['dispatch_ns']-origin)/1e9, (p['lane_available_ns']-origin)/1e9) for p in requests]
            data_role = ('protocol_transfer_posthoc' if tag == 'transfer' else
                         'observed_schedule_extrapolation' if tag == 'b2' else
                         'prespecified_procedure_'+valid['phase'] if tag == 'idle' else
                         'original_frozen_'+valid['phase'])
            item = dict(id=tag+'_'+folder.name[:2], role=valid['phase'], data_role=data_role,
                        condition=valid.get('condition', 'CG_DC'), source_run=run,
                        source_session_index=folder.name[:2], source_sha256=provenance,
                        end_s=(end-origin)/1e9, samples=ap,
                        idle_windows=idle_windows(busy, (end-origin)/1e9))
            if tag in ('idle', 'b2'):
                segments = replay.observed_segments(requests, origin)
                powers = [dict(p, mono_ns=(p['snapshot_start_ns']+p['sensor_read_end_ns'])//2)
                          for p in events if p['kind'] == 'power_sample']
                bins, _, last = residual.sensor_intervals(powers, origin, origin+120_000_000_000, segments, frozen)
                if any(p['observed_j'] is None for p in bins):
                    raise ValueError('missing common-window power')
                # Exact integration splits at last release; sensor bins remain
                # separate and mixed bins are never fitted as state coefficients.
                phases = []
                for label, a, b in [('through_last_release', 0., last), ('resident_idle_tail', last, 120.)]:
                    measured = thermal.integrate(powers, origin+round(a*1e9), origin+round(b*1e9), 1000)['full_energy_j']
                    estimate = sum(frozen['whole_device_power_w'][replay.state_key(state)]*duration
                                   for state, duration in residual.overlap(segments, a, b).items())
                    if measured is None:
                        raise ValueError('incomplete phase energy')
                    phases.append(dict(phase=label, start_s=a, end_s=b, observed_j=measured,
                                       predicted_j=estimate, signed_error_j=estimate-measured))
                item['energy'] = dict(window_s=120., phases=phases,
                    observed_j=sum(p['observed_j'] for p in bins), predicted_j=sum(p['predicted_j'] for p in bins),
                    positive_bin_error_j=sum(max(0, p['signed_error_j']) for p in bins),
                    negative_bin_error_j=sum(min(0, p['signed_error_j']) for p in bins),
                    mixed_bins=sum(p['resolution'] == 'mixed' for p in bins),
                    pair_occupancy_s=sum(s['end_s']-s['start_s'] for s in segments if '+' in s['state']))
                if tag == 'idle':
                    score = read(folder/'ap_analysis/summary.json')
                    item['candidate_scores'] = {k:score[k] for k in ('ap_path_mae_c','ap_path_max_absolute_error_c',
                        'preload_effective_reference_c','initial_ap_c')}
                    provenance['candidate_analysis'] = sha(folder/'ap_analysis/summary.json')
            sessions.append(item)
    if len(sessions) != 8:
        raise ValueError('expected idle2 + B2 + development3 + DC_DG + CG_DC transfer')
    # Extraction is deterministic and fail-closed; no copying of executable plans.
    candidate_freeze = external/'energy_ap_idle_response_run_v1/ap_model_freeze.json'
    if sha(candidate_freeze) != '8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5':
        raise ValueError('candidate freeze changed')
    if sha(frozen_file) != FROZEN_SHA:
        raise ValueError('original freeze changed during extraction')
    write(output, dict(version='ap-simulation-closure-input-v1', frozen_sha256=FROZEN_SHA,
                       candidate_freeze_sha256=sha(candidate_freeze),
                       original_beta=frozen['ap_cooling_rate_per_s'], sessions=sessions))


def csv_write(path, records):
    fields = list(dict.fromkeys(k for p in records for k in p))
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader(); writer.writerows(records)


def evaluate(input_file, output):
    from tools import d1_energy_operational_decision as decision
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    bundle = read(input_file)
    if bundle['frozen_sha256'] != FROZEN_SHA:
        raise ValueError('wrong freeze')
    probes, gaps, energy = [], [], []
    for session in bundle['sessions']:
        gaps.append(dict(session=session['id'], data_role=session['data_role'], **cadence(session['samples'])))
        for i, window in enumerate(session['idle_windows']):
            probes.append(dict(session=session['id'], data_role=session['data_role'], window=i,
                               **window_readout(session['samples'], window)))
        if 'energy' in session:
            e = session['energy']
            difference = e['predicted_j']-e['observed_j']
            if not math.isclose(difference, sum(p['signed_error_j'] for p in e['phases']), abs_tol=1e-7):
                raise ValueError('phase energy conservation')
            if not math.isclose(difference, e['positive_bin_error_j']+e['negative_bin_error_j'], abs_tol=1e-7):
                raise ValueError('sensor bin conservation')
            energy.append(dict(session=session['id'], **{k:v for k,v in e.items() if k != 'phases'},
                signed_error_j=difference, relative_error_pct=100*difference/e['observed_j'],
                through_release_error_j=e['phases'][0]['signed_error_j'],
                tail_error_j=e['phases'][1]['signed_error_j'],
                interpretation='extrapolation_diagnostic_not_policy_ranking'))
    # One exact archived query, with no invented limits or replayed batch.
    fixed = ROOT/'docs/results/energy_operational_sim_01'
    profile, evaluation = fixed/'frozen_profile.json', fixed/'confirmation_evaluation.json'
    query = decision.query_from_recorded_profile(read(profile), 29.1)
    query['profile_sha256'] = sha(profile)
    fixed_result = decision.decide(profile, evaluation, query)
    if fixed_result['status'] != 'TRADEOFF' or fixed_result['model_candidate'] is not None:
        raise ValueError('archived decision unexpectedly changed')
    support_file = ROOT/'docs/results/arrival_policy_screen_01/measured_support_01/support_status.csv'
    with support_file.open(encoding='utf-8-sig', newline='') as stream:
        saved = list(csv.DictReader(stream))
    if len(saved) != 135 or any(r['energy'] != 'UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS' for r in saved):
        raise ValueError('saved support boundary changed; review required')
    representative = [dict(policy=r['policy'], scenario=r['scenario'], seed=r['seed'],
        schedule_response=r['schedule_response'], energy=r['energy'], ap=r['ap'],
        full_window_j=None, full_window_ap_peak_c=None, policy_rank=None,
        new_evidence='B2 actual schedule only; low-temperature AP candidate conditional, not general transition support')
        for r in saved if r['scenario']=='queue' and r['seed']=='201' and r['realized']=='1.5']
    report = dict(version='ap-simulation-closure-v1', input_sha256=sha(input_file),
        source_sha256={'fixed_profile':sha(profile),'fixed_evaluation':sha(evaluation),'saved_support':sha(support_file)},
        candidate_decision='conditional_diagnostic_only_not_default', new_fitted_parameters=0,
        physical_sensor_delay_identified=False, hidden_thermal_state_identified=False,
        evidence_sessions=len(bundle['sessions']), idle_windows=len(probes),
        observed_nonmonotonic_idle_windows=sum(p.get('interior_rise_then_fall') is True for p in probes),
        archived_fixed_episode_case_count=1, complete_dynamic_energy_ap_policy_cases=0,
        fixed_episode=fixed_result, dynamic_representatives=representative,
        experiment_ready=False, accuracy_pass=None, policy_selection_pass=None)
    output.mkdir(parents=True)
    write(output/'summary.json', report)
    csv_write(output/'ap_idle_windows.csv', probes)
    csv_write(output/'sensor_cadence.csv', gaps)
    csv_write(output/'energy_accounting.csv', energy)
    csv_write(output/'policy_support.csv', representative)
    plot(bundle, output)
    page(report, energy, output)
    return report


def page(report, energy, output):
    """Render values from the same report, with no new prediction or assumption."""
    from html import escape
    table = ''.join(f'<tr><td>{escape(r["session"])}</td><td>{r["observed_j"]:.3f}</td>'
                    f'<td>{r["predicted_j"]:.3f}</td><td>{r["signed_error_j"]:+.3f}</td>'
                    f'<td>{r["relative_error_pct"]:+.3f}%</td></tr>' for r in energy)
    fixed = report['fixed_episode']['nominal_and_sensitivity']
    contrasts = []
    for metric in ('work_completion_s','common_window_energy_j_conditional','load_ap_peak_c'):
        predicted = fixed['parallel']['nominal'][metric]-fixed['serial']['nominal'][metric]
        actual = (fixed['parallel']['one_confirmation_error_scenario'][metric]-
                  fixed['serial']['one_confirmation_error_scenario'][metric])
        contrasts.append(f'<tr><td>{escape(metric)}</td><td>{predicted:+.3f}</td><td>{actual:+.3f}</td></tr>')
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>D1Check AP·에너지 판정</title><style>body{font-family:system-ui,sans-serif;margin:36px auto;max-width:1050px;padding:0 18px;line-height:1.7;color:#203040}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ccd7df;text-align:left}.note{background:#fff2da;padding:16px}img{width:100%}a{color:#1265a3}</style>
<h1>AP 판정·에너지 연결·제한 비교</h1><p class="note">새 실측 없음 · 후보 재보정 없음 · experiment_ready=false<br>고정 CC_DG 회고 비교는 사용 가능. 동적 정책 전체창 실측 J/AP 지원은 0개이며 정확도 PASS·정책 우열은 미판정.</p>
<p><a href="../../../AP_SIMULATION_CLOSURE_PC_20260930.md">판정 보고서</a> · <a href="../README.md">재현·입력·CSV</a></p>
<h2>AP: 관측 형태 한계와 센서 지연의 미확정</h2><p>기존8세션 유휴19구간 중 한 확인 세션의2구간에서 상승 후 하강. 단일 AP 상태의 고정 유휴 평형식으로는 이 관측 형태를 표현할 수 없습니다. 센서 내부 갱신시각과 실제 열 지연은 분리 식별되지 않았습니다. 후보 확인 MAE0.418°C는 기본 채택 또는 정책 비교 합격이 아닙니다.</p>
<img src="idle_observation.svg" alt="실제 lane 해제 전후의 기존 HAL AP 표본과 조회 bracket">
<h2>에너지: 같은120초, 실제 일정 조건부 외삽 진단</h2><p>원래 동결 W 재사용. 이후 관측 전류/AP는 예측 입력이 아닙니다. AP 후보는 W를 변경하지 않습니다. 기기 전체 raw=mA 조건부 J이며 절대 정확도 미인증.</p>
<table><tr><th>기록</th><th>관측 J</th><th>동결식 J</th><th>차이 J</th><th>상대차이</th></tr>'''+table+'''</table>
<p>B2의 작은 전체차이를 보편 오차 한도로 사용하지 않습니다. 구간 상쇄·혼합표본은 <a href="energy_accounting.csv">CSV</a>에 보존했습니다. 세 기록의 총량 차이는 정책 절감량이 아닙니다.</p>
<h2>지금 가능한 비교: 고정870건 CC_DG 직렬/병행</h2><p>공통480초·개발 템플릿·저장 확인자료의 회고 비교. 다른 작업량/도착/시작AP는 미지원. 결과는 TRADEOFF, 정책 선택값=null. 확인 결과를 이미 본 뒤 작성한 템플릿의 사후 holdout입니다.</p>
<table><tr><th>병행−직렬</th><th>템플릿 예측</th><th>저장 확인 관측</th></tr>'''+''.join(contrasts)+'''</table>
<h2>동적 목표의 남은 항목</h2><p>기존 CPU_URGENT/B2/B3의 저장 일정·응답은 활용할 수 있습니다. 전체창 실측 기반 J/AP 순위는 아직 계산 불가입니다. B2/B3가 쓰는 짧은 CG_DC/DC_DG→유휴 전이에서 비용·AP 반응·일정 오차와 정책 간 차이를 구분할 근거가 필요합니다. 센서 지연과 숨은 열을 근거 없이 계수로 채우거나 새 실행을 자동 시작하지 않습니다.</p>
<p><a href="policy_support.csv">대표3개 지원 결과</a> · <a href="summary.json">기계 판독 결과·출처 해시</a></p></html>'''
    (output/'index.html').write_text(html+'\n', encoding='utf-8')


def plot(bundle, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['svg.hashsalt'] = 'd1-ap-closure-v1'
    chosen = [s for s in bundle['sessions'] if s['id'] in ('idle_00','idle_01','b2_00')]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, session in zip(axes, chosen):
        window = session['idle_windows'][-1]
        release = window['release_s']
        values = [p for p in session['samples'] if release-8 <= p['t'] <= release+40]
        ax.errorbar([p['t']-release for p in values], [p['ap'] for p in values],
                    xerr=[(p['hi']-p['lo'])/2 for p in values], fmt='o-', ms=3, capsize=2)
        ax.axvline(0, color='#a83232', ls='--', label='Last lane release')
        ax.set(title=session['id'], xlabel='Seconds from last lane release', ylabel='Observed HAL AP (C)')
        ax.legend(fontsize=8)
    fig.suptitle('Archived observations; brackets are query timing, not hardware update timestamps', fontsize=10)
    fig.tight_layout()
    fig.savefig(output/'idle_observation.svg', metadata={'Date':None})
    fig.savefig(output/'idle_observation.png', dpi=130)
    plt.close(fig)
    path = output/'idle_observation.svg'
    path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest='action', required=True)
    ex = sub.add_parser('extract'); ex.add_argument('--external', required=True); ex.add_argument('--output', required=True)
    ev = sub.add_parser('evaluate'); ev.add_argument('--input', default=str(DEFAULT/'inputs.json')); ev.add_argument('--output', required=True)
    args = cli.parse_args()
    if args.action == 'extract':
        extract(args.external, args.output)
    else:
        result = evaluate(args.input, args.output)
        print(json.dumps({k:result[k] for k in ('candidate_decision','idle_windows',
            'observed_nonmonotonic_idle_windows','complete_dynamic_energy_ap_policy_cases')}, indent=2))


if __name__ == '__main__':
    main()
