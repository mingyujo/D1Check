'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),HERE=__dirname,ROOT=path.resolve(HERE,'../..'),O=path.join(HERE,'artifacts/G001');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'),write=(p,v)=>fs.writeFileSync(p,JSON.stringify(v)+'\n',{flag:'wx'});
const files=[__filename,path.join(O,'RESULT.json'),path.join(O,'MODEL.json'),path.join(O,'AUDIT.json'),path.join(O,'PROFILES.json'),path.join(O,'FINAL_PROOF.json'),path.join(O,'FIT_RECEIPTS.jsonl'),path.join(HERE,'SAVED_POWER_RESULT.json'),path.join(ROOT,'THERMAL_REPAIR_REPORT_KO.md')];
const op={schema:'S26_THERMAL_REPORT_V2_POSTPROCESS',utc:new Date().toISOString(),pins:files.map(p=>({path:p,sha256:sha(p)})),new_fit:0,new_policy_environments:0,new_RL:0};
write(path.join(HERE,'REPORT_OPERATION.json'),op);
const r=read(files[1]),m=read(files[2]),a=read(files[3]),profiles=read(files[4]),p=read(files[7]);
if(a.status!=='PASS_SAVED_REPLAY_AND_MATH_ONLY'||r.adopted!==false)throw Error('Expected audited unadopted candidate');
const failures=fs.readFileSync(files[6],'utf8').trim().split(/\r?\n/).map(JSON.parse).filter(x=>x.event==='FAIL');
const full=profiles.find(x=>x.group===null),profile=Object.fromEntries([...new Set(full.fits.map(x=>x.tau_slow_s))].map(t=>[t,Math.min(...full.fits.filter(x=>x.tau_slow_s===t).map(x=>x.train_MSE))]));
const lines=['# S26 작업량 확대와 열 모형 보완 — 최신 로컬 결과','',
 '과도한 고온의 주요 원인은 대기를 포함한 wall-phase 활동과 전력의 외삽이다. 온도 상한을 씌우지 않고 CPU 서비스 입력을 분리했으며, 실측 전력 구동의 두 수동 열응답 후보를 개발 검증했다. 정책환경의 현실성/우위는 아직 입증하지 않았다.','',
 '## 새 두 시간상수 후보','',
 '|자료/구간|세션|원 AP MAE℃|단일 RC MAE℃|두 RC MAE℃|','|---|---:|---:|---:|---:|'];
for(const x of r.summary)lines.push(`|${x.category}${x.from_s?'·256초 이후':''}|${x.sessions}|${x.parent_MAE_C.toFixed(4)}|${x.single_RC_MAE_C.toFixed(4)}|${x.two_RC_MAE_C.toFixed(4)}|`);
lines.push('', '같은208실측세션/25,975관측점, 이미 본 자료의 그룹 제외 개발 OOF다. 실제로 측정된 미래 전력을 입력하므로 배포용 미래 예측 정확도가 아니다. 전체 평균/OLD/M8/R21 및256초이상에서 원 AP·단일RC보다 나쁘지 않은 사전screen은 PASS다.', '',
 `FULL fast/slow tau=${m.tau_fast_s}/${m.tau_slow_s}초, 초기 fast비중=${m.w_fast}, Gf/Gs=${m.gain_fast.toFixed(6)}/${m.gain_slow.toFixed(6)}℃/API-W. **느린tau가 탐색 상한320초, 초기비중이 경계1**이므로 물리 열상수/초기 느린열 상태가 식별됐다고 부르지 않는다. 더 큰tau를 사후 선택해 결과를 바꾸지 않았다.`, '',
 `두RC fit START${r.fit_START}/완료${r.fit_COMPLETE}/실패${r.fit_FAIL}; 단일RC와 합친 새fit1372/완료1370/실패2다. 실패는 KKT 비수렴 identity/사유를 보존했고 재시도하지 않았다. 비수렴 두fit의 parameter 파일은 저장되지 않았으며 이를 재계산해 채우지 않는다. JS/Python독립 replay ${a.points.toLocaleString('en-US')}점 최대차${a.max_JS_python_error_C.toExponential(3)}℃, ${a.checks.toLocaleString('en-US')}검사 PASS. 수학 검산은 실기기 독립 검증이 아니다.`, '',
 '## 열식만 바꾸어서는 충분하지 않음','',
 `기존 저장 전력 경로의 최대81.52 API-W는 공통 적격 실측 최대${p.limits.power_API_W[1].toFixed(2)} API-W를 크게 넘는다. 그 전력을 두RC에 그대로 넣으면 고온이 남는다. 아래는 과거 일정·완료량을 고정한 진단이며 재실행한 정책 결과가 아니다. 전력은0.5초 저장곡선 사이를 보간하고 t0에서 새 열상태를 초기화했으므로 상세값도 진단용이다.`, '',
 '|고정 과거 조건|기존 peak AP℃|두RC 진단 peak℃|예측 peak API-W|정책용 값|','|---|---:|---:|---:|---|');
for(const x of p.rows)lines.push(`|${x.case}|${x.old_curve_peak_AP_C.toFixed(2)}|${x.diagnostic_two_RC_peak_AP_C.toFixed(2)}|${x.predicted_power_peak_API_W.toFixed(2)}|UNSUPPORTED|`);
lines.push('', '열모형이 수학적으로 안정해도 잘못된 전력 입력에서 현실적인 온도를 보장하지 않는다. 이 진단은 정책용 온도값을 null로 반환한다. LOW의 수치도 새 triple/지속부하를 검증한 것은 아니다. 기존 큰 온도/소비 차이로 정책 우위를 인정하지 않는다.', '',
 '## 현재 판정','',
 '두RC 개발 정확도 screen PASS, 기본 엔진/정책환경 채택0이다. CPU 실행·대기를 분리한 전력 예측, 초기 열상태·다중자원 공동 지원, 기기별 thermal severity/속도 제한이 남아 있다. 새 정책환경/RL/기기측정/환경예약0이다. 추가 실측 가능 여부를 사용자에게 확인 중이며 답변 없이 기기 측정을 시작하지 않는다.', '',
 '[후속 검증 요구사항](experiments/thermal_balance_v1/THERMAL_VALIDATION_REQUIREMENTS.md), [두RC 등록](experiments/thermal_balance_v2/OPERATION.json), [수치·원장 감사](experiments/thermal_balance_v2/artifacts/G001/AUDIT.json), [저장전력 진단](experiments/thermal_balance_v2/SAVED_POWER_RESULT.json).', '',
 '## 단일 RC 단계와 작업량 확대 결과 이력','',
 fs.readFileSync(files[8],'utf8'), '');
for(const x of op.pins)if(sha(x.path)!==x.sha256)throw Error('Pin changed');
const report=path.join(ROOT,'THERMAL_REPAIR_REPORT_KO_V2.md');fs.writeFileSync(report,lines.join('\n'),{flag:'wx'});
write(path.join(HERE,'REPORT_PROOF.json'),{status:'LATEST_REPORT_SAVED',operation_sha256:sha(path.join(HERE,'REPORT_OPERATION.json')),report:{path:report,sha256:sha(report)},full_profile_best_MSE_by_slow_tau:profile,failed_fit_receipts:failures,new_fit:0,new_policy_environments:0,new_RL:0});
console.log(JSON.stringify({status:'LATEST_REPORT_SAVED',report,failed_fit_receipts:failures,full_profile_best_MSE_by_slow_tau:profile}));
