# D1Check 현재 상태

- 갱신: 2026-09-17 / CALIB-01B 종료 문서 정리
- 현재 작업 ID: `CALIB-01C-INPUT` — A24 실제 이미지 calibration 입력 준비
- CALIB-01B: completed / `CALIB_01B_PASS`. FIX4까지 production 구현·host 검증·최종 읽기 전용 감사를 완료했다. A24 이미지 종단간 실측이나 최종 스케줄러 효과 검증의 완료를 뜻하지 않는다.
- 기준 저장소: branch `master`, HEAD `38386b94a5a4aaf3d9b9da077e40af71e342dadf` (`Define end-to-end calibration protocol`). 로컬 `origin/master`도 동일하다.
- Git 상태: index 0개, CALIB production/test/문서는 unstaged/untracked이며 아직 커밋되지 않았다. 기존 사용자 변경 4개와 diagnostic 결과 보고서 9개를 보존한다.
- 직접 실기기 범위: Galaxy A24만 해당. S26 새 calibration·설치·앱 실행·스케줄러 검증은 `OUT_OF_SCOPE_NON_BLOCKING`; 기존 formal 80슬롯 보조 사례만 유지한다.
- 긴급·일반 절대 마감시간 상태: `calibration_pending`. 입력·환경 준비와 A24 pilot 안정성/정확도 gate 전에는 고정하지 않는다.

## Git 및 완료된 작업

- `SETUP-01`: completed. 문서 설치 커밋 `1c9d759589e06b48a30e8f2311e3141af8ad4da6` 및 완료 당시 tracking ref/reflog의 일반 push 기록 확인. live 원격 재조회는 별도 미확인이다.
- diagnostic v2는 기존 커밋에 포함돼 있다. CALIB-01B 미커밋 변경과 구분하며 기존 v1/v2 schema·경로·latency 의미는 보존한다.
- `AUDIT-A24-01`, `DIAGNOSTIC-V2-01`, `AUDIT-S26-01`, `DEFINE-01`, `CALIB-01A`, `CALIB-01B`: completed.
- 기존 변경·커밋 제외: `.idea/deploymentTargetSelector.xml`, `.idea/gradle.xml`, `.idea/misc.xml`, app `MainActivity.kt`의 EOF 빈 줄, 모든 `DIAGNOSTIC_V2_*_RESULT.txt`.
- build/cache/APK·기존 A24/S26 데이터·분석·사용자 개인 변경도 제외한다. 소스·테스트·보고서·기존 데이터는 이번 종료 문서 작업에서 수정하지 않는다.
- 공식 시나리오·KPI·사전적 목적함수는 [PROJECT_PLAN.md](PROJECT_PLAN.md)와 [DECISIONS.md](DECISIONS.md)를 따른다. 실패·거절·만료는 도착 분모에 남기고, 완료 P95와 전체 도착 기준 성공률을 함께 보고한다.

## CALIB-01B 최종 검증 증거

검증 대상은 위 HEAD + 미커밋 CALIB-01B FIX4 production/test다. 2026-09-17 사용자 로컬 Temurin 17.0.20.1+1에서 `gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug --rerun-tasks`가 BUILD SUCCESSFUL / exit 0, 161 actionable tasks: 161 executed였다. 최종 감사에서 최신 XML/SARIF·APK·코드 관계를 직접 확인했다. 이번 문서 정리에서는 테스트·빌드를 재실행하지 않았다.

| 모듈 | Suite/Test | Failure/Error/Skip | lint Error/Warning | XML 생성 시각 |
| --- | --- | --- | --- | --- |
| app | 3/9 | 0/0/0 | 0/20 | 2026-09-17 11:45:45 |
| benchmark-runner | 18/97 | 0/0/0 | 0/54 | 2026-09-17 11:48:13 |
| telemetry-contract | 5/13 | 0/0/0 | 0/2 | 2026-09-17 11:46:06 |
| 합계 | 26/119 | 0/0/0 | 0/76 | 최신 로컬 전체 실행 |

