"""Saved-only nine-policy report; outcomes never determine training/model selection."""
import json,gzip,csv,math,statistics,hashlib
from pathlib import Path
V=Path(__file__).resolve().parent;R=V.parents[2];A=R/'a24_simulator';H=A/'experiments/a24_s26_matched_bc_20261022';O=A/'results/A24_S26_MATCHED_BC_20261022_01'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def save(n,x):
    with (O/n).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def text(n,s):
    with (O/n).open('x',encoding='utf-8') as f:f.write(s)
def csvout(n,rows):
    with (O/n).open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
mean=statistics.mean
def p95(x):x=sorted(x);return x[math.ceil(.95*len(x))-1] if x else None
policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_OLD','BC_OLD','TEACHER_MATCH','TEACHER_GUARD','BC_GUARD_FROZEN','BC_MATCHED'];names=dict(zip(policies,['FIFO','EDF','RR','기존 교사','기존 BC','조건맞춤 여유 교사','보완 교사','기존 BC+보완 규칙','보완 BC']))
data=read(O/'RESULT.json');js=read(O/'AUDIT_JS.json');py=read(O/'AUDIT_PYTHON.json');assert js['status']==py['status']=='PASS';rows=[r for r in data['rows'] if r['kind']=='EVAL'];assert len(rows)==72;derived={r['label']:r for r in js['derived']};mimic=read(O/'NN_MIMIC_DIAGNOSTICS.json')
def agg(rr):
    assert rr and all(r['status']=='COMPLETE' for r in rr)
    v={'policy':rr[0]['policy'],'inputs':len(rr),'J':mean(r['metrics']['J'] for r in rr),'AP':mean(r['metrics']['AP'] for r in rr),'J_total':sum(r['metrics']['J'] for r in rr),'increment_J':mean(r['metrics']['increment_J'] for r in rr),'peak':max(r['metrics']['peak'] for r in rr)}
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:v[g+'_'+k]=sum(r['metrics']['service'][g][k] for r in rr)
        v[g+'_on_pct']=100*v[g+'_on']/v[g+'_n'];v[g+'_P95']=mean(r['metrics']['service'][g]['P95'] for r in rr);v[g+'_P95_pooled']=p95([t for r in rr for t in r['metrics']['service'][g]['latencies']])
    v['J_per_request']=v['J_total']/v['ALL_n'];return v
def comp(b,a):return {'reference':a['policy'],'ALL_gain_pp':b['ALL_on_pct']-a['ALL_on_pct'],'U_gain_pp':b['U_on_pct']-a['U_on_pct'],'N_gain_pp':b['N_on_pct']-a['N_on_pct'],'energy_saving_pct':100*(1-b['J']/a['J']),'J_reduction':a['J']-b['J'],'AP_reduction_C':a['AP']-b['AP'],'U_P95_increase_s':b['U_P95']-a['U_P95'],'N_P95_increase_s':b['N_P95']-a['N_P95']}
cohorts=[];tables=[];comparisons=[];byinput=[];harms=[];windows=[];episode=[]
for r in data['rows']:
    c=r['condition'];m=r['metrics'];v={'label':r['label'],'kind':r['kind'],'cohort':c['cohort'],'n':c['n'],'mix':c['mix'],'load':c['nominal_load'],'draw':c['draw'],'policy':r['policy'],'J':m['J'],'AP':m['AP']}
    for g in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete','P95']:v[g+'_'+k]=m['service'][g][k]
        v[g+'_on_pct']=100*v[g+'_on']/v[g+'_n']
    episode.append(v)
