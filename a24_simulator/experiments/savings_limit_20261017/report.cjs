'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output_dir),old=path.join(root,op.parent_output);
const result=read(path.join(out,'RESULT.json')),audit=read(path.join(out,'AUDIT.json')),parent=read(path.join(old,'RESULT.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Exact audited result required');
const ok=(m,b)=>m.response_missing===0&&m.incomplete===0&&m.on_time>=b.on_time&&m.urgent_on_time>=b.urgent_on_time;
const cases=result.bound_cases.map(b=>{
 const candidates=[...parent.rows.filter(r=>r.kind==='FRESH'&&r.case===b.case),...result.rows.filter(r=>r.kind==='FULL_WITNESS'&&r.case===b.case)];
 const feasible=candidates.filter(r=>ok(r.metrics,b.reference));
 const best=feasible.reduce((a,c)=>c.metrics.total_J_proxy<a.metrics.total_J_proxy?c:a);
 const originalEDF=candidates.find(r=>r.kind==='FRESH'&&r.policy==='EDF');
 const joint=feasible.filter(r=>r.metrics.mean_AP_c<=b.reference.mean_AP_c+1e-9).reduce((a,c)=>c.metrics.total_J_proxy<a.metrics.total_J_proxy?c:a,originalEDF);
 return {...b,best_feasible_saved:best.label,best_feasible_total:best.metrics.total_J_proxy,
  found_saving_percent:100*(1-best.metrics.total_J_proxy/b.reference.total_J_proxy),best_feasible_metrics:best.metrics,
  energy_heat_nonworse_saved:joint.label,energy_heat_nonworse_total:joint.metrics.total_J_proxy,
  ten_percent_impossible_even_in_relaxation:b.maximum_total_saving_percent<10,
  half_degree_impossible_even_in_relaxation:b.maximum_AP_reduction_c<.5,
  full_witnesses:candidates.filter(r=>r.kind==='FULL_WITNESS').map(r=>({label:r.label,eligible:ok(r.metrics,b.reference),metrics:r.metrics}))};
});
const micros=[...new Set(result.rows.filter(r=>r.kind==='MICRO_LIST').map(r=>r.case))].map(id=>{
 const ref=result.rows.find(r=>r.kind==='MICRO_REFERENCE'&&r.case===id),all=result.rows.filter(r=>r.kind==='MICRO_LIST'&&r.case===id);
 const legal=all.filter(r=>r.list_plan_eligible&&ok(r.metrics,ref.metrics));
 if(!legal.length)throw Error('No feasible micro schedule');
 const best=legal.reduce((a,b)=>b.metrics.total_J_proxy<a.metrics.total_J_proxy?b:a);
 return {case:id,all_plans:all.length,legal_and_SLA_feasible:legal.length,reference:ref.metrics,best_label:best.label,best_plan:best.extra.plan,best:best.metrics,
  saving_percent:100*(1-best.metrics.total_J_proxy/ref.metrics.total_J_proxy),increment_saving_percent:100*(1-best.metrics.increment_J_proxy/ref.metrics.increment_J_proxy),
  certificate:'Exact minimum over all120 registered list plans; not a continuous-time global certificate and not generalized to48/96 jobs'};
});
const sum=(v,f)=>v.reduce((s,x)=>s+f(x),0),B=sum(cases,x=>x.reference.total_J_proxy),L=sum(cases,x=>x.total_energy_lower),U=sum(cases,x=>x.best_feasible_total);
const summary={schema:'A24-savings-limit-analysis-v1',utc:new Date().toISOString(),source_result_sha256:sha(path.join(out,'RESULT.json')),
 cases,micros,EDF_mean_total:B/cases.length,optimistic_mean_total_lower:L/cases.length,found_feasible_mean_total:U/cases.length,
 found_mean_saving_percent:100*(1-U/B),maximum_mean_saving_percent:100*(1-L/B),
 ten_percent_mean_impossible:100*(1-L/B)<10,ten_percent_impossible_cases:cases.filter(x=>x.ten_percent_impossible_even_in_relaxation).length,
 half_degree_impossible_cases:cases.filter(x=>x.half_degree_impossible_even_in_relaxation).length,
 micro_scope_does_not_prove_full_optimum:true,physical_accuracy_verified:false,new_environment_START:0};
fs.writeFileSync(path.join(out,'ANALYSIS.json'),JSON.stringify(summary,null,2)+'\n',{flag:'wx'});
const f=x=>Number(x).toFixed(4);
const table=cases.map(x=>`| ${x.case} | ${f(x.reference.total_J_proxy)} | ${f(x.best_feasible_total)} | ${f(x.total_energy_lower)} | ${f(x.found_saving_percent)}% | ${f(x.maximum_total_saving_percent)}% |`).join('\n');
const micro=micros.map(x=>`| ${x.case} | ${x.all_plans} | ${x.legal_and_SLA_feasible} | ${f(x.saving_percent)}% | ${f(x.increment_saving_percent)}% |`).join('\n');
const report=`# 스케줄링 절감 한계 — 같은 coupled345 가설 모형의 오프라인 진단

전체12조건 평균의 달성 확인 절감은 **${f(summary.found_mean_saving_percent)}% 이상**, 낙관적인 수학적 완화에서 얻은 최대 가능 절감 상한은 **${f(summary.maximum_mean_saving_percent)}% 이하**다. 참 최적값은 이 사이에 있으며, 상한 자체를 실제로 달성했다고 해석하지 않는다. 총소비10% 목표의 평균 불가능 판정=${summary.ten_percent_mean_impossible}, 개별조건 ${summary.ten_percent_impossible_cases}/12다.

EDF 평균 ${f(summary.EDF_mean_total)}J*, 찾은 납기 비악화 일정 묶음 ${f(summary.found_feasible_mean_total)}J*, 낙관적 소비 하한 ${f(summary.optimistic_mean_total_lower)}J*다. 각 조건에서 기존8정책과 새3진단정책 중 전체/긴급 정시 수를 줄이지 않고 전 요청 응답/AVAILABLE을 완료한 최소소비 일정을 고른 오프라인 묶음이다. 단일 온라인 정책·새 독립 평가·실측 절감이 아니다.

## 전체 조건의 확인 구간

| 조건 | EDF J* | 찾은 실행가능 J* | 낙관적 하한 J* | 달성 확인 절감 | 최대 가능 절감 상한 |
|---|---:|---:|---:|---:|---:|
${table}

모든 조건의 미래 CPU/GPU 잠재 작업량을 공개한 뒤 하한을 구했다. 실제 온라인 정책에는 없는 정보를 허용하고, 온도 궤적 도달 가능성·동시 실행 제약의 일부를 더 완화했다. 따라서 여전히 목표가 불가능하다는 판정은 현재 후보8/NN의 약함만으로 설명할 수 없다. 반대로 목표가 배제되지 않은 경우에는 해당 절감을 달성할 일정이 있다는 뜻이 아니다.

## 하한의 근거

공유 활성 전력 H는 최대2소유자이므로 각 소유자에 H/2를 배분한 합보다 작을 수 없다. 작업량 dw=f dt에 대해 실행 단계의 배분 에너지/작업량은 A(1-l)f²+(Al·leak+H/2)/f, A=p_solo-H다. 나머지 단계는 진행률1이다. 온도26℃ 이상·진행률0.45~1·누설상한3과 RC 전이에서 보수적인 온도상한을 구하고, 0.01℃ 각 구간의 유리한 끝값을 따로 사용해 에너지 하한을 계산했다. 계수마다1e-9를 차감했다.

매 요청이 두 자원 중 하나를 택하는 완화 문제에 전체/긴급 정시 수의 EDF 비악화, 응답 prefix의 도착~기한 구간별 최소 점유량, drain까지 전 단계의 최소 점유량을 넣었다. 비선점 suffix 차단·실제 열 궤적·동시 처리의 일부는 생략한 필요조건이다. HiGHS의 dual bound에서 추가1e-5를 차감한 값과 독립 작업량 하한 중 큰 값을 사용했다. 부동소수점 solver의 보고 하한이며 유리수 형식 증명은 아니다. 각 원 EDF 일정이 이 완화 제약을 실제로 만족하는지 별도로 확인했다.

평균온도는 RC의 에너지 투입 시각별 커널을 사용해, 정시 요청의 응답 prefix 에너지를 기한에 전부 몰아넣는 낙관적 하한도 구했다. 0.5℃ 감소가 이 하한에서도 불가능한 조건은 ${summary.half_degree_impossible_cases}/12다. 그 밖의 조건은 가능성을 배제하지 못한 것이며 달성 증명이 아니다. 시간창·기저 소비·원 물리 계수는 변경하지 않았다.

## 실행 가능한 일정 탐색과 작은 전수 비교

새3정책은 잠재 작업량을 아는 공통 비용식 선택, 잠재 작업량을 아는 ATC, 작업별 저소비 자원을 선호하는 진단 휴리스틱이다. 마지막은 현재 후보8 밖의 ready 요청도 볼 수 있어 현재 NN보다 넓은 정책 공간이다. 어느 것도 전역 최적이라고 부르지 않는다. 납기 손해가 난 새 일정도 모두 저장하고 실현 절감의 증거에서 제외했다.

작은 사례는 FRESH00/06에서 입력만으로 첫 C2개/D2개를 골랐고 원 도착·기한·잠재 key·시간창을 유지했다. 자원 배정과 자원별 순서의 모든120개 list plan을 각 초기온도에서 재생했다. 지정한 즉시배정/합법50ms WAIT 실행 방식 안에서 전수 최적이며, 임의의 연속 대기 시각을 포함한 전체 일정 공간의 최적은 아니다.

| 작은 사례 | 전수 plan | 합법·납기 적격 | 총소비 절감 | 작업증분 절감 |
|---|---:|---:|---:|---:|
${micro}

## 검산·예산·주장 경계

순수8계약 PASS, 원 EDF와 새 진단 P0 두 조건의 시각/지표 정확 일치, 새280 START=280 COMPLETE/FAIL0, 독립 저장검사 ${audit.checks}개 PASS다. 고정 은행은 원8정책의 모든 관측 잠재 벡터와 일치했다. 원602 operation은 재실행하지 않았다. 새288예약 중280소비·잔8이며 이전640의 미할당38과 원256/RR잔1은 건드리지 않았다. 추적 예약은125766/137712 snapshot이며 현재 타host 실제소비 전수값은 아니다. 기기·새 물리 fit·NN학습·자동 후속 실행0이다.

숫자는 A24 실측J나 실기기 최적 한계가 아니라 coupled345 가설 모형의 조건부 한계다. 수학적 완화 상한, 실제 재생으로 찾은 절감, 작은 list class의 전수 최적을 서로 구분한다. 정확한 전역 최적/온라인 도달 가능성/그 외 온도·입력 조건은 미확인이다. ANALYSIS.json에 모든 새 휴리스틱 손해·각 solver의 종료상태/하한·작은 사례 최적 계획을 연결했다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),report,{flag:'wx'});
console.log(JSON.stringify({found_percent:summary.found_mean_saving_percent,upper_percent:summary.maximum_mean_saving_percent,
 impossible10:summary.ten_percent_mean_impossible,impossible_cases:summary.ten_percent_impossible_cases,micros},null,2));
