"""Offline plots of declared units; deliberately no energy or fitted multiplier."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


def export(reference, out):
    out.mkdir(parents=True, exist_ok=False)
    with reference.open(encoding='utf-8-sig', newline='') as f:rows=list(csv.DictReader(f))
    assert len({r['session_id'] for r in rows})==1
    ts=[int(r['read_end_ns']) for r in rows]
    seconds=[(t-ts[0])/1e9 for t in ts]
    current=[int(r['current_raw']) for r in rows]
    counter=[int(r['charge_counter_raw']) for r in rows]
    cumulative=[0.0]
    for i in range(1,len(rows)):
        cumulative.append(cumulative[-1]-(current[i-1]+current[i])/2*(seconds[i]-seconds[i-1])/3600)
    drops=[counter[0]-q for q in counter]
    plt.rcParams['font.family']=FontProperties(fname='C:/Windows/Fonts/malgun.ttf').get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    axes[0].plot(seconds,cumulative,color='#1677a5');axes[0].set_title('전류 × 시간 ÷ 3,600')
    axes[1].step(seconds,drops,where='post',color='#ba4d36');axes[1].set_title('전하량 원값의 감소')
    for ax in axes:
        ax.set_xlabel('같은 시작 표본부터 시간 (초)');ax.set_ylabel('API 명시 단위로 해석한 전하량 (µAh)')
        ax.grid(alpha=.2)
    fig.suptitle(f'같은 구간·같은 단위: {cumulative[-1]:.2f} 대 {drops[-1]:,.0f} µAh')
    fig.text(.5,.015,'두 세로축 범위가 다릅니다. 약 1,210배 차이는 보정계수가 아니며, 어느 센서도 독립 기준으로 검증되지 않았습니다.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.04,1,.95))
    for suffix in ['png','svg']:fig.savefig(out/('01_같은구간_단위환산_불일치.'+suffix),dpi=160)
    plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('reference',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();export(a.reference,a.output)
