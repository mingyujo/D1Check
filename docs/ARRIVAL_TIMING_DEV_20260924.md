# ARRIVAL-TIMING-DEV-01 — 시간 경계·판단 재현 개발 계약

2026-09-24. 시작 `feature/arrival-scheduling-20260923` / `d95a25f9095d4470a612128d7b79890b0d4732a8`, clean. 사용자 승인 범위는 설계·최소 구현·PC 검증·문서이며 ADB/설치/실측/본 simulation은 실행하지 않는다. 새 작업은 시간 계약 보완이며 완성된 PLAN B3나 제안정책 P, 성능 개선 입증으로 부르지 않는다.

## 근거와 보존

- 직전 읽기 전용 분석에서 CONDITIONAL 도착 직후 158호출 중 13호출에 CPU 실행 중 추정 잔여 소진이 관측됐다. dispatch→execution_start와 execution_start→output_ready 경계를 섞었고, null 결정·실제 scheduler lane 해제 기록이 부족했다. 이번에는 해당 원자료 감사·GPU 해시 검증·전체 분석을 반복하지 않았다.
- 기존 `ArrivalPolicy.kt`, `arrival-scheduler-v1`, CPU_FIFO/CPU_URGENT/FIXED_SPLIT/CONDITIONAL, 기존 host runner·validator·분석 경로는 그대로다. 기존 APK·모델·입력·외부 frozen 파일을 쓰지 않는다. 과거 실행을 재현할 때는 동결 APK/manifest를 사용하며 새 소스를 빌드한 APK를 과거 동일 버전으로 취급하지 않는다.
- 기존 198평가요청 `conditional_joint_primary_pass=false`, fixed-split 24시도/23완료/실행 전 연결 실패1/미시도3, 142/162요청·184/216warmup 및 retry/대체0을 유지한다. 남은 세션 재개 금지.
- 기존 공개 자료로 새 수치를 적합하지 않았다. 이후 사용한다면 post-unblinding 개발 자료로 표시하고 독립 검증으로 재사용하지 않는다.

## 새 namespace와 구현 범위

- protocol: `arrival-timing-dev-v1`; policy: `CONDITIONAL_TIMING_DEV_1`; estimate contract: `arrival-phase-budgets-v1`.
- `ArrivalSchedulerActivity`가 기존 runtime/admission/독립 도착/worker/cleanup 구현을 재사용한다. 기존 protocol에는 기존 정책만, 새 protocol에는 새 ID만 허용한다. 새 manifest는 `development_only=true`, `experiment_ready=false`, `timing_estimates`를 요구한다. 기존 `estimated_service_ms`를 새 시간 정의로 전용하지 않는다.
- 출력은 기존 canonical output helper의 새 protocol 하위 UUID 경로다. 기존 파일이 있으면 거절하는 저장 계약을 유지한다. 네 runtime resident·각2warmup·CPU thread1·최대2lane·비선점·기존 thermal/memory gate를 유지한다.
- 새 PC 도구는 읽기 전용 판단 재생/시간 정합성 검사다. 기존 device CLI에 새 protocol 실행/설치 지원을 추가하지 않았다. **실험 준비 미완료**이며 실행 가능한 기기 명령을 제시하지 않는다.

## 관측 시각과 상태 전이

모두 `SystemClock.elapsedRealtimeNanos()`의 ns다. 상태 기록·판단 snapshot은 짧은 동일 monitor로 순서를 정하고, 큐 변경과 배정은 단일 dispatch executor에서만 수행한다.

