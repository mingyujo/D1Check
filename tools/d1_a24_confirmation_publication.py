"""Publish a COPY of multi-visit CONFIRM exports with unchanged AP eligibility."""
import argparse
import csv
import html
import json
import math
from pathlib import Path
import shutil
from d1_a24_laptop_validator import sha256
from d1_a24_measurement_report import save_csv
from d1_a24_partial_confirm_publication import screen


def export(source,out):
    if out.exists():raise FileExistsError('new publication output required')
    def read(name):
        with (source/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    raw_sessions=read('sessions.csv')
    if not raw_sessions or len(raw_sessions)>40 or any(r['stage']!='CONFIRM' for r in raw_sessions):
        raise ValueError('completed CONFIRM sessions only')
    if len({r['session_id'] for r in raw_sessions})!=len(raw_sessions):raise ValueError('duplicate sessions')
    sessions,pairs,intervals=screen(raw_sessions,read('paired.csv'),read('paired_intervals.csv'))
    out.mkdir(parents=True,exist_ok=False)
    allowed=['attempts.csv','requests.csv','reported_AP.csv','battery_API_unvalidated.csv',
             'timeline.csv','run_context.csv','provenance.json']
    for name in allowed:shutil.copyfile(source/name,out/name)
    for p in source.glob('*.analysis.json'):shutil.copyfile(p,out/p.name)
    for name,rows in [('sessions.csv',sessions),('paired.csv',pairs),('paired_intervals.csv',intervals)]:save_csv(out/name,rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
    names={'BASE':'직렬','PAIR_G':'병행','ORDER':'EDD','WAIT200':'대기','CPU':'CPU','GPU':'GPU'}
    labels=[r['block'].replace('R02CONFIRM','블록')+' '+r['recipe']+' '+names[r['arm']] for r in sessions]
    xs=list(range(len(sessions)));width=max(12,len(sessions)*.7)
    def num(x):return float(x) if x not in (None,'') else np.nan
    def finish(fig,name,note):
        fig.text(.5,.015,note,ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.055,1,.94));fig.savefig(out/(name+'.png'),dpi=150);fig.savefig(out/(name+'.svg'));plt.close(fig)
        p=out/(name+'.svg');p.write_bytes(b'\n'.join(s.rstrip() for s in p.read_bytes().splitlines())+b'\n')
    fig,axes=plt.subplots(2,1,figsize=(width,9),sharex=True)
    for task,offset,color in [('C',-.18,'#407da6'),('D',.18,'#cf8b3c')]:
        axes[0].bar([x+offset for x in xs],[100*num(r[task+'_on_time_rate_all_planned']) for r in sessions],width=.36,color=color,label='분류' if task=='C' else '탐지')
        axes[1].plot(xs,[num(r[task+'_response_P95_ms_service_successes'])/1000 for r in sessions],'o',color=color,label='분류' if task=='C' else '탐지')
    axes[0].set_ylabel('전체 예정 대비 기한 내 완료 (%)');axes[0].set_ylim(0,108);axes[0].legend()
    axes[1].set_ylabel('완료 응답 P95 (초)');axes[1].set_xticks(xs,labels,rotation=65,ha='right')
    fig.suptitle(f'새 확인40 중 회수 완료 {len(sessions)}군: 서비스 결과')
    finish(fig,'01_서비스_결과','미실시·실패는 attempts.csv에 별도 보존합니다. 탐지가 없는 조건은 탐지 지표를0으로 만들지 않습니다.')
    fig,ax=plt.subplots(figsize=(width,6))
    ax.plot(xs,[num(r['primary_AP_mean_c']) for r in sessions],'o',label='적격 창 평균 AP')
    ax.plot(xs,[num(r['primary_AP_observed_peak_c']) for r in sessions],'s',label='적격 창 관측 최고 AP')
    for i,r in enumerate(sessions):
        if not r['AP_comparison_eligible']:ax.text(i,.5,'관측창 부적격',transform=ax.get_xaxis_transform(),ha='center',rotation=90)
    ax.set_xticks(xs,labels,rotation=65,ha='right');ax.set_ylabel('보고된 HAL AP (℃)');ax.legend()
    fig.suptitle('AP 관측 적격성과 기기 보고 온도')
    finish(fig,'02_AP_관측','동일한 최대 간격10초 기준. 부적격 군의 최고값을 완전한 관측창의 최고값으로 비교하지 않습니다.')
    timeline=read('timeline.csv');ap=read('reported_AP.csv')
    blocks=sorted({r['block'] for r in sessions if r['recipe']=='M128'})
    representative=next((b for b in blocks if all(any(r['block']==b and r['recipe']=='M128' and r['arm']==a for r in sessions) for a in ['BASE','PAIR_G'])),None)
    if representative:
        fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
        for ax,arm in zip(axes,['BASE','PAIR_G']):
            for r in timeline:
                if (r['block'],r['recipe'],r['arm'])!=(representative,'M128',arm):continue
                lane=0 if r['backend']=='CPU' else 1
                ax.broken_barh([(float(r['dispatch_s']),float(r['available_s'])-float(r['dispatch_s']))],(lane-.3,.6),facecolors='#407da6' if r['task']=='C' else '#cf8b3c')
                ax.plot(float(r['response_s']),lane,'k|',ms=4)
            ax.set_yticks([0,1],['CPU','GPU']);ax.set_title(names[arm]);ax.grid(axis='x',alpha=.2)
        axes[-1].set_xlabel('공통 시작부터 시간 (초)');fig.suptitle('첫 등록 혼합 대응쌍의 실제 실행 시간표')
        finish(fig,'03_실행_시간표','막대: dispatch~실제 lane 반환 / 검은 표식: 응답 완료. 성적 순위로 대표 사례를 고르지 않았습니다.')
        fig,ax=plt.subplots(figsize=(12,5.5))
        for arm in ['BASE','PAIR_G']:
            points=sorted((float(r['read_midpoint_s']),float(r['reported_AP_c'])) for r in ap if (r['block'],r['recipe'],r['arm'])==(representative,'M128',arm))
            x=[];y=[]
            for i,(t,v) in enumerate(points):
                if i and t-points[i-1][0]>10:
                    x.append(np.nan);y.append(np.nan)
                    lo,hi=max(35,points[i-1][0]),min(180,t)
                    if lo<hi:ax.axvspan(lo,hi,alpha=.15,color='#ad553f')
                x.append(t);y.append(v)
            ax.plot(x,y,label=names[arm])
        ax.set_xlim(35,180);ax.set_xlabel('공통 시작부터 시간 (초)');ax.set_ylabel('보고된 HAL AP (℃)');ax.legend()
        fig.suptitle('첫 등록 혼합 대응쌍의 AP 경로')
        finish(fig,'04_AP_시간경로','10초 초과 공백은 연결하지 않습니다. 부분 관측 경로를 보여주는 것이며 부적격 쌍의 열 효과 판정은 아닙니다.')
    eligible=sum(r['AP_comparison_eligible'] for r in sessions)
    completed=sum(int(r['completed']) for r in sessions)
    images=''.join(f'<figure><img src="{html.escape(p.name)}" alt="{html.escape(p.stem)}"></figure>' for p in sorted(out.glob('*.png')))
    table='<table><thead><tr><th>조건</th><th>완료/예정</th><th>분류 기한 내</th><th>탐지 기한 내</th><th>AP 창</th></tr></thead><tbody>'
    for label,r in zip(labels,sessions):
        values=[label,r['completed']+'/'+r['planned'],r['C_on_time']+'/'+r['C_planned'],r['D_on_time']+'/'+r['D_planned'],'적격' if r['AP_comparison_eligible'] else '부적격']
        table+='<tr>'+''.join('<td>'+html.escape(v)+'</td>' for v in values)+'</tr>'
    table+='</tbody></table>'
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A24 확인40 진행 결과</title><style>body{{font:16px sans-serif;max-width:1400px;margin:32px auto;padding:0 18px;line-height:1.6}}img{{max-width:100%}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccd3dc;padding:6px 12px}}.note{{background:#fff3d8;padding:14px}}</style><h1>A24 확인40 진행 결과</h1><p>정상 회수 {len(sessions)}/40군 · 해당 요청 {completed}건 완료 · AP 관측 적격 {eligible}/{len(sessions)}군</p><p class="note">실제 기기 보고값의 검증 범위를 구분합니다. J는 공식 미판정이며, 조건부 에너지 분석은 별도입니다. 미실시·실패를0성능으로 평균내지 않고, AP 부적격 군을 열 비교에서 제외합니다.</p><p><a href="sessions.csv">전체 조건</a> · <a href="attempts.csv">40군 원장</a> · <a href="paired.csv">대응 차이</a> · <a href="paired_intervals.csv">반복 요약</a> · <a href="run_context.csv">시작 상태</a></p>{table}{images}</html>'''
    (out/'index.html').write_text(page,encoding='utf-8')
    proof=dict(status='MULTI_VISIT_CONFIRM_COPY_WITH_AP_MASK',source_code_sha256=sha256(Path(__file__)),
        completed_sessions=len(sessions),AP_eligible_sessions=eligible,completed_requests=completed,
        actual_energy_J=None,raw_or_frozen_contract_modified=False,new_device_commands=0,
        representative_block=representative,representative_rule='first registered complete M128 BASE/PAIR_G pair',
        original_CSV_SHA256={n:sha256(source/n) for n in ['sessions.csv','paired.csv','paired_intervals.csv','run_context.csv']})
    (out/'PUBLICATION_CONTEXT.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();export(args.source,args.output)
