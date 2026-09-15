# D1Check 현재 상태

- 갱신: 2026-09-15 / `SETUP-01` 완료 및 `DEFINE-01` 시작
- 현재 작업 ID: `DEFINE-01` — 앱 사용 사례와 요청·마감·평가지표 계약 결정
- 현재 단계: 선택지 정리. 구현과 실험은 아직 시작하지 않음.
- 기준 저장소: branch `master`, HEAD `1c9d759589e06b48a30e8f2311e3141af8ad4da6` (`Add persistent D1Check project context`)
- upstream: 로컬 `origin/master`도 `1c9d759589e06b48a30e8f2311e3141af8ad4da6`; ahead 0, behind 0
- 증거 원칙: 아래 경로는 이번 작업에서 존재만 직접 확인했다. 과거 보고서의 PASS를 현재 코드 검증으로 승격하지 않는다.

## Git 및 작업 트리

- `SETUP-01` 문서 커밋: `1c9d759589e06b48a30e8f2311e3141af8ad4da6`. 정확히 `AGENTS.md`와 docs 문서 3개를 추가함.
- push 근거: `refs/remotes/origin/master` reflog에 2026-09-15 22:04:59 +0900 `update by push`가 기록됐고 HEAD와 동일함. 현재 네트워크 제한으로 `git ls-remote` 재조회는 실패했으나 완료 당시 Git push 기록은 확인됨.
- diagnostic protocol v2 변경: 부모 커밋 `6312a061c76e35a11b53d2d00e32d075ab64f5ab`에 커밋되어 위 HEAD와 함께 `origin/master` tracking ref에 포함됨.
- 현재 index: staged 0개. tracked unstaged 5개(기존 사용자 변경 4개 + 이 STATUS 갱신 1개), untracked 9개.
- 기존 tracked unstaged: `.idea/deploymentTargetSelector.xml`, `.idea/gradle.xml`, `.idea/misc.xml`, `app/src/main/java/com/example/d1check/MainActivity.kt`.
- 기존 untracked: `DIAGNOSTIC_V2_*_RESULT.txt` 9개. 이 문서 작업의 커밋 대상이 아니다.
- 위 기존 사용자 변경, 소스, 보고서, 실험 데이터는 수정·복원·삭제하지 않는다.

## 직접 확인한 증거 위치

| 항목 | 직접 확인한 경로 | 확인 범위 |
| --- | --- | --- |
| A24 formal 보정 분석 | `C:\Users\LG\Documents\D1Check_Analysis\D1Check_A24_analysis_corrected_20260912_233544\CORRECTED_ANALYSIS_RESULT.txt` | 폴더와 파일 존재. 분석 결론은 이번 작업에서 재검증하지 않음 |
| A24 diagnostic trace-off | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_off_20260915_013906` | 결과 루트 존재. 실행·재감사하지 않음 |
| A24 diagnostic trace-on | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235` | manifest와 runs 경로 존재. 실행·재감사하지 않음 |
| A24 Perfetto trace | `C:\Users\LG\Documents\D1Check_Diagnostics\A24_v2_smoke_on_retry3_20260915_123235\runs\a04ef424-1cac-4177-aa89-4cd7f35fb2c4\diagnostics\d1check-630699bd-98c0-4e8f-9c3e-b7273bad2005.perfetto-trace` | 파일 존재, 3,381,748 bytes. 내용은 이번 작업에서 재처리하지 않음 |
| S26 formal export | `C:\Users\LG\Documents\카카오톡 받은 파일\S26_formal_strict_results.zip` | 파일 존재, 863,500 bytes. raw·소스 정합성은 미확인 |

`DIAGNOSTIC_V2_TRACE_CONTENT_AUDIT.txt`는 `C:\Users\LG\Documents` 아래에서 확인되지 않았다. trace 내용에 관한 이전 결론은 보고 기반이며 보고서 경로가 확인될 때까지 현재 증거로 재판정하지 않는다.

## 완료된 작업

`SETUP-01` 완료: ZIP의 지침·계획·상태·결정을 병합하고 네 문서만 커밋했으며, Git reflog와 tracking ref로 일반 push를 확인했다. `.idea`, app `MainActivity.kt`, diagnostic 결과 보고서는 그대로 남아 있다.

## 현재 작업과 완료 조건

