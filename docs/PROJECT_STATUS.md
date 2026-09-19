# D1Check 현재 상태

- 갱신: 2026-09-20 / 강제 종료 복구 완료, MODEL-02B 후속 gate 미완료.
- 현재 작업: `MODEL-02B-GPU-DIAG` — A24 탐지 raw GPU의 bounded timeout 진단과 수치/decoded gate 진행. 새 진단은 성공했고 과거 원인은 미확정. `SIM-01 INCOMPLETE`; 시뮬레이션 본 실험·장시간 formal은 실행하지 않았다.
- 브랜치: `feature/pre-simulation-ready-20260919`. 최종 검증 코드 HEAD `3e5b685ad2888c50cb09b9be0ebfd8bf3ef6ca10`; 이후 변경은 문서다. master 수정·push·PR·merge 없음.
- 기준: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.4, [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md), [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md).
- 상세 판정·명령·수치·커밋·재개: [PRE_SIMULATION_RECOVERY_20260920.md](PRE_SIMULATION_RECOVERY_20260920.md).
- 외부 증거 E: `C:/Users/LG/Documents/D1Check_Recovery/resume_20260920_020615/`. 최초 diff/index/파일 복사, 명령별 JSON/stdout/stderr, XML/SARIF, source hashes, APK 감사, device context/artifact/cleanup/replay/보존 검증을 남겼다. 이전 상태 원문도 E의 `worktree/docs/PROJECT_STATUS.md`에 보존했다.

## 복구·검증 사실

- 최초 HEAD `f4a7f2a`의 미커밋 이동 7/7 대응. UTF-8/NUL 검사와 컴파일에서 부분 기록·절단 증거 없음. probe 중복·누락 없음.
- opt-in modelProbe/testModelProbe 격리·별도 applicationId·전용 Tasks 의존성을 복구했다. Android 저장 artifact 재검증, host 원격 fixed set/regular file·실패 identity·cleanup fault, CRCRLF 처리, Android filesDir 정규화를 보강했다.
- debug/release APK에는 probe·MediaPipe가 없고 modelProbe에만 있다. 모든 APK에 외부 두 모델/sample은 없으며 기존 MobileNet은 보존. 전이 INTERNET 권한은 제거·APK에서 부재 확인.
- JUnit 최종 probe targeted 1 suite/6 tests, debug 전체 26/119, failure/error/skip 모두 0. runner 97건은 rerun, 루트의 변경 없는 일부 task는 Gradle UP-TO-DATE이며 상세 보고서에서 구분한다.
- Python targeted 18건(skip 1), 전체 213건(skip 2), failure/error 0. skip은 Windows symlink 권한 제한. compileall·logger self-test exit 0.
- lintDebug error 0/warning 76. debug/modelProbe compile, debug/release/modelProbe assemble, APK 감사, host dry-run, diff check 통과. 정확한 검증 대상은 E의 `verified_source_files_final.json` 124파일과 명령별 HEAD/dirty로 특정한다.
- 코드 체크포인트: `aa1b9f0`(격리·artifact 복구), `852ff24`(ADB CRCRLF), `3e5b685`(Android output root 정규화). APK/keystore/cache/개인환경/실험 원본은 커밋하지 않았다.

## A24 직접 실행과 장애

- device ID `a24-sm-a245n-primary`, SM-A245N / Android 16 / API 36 / MT6789 / arm64-v8a. 고정 serial·fingerprint·RAM·ABI·배터리/충전·thermal·화면·저장공간·stale process·원격 기존 artifact를 사전 확인했다.
- 설치본 인증서와 프로젝트 `.android-user/debug.keystore`가 일치했다. 전역 키 충돌을 해소하고 기존 데이터 백업 뒤 uninstall/clear 없이 업데이트했다.
- 최종 smoke APK SHA-256: `1edd2fb16bd06473b46494adebbf20cf81c46df14800b5421025d2743c0d4547`.
- 최초 CPU session `ed8c1147-e91c-43dd-90e1-f3bcab54b54f`: output-root 검사 결함으로 추론 전 실패, host exit 2/timeout. 수정 전 실패 원본·cleanup 성공 기록 보존.
- 수정 후 CPU session `8f7258a7-ee6c-41d6-a510-28bd4ab1331c`: EfficientNet raw CPU 3 cold+1 warmup+10 warm 완료, 8-file/identity/hash/cleanup PASS, exit 0. CPU thread 설정 4, XNNPACK, 배터리 77%/30.7→30.7°C, thermal 0→0, 화면 off.
- GPU session `fb8a750f-9b3d-4d03-8df9-e8c1410a4180`: EfficientDet raw GPU host bounded timeout/exit 2. 263/263 GPU delegation·kernel 생성 로그는 있지만 완료 output 없음. GPU PASS·성능·CPU fallback으로 표시하지 않는다. 29.7→29.7°C, thermal 0→0. force-stop·입력 cleanup 성공, suppressed cleanup error 0.
- timeout의 정확한 native 호출 단계/원인은 미확정이다. 결과는 `MODEL_02B_FIX_REQUIRED(A24)`. 한계를 늘려 성공 처리하지 않았다.
- 실제 CPU session replay는 dispatch·ownership·삭제 전에 거부, 기존 summary 불변. 세 신규 시도 입력 부재·probe process 부재를 최종 확인했다. 결과 artifact는 E의 `new_probe_results/<session>/`에 있다.

