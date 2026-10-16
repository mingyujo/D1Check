"""Inverse coefficient-precision requirements for fixed saved calendars.

Algebra only: no coefficient fitting, uncertainty estimate, new simulation,
device command or inference that a measured confidence interval exists.
"""
import argparse
from datetime import datetime, timezone
import gzip
import html
import json
import math
from pathlib import Path
import subprocess
from tools import d1_joint_calendar_report as source

P = source.P
ROOT = source.ROOT


def exposure(segments, coefficients):
    times = {key: 0. for key in coefficients}
    last = 0.; total = 0.
    for segment in segments:
        lo, hi = segment['start_s'], segment['end_s']; label = segment['state']
        if not all(math.isfinite(v) for v in (lo, hi)) or hi <= lo or abs(lo-last) > 1e-8:
            raise ValueError('complete continuous saved state window required')
        if label != 'idle' and label not in coefficients: raise ValueError('unknown power state, no substitute')
        duration = max(0., min(120., hi)-max(0., lo))
        total += duration
        if label != 'idle': times[label] += duration
        last = hi
    if abs(total-120.) > 1e-8 or abs(last-180.) > 1e-8:
        raise ValueError('whole J/AP saved window required')
    return times


def inverse(candidate, reference, coefficients, delta_j):
    if not math.isfinite(delta_j) or not all(math.isfinite(v) for v in coefficients.values()):
        raise ValueError('finite saved difference and coefficients required')
    a, b = exposure(candidate, coefficients), exposure(reference, coefficients)
    delta = {key: a[key]-b[key] for key in coefficients}
    calculated = sum(delta[key]*coefficients[key] for key in coefficients)
    if abs(calculated-delta_j) > 1e-7: raise ValueError('state-exposure energy identity mismatch')
    norm = sum(abs(v) for v in delta.values())
    gain = -delta_j if delta_j < 0. else None
    return dict(delta_state_seconds=delta, exposure_l1_s=norm, modeled_delta_j=calculated,
        modeled_J_gain_j=gain,
        uniform_increment_error_break_even_w=None if gain is None or norm == 0. else gain/norm,
        actual_coefficient_error_bound_w=None, actual_controller_delta_j=None,
        independent_policy_advantage_confirmed=False,
        condition='fixed actual schedules and common background: epsilon_W * exposure_L1_s + unknown_delta_controller_J < modeled_gain_J',
        equality_erases_strict_gain=True, estimate_of_actual_uncertainty=False)


def analyze():
    prior = source.load(ROOT/'joint_calendar_v1', ROOT/'joint_calendar_witness_v1')
    transfer_root = ROOT/'joint_calendar_transfer_v1'
    registration = json.loads((transfer_root/'registered_before_run.json').read_text(encoding='utf8'))
    from tools import d1_joint_calendar_transfer as transfer
    if registration['spec'] != transfer.specification(): raise ValueError('fixed transfer rule changed')
    for name, sha in {**registration['code'], **registration['resources']}.items():
        if P.digest(P.ROOT/name) != sha: raise ValueError('fixed transfer hash mismatch')
    if P.digest(ROOT/'joint_calendar_v1/records.jsonl.gz') != registration['source_plans_sha256']:
        raise ValueError('fixed source plan changed')
    data = [json.loads(r) for r in gzip.decompress((transfer_root/'records.jsonl.gz').read_bytes()).decode().splitlines()]
    if len(data) != 4 or {(r['meta']['seed'], r['meta']['context']) for r in data} != {
        (seed, context) for seed in transfer.specification()['seeds'] for context in transfer.specification()['contexts']}:
        raise ValueError('complete fixed-transfer denominator required')
    frozen, _ = P.inputs(P.BUNDLE); coefficients = frozen['energy_increment_w']
    controls = source.study.work.budget.readout.source.records(ROOT/'run_v1/records.jsonl.gz')
    refs = {(r['meta']['envelope'], r['meta']['seed'], r['meta']['scenario']): r for r in controls
        if r['meta']['stage'] == source.study.work.budget.STAGE and r['meta']['policy'] == 'EFT_REFERENCE'}
    rows = []
    for row in prior['rows']:
        key = row['envelope'], row['seed']
        detail = next((d for d in prior['details'] if (d['key']['envelope'], d['key']['seed']) == key), None)
        value = dict(delta_state_seconds=None, exposure_l1_s=None, modeled_delta_j=None, modeled_J_gain_j=None,
            uniform_increment_error_break_even_w=None, actual_coefficient_error_bound_w=None, actual_controller_delta_j=None,
            independent_policy_advantage_confirmed=False, estimate_of_actual_uncertainty=False)
        if detail:
            value = inverse(detail['result']['segments'], detail['reference']['segments'], coefficients, row['delta_energy_j'])
        rows.append(dict(envelope=row['envelope'], seed=row['seed'], context='mean', status=row['status'], **value))
    for r in data:
        m = r['meta']; reference = refs[m['envelope'], m['seed'], m['context']]
        source.study.work.audit_record(dict(meta=r['result']['metrics'], ledger=r['result']['ledger'], segments=r['result']['segments']), frozen)
        source.study.work.budget.same_input(r['result'], reference)
        value = inverse(r['result']['segments'], reference['segments'], coefficients, m['delta_energy_j'])
        rows.append(dict(envelope=m['envelope'], seed=m['seed'], context=m['context'], status='fixed_transfer', **value))
    files = [ROOT/'joint_calendar_v1/records.jsonl.gz', transfer_root/'registered_before_run.json',
        transfer_root/'records.jsonl.gz', P.BUNDLE/'model.json', P.BUNDLE/'initial_inputs.json']
    return dict(version='joint-gain-sensitivity-v1', rows=rows, formula_is_conditional_not_accuracy_bound=True,
        actual_uncertainty_estimated=False, new_simulations=0, physical_coefficients_changed=False,
        independent_device_sessions=0, device_commands=0, experiment_ready=False,
        resources={p.relative_to(P.ROOT).as_posix(): P.digest(p) for p in files})


