# S26 시뮬레이션 계획: 열·서비스·실행 구조 검토

작성일: 2026-10-11. 전문가 역할: 열 동역학·서비스 식별·이종 실행. **계획과 읽기 전용 조사만 수행했다. 적합·시뮬레이션 배치·기기 명령은 0건이다.** 이 파일 외 프로젝트 문서는 수정하지 않았다.

## 1차 주장과 직접 확인

기존 `d1sim`을 보존하면서, 현재 S26 혼합 요청의 exact 계약으로 별도 경험 모형을 시작한다. A24 열·전력·서비스 계수, MobileNet 단일 작업의 CPU4/CompiledModel 프로필을 새 CPU1·EfficientNet/EfficientDet 혼합 계약에 직접 옮기지 않는다.

새 엔진을 처음부터 만드는 계획은 아니다. 기존 `env`/`env_v2`, `run_compare_v2`, `policy_eval_v2/sim`·`run_eval`, `v3/predict_v3`·`predict_v3_v2`와 추출·판독 도구는 계약을 대조해 재사용한다. 새 작업은 혼합 CPU1·exact task·request phase를 받는 별도 profile/adapter와 지원 mask다. 기존 v0/v1/v2·throttle v21/v22, `modelerr1009`·`GPUerr1011`·GPU holdout 근거는 각 동결 HEAD·모형·입력·과거 테스트 대상 버전에 묶어 보존한다. 과거 PASS를 새 혼합 adapter의 PASS로 전용하지 않는다.

직접 읽은 원격 기준은 `s26-measure=0a0749890fba2452c5907433c6bea476a2da7e24`, `s26-mixreq=21cba44faa5fff1fb9703b590aa536a6207f8de5`다. 품질 경계는 루트가 확인한 `s26-quality20=5857152ad8244c41975843ded77dd33024f38f2d`의 별도 품질 검토를 따른다. 세 브랜치의 코드·APK·모델을 하나의 동결 실행본이라고 표현하지 않는다.

- 구 V22-M은 MobileNet에서 개발한 열 구조에 EfficientNet용 NPU/GPU 입력 multiplier만 더한다. CPU4 controller·기준 서비스 등은 이전 구조를 유지한다. `g_m`을 두 모델의 CPU1 혼합 요청·persist·전체 lane 점유에 대한 검증으로 읽을 수 없다. [V22 코드](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/d1sim/throttle_v22.py).
- 구 열 프로필의 `tau_f=34.4`, `tau_s≈480.55`, `tau_a=30`초는 해당 과거 자료의 고정값·적합값이다. 새 혼합 자료의 물리 시간상수 식별 결과가 아니다. 냉각 비대칭·BAT 초기 body 보정도 함께 포함돼 독립적인 pole만 비교하는 모형과 다르다. [V22 열 프로필](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/d1sim/profiles/throttle_v22_thermal.json).
- 대표 R4C 요청에는 `actual_arrival_ns`, `dispatch_ns`, `execution_start_ns`, `host_inference_start_ns`, `host_inference_return_ns`, `output_ready_ns`, `persist_complete_ns`, `worker_release_ns`, `lane_available_ns`가 있다. queue를 포함하는 response와 host 호출 시간, 전후 처리·persist·lane 해제를 구분할 수 있다. [대표 requests](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1/device/requests.json).
- R4S NPU manifest의 실제 `used_keys`는 분류 NPU＋탐지 CPU다. CPU/GPU/NPU runtime이 생성됐다는 사실은 세 건 동시 실행이나 탐지 GPU 실행의 증거가 아니다. 분류 원본 SHA `6c7ab0a6…`, NPU 변환본 `311e4aac…`, 탐지 원본 `40338edf…`를 별도 artifact로 묶어야 한다. [대표 NPU manifest](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4S_blocks/S26_MIXREQ_09_S26_NPU_PARALLEL_V1_a1/device/manifest.json).
- A 블록의 CPU 정책도 여러 runtime을 resident로 생성한다. N 블록은 NPU runtime을 추가한 resident 집합이다. 동일 `classification_CPU`라는 이름만으로 resident 기준부하·환경이 동일하다고 간주하지 않는다.

## 38.1°C plateau의 해석

R4S의 유효14세션에서 보고된 SKIN peak38.1°C는 열 차이를 구분하기 어려운 지표다. 그것만으로 같은 열 발생량, 같은 AP 열 이력, 열과 서비스의 인과관계를 주장할 수 없다.

