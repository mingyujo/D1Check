# ARRIVAL-TIMING-CAL-01 — 단독 시간 경계 진단 준비

2026-09-24. **PC 준비 작업 / 실기기 예산 제안 / 기기 실행 승인 전 실행 금지**.
직전 12개 변경과 8개 코드·설정 해시가 검증 기록과 일치하여, 기존 테스트를 먼저 반복하지 않고 `2904165`에 선택적으로 checkpoint했다. 시작 branch는 `feature/arrival-scheduling-20260923`, 이전 HEAD `d95a25f9095d4470a612128d7b79890b0d4732a8`였다. 이번 변경은 그 checkpoint의 후속이다.

기존 198요청 `conditional_joint_primary_pass=false`, fixed-split 24시도/23완료/실행 전 연결 실패1/미시도3·142/162요청·184/216warmup 및 retry/대체0은 보존한다. 중단된 27세션의 남은 예산과 합산하거나 이어 실행하지 않는다. 원본·기존 APK·모델·동결 계획은 수정하지 않는다.

## 1. 목적과 범위

새 질문은 **지정된 CPU/GPU에서 새 시간 경계를 빠짐없이 수집할 수 있으며 단독 조건의 초기 구간값을 기술할 수 있는가**이다. 최초 CPU/GPU 동시 실행, 간섭 인과 계수, 혼합 부하에서의 준비/저장 지연, 초과 실행의 잔여 분포, 정책 우수성·완전한 B3/P를 검증하지 않는다.

- 앱 protocol `arrival-timing-calibration-v1`, policy `CALIBRATION_FIXED_BACKEND_1`, plan protocol `arrival-timing-calibration-plan-v1`, observation contract `arrival-phase-observations-v2`.
- 기존 Activity/adapter/worker/Recorder를 재사용한다. calibration의 명시적 목적은 `boundary_calibration_only`, storage는 `persist_all`, `development_only=true`, `experiment_ready=false`, concurrency1이다. 새 host run은 이 calibration plan만 허용한다. 일반 `CONDITIONAL_TIMING_DEV_1` 정책 실험의 준비 gate를 해제하지 않는다.
- 두 lane 중 하나라도 busy면 시작하지 않는다. 지정 backend 이외의 경로를 고르지 않으며 추정값·후보별 완료시간 비교를 사용하지 않는다. 후보 예측 목록은 빈 배열이다. null/빈 큐 호출도 기록한다.
- 실제 도착 때 이전 lane이 아직 재사용 가능하지 않았으면 `solo_arrival_while_lane_busy`로 중단한다. 도착 callback이 늦게 처리되어 그 사이 lane이 풀렸더라도 당시 도착 시각과 비교하여 검출한다. 요청 발생을 완료에 맞춰 늦추는 방식으로 단독 조건을 꾸미지 않는다.

## 2. 기존 20개 추정 대상 점검

아래 약어: D=판단 snapshot `mono_ns`, A=dispatch/ASSIGNED, S=execution_start/EXECUTING, O=output_ready, P=persist_complete, L=scheduler callback의 lane_available. W=worker_release는 P→L 안에 있는 별도 관측이며 event 저장 전이다. 모든 시각은 elapsedRealtimeNanos, inference host API 호출은 S→O 내부의 부분 구간이다.

응답 예측은 urgent D→O, normal D→P다. lane 점유는 A→L이며 판단 시점부터 lane 재사용까지 예측하려면 D→A도 더한다. `R(U,N)`은 urgent/normal 응답에 적용 여부, `Lane`은 **A→L 점유** 예측에 적용 여부다. 각 행의 직접 측정은 해당 실행 경계 차이다.