def save(result, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    P.write(out/'analysis_manifest.json', dict(utc_after_analysis=datetime.now(timezone.utc).isoformat(),
        base_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), source_dirty=True,
        retrospective_readout=True, registration_before_analysis=False,
        rule='all four prior mean solver outcomes plus all four fixed short/long transfers; exposure algebra only',
        source_sha256=P.digest(__file__), resources=result['resources'], new_simulations=0, device_commands=0))
    P.write(out/'result.json', result)
    (out/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
    fields = sorted(set().union(*(r.keys() for r in result['rows'])))
    source.study.followup.x.old.csv_write(out/'requirements.csv', [{k: r.get(k) for k in fields} for r in result['rows']])
    cols = ('envelope', 'seed', 'context', 'status', 'modeled_J_gain_j', 'exposure_l1_s',
        'uniform_increment_error_break_even_w', 'actual_coefficient_error_bound_w', 'actual_controller_delta_j')
    table = '<tr>'+''.join('<th>'+k+'</th>' for k in cols)+'</tr>'
    table += ''.join('<tr>'+''.join('<td>'+html.escape('미확인 / null' if r[k] is None else str(r[k]))+'</td>' for k in cols)+'</tr>' for r in result['rows'])
    (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>작은 J 이득의 계수 정밀도 요구</title>'+
        '<style>body{font:16px/1.7 system-ui;margin:24px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #aaa;padding:6px}.note{background:#fff2ca;padding:15px}.scroll{overflow:auto}</style>'+
        '<h1>모형 이득을 실제 우열로 사용할 수 없는 이유</h1><p class="note">표는 실제 계수 불확실성을 추정한 결과가 아닙니다. 같은 고정 일정/공통 background에서 각 증가전력 계수 오차가 ε W 이내라는 조건을 가정했을 때, 최대 J 차이 변화는 ε×상태시간차이 L1입니다. 실제 ε와 제어 비용은null이며 엄격한 이득은 등호에서 없어집니다.</p>'+
        '<p>조건: ε_W×L1_s + 미모형화 차등제어J &lt; 계산상J이득. 공통 baseline 변화·일정 변경·비정상 소비·센서 절대 정확도·AP 정확도는 이 식으로 인증하지 않습니다. 계수 변경/새 시뮬레이션/실측/정확도PASS는 없습니다.</p>'+
        '<div class="scroll"><table>'+table+'</table></div><p><a href="requirements.csv">전체8행·상태시간차이</a> · <a href="result.json">조건·원해시·미판정</a> · <a href="../README.md">해석·검증·한계</a></p>', encoding='utf8')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    save(analyze(), parser.parse_args().output)