## 작업 상태·시뮬레이션 gate

| 작업 | 상태 | 의미 |
| --- | --- | --- |
| SETUP-01 / AUDIT-A24-01 / DIAGNOSTIC-V2-01 / AUDIT-S26-01 | completed(기존) | 기존 측정·감사이며 새 작업 PASS로 전용하지 않음 |
| DEFINE-01 / CALIB-01A / CALIB-01B | completed(기존) | legacy 단일 모델 설계·host PASS; A24 이미지 calibration 완료 아님 |
| CALIB-01C-INPUT | 보류·재계획 | 기존 1001행 label·8이미지·host thermal gate 미완료 |
| SCOPE-02 / MODEL-02A / MODEL-02B-PREP | 기존 판정 유지 | 분류 host PASS, 탐지 비배포 연구용 conditional, 외부 probe 계약 |
| MODEL-02B-RECOVERY / HOST-EXEC-VERIFY | completed | 소스·host·APK·실제 CPU artifact/cleanup·실패/replay 검증 |
| MODEL-02B-DEVICE / 품질 | partial / FIX_REQUIRED | 탐지 GPU timeout, raw 수치 비교·새 decoded sample golden·peak memory 미완료 |
| TASK-02 / PROFILE-02 | pending, 선행 gate 부족 | 실제 사용자 완료/ledger 및 solo/transition/co-run full service·thermal profile 없음 |
| SCHED-02 / EVAL-02 / XDEV-02 | pending | 정책 동결·독립 A24 평가·추가 기기 재현 미실행 |
| SIM-01 | INCOMPLETE | simulation schema/validator/no-op·실측 profile·seed/반복/절대 deadline 미준비 |

- 새 deadline은 `calibration_pending`, 서비스 하한·안전/안정성·성공 기준·최종 반복 수는 `thresholds_pending`. probe 시간을 request service distribution으로 승격하지 않는다.
- B0/B1/B2/B3/P, task와 독립인 긴급/일반 등급, W-burst/W-sustain 등은 계획 정의이며 정책 구현·효과 입증이 아니다. 완료 P95와 전체 도착 기준 서비스율을 함께 평가한다.
- A24는 개발·주평가 기기. 정책 동결 후 최소 한 대의 추가 Android 기기에서 같은 계약으로 별도 profile·축소 재현한다. 성능/thermal 값은 기기별 재측정하며 S26 기존 자료로 대체하지 않는다.
- 모델 exact hash/labels/host golden은 [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md). EfficientDet exact binary license는 미확인; 실행자 원 URL 직접 확보·비배포 연구 probe만 허용, Git/APK/공유물 번들 금지.

## 보존과 다음 행동

- E의 `preservation_result.json`: A24 formal 834파일(기존 80-slot manifest hash 일치), 분석·diagnostic 40파일, S26 ZIP, 이전 probe 91파일, 기존 기기 artifact 33파일 불변 확인. 기존 v1/v2/calibration/image-v3/timer/main production 경로를 유지했다.
- 이전 `D1Check_Data/SIM-01_READY_20260919`의 이름은 READY 증거가 아니다. 그 원본과 이전 복구 E `resume_20260919_102344`는 보존했다. 당시 남았던 staging은 이번 사전 검사에서 부재였다.
1. `MODEL-02B-GPU-DIAG`: 단계별 monotonic 진행 기록으로 탐지 GPU timeout 위치를 확인하고, 기존 bounded gate 안에서 원인을 수정한다.
2. raw CPU/GPU 수치·decoded golden·품질/메모리 gate를 완료하고, 검증된 backend만 TASK-02 실제 완료 경계에 연결한다.
3. PROFILE-02 실측·독립 holdout과 deadline/seed/반복 동결, simulation 전용 schema/validator/no-op를 준비한 뒤 SIM-01을 재판정한다. 본 실험은 실행하지 않는다.

## 2026-09-20 GPU 진단 체크포인트

- 외부 증거: `C:/Users/LG/Documents/D1Check_GPU_Diag/run_20260920/`. 첫 진단 e086578d는 진행 기록 115개·미종료 phase 0·artifact 8개/cleanup PASS, 약 31초에 완료했다. 과거 timeout은 미재현이며 exact phase/원인은 unknown이다.
- raw 출력 보존과 고정 CPU/GPU comparator를 추가했다. 현재 seed 0/1/2 탐지, seed 0/1 분류가 수치 gate를 통과했으며 남은 분류 seed 2를 실행 중이다. 현재 APK `879f7c18b628bbc8a0fe5cff37ad61b629dd3f4a78ab9a435dde3e759a58b8ea`.
- JVM targeted 15건, progress/비교 Python 6건, simulation 준비 계약 Python 8건 PASS. 최종 전체 검증은 아직 실행 전이다.
- host 새 sample golden은 MediaPipe 1.0.1 CPU 3회 동일(cat/horse)이며 실제 정답 데이터가 아니다. 품질/전체 service profile/deadline은 미완료다.
