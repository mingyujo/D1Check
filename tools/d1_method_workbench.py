"""Read-only bridge from the simulator CLI to registered method evidence.

Mapping to measured coefficient names is not independent validation of a new
schedule. This route cannot simulate, fit, deploy, or invent missing costs.
"""
import html
import json
import math
from pathlib import Path
from tools import d1_method_tradeoff_budget as budget

ROOT = budget.readout.source.f.x.p.ROOT
RESOURCE = ROOT/'docs/results/method_followup_01/method_readout_resources.json'


def verify_resources(resource=RESOURCE):
    spec = json.loads(Path(resource).read_text(encoding='utf8'))
    if spec['version'] != 'method-workbench-resources-v1':
        raise ValueError('method resource version')
    expected = {
        f'docs/results/method_followup_01/{block}/{name}'
        for block in ('run_v1', 'beam_v1', 'beam_v2')
        for name in ('registered_before_run.json', 'records.jsonl.gz')
    } | {
        'docs/results/online_policy_study_01/overnight_sustained_run01/model.json',
        'docs/results/online_policy_study_01/overnight_sustained_run01/initial_inputs.json',
    }
    if set(spec['files']) != expected:
        raise ValueError('complete registered method resources required')
    for name, digest in spec['files'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or budget.readout.source.f.x.p.digest(path) != digest:
            raise ValueError('method resource mismatch: '+name)
    return spec['files']


def audit_record(record, frozen):
    """Check stored D..L ownership and complete modeled windows, without running it."""
    p = budget.readout.source.f.x.p
    budget.ledger_counts(record)
    jobs = []
    for q in record['ledger']:
        if any(type(q.get(k)) not in (int, float) or not math.isfinite(q[k])
               for k in ('arrival_ns', 'dispatch_ns', 'execution_start_ns', 'output_ready_ns',
                         'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')):
            raise ValueError('non-finite saved timing')
        if q['backend'] not in p.backends(q):
            raise ValueError('unsupported method task/backend')
        if not 35e9 <= q['arrival_ns'] < 120e9:
            raise ValueError('registered arrival window')
        if q['deadline_offset_ns'] != (1.5e9 if q['priority'] == 'urgent' else 6e9):
            raise ValueError('registered response deadline')
        if q['status'] != 'succeeded' or q['lane_available_ns'] > 120e9:
            raise ValueError('no whole-window cost for incomplete lane history')
        jobs.append(dict(state=q['task']+'_'+q['backend'], backend=q['backend'],
                         start=q['dispatch_ns']/1e9, end=q['lane_available_ns']/1e9))
    for i, left in enumerate(jobs):
        for right in jobs[i+1:]:
            if min(left['end'], right['end']) > max(left['start'], right['start']):
                if left['backend'] == right['backend']:
                    raise ValueError('overlapping same lane')
                p.state([left['state'], right['state']])
    expected = p.segments(jobs, 0., 180.)
    stored = record['segments']
    if len(expected) != len(stored):
        raise ValueError('incomplete stored state transitions')
    for left, right in zip(expected, stored):
        if (left['state'] != right['state'] or
                any(not math.isfinite(right[k]) or abs(left[k]-right[k]) > 1e-8
                    for k in ('start_s', 'end_s'))):
            raise ValueError('state boundaries must match actual saved dispatch/lane release')
        if right['state'] != 'idle' and right['state'] not in frozen['energy_increment_w']:
            raise ValueError('missing energy coefficient; no substitution')
    return len(stored)


def analyze(resource=RESOURCE):
    hashes = verify_resources(resource)
    result = budget.analyze()
    frozen, _ = budget.readout.source.f.x.p.inputs(budget.readout.source.f.x.p.BUNDLE)
    audits = []
    for block in ('run_v1', 'beam_v1', 'beam_v2'):
        records = budget.readout.source.records(budget.ROOT/block/'records.jsonl.gz')
        for record in records:
            if record['meta']['stage'] != budget.STAGE:
                continue
            meta = record['meta']
            audits.append(dict(comparison_block=block, envelope=meta['envelope'],
                seed=meta['seed'], scenario=meta['scenario'], policy=meta['policy'],
                mapped_intervals=audit_record(record, frozen), complete_model_window=True,
                measured_state_coefficients_available=True, strict_support=False,
                schedule_transfer_assumption=True, independent_prediction_validation=False,
                policy_difference_distinguishable=None))
    if len(audits) != len(result['cases']):
        raise ValueError('incomplete method scope audit')
    scope = dict(device='A24 only; no S26 coefficient pooling',
        task_backend_cells=list(budget.readout.source.f.x.p.CELLS),
        states=['resident_idle', *sorted(frozen['energy_increment_w'])],
        ownership='dispatch through lane_available; urgent response output_ready, normal persist_complete',
        energy_window_s=[0, 120], ap_window_s=[35, 180],
        initial_condition='exact registered preload history/power; no later observed AP/current inputs',
        service='mean/short/long whole five-phase development contexts; transfer assumption, not WCET',
        overhead='zero incremental decision/record/dispatch assumption in saved schedules; physical differential cost unknown',
        thermal_to_service='unsupported; no invented slowdown',
        strict_support=False, accuracy_pass=None, deployment_allowed=False,
        experiment_ready=False)
    return dict(version='method-workbench-v1', route='method-readout', scope=scope,
        resource_sha256=hashes, audit=audits, readout=result,
        code_sha256={str(p.relative_to(ROOT)).replace('\\', '/'): budget.readout.source.f.x.p.digest(p)
                     for p in (Path(__file__), ROOT/'tools/d1_simulator.py',
                               ROOT/'tools/d1_method_tradeoff_budget.py',
                               ROOT/'tools/d1_method_decision_readout.py')},
        new_simulations=0, device_commands=0, experiment_ready=False)


def save(result, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    budget.readout.source.f.x.p.write(output/'result.json', result)
    budget.readout.source.f.x.old.csv_write(output/'scope_audit.csv', result['audit'])
    summary = []
    for group in result['readout']['groups']:
        summary.append(dict(group, measured_coefficient_mapping=True, strict_support=False,
            independent_prediction_validation=False, policy_difference_distinguishable=None,
            actual_device_energy_gain=None, deployment_allowed=False))
    budget.readout.source.f.x.old.csv_write(output/'summary.csv', summary)
    budget.save(result['readout'], output/'tradeoffs')
    columns = ('comparison_block', 'envelope', 'policy', 'deadline_met', 'planned',
               'paired_full_service', 'pareto_candidate', 'minimum_saved_energy_budget_j',
               'maximum_required_peak_AP_cap_c', 'joint_modeled_improvement')
    header = ''.join('<th>'+html.escape(k)+'</th>' for k in columns)
    body = ''.join('<tr>'+''.join('<td>'+html.escape('미확인 / null' if row[k] is None else
        str(round(row[k], 6) if type(row[k]) is float else row[k]))+'</td>' for k in columns)+'</tr>'
        for row in summary)
    (output/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8">
<title>D1Check 방법론 판독</title><style>body{font:16px/1.6 system-ui;max-width:1350px;margin:30px auto;padding:20px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:6px}.warning{background:#fff2cf;padding:16px}.scroll{overflow:auto}</style>
<h1>공정 스케줄링 원리를 적용한 저장 PC 비교</h1>
<p class="warning">저장된 세 block/28묶음/168사례만 판독했습니다. 새 시뮬레이션·실측·재보정0. 기한충족과 계수 매핑은 독립 예측 검증 또는 정책 우월성 PASS가 아닙니다. 실제 승자·배포 추천은 미판정입니다.</p>
<h2>판정 층위</h2><ol><li>수치: 저장된 동결식 결과가 있고 전체 예정48요청을 판독했습니다.</li>
<li>조건: 현재 3cell·CG_DC·resident 유휴에 계수가 있으나 새 일정의 시간 전용과 제어 비용0은 탐색 가정입니다. strict 미지원입니다.</li>
<li>독립 예측 확인: 기존 CPU/PAR 기기 확인을 새 ATC/병목/beam 확인으로 승계하지 않습니다.</li>
<li>정책 차이 식별: 작은 J/AP 차이가 기기 오차·세션 변동보다 큰지는 미확인입니다.</li></ol>
<p>같은 block/입력/seed의 EFT와 비교하고 기한 실패를 먼저 배제합니다. Pareto 표시는 5비용의 상충이며 새로운 목적 가중치나 온라인 정책이 아닙니다. 모형상 J 여유도 물리적 절감 보장·제어 지연 예산이 아닙니다.</p>
<p>시간 경계: D→실제L 점유, 긴급O/일반P 응답. J0–120초, AP35–180초. 미래 실측 전류/AP를 입력하지 않습니다. 열→처리시간은 미지원이며 S26 계수를 혼합하지 않습니다.</p>
<p><a href="summary.csv">전체 묶음</a> · <a href="scope_audit.csv">실제 lane/상태 경계 검사</a> · <a href="tradeoffs/index.html">상충·미모형화 비용 여유</a> · <a href="result.json">입력·코드 해시와 판독</a></p>
<div class="scroll"><table><tr>'''+header+'</tr>'+body+'</table></div>', encoding='utf8')
    return output