| 기존 cell | 값 | 시작→종료 | R(U,N) / Lane | 직접 측정 | priority·저장·부하 의존 / 중복·누락 |
|---|---|---|---|---|---|
| classification_CPU | decision_to_dispatch_ns | D→A | 적용,적용 / N/A | 가능, calibration 정책 비용 | 큐/선택 로직/로그 크기 의존; adaptive 정책 비용으로 전용 불가 |
| classification_CPU | dispatch_to_start_ns | A→S | 적용,적용 / 적용 | 가능 | worker 제출·대기·admission 포함; 부하 의존 |
| classification_CPU | start_to_output_ready_ns | S→O | 적용,적용 / 적용 | 가능 | 입력 확인/변환·host inference·후처리·JSON 생성 포함 |
| classification_CPU | output_ready_to_persist_ns | O→P | N/A,적용 / 적용 | 가능 | urgent도 저장; 완료값 처리 분기와 IO 포함 |
| classification_CPU | persist_to_lane_available_ns | P→L | N/A,N/A / 적용 | 가능 | priority별 완료 bookkeeping·W·event 저장·callback 포함 |
| classification_GPU | decision_to_dispatch_ns | D→A | 적용,적용 / N/A | 가능, calibration 정책 비용 | 큐/선택 로직/로그 크기 의존; adaptive 정책 비용으로 전용 불가 |
| classification_GPU | dispatch_to_start_ns | A→S | 적용,적용 / 적용 | 가능 | GPU worker 제출·대기·admission 포함; 부하 의존 |
| classification_GPU | start_to_output_ready_ns | S→O | 적용,적용 / 적용 | 가능 | host API 경계이며 GPU kernel 시간은 아님 |
| classification_GPU | output_ready_to_persist_ns | O→P | N/A,적용 / 적용 | 가능 | urgent도 저장; 완료값 처리 분기와 IO 포함 |
| classification_GPU | persist_to_lane_available_ns | P→L | N/A,N/A / 적용 | 가능 | priority별 bookkeeping·W·event 저장·callback 포함 |
| detection_CPU | decision_to_dispatch_ns | D→A | 적용,적용 / N/A | 가능, calibration 정책 비용 | 큐/선택 로직/로그 크기 의존; adaptive 정책 비용으로 전용 불가 |
| detection_CPU | dispatch_to_start_ns | A→S | 적용,적용 / 적용 | 가능 | worker 제출·대기·admission 포함; 부하 의존 |
| detection_CPU | start_to_output_ready_ns | S→O | 적용,적용 / 적용 | 가능 | 탐지 decode/NMS·JSON 생성 포함; 분류와 별도 |
| detection_CPU | output_ready_to_persist_ns | O→P | N/A,적용 / 적용 | 가능 | 탐지 결과 크기·priority·IO 의존 |
| detection_CPU | persist_to_lane_available_ns | P→L | N/A,N/A / 적용 | 가능 | priority별 bookkeeping·W·event 저장·callback 포함 |
| detection_GPU | decision_to_dispatch_ns | D→A | 적용,적용 / N/A | 가능, calibration 정책 비용 | 큐/선택 로직/로그 크기 의존; adaptive 정책 비용으로 전용 불가 |
| detection_GPU | dispatch_to_start_ns | A→S | 적용,적용 / 적용 | 가능 | GPU worker 제출·대기·admission 포함; 부하 의존 |
| detection_GPU | start_to_output_ready_ns | S→O | 적용,적용 / 적용 | 가능 | host 호출과 탐지 decode/NMS·JSON 생성 포함 |
| detection_GPU | output_ready_to_persist_ns | O→P | N/A,적용 / 적용 | 가능 | 탐지 결과 크기·priority·IO 의존 |
| detection_GPU | persist_to_lane_available_ns | P→L | N/A,N/A / 적용 | 가능 | priority별 bookkeeping·W·event 저장·callback 포함 |

다섯 구간의 합은 정확히 D→L이며 서로 중복하지 않는다. inference_ns나 W→L을 여기에 다시 더하지 않는다. 예정 도착→D(도착 지연·큐 대기·판단 monitor 획득 전 대기)는 이 합 밖이며 end-to-end 응답에는 남아 있다. runtime 생성·warmup·최종 trace flush/close는 workload의 이 5구간 밖에 별도 기록한다. 누락된 비용을 0이라고 가정하는 것이 아니다.

