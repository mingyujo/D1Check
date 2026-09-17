# D1Check 현재 상태

- 갱신: 2026-09-17 / SCOPE-02 근거 조사 완료, MODEL-02A 전환
- 현재 작업: `MODEL-02A` — exact model artifact·labels·license·tensor/metadata/index 계약을 host에서 검증한다. A24 실행은 MODEL-02B다.
- 기준: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.1, [SCOPE_02_EVIDENCE.md](SCOPE_02_EVIDENCE.md), [MULTITASK_EXPERIMENT_PROTOCOL.md](MULTITASK_EXPERIMENT_PROTOCOL.md)(설계, 미구현).
- 코드 기준: 원격 `master`의 `df8192aa61eebacf83df7a7815f0c60c8bbf4004`, `Implement A24 calibration input and validation pipeline`. 이번에 branch/문서/관련 source를 조회했다.
- CALIB production/test는 위 commit에 포함돼 있다. 이전 `38386b9`/CALIB 미커밋 표기는 오래된 기록이었다. 사용자 Windows 작업 트리·index·로컬 HEAD는 이번 원격 작업에서 확인하지 않았다.
- 개정은 [초안 PR #2](https://github.com/mingyujo/D1Check/pull/2)의 문서 branch에 반영하며 master에 자동 병합하지 않는다. SCOPE-02 수정 전 head는 `93ab2ff71b8adec958a4f0e759773b64e4bbb181`이며 새 commit은 PR 기록으로 식별한다.
- 직접 검증은 A24만. S26은 기존 formal 보조자료이며 새 calibration·설치·실행·정책 평가는 범위 밖이다.
- 새 절대 deadline: `calibration_pending`. 서비스 하한·안전/안정성 수치·성공 기준·최종 반복 수: `thresholds_pending`.

## 완료와 미완료의 구분

| 작업 | 상태 | 해석 |
| --- | --- | --- |
| SETUP-01, AUDIT-A24-01, DIAGNOSTIC-V2-01, AUDIT-S26-01 | completed(기존 기록) | 측정 기반·기존 자료 감사 |
| DEFINE-01, CALIB-01A | completed(기존 정의) | 단일 분류 시나리오·legacy protocol. 새 주평가는 개정 4.1로 대체 |
| CALIB-01B | completed / CALIB_01B_PASS | MobileNet production·host 검증. 두 작업/실기기/정책 효과 PASS가 아님 |
| CALIB-01C-INPUT | legacy 준비 보류·재계획 | 기존 모델 1001행 라벨과 이미지 입력 미확정. 완료 처리하지 않음 |
| PLAN-REV04.1 | 문서 개정 완료 | 혼합 요청 주평가·시연·시뮬레이션 역할 정리. 코드·성능 검증이 아님 |
| SCOPE-02 | completed_with_open_gates | 합성 workload 가정, 공식 model/label 후보, 선행 연구·대회 적합성과 주장 한계를 근거 문서에 기록 |
| MODEL-02A | current | exact source/license/hash, metadata·tensor·label index·host golden output 승인 |
| MODEL-02B / TASK-02 / PROFILE-02 / SCHED-02 / EVAL-02 | pending | A24 model smoke→두 adapter→간섭 측정→정책 개발→독립 평가 |

## SCOPE-02 결과와 남은 장애

- 주평가: 일반 backlog 중 긴급 burst와 지속 혼합 요청. 저부하·동일 등급 경합·task별 등급 배치 변경은 보조 조건이다. 사진 정리는 대표 시연 후보이며 연구 범위의 필수 제약이 아니다.
- 실사용 도착 빈도·burst 분포를 입증한 사용자 로그는 없다. A24에서는 도착 시각·task·priority만 합성·재생하고 두 모델/I/O를 실제 실행한다. 별도 시뮬레이션은 실측으로 보정·독립 검증한 범위의 조건 탐색용이다. 실제/가상 표본을 합치지 않으며 실행기·모형은 아직 미구현이다.
- 후보는 EfficientNet-Lite0 FLOAT32 + EfficientDet-Lite0 FLOAT32(탐지 대안 SSD MobileNetV2). 공식 안내와 분류 1001행 label 후보, 탐지 90행 sparse label map(80 object + 10 placeholder)을 확인했다. exact model byte·license·metadata/tensor 결합·A24/현재 runtime 지원은 미검증이다.
- Band·Sung et al.·Pantheon·CoDL 등 관련 연구가 존재한다. 최초 모바일 multi-DNN scheduling을 주장하지 않고, A24 한 앱의 whole-request 비선점 배정·서비스 제약·강한 기준정책 대비 실증으로 범위를 제한한다.
- 공개 공식 대회 목록과 접근 가능한 프로그램에서 동일 제목은 확인하지 못했지만 2023~2025 전체 출품작을 완전 감사한 결과는 아니다. 중복 없음·최초성은 미확정이며 제출 전 RELATED-02에서 다시 확인한다.
- 기준 코드의 calibration은 MobileNet `[1,224,224,3] -> [1,1001]`에 고정돼 있다. 새 adapter/manifest/validator가 필요하며 기존 CLI로 두 작업을 실행할 수 없다.
- 기존 MobileNet label provenance는 사용자 제공 조사에서 미해결이었다. 원격 STATUS에 누락됐던 장애를 복원하며 이번에 원본 모델/외부 WNID 파일을 재검사한 것은 아니다. 새 labels를 기존 출력에 대신 붙이지 않는다.
- B2(최선 정적), B3(단순 동적), P(간섭 고려)의 우열은 미입증이다. 스로틀링은 성공 필수조건이 아니고 일반 서비스 희생만으로 긴급 P95를 낮추는 것은 성공이 아니다.
- 기존 CALIB-01C를 재개하려면 원래 AP/PA/SKIN host 연결·cooling/stability·strict GPU smoke 조건이 필요하다. 새 thermal 계약은 별도 구현하며 구 gate 통과로 소급하지 않는다.

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

1. MODEL-02A: 두 후보의 exact download/source, license, byte count/SHA-256, metadata·tensor·label index와 host golden output을 고정한 inventory를 만든다.
2. MODEL-02B 준비: 승인 bundle만 A24 CPU/GPU strict smoke와 품질·메모리·cold/warm 측정 대상으로 넘긴다. 미지원·fallback을 성공으로 바꾸지 않는다.
3. 두 task cell이 승인되면 TASK-02의 adapter·`multitask-v1` schema·quality/artifact validator를 구현한다. 기존 MobileNet·image-v3·미해결 label을 새 모델에 전용하지 않는다.

## 변경·검증 범위

초안 PR 전체 변경은 AGENTS, 계획/상태/결정/legacy protocol, 신규 두 작업 protocol과 SCOPE-02 근거 문서의 7개다. 이번 단계에서는 SCOPE 근거와 PLAN/STATUS/DECISIONS를 갱신한다. 내부 링크·ID/상태·whitespace·원격 base 대비 파일 집합을 확인한다. production·build·test·APK·ADB·실기기·Perfetto는 실행/변경하지 않는다. `.idea/**`, app MainActivity EOF, diagnostic 보고서, 데이터·캐시 등 사용자 로컬 변경에는 접근하지 않았다.
