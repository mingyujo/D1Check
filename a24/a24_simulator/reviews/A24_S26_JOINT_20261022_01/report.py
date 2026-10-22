"""Saved-only comparison of both preselected scales; always disclose both outcomes."""
import json,gzip,math,csv,statistics,hashlib,collections
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_joint_20261022';O=A/'results/A24_S26_JOINT_20261022_01'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def save(name,obj):
    with (O/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,allow_nan=False,indent=2)
def text(name,s):
    with (O/name).open('x',encoding='utf-8') as f:f.write(s)
def csvout(name,rr):
    with (O/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def mean(v):return statistics.mean(v)
def p95(v):v=sorted(v);return v[math.ceil(.95*len(v))-1]
policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_RISK','BC_NEURAL_URGENT'];names=dict(zip(policies,['FIFO','EDF','RR','교사규칙','롤링+ATC+BC']))
data=read(O/'RESULT.json');rows=data['rows'];selection=read(H/'SELECTION.json');inputs=read(H/'INPUTS.json');js=read(O/'AUDIT_JS.json');py=read(O/'AUDIT_PYTHON.json');assert js['status']==py['status']=='PASS';derived={d['label']:d for d in js['derived']}
def agg(rr):
    assert rr and len({r['policy'] for r in rr})==1
    d={'policy':rr[0]['policy'],'inputs':len(rr),'J':mean(r['metrics']['J'] for r in rr),'J_total':sum(r['metrics']['J'] for r in rr),'AP':mean(r['metrics']['AP'] for r in rr),'peak':max(r['metrics']['peak'] for r in rr),'increment_J':mean(r['metrics']['increment_J'] for r in rr)}
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:d[g+'_'+k]=sum(r['metrics']['service'][g][k] for r in rr)
        d[g+'_on_pct']=100*d[g+'_on']/d[g+'_n'];d[g+'_P95']=mean(r['metrics']['service'][g]['P95'] for r in rr);d[g+'_P95_pooled']=p95([v for r in rr for v in r['metrics']['service'][g]['latencies']])
    d['J_per_request']=d['J_total']/d['ALL_n'];return d
def comp(b,a):
    return {'reference':a['policy'],'ALL_gain_pp':b['ALL_on_pct']-a['ALL_on_pct'],'U_gain_pp':b['U_on_pct']-a['U_on_pct'],'N_gain_pp':b['N_on_pct']-a['N_on_pct'],'energy_saving_pct':100*(1-b['J']/a['J']),'J_reduction':a['J']-b['J'],'AP_reduction_C':a['AP']-b['AP'],'U_P95_increase_s':b['U_P95']-a['U_P95'],'N_P95_increase_s':b['N_P95']-a['N_P95']}
summary=[];combined=[];comparisons=[];perinput=[];harms=[];window=[];allrows=[]
for r in rows:
    c=r['condition'];m=r['metrics'];v={k:c[k] for k in ['setting','n','burst','mix','draw','nominal_load','requests_per_second','supply_s']};v.update(label=r['label'],policy=r['policy'],J=m['J'],AP=m['AP'],increment_J=m['increment_J'])
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete','P95']:v[g+'_'+k]=m['service'][g][k]
        v[g+'_on_pct']=100*v[g+'_on']/v[g+'_n']
    allrows.append(v)
for selected in selection['selected']:
    sid=selected['setting'];rr=[r for r in rows if r['condition']['setting']==sid];assert len(rr)==20;overall=[agg([r for r in rr if r['policy']==p]) for p in policies];mixed=[]
    for mix in [.5,.75]:
        t=[agg([r for r in rr if r['policy']==p and r['condition']['mix']==mix]) for p in policies];mixed.append({'mix':mix,'policies':t,'comparisons':[comp(t[-1],a) for a in t[:-1]]})
    cc=[comp(overall[-1],a) for a in overall[:-1]];joint=all(c['ALL_gain_pp']>1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for c in cc[:3]);mixok=all(c['ALL_gain_pp']>=-1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for m in mixed for c in m['comparisons'][:3]);service=all(m['policies'][-1]['ALL_on_pct']>=95 and m['policies'][-1]['U_on_pct']>=99 and m['policies'][-1]['ALL_missing']==m['policies'][-1]['ALL_incomplete']==0 for m in mixed)
    percase=[]
    for case in sorted({r['case'] for r in rr}):
        qr=[r for r in rr if r['case']==case];b=next(r for r in qr if r['policy']==policies[-1]);ba=agg([b])
        for a in qr:
            if a['policy']==policies[-1]:continue
            c=comp(ba,agg([a]));c.update(setting=sid,case=case,mix=b['condition']['mix'],draw=b['condition']['draw']);perinput.append(c);percase.append(c)
            for k in ['ALL_gain_pp','U_gain_pp','N_gain_pp','energy_saving_pct','AP_reduction_C']:
                if c[k]<-1e-9:harms.append({'setting':sid,'case':case,'reference':a['policy'],'metric':k,'value':c[k]})
            for k in ['U_P95_increase_s','N_P95_increase_s']:
                if c[k]>1e-9:harms.append({'setting':sid,'case':case,'reference':a['policy'],'metric':k,'value':c[k]})
            db=derived[b['label']];dr=derived[a['label']];window.append({'setting':sid,'case':case,'reference':a['policy'],'main_saving_pct':c['energy_saving_pct'],'supply_saving_pct':100*(1-db['supply_J']/dr['supply_J']),'own_completion_saving_pct':100*(1-db['own_completion_J']/dr['own_completion_J']) if db['own_completion_J'] and dr['own_completion_J'] else None,'supply_AP_reduction_C':dr['supply_AP']-db['supply_AP']})
    case0=next(i['case'] for i in inputs['cases'] if i['case']['condition']['setting']==sid);n=case0['n']
    summary.append({'setting':sid,'N':n,'burst':8,'nominal_load':.25,'DEV_selection':selected,'CONF_overall':overall,'CONF_per_mix':mixed,'CONF_comparisons':cc,'joint_aggregate_pass':joint,'mix_nonworse_energy_AP_pass':mixok,'service_quality_gate_pass':service,'all_required_gates_pass':joint and mixok and service,'per_input_all3_joint_strict_pass':all(c['ALL_gain_pp']>1e-9 and c['energy_saving_pct']>0 and c['AP_reduction_C']>0 for c in percase if c['reference'] in policies[:3])})
    for a in overall:combined.append({'setting':sid,**a})
    for c in cc:comparisons.append({'setting':sid,**c})
save('SUMMARY.json',{'id':'A24-S26-JOINT-02','counts':data['counts'],'scales':summary,'strict_vs_each_three_baselines':True,'all_40_disclosed':True,'new_fit':0,'new_measurements':0,'selection_before_CONFIRM':True,'adopted':False});csvout('ALL_EPISODES.csv',allrows);csvout('CONF_POLICY_TABLE.csv',combined);csvout('CONF_COMPARISONS.csv',comparisons);csvout('PER_INPUT_COMPARISONS.csv',perinput);csvout('WINDOW_SENSITIVITY.csv',window)
if harms:csvout('HARMS.csv',harms)
csvout('REUSED_DEV_SCREEN.csv',[{'setting':r['setting'],'eligible':r['eligible'],'BC_mean_all_pct':50*sum(s['all'] for s in r['service']),'BC_min_U_pct':100*min(s['urgent'] for s in r['service']),'min_aggregate_ALL_gain_pp':min(c['all_gain_pp'] for c in r['aggregate_gaps']),'worst_energy_saving_pct':min(c['energy_saving_pct'] for c in r['comparisons']),'worst_AP_reduction_C':min(c['AP_reduction_C'] for c in r['comparisons'])} for r in selection['candidates']])
def table(aa):
    ss=['| 방법 | 예측 소비 J*/입력 평균 | 평균 AP ℃ | 전체 정시 | 긴급 정시 | 일반 정시 | 긴급 P95 초 | 일반 P95 초 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in aa:ss.append(f"| {names[a['policy']]} | {a['J']:.3f} | {a['AP']:.3f} | {a['ALL_on_pct']:.2f}% | {a['U_on_pct']:.2f}% | {a['N_on_pct']:.2f}% | {a['U_P95']:.3f} | {a['N_P95']:.3f} |")
    return '\n'.join(ss)
sections=[]
for i,s in enumerate(summary,1):
    aa=s['CONF_overall'];bc=aa[-1];compared=s['CONF_comparisons'];password='충족' if s['joint_aggregate_pass'] else '미충족';small=[]
    for mix in [.5,.75]:
        c=next(i['case'] for i in inputs['cases'] if i['case']['condition']['setting']==s['setting'] and i['case']['condition']['mix']==mix);small.append(f"분류{mix*100:.0f}%: {c['condition']['requests_per_second']:.6f}건/초·공급{c['condition']['supply_s']:.3f}초")
    delta='\n'.join(f"- {names[c['reference']]} 대비 전체 정시 **+{c['ALL_gain_pp']:.3f}%p**, 소비 **{c['energy_saving_pct']:.3f}% 감소**, 평균 AP **{c['AP_reduction_C']:.3f}℃ 감소**; 긴급/일반 P95 {c['U_P95_increase_s']:+.6f}/{c['N_P95_increase_s']:+.6f}초." for c in compared[:3])
    sections.append(f'''## 사전 후보 {i}: 입력당{s['N']}건 · 8건 묶음 · 명목25%

사용자가 요청한 **합산 정시·소비·온도 동시우위 {password}**. 사전 추가한 혼합별 비악화까지 포함한 모든 gate는 {'충족' if s['all_required_gates_pass'] else '미충족'}이다. {' / '.join(small)}. 4입력×{s['N']}건 = 방법별 {bc['ALL_n']}건, 전체 정시 {bc['ALL_on']}/{bc['ALL_n']}·긴급 {bc['U_on']}/{bc['U_n']}·일반 {bc['N_on']}/{bc['N_n']}다.

{table(aa)}

{delta}

분류50% 입력 두 개:

{table(s['CONF_per_mix'][0]['policies'])}

분류75% 입력 두 개:

{table(s['CONF_per_mix'][1]['policies'])}

혼합별 정시 비악화·소비/AP감소 {'충족' if s['mix_nonworse_energy_AP_pass'] else '미충족'}, 혼합별 전체95%/긴급99%·미응답/미완료0 서비스조건 {'충족' if s['service_quality_gate_pass'] else '미충족'}이다. 입력 하나하나에서도 정시율이 엄격히 높은지의 결과는 {s['per_input_all3_joint_strict_pass']}다. 합산 공동우위와 혼합별/개별입력 동률을 구분한다. BC와 교사 차이는 비교 CSV에 남겼으며 BC 고유의 추가 이득이라고 해석하지 않는다.
''')
headline=' / '.join(f"N{s['N']}: {'합산 공동우위 확인' if s['joint_aggregate_pass'] else '합산 조건 미충족'}" for s in summary)
report=f'''# A24 · S26 평가기준을 유지한 정시·소비·온도 동시우위 조건

**{headline}.** 직전 SCALE-01은 정시율 동률을 허용해 모두100%인 조건을 골랐다. 이번에는 사용자 지시대로 **FIFO·EDF·RR 각각보다 합산 전체 정시율이 엄격히 높으면서 소비·평균 AP가 낮음**을 필수로 삼았다. 기존 DEV100행/10설정은 재실행하지 않고 저장 재사용했다. 두 적격후보를 확인 전에 고정하고 각각 미사용 입력4개×5정책, 새40회 평가를 끝냈다. 결과가 좋은 입력만 추려 합산하지 않았다.

**사전 추가한 더 강한 조건인 ‘혼합별 정시 비악화’는 두 후보 모두 실패했다.** 분류75%·draw2에서 교사/BC 긴급1건이 지각했고 기준선은 그 입력에서 전량정시였다. 따라서 합산 결과는 요청한 세 지표 동시우위를 충족하지만, 모든 혼합에서 비악화라는 추가 gate를 충족한 것으로 채택하지 않는다. 등록규약이나 gate를 소급 수정하지 않고 합산/혼합별 판정을 분리해 공개한다.

{''.join(sections)}
## 유지한 S26 평가 기준

분류는 모두 긴급·기한0.8초, 탐지는 모두 일반·2초, 분류50/75% 혼합을 사용한다. 계획 도착 기준 응답에 준비·대기 지연을 포함하고 전체 도착을 분모로 한다. 입력별 N건을 도착률에 따라 공급하고 공급 끝+45초 배정/+60초 검열 진단/+90초까지 관측한다. 소비는0초~고정 관측끝(35초 시작 전 기저 포함), AP평균은35초~동일끝이다. 표의 J*·AP는 네 입력의 동일가중평균이고 전체 정시는 모든 입력의 전체 도착 합산이다. 같은 N이므로 정시율 평균과 합산이 일치한다. **P95는 입력별 nearest-rank P95의 평균**이며 pooled P95는 CSV 보조값이다.

요청 수256/512, 동시묶음8, A24명목참조25%로 규모만 조정했다. 원S26 발표의1,024건·16묶음·명목85%와 같은 난도는 아니다. 25%는 CPU 이용률이 아니라 A24공개명목5단계·가상CPU3/GPU1 점유기준 참조용량 비율이다. C50/75에서 도착률은2.612820/3.968551건/초다. 비교하는 다섯 방법에는 설정마다 같은 입력·잠재작업·관측창을 적용했다.

## 선정과 확인의 경계

[사전선정](../../experiments/a24_s26_joint_20261022/SELECTION.json)은 알려진 기존 DEV 성적에 새 목적을 적용한 후속 개발선정이다. 후보 둘은 혼합별 BC전체95%/긴급99% 이상·미응답/미완료0, 혼합별 정시비악화·소비/AP감소, 합산 정시 strict 우위라는 조건을 충족했다. 긴급100% 유지→전체정시→개선폭 순 규칙으로256건 후보가1번,512건이2번이다. [기존10설정 전량 스크리닝](REUSED_DEV_SCREEN.csv)에 제외된 조건도 공개한다.

확인에는 예전 입력준비 때 pin했으나 해당 설정/정책으로 실행하지 않은 CONF draw1/2를 썼다. 다른 설정의 관측과 같은 실측 pool·일부 잠재작업을 공유하므로 완전 독립 blind 실기기 검증은 아니다. 확인 후 후보·seed·모형·정책·문턱을 바꾸지 않았다. 두 후보 모두의 확인성적을 보고하며 추가 탐색은 없다. 유한 후보 안의 조건부 결과로 전역최적이나 모든입력 우위를 주장하지 않는다.

## 상충과 모형의 한계

정시율 개선과 응답 P95 변화는 다른 지표다. 일반·긴급별 지각수/모든 P95 손해·교사비교는 [HARMS.csv](HARMS.csv)·[PER_INPUT_COMPARISONS.csv](PER_INPUT_COMPARISONS.csv)에 남겼다. 소비창을 공급끝/개별완료까지 바꾼 수치도 [WINDOW_SENSITIVITY.csv](WINDOW_SENSITIVITY.csv)에 공개한다. 주비교의 고정창은 바꾸지 않았다.

동결 A24-NNBC-URGENT-05의 롤링·ATC·50특징36후보 BC/기존 교사·원ORIGINAL물리를 사용한다. S26의32특징정책·GPU>NPU>CPU 기준선·서비스CPU3와 같은 구현은 아니다. CPU3 추론슬롯·미교정 전력/열·탐지GPU전이·초기26℃·판단계산비용 제외 가정이 있다. J*는 미교정 모형의 예측 적분값이며 실제 배터리J/절감·온도감소 입증이 아니다. 최근 보정 관측기를 CPU3 정책에 대입하지 않았다. 묶음을 바꾸면 작업 순서도 일부 달라지는 SCALE-01의 한정은 유지되지만 이번 두 후보는 묶음8로 같고 Nprefix가 같다.

## 파일·검증

- [확인 비교 그림](figures/CONF_COMPARISON.png), [전체40행 CSV](ALL_EPISODES.csv), [확인 표 CSV](CONF_POLICY_TABLE.csv), [요약 JSON](SUMMARY.json)
- [256건 AP 시간그래프](figures/N256_AP_TIME.png)·[누적소비](figures/N256_ENERGY_TIME.png), [512건 AP 시간그래프](figures/N512_AP_TIME.png)·[누적소비](figures/N512_ENERGY_TIME.png): 원 trace의 부분구간 해석식·1초지점, 평활화/새정책실행0. 네 입력 각각 전량표시.
- [규약](../../experiments/a24_s26_joint_20261022/PROTOCOL.md), [동결등록](../../experiments/a24_s26_joint_20261022/OPERATION.json), [JS독립물리·정책·서비스 검산](AUDIT_JS.json) {js['checks']:,}검사 PASS, [NumPy/Torch NN선택·출처 검산](AUDIT_PYTHON.json) {py['checks']:,}검사/BC{py['numpy_Torch_frozen_NN_choices']:,}선택 PASS.
- START40/COMPLETE40/FAIL0, 새학습·fit·실측/기존완료 재시작0. 공유잠금반환. 두후보 모두 사전등록, 자동추가·재시도·기본교체·게시0.

명령: experiments/a24_s26_joint_20261022/run.py, reviews/A24_S26_JOINT_20261022_01의 audit.cjs/audit_python.py/extract_series.cjs/report.py/finalize.py. 시점2026-10-22, 브랜치codex/a24-simulator-handoff-20261016·HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf+미커밋을 [최종증거](FINAL_PROOF.json)로 특정한다. 계산검산은 실기기 검증과 구분한다.
'''
text('REPORT_KO.md',report)
text('CONTINUE_RUNNING.md','''# A24-S26-JOINT-02 유한 종료

사전 고정한 두 후보·각4입력×5정책의40START/40COMPLETE/FAIL0를 완료했다. run.py 재실행·자동추가/대체seed/학습/fit을 하지 않는다. [정본](REPORT_KO.md)의 두 후보 성적·손해·한계를 모두 확인한다. 완료 기존100DEV/120결과를 재실행하지 않았다. 기본정책/모형의 자동교체는 없다. 새 후속 작업은 사용자 요청·별도ID와 유한규약으로 판단한다.
''')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('C:/Windows/Fonts/malgun.ttf');plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
F=O/'figures';F.mkdir(exist_ok=False);colors=['#999999','#db9c31','#7669ad','#27a392','#3559da']
fig,axes=plt.subplots(2,3,figsize=(13,7.8))
for axs,s in zip(axes,summary):
    for ax,key,title in zip(axs,['ALL_on_pct','J','AP'],['전체 정시율 (%)','예측 소비 (J*/입력)','평균 AP (℃)']):
        aa=s['CONF_overall'];vals=[a[key] for a in aa];ax.barh([names[p] for p in policies],vals,color=colors);ax.invert_yaxis();ax.set_title(f"N{s['N']} · {title}",loc='left',weight='bold');ax.set_xlim(0,max(vals)*1.20)
        for i,v in enumerate(vals):ax.text(v+max(vals)*.02,i,f'{v:.2f}',va='center',fontsize=9)
fig.suptitle('A24 · S26 평가기준 · 사전 선정 두 규모의 별도 확인',fontsize=15);fig.text(.5,.01,'8건 묶음·명목25%·혼합50/75% × draw1/2 | 소비·AP는 입력별 평균 | J*는 미교정 모형값',ha='center',fontsize=9);fig.tight_layout(rect=[0,.035,1,.95]);fig.savefig(F/'CONF_COMPARISON.png',dpi=165);plt.close(fig)
series=read(O/'TIME_SERIES.json.gz')['series']
for n in [256,512]:
    ss0=[s for s in series if s['condition']['n']==n];caseids=sorted({s['label'].split('__')[0] for s in ss0})
    for metric,ylabel,suffix in [('AP_c','AP 온도 (℃)','AP_TIME'),('cumulative_J','0초부터 누적 예측 소비 (J*)','ENERGY_TIME')]:
        fig,axes=plt.subplots(2,2,figsize=(12.7,8.4))
        for ax,case in zip(axes.flat,caseids):
            ss=[s for s in ss0 if s['label'].split('__')[0]==case]
            for p,color in zip(policies,colors):
                t=next(s for s in ss if s['policy']==p);pp=[p for p in t['points'] if p['t_s']>=35];ax.plot([p['t_s']-35 for p in pp],[p[metric] for p in pp],label=names[p],color=color,lw=1.4,ls='--' if p in ['EDF_DYN','TEACHER_RISK'] else '-')
            c=ss[0]['condition'];ax.axvline(ss[0]['supply_stop_s']-35,ls=':',color='#555555',label='요청 공급 끝');ax.set_title(f"분류{c['mix']*100:.0f}%·확인입력{c['draw']}");ax.set_xlabel('요청 시작 후 경과 시간 (초)');ax.set_ylabel(ylabel);ax.grid(alpha=.15)
        handles,lab=axes[0,0].get_legend_handles_labels();fig.legend(handles,lab,loc='lower center',ncol=6);fig.suptitle(f'A24 N{n} · 8건 묶음·명목25% · 확인 입력4개 전량',fontsize=14);fig.tight_layout(rect=[0,.05,1,.95]);fig.savefig(F/f'N{n}_{suffix}.png',dpi=165);plt.close(fig)
save('REPORT_BUILD.json',{'status':'PASS','new_environments':0,'new_fits':0,'both_preselected_scales_reported':True,'harms_rows':len(harms),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
print(json.dumps({'state':'REPORT_BUILT','outcomes':[{'setting':s['setting'],'pass':s['all_required_gates_pass'],'BC_ALL':s['CONF_overall'][-1]['ALL_on_pct'],'BC_U':s['CONF_overall'][-1]['U_on_pct'],'EDF_comparison':s['CONF_comparisons'][1]} for s in summary]},ensure_ascii=False))
