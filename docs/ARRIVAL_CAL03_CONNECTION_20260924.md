# ARRIVAL-CAL03-CONNECT-01 — priority별 추정 연결과 PC 실행 모델

2026-09-24. 시작 `46b6c20b35c74e993f22c111522f22253a6d4154`, 작업 브랜치 `feature/arrival-scheduling-20260923`, 로컬/원격 일치·clean. **PC 구현·검증 완료, Android 앱 연결·새 실기기 검증·정책 성능 검증은 미완료, experiment_ready=false.**

CAL-03 개발/확인 수집을 반복하지 않았다. 동결40값·확인 오차·기존20null·기존 CONDITIONAL/CONDITIONAL_TIMING_DEV_1·198요청 FAIL·fixed-split 부분 결과·종료 계획과 과거 원인 미확정을 보존한다. 확인 자료를 다시 읽어 튜닝하지 않았다. 새 파생 설정도 이미 결과가 공개된 뒤 만든 개발 산출물이며 독립 검증이 아니다.

## 실제 연결한 기능과 보존 경계

- [d1_cal03_connection.py](../tools/d1_cal03_connection.py): 기존 calibration `observations`/timing validator를 재사용하는 변환 계층, 8개 task×backend×priority의 동결40슬롯, 개발 요청의 전체 구간 통계, causal snapshot 정책 `CAL03_SOLO_CONDITIONAL_PC_DEV_1`.
- [d1_cal03_simulator.py](../tools/d1_cal03_simulator.py): 도착→큐→판단 예약→dispatch→실행→결과→저장→worker release→AVAILABLE의 유한 이벤트 엔진. 실제 공동 구간 벡터는 엔진에만 전달하고 정책에는 현재 도착 큐와 관측 lane 상태만 전달한다.
- [test_d1_cal03_connection.py](../tools/test_d1_cal03_connection.py): 변경 위험에 직접 대응하는21개 PC 테스트. 기존 Kotlin/Activity/APK/20필드 설정/기존 host 실행기에는 변경이 없다. 이 정책 ID는 **PC 개발용**이며 앱 manifest에서 선택 가능한 정책이라고 제시하지 않는다.
- 기존 `d1_support_simulation.py`는 동결 유한 배치/병행 원자자료 계약이다. `d1_arrival_simulation_plan.py`는 과거 별도 탐색 계획만 생성하며 worker_release를 점유 종료로 제안했던 버전이다. 이를 소급 변경하거나 새 L 경계와 혼합하지 않는다. 새로운 도착 엔진은 기존 계약을 실행하지 않는다. 이번8요청은 엔진 점검이며 확장 본 시뮬레이션/정책 비교 실행이 아니다.

## 시간 대응표

D=decision snapshot(기존 monitor 획득 후), A=dispatch/ASSIGNED, S=execution_start, O=output_ready, P=persist_complete, W=worker_release, L=scheduler AVAILABLE. Android 관측은 같은 elapsedRealtimeNanos/ns다. 통계 중앙값의0.5ns는 반올림하지 않으며 이벤트 실현값은 정수ns다.

