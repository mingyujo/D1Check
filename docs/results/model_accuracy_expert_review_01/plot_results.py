"""Plot saved diagnostic arithmetic only; no fits, simulator or device commands."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parent


def rows(name):
    with (ROOT/'diagnostics_02'/name).open(encoding='utf8',newline='') as f:
        return list(csv.DictReader(f))


def plot(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':11})
    energy=rows('energy_component_diagnostics.csv')
    ap=rows('AP_component_diagnostics.csv')
    phases=['reference120','registered600','registered_recovery_covered_prefix','registered_and_recovery_covered_prefix']
    labels=['참고120초','등록600초','덮인 회복','등록+회복 prefix']
    selected=[next(r for r in energy if r['session']=='confirmation_1_LOAD_A_LONG' and r['phase']==p) for p in phases]
    series=[('원식',[float(r['frozen_j'])-float(r['observed_j']) for r in selected]),
            ('고정 p4 / δ 제거',[float(r['no_offset_signed_j']) for r in selected]),
            ('최근20초 상수 초기화',[float(r['pre20_signed_j']) for r in selected])]
    fig,axes=plt.subplots(1,2,figsize=(14,5),gridspec_kw={'width_ratios':[2,1]})
    x=np.arange(len(phases));width=.24
    for i,(name,values) in enumerate(series):axes[0].bar(x+(i-1)*width,values,width,label=name)
    axes[0].axhline(0,color='black',linewidth=.7);axes[0].set_xticks(x,labels)
    axes[0].set_ylabel('예측 - 관측 에너지 (J)');axes[0].set_title('LOAD: 짧은 창의 성공이 긴 창의 성공은 아님')
    axes[0].legend(fontsize=9)
    variants=['FROZEN','fixed_fast_without_slow','LOAD_SLOW_full']
    values=[float(next(r for r in ap if r['session']=='confirmation_1_LOAD_A_LONG' and r['phase']=='registered600' and r['variant']==v)['mae_c']) for v in variants]
    axes[1].bar(['원식','고정 빠른 항','빠른+느린 항'],values,color=['#557a95','#e2a03f','#39806a'])
    axes[1].set_ylabel('AP MAE (°C)');axes[1].set_title('같은 등록600초 AP 성분 분해')
    for i,v in enumerate(values):axes[1].text(i,v+.008,f'{v:.3f}',ha='center')
    fig.suptitle('기존 자료 사후 진단 · 새 fit0 · 기본/RL/strict 교체0')
    fig.tight_layout();fig.savefig(out/'component_counterexamples.png',dpi=140);plt.close(fig)
    pair=rows('paired_difference_diagnostics.csv');x=np.arange(len(pair));width=.2
    fig,ax=plt.subplots(figsize=(11,5))
    for i,(key,name) in enumerate([('observed_delta_j','관측'),('original_predicted_delta_j','원식'),('fixed_p4_no_offset_delta_j','δ 제거 고정 p4'),('pre20_diagnostic_delta_j','최근20초 진단')]):
        ax.bar(x+(i-1.5)*width,[float(r[key]) for r in pair],width,label=name)
    ax.axhline(0,color='black',linewidth=.8);ax.set_xticks(x,['짝0 (CPU→PAR)','짝1 (PAR→CPU)','짝2 (PAR→CPU)','짝3 (CPU→PAR)'])
    ax.set_ylabel('PAR - CPU 긴급우선 에너지 (J)');ax.set_title('기존 지속4짝 / 공통120초 · 별도 세션의 사후 비교')
    ax.legend(fontsize=9);fig.tight_layout();fig.savefig(out/'paired_differences.png',dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();plot(a.output)
