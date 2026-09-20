# D1Check 현재 상태

- 갱신: 2026-09-20 / decoded 원인 분리 조사 진행 중. 시작 HEAD `15e244c`, clean 확인; A24 연결 정상.
- 현재 추가 증거: `C:/Users/LG/Documents/D1Check_Decode_Resolution/`. exact 모델 metadata·공식 MediaPipe 소스 확인, 동일 RGB/전처리 raw 재생 진단과 host generator 구현·검증 중. 새 task/backend PASS는 아직 없음.
- 현재 작업: `MODEL-02B-DECODED-GATE`. **SIM-01_INCOMPLETE**. 실제 simulation·formal workload 미실행.
- 브랜치: `feature/pre-simulation-ready-20260919`; 시작 HEAD `10e2a4b67e0cae59108217627993485a5388811b`. master 수정·push·PR·merge 없음.
- 상위 기준: PLAN 개정 4.4. [준비 계약·PROFILE 절차](SIM_01_PREPARATION.md), [probe 계약](MODEL_02B_PROBE.md), [두 작업 계약](MULTITASK_EXPERIMENT_PROTOCOL.md).
- 외부 증거 E: `C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/`. 최종 상세 보고서 `FINAL_REPORT.md`, 실기기 집계 `device_evidence_summary.json`, decoded 판정 `decoded_comparison.json`.
- 이전 복구·원본 보존 이력은 [PRE_SIMULATION_RECOVERY_20260920.md](PRE_SIMULATION_RECOVERY_20260920.md)와 `C:/Users/LG/Documents/D1Check_Recovery/resume_20260920_020615/`에 그대로 있다.

## GPU 진단과 지원 경계

- 기존 raw GPU timeout `fb8a750f-9b3d-4d03-8df9-e8c1410a4180`은 **미재현 / exact phase·원인 unknown**이다. 수정 완료·미지원·native hang으로 단정하지 않는다.
- 신규 단계별 진단 `e086578d-00f6-410d-becb-8715c6151ede`: 약 31초 안에 진행 event 115개·모든 phase 종료·artifact 8개·cleanup PASS. 263/263 GPU delegation/kernel 4회. 한계 120초 유지.
- UUID/manifest hash/elapsedRealtimeNanos/순서를 별도 journal에 매 event fsync한다. host 종료·force-stop 뒤에도 회수 가능하며 stale/replay/잘린 기록·시계 역행을 거부한다.
- raw 출력은 별도 f32le sidecar로 보존하고 기존 finalized artifact의 input/output hash와 대조한다. formal v1/diagnostic v2/calibration-v1/image-v3·공식 timer·8-file artifact 계약은 유지한다.

| 모델·경로 | CPU | GPU | 승인 범위 |
| --- | --- | --- | --- |
| EfficientNet raw | seed 0/1/2 수치 PASS | 동일 입력·full delegation·수치 PASS | raw 배선만; 이미지 task 품질·service 아님 |
| EfficientDet raw | seed 0/1/2 수치 PASS | 263/263·no fallback·수치 PASS | raw 배선만; decoded task 아님 |
| EfficientDet Tasks decoded | 실행·artifact 완료; host golden score 1건 실패 | 실행 완료; CPU 대비 label/box/score 실패; actual delegate unverified | 실제 task/profile GPU 후보에서 제외 |

- raw 6쌍에서 분류 3,000개·탐지 5,416,092개 원소의 tolerance 위반 0. 최대 절대오차 각각 6.10948e-7 / 9.41753e-6.
- 새 sample `cat_and_dog_2.jpg` SHA `85eb9ad2c6b0c397aa873faf97befc4a871d987cea822d9854617415778b6c8c`: host MediaPipe 1.0.1 CPU 3회 동일 cat/horse. Android CPU와 한 score 차이 0.0017070865 > 0.001. Android GPU는 horse/cat 순서와 box·score도 불일치.
- decoded GPU는 hang/timeout이 아니라 102.6초 probe 완료였다. 4회 runtime 생성은 각각 약 23~24.5초. Tasks 내부 옵션·decode·정밀도 차이는 원인 후보이며 raw GPU configuration 적용·full GPU를 주장하지 않는다.
- 일반 정확도는 미평가. 유효한 ground truth·품질 입력과 exact EfficientDet license/NOTICE는 아직 없다. 모델은 실행자가 원 URL에서 직접 확보하는 비배포 probe만 허용한다.
- 탐지 CPU + 분류 GPU는 가능한 축소 후보지만 탐지 CPU golden/품질과 adapter 승인 전에는 REDUCED_PASS가 아니다. tolerance·모델·runtime 변경은 자동 채택하지 않았다.

