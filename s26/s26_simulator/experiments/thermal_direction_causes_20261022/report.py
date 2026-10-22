"""All-candidate temperature/direction/steady report, including cause evidence and uncertainty."""
from engine import *
import csv,datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import markdown
O=H/'artifacts/G001';F=H/'figures';F.mkdir(exist_ok=False);sys.stdout.reconfigure(encoding='utf-8')
r=read(O/'COMPARISON.json');a=read(O/'AUDIT.json');d=read(H/'DIAGNOSIS.json');b=read(O/'PAIRED_DIAGNOSTICS.json');protocol=read(H/'PROTOCOL.json')
KINDS=['BASELINE','HISTGB_RESIDUAL','TREND_BALANCED','MARGIN_BALANCED','MARGIN_STEADY_GUARD'];LABELS=['원모형','온도값 보완','직전 균형 후보','방향 경계 후보','정체 보호 후보'];COLORS=['#94a3b8','#64748b','#087f8c','#d99230','#8d59bb'];ref='TREND_BALANCED';primary='MARGIN_STEADY_GUARD'
def pt(k,cat='ALL'):return next(v for v in r['point_summary'] if v['candidate']==k and v['category']==cat)
def wm(k,cl,cat='ALL'):return next(v for v in r['summary'] if v['candidate']==k and v['category']==cat and v['direction']==cl)['session_macro']
def table(head,rows):return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(str(x) for x in v)+' |' for v in rows)+'\n'
def write(p,s):
    with p.open('x',encoding='utf-8') as f:f.write(s)
def figure(fig,name):fig.savefig(F/(name+'.png'),dpi=160,bbox_inches='tight');fig.savefig(F/(name+'.svg'),bbox_inches='tight');plt.close(fig)
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,4,figsize=(16,4.4))
for ax,title,fn in zip(axes,['전체 온도값','상승 구간','하강 구간','장시간 t≥256초'],[lambda k:pt(k)['MAE_C'],lambda k:wm(k,'RISE')['MAE_C'],lambda k:wm(k,'FALL')['MAE_C'],lambda k:pt(k,'LATE_GE256')['MAE_C']]):
    vals=[fn(k) for k in KINDS];bars=ax.bar(range(5),vals,color=COLORS,width=.7);ax.set_ylim(0,max(vals)*1.25);ax.set_xticks(range(5),LABELS,rotation=30,ha='right');ax.set_title(title);ax.set_ylabel('MAE (℃) ↓');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+.02,f'{v:.3f}',ha='center',fontsize=8)
fig.suptitle('기존 원모형·앞선 보완·새 두 후보: 온도오차 보존 비교',fontsize=15);fig.tight_layout();figure(fig,'01_temperature_retention')
fig,axes=plt.subplots(1,3,figsize=(15,4.6))
for ax,cl,title in zip(axes,['RISE','FALL','STEADY'],['장시간 상승','장시간 하강','장시간 정체']):
    vals=[wm(k,cl,'LATE_GE256')['direction_percent'] for k in KINDS];bars=ax.bar(range(5),vals,color=COLORS,width=.7);ax.set_ylim(0,105);ax.set_xticks(range(5),LABELS,rotation=30,ha='right');ax.set_title(title);ax.set_ylabel('방향 정확도 (%) ↑');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    for bar,v in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,v+1.4,f'{v:.1f}',ha='center',fontsize=9)
fig.suptitle('방향 정확도와 정체 보호: 같은 10초 ±0.2℃ 평가',fontsize=15);fig.tight_layout();figure(fig,'02_direction_and_steady')
prev={z['id']:z for z in read(T/'artifacts/G001/OOF_ROWS.json.gz') if z['candidate']==ref};fresh=read(O/'OOF_ROWS.json.gz');by={k:{z['id']:z for z in fresh if z['candidate']==k} for k in KINDS[3:]};selection=read(N/'artifacts/G001/TRACE_SELECTION.json');fig,axes=plt.subplots(3,2,figsize=(14,11.8))
for ax,uid,title in zip(axes.flat,selection['ids'],selection['rules']):
    z=prev[uid];t=np.array(z['times']);ax.plot(t,z['observed'],color='#202529',lw=1.4,label='실측');ax.plot(t,z['predicted'],color='#087f8c',lw=1.5,label='직전 균형')
    for k,c,label in [('MARGIN_BALANCED','#d99230','방향 경계'),('MARGIN_STEADY_GUARD','#8d59bb','정체 보호')]:ax.plot(t,by[k][uid]['predicted'],color=c,lw=1.2,alpha=.85,label=label)
    if t[-1]>=256:ax.axvspan(256,t[-1],color='#cbd5e1',alpha=.15)
    ax.set_title(title+'\n'+uid,fontsize=9);ax.set_xlabel('실제 경과 시간 (초)');ax.set_ylabel('AP 온도 (℃)');ax.grid(alpha=.2)