- 실제 실행·통과: artifact validator 8/8, 이미지 integration 3/3, production pipeline 6/6, Activity entry 1/1. 중첩 provenance 미등재/실제 hash 등재 및 production finalizer 거부, 루트-only self-hash 제외가 검증됐다.
- Python 전체: 195건·failure/error 0·기존 skip 1, exit 0. skip은 `test_completed_trace_on_resume_rejects_symlinked_trace`의 Windows symlink 생성 권한 부재로 CALIB 핵심 검증이 아니다. calibration CLI targeted 7/7도 통과했다.
- `python -m compileall -q tools`, logger self-test, assembleDebug: PASS. CALIB 관련 lint 24건은 UseKtx 2·SetTextI18n 22로 중대한 보안·정확성 경고는 발견되지 않았다.
- 증거 위치: 각 모듈 `build/test-results/testDebugUnitTest/TEST-*.xml`, `build/reports/lint-results-debug.sarif`; 성공 로그 `.gradle-user/daemon/9.5.0/daemon-24276.out.log`.
- image-v3 configuration SHA-256: `03e507dea1d4111681b6c1120fab7729967a19e49712ccc05d2e72e4f7762cf5`. Kotlin/host CLI/docs 일치. EXIF 부재=1, 명시 1~8만 허용, mirror/회전 후 crop/resize, decode cause 보존 계약 유지.
- runner APK: `benchmark-runner/build/outputs/apk/debug/benchmark-runner-debug.apk`, 55,735,474 bytes, 2026-09-17 11:46:41. SHA-256 `9C5F0C8C939371311ABE2CECDC9198F5935697D5E178B01A232940079EE5A04B`.
- app APK: `app/build/outputs/apk/debug/app-debug.apk`, 5,652,356 bytes, 2026-09-17 11:45:20. SHA-256 `9796C828E9720E28E88A788D1DC3C0DFB4F591FE425F8BA78D4E7BEDE33DC8A6`.
- scoped diff check 통과, index 비어 있음. 전체 diff check의 기존 app EOF 빈 줄은 보존·제외한다. 구현 검증, 실기기 calibration, 스케줄러 효과 입증은 별도 상태다.

## Resolved history

- 2026-09-16~17 sandbox의 Google Maven/AndroidX resolve, Robolectric jar 접근·`C:\.robolectric-download-lock`, debug signing lock 실패는 과거 환경 이력이다. FIX2 전체의 28건·FIX4 targeted 8건/전체 30건 실패는 테스트 본문 전 환경 실패였고, 위 최신 사용자 로컬 전체 119/119 및 assembleDebug 성공으로 완료 대기가 해제됐다. sandbox 권한 제한 자체가 변경됐다고 주장하지 않는다.
- FIX1은 이미지 fixture 리소스와 production writer/validator 계약, FIX2는 terminal/deadline·thermal·A24-only·입력 검증을 정리했다. FIX3 EXIF/decode/Matrix 및 FIX4 중첩 provenance 우회 수정은 최신 동작 테스트와 최종 감사로 완료됐다.
- 과거 FIX3의 이미지 테스트 실패 3건과 이전 미확인·INCOMPLETE 기록은 종료 판정이 아니다. 이전 PASS를 새 버전에 전용하지 않고 최신 FIX4 증거로 `CALIB_01B_PASS`를 확정했다.

## 현재 작업·완료 조건과 실측 사전조건

`CALIB-01C-INPUT`의 완료 조건은 라이선스·ground-truth를 확인한 실제 이미지 8개(최소 4 class, class당 2개), verified 1001-line label mapping 및 image-v3 manifest/provenance를 고정하는 것이다. 각 이미지 bytes/size/MIME/크기/EXIF·라벨·APK hash를 production 계약에 맞춰 확인해야 한다. 임의 이미지 생성·다운로드나 1×1 fixture의 대표/정확도 데이터 승격은 하지 않는다.

