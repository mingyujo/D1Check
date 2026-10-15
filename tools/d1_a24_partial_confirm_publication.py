"""Screen a COPY of partial confirmation exports by the existing AP coverage rule.

Raw measurements, frozen analysis and original engine exports stay unchanged.
An incomplete observation window cannot enter a thermal policy comparison.
"""
import argparse
import copy
import csv
import json
import math
from pathlib import Path
import shutil
import statistics
from d1_a24_laptop_validator import sha256
from d1_a24_measurement_report import CONTRASTS, save_csv


def screen(sessions,pairs,intervals):
    sessions,pairs,intervals=copy.deepcopy((sessions,pairs,intervals))
    by_key={(r['block'],r['recipe'],r['arm']):r for r in sessions}
    for r in sessions:
        valid=r['thermal_window_status']=='READOUT_WINDOW_COVERED'
        r['AP_comparison_eligible']=valid
        r['primary_AP_mean_c']=r['mean_AP_c'] if valid else None
        r['primary_AP_observed_peak_c']=r['observed_peak_AP_c'] if valid else None
        r['observed_peak_interpretation']='covered window observed samples only' if valid else 'INCOMPLETE_WINDOW_LOWER_BOUND_NOT_COMPARABLE'
    contrasts={label:(recipe,a,b) for recipe,a,b,label in CONTRASTS}
    for r in pairs:
        recipe,a,b=contrasts[r['comparison']]
        rows=[by_key.get((r['block'],recipe,arm)) for arm in [a,b]]
        valid=all(x is not None and x['AP_comparison_eligible'] for x in rows)
        r['thermal_comparison_eligible']=valid
        if not valid:
            for key in ['delta_mean_AP_c','delta_observed_peak_AP_c']:
                r['unscreened_engine_'+key]=r.get(key)
                r[key]=None
    from scipy.stats import t
    for r in intervals:
        key=r['metric']
        if key not in ['delta_mean_AP_c','delta_observed_peak_AP_c']:continue
        values=[float(p[key]) for p in pairs if p['comparison']==r['comparison'] and p['thermal_comparison_eligible'] and p.get(key) not in [None,'']]
        n=len(values);mean=statistics.mean(values) if n else None
        width=float(t.ppf(.975,n-1))*statistics.stdev(values)/math.sqrt(n) if n>=2 else None
        r.update(n_independent_blocks=n,mean=mean,lower95=mean-width if width is not None else None,upper95=mean+width if width is not None else None)
    return sessions,pairs,intervals


def require_first_quartet(sessions):
    assert len(sessions)==4 and len({r['block'] for r in sessions})==1
    assert {r['recipe'] for r in sessions}=={'M128'}
    assert {r['arm'] for r in sessions}=={'BASE','ORDER','PAIR_G','WAIT200'}


