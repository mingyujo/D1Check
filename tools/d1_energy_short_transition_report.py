"""Report one short-transition diagnostic without widening the frozen model's support.

The archived session is a protocol-transfer diagnostic. Predictions below the
frozen development AP range are arithmetic extrapolations, never validation.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_energy_state_collection as state
from tools.d1_energy_ap_collect05_partial import paths_for_confirmation

FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(stats, frozen):
    blocks = []
    for block in stats['blocks']:
        seconds = (block['end_ns'] - block['start_ns']) / 1e9
        observed = block['power']['full_energy_j']
        if observed is None or block['state'] not in frozen['whole_device_power_w']:
            raise ValueError('unsupported or uncovered block')
        predicted = frozen['whole_device_power_w'][block['state']] * seconds
        blocks.append(dict(block=block['name'], state=block['state'], duration_s=seconds,
                           actual_lane_overlap_s=block['joint_lane_occupancy_s'],
                           ap_samples=len(block['ap_path']), observed_energy_j=observed,
                           extrapolated_energy_j=predicted, signed_difference_j=predicted-observed))
    groups = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for row in blocks:
        item = groups[row['state']]
        item[0] += row['duration_s']
        item[1] += row['observed_energy_j']
        item[2] += row['extrapolated_energy_j']
        item[3] += 1
    grouped = [dict(state=name, blocks=v[3], duration_s=v[0], observed_energy_j=v[1],
                    extrapolated_energy_j=v[2], signed_difference_j=v[2]-v[1])
               for name, v in sorted(groups.items())]
    return blocks, grouped


def write_dashboard(output, summary, grouped):
    rows = ''.join('<tr>'+''.join(f'<td>{html.escape(str(value))}</td>' for value in (
        row['state'], row['blocks'], f"{row['duration_s']:.3f}",
        f"{row['observed_energy_j']:.3f}", f"{row['extrapolated_energy_j']:.3f}",
        f"{row['signed_difference_j']:+.3f}"))+'</tr>' for row in grouped)
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 짧은 전환 진단</title>
<style>body{{font:16px/1.5 system-ui,'Malgun Gothic';max-width:1050px;margin:2em auto;padding:0 1em;color:#203142}}.notice{{background:#fff1cc;padding:1em}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #bdcbd5;padding:.4em;text-align:right}}td:first-child,th:first-child{{text-align:left}}img{{max-width:100%}}</style>
<h1>A24 CC_DG 짧은 상태 전환 진단 1세션</h1>
<p class="notice"><b>동결 모형의 지원 범위 밖:</b> 시작 AP {summary['initial_ap_c']:.1f}°C는 개발 관측 범위 {summary['model_support']['development_observed_range_c'][0]:.1f}-{summary['model_support']['development_observed_range_c'][1]:.1f}°C의 아래입니다. 점선은 동결식을 수치 대입한 <b>탐색 외삽</b>이며 예측 정확도 검증이 아닙니다. 새 APK/프로토콜 진단이고 임의 도착·정책 절감 실측이 아닙니다.</p>
<p>공통창 {summary['common_window_s']:.3f}초 관측 {summary['common_observed_energy_j']:.3f}J, 상태 매핑 {summary['mapped_s']:.3f}초 관측 {summary['mapped_observed_energy_j']:.3f}J 대 외삽 {summary['mapped_extrapolated_energy_j']:.3f}J. 매핑되지 않은 {summary['unmapped_s']:.3f}초는 0으로 채우지 않았습니다. 작업 {summary['work_calls']}회, 실제 병행 lane 공동 점유 총 {summary['actual_lane_overlap_s']:.3f}초, AP 최고 관측 {summary['observed_ap_peak_c']:.1f}°C.</p>
<p><a href="summary.json">판정과 출처 JSON</a> · <a href="blocks.csv">36개 블록 CSV</a> · <a href="states.csv">상태별 잔차 CSV</a> · <a href="energy_path.csv">에너지 경로 CSV</a> · <a href="ap_path.csv">AP 경로 CSV</a> · <a href="README.md">재현 안내</a></p>
<img src="paths.svg" alt="관측과 지원 범위 밖 동결식 대입의 누적 에너지, AP, 잔차">
<h2>상태별 차이: 동결식 대입 - 관측</h2><table><tr><th>실행 상태</th><th>블록 수</th><th>초</th><th>관측 J</th><th>외삽 J</th><th>차이 J</th></tr>{rows}</table>
<p>J는 A24 전류 raw=mA 해석에 따른 기기 전체 조건부 값이며 절대 정확도는 미인증입니다. AP는 AP 센서(mType=0)로 BAT/표면 온도나 안전 한도가 아닙니다. 센서/요청 표본은 독립 세션 수가 아닙니다. 기존 합성 도착 시뮬레이터의 전력·열 값은 별도 가정이며 이 진단으로 엄격 지원을 확장하지 않았습니다.</p>
<p><a href="../energy_ap_transition_01/dashboard.html">기존 CG_DC 전이 진단</a> · <a href="../arrival_policy_screen_01/dashboard.html">가정 기반 정책 탐색</a></p></html>'''
    (output/'dashboard.html').write_text(page, encoding='utf-8')


def report(run, plan_file, frozen_file, output):
    run, plan_file, frozen_file, output = map(Path, (run, plan_file, frozen_file, output))
    plan = p.read(plan_file)
    receipt = p.read(run/'FINAL_RECEIPT.json')
    if p.digest(frozen_file) != FROZEN_SHA or p.digest(run/'development_freeze.json') != FROZEN_SHA:
        raise ValueError('frozen development artifact changed')
    if plan['experiment_id'] != 'ENERGY-AP-SHORT-TRANSITION-DIAG-01' or len(plan['entries']) != 1:
        raise ValueError('unexpected plan')
    if receipt['status'] != 'completed_short_transition_protocol_diagnostic_only' or receipt['sessions'] != 1:
        raise ValueError('diagnostic did not complete')
    session = run / f"00_{plan['entries'][0]['session_id']}"
    stats = p.read(session/'validated.json')
    if stats['status'] != 'eligible_regimen_only' or stats['condition'] != 'CC_DG' or stats['phase'] != 'confirmation':
        raise ValueError('unexpected session or ineligible data')
    for name, source in [('manifest', session/'artifacts/manifest.json'),
                         ('progress', session/'artifacts/progress.jsonl'),
                         ('thermal', session/'thermal.jsonl')]:
        if p.digest(source) != stats['input_hashes'][name]:
            raise ValueError('source changed: '+name)
    frozen = p.read(frozen_file)
    verdict = state.evaluate(stats, frozen, plan)
    if verdict['status'] != 'unsupported_initial_ap_outside_development_observed_range':
        raise ValueError('expected support decision changed; inspect before reporting')
    energy_rows, ap_rows = paths_for_confirmation(stats, frozen)
    blocks, grouped = summarize(stats, frozen)
    if abs(energy_rows[-1]['observed_energy_j']-stats['common_window']['full_energy_j']) > 1e-6:
        raise ValueError('energy path and common window differ')
    mapped_seconds = sum(row['duration_s'] for row in blocks)
    mapped_observed = sum(row['observed_energy_j'] for row in blocks)
    mapped_extrapolated = sum(row['extrapolated_energy_j'] for row in blocks)
    if abs(mapped_extrapolated-energy_rows[-1]['predicted_energy_j']) > 1e-6:
        raise ValueError('prediction path and block sum differ')
    summary = dict(status='completed_eligible_measurement_but_frozen_prediction_unsupported',
        scope='one A24 CC_DG 10-20 second block transition; protocol transfer only',
        model_support=verdict, frozen_sha256=FROZEN_SHA, plan_sha256=p.digest(plan_file),
        apk_sha256=plan['apk_sha256'], source_manifest_sha256=stats['input_hashes']['manifest'],
        source_progress_sha256=stats['input_hashes']['progress'],
        source_thermal_sha256=stats['input_hashes']['thermal'],
        independent_validation=False, experiment_ready=False, work_calls=stats['work_calls'],
        eligibility_calls=stats['eligibility_calls'], warmup_calls=stats['warmup_calls'],
        common_window_s=stats['common_window']['duration_s'],
        common_observed_energy_j=stats['common_window']['full_energy_j'],
        mapped_s=mapped_seconds, unmapped_s=stats['common_window']['duration_s']-mapped_seconds,
        mapped_observed_energy_j=mapped_observed,
        mapped_extrapolated_energy_j=mapped_extrapolated,
        mapped_signed_difference_j=mapped_extrapolated-mapped_observed,
        initial_ap_c=stats['start_ap_c'], observed_ap_peak_c=max(x['ap_peak_c'] for x in stats['blocks']),
        arithmetic_ap_mae_c=sum(abs(x['predicted_ap_c']-x['observed_ap_c']) for x in ap_rows)/len(ap_rows),
        arithmetic_ap_max_absolute_difference_c=max(abs(x['predicted_ap_c']-x['observed_ap_c']) for x in ap_rows),
        arithmetic_ap_sample_peak_c=max(x['predicted_ap_c'] for x in ap_rows),
        actual_lane_overlap_s=stats['actual_joint_lane_occupancy_s'],
        caveat='Extrapolation below initial AP support by 0.2 C; not a prediction accuracy estimate. Raw current=mA conditional; absolute J unverified.')
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output/'blocks.csv', blocks)
    write_csv(output/'states.csv', grouped)
    write_csv(output/'energy_path.csv', energy_rows)
    write_csv(output/'ap_path.csv', ap_rows)
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot([r['time_s'] for r in energy_rows], [r['observed_energy_j'] for r in energy_rows], label='관측')
    axes[0].plot([r['time_s'] for r in energy_rows], [r['predicted_energy_j'] for r in energy_rows], '--', label='범위 밖 동결식 대입')
    axes[0].set_ylabel('누적 기기 전체 에너지 (J)'); axes[0].legend()
    axes[1].plot([r['time_s'] for r in ap_rows], [r['observed_ap_c'] for r in ap_rows], label='관측 AP')
    axes[1].plot([r['time_s'] for r in ap_rows], [r['predicted_ap_c'] for r in ap_rows], '--', label='범위 밖 동결식 대입')
    axes[1].set_ylabel('AP 센서 (°C)'); axes[1].legend()
    axes[2].plot([r['time_s'] for r in energy_rows], [r['predicted_energy_j']-r['observed_energy_j'] for r in energy_rows])
    axes[2].axhline(0, color='gray', lw=.8)
    axes[2].set_ylabel('누적 대입-관측 (J)'); axes[2].set_xlabel('공통창 시작 후 초')
    fig.suptitle('CC_DG 짧은 상태 전환 1세션: 시작 AP 지원 범위 밖 (정확도 검증 아님)')
    fig.tight_layout()
    svg = output/'paths.svg'
    fig.savefig(svg, metadata={'Date': None})
    fig.savefig(output/'paths.png', dpi=120)
    plt.close(fig)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8')
    write_dashboard(output, summary, grouped)
    print(json.dumps({k: summary[k] for k in ('status', 'common_window_s',
        'common_observed_energy_j', 'mapped_signed_difference_j', 'initial_ap_c')},
        ensure_ascii=True, indent=2))


def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'plan', 'frozen', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    report(args.run, args.plan, args.frozen, args.output)


if __name__ == '__main__':
    main()
