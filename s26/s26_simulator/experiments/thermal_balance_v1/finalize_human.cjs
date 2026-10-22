'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const HERE=__dirname,ROOT=path.resolve(HERE,'../..'),WORKSPACE=path.resolve(ROOT,'../..'),out=path.join(HERE,'artifacts/G001');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const write=(p,x)=>fs.writeFileSync(p,JSON.stringify(x)+'\n',{flag:'wx'});
const external=path.join(WORKSPACE,'recovery/S26_R21_THERMAL_STATUS_INVENTORY.json'),localInventory=path.join(HERE,'R21_THERMAL_STATUS_INVENTORY.json');
const inputs=[path.join(out,'FINAL_HANDOFF_PROOF.json'),path.join(out,'RESULT.json'),path.join(out,'MODEL.json'),path.join(out,'AUDIT.json'),path.join(HERE,'DOMAIN_DIAGNOSIS_V2.json'),path.join(HERE,'SERVICE_CONTRACT_PROOF.json'),external,path.join(ROOT,'experiments/sustained_load_v1/artifacts/G001/SUMMARY.json')];
const op={schema:'S26_THERMAL_HUMAN_REPORT_POSTPROCESS_V1',utc:new Date().toISOString(),source:{path:__filename,sha256:sha(__filename)},inputs:inputs.map(p=>({path:p,sha256:sha(p)})),new_fit:0,new_policy_environments:0,new_RL:0};
const r=read(inputs[1]),m=read(inputs[2]),a=read(inputs[3]),d=read(inputs[4]),service=read(inputs[5]),inventory=read(external),s=read(inputs[7]);
if(a.status!=='PASS_SAVED_REPLAY_AND_MATH_ONLY'||r.adopted!==false||r.deployment_gate_pass!==false)throw Error('Expected audited, unadopted measurement-only candidate');
write(path.join(HERE,'HUMAN_REPORT_OPERATION.json'),op);
fs.copyFileSync(external,localInventory,fs.constants.COPYFILE_EXCL);
const lines=['# S26 장시간 작업·열 모형 보완 결과','',
 '장시간 온도 상승의 주요 원인은 CPU 대기를 포함한 벽시계 구간을 발열 활동으로 외삽하는 구조다. 높은 온도나 큰 정책 차이를 실기기 성과로 채택하지 않는다. CPU 서비스 분리 코드와 실측 전력 구동 수동 열응답 후보를 별도로 구현·검증했다.','',
 '## 관측시간·작업시간·기저소비','',
 'LOW 가정·초기 이력0·단일 신규 stream에서 EDF=ATC다. 작업시간은 첫 도착35초부터 마지막 AVAILABLE까지다. 수치는 API 단위의 모형 결과이며 실제 물리 J 절감 인증이 아니다.','',
 '|요청|관측초|실제 작업초|총 API-J|기저 API-J|기저 비중|peak AP℃|',
 '|---:|---:|---:|---:|---:|---:|---:|'];
for(const id of ['SHORT','LONG64','LONG256']){const z=s.rows.find(x=>x.input===id&&x.model==='LOW'&&x.policy==='ATC');lines.push(`|${z.n}|${z.horizon_s}|${z.work_span_s.toFixed(2)}|${z.total_API_J.toFixed(2)}|${z.baseline_API_J.toFixed(2)}|${(100*z.baseline_fraction).toFixed(1)}%|${z.AP_peak.toFixed(2)}|`);}
lines.push('', '기저 비중은 줄었지만 EDF와 ATC 차이는 생기지 않았다. LONG256 ATC 분류 배정은 CPU21.7%/GPU40.3%/NPU38.0%다. 혼잡 조건의 낮은 에너지는 미완료/일반 납기 손해를 동반하므로 절감으로 판정하지 않는다.', '',
 '[모든36조건·실패·원장 결과](experiments/sustained_load_v1/artifacts/G001/FINAL_REPORT_KO.md). START42=저장28/실패14, 새 비교36 중23저장완료. 최초 봉인 후 report 수정에 따른 pre-case 실패1과 rollout horizon 실패13을 보존했다. 실패 환경 재실행/대체seed0. 저장 계산 감사 PASS는 물리 예측 인증이 아니다.','',
 '## 과도한 온도 예측의 원인','',
 'LONG64/CENTRAL/EDF 저장 곡선 최대261.10℃ 중 POST의 모형 기여가219.74℃다. POST tau16.67 상태는 보정 AP관측점 최대의74.91배다. POST벽시계 체류143.06 owner-s에 비해 모형상 CPU POST 서비스는0.986s였다. 기존에도 지수감쇠는 있으나 새로운 CPU 대기 상태가 기존 벽시계 proxy 영역을 크게 벗어난다. 이 항 분해는 칩의 실측 발열 분해가 아니다.','',
 '원 엔진은 CPU대기 중 작업 progress를 멈추지만 CPU INFER/POST wall-phase 활동은 계속 센다. 새 서비스 ABI는 CPU grant에만 CPU점유를 최대1로 주며 대기와 held slot을 분리한다. 실제 AVAILABLE까지 슬롯은 유지한다. GPU/NPU host추론 경계와 실제 코어 duty도 구별한다. 기존 벽시계 계수는 이 새 ABI에 재사용하지 않았다.','',
 `[서비스 구조/검사 증거](experiments/thermal_balance_v1/SERVICE_CONTRACT_PROOF.json): ${service.tests.checks}검사 PASS. [입력 외삽 진단 V2](experiments/thermal_balance_v1/DOMAIN_DIAGNOSIS_V2.json). 최초 V1 curve helper의 누락/null peak는 보존하고 V2에서 숫자 삼중항 ABI와 유한수 검사를 적용했다. 원 환경/fit/계수 변경0.`, '',
 '## 실측 전력 구동 열응답 후보','',
 '`dT/dt = -(T - (SKIN_initial + delta + G*(P_API - P_baseline)))/tau`, `G>=0`, `tau>0`다. 일정한 전력에서 유한한 평형으로 수렴하며 전력을 줄이면 냉각한다. 온도 clamp나 임의의 S26 감속 임계값은 넣지 않았다. SKIN초기값은 대용 경계이며 주변온도로 식별되지 않았고 API-W도 절대 물리 W로 인증되지 않았다.','',
 `공통 적격 ${r.included_sessions}세션을 사용해 ${r.fits}등록 fit을 완료했다. FULL tau=${m.tau_s}초, G=${m.gain_C_per_API_W.toFixed(6)}℃/API-W, delta=${m.delta_C.toFixed(6)}℃다.`, '',
 '|자료|세션|새 RC OOF MAE℃|원 AP OOF MAE℃|초기 AP 유지 MAE℃|','|---|---:|---:|---:|---:|');
