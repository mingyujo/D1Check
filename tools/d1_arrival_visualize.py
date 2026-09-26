"""Build an offline dashboard from the frozen arrival PC results, without a batch rerun.

Only the 24-request seed-201 ledgers absent from the stored bundle are replayed.
Every replay metric is checked against the original metrics.csv before publishing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch
from tools import d1_arrival_energy_sensitivity as energy_stress
from tools import d1_arrival_plan as io

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = Path('C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_explore_batch_v3/metrics.csv')
DEFAULT_OUTPUT = ROOT / 'docs/results/arrival_visualization_01'
POLICIES = ('CPU_FIFO', 'CPU_URGENT', 'FIXED_SPLIT', 'B2_PC',
            'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC', 'P_NO_PARALLEL_PC', 'P_NO_PAIR_COST_PC')
SCENARIOS = ('low', 'queue', 'burst')
MODES = ('strict', 'explore')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        raise ValueError('empty visualization data')
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(metrics_path=DEFAULT_METRICS, output=DEFAULT_OUTPUT):
    metrics_path, output = Path(metrics_path).resolve(), Path(output)
    summary_path = ROOT / 'docs/results/arrival_explore_20260925/summary.csv'
    sensitivity_path = ROOT / 'docs/results/arrival_explore_20260925/paired_effects.csv'
    freeze_path = ROOT / 'docs/results/arrival_explore_20260925/freeze_before_evaluation.json'
    bundle = ROOT / 'docs/results/arrival_explore_20260925/input_bundle'
    operational_path = ROOT / 'docs/results/energy_operational_sim_01/comparison.csv'
    evaluation_path = ROOT / 'docs/results/energy_operational_sim_01/confirmation_evaluation.json'
    template_path = ROOT / 'tools/assets/d1_arrival_dashboard.html'
    sources = [metrics_path, summary_path, sensitivity_path, freeze_path,
               operational_path, evaluation_path, template_path,
               bundle / 'estimates.json', bundle / 'realizations.json',
               ROOT / 'tools/d1_arrival_energy_sensitivity.py',
               ROOT / 'tools/d1_arrival_visualize.py',
               ROOT / 'tools/d1_arrival_explore.py']
    sources.extend(sorted((metrics_path.parent / 'representative').glob('*.json')))
    for path in sources:
        if not path.is_file():
            raise FileNotFoundError(path)
    for name in ('estimates.json', 'realizations.json'):
        receipt = json.loads((bundle / 'receipt.json').read_text(encoding='utf-8'))
        if io.digest(bundle / name) != receipt['files'][name]:
            raise ValueError('frozen input bundle changed')
    original = read_csv(metrics_path)
    if len(original) != 960:
        raise ValueError('expected stored 960-run metric file')
    original = {(r['mode'], r['scenario'], r['policy'], int(r['seed'])): r for r in original}
    summary = [r for r in read_csv(summary_path) if r['scenario'] in SCENARIOS]
    effects = [r for r in read_csv(sensitivity_path) if r['comparator'] == 'B3_SOLO_EFT_PC']
    freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
    config = io.read(bundle / 'estimates.json')
    vectors = io.read(bundle / 'realizations.json')
    trace_rows = []
    for mode in MODES:
        for scenario in SCENARIOS:
            spec = next(s for s in batch.scenarios() if s['id'] == scenario)
            for policy in POLICIES:
                settings = batch.defaults(mode)
                settings.update(spec['changes'])
                settings.update({k: freeze['B2'][mode]['settings'][k]
                                 for k in ('static_map', 'static_parallel')})
                actual_policy = policy
                if policy == 'P_NO_PAIR_COST_PC':
                    actual_policy = 'P_PAIR_COST_PC'
                    settings['predicted_interference'] = 1.
                stored_trace = metrics_path.parent / 'representative' / f'{policy}.json'
                if mode == 'explore' and scenario == 'queue' and stored_trace.is_file():
                    result = json.loads(stored_trace.read_text(encoding='utf-8'))
                else:
                    result = engine.simulate(config, vectors, batch.workload(scenario, 'evaluation'),
                                             policy=actual_policy, settings=settings, seed=201)
                reference = original[(mode, scenario, policy, 201)]
                for key in ('urgent_p95_ms', 'normal_mean_ms', 'completion',
                            'urgent_deadline_violation', 'normal_timely', 'makespan_s',
                            'unfinished'):
                    value = result['metrics'][key]
                    if not math.isclose(float(reference[key]), value, rel_tol=1e-11, abs_tol=1e-9):
                        raise ValueError(f'replay differs from frozen metrics: {mode}/{scenario}/{policy}/{key}')
                for item in result['ledger']:
                    trace_rows.append(dict(mode=mode, scenario=scenario, policy=policy,
                        seed=201, id=item['id'], priority=item['priority'], task=item['task'],
                        backend=item.get('backend', ''), status=item['status'],
                        deadline_offset_ns=item['deadline_offset_ns'],
                        arrival_ns=item['arrival_ns'], dispatch_ns=item.get('dispatch_ns', ''),
                        execution_start_ns=item.get('execution_start_ns', ''),
                        output_ready_ns=item.get('output_ready_ns', ''),
                        persist_complete_ns=item.get('persist_complete_ns', ''),
                        worker_release_ns=item.get('worker_release_ns', ''),
                        lane_available_ns=item.get('lane_available_ns', ''),
                        late_success=item.get('late_success', '')))
    # Aggregate only original evaluation runs. Request counts are not independent device samples.
    service = []
    for row in summary:
        group = [original[(row['mode'], row['scenario'], row['policy'], seed)]
                 for seed in (201, 202, 203, 204, 205)]
        service.append(dict(mode=row['mode'], scenario=row['scenario'], policy=row['policy'],
            simulation_replicates=5, planned=sum(int(r['planned']) for r in group),
            urgent_planned=sum(int(r['urgent_n']) for r in group),
            normal_planned=sum(int(r['normal_n']) for r in group),
            unfinished=sum(int(r['unfinished']) + int(r['not_arrived']) for r in group),
            urgent_p95_ms_mean=row['urgent_p95_ms'],
            normal_mean_ms_mean=row['normal_mean_ms'],
            urgent_not_timely_rate=row['urgent_deadline_violation'],
            normal_not_timely_rate=str(1-float(row['normal_timely'])),
            makespan_s_mean=row['makespan_s'], throughput_mean=row['throughput']))
    # Fixed 870-job evidence is separate from low/queue/burst; it cannot fill their energy cells.
    operational = read_csv(operational_path)
    evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))
    fixed_rows = []
    for row in operational:
        fixed_rows.append(dict(block=row['block'], mode=row['mode'], order=row['order'],
            work_requests=row['work_requests'], start_ap_c=row['start_ap_c'],
            work_completion_s=row['work_completion_s'],
            work_energy_j_conditional=row['work_energy_j_conditional'],
            common_window_energy_j_conditional=row['common_window_energy_j_conditional'],
            load_ap_peak_c=row['load_ap_peak_c'], evidence='실측 재생·조건부 전류 단위'))
    curves = []
    for mode in ('serial', 'parallel'):
        prediction = evaluation['outcomes'][mode]['prediction']
        phases = prediction['phase_trace']
        start = phases[2]['start_s']
        for phase in phases[2:4]:  # common 480-s window, work then resident wait
            if phase['whole_device_energy_j_conditional'] is None:
                continue
            power = phase['whole_device_energy_j_conditional'] / (phase['end_s']-phase['start_s'])
            previous = sum(p['whole_device_energy_j_conditional'] or 0 for p in phases[2:phases.index(phase)])
            for t, temp in phase['path']:
                elapsed = t-start
                if 0 <= elapsed <= 480:
                    curves.append(dict(mode=mode, phase=phase['phase'], elapsed_s=elapsed,
                        cumulative_energy_j_conditional=previous+power*(t-phase['start_s']),
                        ap_c=temp, preparation_initial_ap_c=evaluation['outcomes'][mode]['initial_ap_c'],
                        load_start_ap_c=phases[2]['ap_start_c'],
                        evidence='확인 시작온도에 적용한 개발 동결 모형·사후 평가'))
        # Include the exact common-window boundary, not merely the last sensor knot.
        boundary = start + 480
        last_phase = next(p for p in phases[2:4] if p['start_s'] <= boundary <= p['end_s'])
        knots = last_phase['path']
        left, right = next((a, b) for a, b in zip(knots, knots[1:]) if a[0] <= boundary <= b[0])
        fraction = (boundary-left[0])/(right[0]-left[0]) if right[0] != left[0] else 0
        ap = left[1] + fraction*(right[1]-left[1])
        curves.append(dict(mode=mode, phase=last_phase['phase'], elapsed_s=480,
            cumulative_energy_j_conditional=prediction['common_window_energy_j_conditional'],
            ap_c=ap, preparation_initial_ap_c=evaluation['outcomes'][mode]['initial_ap_c'],
            load_start_ap_c=phases[2]['ap_start_c'],
            evidence='확인 시작온도에 적용한 개발 동결 모형·사후 평가'))
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / 'timeline.csv', trace_rows)
    write_csv(output / 'service.csv', service)
    write_csv(output / 'sensitivity.csv', effects)
    write_csv(output / 'fixed_870_comparison.csv', fixed_rows)
    write_csv(output / 'fixed_870_model_curve.csv', curves)
    stress_rows, stress_paths, stress_contrasts, stress_break_even = energy_stress.build(
        output / 'timeline.csv', output)
    payload = dict(service=service, timeline=trace_rows, sensitivity=effects,
        fixed=fixed_rows, curves=curves, energyRows=stress_rows,
        energyPaths=stress_paths, energyContrasts=stress_contrasts,
        energyBreakEven=stress_break_even,
        provenance={str(p.relative_to(metrics_path.parent)) if p.is_relative_to(metrics_path.parent)
                    else str(p.relative_to(ROOT)): sha(p) for p in sources},
        labels=dict(arrival='합성 PC 탐색·모형 결과 (실기기 표본 0)',
                    fixed='고정 870건 A24: 실측 재생 / 개발 모형 예측, 임의 도착에 전용 불가'))
    template = template_path.read_text(encoding='utf-8')
    html = template.replace('/*__EMBEDDED_DATA__*/',
                            'const DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + ';')
    (output / 'dashboard.html').write_text(html, encoding='utf-8')
    plot_figures(output, service, effects, fixed_rows, curves)
    for svg in output.glob('*.svg'):
        # Matplotlib emits insignificant trailing spaces in path data.
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
    (output / 'SOURCE_HASHES.json').write_text(json.dumps(payload['provenance'], indent=2), encoding='utf-8')
    return output


def plot_figures(output, service, effects, fixed, curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path('C:/Windows/Fonts/malgun.ttf')
    if font.is_file():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    names = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC')
    rows = [next(r for r in service if r['mode']=='explore' and r['scenario']=='queue' and r['policy']==p) for p in names]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for ax, key, title in zip(axes, ('urgent_p95_ms_mean','normal_mean_ms_mean'),
                              ('긴급 응답 P95 평균 (ms)', '일반 평균 응답 (ms)')):
        ax.bar(range(len(rows)), [float(r[key]) for r in rows], color='#3975ac')
        ax.set_xticks(range(len(rows)), names, rotation=50, ha='right')
        ax.set_title(title); ax.grid(axis='y', alpha=.2)
    fig.suptitle('사전 대표: queue / explore · seed 201–205\n긴급 P95: 반복별 완료 n=6 nearest-rank의 평균 · 실기기 검증 아님')
    fig.tight_layout()
    for suffix in ('png', 'svg'): fig.savefig(output / f'queue_response.{suffix}', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    scenario_ids = [s['id'] for s in batch.scenarios()]
    for mode_index, mode in enumerate(MODES):
        group = [r for r in effects if r['mode']==mode]
        for i, scenario in enumerate(scenario_ids):
            cells = [r for r in group if r['scenario']==scenario]
            for ax, field in zip(axes, ('urgent_relative_pct','normal_relative_pct')):
                values = [float(r[field]) for r in cells]
                x = i+(-.12 if mode_index==0 else .12)
                ax.scatter([x]*len(values), values, alpha=.25, s=15,
                           color='#3975ac' if mode_index==0 else '#ce7844')
                ax.scatter(x, sum(values)/len(values), marker='_', s=150,
                           color='#3975ac' if mode_index==0 else '#ce7844',
                           label=mode if i==0 else None)
    for ax, title in zip(axes, ('긴급 P95', '일반 평균 응답')):
        ax.axhline(0, color='black', lw=.8); ax.set_title(title + ' · P 대비 B3 (%)')
        ax.set_ylabel('음수는 P의 낮은 지연'); ax.grid(alpha=.2); ax.legend()
        ax.set_xticks(range(len(scenario_ids)),scenario_ids)
        ax.tick_params(axis='x', labelrotation=55)
        for tick in ax.get_xticklabels(): tick.set_ha('right')
    fig.suptitle('합성 PC 민감도 · 범주별 seed 5점(연함)과 평균(가로선), 연결선 없음 · 신뢰구간 아님')
    fig.tight_layout()
    for suffix in ('png', 'svg'): fig.savefig(output / f'sensitivity.{suffix}', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 6))
    for row in fixed:
        x = float(row['work_completion_s']); y = float(row['common_window_energy_j_conditional']); t = float(row['load_ap_peak_c'])
        ax.scatter(x, y, c=[t], cmap='inferno', vmin=30, vmax=35, s=120,
                   marker='o' if row['block']=='development' else 's', edgecolors='black')
        ax.annotate(f"{row['block']} / {row['mode']}", (x, y), xytext=(5,5), textcoords='offset points', fontsize=8)
    ax.set_xlabel('870건 작업 완료시간 (s)'); ax.set_ylabel('공통 480초 기기 전체 에너지 (J, 조건부)')
    ax.set_title('고정 CC_DG · 원본 실측 재생 · 색=AP 최고온도(°C)')
    sm = plt.cm.ScalarMappable(cmap='inferno', norm=plt.Normalize(30,35))
    fig.colorbar(sm, ax=ax, label='AP 최고온도 (°C)')
    fig.tight_layout()
    for suffix in ('png', 'svg'): fig.savefig(output / f'fixed_tradeoff.{suffix}', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for mode, color in (('serial', '#3975ac'), ('parallel', '#ce7844')):
        for phase in ('load', 'post_work_wait'):
            rows = [r for r in curves if r['mode'] == mode and r['phase'] == phase]
            for ax, key in zip(axes, ('cumulative_energy_j_conditional', 'ap_c')):
                ax.plot([r['elapsed_s'] for r in rows], [r[key] for r in rows],
                        color=color, label=mode if phase == 'load' else None)
    axes[0].set_ylabel('누적 기기 에너지 (J, 조건부)')
    axes[1].set_ylabel('AP 온도 (°C)')
    for ax in axes:
        ax.set_xlabel('작업 시작 후 시간 (s) · 공통 480초 창')
        ax.grid(alpha=.2)
        ax.legend()
    starts = {m: next(r for r in curves if r['mode']==m) for m in ('serial','parallel')}
    fig.suptitle('별도 고정 870건 개발 동결 모형 · 임의 도착 예측 아님\n'
                 + '부하 시작 AP: 직렬 {:.1f}°C / 병행 {:.1f}°C'.format(
                     starts['serial']['load_start_ap_c'], starts['parallel']['load_start_ap_c']))
    fig.tight_layout()
    for suffix in ('png', 'svg'): fig.savefig(output / f'fixed_model_path.{suffix}', dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrics', type=Path, default=DEFAULT_METRICS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(build(args.metrics, args.output))