| 관측 | 정확한 경계·의미 |
|---|---|
| decision `mono_ns` / `decision_end_ns` | lane lock 획득 후 현재 큐·lane을 복사하고 정책 계산을 시작/종료. 사후 완료값 없음 |
| `dispatch_ns`, ASSIGNED | 선택 후 해당 lane의 논리적 점유 시작. worker 제출·admission·실행 시작 대기 전 |
| `execution_start_ns`, EXECUTING | admission 통과 후 task adapter 호출 직전. 이미지 확인/입력 준비·전후처리 포함 |
| `inference_start_ns` / `inference_end_ns` | `runForMultipleInputsOutputs` host 호출 블록 경계. 예외 반환도 observer가 기록. **GPU kernel 구간 아님** |
| `output_ready_ns`, OUTPUT_READY | task adapter 반환 및 결과 JSON byte 생성 후. urgent 완료 경계 |
| `persist_complete_ns`, PERSISTED | 결과 파일 write/fsync/rename/readback 확인 후. normal 완료 경계 |
| `worker_release_ns`, WORKER_RELEASED | worker finally에서 terminal을 기록한 뒤, request event 파일 저장 **전**. 기존 필드 의미 보존 |
| `lane_available_ns`, AVAILABLE | event 저장 시도 후 dispatch executor에 전달한 callback에서 실제 다음 배정을 허용하는 상태 전이 |

AVAILABLE은 scheduler의 제출 허용 상태다. OS worker thread가 정확히 idle이 된 시각이나 GPU kernel 완료를 추가로 증명하지 않는다. 이전 worker가 callback 제출 후 반환하기까지의 극소 구간은 다음 요청의 dispatch→execution_start에 포함된다. 실패/거절은 중간 성공 단계 없이 WORKER_RELEASED→AVAILABLE로 갈 수 있다. 동일 request 소유권을 확인해 오래된 callback이 새 요청을 해제하지 못한다.

새 모드 drain latch는 lane callback의 pump 종료 후 감소한다. 따라서 정상 drain의 final `requests.json`에는 `lane_available_ns`가 있다. worker가 먼저 저장하는 개별 `.event.json`에는 이 후행 시각이 없으며, PC 검증기는 final ledger에서 이 필드만 제외한 내용과 event를 대조한다. 구버전 자료에는 후행 시각을 추측해 채우지 않는다.

inference의 기존 공식 host timing 의미는 보존한다. observer는 종료 시각 이후 호출하고 원래 inference duration에서 제외한다. 다른 formal/probe 경로는 null observer 경로를 사용한다. 관측 overhead가 실제 서비스/dispatch 지연을 전혀 바꾸지 않는다고 주장하지 않는다.

## 추정 계약과 미확정 처리

task×backend 네 cell 각각 다음 **서로 겹치지 않는 5구간**을 명시한다. 값은 ns 또는 null이고 버전·출처가 필수다.

1. `decision_to_dispatch_ns`: 현재 판단 snapshot부터 선택 요청의 ASSIGNED까지. 정책 계산·기록·배정 비용 포함.
2. `dispatch_to_start_ns`: ASSIGNED→EXECUTING. worker 제출/대기/admission 포함.
3. `start_to_output_ready_ns`: EXECUTING→OUTPUT_READY. host inference만이 아니라 입력/출력 준비 포함.
4. `output_ready_to_persist_ns`: OUTPUT_READY→PERSISTED.
5. `persist_to_lane_available_ns`: PERSISTED→AVAILABLE. worker finally·event 저장·callback 지연 포함. WORKER_RELEASED에서 잔여 추정의 기점을 다시 시작하지 않는다.

busy lane의 남은 점유 예측은 현재 구간 budget에서 **그 구간 시작 후 경과**를 뺀 값과 뒤 구간 budget의 합이다. 배정 전 판단 비용을 이미 busy인 요청에 다시 더하지 않는다. AVAILABLE에서만 잔여0이다. 현재 구간 추정이 소진되면 `UNKNOWN_OVERRUN`, 필요한 값/기점이 없으면 `UNKNOWN_MISSING_BUDGET`, 유효한 추정이면 `ESTIMATED`로 기록한다. 초과 실행의 잔여를 0/임의 양수/무한대 penalty로 바꾸지 않는다. 이후 관측된 다음 phase에서 새 구간 추정을 시작하는 것은 허용한다.