for(const q of r.summary)lines.push(`|${q.category}|${q.sessions}|${q.RC_MAE_C.toFixed(4)}|${q.parent_MAE_C.toFixed(4)}|${q.anchor_MAE_C.toFixed(4)}|`);
lines.push('', '이미 본 자료의 그룹 제외 개발 OOF다. 측정된 미래 전력을 입력하는 진단이므로 배포용 미래 전력 예측 또는 새로운 독립 실기기 정확도로 부르지 않는다. 동일 정책 비용/시간을 다시 학습하거나 결과에 맞춰 계수를 고르지 않았다.','',
 `사전 정확도 gate: **${r.accuracy_gate_pass?'PASS':'FAIL'}**, 기본 식별 gate: **${r.basic_identification_gate_pass?'PASS':'FAIL'}**. 정책환경 채택 gate: **미충족, 후보 채택0**.`, '',
 `독립 JS/Python 저장 replay ${a.JS_replay_points.toLocaleString('en-US')}점 최대차 ${a.max_JS_python_error_C.toExponential(3)}℃, 별도 수치적분 최대차 ${a.max_quadrature_error.toExponential(3)}로 수학/계보 감사 PASS다.`, '',
 '## 채택하지 않은 이유와 다음 근거','',
 '수학적으로 유한한 RC도 입력 전력/상태가 잘못되면 비현실적인 평형을 낼 수 있다. 실제 서비스·대기에 맞춘 미래 전력 예측, 다중자원 상태/초기 이력의 지원범위, 기기별 열완화가 함께 검증되어야 한다. marginal 온도 범위 안이라는 이유만으로 전체 상태를 지원한다고 판정하지 않는다. 지원 밖은 UNSUPPORTED로 반환한다.','',
 `R21 원본 HAL ${inventory.rows.length}CSV의 유효 ${inventory.rows.reduce((v,x)=>v+x.valid_rows,0).toLocaleString('en-US')}행에서 skin_status는0이다. 이 기록은 AP·CPU/GPU/NPU의 감속 곡선 또는 무스로틀링을 식별하지 않는다. [원본 SHA/범위](experiments/thermal_balance_v1/R21_THERMAL_STATUS_INVENTORY.json).`, '',
 '[후속 검증 요구사항](experiments/thermal_balance_v1/THERMAL_VALIDATION_REQUIREMENTS.md)에 CPU서비스·전력·열상태/주파수·냉각 검증을 정리했다. 제조사/센서 정책을 확인하기 전 AP60/100℃를 공통 한계로 발명하지 않는다. [Android 공식 Thermal mitigation](https://source.android.com/docs/core/power/thermal-mitigation), [Thermal API](https://developer.android.com/games/optimize/adpf/thermal).', '',
 `이번 보완은 새 fit${r.fits}, 정책환경/RL/기기측정/환경예약0이다. 원 G004·확대 실험·실패는 보존했다. 현재 변경은 이 PC의 로컬 작업이며 GitHub에 업로드하지 않았다.`, '');
for(const p of op.inputs)if(sha(p.path)!==p.sha256)throw Error('Input changed');
const report=path.join(ROOT,'THERMAL_REPAIR_REPORT_KO.md');fs.writeFileSync(report,lines.join('\n'),{flag:'wx'});
write(path.join(HERE,'HUMAN_REPORT_PROOF.json'),{status:'HUMAN_REPORT_COMPLETED',operation_sha256:sha(path.join(HERE,'HUMAN_REPORT_OPERATION.json')),report:{path:report,sha256:sha(report)},new_fit:0,new_policy_environments:0,new_RL:0});
console.log(JSON.stringify({status:'REPORT_SAVED',report,fit:r.fits,accuracy_gate:r.accuracy_gate_pass,adopted:false}));