def export(source,out):
    assert not out.exists(),'write-once public copy'
    shutil.copytree(source,out)
    def read(name):
        with (source/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    sessions,pairs,intervals=screen(read('sessions.csv'),read('paired.csv'),read('paired_intervals.csv'))
    require_first_quartet(sessions)
    for name,rows in [('sessions.csv',sessions),('paired.csv',pairs),('paired_intervals.csv',intervals)]:save_csv(out/name,rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    import numpy as np
    plt.rcParams['font.family']=FontProperties(fname='C:/Windows/Fonts/malgun.ttf').get_name()
    plt.rcParams['axes.unicode_minus']=False
    names={'BASE':'직렬 기준','ORDER':'납기순 EDD','WAIT200':'200ms 대기','PAIR_G':'병행 허용'}
    labels=[names[r['arm']] for r in sessions];xs=list(range(len(sessions)))
    def numeric(x):return float(x) if x not in [None,''] else np.nan
    def finish(fig,name,note):
        fig.text(.5,.015,note,ha='center',fontsize=10);fig.tight_layout(rect=(0,.05,1,.94))
        fig.savefig(out/(name+'.png'),dpi=160);fig.savefig(out/(name+'.svg'));plt.close(fig)
        p=out/(name+'.svg');p.write_bytes(b'\n'.join(s.rstrip() for s in p.read_bytes().splitlines())+b'\n')
    fig,ax=plt.subplots(figsize=(10,5))
    ax.plot(xs,[numeric(r['primary_AP_mean_c']) for r in sessions],'o',label='적격 관측창 평균')
    ax.plot(xs,[numeric(r['primary_AP_observed_peak_c']) for r in sessions],'s',label='적격 관측창의 관측 최고')
    for i,r in enumerate(sessions):
        if not r['AP_comparison_eligible']:ax.text(i,.5,'관측창 미충족',transform=ax.get_xaxis_transform(),ha='center',rotation=90)
    ax.set_xticks(xs,labels);ax.set_xlim(-.3,len(sessions)-.7);ax.set_ylabel('보고된 HAL AP (℃)');ax.legend();fig.suptitle('직렬 기준의 AP 창 미충족: 열 효과 비교 보류')
    finish(fig,'02_보고된_AP_온도','최대 허용 간격10초는 유지합니다. 미적격 군을0℃나 완전한 최고 온도로 표시하지 않습니다.')
    context=read('run_context.csv');ctx={r['session_id']:r for r in context}
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    initial=[numeric(ctx[r['session_id']]['last_preMAIN_reported_AP_c']) for r in sessions]
    peak=[numeric(r['primary_AP_observed_peak_c']) for r in sessions]
    axes[0].plot(xs,initial,'o',label='MAIN 직전 AP');axes[0].plot(xs,peak,'s',label='적격 창 관측 최고');axes[0].legend()
    axes[1].bar(xs,[p-i for p,i in zip(peak,initial)])
    for ax in axes:ax.set_xticks(xs,labels);ax.set_ylabel('보고된 AP / 차이 (℃)')
    fig.suptitle('시작 상태·AP 창 적격성: 직렬 기준의 열 변화는 미판정')
    finish(fig,'07_시작상태와_보고온도','시작값을 뺀 수치도 인과 보정·표면온도·에너지 절감이 아닙니다. 직렬 기준 최고값은 비교에서 제외했습니다.')
    ap=read('reported_AP.csv');block=sessions[0]['block'];fig,ax=plt.subplots(figsize=(11,5))
    for arm in ['BASE','PAIR_G']:
        points=sorted((float(r['read_midpoint_s']),float(r['reported_AP_c'])) for r in ap if r['block']==block and r['recipe']=='M128' and r['arm']==arm)
        xx=[];yy=[]
        for index,(x,y) in enumerate(points):
            if index and x-points[index-1][0]>10:
                xx.append(np.nan);yy.append(np.nan)
                left,right=max(35,points[index-1][0]),min(180,x)
                if left<right:ax.axvspan(left,right,color='#b44d36',alpha=.12)
            xx.append(x);yy.append(y)
        ax.plot(xx,yy,label=names[arm]+(' · AP 창 미충족' if arm=='BASE' else ''))
    ax.set_xlim(35,180);ax.set_xlabel('공통 시작부터 시간 (초)');ax.set_ylabel('보고된 HAL AP (℃)');ax.legend();fig.suptitle('같은 혼합 요청의 AP 경로 · 관측 공백을 연결하지 않음')
    finish(fig,'04_같은_혼합요청_AP경로','음영은 원래10초 간격 기준을 넘는 미관측 구간입니다. 열 효과 차이를 판정하지 않습니다.')
    html=out/'index.html';s=html.read_text(encoding='utf-8');s=s.replace('<h1>A24 실제 요청 흐름 비교</h1>','<h1>A24 실제 요청 흐름 비교</h1><p><b>새 확인4/40회 회수·512요청 완료,36회 미실시. 직렬 기준 AP 창은12.34초 공백으로 미적격이므로 열 효과 비교 보류. J 미판정.</b></p>');html.write_text(s,encoding='utf-8')
    proof={'status':'PARTIAL_CONFIRM_PUBLICATION_WITH_UNCHANGED_AP_COVERAGE_RULE','script_sha256':sha256(Path(__file__)),'measurement_or_frozen_contract_modified':False,'original_engine_exports_retained':True,'original_CSV_SHA256':{n:sha256(source/n) for n in ['sessions.csv','paired.csv','paired_intervals.csv','run_context.csv']},'completed_sessions':4,'planned_full_confirmation':40,'AP_eligible_sessions':sum(r['AP_comparison_eligible'] for r in sessions),'new_device_commands':0,'thermal_effect_vs_BASE_claim':False}
    (out/'PUBLICATION_CONTEXT.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();export(a.source,a.output)
