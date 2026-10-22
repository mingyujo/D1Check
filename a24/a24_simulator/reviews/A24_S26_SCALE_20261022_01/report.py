"""Saved-only tables, finite-grid accounting and plots. No science entry point."""
import sys,json,gzip,csv,math,statistics,collections,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[3];A=R/'a24_simulator';O=A/'results/A24_S26_SCALE_20261022_01';H=A/'experiments/a24_s26_scale_20261022';V=Path(__file__).resolve().parent
read=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf-8-sig'))
def save(name,x):
    with (O/name).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,allow_nan=False,indent=2)
def csvout(name,rows):
    assert rows
    with (O/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def textout(name,x):(O/name).write_text(x,encoding='utf-8') if not (O/name).exists() else (_ for _ in ()).throw(FileExistsError(name))
data=read(O/'RESULT.json');rows=data['rows'];choice=read(O/'DEV_SELECTION.json');inputs=read(H/'INPUTS.json');js=read(O/'AUDIT_JS.json');py=read(O/'AUDIT_PYTHON.json');pair=read(O/'INPUT_PAIRING_NOTE.json');assert js['status']==py['status']=='PASS'
derived={r['label']:r for r in js['derived']};policies=['FIFO_DYN','EDF_DYN','RR_DYN','TEACHER_RISK','BC_NEURAL_URGENT'];labels=dict(zip(policies,['FIFO','EDF','RR','교사규칙','롤링+ATC+BC']));checks=0
def mean(x):return statistics.mean(x)
def p95(x):
    s=sorted(x);return s[math.ceil(.95*len(s))-1] if s else None
def aggregate(rr):
    assert rr and len(set(r['policy'] for r in rr))==1
    out={'policy':rr[0]['policy'],'inputs':len(rr),'J_mean':mean(r['metrics']['J'] for r in rr),'J_sum':sum(r['metrics']['J'] for r in rr),'AP_mean':mean(r['metrics']['AP'] for r in rr),'trace_peak_max':max(r['metrics']['peak'] for r in rr),'increment_J_mean':mean(r['metrics']['increment_J'] for r in rr),'pre35_baseline_J_mean':mean(r['metrics']['pre35_baseline_J'] for r in rr)}
    for c in ['ALL','U','N']:
        for k in ['n','on','missing','incomplete']:out[c+'_'+k]=sum(r['metrics']['service'][c][k] for r in rr)
        out[c+'_on_pct']=100*out[c+'_on']/out[c+'_n'];out[c+'_P95_session_mean']=mean(r['metrics']['service'][c]['P95'] for r in rr);out[c+'_P95_pooled']=p95([v for r in rr for v in r['metrics']['service'][c]['latencies']])
    out['J_per_request']=out['J_sum']/out['ALL_n'];out['route_counts']={k:sum(r['metrics']['route_counts'][k] for r in rr) for k in ['C_CPU','C_GPU','D_CPU','D_GPU']}
    return out
def compare(bc,ref):
    return {'reference':ref['policy'],'energy_saving_pct':100*(1-bc['J_mean']/ref['J_mean']),'J_reduction_per_input':ref['J_mean']-bc['J_mean'],'AP_reduction_C':ref['AP_mean']-bc['AP_mean'],'ALL_on_change_pp':bc['ALL_on_pct']-ref['ALL_on_pct'],'U_on_change_pp':bc['U_on_pct']-ref['U_on_pct'],'N_on_change_pp':bc['N_on_pct']-ref['N_on_pct'],'U_P95_increase_s':bc['U_P95_session_mean']-ref['U_P95_session_mean'],'N_P95_increase_s':bc['N_P95_session_mean']-ref['N_P95_session_mean']}
selected=data['selected']['id'];conf=[r for r in rows if r['condition']['role']=='CONF'];dev=[r for r in rows if r['condition']['role']=='DEV' and r['condition']['setting']==selected]
assert len(rows)==120 and len(conf)==20 and len(dev)==10
phase={k:[aggregate([r for r in rr if r['policy']==p]) for p in policies] for k,rr in [('DEV_selected',dev),('CONF',conf)]};confirm=phase['CONF'];comparisons=[compare(confirm[-1],r) for r in confirm[:-1]];perinput=[];window=[];episode=[];harm=[];ties=[]
for r in rows:
    c=r['condition'];m=r['metrics'];e={k:c[k] for k in ['role','setting','n','burst','mix','draw','nominal_load','requests_per_second','supply_s']};e.update(label=r['label'],policy=r['policy'],J=m['J'],AP=m['AP'],trace_peak=m['peak'],J_per_request=m['energy_per_request'],increment_J=m['increment_J'])
    for group in ['ALL','U','N']:
        s=m['service'][group];e.update({group+'_'+k:s[k] for k in ['n','on','missing','incomplete','P95']});e[group+'_on_pct']=100*s['on']/s['n']
    episode.append(e)
for case in sorted({r['case'] for r in rows}):
    rr=[r for r in rows if r['case']==case];bc=next(r for r in rr if r['policy']==policies[-1]);b=aggregate([bc])
    for r in rr[:-1]:
        p=compare(b,aggregate([r]));p.update(case=case,role=bc['condition']['role'],setting=bc['condition']['setting'],mix=bc['condition']['mix'],draw=bc['condition']['draw']);perinput.append(p)
        for key in ['energy_saving_pct','AP_reduction_C','ALL_on_change_pp','U_on_change_pp','N_on_change_pp']:
            if p[key]<-1e-10:harm.append({'case':case,'role':p['role'],'reference':p['reference'],'metric':key,'value':p[key]})
        for key in ['U_P95_increase_s','N_P95_increase_s']:
            if p[key]>1e-10:harm.append({'case':case,'role':p['role'],'reference':p['reference'],'metric':key,'value':p[key]})
        d=derived[r['label']];db=derived[bc['label']]
        window.append({'case':case,'role':p['role'],'reference':r['policy'],'main_saving_pct':p['energy_saving_pct'],'supply_window_saving_pct':100*(1-db['supply_J']/d['supply_J']),'own_completion_window_saving_pct':100*(1-db['own_completion_J']/d['own_completion_J']) if d['own_completion_J'] and db['own_completion_J'] else None,'supply_AP_reduction_C':d['supply_AP']-db['supply_AP']})
# Establish why baseline rows coincide in the selected CONF, using request-level timings/routes.
for case in sorted({r['case'] for r in conf}):
    rr=[r for r in conf if r['case']==case and r['policy'] in policies[:3]];fingerprints=[]
    for r in rr:
        raw=read(R/r['raw']['path']);values=[[q[k] for k in ['request_id','route','dispatch_ns','response_ns','available_ns']] for q in raw['result']['requests']];fingerprints.append(hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest())
    assert len(set(fingerprints))==1;ties.append({'case':case,'all_baseline_routes_and_timings_exact':True,'sha256':fingerprints[0]});checks+=1
grid=[]
for rank,c in enumerate(sorted(choice['candidates'],key=lambda c:c['rank']),1):
    s=c['setting'];score=c['score'];rr=[r for r in rows if r['condition']['role']=='DEV' and r['condition']['setting']==s['id']];t={p:aggregate([r for r in rr if r['policy']==p]) for p in policies}
    grid.append({'rank':rank,'setting':s['id'],'N':s['n'],'burst':s['burst'],'nominal_load':s['load'],'BC_ALL_on_pct':t[policies[-1]]['ALL_on_pct'],'BC_min_mix_U_on_pct':100*score['min_urgent'],'FIFO_ALL_on_pct':t[policies[0]]['ALL_on_pct'],'EDF_ALL_on_pct':t[policies[1]]['ALL_on_pct'],'RR_ALL_on_pct':t[policies[2]]['ALL_on_pct'],'teacher_ALL_on_pct':t[policies[3]]['ALL_on_pct'],'worst_energy_saving_pct':score['min_energy_saving_pct'],'worst_AP_reduction_C':score['min_AP_reduction_C'],'service_tier':score['service_tier'],'joint_tier':score['joint_tier']})
pareto=[]
for g in grid:
    keys=['BC_ALL_on_pct','BC_min_mix_U_on_pct','worst_energy_saving_pct','worst_AP_reduction_C']
    if not any(all(h[k]>=g[k] for k in keys) and any(h[k]>g[k] for k in keys) for h in grid):pareto.append(g['setting'])
per_mix=[{'mix':mix,'policies':[aggregate([r for r in conf if r['policy']==p and r['condition']['mix']==mix]) for p in policies]} for mix in [.5,.75]]
cases=[i['case'] for i in inputs['cases'] if i['case']['condition']['role']=='CONF' and i['case']['condition']['setting']==selected]
confcomparison=[p for p in perinput if p['role']=='CONF'];windowconf=[w for w in window if w['role']=='CONF'];basewindow=[w for w in windowconf if w['reference'] in policies[:3]]
summary={'id':'A24-S26-SCALE-01','selection':data['selected'],'counts':data['counts'],'DEV_selected':phase['DEV_selected'],'CONF':confirm,'CONF_comparisons':comparisons,'CONF_per_mix':per_mix,'CONF_per_input_comparisons':confcomparison,'grid':grid,'DEV_pareto_settings':pareto,'input_pairing_qualification':pair,'selected_cases':cases,'baseline_equal_request_level':ties,'P95_primary':'Equal-weight mean of input-specific nearest-rank P95; pooled is secondary','energy_primary':'0 through fixed observation_end_s, including pre35 idle baseline','AP_primary':'35 through same fixed observation_end_s; mean across inputs','CONF_joint_condition_pass':all(x['energy_saving_pct']>0 and x['AP_reduction_C']>0 and x['ALL_on_change_pp']>=0 for x in comparisons[:3]),'CONF_all_three_baselines_also_100_pct':all(x['ALL_on_pct']==x['U_on_pct']==100 for x in confirm[:3]),'sources':{'result_sha256':hashlib.sha256((O/'RESULT.json').read_bytes()).hexdigest(),'operation_sha256':hashlib.sha256((H/'OPERATION.json').read_bytes()).hexdigest()},'adopted_as_default':False,'new_fits':0,'new_measurements':0}
save('SUMMARY.json',summary);csvout('ALL_EPISODES.csv',episode);csvout('GRID_SUMMARY.csv',grid);csvout('CONF_POLICY_TABLE.csv',[{k:v for k,v in r.items() if k!='route_counts'} for r in confirm]);csvout('CONF_COMPARISONS.csv',comparisons);csvout('PER_INPUT_COMPARISONS.csv',perinput);csvout('WINDOW_SENSITIVITY.csv',window);csvout('HARMS.csv',harm)
save('INFERENCE_CONTRACT.json',{'policy':'A24-NNBC-URGENT-05/BC_NEURAL_URGENT','status':'FROZEN_EXISTING_POLICY_WITH_NEW_INPUT_SCALE','checkpoint':read(H/'OPERATION.json')['checkpoint'],'network_sha256':read(H/'OPERATION.json')['network_sha256'],'selected_input_setting':data['selected'],'scope':'Only the declared S26-aligned criteria and scaled synthetic input conditions; no default policy/model replacement','new_training':0,'new_fit':0,'new_measurements':0,'published':False})
fmt=lambda x,n=2:f'{x:.{n}f}'
def table(agg):
    out=['| 방법 | 예측 소비 J*/입력 | 평균 AP ℃ | 전체 정시 | 긴급 정시 | 일반 정시 | 긴급 P95 초 | 일반 P95 초 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for a in agg:out.append(f"| {labels[a['policy']]} | {a['J_mean']:.3f} | {a['AP_mean']:.3f} | {a['ALL_on_pct']:.2f}% | {a['U_on_pct']:.2f}% | {a['N_on_pct']:.2f}% | {a['U_P95_session_mean']:.3f} | {a['N_P95_session_mean']:.3f} |")
    return '\n'.join(out)
b=confirm[-1];ref=confirm[1];co=comparisons[1]
gridtable='\n'.join(['| 순위 | 요청수 | 묶음 | 명목부하 | BC 전체 정시 | BC 혼합별 최저 긴급 정시 | EDF 전체 정시 | 최저 소비 절감 | 최저 AP 감소 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']+[f"| {g['rank']} | {g['N']} | {g['burst']} | {g['nominal_load']*100:.0f}% | {g['BC_ALL_on_pct']:.2f}% | {g['BC_min_mix_U_on_pct']:.2f}% | {g['EDF_ALL_on_pct']:.2f}% | {g['worst_energy_saving_pct']:.3f}% | {g['worst_AP_reduction_C']:.3f}℃ |" for g in grid])
case_lines='\n'.join(f"- 분류 {mix*100:.0f}%: 약 {next(c for c in cases if c['condition']['mix']==mix)['condition']['requests_per_second']:.6f}건/초, 요청 공급 {next(c for c in cases if c['condition']['mix']==mix)['condition']['supply_s']:.3f}초, 입력당 512건." for mix in [.5,.75])
auditchecks=js['checks']+py['checks']
report=f'''# A24 · S26과 평가기준을 맞춘 입력규모 탐색 결과

**전체·긴급 정시율 100%를 충족하면서 소비·온도가 함께 낮은 조건은 입력당 512건, 동시 도착 4건, A24 명목 참조용량의 25%였다.** 사전 10설정의 100회 탐색에서 선정한 뒤 별도 합성 입력 4개·20회로 확인했다. 확인에서 롤링+ATC+BC는 FIFO·EDF·RR 대비 예측 소비 **{co['energy_saving_pct']:.3f}%**, 평균 AP **{co['AP_reduction_C']:.3f}℃** 감소했다.

기준선도 전체·긴급·일반 정시율이 모두 100%다. 따라서 이 조건의 성과는 **같은 정시율을 유지한 소비·온도 감소**이며 정시율 우위는 없다. BC의 긴급 P95는 {co['U_P95_increase_s']:.6f}초, 일반 P95는 {co['N_P95_increase_s']:.6f}초 늘었다. 교사규칙과 BC의 소비·온도는 거의 같다.

## S26과 같은 기준, A24에 맞게 바꾼 규모

분류는 전부 긴급·상대기한 0.8초, 탐지는 전부 일반·2초다. 분류 50%와 75%의 두 혼합을 사용한다. 계획 도착부터 응답까지 측정하며 준비·대기 시간을 포함한다. 정시율 분모는 전체 도착, 미응답·미완료·지각을 그대로 남긴다. 입력별 요청 수로 공급 길이 N/도착률을 정한다. 공급 끝+45초까지 배정, +60초 검열 진단, +90초까지 고정 관측한다.

소비는 0초부터 고정 관측 끝까지, AP 평균은 35초부터 같은 끝까지다. 주 P95는 **입력별 nearest-rank P95의 동일가중평균**이다. 네 입력의 P95를 먼저 구해 평균내며 모든 응답을 한꺼번에 합친 pooled P95와 구별한다. 소비·AP도 입력별 수치의 동일가중평균이다. 요청 수가 같은 확인에서는 정시율을 합산해도 입력별 평균과 같다.

S26 발표의 입력당 1,024건·16건 묶음·명목85%를 A24의 **512건·4건 묶음·명목25%**로 조정했다. 두 기기의 납기·분모·집계 기준은 맞췄지만 입력 난도가 같은 조건은 아니다. 명목25%는 CPU 이용률 또는 실측 지속처리율 25%라는 뜻이 아니다. A24 공개 명목 5단계 시간과 가상 CPU3/GPU1 점유 한도로 계산한 기기 내 참조용량에 대한 비율이다.

{case_lines}

각 혼합을 새 draw1/2로 구성해 총 4입력이다. 방법별 **2,048건(긴급 1,280·일반 768)**, 5방법 총 10,240건이며 반복 표본은 기존 실측 pool을 재사용한다. 독립 새 기기 세션 검증은 아니다.

정책·모형은 사용자가 선택했던 A24-NNBC-URGENT-05를 동결했다. 50특징·36후보 신경망 BC, 롤링 예측·ATC·기존 긴급 보호/위험여유와 FIFO/EDF/RR 동적 경로 선택을 사용한다. S26의 32특징 정책·GPU>NPU>CPU 기준선·서비스 CPU3와 같은 구현은 아니다. 이 작업은 **평가기준 정렬과 입력규모 탐색**이다.

## 선택에 쓰지 않은 확인 결과

{table(confirm)}

위 소비는 한 입력 평균이고 단위 J*는 기존 미교정 전력 모형의 적분값이다. 실제 SI J 정확도나 배터리 절감 검증을 뜻하지 않는다. 4입력 합계는 기준선 {ref['J_sum']:.6f}J*, BC {b['J_sum']:.6f}J*로 차이 {ref['J_sum']-b['J_sum']:.6f}J*다. 한 입력 평균 차이는 **{co['J_reduction_per_input']:.6f}J***다. 미응답·미완료는 모든 방법 0건이다.

FIFO/EDF/RR이 같은 값인 것은 요청별 경로·배정·응답·자원반환 시각까지 네 입력 모두 일치했기 때문이다. 이 작은 묶음에서는 큐 순서 차이가 실행 결과를 바꾸지 않았다. 세 정책을 다른 수치로 보이도록 입력이나 집계 규칙을 바꾸지 않았다. 교사 대비 BC 소비 차이는 {b['J_mean']-confirm[3]['J_mean']:+.6f}J*/입력으로, BC가 교사보다 우월하다는 근거는 없다.

### 혼합별 확인

분류 50%:

{table(per_mix[0]['policies'])}

분류 75%:

{table(per_mix[1]['policies'])}

각 입력의 비교와 손해는 [PER_INPUT_COMPARISONS.csv](PER_INPUT_COMPARISONS.csv)·[HARMS.csv](HARMS.csv), 합산 전 수치는 [ALL_EPISODES.csv](ALL_EPISODES.csv)에 남겼다. P95는 완료 응답에 대한 값이며 미응답·미완료 0건을 함께 확인했다.

## 전체 10설정 탐색과 선택 이유

다음은 **DEV 성적**이며 별도 확인 결과가 아니다. BC 전체 정시는 두 혼합 평균, 긴급은 두 혼합 중 최저다. 소비 절감·AP 감소도 두 혼합×세 기준선 6비교 중 최솟값이다.

{gridtable}

선정 순서는 먼저 두 혼합의 미응답·미완료 0, 긴급100%·전체95% 이상을 우선하고, 기준선 셋 모두 대비 전체 정시 비악화·소비·AP 감소를 충족하는지를 본다. 이 조건을 만족하면 가장 불리한 비교에서의 소비 절감률이 가장 큰 설정을 고른다. 세 설정이 우선 서비스 조건을 충족했고 512·묶음4·25%가 그중 최저 절감률 {choice['selected']['score']['min_energy_saving_pct']:.6f}%로 선정됐다. 확인 전에 선택 파일을 저장했고 확인 후 재선정하지 않았다.

선택 DEV 결과:

{table(phase['DEV_selected'])}

512건·묶음8·25%는 두 혼합 평균 전체정시99.90%이고 분류50% 입력에서 긴급1건이 지각했다. 256건·묶음8·25%는 DEV에서 BC100%와 기준선 대비 정시율 이득이 있으나 두 혼합 중 낮은 소비·AP 이득이 선택 조건보다 작았다. 이 후보의 별도 확인을 추가하지 않았으므로 확인된 대안으로 홍보하지 않는다.

묶음16 진단에서는 같은25%에서도 BC 전체정시77.54/91.60%, 긴급94.14/88.80%로 무너졌다(분류50/75%). 명목50%·512건에서는 묶음4조차 전체77.15/94.92%였다. 입력률이 낮아도 한꺼번에 16건이 들어오면 짧은 납기를 놓칠 수 있으며, 명목 참조용량은 열·경합·준비지연·자원순서를 모두 반영한 지속용량 인증이 아니다. 관측된 동작의 설명이며 새로운 실측 인과 입증은 아니다.

전역최적을 찾았다는 뜻이 아니다. **사전 고정한 10설정 안에서 이 선정기준으로 고른 조건부 최선**이다. DEV의 4지표 Pareto 설정은 {', '.join(pareto)}다. 높은 부하에서 정시율 차이를 보여주는 후보와 모든 납기를 지키는 후보는 목적이 다르다. 기존 초당4건 평가의 2.22%·0.595℃·94.77%와는 기한·긴급구성·공급창이 달라 정책 개선 전후 비교로 쓰지 않는다.

## 계산창·입력 대응의 한계

관측창에 공급 이후90초가 포함되므로 공급창과 개별 완료창 소비도 보조 계산했다. 확인 4입력×세 기준선에서 공급창 절감률 범위는 {min(w['supply_window_saving_pct'] for w in basewindow):.6f}~{max(w['supply_window_saving_pct'] for w in basewindow):.6f}%, 개별 완료창은 {min(w['own_completion_window_saving_pct'] for w in basewindow):.6f}~{max(w['own_completion_window_saving_pct'] for w in basewindow):.6f}%다. 개별 완료창은 정책별 종료시각이 달라 주 비교가 아니다. [WINDOW_SENSITIVITY.csv](WINDOW_SENSITIVITY.csv)에 전량 공개한다.

규약의 잠재작업 대응 문구에 한정이 있다. N·도착률 비교는 묶음을 고정하면 같은 요청 prefix를 쓰지만, 묶음 크기를 바꾸면 묶음별 작업 회전으로 일부 ordinal의 C/D 순서도 바뀐다(N256·분류50%·묶음4↔8에서 {pair['example_N256_C50_B4_vs_B8_changed_task_ordinals']}개). 동일 설정 내 다섯 정책은 정확히 같은 입력이다. 묶음 간 비교는 순서 변화도 포함한 규모 시나리오 비교이며 묶음 크기만의 단독 인과효과가 아니다. 이 차이를 [INPUT_PAIRING_NOTE.json](INPUT_PAIRING_NOTE.json)에 기록하고 등록 코드는 소급 수정하지 않았다.

전력·열 모형 미교정, 가상 CPU 추론3슬롯, 탐지GPU 전이가정, 초기26℃, 정책 판단 계산비용 제외, 기존 개발자료·실측 pool 재사용이라는 한계가 있다. 최근 열/에너지 오차 보정 관측기는 CPU3 정책 rollout에 대한 독립 적격성이 없어 이번 결과에 대입하지 않았다. 실측 소비·온도 감소나 S26보다 우수한 기기 성능을 입증한 것이 아니다.

## 산출물과 검증

- [확인 비교 그림](figures/CONF_COMPARISON.png), [전체 탐색 그림](figures/GRID_COMPARISON.png)
- [AP 시간 꺾은선](figures/CONF_AP_TIME.png), [누적 소비 시간 꺾은선](figures/CONF_ENERGY_TIME.png): 네 확인 입력 모두, 원 trace의 부분구간 해석식으로 1초 지점을 계산했다. 보간·평활화·정책 재실행은 없다. 공급 종료선을 표시했다.
- [기계 판독 요약](SUMMARY.json), [확인 표 CSV](CONF_POLICY_TABLE.csv), [전체120회 CSV](ALL_EPISODES.csv), [시간자료 CSV](TIME_SERIES.csv)
- [사전 규약](../../experiments/a24_s26_scale_20261022/PROTOCOL.md), [동결 등록](../../experiments/a24_s26_scale_20261022/OPERATION.json), [선정 기록](DEV_SELECTION.json)
- [JS 독립 물리·요청 검산](AUDIT_JS.json): {js['checks']:,}검사 PASS. [Python/NumPy 동결신경망·선정·출처 검산](AUDIT_PYTHON.json): {py['checks']:,}검사, BC {py['numpy_Torch_frozen_NN_choices']:,}선택 PASS. 계산 구현 검산이며 실기기 정확도 인증은 아니다.
- 새 과학 START120/COMPLETE120/FAIL0, 새 학습·fit·실측0, 기존 완료 실험 재시작0. 시작 전 import명 충돌과 가상파일명 source pin 오류는 리뷰 폴더에 보존했고 과학 START 전 해결했다. 공유 잠금 반환 확인. 자동 추가·재시도 없음.

검증 명령은 reviews/A24_S26_SCALE_20261022_01의 audit.cjs, audit_python.py, extract_series.cjs, report.py와 final_check.py다. 시점2026-10-22, 브랜치 codex/a24-simulator-handoff-20261016·HEAD ac3a5af569e04bc6be01f1ef976b9dd4eb6558cf와 미커밋 파일 해시를 [최종 증거](FINAL_PROOF.json)로 특정한다. 기존 기본 정책·완료 결과의 자동 교체와 Git 게시를 하지 않았다.
'''
textout('REPORT_KO.md',report)
textout('CONTINUE_RUNNING.md',f'''# A24-S26-SCALE-01 종료·인계

120 START/120 COMPLETE/FAIL0로 유한 종료했다. run.py·prepare.py 재실행, 누락처럼 보이는 미선정 CONF 입력의 추가 실행, 자동 범위 확대를 하지 않는다. 미선정 CONF40입력은 사전 준비된 미사용 자료다.

정본은 [REPORT_KO.md](REPORT_KO.md), 선택 {selected}. 새 합성확인에서 전체·긴급·일반100%, 기준선 대비 소비{co['energy_saving_pct']:.6f}%/AP{co['AP_reduction_C']:.6f}℃감소, 긴급/일반P95+{co['U_P95_increase_s']:.6f}/+{co['N_P95_increase_s']:.6f}초다. 기준선도100%, 교사와BC 거의동일. 결과는 해당규모 한정이며 전역최적·새독립실측 아니다.

추가 작업은 기존 자료 설명·발표자료 반영 또는 별도 ID/유한 규약을 둔 후속 요청이다. 현결과·동결checkpoint·모형·기존보고는 보존한다. 기본자동채택0·새학습/fit/측정0. 최종검사/봉인 상태는 FINAL_PROOF.json을 확인한다.
''')
# Export plots with the standard plotting stack, never a generated illustration.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font=Path('C:/Windows/Fonts/malgun.ttf')
if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']='Malgun Gothic'
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
F=O/'figures';F.mkdir(exist_ok=False);colors=['#999999','#dc9c31','#6d68a8','#31a392','#3559da'];names=[labels[p] for p in policies]
fig,axes=plt.subplots(2,2,figsize=(11.5,7.5));values=[[a['J_mean'] for a in confirm],[a['AP_mean'] for a in confirm],[a['U_P95_session_mean'] for a in confirm],[a['N_P95_session_mean'] for a in confirm]]
for ax,vs,title in zip(axes.flat,values,['예측 소비 (J*/입력 평균)','평균 AP (℃)','긴급 응답 P95 (초)','일반 응답 P95 (초)']):
    ax.barh(names,vs,color=colors);ax.invert_yaxis();ax.set_title(title,loc='left',fontweight='bold');ax.set_xlim(0,max(vs)*1.17)
    for i,v in enumerate(vs):ax.text(v+max(vs)*.015,i,f'{v:.3f}',va='center',fontsize=9)
fig.suptitle('A24 별도 확인: 모든 방법 전체·긴급·일반 정시 100%',fontsize=15,fontweight='bold');fig.text(.5,.015,'512건 × 4입력 · 4건 묶음 · 명목25% | P95는 입력별 값의 평균 | J*는 미교정 모형값',ha='center',fontsize=9);fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(F/'CONF_COMPARISON.png',dpi=170);fig.savefig(F/'CONF_COMPARISON.svg');plt.close(fig)
natural=sorted(grid,key=lambda g:(g['N'],g['burst'],g['nominal_load']));x=list(range(len(natural)));fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
axes[0].plot(x,[g['BC_ALL_on_pct'] for g in natural],'o-',label='BC 전체');axes[0].plot(x,[g['BC_min_mix_U_on_pct'] for g in natural],'s-',label='BC 혼합별 최저 긴급');axes[0].plot(x,[g['EDF_ALL_on_pct'] for g in natural],'x--',label='EDF 전체');axes[0].set(ylabel='정시율 (%)',ylim=(0,105),title='DEV 10설정 전량 공개 · 별도 확인과 구분');axes[0].legend(ncol=3)
axes[1].bar(x,[g['worst_energy_saving_pct'] for g in natural],color=['#3559da' if g['setting']==selected else '#b6c4ef' for g in natural]);axes[1].set(ylabel='최저 소비 절감률 (%)',title='두 혼합 × 세 기준선 6비교 중 최저 절감률');axes[1].set_xticks(x,[f"N{g['N']}\n묶음{g['burst']}\n명목{g['nominal_load']*100:.0f}%" for g in natural]);fig.tight_layout();fig.savefig(F/'GRID_COMPARISON.png',dpi=170);plt.close(fig)
series=read(O/'TIME_SERIES.json.gz')['series'];cases_order=sorted({s['label'].split('__')[0] for s in series})
for metric,title,filename in [('AP_c','AP 온도 (℃)','CONF_AP_TIME'),('cumulative_J','0초부터 누적 예측 소비 (J*)','CONF_ENERGY_TIME')]:
    fig,axes=plt.subplots(2,2,figsize=(13,8.5))
    for ax,case in zip(axes.flat,cases_order):
        ss=[s for s in series if s['label'].split('__')[0]==case];end=ss[0]['observation_end_s']
        for p,color in zip(policies,colors):
            s=next(s for s in ss if s['policy']==p);pts=[p for p in s['points'] if p['t_s']>=35];ax.plot([p['t_s']-35 for p in pts],[p[metric] for p in pts],color=color,label=labels[p],lw=1.5,linestyle='--' if p in ['EDF_DYN','TEACHER_RISK'] else '-',alpha=.9)
        c=ss[0]['condition'];ax.axvline(ss[0]['supply_stop_s']-35,color='#555555',ls=':',label='요청 공급 끝');ax.set_title(f"분류 {c['mix']*100:.0f}% · 확인 입력 {c['draw']}");ax.set_xlabel('요청 시작 후 경과 시간 (초)');ax.set_ylabel(title);ax.grid(alpha=.16);ax.set_xlim(0,end-35)
    handles,leg=axes[0,0].get_legend_handles_labels();fig.legend(handles,leg,loc='lower center',ncol=6);fig.suptitle('A24 확인 입력 4개 · 동일 고정 관측창 · 원 trace 해석식',fontsize=14);fig.tight_layout(rect=[0,.055,1,.95]);fig.savefig(F/(filename+'.png'),dpi=170);plt.close(fig)
save('REPORT_BUILD.json',{'status':'PASS','saved_only':True,'new_environments':0,'new_fits':0,'request_level_baseline_checks':checks,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'conf_summary':{'energy_saving_pct':co['energy_saving_pct'],'AP_reduction_C':co['AP_reduction_C']},'harms_rows':len(harm),'window_sign_flips_CONF_vs_baselines':sum(w['supply_window_saving_pct']<0 or w['own_completion_window_saving_pct']<0 for w in basewindow)})
print(json.dumps({'state':'REPORT_BUILT','selected':selected,'CONF_comparison':co,'all_CONF':b['ALL_n'],'all_on':b['ALL_on'],'Pareto':pareto,'harms':len(harm)},ensure_ascii=False))