대표 유효 R4S index0의 `hal.csv`를 읽으면 실제 SKIN38.0°C가85행, 38.1°C가6행이고 여러 값으로 가열·냉각한다. 따라서 이 한 세션은 summary에 상수를 넣은 것만으로 설명되지 않는다. 반대로 실패 N13/N14의 보고값에는38.2~38.9°C도 있어 전체 센서의 38.1°C 고정 clip도 확인된 사실이 아니다. [대표 원시 HAL](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4S_blocks/S26_MIXREQ_00_CPU_URGENT_ONLINE_V1_a1/host/hal.csv).

먼저 raw peak·공통720초 peak·부하600초 peak·센서별 파싱·중복 및 plateau 길이를 대조한다. 유효 세션만의 peak가 모이면 drain 성공 조건으로 인한 선택편향도 의심해야 한다. 유효14/실제18/실패4/준비 중단2, N 유효쌍2/A 유효쌍4를 각각 보존한다. 실패 prefix는 관측 종료까지 진단하되 누락된 온도·J·완료 시간을 정답으로 채우지 않는다. 원 자료의 무효 판정을 성공으로 바꾸지 않는다.

## 시각·상태·응답 경계

대표 R4S index0 HAL은249행이며 device boottime 간격 평균3.2812초, 최소3.19/최대3.58초다. 이는 전력 샘플의 약900ms 주기와 다르다. `pc_ms`·`device_boottime_s`만 있고 읽기 전후 bracket은 없으므로, 요청의 단조시계와 HAL boottime의 원점·의미를 먼저 확인한다.

정렬은 기기 시계를 기준으로 하고, 최근 과거 표본만 서비스 예측 입력으로 허용한다. 다음 온도 표본을 보간해서 과거 요청의 서비스 predictor에 넣지 않는다. ±한 HAL 관측 간격의 정렬 이동으로 결과 민감도를 공개하되 **통계적 신뢰구간이나 보증 오차로 표현하지 않는다**. 센서 내부 갱신 지연은 이 파일만으로 식별되지 않는다.

완료 응답은 기존 계약의 urgent output/normal persist 경계를 유지한다. lane은 `lane_available` 전까지 재배정하지 않는다. host 호출이 끝난 뒤 persist 중인 요청도 전체 성공률 분모와 해당 lane 점유에 남긴다. 전력·열의 경험 state는 host 호출만이 아니라 전후 CPU 처리·쓰기까지 포함하는 측정 계약을 명시한다.

## 최소 모형과 순서

서비스 후보는 이번 단계에서 두 구조로 제한한다.

| 후보 | 정의 | 역할·경계 |
|---|---|---|
| S0 | exact task/backend/context별 고정 phase 벡터 또는 전체 세션 블록 재생 | 1차 기준선. 요청별 독립 임의 추출로 순서 상관을 없애지 않는다. 5phase 안의 host 호출은 추가로 분해·공개한다. |
| S1 | S0＋실행 누적시간 또는 누적점유 한 변수의 제한된 감속 | CPU 장기 후반 감속을 예측하는 경험 후보. 온도 효과라고 명명하지 않는다. 둘 중 predictor 하나를 결과 전에 정하고 자유도를 제한한다. |

S2인 온도→서비스 식은 이번 적합 grid에서 제외한다. 같은 시간/누적작업량에서 다른 열 이력과 회복을 만든 자료가 없으면 time-only보다 예측이 나아져도 인과적 스로틀 식별은 아니다. host 호출·전후 phase를 각각 확인하여 단순 queue 증가를 추론 감속으로 바꾸지 않는다.

온도 후보도 두 구조로 제한한다.

| 후보 | 정의 | 역할·경계 |
|---|---|---|
| T0 | 작업 시작 전 최종 AP/SKIN을 유지하는 persistence | 적합0 기준선. AP와 SKIN은 별도 관측이며 BAT·실내온도와 혼동하지 않는다. |
| T1 | 예측 점유 state의 양의 1pole 경험 응답, AP/SKIN별 gain·초기 anchor | 유한한 τ 범위와 선택 규칙을 적합 전에 등록한다. 센서별 동역학이며 물리 RC·전력 rail 식별을 주장하지 않는다. |