후보 CPU 응답 예측은 현재 CPU의 AVAILABLE까지 잔여 + 앞선 대기 요청의 CPU 점유 전체 + 해당 요청의 판단→urgent output_ready 또는 normal persist_complete까지다. GPU가 AVAILABLE이면 해당 요청의 같은 완료 경계까지 예측한다. 후보 값은 snapshot 시점부터의 상대 ns이며, 이미 기다린 시간은 더하지 않는다. 비교는 같은 요청의 대안이다. 앞선 큐가 모두 CPU에서 순차 실행된다는 단순 투영은 **가정**이며 실제 미래 배정을 보장하지 않는다. GPU busy 때 GPU가 미래에 풀릴 시각을 예약하지 않는다. 동시 실행 간섭·deadline·aging·일반 서비스 보장은 최적화하지 않는다.

선택은 urgent→ordinal→ID 순서에서 가능한 첫 후보다. 두 lane busy면 `wait_both_busy`; 비교값이 미확정이면 CPU가 비어 있을 때만 `fallback_cpu_unknown`, CPU가 busy이면 `wait_unknown`; 둘 다 알려진 비교에서 CPU 동률 우선, GPU가 빠르면 GPU, CPU가 빠르지만 busy이면 `wait_estimated_cpu`다. 뒤 후보도 비교 기록하며 앞 후보가 대기하면 뒤 후보가 선택될 수 있다. 후보별 reason은 대안 계산이고 최종 배정은 `selected` 하나뿐이다.

이 fallback은 불확실한 상태의 진단 실행을 유한한 규칙으로 정의한 것이며 성능 보장/새 기여가 아니다. CPU를 기다리는 동안 GPU를 놀릴 수 있고 긴급 성능이 나빠질 수 있다. 큐·부하에 따른 판단 비용과 구간 예측 정확도도 아직 검증되지 않았다.

[미확정 설정](arrival_timing_dev_estimates_pending.json)은 **20값 모두 null**이다. 기존 97/250/558/1063ms를 새 구간에 자동 복사하지 않는다. 이 설정에서는 CPU 긴급 우선 진단 fallback이며 GPU 서비스 표본을 수집하는 보정 계획이 아니다. 숫자를 모두 채워도 자동 `experiment_ready=true` 승격은 없다. 별도 기기 검증과 전향적 개발 계획이 필요하다.

## 판단 기록·비용·유실

`decision_trace.json`은 추정 contract/version/provenance/budgets, 고정 clock, 기록 seq, 모든 phase 전이와 **선택이 없는 호출/빈 큐 호출까지** 포함한다. 각 판단에는 정렬된 전체 도착 큐의 ID/task/priority/ordinal, 두 lane의 소유 request/task·phase·phase 시작·persist 기점·잔여값/상태, 후보별 CPU/GPU 예측·reason, selected/null을 저장한다. deadline/thermal/memory는 선택 함수 입력이 아니다. 기존 deadline·환경 로그는 결과 판정/admission 용도다. 예정 미래 도착 목록과 실제 미래 종료값은 이 정책 API에 들어가지 않는다.

