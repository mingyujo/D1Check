'use strict';
// A synthesis of completed, audited stages; no further science executions.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),W=path.resolve(__dirname,'..'),S=path.join(W,'S26-D1Check/s26_simulator'),H=path.join(S,'experiments/a24_stable_learning_v1'),O=path.join(H,'artifacts/G001'),read=p=>JSON.parse(fs.readFileSync(p)),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),fmt=(x,n=3)=>Number.isFinite(x)?x.toFixed(n):'NA',s=read(path.join(O,'COMPARISON_SUMMARY.json')),proof=read(path.join(O,'FINAL_PROOF.json')),get=(load,m)=>s.summaries.find(r=>r.load===load&&r.method===m);
if(!proof.status.startsWith('PASS'))throw Error('Finish all new saved audits first');
const rr=s.rows.filter(r=>r.kind==='EVAL'&&r.variant==='REPAIR'),min=a=>Math.min(...a),max=a=>Math.max(...a),obs=rr.map(r=>r.observation_s),work=rr.map(r=>r.work_s),parent=read(path.join(S,'experiments/a24_policy_repair_v1/artifacts/G001/COMPARISON_SUMMARY_V2.json'));
const lines=['# S26 최종 결과와 원인 분석','','납기 보호를 제외한 A24 롤링+ATC+RL 구조를 S26 모형에 구현하고, 결과가 부족한 원인을 분석해 후보·예측 구간·초기 정책·학습 안정성·전력/열 보정을 순서대로 보완했다. **납기 성과는 단순 EDF보다 좋아졌지만, 큰 열·에너지 절감과 RL의 뚜렷한 추가 우위는 입증되지 않았다.**','',
'새 시뮬레이션768회(512+256), 추가 학습288회·144PPO update, 별도 전력/열 적합168회를 완료했다. 이번 두 정책 단계의 실행 실패는0이며 이전의 실패·원자료·체크포인트·원 보고서를 모두 보존했다. 아래 수치는 마지막 새 입력 평가80회의 전체 도착 기준이며 실제 기기 실측 성과가 아니다.','',
'## 최종 정시율','','|명목부하|단순EDF GPU우선|ATC|soft 살비지 ATC|보완 RL 3seed평균|','|---|---:|---:|---:|---:|'];
for(const g of s.grouped_by_load)lines.push(`|${100*g.load}%|${fmt(g.EDF_GPU_FIRST_on_percent)}%|${fmt(g.ATC_on_percent)}%|${fmt(g.ATC_SALVAGE_on_percent)}%|${fmt(g.REPAIR_on_percent)}%|`);
lines.push('', '조건당1,024요청·분류50/75%의2구성, 각 구성에서 같은 잠재 입력 흐름을 모든 정책에 적용했다. RL3seed는 공통 출발 가중치에서 새로 학습한3개이며 모든 부하에서 정시율이 같았다. 이들은 독립 실측 세션3개가 아니며 seed 범위를 통계적 신뢰구간으로 해석하지 않는다. 주 비교군은 미래예측이나 롤링 배정을 쓰지 않는 EDF다. soft ATC는 늦을 가능성을 점수에 부드럽게 반영한 강한 규칙 대조다.','',
'85%에서 RL−EDF는 '+fmt(s.grouped_by_load.find(g=>g.load===.85).REPAIR_on_percent-s.grouped_by_load.find(g=>g.load===.85).EDF_GPU_FIRST_on_percent)+'%p지만, 강한soft ATC 대비는 '+fmt(s.grouped_by_load.find(g=>g.load===.85).REPAIR_minus_SALVAGE_pp)+'%p다. 단순 EDF와의 큰 격차 전체를 RL만의 기여로 해석할 근거는 없다.','',
'## 과부하의 비용: 정시율과 지연 꼬리','','|부하|RL 긴급 정시율|RL 일반 정시율|EDF 세션P95 평균|RL 세션P95 평균|','|---|---:|---:|---:|---:|');
for(const g of s.grouped_by_load){const a=get(g.load,'REPAIR'),b=get(g.load,'EDF_GPU_FIRST');lines.push(`|${100*g.load}%|${fmt(a.urgent_on_percent)}%|${fmt(a.normal_on_percent)}%|${fmt(b.mean_case_P95_s)}s|${fmt(a.mean_case_P95_s)}s|`);}
lines.push('', '모든 요청은 AVAILABLE까지 완료했다. 높은 부하에서 이미 늦은 요청을 뒤로 미루면 더 많은 요청이 납기를 지킬 수 있지만 일부 요청의 대기가 길어진다. 105%는 그 상충이 뚜렷해, 정시율만 높다는 이유로 좋은 운용점이라 할 수 없다. 이번 조건에서85%는 납기와 꼬리지연을 함께 비교하기 좋은 구간이었다. 모든4부하를 보존했고 좋은 구간만 결과에서 고르지 않았다. P95는 세션별 응답완료 분포의 P95를 평균한 값이다.','',
'## 관측시간·작업시간·기저','','마지막 RL 평가의 관측시간은 '+fmt(min(obs))+'~'+fmt(max(obs))+'초, 첫 도착35초부터 마지막AVAILABLE까지의 작업경과는 '+fmt(min(work))+'~'+fmt(max(work))+'초다. 관측은 유휴·종료 뒤 냉각 구간을 포함한다. 작업경과는 CPU 합산 작업시간과 구분한다.','',
'초기 유휴 API전력 중앙값은0.5764 API-W, 후보 모형의 고정 기저항은0.703818 API-W다. 보고서의 기저 소비는 모형 고정항×같은 관측시간으로 계산했다. API-W/API-J는 외부 전력계로 보정한 절대W/J가 아니다.','',
'|부하|RL 모형 기저 비중|고정한 관측작업 완화하한과 소비 차이|대EDF 서비스 비악화 적격/6|적격 전체API-J 차이|적격 평균AP 차이|','|---|---:|---:|---:|---:|---:|');
for(const g of s.grouped_by_load){const e=s.energy_structure.find(e=>e.load===g.load);lines.push(`|${100*g.load}%|${fmt(e.mean_model_baseline_share_percent)}%|${fmt(e.mean_conditional_fixed_recorded_work_gap_percent)}%|${g.eligible_EDF}/6|${fmt(g.paired_EDF_API_J_delta_percent)}%|${fmt(g.paired_EDF_mean_AP_delta_C)}℃|`);}
lines.push('', '적격은 같은 입력·관측창, 양쪽 전량AVAILABLE, 전체·긴급·일반 정시 각각 비악화다. 현재 일정의 소비와 완화하한 차이는 같은 경로별 추론시간·CPU grant 작업량을 고정한 대수적 진단이다. 달성 가능한 절감률이나 모든 재배정·실제 기기의 전역 상한을 뜻하지 않는다. 큰 절감을 기대하려면 경로/실행시간/실제 전력 변화도 검증해야 하며, 시간과 요청 수를 늘리는 것만으로 에너지 격차가 커진다고 보장할 수 없다.','',
'## 원인별로 실행한 보완과 판정','','|분석 대상|실제로 실행한 보완|확인된 결과|','|---|---|---|',
'|작업량·평균부하|1,024요청에서40/65/85/105% 부하와2구성 비교|85%의 납기·P95가 함께 개선됐다.105%는 긴 지연 꼬리가 남았다.|',
'|후보 누락·예측 특징|종류/우선순위·오래된/새 요청을 포함한8행동대상,32요청 예측,국소 예측구간|첫512회에서85% 평균 +7.992%p였지만 긴급 손해·seed 변동으로 등록목표는 실패했다.|',
'|초기정책·학습 변동|이전EVAL 전에 DEV가 고른동일가중치에서3seed,기존LR와1/10 LR·minibatch KL중단 비교|3seed 정시율이 같아졌으나 두학습방식과 출발RL의정시율 차이는 모두0%p였다. 낮은LR의추가이득을입증하지못했다.|',
'|기저/누적소비·온도오차|관측기저 일치 후보84fit,세션 에너지 항 추가 후보84fit|일부최근자료 지표는좋아졌지만 전체·장시간 정확도 기준은 모두FAIL이었다.|',
'|소비 격차의 구조|22개 전력basis 적분,기저 분리,조건부고정작업 하한,30계수군 재생|순서와겹침만바꾸는진단에서는여유가작았다.계수군 범위는실기기인증/신뢰구간이아니다.|',
'|비교군·집계|단순EDF,ATC,soft ATC,출발RL고정,동등학습대조와전seed 보고|강한규칙도많은개선을냈다.첫전체평균필터오류는7.642619→7.387288%p로정정하고원본을보존했다.|','',
'## 남는 물리·자료 한계','','현재 M8 온도77세션의 최대 관측은211.682초이며256초 이후 세션은0이다. 장시간37세션은OLD 프로토콜이다. M8만 남겨 짧은 구간의 점수를 높여도400초대 예측의 검증 근거는 생기지 않는다.','',
'모형은 CPU/GPU/NPU 실행슬롯 각1개와 공유 CPU 서비스1서버를 가정한다. CPU 서비스시간, 미측정 자원쌍·triple 간섭, 지속 고부하 스로틀링의 실제S26전이는 검증하지 못했다. AP 관측범위26~46.6℃를 넘는 예측은 외삽이다. 수동 열평형 구조는 수학적 무한발산을 줄여도 실제 지속온도나 안전상한을 보장하지 않는다. 임의 온도clamp나 만들어낸 감속상수를 넣지 않았다.','',
'기기에서 수행할 예측·NN·제어의 실행시간과 전력도 측정하지 않았고, PC에서 걸린 계산시간을 가상의 휴대전화 비용으로 넣지 않았다. 분류=긴급·탐지=일반으로 연결된 자료여서 작업종류와 우선순위의 독립효과도 분리하지 못한다. 후속256회는CENTRAL만 평가했으며 이전LOW/HIGH 결과를 새가중치의 검증으로 전용하지 않는다.','',
'## 현재 기준과 보관','','조건부 연구 기준은 **보완 후보/예측 표현과 이미DEV에서 선정한 REPAIR481083 EP032 체크포인트를 보존**하는 것이다. 새 추가학습가중치를 기본엔진에 승격하지 않는다. 더 많은 RL학습만 반복할 근거를 이번 결과에서 찾지 못했다. 실제S26의 큰열·에너지절감/안전/정책우위 인증은 미완료다.','',
'Git 기반버전은b0b1c7df이며 이 결과는 로컬 미커밋·미업로드 상태다. 새실측·설치·자동예약·완료실험 재실행은0이다. 원자료·실패·모든체크포인트·원보고서와정정본을보존한다.','',
'[후속256회 전체 수치·P95·비용·자원사용](S26_STABLE_LEARNING_RESULTS_KO.md) · [앞512회 정정 보고](S26_POLICY_REPAIR_RESULTS_KO_V3.md) · [봉인 설계](experiments/a24_stable_learning_v1/PROTOCOL.json) · [후속 독립감사](experiments/a24_stable_learning_v1/artifacts/G001/FINAL_PROOF.json) · [최종 보존·해시 검증](../../recovery/S26_REPAIR_FINAL_VERIFICATION.json)','');
const target=path.join(S,'S26_FINAL_DIAGNOSIS_KO.md');fs.writeFileSync(target,lines.join('\n'),{flag:'wx'});const data={status:'SYNTHESIS_OF_COMPLETED_AUDITED_STUDIES',utc:new Date().toISOString(),report:{path:target,sha256:sha(target)},source_sha256:sha(__filename),stable_summary_sha256:sha(path.join(O,'COMPARISON_SUMMARY.json')),stable_final_proof_sha256:sha(path.join(O,'FINAL_PROOF.json')),parent_corrected_aggregate_pp:parent.aggregate_REPAIR_minus_BASE_pp,new_environment:0,new_training:0,new_fit:0,physical_validation:false};fs.writeFileSync(path.join(H,'SYNTHESIS_PROOF.json'),JSON.stringify(data,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(data));
