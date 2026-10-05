"""Saved equal-work method tradeoffs and inverse unmodeled-cost budgets.

No simulation, fitting, policy selection, device command, or invented error bound.
A deadline slack is descriptive, never a globally safe controller delay budget.
"""
import argparse
import html
import json
import math
from pathlib import Path
from tools import d1_method_decision_readout as readout

ROOT = readout.source.f.ROOT
STAGE = 'new_seed_confirmation'
METRICS = readout.METRICS


def ledger_counts(record):
    rows = record['ledger']; meta = record['meta']
    if len(rows) != 48 or len({q['id'] for q in rows}) != 48 or meta['planned'] != 48:
        raise ValueError('full denominator/unique arrival identity required')
    completed = sum(q['status'] == 'succeeded' for q in rows)
    met = sum(q['status'] == 'succeeded' and 'response_ns' in q and
              q['response_ns'] <= q['deadline_offset_ns'] for q in rows)
    if completed != meta['completed'] or met != meta['deadline_met']:
        raise ValueError('service summary disagrees with saved ledger')
    for q in rows:
        if q['status'] != 'succeeded':
            continue
        times = [q[k] for k in ('dispatch_ns', 'execution_start_ns', 'output_ready_ns',
                               'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')]
        if times != sorted(times) or times[0] < q['arrival_ns']:
            raise ValueError('response/lane boundary changed')
        boundary = q['output_ready_ns'] if q['priority'] == 'urgent' else q['persist_complete_ns']
        if q['response_ns'] != boundary-q['arrival_ns']:
            raise ValueError('wrong priority response boundary')
    slacks = [(q['deadline_offset_ns']-q['response_ns'])/1e6
              for q in rows if q['status'] == 'succeeded' and 'response_ns' in q]
    return completed == met == 48, min(slacks) if len(slacks) == 48 else None


def same_input(candidate, reference):
    left = {q['id']: q for q in candidate['ledger']}
    right = {q['id']: q for q in reference['ledger']}
    fields = ('task', 'priority', 'arrival_ns', 'deadline_offset_ns', 'ordinal')
    if set(left) != set(right) or any(any(left[k][f] != right[k][f] for f in fields) for k in left):
        raise ValueError('reference must preserve exact same arrivals/tasks/deadlines')


