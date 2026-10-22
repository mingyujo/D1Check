'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const H=__dirname,R=path.resolve(H,'../..'),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),at=(d,n)=>path.join(R,'experiments',d,n),g=(d,n)=>at(d,'artifacts/G001/'+n);
const dirs=['thermal_balance_v1','thermal_balance_v2','capacity_power_v1','pipeline_thermal_v1'];
const receiptFiles=dirs.map(d=>g(d,'FIT_RECEIPTS.jsonl'));
const pins=[__filename,...receiptFiles,g('sustained_load_v1','SUMMARY.json'),...dirs.flatMap(d=>[g(d,'RESULT.json'),g(d,'AUDIT.json')]),g('thermal_review_v3','RESULT.json'),g('thermal_review_v3','AUDIT.json'),g('thermal_review_v3','FINAL_PROOF.json')];
const op={schema:'S26_EXISTING_DATA_REPORT_V3',utc:new Date().toISOString(),pins:pins.map(p=>({path:path.relative(R,p).replaceAll('\\','/'),sha256:sha(p)})),new_fit:0,new_policy_environments:0,new_RL:0,new_measurements:0};
fs.writeFileSync(path.join(H,'REPORT_OPERATION.json'),JSON.stringify(op,null,2)+'\n',{flag:'wx'});
const old=read(g('sustained_load_v1','SUMMARY.json')),p=read(g('capacity_power_v1','RESULT.json')),t=read(g('pipeline_thermal_v1','RESULT.json')),diag=read(g('thermal_review_v3','RESULT.json')),audit=read(g('thermal_review_v3','AUDIT.json'));
const counts=dirs.map((d,j)=>{const r=fs.readFileSync(receiptFiles[j],'utf8').trim().split(/\r?\n/).map(JSON.parse);return {dir:d,START:r.filter(x=>x.event==='START').length,COMPLETE:r.filter(x=>x.event==='COMPLETE').length,FAIL:r.filter(x=>x.event==='FAIL').length};});
const totals=counts.reduce((s,x)=>({START:s.START+x.START,COMPLETE:s.COMPLETE+x.COMPLETE,FAIL:s.FAIL+x.FAIL}),{START:0,COMPLETE:0,FAIL:0});
if(totals.START!==1456||totals.COMPLETE!==1454||totals.FAIL!==2||t.accuracy_gate_pass!==false)throw Error('Unexpected final lineage');
const low=old.rows.filter(r=>r.model==='LOW'&&r.policy==='ATC'&&['SHORT','LONG64','LONG256'].includes(r.input));
const lines=['# S26 작업량 확대·온도 보완: 기존 자료만으로 진행한 최종 로컬 판독','',
 '사용자 최신 지시: 추가 실측 없이 기존 자료만 사용한다. 새 기기 실행·설치·측정·RL은 0이다. 작업량은 128→512→2,048건, 공급 시간은 16→64→256초로 확장했다. CPU 대기를 발열로 중복 합산하는 문제가 확인되어 별도 전력·수동 열응답 후보를 구현하고 검증했다. **긴 실측 구간의 오차 검증을 통과하지 못해 기본 정책 엔진에는 채택하지 않았다.**','',
 '## 관측 시간·작업 시간·기저 소비','',
 '아래는 원 확대 실험 LOW 가정의 EDF=ATC 결과다. 전체 관측창에는 작업 전후 대기가 포함된다. 작업시간은 첫 요청 도착(35초)부터 마지막 AVAILABLE까지의 경과시간이며, CPU/GPU/NPU 실행시간을 합한 값이 아니다. 공급 시간의 마지막 구간에는 도착이 없어 작업 경과시간이 공급 시간보다 조금 짧을 수 있다. API 단위의 시뮬레이션 값이며 실기기 절대 J 인증이 아니다.','',
 '|요청 수|공급 시간(s)|전체 관측(s)|작업 경과(s)|전체 API-J|기저 API-J|기저 비중|전체 정시/도착|',
 '|---:|---:|---:|---:|---:|---:|---:|---:|'];
