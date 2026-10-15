"""Offline supplement: exact C252 pair timeline and AP readout, no device access."""
import argparse
import csv
from pathlib import Path


def supplement(directory: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    font = FontProperties(fname=str(Path('C:/Windows/Fonts/malgun.ttf')))
    plt.rcParams['font.family'] = font.get_name()
    plt.rcParams['axes.unicode_minus'] = False

    def rows(name):
        with (directory / (name + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(directory / (name + '.png'), dpi=160)
        plt.close(fig)

    sessions = rows('sessions')
    if {s['arm'] for s in sessions} != {'CPU', 'GPU'}:
        return
    # Representative choice fixed independently of observed performance:
    # earliest16 scheduled requests in each arm, never fastest/slowest examples.
    timeline = rows('timeline')
    fig, ax = plt.subplots(figsize=(12, 4))
    for lane, arm in enumerate(['GPU', 'CPU']):
        selected = sorted((r for r in timeline if r['arm'] == arm), key=lambda r: float(r['dispatch_s']))[:16]
        for r in selected:
            start, end = float(r['dispatch_s']), float(r['available_s'])
            ax.broken_barh([(start, end - start)], (lane - .25, .5), facecolors=['#3876b7' if arm == 'GPU' else '#dd9141'])
    ax.set_yticks([0, 1], ['분류 GPU', '분류 CPU'])
    ax.set_xlabel('공통 시작부터 시간 (초)')
    ax.set_title('각 조건의 첫16건: 배정부터 실제 자원 반환까지')
    save(fig, '03_같은_분류요청_실행시간표')

    ap = rows('reported_AP')
    fig, ax = plt.subplots(figsize=(12, 4))
    for arm in ['GPU', 'CPU']:
        selected = [r for r in ap if r['arm'] == arm]
        ax.plot([float(r['read_midpoint_s']) for r in selected], [float(r['reported_AP_c']) for r in selected], label='분류 ' + arm)
    ax.axvspan(35, 180, alpha=.1, color='grey', label='공통 AP 평가창 35~180초')
    ax.set_xlim(0, 210)
    ax.set_xlabel('공통 시작부터 시간 (초)')
    ax.set_ylabel('HAL AP 읽기값 (℃)')
    ax.set_title('동일 분류252건의 AP 읽기 경로 · 대응쌍1개')
    ax.legend()
    save(fig, '04_같은_분류요청_AP경로')
    html = directory / 'index.html'
    page = html.read_text(encoding='utf-8')
    for name in ['03_같은_분류요청_실행시간표', '04_같은_분류요청_AP경로']:
        page += f'<img src="{name}.png" alt="{name}">'
    html.write_text(page, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    supplement(parser.parse_args().directory)