**계약 보완:** 기존 `arrival-phase-budgets-v1`과 20 null 설정은 변경하지 않는다. 새 관측/초기 fit은 task×backend×priority **8조건×5구간=40개 관측 슬롯**을 별도 v2로 유지한다. 실제 코드의 O→P/P→L 완료 처리 분기와 응답 경계가 달라 priority를 합치지 않는다. S→O의 task 처리 코드는 priority에 의존하지 않지만, 작은 표본을 먼저 pooling하지 않고 ordinal/조건별 원값을 보존한다. 저장 없음 변형은 이번 범위에 추가하지 않는다.

- N/A는 **특정 예측 목적에 해당하지 않는 항목**이다. 예: urgent 응답의 O→P는 `response_use=not_applicable`지만 실제 저장과 lane 점유에는 적용되므로 그 관측값을 지우거나 0으로 만들지 않는다. D→A는 A→L 점유에는 N/A다.
- missing은 측정되지 않았거나 실패/누락으로 필요한 증거가 없는 상태다. 기존 null20개는 missing이다. 실패 후 없는 P/L을 N/A 또는 0으로 채우지 않으며 fit을 차단한다.
- 고정 진단의 D→A는 측정 가능하지만 CONDITIONAL의 D→A는 여전히 `missing_policy_specific_measurement`다. 새 fit을 그대로 기존 정책에 넣지 않는다. 고정 경로의 단독 비용과 적응형 판단·기록 비용이 같다는 근거가 없다.
- 선택 없는 호출에는 dispatch가 없으므로 D→A 표본이 N/A다. 해당 호출의 `decision_end_ns−mono_ns` 자체는 기록하며 소거하지 않는다. 선택 요청의 `policy_compute_ns`와 비교하되 포함 비용 차이를 유지한다.

## 3. 최소 제안 예산 — 승인 전 실행 금지

| 항목 | 제안 |
|---|---|
| 조건 | classification/detection × CPU/GPU × urgent/normal =8. 모델과 등급을 동일시하지 않음 |
| 개발 | 조건당 새 세션1 ×8 =8세션, 진단32요청, warmup64호출 |
| 확인 | 개발 fit 파일을 고정한 뒤 조건당 새 세션1 ×8 =8세션, 진단32요청, warmup64호출 |
| 총 상한 | **16세션 시도, 진단64요청, warmup128호출**. 별도 smoke 없음; 첫 개발 세션도 이 예산에 포함 |
| 반복 단위 | 프로세스 초기화·runtime 생성·warmup·cooling을 거친 세션. 한 세션의 4요청을 독립 반복4개로 취급하지 않음 |
| retry/대체/추가 | 모두0. 첫 기술적/환경/수집 실패에 종료. 실패 세션과 미시도는 분모에 유지 |
| 예상 시간 | 기기와 host가 실행 중인 합계45~60분. 개발/확인 사이 PC fit·검토·충전 대기는 별도 |
| 고정 상한 | 각 phase host3600초 + bounded cleanup45초, 두 phase 합7290초=121.5분. 최초 실패 시 다음 phase도 금지 |
| cooling | 각 phase 시작120초 및 phase 내 7간격×120초. 총16×120초=32분 |
| 시간 근거 | 4요청의 마지막 예정 도착15초 + 마지막 단독 처리, setup/warmup/회수 대략25~50초/세션이라는 예약 가정; 전송/설치 여유 포함. 현재 미측정 새 계측 경로의 시간 보장은 아님 |

독립 개발 세션 n=1/조건, 확인 n=1/조건이므로 세션 간 변동성·검정력·안정된 tail은 추정할 수 없다. 최소안 목적은 계측 계약·수집 가능성 확인과 초기 중앙값 기술이다. 추가 반복을 자동 요청하거나 성능이 좋아질 때까지 연장하지 않는다.