| 항목 | CAL-03 관측/새 연결 | 적용 판정과 중복·누락 방지 |
|---|---|---|
| 예정/실제 도착→큐→D | ledger/trace에는 존재하나 새40값에 없음 | 부하별 도착 지연·큐/lock 지연 모형 미측정. 시뮬레이터는 도착 지연0·즉시 큐진입을 명시적 가정으로만 사용 |
| D→A | 고정 calibration 경로의 동결값8개 보존 | 고정 경로에는 직접 관측. 새 적응형 정책 비용은 **missing/null**, 고정값을 복사하지 않음. 이미 busy인 요청의 잔여 점유에 다시 더하지 않음 |
| A→S | dispatch→worker 대기/admission→실행 시작 | 직접 관측; 새 정책·큐 부하로의 전이는 조건부. 이를 S→O로 합쳐 service라고 부르지 않음 |
| S→O | 입력 준비·host inference API·출력 처리 포함 | 단독 resident 요청의 직접 관측. GPU kernel 시간/초기화 시간 아님. 정책/엔진은 별도 inference 비용을 중복 추가하지 않음 |
| O→P | urgent도 결과를 실제 저장 | normal 응답에는 적용, urgent 응답에는 **N/A**지만 lane 점유에는 적용. N/A를 미측정 또는0으로 대체하지 않음 |
| P→W→L | 동결값은 P→L, 원 ledger에는 W도 있음 | 응답 예측에는 N/A, lane 예측에는 적용. event 저장·callback 포함. W에서 busy를 해제하거나 P→L 시계를 다시 시작하지 않음 |
| A→응답 | urgent A→O / normal A→P를 요청별 계산 후 중앙값 | phase 중앙값 합 대신 개발자료의 별도 공동 구간 통계. D→A/큐 대기는 포함하지 않음 |
| A/S/O/P→L | 각 원점→L의 요청별 차를 먼저 산출 후 중앙값 | lane 전체/단계별 잔여 점유의 점예측. 여러 전체 구간을 다시 합하지 않음 |
| 초기화·warmup | 요청 이전의4runtime/8warmup | resident 요청 예측에는 N/A. cold start에 적용 불가 |
| CPU/GPU overlap·고부하 준비/저장/callback | CAL-03은 단독·5초 간격 | 간섭·부하 의존 비용 미측정. 엔진에서 concurrency>1은 OUT_OF_SUPPORT로 차단 |

파생 통계는 `median(r.end-r.start)`이다. `median(A→S)+median(S→O)+...`가 아니다. 예를 들어 분류/CPU/일반의 A→P 중앙값은 **173.536115ms**, 개별 구간 중앙값 합은 **167.859308ms**, 차이는−5.676807ms다. 이는 개발 동일4요청 내 계산 차이이며 새 확인 오차가 아니다.

동결 fit SHA-256 `f4f55b65756ed965e6f69e70f6e6d50ce30576c45911aae83afa5944314106fb`는 변경하지 않는다. 새 설정 `cal03-priority-joint-estimates-dev-v1`은 원40개 통계·response/lane 적용 표식, 공동 구간40개 통계, fit/plan hash·실행 source identity·개발 입력 hash, 모델/입력/tensor/runtime/APK/fingerprint·CPUthread1·resident4·warmup8·단독·환경 범위를 보유한다. 모델 바이너리/키/원자료는 Git에 포함하지 않는다.

## 정책의 실제 동작

도착한 큐만 urgent→ordinal→ID 순으로 본다. lane 상태는 task와 priority를 함께 보유한다. 후보별 A→응답, A→L 중앙값을 표시한다. 점유 중 lane은 추정에 관계없이 AVAILABLE callback 전까지 busy다.

현재 phase의 중앙값보다 경과가 크거나 같으면 `UNKNOWN_OVERRUN`, 시계 원점이 없으면 `UNKNOWN_MISSING_ORIGIN`이다. 초과 잔여를0/임의 상수/무한대로 채우지 않는다. 아직 phase 중앙값을 넘지 않았다면 해당 phase 원점→L의 **공동 구간 중앙값−경과**를 표시한다. 이는 조건부 잔여시간 분포 추정이 아닌 단순 점예측이며 보장이 없다. WORKER_RELEASED에서도 P를 원점으로 유지한다.

1. **엄격 기본 모드:** 한 lane이라도 busy면 단독 지원 범위를 지켜 대기한다. 둘 다 AVAILABLE이고 adaptive D→A가 missing이면 CPU fallback한다. CAL-03 후보/잔여값은 실제 계산하지만, 미측정 비용이 포함된 전 구간 비교로 GPU 선택을 정당화하지 않는다. CPU fallback은 성능 보장이나 P의 기여가 아니다.
2. **명시적 PC 가정 모드:** 호출자가 공통 D→A 가정값을 별도로 제공할 때만 A→응답 중앙값에 공통값을 더해 CPU/GPU 최소 응답 후보를 선택한다(동점CPU). 원 설정의 missing은 그대로다. 선택에 공통 비용이 상쇄되더라도 총 응답에는 포함한다. 실제로 공통/고정이라는 근거는 없으므로 미검증 가정으로 출력한다.

