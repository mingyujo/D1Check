# D1Check 현재 상태

- 갱신: 2026-09-15 / `DEFINE-01` 완료 및 `CALIB-01` 전환
- 현재 작업 ID: `CALIB-01` — 실제 사용자 이미지 경로의 종단간 지연 측정과 절대 마감시간 고정
- 현재 단계: 측정 계약 준비. 구현·측정·실기기 실행은 아직 시작하지 않음.
- 기준 저장소: branch `master`, HEAD `1c9d759589e06b48a30e8f2311e3141af8ad4da6` (`Add persistent D1Check project context`)
- upstream: 로컬 `origin/master`도 `1c9d759589e06b48a30e8f2311e3141af8ad4da6`; ahead 0, behind 0
- 증거 원칙: 아래 경로는 이번 작업에서 존재만 직접 확인했다. 과거 보고서의 PASS를 현재 코드 검증으로 승격하지 않는다.

## Git 및 작업 트리

- `SETUP-01` 문서 커밋: `1c9d759589e06b48a30e8f2311e3141af8ad4da6`. 정확히 `AGENTS.md`와 docs 문서 3개를 추가함.
- push 근거: `refs/remotes/origin/master` reflog에 2026-09-15 22:04:59 +0900 `update by push`가 기록됐고 HEAD와 동일함. 현재 네트워크 제한으로 `git ls-remote` 재조회는 실패했으나 완료 당시 Git push 기록은 확인됨.
- diagnostic protocol v2 변경: 부모 커밋 `6312a061c76e35a11b53d2d00e32d075ab64f5ab`에 커밋되어 위 HEAD와 함께 `origin/master` tracking ref에 포함됨.
- 현재 index: staged 0개. 문서 갱신 완료 시 tracked unstaged 7개(기존 사용자 변경 4개 + docs 3개), untracked 9개.
- 기존 tracked unstaged: `.idea/deploymentTargetSelector.xml`, `.idea/gradle.xml`, `.idea/misc.xml`, `app/src/main/java/com/example/d1check/MainActivity.kt`.
- 기존 untracked: `DIAGNOSTIC_V2_*_RESULT.txt` 9개. 이 문서 작업의 커밋 대상이 아니다.
- 위 기존 사용자 변경, 소스, 보고서, 실험 데이터는 수정·복원·삭제하지 않는다.

## 직접 확인한 증거 위치