기술적/환경 중단 조건에 해당하지 않는 한 개발 관측값이 크거나 작다는 이유로 확인 phase를 생략하거나 조건·요청 수·중앙값 규칙을 바꾸지 않는다. 개발→freeze→확인 순서 전체가 제안 예산의 한 계획이다.

seed `2026092401`의 실행 순서:

| 개발 index | task / backend / priority | 확인 index |
|---|---|---|
| 0 | classification / GPU / urgent | 15 |
| 1 | detection / CPU / normal | 14 |
| 2 | detection / GPU / normal | 13 |
| 3 | detection / CPU / urgent | 12 |
| 4 | classification / CPU / urgent | 11 |
| 5 | classification / CPU / normal | 10 |
| 6 | detection / GPU / urgent | 9 |
| 7 | classification / GPU / normal | 8 |

개발 순서를 seed로 한 번 정하고 확인 순서는 역순이다. 이는 초기/후기 위치를 뒤집는 설계이며 완전한 시간 효과 제거를 뜻하지 않는다. 조건마다 4요청의 예정 도착은 0/5/10/15초다. 서비스 완료와 독립된 도착이고, 실제 도착에 앞선 요청이 여전히 busy이면 단독 지원 범위 위반으로 중단한다. 5초는 예약 간격이며 검증된 서비스 상한이 아니다. 5초 deadline은 진단용 scenario로 기록할 뿐 정책 차별 지표/UX SLA로 사용하지 않는다.

## 4. 동일 자원·입력과 중단 규칙

- A24 `SM-A245N`, 기존 plan의 동일 fingerprint. 현재 연결 여부는 이번 작업에서 확인하지 않았다.
- 기존 exact EfficientNet-Lite0 / EfficientDet-Lite0, image `00575b9132bb3746` 하나, 동일 image/anchors/labels/model hash, LiteRT1.4.2·XNNPACK·CPU thread1. 이미지 간 일반화 없음. 이 두 모델 binary는 외부 원본 참조만 하고 저장소/새 APK에 넣지 않는다. 기존 앱의 legacy MobileNet asset은 유지한다.
- 매 세션 네 task/backend runtime를 모두 resident로 생성하고 각2회 warmup(총8)을 직렬 수행한다. 본 진단은 지정 backend의 한 요청만 실행한다. 단일 runtime 구성의 메모리나 CPU/GPU 간섭 검증으로 해석하지 않는다. task/backend 전환 분포도 이 동일 cell 반복만으로 검증하지 않는다.
- 세션 전 앱 프로세스 종료 확인, thermal0, memory admission, 충전 분리, phase 시작 배터리≥55%, 이후≥30%, 배터리 온도≤35°C. 고정120초 cooling 후에도 gate 미달이면 더 기다려 통과할 때까지 반복하지 않고 종료한다. sampled thermal0은 모든 하드웨어 스로틀링 부재의 증명이 아니다.
- Activity watchdog120초, workload drain100초, host 종료 poll125초. 원래 단계별 runtime 생성/warmup get timeout30초와 bounded close를 유지한다. 실패/거절/solo 위반 뒤에는 새 calibration 배정을 중지한다. 예약된 후속 도착·미완료는 원래 ledger 분모에 유지하고 bounded drain으로 종료한다.
- warmup 시작/종료/성공·실패를 새 `warmup_trace.json`에 남긴다. complete8호출을 정수로 추정해 쓰지 않고 실제16개 start/end 기록과 대조한다. trace overflow/누락, 잘못된 시간 순서, actual backend/GPU 증거 불일치, 결과 hash·manifest 오류, 환경 이탈은 세션/phase 종료 조건이다.
- event 미완료 요청은 calibration에서 도착 시 복사한 immutable 사실(예정/실제 도착·queue 진입)을 final ledger에 보존한다. 실제 도착 자체가 없으면 해당 시각을 만들지 않는다. 어느 경우도 event 부재를 성공으로 바꾸지 않는다. 이 보완 전후 APK·계획은 별도 v1/v2로 보존하며 두 버전 모두 현재 실측0이다.
- phase claim은 Device 생성/설치 이전에 experiment별 registry의 `*_consumed.json`을 배타 생성한다. 다른 출력 root를 지정해도 같은 phase 재실행은 거절한다. host 초기 연결/설치 실패는 session attempt0일 수 있지만 phase는 소비·중단되어 자동 재시도하지 않는다. 세션별 `attempt.json`과 `launch_attempt.json`/launch stdout/원자료로 실행 의도와 실제 활동을 구분한다.
- 연결 단절은 stopped/error/cleanup/recovery 기록으로 남긴다. 별도 `recover`는 기존 UUID 출력 회수와 bounded cleanup만 수행하고 Activity를 실행하지 않는다. `.part`도 회수 가능하며 원본을 덮어써 mismatch를 없애지 않는다. 이미 회수한 파일과 다르면 새 recovery root에서 보존한다. 계획·APK 변경으로 같은 실험 ID를 이어 실행하지 않는다.
- 설치는 `-r`만 지원한다. 데이터 삭제/패키지 제거가 필요하면 실패 상태와 원인을 보고하며 자동 uninstall/clear하지 않는다. 다른 앱/보안 설정은 변경하지 않는다.

