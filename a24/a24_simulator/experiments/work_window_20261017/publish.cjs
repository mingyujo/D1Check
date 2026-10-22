'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),repo=path.dirname(root),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const op=read(path.join(__dirname,'OPERATION.json')),out=path.join(root,op.output),r=read(path.join(out,'RESULT.json')),audit=read(path.join(out,'AUDIT.json'));
if(audit.result_sha256!==sha(path.join(out,'RESULT.json')))throw Error('Exact audited result required');
if(fs.existsSync(path.join(out,'FINAL_HANDOFF_PROOF.json')))throw Error('Publication consumed');
for(const p of [...op.sources,...op.inputs])if(sha(path.join(repo,p.path))!==p.sha256)throw Error('Immutable inputs');
const f=n=>Number(n).toFixed(4),s=r.summary,headers=['original','common','completion'],names={original:'기존 고정 종료',common:'8정책 공통 작업 종료',completion:'정책별 자기 작업 종료'};
const table=headers.map(w=>{const a=s[w];return `| ${names[w]} | ${f(a.EDF_mean_duration_s)} | ${f(a.EDF_mean_baseline_J_proxy)} | ${f(a.EDF_mean_increment_J_proxy)} | ${f(a.EDF_mean_total_J_proxy)} | ${f(100*a.EDF_baseline_fraction)}% | ${f(a.found_feasible_portfolio_saving_percent)}% |`;}).join('\n');
const policy=op.primary_policies.map(p=>{const a=r.policies[p];return `| ${p} | ${f(a.common.mean_total)} | ${f(a.completion.mean_total)} | ${f(a.common.mean_AP)} | ${a.common.on_time}/864 | ${a.common.urgent_on_time}/216 | ${a.common.response_missing}/${a.common.incomplete} |`;}).join('\n');
const cases=r.cases.map(c=>`| ${c.case} | ${f(c.common_duration_s)} | ${f(c.reference.completion.duration_s)} | ${f(c.picks.common.saving_percent)}% | ${f(c.picks.completion.saving_percent)}% | ${f(c.common_upper_percent)}% | ${f(c.completion_upper_percent)}% |`).join('\n');
const report=`# 작업 구간으로 소비 평가창 축소 — 저장 결과 사후 재집계

사용자 요청으로 작업 완료 후 남은 긴 유휴 구간을 제외했다. 원132개 일정과 물리·전력계수·학습·납기·요청은 그대로 두고 새 시뮬레이션/학습/적합/최적화/예약0으로 재적분했다. 기존 결과·실패·한계 보고서는 보존한다.

## 같은 EDF의 평가창별 소비

| 평가 범위 | 평균 길이 s | 기저 J* | 증분 J* | 총 J* | 기저 비율 | 찾은 납기 적격 일정 묶음 절감 |
|---|---:|---:|---:|---:|---:|---:|
${table}

분자는 조건별 총소비를 합산하고 같은 EDF 합으로 나눈 비율이다. 절감 묶음은 원8정책과 새3개 미래 작업량 진단 휴리스틱 중 조건별 최소소비 적격 일정을 사후 선택한 값이며 단일 온라인 정책의 성능이 아니다. 모든 예정 요청과 전체/긴급 정시 수를 유지한 일정만 절감 근거에 포함했다. 새3개 진단의 불완료/납기 손해도 RESULT.json에 남긴다.

## 범위의 정확한 뜻

- 공통 시작은 원 입력의 첫 예정 도착35초다. 시작 지연과 작업 사이의 유휴·명시 WAIT는 모두 포함한다. 실제 CPU/GPU가 바빴던 조각만 이어 붙여 비용을 낮추지 않았다.
- **공통 작업 종료**는 조건마다 기존8개 동결 정책의 실제 마지막 AVAILABLE 중 최댓값이다. 모든 원정책에 같은 시각을 적용하고 새로운 미래 진단정책을 기준 시각 선정에 넣지 않았다. 이보다 늦게 끝나는 진단 일정은 해당 창에서 미완료로 남겨 적격 집합에서 제외한다. 이 종료는 평가 결과로 정한 사후 기술 통계이며 새 사전 독립평가가 아니다. 비교 정책 집합이 바뀌면 끝도 바뀔 수 있다.
- **자기 작업 종료**는 각 정책의 마지막 AVAILABLE이다. 같은 요청 묶음을 끝내는 데 쓴 에너지라는 별도 지표다. 정책이 더 빨리 끝내면 기저 비용도 줄어든다. 휴대폰의 같은 실제 시간 동안 총전력이 그만큼 절감됐다는 주장은 아니다. 정책별 완료시간을 같이 공개한다.
- 완료 후 공유 활성 decay는 약0.196J*로 남는다. 이를 숨기지 않고 각 row의 post_completion_activation_tail_J_proxy에 별도로 표시한다. 이후 기저 소비와 잔열 관측도 원 기록에 보존했다. 짧아진 창을 새로운 전체 수명주기 소비로 부르지 않는다.
- 주 온도 비교는 같은 공통 종료까지의 평균AP다. 자기 완료 구간의 평균은 시간 길이가 달라지는 기술 지표다. 기존 평균AP의35초~service끝 정의도 별도 필드에 그대로 남겼다. 창 변경만으로 옛0.5℃ 목표를 소급 PASS로 바꾸지 않는다.

## 기존8정책의 모든 결과

| 정책 | 공통 종료 총 J* | 자기 종료 총 J* | 공통 평균AP ℃ | 전체 정시 | 긴급 정시 | 공통 미응답/미완료 |
|---|---:|---:|---:|---:|---:|---:|
${policy}

## 절감 한계의 갱신

짧은 공통 작업창에서 찾은 절감은 평균 **${f(s.common.found_feasible_portfolio_saving_percent)}%**, 재사용한 낙관적 작업량 하한이 허용하는 상한은 **${f(s.common.maximum_mean_saving_percent)}%**다. 이 상한은 모든 작업을 해당 공통 시각까지 끝내고 원 EDF 전체/긴급 정시 수를 유지하는 일정에 적용된다. 원래 더 긴 drain 제약으로 구한 하한을 재사용하므로 느슨하지만 보수적인 방향이다. 새 최적화는 실행하지 않았다.

자기 작업 종료 지표의 확인 절감은 **${f(s.completion.found_feasible_portfolio_saving_percent)}%**, 별도 낙관적 상한은 **${f(s.completion.maximum_mean_saving_percent)}%**다. 기저 시간 하한은 각 요청의 admission 이후 최소 cold full work, 그리고 각 release 시점 이후 모든 작업의 최소 work 합/2를 사용했다. 실제 열 감속과 비선점/자원별 배정을 생략했으므로 실제 최단 완료시간 이하이고1마이크로초 수치 여유를 뺐다. 여기에 원 작업 에너지 하한을 더했다. 원 입력의 drain까지 전체 완료와 EDF 정시 개수 조건은 유지한다. 상한이10%를 넘더라도 달성 가능한10% 일정의 증명은 아니다.

기존 **3.9828% 상한**은 기존 고정 종료 총소비에 대한 판정으로 남긴다. 짧은 평가창이나 자기 종료 목표에 그 수치를 그대로 대입하지 않는다. 이번은 이미 본 평가의 지표 재정의이므로 원10%/.5℃ 사전 목표의 성공·새 독립평가·재학습 효과로 바꾸지 않는다.

| 조건 | 공통창 s | EDF 자기창 s | 확인 공통 절감 | 확인 자기 절감 | 공통 낙관적 상한 | 자기 낙관적 상한 |
|---|---:|---:|---:|---:|---:|---:|
${cases}

## 검산과 계보

원132개 저장 일정×3창=396개 prefix를 재집계했다. 기존 소비 재현 최대차 ${r.original_energy_max_error}J*, 경계 일부만 포함되는 ${audit.independent_RK4_partial_intervals}개 구간은 별도 RK4 전력/RC 적분으로 대조했다. 독립${audit.checks}검사 PASS·최대차${audit.max_absolute_error}다. 요청별 response/AVAILABLE·정시 분모와 공통 endpoint를 별도로 확인했다. OPERATION.json에 소스/원자료 SHA를 고정했다.

학습 보상·기본 UI·물리 모델·정책 변경0이며 새 환경/훈련/fit/solver/기기/예약0이다. 원 coupled 잔38, savings 잔8, RR잔1은 그대로다. 이번 J*는 가설 모형의 비용이며 실측J/실기기 절감 인증이 아니다. 원 수치/처리시간 표본과 과거 handoff proof는 해당 역사 버전 그대로 보존한다.
`;
fs.writeFileSync(path.join(out,'REPORT.md'),report,{flag:'wx'});
const concise=`작업 구간 재집계 완료: EDF 기저 비율 기존${f(100*s.original.EDF_baseline_fraction)}%→공통 작업창${f(100*s.common.EDF_baseline_fraction)}%/자기 완료창${f(100*s.completion.EDF_baseline_fraction)}%다. 납기 적격 사후 일정 묶음의 절감은 공통${f(s.common.found_feasible_portfolio_saving_percent)}%/자기${f(s.completion.found_feasible_portfolio_saving_percent)}%, 낙관적 상한은 각각${f(s.common.maximum_mean_saving_percent)}%/${f(s.completion.maximum_mean_saving_percent)}%다. 정확한 최적값·단일 온라인 정책 우위는 미확인이다.`;
const prepend=(p,t)=>fs.writeFileSync(p,t+'\n\n'+fs.readFileSync(p,'utf8'));
prepend(path.join(repo,'docs/PROJECT_STATUS.md'),`## 2026-10-17 A24 작업 구간 소비 — 저장 재집계·독립검산 완료\n\n${concise}\n\n[정본/모든 조건](../a24_simulator/${op.output}/REPORT.md). ${audit.checks}검사 PASS·396 prefix 재적분·새환경/학습/fit/solver/예약0·원38/8/RR1불변이다. 기존3.9828%는 원 고정창 판정으로 보존·새 창의 원사전목표 PASS 승격0다. 검증은 새 OP/원132 SHA·최종proof를 따른다. 다음은 사용자 해석/공유이며 이번 재집계는 완료·자동후속0이다.`);
prepend(path.join(repo,'docs/PROJECT_PLAN.md'),`## 2026-10-17 작업 동안의 소비 범위로 재평가 완료\n\n${concise}\n\n새환경 없이 원 저장396 prefix만 재집계했다. 공통8정책 endpoint는 사후 기술 통계이며 자기 완료 에너지는 정책별 평가 길이가 다르다. 둘 다 작업 사이 WAIT/유휴를 포함한다. 기존 사전목표와 새 지표를 구분하며 [보고서](../a24_simulator/${op.output}/REPORT.md)를 정본으로 한다. 기본UI/학습보상/실제 정책을 수정하거나 완료실험을 재실행하지 않았다.`);
prepend(path.join(repo,'docs/DECISIONS.md'),`## 2026-10-17 A24-WORK-WINDOW — 사용자 요청의 사후 지표 재정의\n\n사용자 '작업하는 동안으로 범위 축소' 요청으로 같은 작업 묶음의 에너지를 공통 작업 종료/자기 완료 종료로 분리한다. 마지막 요청 이후 고정15+30초를 계속 주지 않고 원8정책의 최대 실제 AVAILABLE을 공통 endpoint로 쓰는 기술 통계다. 자기 종료는 완료시간과 함께 보고하며 실제 같은 벽시계의 폰 총에너지 절감과 구분한다. ${concise}\n\n원 물리/원시 일정/실패/목표 판정은 보존, 새환경/학습/fit/예약0이다. 근거는 [완료보고](../a24_simulator/${op.output}/REPORT.md)와 새 OP SHA다.`);
prepend(path.join(root,'README.md'),`**작업 구간 소비 재집계 완료:** [완료 뒤 긴 유휴를 제외한 전체 결과](${op.output}/REPORT.md). ${concise}`);
const p=path.join(root,'CONTINUE.json'),cont=read(p);fs.writeFileSync(p,JSON.stringify({work_window_reaccount:{status:'COMPLETED_SAVED_ONLY_REACCOUNT',operation:'experiments/work_window_20261017/OPERATION.json',report:op.output+'/REPORT.md',result:op.output+'/RESULT.json',audit_checks:audit.checks,native_START:0,new_reservation:0,summary:s,posthoc_metric_change:true,training_objective_unchanged:true,original_results_preserved:true},...cont},null,2)+'\n');
const docs=['docs/PROJECT_STATUS.md','docs/PROJECT_PLAN.md','docs/DECISIONS.md','a24_simulator/README.md','a24_simulator/CONTINUE.json'].map(p=>path.join(repo,p));
const files=[...fs.readdirSync(out).map(f=>path.join(out,f)),...fs.readdirSync(__dirname).map(f=>path.join(__dirname,f)),...docs];
const proof={schema:'A24-work-window-publication-proof-v1',utc:new Date().toISOString(),command:process.argv,HEAD:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).trim(),uncommitted_changes:true,
 files:files.map(p=>({path:path.relative(repo,p).replaceAll('\\','/'),sha256:sha(p),bytes:fs.statSync(p).size})),source_pins_verified:op.sources.length,input_pins_verified:op.inputs.length,native_START:0,new_reservation:0,original_3_9828_bound_scope:'original longer fixed window only; current docs are a later historical version'};
fs.writeFileSync(path.join(out,'FINAL_HANDOFF_PROOF.json'),JSON.stringify(proof,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:'PUBLISHED_ARTIFACTS',summary:s,files:proof.files.length},null,2));