for(const r of low)lines.push(`|${r.n.toLocaleString('en-US')}|${r.duration_s}|${r.horizon_s}|${r.work_span_s.toFixed(2)}|${r.total_API_J.toFixed(2)}|${r.baseline_API_J.toFixed(2)}|${(r.baseline_fraction*100).toFixed(1)}%|${r.on_time}/${r.planned}|`);
lines.push('', '이 초기 이력에서 기존 모형의 기저는 0.66531697 API-W다. 기저를 뺀 소비는 79.58/322.35/1,301.75 API-J다. 긴 작업에서 기저 비중이 줄었지만 EDF와 ATC의 추가 차이는 0이었다. 같은 LOW에서 FIFO는 전량 정시를 유지하면서 전체 API-J가 더 낮았다. 작업량 증가만으로 제안 정책의 우위가 생긴다고 결론내리지 않는다.', '',
 '2,048건 LOW/ATC 분류 배정은 CPU333/GPU619/NPU584건(21.7/40.3/38.0%)이고 탐지 CPU512건은 따로 집계한다. 기존 G004의 같은 3슬롯 CENTRAL도 분류 CPU26.2/GPU36.4/NPU37.4%로 이미 분산되어 있었다. NPU 쏠림 해소를 새 성과로 주장하지 않는다. 혼잡 2,048건/64초에서는 미완료·일반 납기 손해가 있어 총소비만 비교하지 않는다.', '',
 '[확대 36조건·실패·공통 작업창·모든 정책 결과](experiments/sustained_load_v1/artifacts/G001/FINAL_REPORT_KO.md). 새 비교 36건 중 저장23/계산실패13, P0를 포함한 START42=저장28/보존실패14다. 봉인 후 파일 변경에 따른 pre-case SHA실패1 및 rollout horizon실패13을 보존했다. 미시작만 복구했고 실패 환경 재실행·대체seed는 0이다.', '',
 '## 과도한 온도의 원인과 수정 후보','',
 '기존 열식에도 지수 감쇠가 있다. 문제는 POST 단계의 CPU 대기 시간을 실제 발열 입력처럼 계속 누적하는 wall-time proxy와 그 범위를 벗어난 계수 적용이다. LONG64/CENTRAL/EDF 저장 0.5초 곡선 최고261.10℃ 중 POST proxy 항만219.74℃였다. 해당 필터 상태는 보정 AP 관측시점 최대의74.91배다. 기존 예측 전력도81.52 API-W로 공통 적격 실측 최대19.96을 넘었다. 냉각식만 바꿔도 이 전력을 넣으면 약197.25℃가 남았다.', '',
 '새 전력 후보는 CPU infer/입장/POST의 시간 합집합, 탐지 CPU 증분, GPU infer, NPU infer, owner 합집합의 5개 0~1 입력을 쓴다. 겹친 POST owner 3명을 CPU 3개처럼 더하지 않는다. 실제 core utilization을 식별한 것은 아니고, 대기가 전부 전력0이라고 가정하지도 않았다. 양의 열응답 두 개를 연결하여 입력이 유지될 때 유한한 평형으로 접근하고 제거되면 냉각하도록 했다. 온도 clamp·임의 스로틀링 온도·원하는 정책이 이기도록 하는 계수 조정은 없다.', '',
 '## 실측 검증: 통과한 계산과 통과하지 못한 정확도','',
 '같은208세션/25,975개 AP 관측점을 사용한 개발용 그룹 제외 검증이다. 각 외부 그룹의 전력·열 계수는 그 그룹을 제외하고 맞췄다. 기존 자료를 여러 단계에서 본 결과이므로 새로운 독립 최종 평가로 부르지 않는다. 아래 오차는 세션별 MAE의 평균이며 “256초 이후”는 해당 관측점이 있는37세션이다.', '',
 '|자료/관측 구간|세션|기존 AP MAE(℃)|실측 전력 입력 두 열응답(℃)|새 예측 전력→재보정 열응답(℃)|',
 '|---|---:|---:|---:|---:|');
