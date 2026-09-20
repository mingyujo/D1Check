# D1Check 현재 상태

- 갱신: 2026-09-20. 최종 **SIM-01_INCOMPLETE**. 현재 작업 `SERVICE-MODEL-FREEZE`의 후보 비교·검증/사전 기준·준비 입력은 구현했으나 독립 holdout과 제약 동결은 미완료다.
- 브랜치 `feature/pre-simulation-ready-20260919`. 최초 분석 시작 `c507f40`, 이번 재개 시작은 후속 분석까지 커밋된 `b6ae6a1` clean이다. 코드 checkpoint `a4460ea`, `80a1adf`. push/merge/rebase/master 전환 없음.
- 본 scheduling simulation·formal·정책 비교 미실행. 이번 새 실기기 session0. 기존31 session/233 profile 요청을 보존·재분석했다.
- 최신 재개 검증: `C:/Users/LG/Documents/D1Check_Decode_Resolution/service_model_recheck_20260920T125231Z/FINAL_REPORT.md`. 분석 원본: `C:/Users/LG/Documents/D1Check_Decode_Resolution/service_model_freeze_20260920T100651Z/FINAL_REPORT.md`.
- 저장소 요약: [SERVICE-MODEL-FREEZE](SERVICE_MODEL_FREEZE_20260920.md). 이전 [재개 결과](A24_RESUME_20260920.md), [decoded 수정](DECODE_RESOLUTION_20260920.md), 외부 기존 보고서는 그대로 보존한다.

## 모델·품질·capability

| Cell | 실제 backend/decoded | 기존 solo warm 평균 |
| --- | --- | ---: |
| classification CPU | PASS_EQ / actual CPU | 94.90ms |
| classification GPU | PASS_EQ / full GPU | 235.33ms |
| detection CPU | PASS_EQ / actual CPU | 554.97ms |
| detection GPU | PASS_EQ / full GPU | 1,068.72ms |

- canonical-srgb-png-v2 / canonical-srgb-q16-stretch-v2 / explicit-image-task-v2 / task-profile-v3. 20-image/cell, CPU↔GPU 직접40쌍 PASS_EQ. JPEG diagnostic 동일 tensor raw 비교는 별도1-image 범위다.
- JPEG decode·resize·PNG color 처리 및 외부 분류 golden 경로 혼용 수정은 이전 단계에서 완료했다. 이번 Android/decoder/모델 변경 없음.
- numerical/decoded 동등성, 실제 accuracy, scheduling quality preservation을 구분한다. 부분 GT15/28은 mAP/일반 품질 승인이 아니다. simulation accuracy를 임의 생성하지 않고 동일 모델/입력/전처리/decoder의 승인 cell만 허용한다.
- EfficientDet SHA40338edf...dbf58 유지. exact license/NOTICE 미확인, 기존 직접 확보·비배포 연구 probe 한정. 저장소/APK에 모델 없음. 기존 provenance와 host golden 계약 보존.
- A24는 관측한 solo에서 CPU 우세. CPU-only matched serial control이 없어 GPU 전체 지배 또는 긴급 응답/완료율 개선은 미입증. GPU cell은 제외하지 않는다.

## SERVICE-MODEL-FREEZE 결과

