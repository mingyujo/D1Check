'use strict';
// Documentation changes only; scientific sources/results and earlier reports remain immutable.
const fs=require('node:fs'),path=require('node:path'),R=path.resolve(__dirname,'../S26-D1Check');
function replacePrefix(file,marker,prefix){const p=path.join(R,file),s=fs.readFileSync(p,'utf8'),i=s.indexOf(marker);if(i<0)throw Error('Missing marker '+file);fs.writeFileSync(p,prefix+'\n\n'+s.slice(i));}
replacePrefix('docs/PROJECT_STATUS.md','2026-10-17 22:21 KST 로컬 인계 확인:',`현재 사용자 요청: S26 작업량·시간 확대와 비현실적 온도 보완. **2026-10-18 추가 실측 없이 기존 자료만으로 진행**한다고 확정했다. [최신 전체 판독](../s26_simulator/THERMAL_REPAIR_REPORT_KO_V3.md). 아래 과거 인계·원 기준판 이력과 구분한다.

128/512/2048건·공급16/64/256초 확대를 완료했다. LOW/EDF=ATC 전체 관측180/228/420초, 작업 경과15.34/63.17/255.18초, 기저119.76/151.69/279.43 API-J(60.1/32.0/17.7%)다. 분류 NPU36.5/37.8/38.0%로 쏠림 해소/정책 우위는 미입증이다. 36조건 중23저장/13rollout실패, P0 포함42START=28저장/14보존실패다. SHA 운영실패1은 root agent가 봉인 후 report를 변경한 사건이며 미시작만 복구했고 failed retry/대체seed0이다. 원P0 실제정확5＋EDF128공개상태 귀납증거이며 원6개 전부 실제정상PASS는 아니다. [확대·전체정책·실패](../s26_simulator/experiments/sustained_load_v1/artifacts/G001/FINAL_REPORT_KO.md).

CPU대기 POST wall proxy가 LONG64/CENTRAL/EDF 저장곡선261.10℃ 중219.74℃를 차지했다. 기존 감쇠항은 존재하고 기존 예측전력81.52 API-W도 실측최대19.96을 넘었다. CPU서비스 분리ABI10검사와 합집합0~1 demand 전력/수동 두열응답 후보를 새 계보에 구현했다. 고정 과거 활동 재생에서는261.10→45.00℃·81.52→8.89 API-W지만 새 속도/배정/납기 재실행은 아니다.

동일208실측세션/25,975점에서 실측미래전력용 두열응답은 MAE0.6336℃였으나 배포 정확도가 아니다. 새 예측전력에 재보정한 마지막 열후보는 전체1.1752 vs기존1.1021℃,256초이후37세션2.3570 vs2.0617℃로 정확도gate FAIL/채택0이다. 전력209세션도 전체MAE0.8172 vs0.8121 API-W·OLD 에너지 상대오차 악화를 보존했다. 새 열후보가 유한 평형에 접근해도 현실성이 자동 보장되지 않는다. AP26~46.6℃는 검증범위이며 안전상한/스로틀링임계값이 아니다. 정책용 온도는 UNSUPPORTED/null, 임의 clamp/감속계수0다.

보정 계보 합계1456fit START/1454완료/비수렴2보존·재시도0. 기존 실패2parameter는 미저장이며 재수집하지 않는다. 전력 JS/Python69,952점 최대차3.55e-15 API-W, 열basis25,975점5.12e-13℃, 마지막 진단2,142검사/독립Simpson최대차1.54e-12 PASS다. 계산PASS는 물리검증PASS가 아니다. 확대 이후 새 정책환경/RL/기기측정/환경예약0, 로컬 미커밋·미업로드이며 모든 작업 종료다. 확대48예약/로컬추적125838/137712는 등록시 snapshot, 최신 전역census가 아니다.

다음 최대3: (1) 기존 원자료의 CPU 실행/대기·열상태 관측 범위/식별 가능성 정리, (2) 근거 없는 계수 탐색을 반복하기 전에 지원범위와 검증실패 원인 판정, (3) 유효한 별도 등록 엔진에서만 새 정책평가. 추가 실측 요청은 닫고 기존자료만 사용한다. 원소스/원모형/실패/원장/다른A24·PAUSED자동화는 보존한다. HEAD b0b1c7df1775fcae3ba2944ed5df6d800382b4cc+미커밋 변경을 원본CORE와 로컬 overlay/snapshot으로 구분한다.`);
replacePrefix('s26_simulator/START_HERE.md','최신 정본: **MULTI001_G004',`# 여기서 S26 작업을 재개한다

**2026-10-18 현재 PC의 후속 작업(미커밋·미업로드):** [최신 결과 V3](THERMAL_REPAIR_REPORT_KO_V3.md)부터 읽는다. 사용자 지시로 추가 실측 없이 기존 자료만 사용한다. 128/512/2048건·공급16/64/256초를 확장했고 LOW/EDF=ATC 작업15.34/63.17/255.18초, 기저비중60.1/32.0/17.7%다. 확대36조건 중23저장/13계산실패를 보존했다.

CPU대기 wall proxy/전력 중복 외삽을 진단하고 0~1 합집합 전력·수동 두열응답 후보를 구현했다. 고정 과거 활동에서261.10→45.00℃로 줄었지만 정책 재실행 결과가 아니다. 마지막 예측전력 구동 후보의 실측 검증은 전체MAE1.1752 vs기존1.1021℃,256초이후2.3570 vs2.0617℃로 gate FAIL/기본엔진 채택0이다. 실제 미래전력을 주었을 때의0.6336℃를 배포 정확도로 인용하지 않는다. 미지원 정책온도는 null이며 clamp/임의 스로틀링 규칙은 없다.

새fit1456/완료1454/실패2보존, 확대 이후 새정책환경/RL/기기측정/환경예약0. 모든 작업 종료다. 소비된 namespace를 재실행하지 않는다. 공개 CORE_MANIFEST 원본은 docs/history에 보존하고 로컬 문서 overlay와 새6개 실험 snapshot을 별도로 검산한다. 원 G004는 아래 공개 기준판이다.`);
replacePrefix('s26_simulator/STATUS.md','## 공개 인계 기준판',`# S26 현재 상태

## 현재 PC 후속 작업 — 기존 자료만 사용

- 사용자 2026-10-18 답변으로 추가 실측 없이 기존 자료만 진행한다. 기기 실행/설치/측정0이다. [최신 전체 결과 V3](THERMAL_REPAIR_REPORT_KO_V3.md). 모든 작업은 종료됐고 로컬 미커밋·미업로드다.
- [확대 전체표](experiments/sustained_load_v1/artifacts/G001/FINAL_REPORT_KO.md):128/512/2048건, 공급16/64/256초. LOW/EDF=ATC 관측180/228/420초·작업15.34/63.17/255.18초·기저119.76/151.69/279.43 API-J(60.1/32.0/17.7%). 작업시간은 첫도착부터 마지막AVAILABLE까지이며 자원별 실행시간 합이 아니다. 기저 비중 감소는 확인했으나 정책 우위/NPU쏠림 해소는 미입증이다.
- 36조건 중23저장/13rollout horizon실패, P0포함42START=28저장/14실패 보존이다. SHA 운영실패1은 root agent의 봉인 후 파일 변경 사건이며 미시작만 복구했고 failed retry/대체seed0다. 원P0 실제정확5＋EDF128공개상태 귀납증거로 원6개 전부 실제PASS는 아니다. 확대48예약/추적125838/137712는 당시 snapshot, 최신 전역census가 아니다.
- CPU대기 POST wall proxy가 LONG64/CENTRAL/EDF 저장곡선261.10℃ 중219.74℃다. 기존 감쇠항은 존재하며 예측전력81.52 API-W도 실측최대19.96을 넘는다. CPU서비스 분리ABI10검사, 합집합 demand0~1 전력과 수동 두열응답을 별도 구현했다. 고정 과거 활동 진단261.10→45.00℃·81.52→8.89 API-W는 새 정책/속도/납기 결과가 아니다.
- [전력 후보](experiments/capacity_power_v1/artifacts/G001/RESULT.json):209세션28fit완료. 전체MAE0.8172 vs기존0.8121 API-W, J상대오차 중앙13.58 vs14.64%이나 OLD는 악화다. [예측전력 구동 열후보](experiments/pipeline_thermal_v1/artifacts/G001/RESULT.json):208세션56fit완료, 전체MAE1.1752 vs1.1021℃·256초이후37세션2.3570 vs2.0617℃로 정확도gate FAIL/채택0다. 실측미래전력 입력 두열응답0.6336℃는 배포 정확도가 아니다.
- 보정fit합계1456START/1454완료/비수렴2보존·재시도0. 실패parameter는 미저장이며 재계산해 채우지 않는다. 전력69,952점 JS/Python차3.55e-15 API-W/열basis25,975점5.12e-13℃/마지막2,142검사 PASS다. 계산PASS와 물리검증은 별개다.
- [최종 고정재생·미지원 사유](experiments/thermal_review_v3/artifacts/G001/RESULT.json):정책용 온도 UNSUPPORTED/null, clamp/임의감속0. AP26~46.6℃는 검증범위이며 물리적 안전상한이 아니다. 모든5입력1의 평형89.76℃도 미지원이고 현실성 해결의 증거가 아니다. 실제CPU실행·공동상태·초기열·기기열완화가 미식별이다. 확대 이후 새정책환경/RL/실측/환경예약0.

다음 최대3: (1) 기존 원자료의 CPU 실행/대기·열상태 관측 범위와 식별 가능성 정리, (2) 새 근거 없는 계수 탐색을 반복하기 전에 지원범위/검증실패 판정, (3) 유효한 별도 등록 엔진에서만 새 정책평가. 추가 실측 요청은 닫고 기존자료만 사용한다. 원소스/실패/원장/다른A24·PAUSED자동화는 보존한다.

검증 대상: HEAD b0b1c7df1775fcae3ba2944ed5df6d800382b4cc+미커밋 후속6계보. 원CORE는 history에 보존하고 현재 문서overlay와 LOCAL_EXTENSION_MANIFEST에 새 파일을 구분한다.`);
const planPath=path.join(R,'docs/PROJECT_PLAN.md'),plan=fs.readFileSync(planPath,'utf8');
fs.writeFileSync(planPath,plan.replace('# D1Check 프로젝트 수정 실행계획','# D1Check 프로젝트 수정 실행계획\n\n2026-10-18 최신 확정: 사용자는 추가 실측 없이 기존자료만 진행하라고 답했다. 작업량128/512/2048건 확대와 별도 전력28/예측전력 구동 열56fit을 완료했다. 마지막 통합 후보는 전체1.1752 vs기존1.1021℃/256초이후2.3570 vs2.0617℃로 정확도gate FAIL·채택0다. 고정 과거활동261.10→45.00℃ 진단은 정책 재실행 결과가 아니다. fit총1456/완료1454/실패2보존, 확대 이후 새정책환경/RL/실측/예약0. 추가 실측 요청은 닫고 지원범위·식별 가능성을 기존자료로 판정하며 근거 없는 계수/스로틀링 상수를 만들지 않는다. [V3 판독](../s26_simulator/THERMAL_REPAIR_REPORT_KO_V3.md). 아래는 단계별 이전 계획 이력이다.'));
fs.appendFileSync(path.join(R,'docs/DECISIONS.md'),`\n\n## 2026-10-18 — 기존 자료만 사용·전력/열 통합 후보 미채택\n\n- 상태: 채택(자료 범위와 검증 판정); 후보 엔진 채택은 기각. 사용자가 추가 실측 없이 기존자료만 진행하라고 답했으므로 기기 실행/설치/측정0을 유지하고 추가 실측 가능 여부 질문을 닫는다.\n- 0~1 합집합 demand 전력28fit·예측전력 구동 두열응답56fit을 별도 봉인해 완료했다. 마지막 그룹 제외 검증은 전체1.1752 vs원1.1021℃,256초이후2.3570 vs2.0617℃로 정확도gate FAIL이다. 실측미래전력용0.6336℃를 실제 정책 정확도로 전용하지 않는다.\n- 고정 과거 활동 진단은261.10→45.00℃였으나 속도/일정/납기 재실행은 아니다. 새 공동상태 미검증과 정확도gate FAIL로 정책온도 UNSUPPORTED/null을 반환한다. 수학적 평형89.76℃도 현실성 해결의 증거로 인용하지 않는다. clamp/임의 스로틀링 온도/물리계수 승격0다.\n- 보정총1456fit START/1454완료/비수렴2보존·재시도0, 확대 이후 새정책환경/RL/실측/환경예약0. 원소스·원결과·비수렴parameter미저장·실패identity와 소비원장을 보존한다. 지원범위와 관측에 의한 식별 가능성 판단을 다음 단계로 둔다.\n- 근거: [최신 V3 보고서](../s26_simulator/THERMAL_REPAIR_REPORT_KO_V3.md), experiments/capacity_power_v1·pipeline_thermal_v1·thermal_review_v3의 봉인·원장·감사.\n`);
console.log('S26 existing-data-only status, plan and decision updated');
