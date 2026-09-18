# D1Check 현재 상태

- 갱신: 2026-09-18 / MODEL-02B-SEAM 구현과 사용자 로컬 Android·Python 전체 검증 결과 반영
- 현재 작업: `MODEL-02B-HOST-EXEC` — `MODEL-02B-SEAM`의 debug-only 외부 모델 loader, raw/decoded adapter, host validator·no-I/O dry-run은 사용자 로컬 JDK 17에서 전체 Gradle과 Python 회귀를 통과했다. 다음 gate는 실제 subprocess·ADB ready/wait/pull/cleanup·delegate-log finalization이며, A24 실기기 PASS는 아직 아니다.
- 기준: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.4, [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md), [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md), [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)(설계, 미구현).
- 코드 기준: [초안 PR #2](https://github.com/mingyujo/D1Check/pull/2)의 `docs/competition-plan-v4-20260917` HEAD `177a8f3e9bf2a2091f383444767b7cb49cdf8c66` 위에 별도 stacked 구현 초안으로 진행한다. master에 자동 병합하지 않는다.
- A24와 추가 기기 실행은 아직 승인·수행하지 않았다. model/sample binary는 저장소·PR·APK에 포함하지 않았다.
- A24는 개발·주평가 기기다. 정책 동결 뒤 최소 한 대의 다른 Android 기기에서 같은 runner로 축소 재현평가한다. 추가 기기는 아직 미선정·미실행이며, 기존 S26 formal은 새 두 작업 재현평가를 자동 대체하지 않는다.
- 새 절대 deadline: `calibration_pending`. 서비스 하한·안전/안정성 수치·성공 기준·최종 반복 수: `thresholds_pending`.

## 완료와 미완료의 구분

| 작업 | 상태 | 해석 |
| --- | --- | --- |
| SETUP-01, AUDIT-A24-01, DIAGNOSTIC-V2-01, AUDIT-S26-01 | completed(기존 기록) | 측정 기반·기존 자료 감사 |
| DEFINE-01, CALIB-01A | completed(기존 정의) | 단일 분류 시나리오·legacy protocol. 새 주평가는 개정 4.4로 대체 |
| CALIB-01B | completed / CALIB_01B_PASS | MobileNet production·host 검증. 두 작업/실기기/정책 효과 PASS가 아님 |
| CALIB-01C-INPUT | legacy 준비 보류·재계획 | 기존 모델 1001행 라벨과 이미지 입력 미확정. 완료 처리하지 않음 |
| PLAN-REV04.4 / SCOPE-02 | 문서 개정·근거 조사 완료 | 혼합 요청 범위, 합성 workload 가정, 선행 연구와 증거 경계, A24 주평가+추가 기기 무재튜닝 재현 계약 확정 |
| MODEL-02A 분류 | HOST_CONTRACT_PASS | EfficientNet-Lite0 v1 source/hash/tensor/내장 labels/license·고정 host output 확인; 실기기 미검증 |
| MODEL-02A 탐지 | conditional pass / research-only | EfficientDet raw·decoded host golden 통과. exact binary license 귀속 미확인으로 승인 기기 내부 비배포 probe만 허용 |
| MODEL-02B-PREP | completed / `MODEL_02B_PREP_READY` | [MODEL_02B_PROBE.md](MODEL_02B_PROBE.md)에 기기 이식형 외부 manifest·staging·비교·cleanup·기기별 판정 계약 고정 |
| MODEL-02B-SEAM / MODEL-02B device | code validation PASS / device pending | 전체 Gradle·Python 회귀 통과. Android debug seam의 compile/test/lint/assemble은 확인했으나 실제 A24·추가 기기·delegate 증거는 미실행; binary 번들 금지 |
| TASK-02 / PROFILE-02 / SCHED-02 / EVAL-02 / XDEV-02 | pending | A24 adapter→full profile→정책→독립 평가 후 최소 한 대 추가 기기 축소 재현 |

## MODEL-02A 확인 사실과 남은 제한

- 정확한 파일·label·tensor·host output은 [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)에 기록했다. `/1/` URL을 고정했고 조사 시점의 `latest`와 byte-identical임을 확인했다.
- EfficientNet-Lite0 FLOAT32: 18,582,189 bytes, SHA-256 `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0`; FLOAT32 `[1,224,224,3] -> [1,1000]`; 내장 labels 1000행; metadata Apache-2.0; LiteRT CPU 3회 output hash 동일.
- EfficientDet-Lite0 FLOAT32: 13,836,895 bytes, SHA-256 `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58`; score `[1,19206,90]`·location `[1,19206,4]`; 내장 90행 중 10 placeholder; raw CPU 3회 동일. metadata license는 null이다.
- 대안 SSD MobileNetV2 FLOAT32도 11,316,189 bytes, SHA-256 `b8ccb1a25d45455ba52e85f26531948e1cb75efeb94c7c3d456d54fd4d6fbdd2`, 91행 background 포함 계약과 raw CPU 실행을 확인했지만 license가 null이다.
- Google 공식 안내는 EfficientDet-Lite0 FLOAT32를 내려받아 프로젝트에 저장하도록 안내하고 공식 Apache-2.0 sample은 위 고정 v1 URL을 직접 사용한다. TensorFlow/Kaggle EfficientDet variants도 Apache-2.0이지만 내려받은 공식 metadata TFLite는 SHA-256·dtype·출력 계약이 달라 exact GCS binary의 license 증거로 전용하지 않는다.
- exact GCS binary 주변 bucket에는 LICENSE/NOTICE가 없고 metadata license도 null이다. 따라서 법적·재배포 승인이 아니라 **비배포 연구 평가에 대한 프로젝트 위험 수용**으로만 조건부 통과시켰다. binary는 저장소·PR·APK·팀 ZIP에 넣지 않으며 배포 전에는 exact license/NOTICE 또는 모델 교체가 필요하다.
- host `libGLESv2.so.2`는 임시 외부 system library로 해결했다. MediaPipe Tasks 1.0.1 CPU XNNPACK, score threshold 0.5, 공식 `cat_and_dog.jpg`(69,041 bytes, SHA-256 `cfa90c34bb93021165e48bd22cfc20dbbb0440ff638a54878939bf30d362e824`)를 같은 detector에서 3회 실행해 decoded canonical hash `83de431de773572d37ad8849bbca261ae92995fa6208f950823ccfbd40d60413`과 cat/dog 2개 결과가 동일함을 확인했다. host 시간은 A24 수치로 사용하지 않는다.
- 모델 binary와 host 산출물은 저장소/PR에 추가하지 않았다. APK·ADB·A24·GPU/delegation·메모리·실제 이미지 품질도 실행하지 않았다.
- 기존 80슬롯·diagnostic v2·CALIB-01B, MobileNet label blocker, workload/기준정책/thermal 주장 한계는 그대로 보존한다.

## 보존한 CALIB-01B 검증 기록

아래는 2026-09-17 기존 사용자 로컬 Temurin 17.0.20.1+1 실행과 최종 감사 기록이다. 이번에는 재실행하지 않았다. 당시 `gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug --rerun-tasks`는 exit 0 / 161 tasks executed였다.

| 모듈 | Suite/Test | Failure/Error/Skip | lint Error/Warning |
| --- | --- | --- | --- |
| app | 3/9 | 0/0/0 | 0/20 |
| benchmark-runner | 18/97 | 0/0/0 | 0/54 |
| telemetry-contract | 5/13 | 0/0/0 | 0/2 |
| 합계 | 26/119 | 0/0/0 | 0/76 |

- artifact 8/8, 이미지 3/3, pipeline 6/6, Activity 1/1. Python 195건·실패/오류 0·기존 Windows symlink skip 1; CALIB targeted 7/7. compileall·logger self-test·assemble PASS.
- 증거: 모듈별 `build/test-results/testDebugUnitTest/TEST-*.xml`, `build/reports/lint-results-debug.sarif`, `.gradle-user/daemon/9.5.0/daemon-24276.out.log`(사용자 로컬). 이번 원격 조회에서 build 산출물을 읽은 것은 아니다.
- 당시 runner APK: 55,735,474 bytes, SHA-256 `9c5f0c8c939371311abe2cecdc9198f5935697d5e178b01a232940079ee5a04b`.
- 당시 app APK: 5,652,356 bytes, SHA-256 `9796c828e9720e28e88a788d1dc3c0dfb4f591fe425f8ba78d4e7bede33dc8a6`.
- image-v3 hash: `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`. 기존 schema 2·EXIF·root-only provenance·SUCCEEDED/LATE 계약 유지.
- 과거 Maven/Robolectric/signing-lock 실패는 위 성공으로 검증 대기가 해제된 이력이다. 새 task의 PASS로 전용하거나 완료한 감사를 반복하지 않는다.

## 기존 자료 위치·범위

- A24 formal 보정 분석: `C:\Users\LG\Documents\D1Check_Analysis\D1Check_A24_analysis_corrected_20260912_233544\CORRECTED_ANALYSIS_RESULT.txt`.
- A24 diagnostic off/on: `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_off_20260915_013906`, 같은 부모 폴더의 `A24_v2_smoke_on_retry3_20260915_123235`.
- trace: on 루트의 `runs\a04ef424-1cac-4177-aa89-4cd7f35fb2c4\diagnostics\d1check-630699bd-98c0-4e8f-9c3e-b7273bad2005.perfetto-trace`, 기록상 3,381,748 bytes.
- S26: `C:\Users\LG\Documents\카카오톡 받은 파일\S26_formal_strict_results.zip`. compatibility-list false/override true와 측정 계약 차이를 공시한다.
- trace 감사 보고서는 사용자 기록상 별도 외부 경로였으며 이번에 재확인하지 않았다. 과거 Documents 검색 실패를 보고서 부재로 단정하지 않는다.
- A24 위치 변경·주변온도, APK-source binding, FP32/FP16·GPU 내부 timing·에너지 단위 한계는 PLAN 13절에 보존했다. raw·파생자료를 이번에 재분석하지 않았다.

## 다음 행동 (최대 3개)

1. host 실행기의 실제 subprocess·bounded ready/wait·artifact pull·cleanup·delegate-log finalization을 구현한다. 현재 CLI는 validation과 no-I/O argv plan까지만 제공한다.
2. 실제 모델·sample을 저장소 밖 고정 입력 bundle로 준비하고 APK-source binding·manifest·SHA-256을 검증한 뒤 A24 CPU/GPU seam pilot 한 session을 실행한다.
3. A24 seam 통과와 정책 freeze 이후 같은 manifest/runner로 최소 한 대의 다른 Android 기기에서 축소 재현한다.

## 변경·검증 범위

이번 구현 조각은 `src/debug`의 host entry·manifest parser·외부 file verifier·LiteRT raw adapter·Tasks decoded adapter, debug-scoped Tasks Vision 1.0.0 후보 의존성, host validator/plan/artifact validator와 테스트를 추가한다. 사용자 로컬 JDK 17에서 targeted `ModelProbeContractTest`와 루트 `testDebugUnitTest lintDebug assembleDebug --rerun-tasks`가 `BUILD SUCCESSFUL`이었고, Python 전체 205건은 failure/error 0·Windows symlink 권한에 따른 skip 2로 통과했다. compileall과 logger self-test도 동일 production 코드에서 통과했다. Windows checkout의 canonical fixture CRLF를 LF와 동등하게 처리하도록 Kotlin·Python 회귀 검증을 보강했다. debug entry는 격리 process에서 bounded watchdog을 사용하며 성공 provenance를 만들지 않고 `seam_smoke_only_unfinalized`만 남긴다. ADB·설치·A24·추가 기기·Perfetto·Git master 병합은 수행하지 않았다. model/sample/system-library binary, host cache, 가상환경은 포함하지 않는다.