현재8조건의 단독 중앙값은 CPU가 빠르지만 최선의 혼합 정적 B2를 선정한 결과가 아니다. 이 단독 제한·fallback PC 정책은 완전한 B3/P도 기존 CONDITIONAL의 대체 버전도 아니다. PLAN의 강한 B2/B3/P·기존 시스템 비교 요구는 유지하며 FIFO만으로 대체하지 않는다. deadline/aging/일반 서비스 보장/간섭 보정을 새로 구현하지 않았다.

## 최소 실행 모델과 해석

- 예정 도착 이벤트는 완료와 독립적이다. 엔진은 미래 이벤트를 보유하되 정책 API에 미래 도착, 실제 종료, 선택하지 않은 경로의 실현값을 전달하지 않는다. 부가 필드나 미래 도착 ticket은 거절한다.
- 정책 예상값은 개발 중앙값, 실현은 개발4요청의 **A→S/S→O/O→P/P→W/W→L 공동 벡터**를 원 ordinal 순으로 순환한다. 서로 다른 구간을 독립 추출하거나 분포/tail/CI를 만들지 않는다. 새 도착/순서에 옮기는 것은 exchangeability 가정이지 실측 예측 검증이 아니다.
- 가정한 판단 비용 동안에도 도착은 계속된다. 이미 선택한 요청을 예약하고 A에서만 lane을 점유한다. 동시각에 이미 예약된 이벤트를 삽입 순서로 모두 처리한 후 판단한다. L과 도착이 같으면 둘 다 관측한다. 실제 OS 동률 순서를 검증한 것은 아니다.
- O/P의 응답 완료와 L의 terminal 성공을 구분한다. W만으로 재사용하지 않는다. 1..32요청/시계상한120초의 PC 점검 범위이며 원 실측 watchdog을 실행/변경하지 않는다. horizon 이후 대기/실행 요청은 `unfinished_at_horizon`, 아직 도착하지 않은 요청은 `not_arrived`로 planned 분모에 남긴다. 응답 준비 수와 terminal 성공 수도 별도다.
- 성공 서비스 벡터만 있는 엔진이다. 앱 실패/거절/만료 발생모형은 **미지원**이며 그 발생률을0으로 추정하지 않는다. scenario deadline은 soft이고 늦은 응답은 late_success로 남긴다. 완전 drain일 때만 첫 예정 도착→마지막 L makespan 및 planned/makespan throughput을 계산한다. 미완료면 둘은null이다.
- PC policy 계산 경과는 `pc_compute_ns`로 별도 출력한다. Android 비용으로 전용하거나 동결값에서 빼지 않는다. 시뮬레이션의 D→A 가정값은 선택된 호출의 응답·전체 완료 구간에 포함한다. 선택 없는 판단의 가상 비용은0 가정이며 미측정을0으로 채운 설정이 아니다. 각 event batch 뒤 판단하는 추상 엔진으로, Activity의 정확한 callback 호출 빈도·no-selection 부하까지 재현하지 않는다.

## 검증과 실제 산출물

2026-09-24, 시작 HEAD+이번 새 Python3파일/문서 변경에 대해 수행했다. 새 테스트21건 통과(초기 fixture 접근 오류3건 수정 후21/21). 새 Android 코드가 없으므로 Gradle/APK/실기기·이전 전체 테스트/감사를 반복하지 않았다.

- 구간 이중 계산/중앙값 비가산성, priority/N/A/missing 구분, A→S 지연·service overrun, O/W 뒤 busy 유지, P 원점 유지, 두 lane busy/선택 없음, snapshot 재생·미래정보 거절, 엄격fallback/가정선택 차이.
- 실현시간을 바꿔도 최초 선택 불변, 완료와 독립인 도착, 판단 비용 중 도착, callback/도착 동률, 전체 분모·미완료, overlap/미지정 비용 차단, 기존null 정책 의미 유지.
- 개발8세션32요청을 기존 validator로 읽기 전용 경계 재생하고 새 변환과 원 동결 median의 대응 확인. 24lane 재사용쌍. 새 자료 적격성 감사나 독립 예측 검증이라고 재명명하지 않는다. 확인8세션은 새 변환 입력에 포함하지 않는다.
- 동일 8요청 엔진 점검(최초 실행과 가정 표기 보완 후 최종 재실행): planned/arrived8, 엔진 terminal8·완전drain. 공통 판단 비용 **1ms는 가정**, 도착100ms 간격도 PC 점검용이다. 기기 호출0. 성능 비교/우월성/정확도PASS를 산출하지 않았다.