- 기존 실제31 session = profile29 + raw진단2. profile233/233 완료. 별도 host preflight 실패10계획을 포함한 시도 기준233/243=95.88%도 보존한다.
- calibration24 session/206요청, 과거 holdout4/20, 사후 warmup 진단1/7. 새 독립 holdout0. seed20260920과 전체 UUID를 `service_model_v1/split.json`에 기록했다.
- 6후보 비교의 임시 선택 `initial_state_mean`: cell별 cold 첫 호출/초기 직후/warm 분리. calibration LOSO MAE54.59ms/WAPE7.61%/interval coverage82.52%. 기준90% 실패. 과거 holdout WAPE3.71%/coverage90%는 독립 승인으로 사용할 수 없다.
- acceptance v1: calibration session 간 변동 Q95×2로 WAPE/분포 상대오차43.1914%, MAE432.808616ms; coverage≥90%, 지원율100%, 독립 반복/상태별 평가 필수. 넓은 engineering 기준이며 연구 정밀도 보장은 아니다. 과거 holdout에 소급 PASS를 주지 않는다.
- 기존74.57% 오차의 분류 CPU 두 번째381.316923ms를 보존한다. 첫 cold774.244ms와 별개다. 사후 두 번째195.28ms도 있어 안정성 미확정. JIT/GC 인과 미확인.
- 전환 prepare 분류CPU→GPU517.66/GPU→CPU24.63ms, 탐지1,135.42/504.23ms 각각1건. 이미 service에 포함, 중복 가산 금지.
- co-run/solo service비: 분류GPU0.905+탐지CPU0.992, 분류CPU1.022+탐지GPU0.988. 각각1 session, 동일 backend contention 미측정.
- thermal0에서만674표본, battery29.9~32.0°C, sampled peak PSS314,184kB. 후보 guard340,066kB/headroom25,882kB는 실제 최대나 승인 memory limit가 아니다.
- 준비 제약: fallback 금지, thermal0, 최대 in-flight1, 승인 co-run 없음. 품질 유지·전체 terminal states·다섯 baseline 인터페이스 동일 input hash. 기존 workload/seed/KPI/adapter 경계 유지.
- deadline=`calibration_pending`/null. service/response Q50/Q95 후보를 matched control과 공통 목표로 검증해야 한다. 모든 요청이 성공하도록 임의 deadline을 만들지 않는다.
- candidate model/hash·preparation input/hash·schema·validator·provenance·split·no-op 구현. **frozen service model은 발행하지 않았다.** no-op dispatch0/가상완료0/비교null.

## 검증·보존

- 재개 검증(2026-09-20 12:52 UTC 시작): `b6ae6a1` clean에서 targeted47/전체295건(293 PASS·기존 skip2), compileall·실제 schema·validator·no-op PASS. 모델/input hash 동일, Android source diff 없음·3개 APK SHA 불변. 새 Python/Android 변경 없이 문서의 재개 기준과 검증 연결만 갱신했다. 명령·시각·HEAD·source hash는 최신 외부 `receipts.json`/`audit.json` 참조.
- 새 targeted47건 PASS(서비스 모델37 + 관련10), 전체 Python295건(293 PASS/기존 skip2), compileall·schema·validator·no-op·실제 재생성 결정론 PASS. 대상은 `80a1adf` 코드 + 문서 변경, 명령/시각/source hash는 외부 receipt에 있다.
- 준비 input SHA `3840b437d8b2b8c704187b52f43f93e8c5c18aeade0a056ce743fad344bfdec6`, 후보 model SHA `300be49c35a191018ddb09479ba7c389ae6aeea3fcf39f3026b93dd16ba78f34`. 독립 승인/frozen hash가 아니다.
- source closure981파일과 이전 hash audit278파일 PASS. 재사용/누수/stale/실행 여부 불명 receipt 누락/fake no-op/입력 drift 거부 테스트를 포함한다.
- Android source/APK 불변을 이전278파일 hash audit와 연결한다. 기존 debug JVM119/modelProbe115, lint/build/logger/isolation PASS를 이번 재실행으로 기록하지 않는다.
- modelProbe APK SHA `8b805d3acfcede25fe6e4bcd17075d172c5ef66b425ff40ff29e2317ffce2489` 유지.
- formal v1/diagnostic v2/calibration-v1/image-v3/공식 timer/A24 80슬롯/S26/이전 raw·보고서 보존. 이번 기기 접근·임시 파일 삭제 없음.

## 다음 행동

1. 최소 calibration4 session: task별 전환1씩·co-run pair별1씩 보강. 간격/직후 호출·메모리 admission 부족 조건을 함께 관측하고 모델/기준/recipe v2를 새 holdout 전에 잠근다.
2. untouched holdout16 session(네 solo cell×2, 두 task 전환×2, 두 co-run pair×2) + CPU-only matched serial control2. 상세 최소22 session 설계와 반복 한계는 요약 문서 참조. 동일 backend 병행은 계속 금지한다.
3. 새 독립 오차·포함률·memory·deadline 판별력·품질 유지 계약을 충족할 때만 SIM-01 gate 재판정. 본 simulation/formal은 여전히 실행하지 않는다.