for cohort in ['PRIMARY','SMALL','STRESS']:
    rr=[r for r in rows if r['condition']['cohort']==cohort];aa=[agg([r for r in rr if r['policy']==p]) for p in policies];b=aa[-1];cc=[comp(b,a) for a in aa[:-1]];mixed=[]
    for mix in [.5,.75]:
        t=[agg([r for r in rr if r['condition']['mix']==mix and r['policy']==p]) for p in policies];mixed.append({'mix':mix,'policies':t,'comparisons':[comp(t[-1],a) for a in t[:-1]]})
    joint=all(c['ALL_gain_pp']>1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for c in cc[:3]);mixok=all(c['ALL_gain_pp']>=-1e-9 and c['energy_saving_pct']>1e-9 and c['AP_reduction_C']>1e-9 for m in mixed for c in m['comparisons'][:3]);quality=all(m['policies'][-1]['ALL_on_pct']>=95 and m['policies'][-1]['U_on_pct']>=99 and m['policies'][-1]['ALL_missing']==m['policies'][-1]['ALL_incomplete']==0 for m in mixed)
    ablations=[]
    for policy,ref in [('TEACHER_MATCH','TEACHER_OLD'),('TEACHER_GUARD','TEACHER_MATCH'),('BC_GUARD_FROZEN','BC_OLD'),('BC_MATCHED','BC_GUARD_FROZEN'),('BC_MATCHED','BC_OLD'),('BC_MATCHED','TEACHER_GUARD')]:
        a=next(a for a in aa if a['policy']==policy);refa=next(a for a in aa if a['policy']==ref);ablations.append({'policy':policy,**comp(a,refa)})
    cohorts.append({'cohort':cohort,'N':rr[0]['condition']['n'],'load':rr[0]['condition']['nominal_load'],'overall':aa,'mixes':mixed,'comparisons':cc,'ablations':ablations,'joint_vs_baselines':joint,'mixed_nonworse_joint':mixok,'quality_gate':quality,'all_gates':joint and mixok and quality})
    tables.extend({'cohort':cohort,**a} for a in aa);comparisons.extend({'cohort':cohort,**c} for c in cc)
    for case in sorted({r['case'] for r in rr}):
        qq=[r for r in rr if r['case']==case];br=next(r for r in qq if r['policy']=='BC_MATCHED');ba=agg([br]);db=derived[br['label']]
        for ar in qq:
            if ar['policy']=='BC_MATCHED':continue
            c=comp(ba,agg([ar]));c.update(cohort=cohort,case=case,mix=br['condition']['mix'],draw=br['condition']['draw']);byinput.append(c)
            for k in ['ALL_gain_pp','U_gain_pp','N_gain_pp','energy_saving_pct','AP_reduction_C']:
                if c[k]<-1e-9:harms.append({'cohort':cohort,'case':case,'reference':ar['policy'],'metric':k,'value':c[k]})
            for k in ['U_P95_increase_s','N_P95_increase_s']:
                if c[k]>1e-9:harms.append({'cohort':cohort,'case':case,'reference':ar['policy'],'metric':k,'value':c[k]})
            da=derived[ar['label']];windows.append({'cohort':cohort,'case':case,'reference':ar['policy'],'main_saving_pct':c['energy_saving_pct'],'supply_saving_pct':100*(1-db['supply_J']/da['supply_J']),'own_completion_saving_pct':100*(1-db['own_completion_J']/da['own_completion_J']) if db['own_completion_J'] and da['own_completion_J'] else None})