2RC, 냉각 비대칭, body 초기상태 추가, 신경망·GP, 온도→서비스를 한꺼번에 선택하지 않는다. T1의 부하·냉각 잔차를 먼저 보고, 추가 구조가 필요한 구체 반례가 있을 때 별도 ID로 확장한다. 구 순차 MobileNet 자료는 구조 참고·조건부 민감도만 허용하고 주 적합은 새 CPU1 혼합 exact 계약으로 제한한다.

전력 적격성 실패가 모든 온도 B 모형을 자동 차단하지는 않는다. **예측전력→열 입력**은 전력 gate를 통과해야 하지만, **예측 점유 state→온도 경험 gain**은 별도로 검증할 수 있다. 후자는 전력·열의 물리 연결을 식별했다는 의미가 아니다. 새로운 임의 온도 threshold나 gauge 실패를 보정하는 열 gain을 만들지 않는다.

## 시간상수·초기상태의 실무 식별

주장 가능한 것은 먼저 경험 응답의 예측 가능성이다. 수치 rank가 충분하다는 사실만으로 독립 state gain·τ·ambient·hidden H의 물리 식별이 완료되지 않는다.

1. 각 상태의 실제 노출·반복·부하 전후 온도 변화, 단독/병행 열 basis의 선형 관계와 condition을 확인한다. 항상 같은 비율의 solo/joint면 각 gain을 독립 항으로 적합하지 않는다.
2. τ profile이 평평하거나 경계에 붙고, 초기 anchor/시각 이동에 따라 최선값이 크게 달라지면 시간상수는 미식별로 판정한다. 특히 짧은192요청 창만으로 약480초의 느린 항을 새로 식별할 수 있다고 전제하지 않는다.
3. 짧은 pre에 ambient와 여러 hidden state를 자유롭게 동시에 맞추지 않는다. 최종 pre anchor와 제한된 pre 기울기, 또는 기록된 준비·conditioning 이력을 우선한다. 알려지지 않은 이전 부하를0으로 둘 경우 가정이라고 표시한다.
4. initial AP/SKIN/BAT·resident 집합·실내온도 미확인·SOC·충전 이력을 기록한다. 게이트 PASS와 작업 시작 상태는 별개다. 게이트 뒤 setup/warmup/baseline 동안의 변화도 고려한다.