외부 로컬 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/cal03_connection_pc_v1/`:
`estimates.json`, `realizations.json`, `boundary_replay.json`, `receipt.json`, `scenario.json`, `engine_check.json`(초기), `engine_check_final.json`(최종), `VERIFICATION.json`, `FINAL_REPORT.md`, `REPRODUCE.ps1`. 외부 파일은 GitHub에 포함되지 않는다.

```powershell
python -B -m unittest tools.test_d1_cal03_connection -v
# 새 출력 폴더 사용. 원 fit/확인 자료를 다시 산출하지 않는다.
python -B -m tools.d1_cal03_connection --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_plan_v3/calibration_plan.json --fit C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_fit_v1.json --development C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_cal03_run_v1/development --output C:/Users/LG/Documents/D1Check_Arrival_Extension/cal03_connection_pc_reproduced_v1
python -B -m tools.d1_cal03_simulator --bundle C:/Users/LG/Documents/D1Check_Arrival_Extension/cal03_connection_pc_reproduced_v1 --scenario C:/Users/LG/Documents/D1Check_Arrival_Extension/cal03_connection_pc_v1/scenario.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/cal03_connection_pc_reproduced_v1/engine_check.json
```

## experiment_ready 필수 조건

| 조건 | 현재 판정 |
|---|---|
| exact 모델/입력·기기·단독 resident 관측, 개발/확인 분리 | CAL-03 기존 범위에서 확인됨; 이번 변경의 기기 검증 아님 |
| task×backend×priority·응답/점유 경계·누락 구분 | PC 변환/정책/엔진 구현 및 관련 테스트 통과 |
| busy 유지·초과 상태·lane callback 경계 | PC 통과; 기존 CAL-03 단독 재사용48쌍 증거 보존 |
| 적응형 D→A·새 정책 기록/선택 overhead | 미측정. 엄격모드는fallback, 가정모드는PC전용 |
| 큐 부하의 준비·저장·callback 비용과 CPU/GPU 병행 모형 | 미측정/미검증; 병행 실행 차단 |
| 중앙값 초과의 잔여시간·안전 상한/예측 정확도 허용폭 | 미확정. UNKNOWN_OVERRUN 유지;32.270ms를 margin으로 사용하지 않음 |
| 새 앱 정책 연결·기기 반복/자원/환경 검증 | 미구현·미실행. 실험 manifest 지원/APK 준비라고 주장하지 않음 |
| B2/B3/P 차별성·정적 기준 선정·목적/허용손실·독립 평가 | 기존 계약 유지, 미충족; 이번 작업으로 새 성공 기준을 확정하지 않음 |

따라서 전체 `experiment_ready=false`. 독립 확인의 기존 performance_pass=null은 바꾸지 않는다.

## 다음 최소 행동

먼저 이 PC 계약을 기준으로 **새 정책 호출의 D→A 및 큐 부하 전이만 확인할 개발 수집 설계**를 작성한다. 단독 관측의 값 연결은 끝났으므로 같은 CAL-03을 반복할 이유는 없다. 앱 연결 전에는 후보 계산/trace 비용을 실제 목표 경로에서 재야 절대 응답 예측을 사용할 수 있다. queued 상태의 A→S/P→L 전이가 필요한지도 최소 조건으로 포함한다. 반복 수/예산/허용폭은 이 작은 표본으로 보장할 수 없어 여기서 확정하지 않는다.

CPU/GPU 병행 정책을 다음 범위로 선택할 때만 동일 입력/실행 순서/환경의 단독 대조와 통제된 overlap을 비교해야 한다. 이는 간섭 식별을 위한 별도 질문이며 현재 자료의 시간 차이나 PC 시나리오로 대신할 수 없다. 추가 정책 개발의 기여는 B3 대비 결정 차이와 강한 정적 대조에서 검토해야 하며, 이 보정 보완을 P의 독창성으로 주장하지 않는다. 새 측정/본 simulation/정책 평가 실행은 별도 승인 대상이다.