- `decision_end_ns−mono_ns`: snapshot 복사/정렬·정책 계산 시간. 뒤의 기록 객체 구성·append 비용과 lock 대기는 제외한다.
- 선택 요청의 `policy_compute_ns`: Activity에서 choose 진입 전부터 반환 후까지. lock 대기·snapshot·기록 객체/append 포함. `policy_evaluation_ns`는 위 내부 계산 구간이다. `dispatch_ns−decision.mono_ns`로 실제 배정까지 비용을 따로 복원한다. 선택 없는 호출도 내부 계산 구간은 남는다. no-selection의 전체 logger/lock 비용을 별도 직접 측정했다고 주장하지 않는다.
- 응답시간은 기존 예정 도착→완료 경계이므로 판단·계측·대기도 실제 경로에 포함된다. 서비스시간과 dispatch 지연을 따로 보고하며 응답시간을 서비스시간 입력으로 쓰지 않는다.
- 최대512개 immutable snapshot을 RAM에 보관한다. 정상 n≤24에서 decision=3n, null=2n, phase≤6n, 전체≤216이다(도착/해제 pump 각n, 선택n). dispatch에서 JSON 직렬화·파일 IO를 하지 않는다. snapshot/monitor 비용의 실제 상한은 PC 통과만으로 보장하지 않는다.
- 가득 차면 overwrite하지 않고 overflow/dropped를 기록하며 이후 선택을 중지한다. 기록하지 못한 선택은 반환하지 않는다. 이미 실행 중인 worker는 마무리하고 기존 bounded drain/watchdog를 따른다. 전체 trace를 invalid 처리하며 조용히 일부 표본만 분석하지 않는다.
- drain/실패 처리와 runtime close 뒤에 한 번 저장한다. write/fsync/rename 실패는 failure receipt/cleanup 실패로 남긴다. 강제 종료·watchdog·전원 손실이면 RAM trace가 소실될 수 있다. trace 부재/complete=false/overflow는 재현 통과가 아니며 원본을 수정해 복구한 것처럼 만들지 않는다. `complete`는 기록 drain 의미이지 모든 요청 성공/전체 실험 품질 PASS가 아니다.

## PC 검증과 재개 명령

