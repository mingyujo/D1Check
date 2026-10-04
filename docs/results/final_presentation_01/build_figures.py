"""Render presentation evidence from frozen results; no simulation or device calls."""
from pathlib import Path
import csv
import hashlib
import json
import math
from datetime import datetime, timezone

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'online_policy_study_01' / 'overnight_sustained_run01'
PINS = {
    'metrics.csv': '8ccc5fad75884ffb0e994f2a4c6e903d4e9fdf7bd6310cdcbdc0b1b70e5a1038',
    'pair_differences.csv': '743a490139f7d6e8b4d47224fcae753b86ee29016213249b23c0847d686d161f',
    'model.json': '5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    with (SOURCE / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    for name, expected in PINS.items():
        assert sha(SOURCE / name) == expected, f'Source changed: {name}'
    rows = sorted((r for r in load('metrics.csv') if r['prediction'] == 'arrival_forecast'),
                  key=lambda r: int(r['index']))
    pairs = load('pair_differences.csv')
    assert len(rows) == 8 and len(pairs) == 4
    assert [int(r['index']) for r in rows] == list(range(8))
    assert all(int(r['actual_deadline_met']) == int(r['planned']) == 192 for r in rows)
    assert all(r['strict_supported'] == 'False' and r['accuracy_pass'] == '' for r in rows)
    for p in pairs:
        members = [r for r in rows if r['pair'] == p['pair']]
        cpu, = [r for r in members if r['policy'] == 'CPU_URGENT_ONLINE_V1']
        par, = [r for r in members if r['policy'] == 'B2_PARALLEL_ONLINE_V1']
        for source, delta in [('observed_120s_j', 'observed_par_minus_cpu_j'),
                              ('actual_urgent_p95_ms', 'urgent_p95_difference_ms'),
                              ('observed_peak_ap_c', 'observed_peak_ap_difference_c'),
                              ('common_start_ap_c', 'initial_ap_difference_c')]:
            assert math.isclose(float(par[source]) - float(cpu[source]), float(p[delta]), abs_tol=1e-9)
    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ('Malgun Gothic', 'Noto Sans CJK KR', 'NanumGothic') if f in installed), None)
    if font is None:
        raise RuntimeError('Install a Korean font: Malgun Gothic / Noto Sans CJK KR / NanumGothic')
    plt.rcParams.update({'font.family': font, 'font.size': 14, 'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'path', 'svg.hashsalt': 'd1check-final-presentation-01'})
    blue, orange = '#1565A3', '#C75613'
    artifacts = []

    def save(fig, stem, footer):
        fig.text(.06, .055, footer, fontsize=11, color='#444444')
        fig.subplots_adjust(left=.09, right=.97, top=.83, bottom=.23, wspace=.3)
        for ext in ('png', 'svg'):
            path = HERE / f'{stem}.{ext}'
            fig.savefig(path, dpi=170, facecolor='white', metadata={'Date': None} if ext == 'svg' else None)
            if ext == 'svg':
                # Whitespace between SVG path tokens has no visual meaning.
                path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()) + '\n',
                                encoding='utf-8', newline='\n')
            artifacts.append(path)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fig.suptitle('병행 정책의 긴급 응답 P95가 네 비교쌍에서 짧았다', fontsize=23, x=.06, ha='left')
    for policy, label, color, offset in [('CPU_URGENT_ONLINE_V1', 'CPU 우선', blue, -.11),
                                          ('B2_PARALLEL_ONLINE_V1', '분류 GPU + 탐지 CPU', orange, .11)]:
        group = sorted((r for r in rows if r['policy'] == policy), key=lambda r: int(r['pair']))
        xs = [int(r['pair']) + 1 + offset for r in group]
        ys = [float(r['actual_urgent_p95_ms']) for r in group]
        ax.scatter(xs, ys, s=100, color=color, label=label, zorder=3)
        for x, y in zip(xs, ys):
            ax.annotate(f'{y:.1f}', (x, y), xytext=(0, 10), textcoords='offset points', ha='center', fontsize=12)
    ax.set(xticks=[1, 2, 3, 4], xticklabels=['쌍 1', '쌍 2', '쌍 3', '쌍 4'],
           ylabel='실측 긴급 응답 P95 (ms)', ylim=(0, 500), xlim=(.55, 4.45))
    ax.grid(axis='y', alpha=.2)
    ax.legend(loc='lower left', frameon=False)
    save(fig, '01_response', 'A24 등록 192요청/400ms · 정책별 4세션 · 모든 세션 192/192 기한 충족\n각 점은 한 세션의 P95. 독립 표본 192개 또는 보편적인 응답 개선 보장을 뜻하지 않음.')

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 7.2))
    fig.suptitle('에너지와 최고 AP의 관측 차이는 방향이 일정하지 않았다', fontsize=23, x=.06, ha='left')
    for ax, key, title, unit in [(axes[0], 'observed_par_minus_cpu_j', '공통 120초 에너지', 'J'),
                                  (axes[1], 'observed_peak_ap_difference_c', '관측 최고 AP', '°C')]:
        ys = [float(p[key]) for p in pairs]
        ax.axhline(0, color='#666666', linewidth=1)
        ax.scatter([1, 2, 3, 4], ys, color=orange, s=95, label='관측 차이', zorder=3)
        ax.set(xticks=[1, 2, 3, 4], xticklabels=['쌍 1', '쌍 2', '쌍 3', '쌍 4'],
               title=title, ylabel=f'병행 - CPU ({unit})', xlim=(.5, 4.5))
        ax.grid(axis='y', alpha=.2)
        for x, y in enumerate(ys, 1):
            ax.annotate(f'{y:+.2f}', (x, y), xytext=(0, 10), textcoords='offset points', ha='center', fontsize=12)
    axes[0].set_ylim(-9, 17)
    axes[1].set_ylim(-.65, .8)
    axes[1].scatter([1, 2, 3, 4], [float(p['initial_ap_difference_c']) for p in pairs],
                    facecolors='none', edgecolors=blue, marker='s', s=100, label='시작 AP 차이')
    axes[1].legend(loc='upper left', frameon=False, fontsize=11)
    save(fig, '02_policy_differences', '실측 4쌍의 기술적 비교. 시작 AP·배경 전력·열 이력 차이를 사후로 제거하지 않음.\n낮은 값이 유리한 방향이지만, 에너지·열 우월성이나 동등성의 통계적 판정은 미완료.')

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 7.2))
    fig.suptitle('동결 모형의 예정 도착 기반 예측을 8세션과 대조했다', fontsize=23, x=.06, ha='left')
    xs = list(range(1, 9))
    labels = [f'{i+1}\n' + ('CPU' if r['policy'].startswith('CPU') else 'PAR') for i, r in enumerate(rows)]
    axes[0].axhline(0, color='#666666', linewidth=1)
    axes[0].scatter(xs, [float(r['energy_signed_error_j']) for r in rows], s=65, color=blue)
    axes[0].set(title='공통 120초 에너지 오차', ylabel='예측 - 관측 (J)', ylim=(-8, 11))
    axes[1].scatter(xs, [float(r['mae_c']) for r in rows], s=65, color=blue, label='MAE')
    axes[1].scatter(xs, [float(r['max_absolute_error_c']) for r in rows], s=65, marker='x', color=orange, label='최대 절대오차')
    axes[1].set(title='AP 경로 오차', ylabel='오차 (°C)', ylim=(0, 1.5))
    axes[1].legend(frameon=False, loc='upper left', fontsize=11)
    for ax in axes:
        ax.set_xticks(xs, labels)
        ax.tick_params(axis='x', labelsize=11)
        ax.grid(axis='y', alpha=.2)
    save(fig, '03_prediction_errors', 'B: 예정 도착·동결 처리시간 + 부하 전 AP 이력/전력. 이후 실측 전류·AP는 예측 입력에 사용하지 않음.\nAP 평가는 common 35초 이후~냉각 종료의 유효 관측점. 보편 오차 한도·정확도 PASS가 아님.')

    table = HERE / 'session_table.csv'
    fields = ['index', 'pair', 'policy', 'actual_deadline_met', 'planned', 'actual_urgent_p95_ms',
              'common_start_ap_c', 'observed_120s_j', 'observed_peak_ap_c', 'energy_signed_error_j',
              'mae_c', 'max_absolute_error_c', 'overlap_s', 'ap_window_start_s', 'ap_window_end_s', 'ap_samples']
    with table.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in rows)
    artifacts.append(table)
    for name, expected in PINS.items():
        assert sha(SOURCE / name) == expected
    verification = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'base_head': '056993e2a202df731925fab3ffcd7f59f6811e25',
        'working_tree': 'presentation-only additions and navigation/status edits',
        'command': 'python -B docs/results/final_presentation_01/build_figures.py',
        'source_sha256': PINS, 'generator_sha256': sha(Path(__file__)),
        'artifacts_sha256': {p.name: sha(p) for p in artifacts},
        'checks': ['8 unique forecast sessions', '192/192 deadlines per session',
                   '4 pair deltas independently recomputed', 'strict false and accuracy null retained',
                   'source and frozen-model bytes unchanged'],
        'new_simulations': 0, 'new_fits': 0, 'device_commands': 0,
    }
    (HERE / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('8 sessions, 4 pairs verified; 3 PNG + 3 SVG + table generated; device commands 0')


if __name__ == '__main__':
    main()
