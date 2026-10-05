"""Fixed six-session retrospective policy resolution; no fitting/device calls."""
import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

from tools import d1_separated_power_readout as replay

CPU = 'CPU_URGENT_ONLINE_V1'
PAR = 'B2_PARALLEL_ONLINE_V1'
SER = 'B2_SERIAL_ONLINE_V1'
POLICIES = (CPU, PAR, SER)
IDS = [f'confirmation_{i}_{p}' for i, p in enumerate((CPU, PAR, SER, SER, PAR, CPU))]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def csv_write(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def historical_sensitivity(delta, policy_errors, reference_errors):
    """Observed residuals transplanted arithmetically, never a future bound/CI."""
    values = [delta, *policy_errors, *reference_errors]
    if not policy_errors or not reference_errors or any(v is None or not math.isfinite(v) for v in values):
        raise ValueError('finite complete residuals required; no zero fill')
    contrasts = [a-b for a, b in itertools.product(policy_errors, reference_errors)]
    adjusted = [delta-e for e in contrasts]
    return dict(historical_low=min(adjusted), historical_high=max(adjusted),
                combinations=len(adjusted), sign_retained=all(x*delta > 0 for x in adjusted),
                future_bound=None, policy_winner=None)


def trace_signature(requests):
    return [{k: q[k] for k in ('ordinal', 'task_id', 'priority', 'offset_ms', 'deadline_ms')} for q in requests]


def load(bundle):
    bundle = Path(bundle)
    resource = read(bundle / 'resources.json')
    if not {'evaluation.json', 'initial_inputs.json', 'model.json', 'policy_differences.json', 'summary.csv'} <= resource['files'].keys():
        raise ValueError('required evidence bindings')
    for name, expected in resource['files'].items():
        p = (bundle / name).resolve()
        if p.parent != bundle.resolve() or digest(p) != expected:
            raise ValueError('source hash mismatch')
    frozen = read(bundle / 'model.json')
    if (frozen['version'] != 'separated-power-model-v1' or frozen['preload_power_window_s'] != [-20, 30]
            or frozen['energy_baseline_mode'] != 'session_preload'):
        raise ValueError('registered model required')
    inputs = {c['id']: c for c in read(bundle / 'initial_inputs.json') if c['phase'] == 'confirmation'}
    cases = {c['id']: c for c in read(bundle / 'evaluation.json') if c['phase'] == 'confirmation'}
    if set(inputs) != set(IDS) or set(cases) != set(IDS):
        raise ValueError('all six confirmation sessions required; no outlier removal')
    signature = trace_signature(inputs[IDS[0]]['manifest_requests'])
    for c in inputs.values():
        replay.protocol.validate('confirmation', c['manifest_requests'])
        if trace_signature(c['manifest_requests']) != signature:
            raise ValueError('different arrival/deadline/task trace')
    return resource, frozen, inputs, cases


def counterfactual(initial_case, frozen):
    # Whitelist pre-load inputs. This function has no evaluation/actual-row argument.
    initial = {k: initial_case['initial'][k] for k in ('preload', 'preload_power_w')}
    outputs = {}
    for policy in POLICIES:
        result, segments = replay.shared.model.forecast(initial, initial_case['manifest_requests'], policy,
                                                       frozen, planning_input_role='confirmation')
        costs = replay.shared.model.costs(segments, initial, list(range(35, 181)), frozen, 180)
        responses = []
        met = 0
        for r in result['ledger']:
            field = 'output_ready_ns' if r['priority'] == 'urgent' else 'persist_complete_ns'
            response = r[field]-r['arrival_ns']
            met += response <= r['deadline_offset_ns']
            if r['priority'] == 'urgent':
                responses.append(response/1e6)
        outputs[policy] = dict(predicted_120s_j=costs['whole_120s_j'],
                               predicted_35_180s_peak_c=max(costs['ap_path']),
                               urgent_p95_ms=sorted(responses)[math.ceil(.95*len(responses))-1],
                               deadline_met=met, planned=len(result['ledger']))
    return outputs


def analyze(bundle, output, contract):
    resource, frozen, inputs, cases = load(bundle)
    contract = Path(contract)
    rules = read(contract)
    if rules['session_ids'] != IDS or rules['counterfactual_ap_grid_s'] != [35, 180, 1] or rules['energy_window_s'] != [0, 120]:
        raise ValueError('fixed analysis contract')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sessions = []
    for id in IDS:
        c = cases[id]
        f = c['outputs']['arrival_forecast']
        sessions.append(dict(id=id, policy=c['policy'], initial_ap_c=c['common_start_ap_c'],
            observed_120s_j=c['observed_120s_j'], predicted_120s_j=f['whole_120s_j'],
            energy_error_j=f['energy_signed_error_j'], ap_mae_c=f['ap_scores']['mae_c'],
            ap_max_error_c=f['ap_scores']['max_absolute_error_c'], peak_error_c=f['ap_scores']['peak_signed_error_c'],
            observed_peak_c=max(c['observed_ap_c']), ap_first_s=min(c['ap_query_s']), ap_last_s=max(c['ap_query_s']),
            urgent_p95_ms=c['service']['actual_urgent']['p95_ms'],
            deadline_met=c['service']['actual_all']['deadline_met'], planned=c['service']['actual_all']['planned']))
    errors = {p: [r['energy_error_j'] for r in sessions if r['policy'] == p] for p in POLICIES}
    pairs = []
    for block, ref, others in ((0, IDS[0], IDS[1:3]), (1, IDS[5], [IDS[4], IDS[3]])):
        a = next(r for r in sessions if r['id'] == ref)
        for id in others:
            b = next(r for r in sessions if r['id'] == id)
            pred = b['predicted_120s_j']-a['predicted_120s_j']
            obs = b['observed_120s_j']-a['observed_120s_j']
            error = b['energy_error_j']-a['energy_error_j']
            if not math.isclose(pred-obs, error, abs_tol=1e-9):
                raise ValueError('contrast error conservation')
            pairs.append(dict(block=block, policy=b['policy'], reference_id=ref, policy_id=id,
                initial_ap_delta_c=b['initial_ap_c']-a['initial_ap_c'], observed_energy_delta_j=obs,
                predicted_energy_delta_j=pred, contrast_error_j=error,
                observed_peak_delta_c=b['observed_peak_c']-a['observed_peak_c'],
                peak_error_delta_c=b['peak_error_c']-a['peak_error_c'],
                urgent_p95_delta_ms=b['urgent_p95_ms']-a['urgent_p95_ms'],
                causal_policy_effect=False))
    # Check stored comparison arithmetic; don't silently redefine the previous result.
    old = read(Path(bundle)/'policy_differences.json')
    if len(old) != len(pairs):
        raise ValueError('stored comparison count')
    for row in pairs:
        previous = next(r for r in old if r['repeat'] == row['block'] and r['policy'] == row['policy'])
        for current, prior in [('observed_energy_delta_j','observed_j_difference'),
                               ('predicted_energy_delta_j','predicted_j_difference'),
                               ('urgent_p95_delta_ms','observed_urgent_p95_ms_difference'),
                               ('observed_peak_delta_c','observed_peak_ap_difference')]:
            if not math.isclose(row[current], previous[prior], abs_tol=1e-9):
                raise ValueError('stored comparison mismatch')
    comparisons = []
    predictions = []
    for id in IDS:
        pred = counterfactual(inputs[id], frozen)
        own = cases[id]['outputs']['arrival_forecast']
        if not math.isclose(pred[cases[id]['policy']]['predicted_120s_j'], own['whole_120s_j'], abs_tol=1e-9):
            raise ValueError('original forecast reproduction')
        predictions.extend(dict(initial_id=id, policy=p, **pred[p]) for p in POLICIES)
        for policy in (PAR, SER):
            delta = pred[policy]['predicted_120s_j']-pred[CPU]['predicted_120s_j']
            sensitivity = historical_sensitivity(delta, errors[policy], errors[CPU])
            comparisons.append(dict(initial_id=id, policy=policy, reference=CPU,
                predicted_energy_delta_j=delta,
                predicted_peak_delta_c=pred[policy]['predicted_35_180s_peak_c']-pred[CPU]['predicted_35_180s_peak_c'],
                urgent_p95_delta_ms=pred[policy]['urgent_p95_ms']-pred[CPU]['urgent_p95_ms'],
                predicted_deadline_met=pred[policy]['deadline_met'], planned=pred[policy]['planned'],
                **sensitivity))
    ranges = []
    for policy in POLICIES:
        rows = [r for r in sessions if r['policy'] == policy]
        ranges.append(dict(policy=policy, sessions=2,
            observed_j_range=max(r['observed_120s_j'] for r in rows)-min(r['observed_120s_j'] for r in rows),
            observed_peak_range_c=max(r['observed_peak_c'] for r in rows)-min(r['observed_peak_c'] for r in rows),
            energy_error_min_j=min(errors[policy]), energy_error_max_j=max(errors[policy]),
            future_bound=None, controlled_repeat_variability=False))
    for name, rows in [('sessions',sessions), ('observed_contrasts',pairs),
                       ('same_initial_comparisons',comparisons), ('descriptive_ranges',ranges),
                       ('counterfactual_predictions',predictions)]:
        csv_write(output/(name+'.csv'), rows)
    result = dict(source_resource_sha256=digest(Path(bundle)/'resources.json'), source_files=resource['files'],
        source_freeze_sha256=resource['source_freeze_sha256'], contract_sha256=digest(contract),
        sessions=sessions, observed_contrasts=pairs, same_initial_comparisons=comparisons,
        counterfactual_predictions=predictions, descriptive_ranges=ranges, decision_support=replay.decision_support(),
        same_initial_forecasts=18, new_fits=0, new_independent_sessions=0,
        device_commands=0, accuracy_pass=None, experiment_ready=False)
    write(output/'evaluation.json', result)
    render(output, result)
    # Recheck source immutability after calculations.
    load(bundle)
    return result


def render(output, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    short = {CPU:'CPU', PAR:'PAR', SER:'SER'}
    rows = result['sessions']
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    labels = [f'{i}: {short[r["policy"]]}' for i,r in enumerate(rows)]
    for ax,key,title,unit in [(axes[0],'energy_error_j','Forecast - observed: 0-120 s','J'),
                              (axes[1],'ap_mae_c','AP error at recorded query times','MAE (C)'),
                              (axes[2],'urgent_p95_ms','Observed urgent response','P95 (ms)')]:
        ax.bar(labels,[r[key] for r in rows]); ax.axhline(0,color='black',linewidth=.7)
        ax.set(title=title,ylabel=unit); ax.tick_params(axis='x',rotation=45)
    fig.suptitle('Six retained confirmation sessions; post-hoc readout, no policy energy/AP winner')
    fig.tight_layout(); fig.savefig(output/'comparison.png',dpi=150); plt.close(fig)
    table = ''.join(f'<tr><td>{i} {short[r["policy"]]}</td><td>{r["energy_error_j"]:+.3f}</td><td>{r["ap_mae_c"]:.3f}</td><td>{r["urgent_p95_ms"]:.1f}</td><td>{r["deadline_met"]}/{r["planned"]}</td></tr>' for i,r in enumerate(rows))
    Path(output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>정책 차이와 확인 오차</title>
<style>body{max-width:1100px;margin:2rem auto;font:17px/1.6 system-ui;padding:1rem}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.5rem}img{width:100%}.notice{background:#fff2cc;padding:1rem}</style>
<h1>정책 차이와 확인 오차</h1><p class="notice">새 실측 0 · 동결 계수 유지 · 기존 독립 확인 6개를 사후 재분석. 에너지/AP 정책 우열 보류, experiment_ready=false.</p>
<p>서비스: 이 96요청에서는 CPU/PAR 모두 기한 96/96, SER 61/96. PAR 긴급 P95는 CPU보다 두 실행에서 약 0.46초 짧았습니다. 인과 효과·다른 부하로 일반화하지 않습니다.</p>
<table><tr><th>실행</th><th>J 오차</th><th>AP MAE °C</th><th>긴급 P95 ms</th><th>전체 기한</th></tr>'''+table+'''</table>
<img src="comparison.png" alt="보존된 여섯 확인의 에너지 오차, AP MAE, 실제 긴급 응답 P95">
<p>에너지는 0~120초. AP는 각 세션의 실제 조회 시각(~35초 이후~180초 전)이며 서로 다른 최고온도 창은 CSV에 명시했습니다. 센서 점은 독립 세션이 아닙니다.</p>
<p>동일 초기 입력의 18개 PC 예측은 새로운 실측이 아닙니다. 과거 에너지 잔차 2×2 조합 대입은 산술 민감도이며 미래 오차 한도·확률·신뢰구간이 아닙니다. 실제 세션 차이는 초기조건/배경활동 차이를 포함합니다.</p>
<p><a href="../README.md">결론·정확한 수치·재현</a> · <a href="evaluation.json">결과 JSON</a> · <a href="same_initial_comparisons.csv">동일 초기 입력 비교</a> · <a href="observed_contrasts.csv">관측 차이와 오차</a></p></html>''',encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle','output','contract'): p.add_argument('--'+name,required=True)
    a = p.parse_args()
    r = analyze(a.bundle,a.output,a.contract)
    print(json.dumps(dict(sessions=len(r['sessions']),forecasts=r['same_initial_forecasts'],device_commands=0)))


if __name__ == '__main__':
    main()