primary=cohorts[0];ed=primary['comparisons'][1];old=next(c for c in primary['comparisons'] if c['reference']=='BC_OLD');learn=next(c for c in primary['comparisons'] if c['reference']=='BC_GUARD_FROZEN');bc=primary['overall'][-1];risk=read(O/'RISK_CALIBRATION.json');oldrisk=read(A/'results/A24_NN_URGENT_TIE_20261021_01/RISK_CALIBRATION.json')
save('SUMMARY.json',{'id':'A24-S26-MATCH-04','counts':data['counts'],'cohorts':cohorts,'primary_frozen_before_eval':True,'fresh_eval_draws':[201,202],'new_training_cases':10,'new_NN_fits':2,'new_measurements':0,'new_physical_fit':0,'adopted':False});csvout('ALL_EPISODES.csv',episode);csvout('EVAL_POLICY_TABLE.csv',tables);csvout('EVAL_COMPARISONS.csv',comparisons);csvout('PER_INPUT_COMPARISONS.csv',byinput);csvout('WINDOWS.csv',windows)
if harms:csvout('HARMS.csv',harms)
save('INFERENCE_CONTRACT.json',{'policy':'A24_BC50_S26_MATCHED_LATEST_START_WAIT_V5','checkpoint':data['fits'][1]['checkpoint'],'network_sha256':read(O/'FREEZE.json')['network_sha256'],'risk_calibration':{'path':(O/'RISK_CALIBRATION.json').relative_to(R).as_posix(),'sha256':hashlib.sha256((O/'RISK_CALIBRATION.json').read_bytes()).hexdigest()},'Net_shape':[36,50],'decision':'Frozen neural logits argmax within public shared latest-start/risk/normal mask; no post-NN teacher override','cost_regression':False,'PPO':False,'EVAL_selection':False,'adopted':False,'mobile_validated':False})
save('TEACHER_MATCH_CONTRACT.json',{'policy':'TEACHER_MATCH','implementation':'a24_nn_urgent_tie_20261021.policy.Policy with learner=None and this run RISK_CALIBRATION.task_margin_s','new_WAIT_guard':False,'uses_retrained_NN':False,'risk_calibration_path':(O/'RISK_CALIBRATION.json').relative_to(R).as_posix(),'evaluated_as_predeclared_ablation':True,'selected_for_any_new_EVAL':False,'adopted':False})
teacher_match=next(a for a in primary['overall'] if a['policy']=='TEACHER_MATCH')
fixed=read(O/'FIXED_STATE_COMPARISON.json')['cohorts'];fc=fixed['PRIMARY']['counts'];fsmall=fixed['SMALL']['counts'];fstress=fixed['STRESS']['counts']
def table(aa):
    return '\n'.join(['| 방법 | 예측J*/입력 | 평균AP ℃ | 전체정시 | 긴급정시 | 일반정시 | 긴급P95 초 | 일반P95 초 |','|---|---:|---:|---:|---:|---:|---:|---:|']+[f"| {names[a['policy']]} | {a['J']:.3f} | {a['AP']:.3f} | {a['ALL_on_pct']:.2f}% | {a['U_on_pct']:.2f}% | {a['N_on_pct']:.2f}% | {a['U_P95']:.3f} | {a['N_P95']:.3f} |" for a in aa])