def summarize(records, block):
    selected = [z for z in records if z['meta']['stage'] == STAGE]
    # Reuse strict block completeness/finite metric checks; missing costs remain null.
    groups = readout.summarize(records, block, STAGE, {})
    refs = {(z['meta']['envelope'], z['meta']['seed'], z['meta']['scenario']): z
            for z in selected if z['meta']['policy'] == 'EFT_REFERENCE'}
    cases = []
    for rec in selected:
        m = rec['meta']; ref = refs[m['envelope'], m['seed'], m['scenario']]; rm = ref['meta']
        same_input(rec, ref)
        complete, slack = ledger_counts(rec); ref_complete, ref_slack = ledger_counts(ref)
        known = all(type(z.get(k)) in (int, float) and math.isfinite(z[k])
                    for z in (m, rm) for k in METRICS)
        feasible = complete and ref_complete and known
        delta = {k: m[k]-rm[k] if known else None for k in METRICS}
        # B = -Delta J. Equality erases the modeled gain; strict saving needs Delta E_unknown < B.
        energy_budget = -delta['energy_j'] if feasible and delta['energy_j'] < -readout.TOL else None
        host_total = m.get('decision_host_total_s')
        host_max = m.get('decision_host_max_ms')
        if m['policy'] == 'EFT_REFERENCE':
            # Its constructor has no callback_times instrumentation. Stored zero is not a measurement.
            host_total = host_max = None
        cases.append(dict(comparison_block=block, envelope=m['envelope'], seed=m['seed'],
            scenario=m['scenario'], policy=m['policy'], planned=48, deadline_met=m['deadline_met'],
            feasible_service_and_known_metrics=feasible, min_saved_response_slack_ms=slack,
            reference_min_saved_response_slack_ms=ref_slack,
            **{'delta_'+k: v for k, v in delta.items()},
            strict_energy_gain_requires_unknown_delta_j_below=energy_budget,
            unknown_device_controller_delta_j=None, decision_calls=m.get('decision_calls'),
            recorded_candidate_PC_callback_total_s=host_total, recorded_candidate_PC_callback_max_ms=host_max,
            reference_PC_callback_measured=False, safe_global_extra_delay_ms=None,
            future_accuracy_margin_j=None, future_accuracy_margin_c=None,
            device_energy_gain_verified=False, device_policy_winner=None))
    for g in groups:
        cs = [z for z in cases if z['envelope'] == g['envelope'] and z['policy'] == g['policy']]
        eligible = g['complete_service_and_metrics'] and all(z['feasible_service_and_known_metrics'] for z in cs)
        g['paired_full_service'] = eligible
        budgets = [z['strict_energy_gain_requires_unknown_delta_j_below'] for z in cs]
        g['energy_gain_in_all_saved_cases'] = eligible and all(z is not None for z in budgets)
        g['minimum_saved_energy_budget_j'] = min(budgets) if g['energy_gain_in_all_saved_cases'] else None
        g['maximum_required_peak_AP_cap_c'] = g['max_delta_peak_ap_c'] if eligible else None
        g['maximum_required_AP_area_cap_c_s'] = g['max_delta_thermal_degree_seconds'] if eligible else None
        slacks = [z['min_saved_response_slack_ms'] for z in cs]
        g['minimum_saved_response_slack_ms'] = min(slacks) if all(z is not None for z in slacks) else None
        g['safe_global_extra_delay_ms'] = None
        g['unknown_device_controller_delta_j'] = None
        g['future_accuracy_margin_j'] = g['future_accuracy_margin_c'] = None
        g['joint_modeled_improvement'] = eligible and all(g['max_delta_'+k] <= readout.TOL for k in
            ('energy_j', 'peak_ap_c', 'thermal_degree_seconds')) and any(g['max_delta_'+k] < -readout.TOL
            for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds'))
    return groups, cases


def analyze(root=ROOT):
    root = Path(root)
    readout.source.f.x.p.inputs(readout.source.f.x.p.BUNDLE)
    groups = []; cases = []; checks = {}; hashes = {}
    for block in ('run_v1', 'beam_v1', 'beam_v2'):
        registration_path = root/block/'registered_before_run.json'
        registration = json.loads(registration_path.read_text(encoding='utf8'))
        checks[block] = {p: readout.source.verify_registered_source(p, d, root)
                         for p, d in registration['hashes'].items()}
        ledger = root/block/'records.jsonl.gz'
        hashes[registration_path.relative_to(readout.source.f.x.p.ROOT).as_posix()] = readout.source.f.x.p.digest(registration_path)
        hashes[ledger.relative_to(readout.source.f.x.p.ROOT).as_posix()] = readout.source.f.x.p.digest(ledger)
        local, detail = summarize(readout.source.records(ledger), block)
        groups.extend(local); cases.extend(detail)
    return dict(version='method-tradeoff-budget-pc-v1', selection_type='posthoc saved-evidence readout only',
        interpretation='Delta J_total = Delta J_model + Delta E_unmodeled; equal schedules/accounting are conditional, not physical validation',
        strict_energy_saving_rule='Delta E_unmodeled < -Delta J_model; equality erases the gain',
        deadline_slack_rule='descriptive response-to-deadline slack, not safe global/controller extra latency',
        callback_rule='candidate PC wall time only; EFT stored zeros were not callback measurements; do not convert to phone J or duration',
        source_checks=checks, source_hashes=hashes, groups=groups, cases=cases,
        analysis_code_sha256=readout.source.f.x.p.digest(Path(__file__)),
        new_simulations=0, device_commands=0, new_accuracy_thresholds=False,
        accuracy_pass=None, device_policy_winner=None, experiment_ready=False,
        physical_model_sha256=readout.source.f.x.p.MODEL_SHA,
        initial_sha256=readout.source.f.x.p.INITIAL_SHA)


def save(result, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    readout.source.f.x.p.write(output/'result.json', result)
    readout.source.f.x.old.csv_write(output/'groups.csv', result['groups'])
    readout.source.f.x.old.csv_write(output/'cases.csv', result['cases'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    aliases = {'g1.2_c0.5_b1': 'low', 'g0.45_c0.5_b4': 'queue50',
               'g0.45_c0.75_b4': 'queue75', 'g0.15_c0.5_b8': 'burst50'}
    colors = {'ATC_QUEUED_GUARD_V1': '#3178ac', 'CPU_BOTTLENECK_GUARD_V1': '#c1781b'}
    origin_labels = []
    for g in result['groups']:
        if g['comparison_block'] != 'run_v1' or g['policy'] == 'EFT_REFERENCE':
            continue
        x = g['max_delta_energy_j']; y = g['max_delta_peak_ap_c']
        if x is None or y is None:
            continue
        label = aliases[g['envelope']]+' / '+('ATC' if 'ATC' in g['policy'] else 'CPU bottleneck')
        if abs(x) <= readout.TOL and abs(y) <= readout.TOL:
            origin_labels.append(label)
            continue
        ax.scatter(x, y, color=colors[g['policy']], marker='o' if g['paired_full_service'] else 'x', s=55)
        ax.annotate(label,
                    (x, y), xytext=(5, 5), textcoords='offset points', fontsize=8)
    if origin_labels:
        ax.scatter(0, 0, color='gray', s=55)
        ax.annotate('Same modeled metrics as EFT:\n'+'\n'.join(origin_labels), (0, 0),
            xytext=(-205, 18), textcoords='offset points', fontsize=8,
            arrowprops=dict(arrowstyle='-', color='gray', lw=.8))
    ax.axvline(0, color='gray', lw=.8); ax.axhline(0, color='gray', lw=.8)
    ax.set_xlabel('Maximum paired candidate - EFT J across six saved cases')
    ax.set_ylabel('Maximum paired candidate - EFT peak AP (C)')
    ax.set_title('Frozen model tradeoff; not a measured phone improvement\nCircle = full paired service; cross = service ineligible')
    ax.grid(alpha=.2); fig.tight_layout()
    for suffix in ('png', 'svg'): fig.savefig(output/f'tradeoff.{suffix}', dpi=140)
    plt.close(fig)
    p = output/'tradeoff.svg'
    p.write_text('\n'.join(z.rstrip() for z in p.read_text(encoding='utf8').splitlines())+'\n', encoding='utf8')
    cols = ('comparison_block', 'envelope', 'policy', 'deadline_met', 'planned', 'paired_full_service',
            'minimum_saved_energy_budget_j', 'maximum_required_peak_AP_cap_c',
            'maximum_required_AP_area_cap_c_s', 'minimum_saved_response_slack_ms', 'joint_modeled_improvement')
    head = ''.join('<th>'+html.escape(k)+'</th>' for k in cols)
    body = ''.join('<tr>'+''.join('<td>'+html.escape('미판정 / null' if g[k] is None else
        str(round(g[k], 6) if type(g[k]) is float else g[k]))+'</td>' for k in cols)+'</tr>' for g in result['groups'])
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>모형 상충과 제어비용 여유</title>
<style>body{font:16px sans-serif;max-width:1400px;margin:30px auto;padding:0 20px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:6px}.warn{padding:15px;background:#fff2cf}img{max-width:100%}.wrap{overflow:auto}</style>
<h1>기한을 지키는 모형상 절감의 손익분기 여유</h1>
<p class="warn">새 시뮬레이션·실측0. 각 block/입력의 동일seed·3처리문맥만 대조했습니다. 아래 여유는 조건부 산술이며 물리적 보장·정확도 기준·새 정책 채택이 아닙니다.</p>
<p>총 J 차이 = 모형 J 차이 + 미모형화된 차등 비용. 절감을 남기려면 추가 차등 비용이 표의 양의 J 여유보다 작아야 합니다. 동일한 여유가 앞으로의 입력에도 유지된다는 보장은 없습니다. 일정이 달라질 때의 시간·AP 영향과 측정 오차는 별도 미확인입니다.</p>
<p>AP 상한 필요량은 기존 EFT 대비 저장된 최대 차이입니다. 사용자 허용폭·안전기준·정확도 합격선으로 채택하지 않았습니다. 응답 여유는 당시 최소 기한잔여이며 제어기의 허용 추가 지연이 아닙니다. EFT의 기록된 계산시간0은 계측 부재였으므로 null로 표시했습니다.</p>
<p><a href="groups.csv">묶음 CSV</a> · <a href="cases.csv">사례별 비용·응답 여유</a> · <a href="../README.md">원 비교·한계·재현</a></p>
<img src="tradeoff.png" alt="기기 관측이 아닌 기존 동결식의 모형 비용 차이"><div class="wrap"><table><tr>'''+head+'</tr>'+body+'</table></div></html>'
    (output/'index.html').write_text(page, encoding='utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--output', required=True); args = parser.parse_args()
    save(analyze(args.root), args.output)