## 5. 수집 후 추정·확인

1. 개발8세션 모두 완전할 때만 `fit`을 수행한다. 요청/manifest identity, 시간·phase·응답 경계, null 호출 포함 정상 호출3n/null2n, event/final ledger, 단독성, 실제 warmup 기록을 먼저 검증한다. host는 환경/admission·GPU full delegation·payload hash·cleanup도 확인한다. 실패 세션을 제외하고 남은 조건으로 완전한 fit을 발행하지 않는다.
2. 각8조건×5구간의 4개 관측에 대해 **중앙값·최솟값·최댓값**, ordinal 원값, 세션수1/요청수4를 보고한다. 중앙값은 치우친 지연의 초기 전형값 기술이며 보수적 상한/잔여 기대값이 아니다. 비대칭·최댓값 급증·표본 부족도 그대로 남긴다. outlier 제거, winsorization, P95/PI/CI 보장은 하지 않는다.
3. 개발 원자료 hash inventory, plan/code hash, 분석 규칙, 값들을 write-once `fit` 파일에 고정한다. 확인 phase는 이 파일 hash를 consumed receipt에 고정한 뒤에만 시작된다. 확인 자료는 fit 입력으로 읽지 않는다. 확인은 동일 입력의 후속 새 세션이며 입력 holdout이나 정책 독립 우수성 평가는 아니다.
4. 확인 세션의 구간별 실제 값, 고정 중앙값 대비 signed error, 초과 횟수/분모4를 보고한다. 확인 결과로 해당 fit을 수정하지 않는다. 향후 수정 시 새로운 개발 버전으로 분리해야 한다. 모집단 오차 보장이나 정책 PASS를 만들지 않는다.
5. 기존 UNKNOWN_OVERRUN은 계속 필요하다. 구간 경과가 추정 이상인데 실제 busy이면 잔여 미확정이다. 초기 중앙값보다 긴 사례를 보고 상수 penalty·미래 실제 종료·조건별 사후 유리한 계수로 대체하지 않는다. 단독 D→A는 calibration 정책 비용이며 adaptive의 해당 항목은 missing으로 남긴다.

단독의 A→S·O→P·P→L은 큐, admission, OS scheduling, 저장장치/cache, 로그 크기에 따라 달라질 수 있다. 네 runtime resident·한 고정 이미지·4회 warm 단독·관측 환경만 지원한다. 병행/고부하·다른 입력·다른 순서에 median을 그대로 쓸 근거가 없으며, 모든 값을 얻어도 `experiment_ready=false`다. 간섭을 식별하려면 별도 matched solo/co-run 및 overlap 위치 통제가 필요하다. 이번 예산에는 넣지 않는다.

## 6. 실제 구현 명령과 산출물

현재 PC 명령(읽기 전용 dry-run, 실제 plan 위치는 종료 기록 참조):