sections=[]
for c in cohorts:
    b=c['overall'][-1];ab='\n'.join(f"| {names[r['policy']]} ← {names[r['reference']]} | {r['ALL_gain_pp']:+.4f}%p | {r['energy_saving_pct']:+.4f}% | {r['AP_reduction_C']:+.4f}℃ |" for r in c['ablations'])
    sections.append(f'''## {c['cohort']} · N{c['N']}·묶음8·명목{c['load']*100:.0f}%

방법별 입력{b['inputs']}개·{b['ALL_n']}도착, 보완BC 전체{b['ALL_on']}/{b['ALL_n']}·긴급{b['U_on']}/{b['U_n']}·일반{b['N_on']}/{b['N_n']}정시다. 기준선셋 대비 합산3지표 공동우위 {c['joint_vs_baselines']}, 혼합별비악화/소비AP감소 {c['mixed_nonworse_joint']}, 서비스gate(전체95/긴급99%·미응답/미완료0) {c['quality_gate']}다. 한gate와 전체gate를 구별한다.

{table(c['overall'])}

효과 분리(양수 소비/AP 값은 감소):

| 변경 비교 | 전체정시 변화 | 예측소비 감소율 | 평균AP 감소 |
|---|---:|---:|---:|
{ab}

분류50%:

{table(c['mixes'][0]['policies'])}

분류75%:

{table(c['mixes'][1]['policies'])}
''')
report=f'''# A24 · S26 조건 교사규칙·학습자료 정렬 및 BC 신경망 보완 결과

**주 평가에서 보완BC 전체정시 {bc['ALL_on_pct']:.4f}%·긴급 {bc['U_on_pct']:.4f}%**다. 같은 새 입력의 EDF 대비 전체정시 {ed['ALL_gain_pp']:+.4f}%p, 예측소비 {ed['energy_saving_pct']:+.4f}% 감소·평균AP {ed['AP_reduction_C']:+.4f}℃ 감소다. 소비/AP의 음수 감소율은 악화를 뜻한다. 기준선셋 공동우위는 {primary['joint_vs_baselines']}, 모든 사전gate는 {primary['all_gates']}다.

동일 새입력의 기존BC 대비 전체정시 {old['ALL_gain_pp']:+.4f}%p, 예측소비 {old['energy_saving_pct']:+.4f}% 감소·AP {old['AP_reduction_C']:+.4f}℃ 감소다. **기존NN에 보완규칙만 적용한 경우와 비교한 재학습 추가효과**는 전체 {learn['ALL_gain_pp']:+.4f}%p·소비 {learn['energy_saving_pct']:+.4f}%·AP {learn['AP_reduction_C']:+.4f}℃다. 교사·mask 개선과 학습 자체의 효과를 합쳐서 BC 고유효과로 주장하지 않는다. 기본정책 자동교체0이다.

**보완 판정:** 재학습판의 기존BC 대비 정시율 변화가 없고 소비/AP가 늘면 종합개선판으로 채택하지 않는다. 이번 수치에서 안전여유만 현재조건에 맞춘 교사는 전체 {teacher_match['ALL_on_pct']:.4f}%·긴급 {teacher_match['U_on_pct']:.4f}%이며, 새 대기guard와 재학습NN을 사용하지 않은 별도 사전평가 정책이다. 이를 ‘재학습BC 100%’로 표기하지 않는다. 직전 draw1/2의99.85%와 이번 새draw201/202의99.95% 차이도 학습효과가 아니며, 학습효과는 이번동일입력의BC_OLD/BC_MATCHED로 비교한다. [여유보완 교사 계약](TEACHER_MATCH_CONTRACT.json).

## 검토한 문제와 실제 변경

기존05의 최근 보완TRAIN은128건·1/4건/s·C/D에일반/긴급혼재였다. 현재평가는 C전부긴급.8초·D전부일반2초·C50/75%·N256/512건이므로 분포차이가 있다. 그러나 구교사와구BC 성과가거의같아 학습부족만 원인이라고 확정하지 않았다.

기존 알려진 C75 draw2의 요청scale-000007은35.020963초에준비·35.8초기한인데, 배정가능상태에서 WAIT/WAIT_EVENT를 반복해35.717292초배정·35.838046초응답으로 지각했다. 새guard는 공개 DISPATCH 후보의 예측응답+TRAIN 여유로 배정여유를계산하고, 긴급요청의여유보다큰최대대기(+tick)를가진WAIT만 먼저제외한다. 미래도착/비공개작업량/특정요청ID를조건문에넣지않는다. 교사와BC는같은mask를쓰고NN선택후교사덮어쓰기0이다.

현재조건의 TRAIN10개로 여유를추정한 결과 C는{oldrisk['task_margin_s']['C']:.6f}→{risk['task_margin_s']['C']:.6f}초, D는{oldrisk['task_margin_s']['D']:.6f}→{risk['task_margin_s']['D']:.6f}초다. D는현재일반요청이며위험guard는U에만적용한다. 이것은새실측물리보정이아니라 모의TRAIN예측잔차의nearest-rank90% 안전여유다.

같은원BC50신경망/36후보를유지해 조건맞춤교사자료로128epoch학습→1차NN의TRAIN방문상태추가→128epoch재학습했다. 라벨·mask·비용은공개상태에서만계산했다. 마지막2차fit을평가전에동결했고, 평가로epoch/seed/체크포인트를고르지않았다. TRAIN상태는 {data['fits'][0]['TRAIN_frames']:,}→{data['fits'][1]['TRAIN_frames']:,}개다. [순수모방오차/비용regret](NN_MIMIC_DIAGNOSTICS.json)를방문궤적별로공개하며 행동불일치와실제결과차이는구분한다.

{''.join(sections)}
## 재학습만의 효과와 남은 문제

새 규칙의 동일한 고정 공개상태 {fc['OLD']['states']:,}개에 구NN과재학습NN을모두적용했다. 교사행동과다른선택은 {fc['OLD']['exact_errors']}→{fc['RETRAINED']['exact_errors']}개로줄었지만, 주평가 전체정시율은기존BC와같고 소비/AP는소폭악화했다. 모방을더정확히하는것과실제서비스성과가좋아지는것을구별해야한다. 소규모고정상태오차는 {fsmall['OLD']['exact_errors']}→{fsmall['RETRAINED']['exact_errors']}개로늘었고,고부하는 {fstress['OLD']['exact_errors']}→{fstress['RETRAINED']['exact_errors']}개로줄어도최대교사비용regret는 {fstress['OLD']['max_cost_regret']:.6f}→{fstress['RETRAINED']['max_cost_regret']:.6f}로늘었다. [동일상태검사](FIXED_STATE_COMPARISON.json)는재학습/새환경0이며모델선정에쓰지않았다.

긴급대기를더엄격히막는guard는일부응답을앞당기지만, 자원이끝나기를기다리는선택도제외한다. 그결과소비·열/고부하경합의상충이생길수있다. 이번분리평가에서guard추가가전조건개선을주지않았고,안전여유만다시추정한교사가주평가정시율에서더좋았다. 이는기존특정지각사례의원인검토가맞더라도그사례를막는일반규칙이전체성과를보장하지않는다는뜻이다. 추가guard/재학습판을기본개선판으로자동채택하지않는다.

## 평가 계약·출처·해석 범위

분류긴급0.8초/탐지일반2초·분류50/75%·전체도착분모·계획도착부터응답(준비/큐포함)을S26과맞췄다. 공급=N/도착률, 공급끝+45초배정/+60검열진단/+90고정관측이다. 소비는0초~관측끝(전35초기저포함), AP는35초~같은끝, 주P95는입력별nearest-rankP95 평균이다. pooledP95는CSV보조다. J*/AP도입력별동일가중평균이며각cohort안N이같아합산정시율과입력평균이일치한다.

주평가PRIMARY는512건·명목25%·두혼합×새draw201/202의4입력이고, SMALL은256건25%/STRESS는512건50%의두혼합각1입력이다. 세cohort를섞어대표성과를만들지않았다. 도착률은A24공개명목기준용량의비율이며실측CPU이용률이아니다.

TRAIN/EVAL은canonical key별source 멤버를분리했지만같은원실측세션·반복pool을공유할수있다. 알려진benchmark를본후보완한개발검증이며신규기기세션독립holdout은아니다. 현재105START를보고임의범위확대/재시도/추가학습/미사용후보선택을하지않았다.

ORIGINAL물리·가상CPU3/GPU1·beta.25·D_GPU전이·초기26℃·정책계산비용제외를유지했다. 전력열미교정J*는모형예측적분이며실제배터리J/온도감소입증이아니다. 최근보정관측기를CPU3정책에대입하지않았다. BC입력계산에도교사공개비용/롤링계산을수행하므로제어계산량절감을주장하지않는다. S26과같은정책구현/엔진이라고하지않는다.

## 보존 파일과 검증

- [요약 JSON](SUMMARY.json), [102환경 전량CSV](ALL_EPISODES.csv), [평가표](EVAL_POLICY_TABLE.csv), [모든평가비교](EVAL_COMPARISONS.csv), [개별입력비교](PER_INPUT_COMPARISONS.csv), [모든손해](HARMS.csv), [소비창보조](WINDOWS.csv)
- [정책비교그림](figures/PRIMARY_COMPARISON.png), [주평가 AP시간그래프](figures/PRIMARY_AP_TIME.png), [누적소비시간그래프](figures/PRIMARY_ENERGY_TIME.png), [동결체크포인트계약](INFERENCE_CONTRACT.json)
- [규약](../../experiments/a24_s26_matched_bc_20261022/PROTOCOL.md), [동결등록](../../experiments/a24_s26_matched_bc_20261022/OPERATION.json), [평가전2차동결](FREEZE.json)
- [독립JS 물리/정책/guard/여유검산](AUDIT_JS.json) {js['checks']:,}검사 PASS, [Python/NumPy NN·학습라벨/출처검산](AUDIT_PYTHON.json) {py['checks']:,}검사/{py['independent_numpy_Torch_choices']:,}NN선택 PASS. 계산검산과실기기검증을구분한다.

105START/105COMPLETE/FAIL0=환경102+여유추정1+BCfit2. 새실측/물리fit/PPO/기존완료재시작0·공유잠금반환. 준비import에서구helper에없는pt참조는과학START0에서새전용serializer로교정하고오류기록을보존했다. 이전실험/모형/체크포인트/실패자료는보존한다.

검증명령은experiments/a24_s26_matched_bc_20261022/prepare.py·run.py와reviews/A24_S26_MATCHED_BC_20261022_01의audit.cjs·audit_python.py·report.py·finalize.py다. 시점2026-10-22, 브랜치codex/a24-simulator-handoff-20261016·HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf+미커밋을[최종증거](FINAL_PROOF.json)로특정한다. 자동채택/게시0.
''';text('REPORT_KO.md',report);text('CONTINUE_RUNNING.md','# A24-S26-MATCH-04 유한종료\n\n105 START/105 COMPLETE/FAIL0를완료했다. 새환경102/여유추정1/BCfit2이며run.py·완료identity를재실행하지않는다. [정본](REPORT_KO.md)의주평가/소규모/고부하·규칙/학습효과·모든손해를함께검토한다. 기본모형/정책자동채택0이다. 후속은사용자요청·별도ID/유한규약으로판단한다.\n')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('C:/Windows/Fonts/malgun.ttf');plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'font.size':9})
F=O/'figures';F.mkdir(exist_ok=False);colors=['#999999','#bda033','#9477ae','#c58a58','#718dbd','#cdba83','#29a392','#54b1bf','#3559da']
fig,axes=plt.subplots(1,3,figsize=(14,6.5))
for ax,k,title in zip(axes,['ALL_on_pct','J','AP'],['전체 정시율 (%)','예측 소비 (J*/입력)','평균 AP (℃)']):
    vals=[a[k] for a in primary['overall']];ax.barh([names[p] for p in policies],vals,color=colors);ax.invert_yaxis();ax.set_title(title,loc='left',weight='bold');ax.set_xlim(0,max(vals)*1.19)
    for i,v in enumerate(vals):ax.text(v+max(vals)*.015,i,f'{v:.3f}',va='center',fontsize=8)