`DEFINE-01`은 구현 전에 다음 계약을 결정하는 작업이다. 완료 조건은 실제 앱 기능 하나, 긴급·일반 요청 의미, 절대 마감시간, 요청 도착 규칙과 평가지표를 근거와 함께 문서화하는 것이다.

### 실제 앱 기능 선택지

| 선택지 | 긴급 요청 | 일반 요청 | 평가 |
| --- | --- | --- | --- |
| A. 사용자 선택 이미지 즉시 분류 + 갤러리 백그라운드 분류 | 사용자가 사진을 선택하고 결과를 기다리는 1회 분류 | 갤러리 이미지의 비동기 분류·색인 | **권장.** 현재 MobileNet·CPU/GPU 경로를 그대로 활용하고 두 요청의 출력 의미가 같아 비교가 명확함 |
| B. 카메라 미리보기 분류 + 탭 순간 정밀 분류 | 사용자가 탭한 프레임의 즉시 결과 | 주기적인 미리보기 프레임 분류 | 프레임 폐기 정책이 일반 요청 완료율을 왜곡할 수 있고 카메라 입력 경로가 추가로 필요함 |
| C. 안전·의료 이벤트 감지 | 경보가 필요한 사건 | 배경 모니터링 | 현재 모델 정확도와 실제 위험 자료가 없어 부적절함. 초기 범위에서 제외 |

### 마감시간 선택지

- 고정 UX 예산: 모든 기기에 같은 절대 마감시간을 사용한다. 실제 사용자 요구가 명확하면 가장 해석하기 쉽지만 현재 근거가 없다.
- 기기별 calibration 배수: 출력 준비 latency 분포의 배수로 정한다. 부하 생성에는 유용하지만 느린 기기에 느슨한 SLA를 주므로 최종 기기 간 비교에는 부적합하다.
- **권장 절차:** 짧은 독립 calibration으로 가능한 범위를 확인한 뒤, 결과를 보기 전에 사용성 근거가 있는 절대 긴급·일반 마감시간을 고정한다. 250/500/1000 ms와 2/5/10 s는 후보 탐색값일 뿐 확정값이 아니다.

### 평가지표 선택지

- **권장:** 긴급 출력 준비 응답시간 P95를 주지표로 하고, 긴급 기한 위반율·일반 기한 내 완료율·전체 완료율을 제약/동반 지표로 사용한다. 전체 도착 요청을 분모로 하며 실패·거절·만료를 별도 집계한다.
- 기한 내 완료율만 사용하면 지연 분포 개선을 놓치므로 보조지표로만 사용한다.
- 가중합 단일 점수는 가중치가 결과를 좌우하므로 초기 비교에는 사용하지 않는다.

## 미확인 증거

- S26 export의 전체 raw 데이터·실행 소스·APK 해시 정합성.
- trace content audit 보고서의 현재 실제 경로와 그 보고서가 검사한 trace/binary 해시.
- `DEFINE-01`의 앱 기능, 긴급·일반 요청 의미, 도착·마감·열·서비스 임계값 최종 선택.

## 다음 행동

1. 선택지 A를 실제 사용 사례로 채택할지 결정하고 긴급·일반 요청의 입력·출력 완료 경계를 확정한다.
2. calibration 결과와 UX 근거로 절대 마감시간 및 요청 도착 패턴을 고정한다.
3. 전체 도착 분모, 조건부 P95, 완료·실패 상태와 열·서비스 제약의 집계 계약을 확정한다.

## 최신 검증 기록

- 2026-09-15 | `SETUP-01` | `master` / `1c9d759589e06b48a30e8f2311e3141af8ad4da6`, 기존 미커밋 변경 있음 | log, commit name-status, tracking ref, reflog, ahead/behind 확인 | 문서 설치·커밋·push 완료. live 원격 재조회는 네트워크 제한으로 미확인.
- 2026-09-15 | `DEFINE-01` | 실제 app `MainActivity`와 계획의 요청·지표 계약을 읽기 전용 확인 | 사용 사례·마감·지표 선택지 정리. 구현·테스트·실기기 실행 없음.
- 구현 완료, host 검증, 실기기 검증, 효과 입증 상태를 서로 구분한다.

## 재개 요청

`PROJECT_STATUS.md의 DEFINE-01 선택지를 검토하고 실제 앱 기능, 긴급·일반 요청, 마감시간과 평가지표 계약을 확정해줘. 아직 구현하지 마.`
