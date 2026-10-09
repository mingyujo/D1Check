"""Plot stored scores only; no simulation or fitting."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', required=True)
    args = parser.parse_args()
    out = Path(args.results)
    with (out / 'retained_errors.csv').open(encoding='utf8') as f:
        rows = list(csv.DictReader(f))
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(3, 1, figsize=(12, 16), constrained_layout=True,
                             gridspec_kw={'height_ratios': [3, 10, 2.5]})
    stages = ('development_loso', 'archive_posthoc', 'independent_long_transfer')
    titles = ('개발 4세션: 저장된 사후 LOSO (fold별 후보)',
              '과거 29세션(도착·이력 대조): 사후 계산 · 새 후보 경로에서는 모두 차단',
              '새 장시간 2조건: 실행 전에 고정된 동일 후보 확인')
    for ax, stage, title in zip(axes, stages, titles):
        group = [r for r in rows if r['evidence_stage'] == stage]
        y = list(range(len(group)))
        ax.barh([i-.18 for i in y], [float(r['frozen_mae_c']) for r in group],
                height=.35, label='기존 동결식', color='#e49b3c')
        ax.barh([i+.18 for i in y], [float(r['load_slow_mae_c']) for r in group],
                height=.35, label='LOAD_SLOW', color='#26856c')
        ax.set_yticks(y, [r['session'] for r in group])
        ax.invert_yaxis()
        ax.set_xlabel('AP 경로 MAE (°C)')
        ax.set_title(title)
        ax.legend()
        ax.grid(axis='x', alpha=.2)
        for tick, row in zip(ax.get_yticklabels(), group):
            if row['worse_than_frozen'] == 'True':
                tick.set_color('#b91c1c')
    fig.suptitle('기존 오차 보존: 개선·악화·적용 범위를 분리\n'
                 '표본 수로 세션을 가중하지 않음 · 정확도 PASS/정책 우월성 없음', fontsize=14)
    fig.savefig(out / 'retained_session_errors.png', dpi=130)
    fig.savefig(out / 'retained_session_errors.svg')
    svg = out / 'retained_session_errors.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf8').splitlines()) + '\n',
                   encoding='utf8', newline='\n')
    plt.close(fig)


if __name__ == '__main__':
    main()