fig.suptitle('A24 · 같은 새 PRIMARY 입력 · 교사규칙과 BC 재학습 효과 분리',fontsize=15);fig.text(.5,.01,'N512·묶음8·명목25%·두혼합×새draw201/202 | 기존 05/보완정책 동일 입력 | J* 미교정모형값',ha='center',fontsize=9);fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(F/'PRIMARY_COMPARISON.png',dpi=170);plt.close(fig)
series=read(O/'TIME_SERIES.json.gz')['series'];show=['FIFO_DYN','EDF_DYN','RR_DYN','BC_OLD','TEACHER_GUARD','BC_MATCHED'];col=['#999999','#bda033','#9477ae','#c58a58','#29a392','#3559da'];cases=sorted({s['label'].split('__')[0] for s in series})
for metric,ylabel,suffix in [('AP_c','AP 온도 (℃)','AP_TIME'),('cumulative_J','0초부터 누적 예측 소비 (J*)','ENERGY_TIME')]:
    fig,axes=plt.subplots(2,2,figsize=(12.7,8.4))
    for ax,case in zip(axes.flat,cases):
        ss=[s for s in series if s['label'].split('__')[0]==case]
        for p,color in zip(show,col):
            s=next(s for s in ss if s['policy']==p);pts=[p for p in s['points'] if p['t_s']>=35];ax.plot([p['t_s']-35 for p in pts],[p[metric] for p in pts],label=names[p],color=color,lw=1.5,ls='--' if p in ['BC_OLD','TEACHER_GUARD'] else '-')
        c=ss[0]['condition'];ax.axvline(ss[0]['supply_stop_s']-35,ls=':',color='#555555',label='요청공급끝');ax.set_title(f"분류{c['mix']*100:.0f}%·새draw{c['draw']}");ax.set_xlabel('요청시작후 경과시간 (초)');ax.set_ylabel(ylabel);ax.grid(alpha=.15)
    hh,ll=axes[0,0].get_legend_handles_labels();fig.legend(hh,ll,loc='lower center',ncol=7);fig.suptitle('A24 주평가 네입력 전량 · 원trace 해석식 · 보간/평활화/재실행0',fontsize=13);fig.tight_layout(rect=[0,.05,1,.95]);fig.savefig(F/f'PRIMARY_{suffix}.png',dpi=170);plt.close(fig)
save('REPORT_BUILD.json',{'status':'PASS','new_environments':0,'new_fits':0,'all_EVAL_rows':72,'cohort_aggregates':27,'harms_rows':len(harms),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()});print(json.dumps({'state':'REPORT_BUILT','PRIMARY_newBC_vs_EDF':ed,'PRIMARY_newBC_vs_oldBC':old,'PRIMARY_retraining_only':learn,'gates':{c['cohort']:[c['joint_vs_baselines'],c['mixed_nonworse_joint'],c['quality_gate']] for c in cohorts}},ensure_ascii=False))