axes[0,0].legend(frameon=False,ncol=2,fontsize=8);fig.suptitle('같은 6개 시계열을 유지한 비교',fontsize=15);fig.tight_layout(h_pad=2);figure(fig,'03_same_traces')
goals={v['candidate']:v for v in r['comparisons']};passing=[k for k in KINDS[3:] if goals[k]['joint_goal_met']]
recommend=primary if primary in passing else passing[0] if passing else ref
verdict='사전 보존 조건 안에서 장시간 상승·하강을 동시에 개선한 후보가 있다.' if passing else '새 두 후보는 사전 온도·정체 보존 조건과 장시간 양방향 개선을 모두 만족하지 못했다.'
save(O/'CONCLUSION.json',dict(verdict=verdict,recommendation_for_review_only=recommend,primary=primary,primary_metrics=dict(overall=pt(primary)['MAE_C'],late=pt(primary,'LATE_GE256')['MAE_C'],late_rise_direction=wm(primary,'RISE','LATE_GE256')['direction_percent'],late_fall_direction=wm(primary,'FALL','LATE_GE256')['direction_percent'],late_steady_direction=wm(primary,'STEADY','LATE_GE256')['direction_percent']),passing_candidates=passing,goals=r['comparisons'],adopted=False))
with (O/'PAIRED_SESSIONS.csv').open(encoding='utf-8-sig',newline='') as f:sessions=list(csv.DictReader(f))
group_details=[]
for group in sorted({z['group'] for z in sessions if z.get('late_MAE')}):
    item={'group':group}
    for k in KINDS[2:]:
        for metric in ['late_MAE','LATE_RISE_direction','LATE_FALL_direction','LATE_STEADY_direction']:
            zz=[float(z[metric]) for z in sessions if z['group']==group and z['candidate']==k and z.get(metric)];item[k+'_'+metric]=float(np.mean(zz)) if zz else None
    group_details.append(item)
