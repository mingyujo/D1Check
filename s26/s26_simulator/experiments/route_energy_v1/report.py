"""Summarize all saved results, with same-scenario baselines and service checks."""
import json,datetime,statistics,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];O=H/'artifacts/G001'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def mean(a):return statistics.mean(a) if a else None
result=read(O/'RESULT.json');rows=[r for r in result['rows'] if r['kind']=='EVAL'];selection=read(O/'SELECTION_FROZEN.json');bound=read(H/'ROUTE_BOUND_RESULT.json');training=read(O/'TRAINING_COMPLETE.json')
power=read(R/'experiments/capacity_power_v1/artifacts/G001/MODEL.json');gamma=power['coef'][2]/power['scale'][2]
def method(r):return 'FROZEN_RL' if r['seed']==481083 else 'BALANCED_RL' if r['balanced'] else r['mode']
baseline={(r['model'],r['input']):r for r in rows if r['mode']=='EDF_GPU_FIRST'}
frozen={(r['model'],r['input']):r for r in rows if r['seed']==481083}
def nonharm(r,b,tol=0.):return r['unfinished']==b['unfinished']==0 and all(r['service'][k]['on_time']/r['service'][k]['planned']+tol>=b['service'][k]['on_time']/b['service'][k]['planned'] for k in ['all','urgent','normal'])
def group(rr,m):
    bb=[baseline[(r['model'],r['input'])] for r in rr];ff=[frozen[(r['model'],r['input'])] for r in rr]
    J=mean([r['J'] for r in rr]);eJ=mean([b['J'] for b in bb]);T=mean([r['AP_mean'] for r in rr]);eT=mean([b['AP_mean'] for b in bb]);charged=mean([r['J']+gamma*r['extra_CPU_core_s'] for r in rr]);ebase=mean([b['J']+gamma*b['extra_CPU_core_s'] for b in bb])
    return dict(model=rr[0]['model'],load=rr[0]['load'],method=m,rows=len(rr),on_percent=100*mean([r['service']['all']['on_time']/r['n'] for r in rr]),urgent_percent=100*mean([r['service']['urgent']['on_time']/r['service']['urgent']['planned'] for r in rr]),normal_percent=100*mean([r['service']['normal']['on_time']/r['service']['normal']['planned'] for r in rr]),mean_API_J=J,EDF_delta_percent=100*(J/eJ-1),mean_AP_C=T,EDF_AP_delta_C=T-eT,max_sampled_AP_C=max(r['AP_peak'] for r in rr),mean_case_P95_s=mean([r['service']['all']['p95_s'] for r in rr]),unfinished=sum(r['unfinished'] for r in rr),outside_AP_rows=sum(r['outside_AP'] for r in rr),mean_extra_CPU_core_s=mean([r['extra_CPU_core_s'] for r in rr]),mean_shared_CPU_wait_s=mean([r['shared_CPU_wait_s'] for r in rr]),EDF_service_nonharm_pairs=sum(nonharm(r,b) for r,b in zip(rr,bb)),FROZEN_service_nonharm_pairs=sum(nonharm(r,b) for r,b in zip(rr,ff)),FROZEN_within0_5pp_pairs=sum(nonharm(r,b,.005) for r,b in zip(rr,ff)),CPU_proxy_surcharge_API_W=gamma,mean_API_J_with_proxy_surcharge=charged,EDF_delta_with_proxy_surcharge_percent=100*(charged/ebase-1),mean_classification_route_counts={k:mean([r['routes'][k] for r in rr]) for k in ['classification_CPU','classification_GPU','classification_NPU']},seed_on_percent={str(s):100*mean([r['service']['all']['on_time']/r['n'] for r in rr if r['seed']==s]) for s in sorted(set(r['seed'] for r in rr if r['seed'] is not None))})
groups=[]
order=['EDF_GPU_FIRST','ATC','ATC_SALVAGE','ENERGY_ONLY','FROZEN_RL','BALANCED_RL']
for model in ['CENTRAL','CPU3']:
    for load in [.65,.85,1.05]:
        for m in order:
            rr=[r for r in rows if r['model']==model and r['load']==load and method(r)==m];groups.append(group(rr,m))
        rr=[r for r in rows if r['model']==model and r['load']==load and r['seed']==selection['selected'][model]];groups.append(group(rr,'DEV_SELECTED_BALANCED_RL'))