- representative image set과 verified label mapping은 아직 준비되지 않았다. 현재 입력 준비는 A24만 대상이며 S26 end-to-end 결과를 주장하지 않는다.
- A24 baseline 실측 전 host AP/PA/SKIN 시계열, cooling/stability gate와 session/monotonic 시간 연결이 필요하다. 기존 logger 수집 기능은 있지만 calibration과 자동 연결돼 있지 않다. 앱의 battery temperature/Android thermal status로 AP/PA/SKIN을 대체했다고 주장하지 않는다.
- baseline pilot/formal/stress 분리, baseline 시작 status 0/1, formal 사전 policy/hash 계약 유지. THERMAL_STRESS는 baseline에 합산하지 않는다.
- A24 strict CompatibilityList GPU 진입 smoke와 full-delegation/fallback 외부 증거가 남아 있다. GPU 실패의 silent CPU fallback·S26 override·기기 모델 기반 우회는 금지한다.
- 긴급 output-ready/일반 durable persistence 완료는 늦어도 SUCCEEDED/LATE다. 미완료 만료만 EXPIRED이고 비성공에는 결과가 없어야 한다. 늦은 성공은 전체 완료율에는 포함하지만 기한 내 완료율에는 포함하지 않는다.
- 순수 Interpreter.run() 구간 밖에서 I/O·전처리·후처리·checksum·telemetry·저장을 수행한다. 기존 tensor-only 80슬롯은 이미지 종단간 지연의 대체 근거가 아니다.

## 기존 실기기 증거 위치와 해석 한계

아래는 기존에 확인한 자료로, 이번 종료 문서 작업에서 재측정·재처리하지 않았다.

| 자료 | 경로 및 기존 확인 범위 |
| --- | --- |
| A24 formal 80슬롯 | `C:\Users\LG\Documents\D1Check_Analysis\D1Check_A24_analysis_corrected_20260912_233544\CORRECTED_ANALYSIS_RESULT.txt`. CPU 중앙 약 41.2 ms, GPU 약 131.6 ms, 비율 약 3.196. CPU 1/2/4 차이 작음, 위치 민감도에서도 CPU 우세 방향 유지 |
| A24 diagnostic off | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_off_20260915_013906`. 기존 결과 루트 |
| A24 diagnostic on | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235`. 기존 manifest/runs |
| A24 trace | 위 on 루트의 `runs\a04ef424-1cac-4177-aa89-4cd7f35fb2c4\diagnostics\d1check-630699bd-98c0-4e8f-9c3e-b7273bad2005.perfetto-trace`, 3,381,748 bytes |
| S26 formal 보조자료 | `C:\Users\LG\Documents\카카오톡 받은 파일\S26_formal_strict_results.zip`. 원시자료 감사/지연 재계산 통과. GPU duty별 약 1.062~1.201배 빠름, 20개 대응 비교 모두 GPU 지연/AP 상승 낮음. 모든 GPU run 31/31 full delegation·fallback 없음 |

- A24 위치 변경·주변온도 제한은 유지한다. S26 compatibility-list false/override true를 기존 formal 비교에 공시하고 dataset manifest accuracy/pilot 문구와 재시도 failure 기록의 불완전성을 유지한다.
- 실제 FP32/FP16, GPU H2D/GPU/D2H·fence timing은 unknown이다. 미검증 에너지 단위로 J/mWh나 에너지 절감을 주장하지 않는다. 과거 측정 APK와 Git 소스의 완전한 cryptographic binding도 미확보다.
- trace content audit 보고서의 현재 경로·trace/binary hash는 미확인이다. `DIAGNOSTIC_V2_TRACE_CONTENT_AUDIT.txt`는 이전 `C:\Users\LG\Documents` 조사에서 찾지 못했으며 보고 기반 결론을 새 독립 증거로 승격하지 않는다.

## 다음 행동 (최대 3개)

1. 실제 이미지 8개의 출처·라이선스·ground-truth와 verified 1001-line label mapping을 확정한다.
2. image-v3·현재 runner APK hash에 맞는 입력 bundle/manifest/provenance를 준비하고 production 입력 계약으로 검증한다.
3. 입력 완료 후 host thermal/cooling 연결과 A24 strict GPU smoke의 별도 계획·승인을 확인한다. 모든 사전조건 전에는 설치·앱 실행·calibration을 시작하지 않는다.

이번 종료 작업: 위 세 문서만 정리했으며 테스트·빌드·ADB·설치·앱·실기기·Perfetto·stage·commit·push는 수행하지 않았다.