## 직접 실행·검증 버전

- A24 SM-A245N / Android 16 API 36 / MT6789 / arm64-v8a, 기존 고정 serial 한 대만 사용.
- 직접 실행 총 15세션 = GPU 진단 1 + raw 12 + decoded 2. 모두 3 cold + 1 warmup + 10 warm, host artifact/cleanup 완료. decoded 의미 gate 실패를 실행 성공과 구분한다.
- 원격 기존 artifact 41파일 hash 불변, 신규 15세션 입력 부재·probe process 부재 확인. 이전 formal/분석/S26 데이터는 건드리지 않았다.
- sampled per-process peak PSS 최대 263,978 kB. 약 2초 간격 표본이며 연속 true peak·장치 전체 memory·에너지가 아니다. 시작/끝 thermal 0, 배터리 29.6~30.8°C; service/thermal profile로 전용 금지.
- 실기기 최종 실행 APK `879f7c18b628bbc8a0fe5cff37ad61b629dd3f4a78ab9a435dde3e759a58b8ea`; exact source는 E/`compiled_source_879f7c18/`. 한 host context의 미빌드 source 관측 차이는 원본 보존 후 `source_binding_correction.json`으로 분리했다.
- 최종 host 검증 APK `454bac9b49f995a78adac7fec5a860f8aaa789b783ab2a07a21d24e6ce07e98f`는 실제 close 실패를 finish 대신 failed로 기록하는 후속 진단 보강 포함. 이 최종 APK의 새 실기기 PASS는 주장하지 않는다.
- 최종 전체 검증: debug JVM 26 suites/119건, modelProbe JVM 20 suites/108건, 각각 failure/error/skip 0. 두 variant의 중복 테스트를 고유 테스트 수로 합산하지 않는다.
- Python 229건, failure/error 0, Windows symlink 권한 skip 2. lintDebug error 0/warning 76. compileall/logger self-test/diff check PASS.
- Gradle `--rerun-tasks` 295/295 실제 실행: debug/modelProbe unit·lintDebug·assembleDebug/modelProbe/release PASS. APK DEX/manifest/model 격리·hash PASS. debug/release에 probe/MediaPipe/외부 모델 없음.
- 검증 코드 기준은 `375a585` + close-failure 보강·simulation 준비 코드이며 E/`final_checks/verified_source_files.json`으로 특정한다. 명령별 JSON에 UTC·HEAD·dirty·exit를 기록했다.

## 작업 상태·다음 행동

| 작업 | 현재 상태 |
| --- | --- |
| 기존 SETUP/AUDIT/DIAGNOSTIC/DEFINE/CALIB-01A/B | 기존 완료 판정 유지; 새 모델 실측에 전용하지 않음 |
| CALIB-01C-INPUT | legacy 1001행 라벨/입력·열 gate 보류 |
| SCOPE-02 / MODEL-02A / RECOVERY | 기존 근거·조건부 승인·복구 완료 유지 |
| MODEL-02B | raw 통과, decoded/품질 미완료; 전체 FULL/REDUCED PASS 아님 |
| TASK-02 / PROFILE-02 | 실제 두 adapter·UI/영구 저장 ledger·service/전환/간섭/holdout 미구현·미실측 |
| SIM-01 준비 | draft JSON schema/validator·seed·정책 인터페이스·host KPI·deterministic no-op PASS; frozen service-profile schema 및 필수 실측 없음 |
| SCHED/EVAL/XDEV | 미실행; A24 정책 동결 후 최소 추가 Android 1대 원칙 유지 |

- deadline=`calibration_pending`, 안전/서비스/반복=`thresholds_pending`. no-op는 dispatch 0·가상 완료 0·비교 결과 null, 결과 INCOMPLETE다.
1. 기존 tolerance를 유지하며 탐지 decoded의 host/Android 및 CPU/GPU 전처리·runtime 옵션 동등성을 규명한다. 유효한 ground truth와 입력 출처를 확보해 CPU golden/품질 기준을 확정한다.
2. 검증된 탐지 CPU + 분류 GPU 축소 후보 또는 계약을 집행하는 decoded adapter를 근거로 결정한 뒤 TASK-02 실제 한 요청 완료부터 연결한다.
3. [PROFILE 절차](SIM_01_PREPARATION.md)에 따라 service/전환/허용 간섭·안전/holdout을 확보하고 frozen 입력·deadline을 검증한 뒤 SIM-01을 재판정한다.