[HotSpot 원 논문](https://www.cs.virginia.edu/~skadron/Papers/hotspot_isca03.pdf)은 RC 지수응답과 센서·초기조건의 중요성을 뒷받침한다. [DATE2018 스마트폰 피부온도 연구](https://www.date-conference.com/proceedings-archive/2018/pdf/0771.pdf)는 거의100% utilization에서의 계측이 낮은 온도 조건의 예측 오차로 이어질 수 있음을 보고한다. 해당 물리 구조·센서·기기·오차 수치를 이 S26 AP/HAL 계약으로 전용하지 않는다.

## 평가·분할·추가 실측 발동

- A는 실제 일정 조건부 오차이고, B는 예정 도착부터 서비스·queue·점유·온도를 예측한 오차다. B에 미래 실제 온도·duty·완료 queue·lane 시각을 넣지 않는다. 실제 미래 온도/전력은 정답에만 쓴다.
- R3/R4C는 이미 본 자료다. 같은 run의 앞/뒤·부하/회복 창이나 요청 표본을 독립 fold로 나누지 않고 pair/day/block 전체를 묶는다. MobileNet→EffNet 전이, short→long 전이, CPU resident4→5 전이는 별도 외삽 판독이다.
- 서비스: host 호출·phase별 MAE, 완료-P95 오차, 전체 도착 기준 성공률, 실제·예측 실패/미완료를 함께 보고한다. 온도: AP/SKIN별 MAE·최대오차·peak·부하/냉각 방향과 초기값 민감도를 별도로 보고한다. °C/J/ms를 임의 합산하지 않는다.
- R4S는 유효 세션의 탐색적 장기 stress 자료와 실패 prefix로 취급한다. 유효 N2쌍을 A4쌍과 합쳐 검증된 NPU 효과 표본수를 늘리지 않는다.
- 품질20의 exact artifact/backend/정밀도 gate가 미통과인 경로는 관측 재생·비용 기술은 가능하되 정책 후보로 승격하지 않는다. NPU host 호출·계약 통과는 코어 직접 실행 증거와 구분한다.

추가 실측은 다음 중 하나가 확인되고, 해당 질문·예산·분할을 먼저 등록한 뒤에만 발동한다: ① S0의 CPU 후반 서비스 잔차가 커서 S1 확인이 필요함, ② T1의 부하/냉각 방향 또는 τ/초기값이 안정적으로 식별되지 않음, ③ 온도→서비스를 정책에 넣기 위해 시간/열 교락 분리가 필요함, ④ 새 backend/병행 조합·품질·resident 계약을 후보로 열어야 함.

③의 최소 설계는 동일 warmup·resident·목표 probe와 같은 elapsed 시각을 유지한 가열/유휴 대조다. 부하 전·직후와 등록된 회복 간격의 host 호출을 비교하고 순서를 교차한다. 시간만 지난 대조와 감속 후 회복을 함께 확인하지 못하면 온도 함수를 추가하지 않는다. 특정 회복초·반복수·PASS threshold는 기존 자료의 편차 감사 뒤 사전 등록할 제안값이며 이 문서가 실행 승인을 만들지 않는다.

최소 정책 확인은 품질과 비용 모형 gate를 통과한 기존 CPU 직렬과 실제 검증된 병행 하나부터 시작한다. 같은 도착열·기한·완료량·출력 계약, 교차 순서와 독립 확인 세션을 고정한다. 최대2건 병행만 허용하고 분류 GPU＋탐지 CPU, 분류 NPU＋탐지 CPU 등 실제 검증 조합별로 지원 표를 작성한다. GPU＋NPU, 탐지 GPU, 3건 동시 실행은 별도 실측 없이는 마스킹한다. 장기200ms stress의 실제 일반 기한 실패를 낮은 부하 선택이나 drain 연장으로 지우지 않는다.

## 2차 토론 반론과 수정 합의

- 에너지 역할의 반론을 반영했다. gauge 내부 비교 FAIL·정책 차이 부호 역전이 남으면 E1 prelate 보정과 전력→열 입력을 먼저 확장하지 않는다. raw `power_sample`과 admission sensor 중복, 전력 주기와 HAL 주기는 분리한다. 전력 gate가 실패해도 점유 기반 경험 T1의 독립 검증은 가능하다는 구분을 추가했다.
- 검증 역할의 반론을 반영했다. 실패4 prefix를 성공의 일부나 결측 정답으로 채우지 않고, 유효14/전체18 분모를 분리한다. 회복 창을 같은 세션의 새로운 독립 반복으로 쓰지 않는다. 새 반복 수·임계값은 진단 결과를 보고 사전 등록한다.
- 루트의 후보 수 제한에 합의했다. 서비스 S0/S1, 온도 T0/T1부터 시작하고 온도→서비스·2RC·복잡한 ML은 다음 질문으로 보류한다. 과거 순차3backend의 구조 참고와 현재 CPU1 혼합의 적합·확인을 분리한다.
- 합의는 계획의 범위를 좁힌 것이며 새 모형 정확도·정책 우월성·에너지 적격성 PASS가 아니다. 기존 A24/S26 원본·FAIL·구 모형·기본·strict·`experiment_ready=false`를 유지한다.

| 1차 제안·불확실성 | 2차 반박과 최종 변경 |
|---|---|
| 고정 서비스와 온도→서비스를 비교할 수 있음 | 선택지 팽창과 시간 교락 때문에 이번에는 S0/S1만. S2는 가열/유휴 및 회복 대조가 성립한 뒤 별도 ID로 등록한다. |
| 구 RC의 여러 시간상수·초기 상태를 구조 참고로 활용 | 수치 상속·동시 재적합을 금지하고 T0/T1만. 2RC·ML와 자유 ambient/H는 잔차·실무 식별 진단 뒤 보류 범위다. |
| 전력 적격성이 열 B 입력도 제한함 | 예측전력→열과 점유 state→온도를 구분한다. 전력 gate 실패가 점유 기반 T1까지 자동 차단하지는 않는다. |
| 유효14세션의 공통38.1°C peak | 대표 raw를 대조했고 실패에서는 더 높은 값도 있다. 전체 clipping을 단정하지 않으며 실패 prefix·유효 선별 편향·센서 집계범위를 별도 감사한다. |
| 별도 경험 모형을 시작함 | 기존 시뮬레이터·추출·판독을 재사용하고 새 mixed profile/adapter만 설계한다. 과거 모형/오차 확인/테스트는 버전별 근거로 보존한다. |