summary=dict(status='ALL_FRESH_EVALUATIONS_SUMMARIZED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),START=result['START'],COMPLETE=result['COMPLETE'],FAIL=result['FAIL'],PPO_updates=result['PPO_updates'],selected=selection['selected'],EVAL_unfinished=sum(r['unfinished'] for r in rows),EVAL_cases_with_unfinished=sum(r['unfinished']>0 for r in rows),groups=groups,rows=rows,route_LP=bound['grouped'],physical_validation=False,extra_CPU_power='Unknown. gamma0 keeps frozen union power; gamma1.887756 uses existing CPU union coefficient as an illustrative extra-active-core surcharge, not measured marginal core power or a certified interval. Temperature rows do not include this surcharge.',no_deadline_protection=True)
write(O/'COMPARISON_SUMMARY.json',summary)
names={'EDF_GPU_FIRST':'단순 EDF','ATC':'ATC','ATC_SALVAGE':'보완 ATC','ENERGY_ONLY':'에너지 전용 진단','FROZEN_RL':'기존 RL 고정','BALANCED_RL':'보완 RL 3seed 평균','DEV_SELECTED_BALANCED_RL':'DEV 선정 보완 RL'}
lines=['# S26 경로 선택·CPU 병렬 가정·균형 보상 결과','',f"등록420회 중 START{result['START']} / COMPLETE{result['COMPLETE']} / FAIL{result['FAIL']}. TRAIN96·학습 참조32·P0 4·DEV96·새 EVAL192, PPO update48. 기존 자료만 사용했고 새 실측·물리 fit·납기 보호·NN 뒤 덮어쓰기·업로드는0이다.",'','## 경로 선택 완화하한','', '|공유 CPU 서비스|명목부하|이전 EDF API-J|경로 선택 완화하한 API-J|낙관적 절감 상한|','|---|---:|---:|---:|---:|']
lines.insert(3,f"새 EVAL 중 {summary['EVAL_cases_with_unfinished']}/192 세션에 미AVAILABLE 요청이 있으며 합계 {summary['EVAL_unfinished']}건이다. 계산 COMPLETE와 모든 작업의 실제 완료를 구분한다. 미완료·납기 손해가 있는 행의 낮은 소비를 동등 서비스 절감으로 인정하지 않는다.")
if (H/'OPERATION_RESUME_V2.json').exists():
    lines.insert(3,'168START/168COMPLETE 뒤 다음 START 전 메모리 검사로 운영 중단1회가 있었다. 원 실패 파일·체크포인트를 보존하고 6개 최종 학습기를 복원해 미시작252회만 이었다. 완료 환경/학습 재실행0이며, 재개 드라이버의 자원/저장분 재사용 부분을 제외한 simulate AST는 원본과 같다. 이후 완결8회 경계에서 Node 엔진 메모리를 회수하고 실제 호스트 여유를 기다렸다.')
for g in bound['grouped']:
    lines.append(f"|{g['cpu_workers']}개|{g['load']:.0%}|{g['EDF_API_J']:.3f}|{g['lower_API_J']:.3f}|{g['optimistic_upper_saving_vs_EDF_percent']:.3f}%|")
lines+=['','이 표는 과거 R7 평가의 같은 관측창·latent route template 맵과 AP26~60℃ 조건에서 계산한 낙관적 LP다. 모든 요청의 경로를 고를 수 있지만 납기·정수 배정·실행 순서를 완화했다. 가능한 최소소비의 하한이며 실제 달성 절감률이 아니다. CPU3 행도 과거 CPU1 EDF를 분모로 썼으므로 CPU 병렬화와 정책 효과를 분리한 우위가 아니다. 실제 평가에서는 아래처럼 같은 CPU 시나리오의 EDF를 기준으로 한다.','', '## 새 평가 전체 비교','']
for model in ['CENTRAL','CPU3']:
    lines +=[f"### {'기존 CPU 서비스1개' if model=='CENTRAL' else 'CPU 서비스 최대3개 병렬 가정'}",'','|부하|방식|전체 정시율|긴급/일반 정시율|API-J|대EDF 소비|평균AP|대EDF 평균AP|최고AP표본|세션P95 평균|','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for g in groups:
        if g['model']!=model:continue
        lines.append(f"|{g['load']:.0%}|{names[g['method']]}|{g['on_percent']:.3f}%|{g['urgent_percent']:.3f}/{g['normal_percent']:.3f}%|{g['mean_API_J']:.3f}|{g['EDF_delta_percent']:+.3f}%|{g['mean_AP_C']:.3f}℃|{g['EDF_AP_delta_C']:+.3f}℃|{g['max_sampled_AP_C']:.3f}℃|{g['mean_case_P95_s']:.3f}s|")
    lines+=['']
lines+=['## 同一 서비스와 추가 CPU 전력 감도','', '|CPU 시나리오|부하|방식|대EDF 전군 비악화 쌍|대기존RL 전군 비악화 쌍|추가 CPU core-s|기존 CPU계수 추가부과시 대EDF 소비|','|---|---:|---|---:|---:|---:|---:|']
for g in groups:
    if g['method'] not in ['ENERGY_ONLY','BALANCED_RL','DEV_SELECTED_BALANCED_RL']:continue
    lines.append(f"|{g['model']}|{g['load']:.0%}|{names[g['method']]}|{g['EDF_service_nonharm_pairs']}/{g['rows']}|{g['FROZEN_service_nonharm_pairs']}/{g['rows']}|{g['mean_extra_CPU_core_s']:.3f}|{g['EDF_delta_with_proxy_surcharge_percent']:+.3f}%|")
lines+=['','비악화는 같은 입력에서 전체·긴급·일반 정시율이 모두 낮아지지 않고 전량 AVAILABLE인 경우다. 에너지 전용 진단이 소비를 줄여도 납기를 손해 보면 같은 서비스의 절감으로 인정하지 않는다. CPU3의 추가 코어 전력은 기존 자료로 식별할 수 없다. 기존 전력모형의 CPU union 계수 '+f'{gamma:.6f}'+' API-W/core를 추가 CPU 동시 가동시간에 부과한 감도도 표시한다. 이 계수는 실제 코어당 추가소비라는 실측이 아니며 감도 구간이 신뢰구간/물리상한도 아니다. 추가부과는 저장 스케줄의 에너지만 재계산하며 속도·온도 피드백을 다시 실행하지 않았다.','', '## 학습 보완과 한계','', '원 에너지/열 cost는 TRAIN 참조 중앙값으로 정규화했다. 긴급/일반 지연은 각 군 분모로 정규화하고 추가 지각항을0.2에서0.02로 줄였다. 각 목적의 actor advantage를 RMS로 정규화해 단위/크기 차이가 정책 기울기를 독점하지 않게 했다. 납기 벌점 multiplier는 TRAIN에서 기존 RL 각 군 정시율−0.5%p를 목표로 조절한다. 이는 보상 학습이며 납기 기반 행동제거·강제요청·NN 이후 대체는 아니다. 보완판은 임의 WAIT 총12초/선두1.5초 한도를 제거하고 등록 dispatch stop/horizon만 유지했다.','', '동일 부모 actor에서3seed를 시작하고 critic/Adam/RNG를 새로 설정했다. 보상·학습·WAIT 한도를 함께 바꾼 묶음검증이므로 개별 변경의 인과효과를 분리하지 못한다. 3seed의 개별 결과를 JSON에 모두 보존하고 DEV에서 대표를 고른 뒤 새 EVAL을 열었다. 새 평가 반복은 같은 burst16 도착 패턴에서 latent phase/template 스트림을 새로 뽑은 경우이며 독립 실기기 반복측정이 아니다.','', 'CPU3은 작업/CPU서비스시간을 삭제하지 않고 grant capacity만 최대3으로 바꾼 가정이다. CPU/GPU/NPU route 슬롯은 각각1개·비선점·AVAILABLE까지 예약을 유지하고 탐지의 GPU/NPU 전이는 지원하지 않는다. CPU3 가정의 단독 효과와 정책 추가효과를 구분한다.','', 'API-J는 기저 포함 후보 전력모형의 전체 관측창 적분이다. 평균AP는 첫 도착35초부터 관측 종료까지 시간평균이며 유휴/냉각도 포함한다. 온도는 AP 센서 예측으로 실측 체감온도/안전상한이 아니다. 원 전력·열 정확도gate FAIL, 미측정 CPU 동시처리/자원쌍·삼중 간섭·스로틀링·기기 제어비용이 남아 실기기 절감 인증으로 승격하지 않는다. 임의 온도clamp·가공 절감상수는0이다.','', '[계산 요약](experiments/route_energy_v1/artifacts/G001/COMPARISON_SUMMARY.json) · [등록](experiments/route_energy_v1/PROTOCOL.json) · [원자료·원장](experiments/route_energy_v1/artifacts/G001/)']
report=R/'S26_ROUTE_ENERGY_RESULTS_KO.md'
with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
print(json.dumps(dict(status=summary['status'],primary85=[g for g in groups if g['load']==.85]),ensure_ascii=False,indent=2))
