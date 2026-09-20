# D1Check 현재 상태

- 갱신: 2026-09-20. 최종 **SIM-01_INCOMPLETE**. 연결 복구·decoded gate 완료, 연구 기준/서비스 모델 동결은 미완료.
- 브랜치 feature/pre-simulation-ready-20260919. 재개 시작 adb5c38 clean, host 코드 checkpoint 8d56f36/d482ac8. push/merge/rebase/master 전환 없음.
- 현재 작업: MODEL-02B 최종 색상 계약 PASS_EQ → TASK-02/PROFILE-02 bounded 준비. 본 scheduling simulation·장시간 formal·정책 비교 미실행.
- 외부 E: C:/Users/LG/Documents/D1Check_Decode_Resolution/resume_20260920T090545Z/. 새 FINAL_REPORT.md, simulation_input_provenance.json, final_device_receipt.json.
- [재개 상세](A24_RESUME_20260920.md). 이전 ../FINAL_REPORT.md와 raw/분석/모델 보존. 연결 단절 blocker는 해소됐다.

## 원인과 수정

- 이전 JPEG RGB decode·Tasks CPU/GPU resize·PNG iCCP 차이는 [기존 조사](DECODE_RESOLUTION_20260920.md)에 보존.
- canonical-srgb-png-v2 / canonical-srgb-q16-stretch-v2 / explicit-image-task-v2 / task-profile-v3를 실제 A24에서 검증했다.
- 재개 시 외부 runner와 분류 golden의 새 manifest/이전 PNG 경로 혼용을 추가 발견. 첫 분류 CPU 비교 1/10 실패를 보존했다.
- 새 tools/d1_classification_reference.py는 실제 bytes/hash 결합·tensor metadata·3회 raw 재현성·raw 파일을 기록한다. 올바른 새 golden과 기기 결과는 일치한다.
- artifact validator는 v3 raw hash 개수/형식·task/timing/geometry·cold 전환을 검증한다. false warm으로 GPU delegate 증거를 생략할 수 없다.
- threshold/tolerance 완화·silent CPU fallback·모델 교체 없음. host golden은 ground truth가 아니다.

## A24 capability와 품질

| Cell | 최종 20-image 계약 | 원래 solo warm 평균 |
| --- | --- | ---: |
| classification CPU | PASS_EQ / actual CPU | 94.90ms |
| classification GPU | PASS_EQ / full GPU 확인 | 235.33ms |
| detection CPU | PASS_EQ / actual CPU | 554.97ms |
| detection GPU | PASS_EQ / full GPU 확인 | 1,068.72ms |

- host↔A24 input tensor/decoded 일치, CPU↔GPU 직접 40쌍 PASS. 새 JPEG diagnostic 동일 tensor raw/decoded CPU↔GPU 및 host↔CPU도 PASS.
- 20-image raw hash와 새 1-image raw 원소별 비교의 범위를 구분한다. 품질·formal 안정성 승인으로 확대하지 않는다.
- Open Images 공식 부분 주석: CPU/GPU 각 15/28 bbox, Car 0/4. 작은 5-class 표본이고 mAP/일반 정확도·품질 승인 아님.
- EfficientDet SHA40338edf...dbf58 유지. exact license/NOTICE 미확인, 기존 직접 확보·비배포 연구 probe 한정. Git/APK에 모델 없음.
- 이 pilot은 두 작업 모두 solo CPU가 빠르다. GPU 배정 또는 heterogeneous scheduling의 이득을 전제하지 않는다.

## 완료한 bounded 측정·준비

- 실제 31 session: correctness8, 원래 solo8, transition2, matched solo4, co-run2, holdout4, 후속 warmup 진단1, raw 진단2. 별도 host preflight 실패 UUID1.
- profile 29 session/233도착 모두 완료. host 미실행 계획10건도 포함한 시도 기준은 233/243=95.88%. 완료 응답 P95 11,138.01ms는 혼합 진단 기록이며 정책 결과 아님.
- CPU→GPU/GPU→CPU prepare: classification517.66/24.63ms, detection1,135.42/504.23ms. 방향당1건, service에 포함하므로 중복 가산 금지.
- co-run/matched solo 평균비: classification GPU0.905 + detection CPU0.992; classification CPU1.022 + detection GPU0.988. 실제 overlap 확인, 안정적 간섭표는 아님.
- 500ms 환경 표본674개, sampled peak PSS314,184kB, thermal status0, 배터리29.9~32.0°C. 연속 true peak·에너지·스로틀링 부재 주장 아님.
- 원래 holdout warm 최대 상대오차: classification CPU74.57%/GPU7.67%, detection CPU3.43%/GPU0.94%. 오차 하한/수용 gate 미동결.
- 분류 CPU 두 번째 요청381ms, inference34.5ms. 추가2-warmup 진단의 같은 holdout97~108ms. 초기 호출 상태 영향 근거이며 JIT/GC exact 원인 미확정. 원래 오차를 삭제하지 않았다.
- 실제 adapter/완료 경계, workload/validator/seed, B0/B1 결정 함수 및 B2/B3/P 인터페이스, KPI 계약 준비. 실제 측정→simulation input provenance 연결 완료.
- no-op: dispatch0/가상완료0/비교null, 결정론 PASS. deadline=calibration_pending; frozen service schema·품질·holdout 수용·공통 제약/반복/평가 동결 pending.

## 검증과 보존

- host 최종 전체 Python258건, 실패/오류0·기존 skip2. targeted17건, compileall, JSON Schema2개, artifact/입력/hash278파일, no-op, diff check PASS.
- Android source/APK 불변: 기존 debug JVM119/modelProbe115, lint0error76warning, debug/modelProbe/release build·logger self-test·isolation PASS에 hash로 연결. 이번 재실행으로 기록하지 않는다.
- 설치 APK8b805d3...ce2489 원격 hash 확인. 마지막 프로젝트 process 없음, 모든 own input/shared staging 없음, 기존 probe161파일 hash 불변.
- 이전 설치 host 임시 part00~04는 APK와 byte 일치 확인 후 E/prior_owned_install_chunks.zip에 hash 검증 보존하고 원래 임시 파일만 정리했다.
- host ADB daemon 사전조회1회 실패는 bounded 복구 후 새 UUID. co-run start 응답 중 연결 단절은 재실행 없이32.24초 완료 artifact 회수·검증·정리. 명령 실패/복구 기록 보존.
- formal v1/diagnostic v2/calibration-v1/image-v3/공식 timer/A24 80슬롯/S26/이전 보고서 보존.

## 다음 행동

1. 실제 품질 수용 목표·독립 holdout 오차/안정성·공통 제약·반복 기준을 연구 계약으로 사전 동결한다. 관측값에 맞춰 임계값을 임의로 정하지 않는다.
2. cold boolean만으로 안정적 warm을 가정하지 않는 초기 호출/시간 상태의 서비스 모델을 검증하고, 별도 calibration으로 동결 기준을 평가한다.
3. frozen service profile·실측 근거의 deadline을 준비 입력에 연결해 SIM-01 gate 재판정. 본 simulation/formal은 별도 승인 전 실행하지 않는다.