```powershell
python -B -m tools.d1_arrival_timing_calibration check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_bound_v2/calibration_plan.json
python -B -m unittest tools.test_d1_arrival_timing_calibration tools.test_d1_arrival_timing_dev -v
```

APK와 manifest를 **새 위치에 준비할 때만** 사용하는 구현된 PC 명령이다. 기존 경로가 있으면 거절한다. package는 모든 Gradle build output을 새 root로 옮겨 기존 APK를 보존하며 설치하지 않는다.

APK binding은 build receipt의 Android/Gradle 입력 hash와 현재 동일 입력을 대조한다. APK에 들어가지 않는 host Python은 plan의 별도 source hash로 동결한다. host validator만 수정했다고 같은 Android binary를 재빌드할 필요는 없지만, 새 plan/hash와 관련 PC 검증은 필요하다. 원래 build receipt를 고쳐 hash 차이를 없애지 않는다. GPU raw의 `unverified_requires_host_delegate_log`도 그대로 보존하고, 별도 delegate proof를 통과해야 host 검증 완료로 처리한다.

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME='C:\Users\LG\AppData\Local\Android\Sdk'
$base='C:\Users\LG\Documents\D1Check_Arrival_Extension'
python -B -m tools.d1_arrival_timing_calibration package --output "$base\timing_calibration_apk_v2"
$build=Get-Content "$base\timing_calibration_apk_v2\build_receipt.json" -Raw | ConvertFrom-Json
python -B -m tools.d1_arrival_timing_calibration prepare --source-plan "$base\independent_evaluation_plan_v1_proposal\evaluation_plan.json" --output "$base\timing_calibration_bound_v2" --apk $build.apk_path --build-receipt "$base\timing_calibration_apk_v2\build_receipt.json"
```

**이 아래는 제안16세션 예산 승인 후에만 실행한다. 이번 작업에서 실행하지 않는다.** `$A24Serial`은 당시 연결된 A24의 실제 serial을 지정한다. `Device.identify`가 모델/fingerprint/유일 연결을 다시 확인한다. 설치 및 warmup도 run 안에 있으므로 별도 smoke를 실행하지 않는다.

```powershell
$base='C:\Users\LG\Documents\D1Check_Arrival_Extension'
$plan="$base\timing_calibration_bound_v2\calibration_plan.json"
$planHash=(Get-FileHash -LiteralPath $plan -Algorithm SHA256).Hash.ToLowerInvariant()
$adb='C:\Users\LG\AppData\Local\Android\Sdk\platform-tools\adb.exe'
$A24Serial=Read-Host '승인된 실행에 사용할 연결된 A24 serial'
python -B -m tools.d1_arrival_timing_calibration run --plan $plan --phase development --output "$base\timing_calibration_development_run_v1" --adb $adb --serial $A24Serial --approved-total-cap 16 --expected-plan-sha256 $planHash
# 위 개발 phase가 전부 완료된 경우에만 다음 명령을 실행한다.
python -B -m tools.d1_arrival_timing_calibration fit --plan $plan --run "$base\timing_calibration_development_run_v1" --output "$base\timing_calibration_fit_v1.json"
python -B -m tools.d1_arrival_timing_calibration run --plan $plan --phase confirmation --output "$base\timing_calibration_confirmation_run_v1" --adb $adb --serial $A24Serial --approved-total-cap 16 --expected-plan-sha256 $planHash --freeze "$base\timing_calibration_fit_v1.json"
python -B -m tools.d1_arrival_timing_calibration confirm --plan $plan --run "$base\timing_calibration_confirmation_run_v1" --freeze "$base\timing_calibration_fit_v1.json" --output "$base\timing_calibration_confirmation_report_v1.json"
```

중단 시 위 run 명령은 재실행하지 않는다. 회수만 필요할 때 실제 시도한 UUID를 지정해 구현된 `recover --plan $plan --adb $adb --serial $A24Serial --session-id <실제-시도-UUID> --output <새-회수-root>`를 사용한다. 이 두 꺾쇠 값은 실제 시도 기록/새 경로로 바꿔야 하며 현재 실측 UUID나 결과가 있다는 뜻이 아니다.

예상 산출물: 새 APK/build receipt/log, plan+16 manifests, PC receipt; 향후 phase consumed/attempt/complete 또는 stopped, 세션 attempt·launch·identity·환경·GPU 로그·validated/host_cleanup, 원본 manifest/request/event/result/decision_trace/warmup_trace/summary/environment/cleanup/failure, 개발 fit freeze와 확인 오차 보고서. 실제 측정·fit 파일은 이번 PC 준비에서 생성하지 않는다.

## 7. 검증·종료 기록

최종 검증 대상은 `2904165` + 이번13개 소스·문서 변경이다. 기기 연결/설치/실제 추론·본 simulation은 미실행, 소비0/16이다. 종료 commit/worktree는 외부 `timing_calibration_pc_verification_v1/GIT_FINAL.json`에 기록한다.

| 항목 | 결과·근거 |
|---|---|
| JVM / 관련 컴파일 | PASS 27: calibration7 + timing-dev13 + 기존 정책7, failure/error/skip0. XML 시각 2026-09-23T17:13:09Z(09-24 02:13 KST) |
| Python | PASS22: calibration13 + 기존 timing-dev9. 실제 device/subprocess 금지 mock, synthetic 경계/중단/소비/fit 분리 fixture. 외부 `PC_PYTHON_TESTS_FINAL.txt` |
| APK build root | query task가 새 외부 root를 반환했고, v2 `assembleModelProbe` PASS(2026-09-24 KST). 기존 APK를 덮어쓰는 assemble은 실행하지 않음 |
| 새 APK | `timing_calibration_apk_v2/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, 106010140 bytes, SHA `7bf84ce9997ed1fc0866ed89c38c84a78f37d5589a04eedef28ff65f16ae11e5` |
| 현행 plan | `timing_calibration_bound_v2/calibration_plan.json`, SHA `a340a6c61e4eb4a85591ce226965495627ebd6751c3db4075b7b558a9d0553a2`; manifest16개, 개발/확인 UUID 분리 |
| dry-run | PC_PLAN_VALID_NOT_MEASURED, apk_bound=true, 16/64/128, experiment_ready=false, ADB0/추론0/생성 측정값0. `PC_PREPARATION_RECEIPT.json`에96개 source hash와 입력 identity 결합 |
| 보존 | 기존20값 null 유지, 기존 정책/plan/device runner/GPU proof 코드 불변. 원본·과거 동결 결과 감사 재실행 없음. diff --check PASS |