for(const r of t.summary)lines.push(`|${r.category}${r.from_s?'·256초 이후':''}|${r.sessions}|${r.parent_MAE_C.toFixed(4)}|${r.measured_power_oracle_MAE_C.toFixed(4)}|${r.pipeline_MAE_C.toFixed(4)}|`);
lines.push('', '실측 미래 전력을 주면 두 열응답의 오차가 작아지지만, 이는 실제 정책의 미래 전력 예측이 아니다. 새 예측 전력에 맞춰 열응답을 재보정하면 전체·OLD·긴 구간에서 기존보다 나빠 사전 정확도 gate는 FAIL이다. 단일RC도 긴 구간 악화로 채택하지 않았다. 중간의 “새 전력+실측전력용 열계수” 조합은 긴 구간5.9941℃로 더 나빴고, 마지막 재보정에서2.3570℃까지 줄었지만 기존2.0617℃에는 못 미쳤다.', '',
 '|전력 검증 자료|세션|기존 MAE(API-W)|새 MAE(API-W)|기존 중앙 절대 J 상대오차|새 중앙 절대 J 상대오차|',
 '|---|---:|---:|---:|---:|---:|');
for(const r of p.power_summary)lines.push(`|${r.category}|${r.sessions}|${r.parent_MAE_API_W.toFixed(4)}|${r.MAE_API_W.toFixed(4)}|${(r.parent_median_abs_relative_J_error*100).toFixed(2)}%|${(r.median_abs_relative_J_error*100).toFixed(2)}%|`);
lines.push('', '전력도 전체 J 상대오차 중앙값 일부 개선만으로 채택하지 않았다. 순간 전력 MAE는 전체에서 조금 악화했고 OLD의 에너지 오차도 악화했다. 초기 느린 열상태와 기기 열완화/속도 제한, CPU 실행시간 및 새3자원 공동상태는 여전히 식별되지 않았다. 실제 AP 관측범위26~46.6℃는 검증 범위이며 물리적 안전 상한은 아니다. SKIN 상태값을 AP 스로틀링 규칙으로 바꾸지 않았다.', '',
 '## 저장 일정 고정 진단: 정책 재실행 결과와 구분','',
 '다음은 같은 과거 활동 시각·배정·응답시간을 고정한 재생이다. 새 전력과 마지막 열후보를 함께 적용하고 t0의 저장 AP로 초기화했다. 그 전의 잠재 열상태는 알 수 없어 t0에서 열응답 상태를0으로 두었다. 최고값은0.5초 저장 시각의 표본 최고이며 모든 시각의 최대라는 뜻이 아니다. 바뀐 온도에 따른 작업 속도·스케줄 재계산을 하지 않았으므로 정책 간 절감/납기 결과로 인용하지 않는다.', '',
 '|고정 과거 조건|기존 최고 AP℃|열식만 변경℃|전력+열후보 진단℃|기존 최고 API-W|새 최고 API-W|정책용 판정|',
 '|---|---:|---:|---:|---:|---:|---|');
for(const r of diag.rows)lines.push(`|${r.case}|${r.old_curve_peak_AP_C.toFixed(2)}|${r.thermal_only_peak_AP_C.toFixed(2)}|${r.diagnostic_pipeline_peak_AP_C.toFixed(2)}|${r.old_predicted_power_peak_API_W.toFixed(2)}|${r.diagnostic_capacity_power_peak_API_W.toFixed(2)}|UNSUPPORTED|`);
lines.push('', `진단값이46.6℃ 아래여도 통합 정확도와 새 공동상태 검증이 통과되지 않았으므로 정책용 온도는 null이다. 모든5입력을1로 영구 유지하는 수학적 극한에서는 평형이 ${diag.model_all_five_proxies_held_at_one.AP_equilibrium_C.toFixed(2)}℃다. 이는 검증된 실제 상태/기기 상한이 아니며, **유한한 평형식만으로 현실성 문제가 모두 해결되는 것은 아님**을 보여준다. 이 범위도 UNSUPPORTED이고 값 자체를 잘라내지 않는다.`, '',
 '## 보존·검증·현재 결론','',
 '|신규 보정 계보|fit START|완료|보존 실패|','|---|---:|---:|---:|');