검증 대상은 시작 HEAD + 이번 미커밋 변경이다. 소스 identity·시각·결과는 아래 검증 기록에 남긴다. 구버전 raw를 새 trace로 변환하거나 과거 반사실적 성능을 계산하지 않는다.

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME='C:\Users\LG\AppData\Local\Android\Sdk'
.\gradlew.bat :benchmark-runner:testModelProbeUnitTest --tests '*ArrivalTimingDevTest' --tests '*ArrivalPolicyTest' -PenableModelProbe=true --console=plain
python -B -m unittest tools.test_d1_arrival_timing_dev -v
python -B -m tools.d1_arrival_timing_dev --check-estimates docs/arrival_timing_dev_estimates_pending.json
```

새 artifact가 **나중에 실제 존재할 때만** `python -B -m tools.d1_arrival_timing_dev --artifacts <새-session-output-directory>`로 읽기 전용 재생을 수행한다. 이 명령은 ADB나 파일 출력을 하지 않는다. CLI가 검증하는 것은 snapshot 재생, phase/ledger/event 경계, 분모·호출 누락이며 모델 품질/GPU delegate/memory/thermal 전체 gate가 아니다. 실패/거절도 terminal_counts로 분리한다. 구버전 protocol은 기존 validator로 보내야 한다.

## 다음 최소 행동과 측정 경계

시간 경계 확인용 **별도 개발 보정 계획**을 먼저 작성한다. 필요한 질문은 (1) admission/worker 대기와 서비스의 분리, (2) result 저장·event 저장·callback 지연, (3) 계측 비용과 완전 기록, (4) 같은 입력/초기상태에서 각 phase estimate의 지원 범위다. 입력은 같은 exact 모델·이미지/tensor identity, lane 배정·순서·arrival, resident/warmup, CPU thread1, thermal/memory/초기 상태다. 출력은 새 trace와 기존 result/event/ledger/환경/cleanup이다. 추정값 미확정 fallback으로는 GPU cell을 보정할 수 없으므로, 후속 계획에는 **추정값에 의존하지 않는 고정 backend 진단 수집 경로**의 필요성을 명시해야 한다. 해당 기기 실행기/새 예산은 이번에 만들거나 승인하지 않았다.

CPU/GPU 간섭 식별은 별도 질문이다. 같은 입력·경계·실행 순서/초기 상태를 맞춘 단독과 동시 실행, overlap 시작 위치를 통제한 비교가 필요하다. 단순한 기존 예측 오차나 이 계측 코드만으로 인과 계수를 구할 수 없다. 반복 수/예산·초과잔여의 분포·간섭 수치·정책 우수성은 미확정이며 임의로 채우지 않는다. 독립 평가나 본 simulation 준비 완료로 표시하지 않는다.

## 검증 기록

2026-09-24 KST. 검증 대상 `d95a25f9095d4470a612128d7b79890b0d4732a8` + 아래 미커밋 소스. 위 실제 PC 명령을 실행했다.

| 검사 | 결과·한계 |
|---|---|
| 관련 modelProbe Kotlin 컴파일 및 선택한 JVM 테스트 | PASS. `ArrivalTimingDevTest` 13, 기존 `ArrivalPolicyTest` 7, 총20; failure/error/skip0. 최종 XML 시각 2026-09-23T16:22:07Z(09-24 01:22 KST). Android Activity 전체 실행이나 기기 추론 테스트는 아님 |
| Python 재생/거절/경계 테스트 | PASS 9, failure/error/skip0. 인메모리 synthetic fixture 사용. 2026-09-24 KST, 아래 최종 소스 hash 대상 |
| 실제 pending 설정 CLI dry-run | configuration_valid=true, missing_budgets20, experiment_ready=false. 설정의 구조 통과이며 보정 수치/기기 준비 통과가 아님 |
| Git diff 및 보존 경로 확인 | diff --check PASS. 기존 ArrivalPolicy·device runner·plan generator diff 없음. 외부 원본/기존 결과 hash 감사 반복 없음. 기존 formal host 호출 timer 경계 코드 검토 |
| 미실행 | APK assemble/설치, ADB, 실기기 추론, 본 simulation, 기존 전체 분석·전체 테스트, commit/push/merge |

JVM XML/HTML은 `benchmark-runner/build/test-results/testModelProbeUnitTest/`와 `benchmark-runner/build/reports/tests/testModelProbeUnitTest/`에 있으며 캐시·결과물은 커밋 대상이 아니다. 기존 deprecated API warning만 발생했고 컴파일 오류는 없었다. Python 테스트와 pending 검사 도구는 결과 파일을 쓰지 않는다.

검증한 파일의 SHA-256(작업 트리 byte 기준, LF/CRLF 변환 시 달라질 수 있음):

| 파일 | SHA-256 |
|---|---|
| `ArrivalTimingDev.kt` (modelProbe) | `8531a0f1c0595850fc45954730e29ecfdc7ff8d1a4b8e297af60ae0e16babc37` |
| `ArrivalSchedulerActivity.kt` (modelProbe) | `3b38d6aa4ddff9b40efd8bc2ea963bbe0b493cdde9783150c191b7d4f280f3b1` |
| `ProbeRawAdapter.kt` (modelProbe) | `81696a93e9eca3c6a6ef1f4002727802481197eaeeb5c50066da589c38ecef2b` |
| `ProbeTaskAdapter.kt` (modelProbe) | `8fd108570f2335d9062bb9f69cfa30dee950179f56e81c9656920b5129d34105` |
| `ArrivalTimingDevTest.kt` (test) | `005c09c8f39167e769c9926f7c3db548f33ac78c99f0d4562ba7270f3a0cee02` |
| `tools/d1_arrival_timing_dev.py` | `98a74c44203f918c10d53e036b49a33f7dba1abd1b5c3c4916e16f69af861566` |
| `tools/test_d1_arrival_timing_dev.py` | `b1cbbcb45b10a7179b0e27fe4816719d502a76917b7b08f6340ba83483570b0a` |
| `docs/arrival_timing_dev_estimates_pending.json` | `23518ff42b7935f5fa4d9f96a5cc6a813cb86a3fa5da232fb018dc84d002f7e1` |