save(O/'GROUP_DETAILS.json',group_details)
def fmt(v):return '해당 없음' if v is None else f'{v:.2f}'
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds')
parts=['# S26 장시간 방향 저정확도 원인과 정체 보호 보완','',f'작성(KST): {now} · 기존 정책/모델/앞선 후보 모두 보존 · 개발 비교 · 새 후보 미채택','',
'## 1. 판정','',f'**{verdict}** 검토용 추천은 `{recommend}`이며 자동 채택은 하지 않았다. 사전 주후보는 정체 보호 후보다.','',
f"주후보 전체 MAE는 {pt(ref)['MAE_C']:.3f}→{pt(primary)['MAE_C']:.3f}℃, 장시간 MAE는 {pt(ref,'LATE_GE256')['MAE_C']:.3f}→{pt(primary,'LATE_GE256')['MAE_C']:.3f}℃다. 장시간 방향은 상승 {wm(ref,'RISE','LATE_GE256')['direction_percent']:.2f}→{wm(primary,'RISE','LATE_GE256')['direction_percent']:.2f}%, 하강 {wm(ref,'FALL','LATE_GE256')['direction_percent']:.2f}→{wm(primary,'FALL','LATE_GE256')['direction_percent']:.2f}%, 정체 {wm(ref,'STEADY','LATE_GE256')['direction_percent']:.2f}→{wm(primary,'STEADY','LATE_GE256')['direction_percent']:.2f}%다.",'',
'## 2. 왜 장시간 방향이 낮았나: 확인한 사실과 가설','',
table(['확인한 사실','의미와 판정 범위'],[['전체 AP값은 100% 0.1℃ 격자, 장시간 연속 관측의 약 54.6%는 같은 값','작은 변화의 10초 방향 판정이 보고값 해상도·반복 구간에 민감하다. 반복만으로 센서 캐시 오류를 확정하지 않는다.'],['장시간 관측 간격 세션 중앙값 약 3.25초, 같은 온도 유지 구간 중앙 약 6.66초','연속 온도 곡선의 작은 기울기와 계단형 보고값의 10초 변화가 다를 수 있다.'],['창을 ±2초 이동하면 상승 약 29.25%, 하강 약 23.55%, 정체 약 10.96%의 판정이 바뀜','판정 민감성을 확인했다. 원 판정 기준·분모를 완화하거나 바꾸지 않는다.'],['창 전체에 기록된 활동이 없는 장시간 구간: 상승 약 42.76%, 하강 약 62.22%(세션평균)','활동 채널만으로 모든 보고 온도 변화를 설명하기 어렵다. 실제 완전 유휴나 특정 배경부하를 입증한 값은 아니다. 초기 DIAGNOSIS의 하강63.27%는 창 중간시점 기준이며 전체창 검산은 ACTIVITY_COVERAGE_CHECK에 보존했다.'],['해당 상승/하강 창 안의 실측 전력 변화와 AP변화에 연관이 있음','해당 세션들의 조건부 상관 평균은 약 0.41/0.78이다. 미래 구간의 실제 전력은 모델 입력으로 쓸 수 없고 인과 관계도 확정할 수 없다.'],['직전 10초 실측 방향을 다음 10초에 유지하는 관측기 진단: 상승 7.55%, 하강 27.34%','직전 추세를 그대로 이어도 낮다. 이는 후속 실측 AP를 사용하는 다른 정보 조건의 진단이며 자유 예측 대조군을 대체하지 않는다.']]),
'이전 모형의 제곱오차 학습은 비슷한 입력에서 상승·하강이 섞이면 작은 평균 변화량을 내는 경향이 있다. 실제로 직전 온도값 보완 후보는 장시간 상승 177창 중 167창을 거의 정체로 예측했다. **손실함수의 평균화, 현재 특징이 포착하지 못한 상태, 보고값의 판정 민감성이 겹친다는 가설**이다. 각 원인의 독립 기여나 열 조절/DVFS를 인과적으로 식별한 것은 아니다.','',
'## 3. 새로 바꾼 부분','',
'현재 TREND_BALANCED의 전력·열·HGB·추가 트리를 모두 동결했다. 새 보완만 별도 학습했다. 초기 맥락만으로 포착하지 못한 열 이력을 보충하기 위해, 시작 전에 실제 이용 가능했던 AP/SKIN/BAT 관측으로 기울기·범위·표준편차·반복 정도 등 12특징을 추가했다. 기존 47특징 + 동결된 현재 온도값 + 12이력 = 60특징이다.','',
'이력은 관측의 `available_upper_s ≤ anchor`인 값만 사용한다. 미래 실측 AP/SKIN/BAT/전력을 바꿔도 초기 특징이 바뀌지 않는 사전 검사를 통과했다. 이력이 부족한 기울기는 0으로 처리하며 유효 관측 개수를 별도 특징으로 포함한다. 반복 온도 유지시간은 시작 전 관측 범위에서 확인된 값이며 실제 전체 유지시간을 안다고 가정하지 않는다.','',
'```text\nT_new(t) = T_current(t) + (1−exp(−(t−anchor)/10)) × Σ tree_m(x60(t))\nL = MSE_temperature +4×MSE_to_current\n    +(.25×all+.5×late)×MSE_true_10s_delta\n    +direction_margin_loss\n상승 목표: ΔT≥+0.22℃ / 하강: ΔT≤−0.22℃\n정체 보호: |ΔT|≤0.16℃\n```','',
'0.22/0.16℃는 학습 손실의 여유 구간이다. 평가의 10초 ±0.2℃ 기준을 바꾼 것이 아니다. 목표 밖 오차에 제곱 hinge 손실을 주고, 정체 보호 후보는 정체 손실을 8배 가중한다. 임의 주기파나 온도 clip은 사용하지 않는다. 각 트리의 잎 값은 활성 손실을 연결한 이차식으로 갱신하며, 고정 반감 line search로 실제 손실이 감소하는지 검사한다. 이는 적합 내부 최적화이며 실패 적합 재실행이 아니다.','',
table(['새 후보','전체/장시간 hinge 가중치','정체 가중치','역할'],[['MARGIN_BALANCED','1 / 8','1','방향 경계 후보'],['MARGIN_STEADY_GUARD','1 / 8','8','사전 주후보, 정체 보호']]),
'두 후보 모두 80단계, 학습률 0.1, 잎 최대 15개, 깊이 5, 잎 최소 50표본, 분할당 특징 16개, 고정 seed 규칙을 사용한다. 손실과 초기 특징을 함께 바꿨으므로 개선이 생겨도 어느 한 요소만의 독립 기여로 표현하지 않는다.','',
'## 4. 같은 자료·같은 평가와 사전 기준','',
'AP 208세션/25,975점, 27개 제외 그룹과 같은 비중첩 10초 5,879창이다. 전체 상승 892창/201세션, 하강 1,601창/206세션, 정체 3,386창/208세션이다. 장시간 점은 t≥256초의 37세션/7,260점이고, 장시간 창은 시작시각 ≥256초(실제 260초 이상)다. 상승 177창/36세션, 하강 382창/34세션, 정체 1,400창/37세션이다.','',
'각 제외 그룹 G의 전체 동결 모델 사슬과 새 보완 모두 G를 학습에서 제외했다. 나머지 학습 세션의 특징도 같은 G 사슬로 계산했다. 원시 정답·관측시각·보간·제외 규칙을 유지했다. 실제 활동 일정을 공급하는 조건부 개발 평가이며, 새 독립 확인이나 실제 S26 정책 성능 검증이 아니다.','',
'이번 사용자 요청이 정체 보존을 강조해, 적합 전에 **현재 후보 대비 전체·상승·하강·장시간 MAE 각각 +3% 이내, 전체·장시간 정체 방향 −0.5%p 이내, 전체 상승·하강 −1%p 이내**를 고정했다. 그 안에서 장시간 상승·하강이 모두 증가하는지 본다. 이전 작업의 각각 +5%p 목표 미달 기록은 보존하며, 새 후보도 +5%p 충족 여부를 별도로 공개한다.','',
'## 5. 온도값 오차 비교','',
table(['모형','전체 MAE ℃','상승 MAE ℃','하강 MAE ℃','장시간 MAE ℃'],[[LABELS[i],f"{pt(k)['MAE_C']:.3f}",f"{wm(k,'RISE')['MAE_C']:.3f}",f"{wm(k,'FALL')['MAE_C']:.3f}",f"{pt(k,'LATE_GE256')['MAE_C']:.3f}"] for i,k in enumerate(KINDS)]),
'전체/장시간 MAE는 세션 내 관측점 평균 후 세션균등 평균이다. 방향별 MAE는 유효창 오차를 시간적분한 세션평균으로 집계하므로 분모가 다르다.','',
'![온도오차 보존](figures/01_temperature_retention.png)','',
'## 6. 상승·하강과 정체 방향 정확도','',
table(['모형','전체 상승 %','전체 하강 %','전체 정체 %','장시간 상승 %','장시간 하강 %','장시간 정체 %'],[[LABELS[i]]+[f"{wm(k,cl,cat)['direction_percent']:.2f}" for cat,cl in [('ALL','RISE'),('ALL','FALL'),('ALL','STEADY'),('LATE_GE256','RISE'),('LATE_GE256','FALL'),('LATE_GE256','STEADY')]] for i,k in enumerate(KINDS)]),
'![방향과 정체 정확도](figures/02_direction_and_steady.png)','',
table(['후보','온도 유지','전체 정체 보호','장시간 정체 보호','양방향 증가','동시 조건','양방향 +5%p'],[[k,'PASS' if goals[k]['checks']['temperature_retention'] else 'FAIL','PASS' if goals[k]['checks']['steady_direction_drop_le0p5pp'] else 'FAIL','PASS' if goals[k]['checks']['late_steady_drop_le0p5pp'] else 'FAIL','PASS' if all(v>0 for v in goals[k]['late_direction_gain_pp'].values()) else 'FAIL','PASS' if goals[k]['joint_goal_met'] else 'FAIL','PASS' if goals[k]['stronger_ge5pp_each'] else 'FAIL'] for k in KINDS[3:]]),
'## 7. 그룹별 변동과 변화량 오차','',
table(['제외 그룹','직전 상승 %','보호 후보 상승 %','직전 하강 %','보호 후보 하강 %','직전 정체 %','보호 후보 정체 %'],[[v['group']]+[fmt(v[k+'_'+metric]) for metric in ['LATE_RISE_direction','LATE_FALL_direction','LATE_STEADY_direction'] for k in [ref,primary]] for v in group_details]),
table(['모형','장시간 상승 ΔMAE ℃/10초','장시간 하강 ΔMAE ℃/10초','장시간 정체 ΔMAE ℃/10초'],[[LABELS[i]]+[f"{wm(k,cl,'LATE_GE256')['delta_MAE_C']:.3f}" for cl in ['RISE','FALL','STEADY']] for i,k in enumerate(KINDS)]),
table(['후보/지표','세션/그룹','새−직전','기술적 95% 구간','개선/악화/동률'],[[v['candidate']+' / '+v['metric'],f"{v['sessions']}/{v['groups']}",f"{v['new_minus_previous']:.3f}",f"[{v['descriptive_95'][0]:.3f}, {v['descriptive_95'][1]:.3f}]",f"{v['improved']}/{v['worse']}/{v['equal']}"] for v in b['statistics'] if v['metric'] in ['overall_MAE','late_MAE','LATE_RISE_direction','LATE_FALL_direction','LATE_STEADY_direction']]),
'MAE 차이는 ℃, 방향 차이는 %p다. 27개 그룹을 4,000회 대응 재표집했다. 장시간은 실제 10개 그룹뿐이며, 이 구간은 기존 개발 자료의 기술적 변동성 설명이다. OOF 학습 집합 중복과 후보 개발 이력을 고려한 독립 사후선택 신뢰구간은 아니다.','',
'자료군별 주후보 전체 MAE(직전→새): '+', '.join(f"{cat} {pt(ref,cat)['MAE_C']:.3f}→{pt(primary,cat)['MAE_C']:.3f}℃" for cat in ['OLD','M8','R21'])+'. OLD 131세션, M8 77세션이며 R21 19세션은 M8의 부분집합이다.','',
'## 8. 판정 기준 민감도와 같은 시계열','',
table(['창/판정','모형','장시간 상승 %','장시간 하강 %','장시간 정체 %'],[[f'{width}초 ±{threshold}℃',LABELS[KINDS.index(k)]]+[f"{next(v for v in r['sensitivity'] if v['candidate']==k and v['category']=='LATE' and v['window_s']==width and v['threshold_C']==threshold and v['direction']==cl)['session_macro']['direction_percent']:.2f}" for cl in ['RISE','FALL','STEADY']] for width,threshold in [(10,.1),(10,.5),(20,.4)] for k in KINDS[2:]]),
'앞선 두 보고서와 같은 6개 세션을 표시했다. 장시간 상승·하강·기존 오차 큰 과거 사례, M8/R21 중앙 사례, 초기 온도 보완의 최악 악화 사례다. 새 결과를 본 뒤 좋은 사례만 고르지 않았다.','',
'![같은 시계열 비교](figures/03_same_traces.png)','',
'## 9. 보존·실행·검산과 한계','',
f"신규 열 보완 모델 {r['fit']['fit_START']} START/{r['fit']['fit_COMPLETE']} COMPLETE/FAIL {r['fit']['fit_FAIL']}, 각 80단계 트리다. 적합 시간은 {r['fit']['elapsed_s']:.1f}초다. 기존 완료 모델 재적합, 전력 적합, BC/RL 학습, 정책 환경 실행, 실기기 측정은 모두 0이다.",'',
f"독립 JavaScript가 초기 이력을 별도 추출하고 전력/열/활동 상태와 3단계 트리를 순회해 새 예측 {a['prediction_points']:,}점 전체를 검산했다. 최대 차이 {a['max_JS_python_error_C']:.3g}℃다. 새 방향 손실의 기울기도 유한차분 검사로 확인했다. 고유 적합 원장·모델 SHA·그룹 배제·기존 정책/체크포인트/보고서를 보존했다.",'',
'첫 독립 검산에서는 일정한 BAT 이력의 기울기가 Python에서는 0, JavaScript에서는 약 −1.34×10⁻³⁰으로 계산됐다. 그 차이가 0 부근 트리 분기를 바꿔 방향 경계 대조 후보 한 세션의 90점에서 최대 0.01025℃ 차이를 만들었다. 주후보는 영향을 받지 않았다. 독립 구현에서 상수 이력의 기울기를 정확히 0으로 처리한 V2 검산은 전체 일치했다. 학습 모델·Python 평가·지표를 수정하거나 재적합하지 않았고 첫 실패 출력도 보존했다. 다른 실행환경의 0 부근 특징 분기 안정성은 배포 전에 추가 확인할 항목이다.','',
'표의 원인은 확인한 관측 패턴과 보완 가설을 구분해야 한다. 배경 앱·DVFS·보고 센서의 실제 갱신 지연·열 조절 동작은 이번 상관 분석만으로 식별하지 못했다. 새 경험적 잔차의 수동성/단조성이나 실제 활동 일정 예측 오차도 검증하지 않았다. 기존 전력·열 물리 정확도 gate FAIL, CPU3/모바일 계산 비용 미검증을 유지한다. 기존 정책의 FIFO/EDF/RR 비교 수치도 바꾸지 않았다.','',
'## 10. 파일과 재개 안내','',
'- [사전 진단 결과](DIAGNOSIS.json)\n- [장시간 구간 진단 CSV](LATE_WINDOW_DIAGNOSTICS.csv)\n- [새 후보 사전 설계](PROTOCOL.json)\n- [초기 이력과 이용 가능 시각](INITIAL_HISTORY.json)\n- [전체 비교 JSON](artifacts/G001/COMPARISON.json)\n- [결론과 판정](artifacts/G001/CONCLUSION.json)\n- [세션별 대응 CSV](artifacts/G001/PAIRED_SESSIONS.csv)\n- [그룹별 장시간 값](artifacts/G001/GROUP_DETAILS.json)\n- [독립 검산](artifacts/G001/AUDIT.json)\n- [원장](artifacts/G001/FIT_RECEIPTS.jsonl)\n- [직전 균형 후보 보고서](../thermal_trend_preservation_20261021/REPORT_KO.html)\n- [정체 보호 FULL 모델](artifacts/G001/models/FULL__MARGIN_STEADY_GUARD.json.gz)','',
'새 후보의 공식 채택이나 배치는 하지 않았다. 후속 실측·정책 학습·자동화는 자동 시작하지 않는다.']
md='\n'.join(parts);write(H/'REPORT_KO.md',md);css='''body{margin:0;background:#f1f5f9;color:#17212b;font-family:"Malgun Gothic",sans-serif;line-height:1.75}main{max-width:1200px;margin:28px auto;padding:36px 44px;background:white;border-radius:14px}h1{font-size:30px;line-height:1.4}h2{font-size:23px;margin-top:42px;border-bottom:2px solid #dae5eb;padding-bottom:8px}table{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0;line-height:1.6}td,th{padding:9px;border:1px solid #d6e0e6;text-align:left}th{background:#e9f3f4}tr:nth-child(even){background:#f8fafc}img{max-width:100%;height:auto}a,strong{color:#087480}pre{padding:18px;background:#0f2533;color:#edffff;border-radius:7px;overflow:auto}code{font-size:12px;overflow-wrap:anywhere}@media(max-width:800px){main{margin:0;padding:20px 14px}table{display:block;overflow-x:auto}}''';write(H/'REPORT_KO.html','<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>S26 방향 원인과 정체 보호</title><style>'+css+'</style></head><body><main>'+markdown.markdown(md,extensions=['tables','fenced_code'])+'</main></body></html>');print(json.dumps(dict(verdict=verdict,recommend=recommend),ensure_ascii=False))