for(const r of counts)lines.push(`|${r.dir}|${r.START}|${r.COMPLETE}|${r.FAIL}|`);
lines.push(`|합계|${totals.START}|${totals.COMPLETE}|${totals.FAIL}|`, '',
 `두RC의 비수렴2건은 identity/사유를 보존하고 재시도하지 않았다. 당시 parameter파일은 미저장이며 재계산해 채우지 않는다. 전력 JS/Python69,952점 최대차3.55e-15 API-W, 마지막 열 basis25,975점 최대차5.12e-13℃다. 이번 고정재생의 독립 Simpson/전력/평형/거절 검산${audit.checks.toLocaleString('en-US')}회 PASS(최대 Simpson 차${audit.max_independent_Simpson_error.toExponential(3)}). 계산 PASS는 물리 정확도 PASS가 아니다.`, '',
 '확대실험 이후 새 정책환경·RL·실기기 측정·환경예약은0이다. 원 G0043,240건과 원소스/모형/원자료·실패·소비원장을 보존했다. 추가48환경 예약/42START는 확대 실험 등록 당시 로컬 추적값이며 다른 작업을 포함한 최신 전역 잔여 예산으로 해석하지 않는다. 이번 계산은 소규모 저장 후처리로 Python/heavy worker를 추가하지 않았다. Git HEAD b0b1c7df1775fcae3ba2944ed5df6d800382b4cc 기준의 미커밋·미업로드 로컬 변경이다.', '',
 '**현재 결론:** 작업량 확대에서 기저 비중 감소는 확인했으나 정책 우위는 없었다. 비현실적 고온의 원인을 찾아 중복 집계를 줄이는 후보와 미지원값 거절 경로를 구현했다. 기존 자료만으로 새 장시간3자원 환경의 물리 정확도까지 입증하지는 못했다. 이 후보를 검증된 엔진처럼 사용하거나 새RL을 시작하지 않는다. 추가 실측 요청은 닫고 기존 자료만 사용하는 제약을 유지한다.', '',
 '재개 시 다음 최대3: (1) 기존 원자료에서 공유CPU 실행·대기와 열상태를 구분할 수 있는 관측의 정확한 범위 정리, (2) 새로운 근거 없는 전력/열 계수 탐색을 반복하기 전에 식별 가능성과 지원범위 판정부터 검토, (3) 유효성을 확보한 별도 등록 엔진에서만 새로운 정책 평가. 소비된 확대/보정 namespace는 재실행하지 않는다.', '',
 '[새 전력 모형·등록](experiments/capacity_power_v1/OPERATION.json) · [예측전력 구동 열후보·등록](experiments/pipeline_thermal_v1/OPERATION.json) · [고정 재생 결과·미지원 사유](experiments/thermal_review_v3/artifacts/G001/RESULT.json) · [검산](experiments/thermal_review_v3/artifacts/G001/AUDIT.json) · [이전 보고서 이력](THERMAL_REPAIR_REPORT_KO_V2.md)', '');
for(const x of op.pins)if(sha(path.join(R,x.path))!==x.sha256)throw Error('Report input changed');
const report=path.join(R,'THERMAL_REPAIR_REPORT_KO_V3.md');fs.writeFileSync(report,lines.join('\n'),{flag:'wx'});
writeProof();
function writeProof(){fs.writeFileSync(path.join(H,'REPORT_PROOF.json'),JSON.stringify({status:'EXISTING_DATA_REPORT_V3_COMPLETE',operation_sha256:sha(path.join(H,'REPORT_OPERATION.json')),report:{path:path.relative(R,report).replaceAll('\\','/'),sha256:sha(report)},fit_counts:counts,totals,new_fit:0,new_policy_environments:0,new_RL:0,new_measurements:0},null,2)+'\n',{flag:'wx'});}
console.log(JSON.stringify({status:'REPORT_V3_SAVED',report,totals}));