외부 공통 root는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/`이다. `timing_calibration_preparation_v1`(APK 미결합), `timing_calibration_bound_v1`/`timing_calibration_apk_v1`(미완료 arrival 사실 보존 수정 전)은 덮어쓰지 않고 보존한다. **현행 실행 후보는 bound_v2/apk_v2뿐**이다. 모든 준비 버전의 실측0이며, v1/v2 자료를 측정 표본으로 합치지 않는다.

전체 테스트/과거 원본 분석은 반복하지 않았다. 변경된 공통 Recorder/Activity/validator의 회귀 범위만 재검증했고, 미완료 도착 보존 수정 후 관련 테스트·새 격리 APK만 갱신했다. CLI `package`, `prepare`, `check`, `run`, `fit`, `confirm`, `recover`는 구현되어 있으나 `run`/실제 자료의 `fit`/`confirm`/기기 `recover`는 미실행이다. synthetic 단위 테스트 성공을 실기기 PASS로 표시하지 않는다.

남은 실행 전 조건은 이 **16세션 예산 승인**, frozen hash/아직 소비되지 않은 registry 확인, 동일 A24와 연결·초기 앱·배터리/thermal/memory gate다. 승인되어도 일반 적응형 성능 실험 READY를 선언하거나 과거 fixed-split을 재개하지 않는다.