| 항목 | 직접 확인한 경로 | 확인 범위 |
| --- | --- | --- |
| A24 formal 80슬롯 | `C:\Users\LG\Documents\D1Check_Analysis\D1Check_A24_analysis_corrected_20260912_233544\CORRECTED_ANALYSIS_RESULT.txt` | CPU 중앙 약 41.2 ms, GPU 약 131.6 ms, GPU/CPU 약 3.196. CPU 1/2/4 차이는 작고 위치 민감도 검사에서 우열 방향 유지 |
| A24 diagnostic trace-off | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_off_20260915_013906` | 결과 루트 존재. 실행·재감사하지 않음 |
| A24 diagnostic trace-on | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235` | manifest와 runs 경로 존재. 실행·재감사하지 않음 |
| A24 Perfetto trace | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235\runs\a04ef424-1cac-4177-aa89-4cd7f35fb2c4\diagnostics\d1check-630699bd-98c0-4e8f-9c3e-b7273bad2005.perfetto-trace` | 파일 존재, 3,381,748 bytes. 내용은 이번 작업에서 재처리하지 않음 |
| S26 formal 80슬롯 | `C:\Users\LG\Documents\카카오톡 받은 파일\S26_formal_strict_results.zip` | 원시자료 감사·지연 재계산 통과. GPU가 pooled CPU보다 duty별 약 1.062~1.201배 빠르고 20개 대응 비교 모두 GPU 우세·AP 온도 상승도 더 낮음. 31/31 full delegation, fallback 없음 |

`DIAGNOSTIC_V2_TRACE_CONTENT_AUDIT.txt`는 `C:\Users\LG\Documents` 아래에서 확인되지 않았다. trace 내용에 관한 이전 결론은 보고 기반이며 보고서 경로가 확인될 때까지 현재 증거로 재판정하지 않는다.

## 완료된 작업

`SETUP-01` 완료: ZIP의 지침·계획·상태·결정을 병합하고 네 문서만 커밋했으며, Git reflog와 tracking ref로 일반 push를 확인했다. `.idea`, app `MainActivity.kt`, diagnostic 결과 보고서는 그대로 남아 있다.

- `AUDIT-A24-01`: completed.
- `DIAGNOSTIC-V2-01`: completed.
- `AUDIT-S26-01`: completed.
- `DEFINE-01`: completed. 공식 범위·사용 시나리오·완료 시점·KPI·목적함수 우선순위·자원 범위를 문서화했다.

## DEFINE-01 공식 계약

- 범위: 하나의 온디바이스 AI 앱 내부에서 CPU/GPU/NPU 후보를 선택하고 긴급·일반 요청 큐를 관리한다. Android OS 전체 스케줄러가 아니다.
- 긴급 요청: 사용자가 갤러리 사진 한 장의 즉시 분류 결과를 요청하는 대화형 작업.
- 일반 요청: 여러 갤러리 사진을 백그라운드에서 분류·색인하는 일괄 작업.
- 긴급 완료: 앱 큐 진입부터 결과가 사용자에게 제공 가능한 output-ready 시점까지.
- 일반 완료: 앱 큐 진입부터 해당 이미지 분류 결과가 저장된 시점까지.
- `Interpreter.run()` 순수 지연과 이미지 읽기·전처리·큐 대기·후처리·반환/저장을 포함한 종단간 지연을 분리한다.
- 진행 중 일반 요청 처리 방식은 일반 이미지 완료 후 긴급 실행, 다음 이미지 경계에서 batch 중단, 다른 가용 자원 동시 실행을 후속 비교한다. `Interpreter.run()` 중간 강제 중단은 가정하지 않는다.
- 1차 구현 자원은 CPU/GPU다. NPU는 capability와 실제 실행 검증을 통과한 기기에서만 활성화하며 미지원·접근 실패 시 필수조건이 아니다. S26은 현재 `nnapi-reference` CPU만 노출했다.

### KPI와 목적함수

- 긴급 output-ready 응답시간 P95, 긴급 마감 위반율, 일반 기한 내 완료율, 전체 도착 대비 완료율, 처리량, 최고 온도 또는 Android thermal status, CPU/GPU 실제 사용 비율, 정확도 검증 통과 여부를 각각 보고한다.
- 실패·거절·만료 요청은 전체 도착 요청 분모에서 제외하지 않는다.
- 사전적 우선순위: 안전·정확도 → 긴급 마감 위반 최소화 → 긴급 P95 최소화 → 일반 기한 내 완료율 최대화 → 처리량 최대화 → 온도·전환 비용 최소화.
- 가중합 목적함수는 아직 사용하지 않는다.

## 현재 작업과 완료 조건

긴급·일반 절대 마감시간 상태는 `calibration_pending`이다. `CALIB-01` 완료 조건은 A24와 S26에서 실제 사용자 이미지 경로의 종단간 구성요소를 소규모로 측정하고, 입력·시계·반복·열 조건과 함께 기록한 뒤 평가 결과를 보기 전에 절대 마감시간과 요청 도착 규칙을 사전 고정하는 것이다.

## 미확인 증거

- A24 위치 변경·주변온도 영향의 완전한 제거.
- S26 `gpu_compatibility_list_supported=false`, `formal_gpu_compat_list_override=true`; 결과 비교에서 반드시 공시. dataset manifest accuracy/pilot 문구와 재시도 raw run 하나의 failure 기록은 보완 필요.
- 실제 FP32/FP16 하드웨어 실행, GPU 내부 H2D/GPU/D2H·fence timing은 unknown. 에너지 단위가 미검증이므로 J/mWh 사용 금지.
- 측정 당시 설치 APK와 Git 소스의 완전한 cryptographic binding.
- trace content audit 보고서의 현재 실제 경로와 그 보고서가 검사한 trace/binary 해시.

## 다음 행동

1. CALIB-01의 실제 이미지 입력 집합, 시계, 반복 수, cold/warm 및 열 초기조건을 고정한다.
2. 이미지 읽기·전처리·큐 대기·추론·후처리·긴급 output-ready·일반 결과 저장 시점을 A24와 S26에서 측정한다.
3. 측정 결과를 근거로 절대 마감시간과 요청 도착 규칙을 평가 전에 고정한다.

## 최신 검증 기록

- 2026-09-15 | `SETUP-01` | `master` / `1c9d759589e06b48a30e8f2311e3141af8ad4da6`, 기존 미커밋 변경 있음 | log, commit name-status, tracking ref, reflog, ahead/behind 확인 | 문서 설치·커밋·push 완료. live 원격 재조회는 네트워크 제한으로 미확인.
- 2026-09-15 | `DEFINE-01` | PROJECT_PLAN·PROJECT_STATUS·DECISIONS | 사용자 지시에 따라 공식 범위·시나리오·완료·KPI·사전적 목적함수·자원 계약 확정. 마감시간은 `calibration_pending`. 구현·테스트·실기기 실행 없음.
- 구현 완료, host 검증, 실기기 검증, 효과 입증 상태를 서로 구분한다.

## 재개 요청

`PROJECT_STATUS.md의 CALIB-01 완료 조건을 확인하고 실제 이미지 종단간 지연 측정 계약을 작성해줘. 아직 구현·실기기 실행은 하지 마.`
