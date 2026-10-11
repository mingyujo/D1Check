# S26 시뮬레이션 계획 — 에너지 검토와 2차 합의

2026-10-11. 에너지 계측·식별 역할의 계획 검토다. 현재 실행은 GitHub 고정 HEAD 읽기·대표 원자료 스키마/시각 점검·공식 자료 확인뿐이다. **모형 적합0, 시뮬레이션 배치0, 실기기0**이며 아래 적합·검증·추가 측정은 제안이다. A24·기존 S26 판정·별도 데스크톱/RL/WIP·기본·strict·`experiment_ready=false`를 변경하지 않는다.

작업 방향은 **기존 GitHub d1sim의 시뮬레이션 구조를 참고하고, 최신 혼합 요청 CPU1/exact 모델의 S26 프로필을 독립 보정·검증하는 것**이다. 기존 엔진이 없다는 뜻이 아니다. 옛 MobileNet/CPU4·다른 런타임의 정적 J표는 legacy 비교로만 보존하며 현재 E0의 계수로 상속하지 않는다.

## 근거와 직접 확인 범위

| 대상 | 고정 HEAD | 이번 역할의 확인 |
|---|---|---|
| s26-measure | `0a0749890fba2452c5907433c6bea476a2da7e24` | energy_1008 최신 결과/작업결과 문서 |
| s26-mixreq | `21cba44faa5fff1fb9703b590aa536a6207f8de5` | 대표 R4C0 manifest·progress.jsonl·HAL header/초반 행 |
| s26-quality20 | `5857152ad8244c41975843ded77dd33024f38f2d` | 공통 검토에서 지정한 품질 gate 근거; 본 역할의 독립 원자료 감사는 아직 없음 |

[에너지 결과 원문](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/s26/results/energy_1008/에너지_결과_1008.md)·[작업결과](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/s26/results/energy_1008/작업결과_1008_에너지C.md)·[대표 R4C 원시료](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1/device/progress.jsonl)·[manifest](https://github.com/mingyujo/D1Check/blob/21cba44faa5fff1fb9703b590aa536a6207f8de5/s26/results/mixreq_1008/R4C_blocks/S26_MIXREQ_00_B2_PARALLEL_ONLINE_V1_a1/device/manifest.json).

직접 읽은 대표 R4C0의 사실은 다음과 같다. 전체 세션에 동일하다고 아직 일반화하지 않는다.

- progress 2,988행 중 `power_sample`239행, `admission`204행이다. 두 종류 모두 센서 필드를 가져 총443행이지만, 정기 적분 대상은 **kind=power_sample 239행만**이다. admission을 함께 적분하면 계측 빈도가 부하에 종속된다.
- `current_valid`는239개 모두 true, current는 방전 음수이며 인접 동일값은3쌍이다. 동일값이라는 이유로 표본을 삭제하지 않는다.
- `charge_counter_raw`의 서로 다른 값은6개, 인접 변화는0/−4,275/−17,100μAh다. 4눈금 몰림이 관측된다. 짧은 창의 작은 정책 차를 정밀하게 구분한다고 가정할 수 없다.
- power 시각을 snapshot 시작/센서 읽기 종료의 중앙으로 잡으면 간격 중앙값0.900112초, 최대0.912645초다. snapshot 폭 최대59.248ms다. 이것은 관측된 앱 호출 폭이며 연료게이지 자체 지연/갱신주기를 교정한 값이 아니다.
- 샘플에 `sample_period_ms`와 `power_save_mode`는 없다. 주기900ms는 manifest의 `sample_period_ms`로 확인한다. 절전 false를 채워 넣지 않는다.
- manifest는 S26 전용 구조다. `phases.baseline_s=30`, `common_s=120`, `cooling_s=60`, `runtimes`의 CPU thread1, 분류 EffNet SHA `6c7ab0a6…`, 탐지 EffDet SHA `40338edf…`다. 첫 도착35초, 마지막 도착73.2초이며 **이 세션 하나에192요청**이 있다. R3/R4C의16세션과192요청/세션을 혼동하지 않는다.
- HAL header는 `pc_ms/device_boottime_s/SKIN/AP/BAT/PA/thermal_status`다. before/after bracket이 없어 device clock 연결 오차를 따로 점검해야 한다. HAL 온도나 PC시각을 전력 시각으로 대신 쓰지 않는다.

원 20261005 export의 대용량 목록과 최신 Git의 혼합 요청 원자료는 확보 상태가 다르다. 최신 원자료가 없다는 이유로 신규 실측부터 시작할 필요는 없다. 다만 대표 한 건의 점검을 R3/R4C/R4S 전량 감사 PASS로 승격하지 않는다.

## 기존 에너지 판정의 경계

energy_1008 C1/C2에서 `R_sum=Q_int/ΔQ_cc`는0.957/0.959로 내부 일관성 **FAIL**이었다. 팔 사이 평균 `d_R=−0.022`, 한계0.034 검사는 통과했고, 등록 규칙상6쌍의 잔량계 차이가 ±2눈금≈±126J 범위 안이라 조건부 적격이었다. 이는 **900초·같은 일·등록 범위의 동등성**이며 절대 에너지 교정이 아니다.

같은6쌍에서 평균 A−B 차이는 E_cc +22.8J, E_int 약−26J로 방향이 반대였다. 원 결과의 동등 범위 판정은 유지하되, 이 사실을 에너지 절감 또는 두 계기 일치로 바꾸지 않는다. 900초의 ±126J/약5.9%를 새120초·720초 창의 오차 한계로 전용하지 않는다. 창 경계에서4눈금 몰림도 있으므로 ±1/2눈금을 일반적인 하드웨어 정확도 한계로 단정하지 않는다.

E_int와 E_cc는 같은 폰의 내부 센서/연료게이지 경로다. 둘의 일치는 외부 독립 표준에 대한 절대 교정을 뜻하지 않는다. 불일치를 없애려고 전류 단위 또는 gain을 사후 조절하지 않는다.

작은 기존 교차검증 소스 [energy_judge_v1.py](https://github.com/mingyujo/D1Check/blob/0a0749890fba2452c5907433c6bea476a2da7e24/s26/tools/energy_1008/energy_judge_v1.py)를 읽어 `_trap_energy`·`energy_run`·`session_check`의 μA/mV/μAh 단위식과 ratio/CC 몰림 기록을 확인했다. 이 부분을 재사용 대상으로 삼고 raw 전체 재다운로드·대형 clone는 계획의 선행 조건으로 만들지 않는다.

**원 판정 재현과 새 혼합 프로필의 적분 계약은 분리한다.** 원 judge는 창 안 첫/마지막 유효 표본까지를 적분하며 경계 보간이 없고, legacy QC에는10초 갭/4,275μAh 눈금/시작 전후 전류比 등 등록 기준이 있다. 이를 새900ms 앱 JSONL의 full120/full720 coverage·snapshot 중앙시각 계약으로 조용히 바꾸지 않는다. 새 분석은 그 차이를 명시한 별도 adapter로 원 `power_sample`만 선택한다. 기존 QC의 잔량 증가 제외·CC 몰림 기록도 보존한다. 내부 ratio는 E_int와 CC가 실제로 공유하는 첫/끝 표본 구간에서 비교하고, 별도의 정확한0..T 적분과 구분한다.

## 1차 주장 → 상호 반박 → 2차 결정

1차는 S26 전용 상태별 고정 증분전력 E0와, 사전 후반전력으로 baseline을 이동하는 작은 시간변동 E1을 최대2개 후보로 제안했다. 미래 power/AP/CC는 예측 입력이 될 수 없다고 했다.

| 반박/보완 | 2차 결정 |
|---|---|
| 루트: A24의 prelate·τ30항은 새 확인4에서 에너지 오차를 키웠다. S26에서 재사용할 근거가 없다. | **채택. E1 즉시 등록을 기각한다. 현재 우선 후보는 E0 하나다.** A24 τ30을 상속하지 않는다. |
| 루트: S26 baseline은 nested manifest·phase/anchor로 재구성해야 한다. | **채택.** A24의 −20..30초 표본창을 복사하지 않는다. S26 실제 baseline 시작/종료와 최초 요청 전에 읽기가 끝난 관측으로 창을 정한다. |
| 열/서비스: 정적 상태전력도 rank만으로 병행·backend별 실제 전력이 식별된 것은 아니다. | **채택.** 상태별 노출·반복·condition·고정 비율의 공선성·지원 조합을 먼저 검사한다. joint 전력을 CPU/GPU/NPU 단독 합으로 만들지 않는다. |
| 열/검증: 유효 R4S14만 남기면 고온/배출 실패 prefix를 제거하는 선택 편향이 생긴다. | **채택.** 실제18시도·유효14·실패4와 모든 prefix를 별도 상태로 유지한다. 관측이 없는 뒤쪽 J를0으로 채우지 않는다. |
| 검증: pair/day/session을 통째로 제외해야 하며 이미 본 R4C는 새 blind가 아니다. | **채택.** 요청 행 random split 금지, 고정모형의 사후 전이와 새 독립 확인을 분리한다. |
| 열: 전력 계수가 미식별이면 이를 입력으로 하는 온도 B 예측도 근거가 약하다. | **조건부 채택.** 예측전력→온도 경로는 보류한다. 전력을 쓰지 않는 점유 state→AP/SKIN 경험모형은 별도 검증할 수 있으며 전력 gate와 자동으로 묶지 않는다. |

## 먼저 확인할 gate와 유한 모형

G0 — **계약/품질/원장**: device·fingerprint·exact model/input/labels·backend·CPU thread·런타임/정밀도·APK·품질 기준을 잠근다. 예전 d1sim의 MobileNet/CPU4 전력표를 새 EffNet/EffDet/CPU1 값으로 쓰지 않는다. NPU의 엔진/정밀도/실제 실행 장치·출력 품질 gate가 남으면 해당 NPU 후보는 미지원이다. A24 mA 가정과 S26 μA 계약을 한 회귀에 합치지 않는다.

G1 — **센서/시간/coverage**: JSONL 순서·중복·소유권·current/charge valid·방전 부호·전압·충전·battery scale·온도/메모리 gate를 전량 검사한다. snapshot 중앙시각과 nominal 주기, 실제 갭·중복 값·계측 공백·CC 갱신 몰림을 공개한다. 적분은 선형 보간의 경계 절단만, 외삽/forward fill/긴 공백 연결/미측정0 대체는 금지한다. 완전 coverage가 없는 창은 full-J 부적격으로 남긴다. 허용 갭·센서 불확실성의 기준은 결과 판독 전에 S26 계약으로 등록해야 한다.

S26 계약의 기술 적분은 `E_int=−∫I_raw(μA)·V_mV·10⁻⁹ dt`다. 내부 CC 점검은 raw counter 변화·같은 창의 전압·경계 갱신 시각을 보존하며, 상승/재추정/이상값을 양의 감소만으로 잘라 숨기지 않는다. `Q_int`, `ΔQ_cc`, ratio, 관측된 CC 눈금/몰림, 두 끝 경계를 인접 갱신 시점으로 바꾼 민감도를 함께 보고한다. 이 민감도는 통계 신뢰구간이 아니다.

G2 — **모형 입력의 관측 가능성**: baseline 전력은 실제 사전 유휴 창에서만 계산한다. 미래 idle 평균을 세션 nuisance로 넣거나 임의 고정 mean으로 바꾸지 않는다. 배경 OS/화면/통신/계측 부하·SoC·이전 열 상태가 pre와 후속에서 달라질 수 있음을 residual로 남긴다. 기록되지 않은 절전/실내온도를 정상값으로 가정하지 않는다.

G3 — **상태전력 식별**: 관측된 순서·worker/lane 소유권 경계에 따라 단독/병행 상태 노출을 만든다. 900ms 전력보다 짧은 요청을 개별 current 표본과 일대일 귀속하지 않는다. 고정 수초 bin의 노출행렬에서 rank/정규화 condition·상태별 총노출·세션 반복·source별 변동을 검사한다. 부족한 column은 사후 숫자로 채우지 않고 unsupported/식별 보류로 둔다. full rank도 CPU/GPU/NPU rail 전력의 인과적 식별이 아니다.

**E0 우선**: `E_hat(0,T)=P_pre·T+Σp_s·occupied_seconds_s(0,T)`. 상태별 증분은 S26 exact 계약의 지정 개발자료만으로 추정하고 같은 모형을 모든 평가 세션에 적용한다. 세션 배경 오프셋은 미래자료로 학습해 예측에 추가하지 않는다. 음의 baseline 차감 표적도 보존한다. 새 적합 전 bin·개발/평가 분할·정규화·정규화 강도 유한목록·fit/time 상한을 별도 등록한다. 이번 계획에서 실제 fitting은 하지 않는다.

**E1 보류 조건**: S26 개발자료에서 사전 power 특징이 이후 실제 idle residual을 pair/day/session 제외로 예측하는 관계가 먼저 보여야 한다. raw ratio 보정이나 같은 세션 future mean으로 만든 관계는 인정하지 않는다. 관계가 없으면 **E0로 종료**한다. 관계가 있고 시간상수/형태를 S26 자료 또는 장치 측 정보로 정당화할 때만 별도 범위로 시간변동1항을 등록한다. 최대2 family·유한 강도·새 독립 확인이며 τ/gain/grid를 실패 후 무제한 확대하지 않는다.

## 정량 평가와 가능한 주장

- A: **실제 일정 조건부** E0 센서표적 오차. B: **예정 도착→예측 일정** 비용 오차. 두 경우 동일한 사전 baseline·동일 센서 적분 정답을 쓰고 일정 오차와 비용 오차를 구분한다.
- R3/R4C0..120초와 R4S0..720초의 J 절대오차/부호오차/상대오차는 별도 표다. 평균 power오차 `absJ/T`는 창 비교의 보조 지표이며 J평균을 소급 하나로 합치지 않는다. baseline/load/drain/cooling 창도 실제 anchors로 별도 표시한다.
- 세션평균→pair/day/source 평균, median·P95/worst session·오차 방향·노출 support를 공개한다. 표본 수/관측 창/valid·failed를 함께 쓰며 긴 trace 또는 많은 요청이 평균을 독점하지 않게 한다.
- 정책 비교에는 같은 등록 전체 도착 수·deadline·성공/실패/거절/만료/미완료를 사용한다. 완료 P95와 전체 도착 성공률을 함께 보고한다. J/완료추론은 실패가 많은 정책을 유리하게 만들 수 있어 단독 주지표로 쓰지 않는다.
- R4S 실패 prefix는 관측된 구간 누적J·coverage·실제 시작/완료 요청을 보고한다. 종료 뒤720초까지 미관측이면 full720-J는 unavailable이다. 유효14/18·실패4/18 비율과 planned 전체 도착 원장은 따로 유지하고 유효14만의 평균을 전체18의 성능으로 부르지 않는다.
- 절대 J의 sensor-target MAE 감소와 정책차 `ΔE` 정확도는 다르다. pair별 predicted−observed ΔE 오차·E_int/E_cc 각각의 부호·내부 불일치·순서/시각/시작 상태 차이를 공개한다. 작은 차이가 내부 불확실성/눈금보다 작거나 부호가 반대면 절감 방향은 보류한다.

외부 전력계 없이 가능한 범위는 **같은 기기·같은 센서 계약·정해진 shape에서 내부 trace 적분과의 예측 오차**, 관측범위 내 sensitivity, 기존 조건부 등록 판정의 재현이다. 이를 절대 교정·임의 사용자 부하 일반화·전력 rail 귀속·정책 에너지 우월로 부르지 않는다. 상대비교의 미교정 공통 bias가 상쇄된다고 단정하지 않는다.

작은 절감률의 방향, E_int/E_cc 방향 역전의 해소, 절대 J 또는 임의 조건의 실제 에너지 정확도를 주장하려면 별도 독립 참조가 필요하다. 적절한 외부 계측은 전원 경로·배터리 충방전·변환손실·clock sync·계측 영향까지 통제해야 하며, 충전 중 USB입력 전력을 곧바로 배터리 방전 에너지로 대체하지 않는다. 내부 센서 두 개만으로 그 역할을 대체하지 않는다.

## 추가 자료/실측의 발동 조건 — 제안만

1. **원자료 gap/단위/clock/품질 미해결**: 우선 해당 raw·runtime/센서 설정·실패 원장·HAL 연결 근거를 회수한다. 대형 clone나 실측 반복보다 이 gate가 먼저다.
2. **특정 state 미식별**: 같은 exact runtime/품질 contract에서 필요한 단독/joint 노출만 최소 보충한다. 불필요한3backend 동시실행·전체 policy 반복으로 대체하지 않는다. 예비 최솟값은 미식별 state의 부하/유휴 짝을 서로 다른 세션2회씩 확보하는 안이며, 실제 횟수/작업량/기기 상한은 미식별 정도를 확인한 뒤 등록한다.
3. **동결 E0의 독립성 부족**: 새 날짜에 동일 fixed shape의 기준/대안 ABBA4세션을 최소 독립 확인안으로 둔다. 실행 전 모형·APK·입력·shape·초기상태범위·시간/추론/종료 한도를 등록하고 추가 fitting/대체 반복은 하지 않는다. ABBA만으로 실내·SoC·앞 칸 효과가 모두 상쇄되는 것은 아니다.
4. **정책 ΔE가 센서 불확실성보다 작거나 E_int/E_cc 방향이 불일치**: 외부 동기 계측을 우선 검토한다. 외부 장비 없이 주장 범위를 sensor-target 예측으로 줄이면 새 기기 실측을 자동 발동하지 않는다.
5. **E1의 전이 근거 없음**: 추가 시간변동 fitting을 하지 않고 E0 한계로 종료한다. E1의 조건부 연구를 진행하려면 별도 pre/idle 진단·개발 분할·S26 시간상수 근거부터 등록한다.

## 공식 근거의 적용과 한계

[Android BatteryManager](https://developer.android.com/reference/android/os/BatteryManager)는 CURRENT_NOW의 μA·방전 음수, CHARGE_COUNTER의 μAh 계약을 명시한다. CURRENT_AVERAGE의 평균 기간은 fuel-gauge 설정에 의존한다고 설명하지만 NOW의 특정 평균 기간·S26 실제 교정·CC 눈금 정확도까지 보증하지 않는다.

[Pathak 등의 공식 연구기관 설명](https://www.microsoft.com/en-us/research/video/fine-grained-power-modeling-for-smartphones-using-system-call-tracing/)은 utilization과 무관한 driver power 상태의 존재를 설명한다. 따라서 software lane 해제 직후 전력도 즉시 idle이라는 가정을 점검할 근거이며 S26 tailτ/계수를 그대로 가져올 근거는 아니다.

[Carroll·Heiser, USENIX ATC2010](https://www.usenix.org/conference/usenix-atc-10/analysis-power-consumption-smartphone)은 구성요소·전체기기 계측을 구분한 원 연구다. S26 내부 battery 센서가 그 외부/구성요소 계측과 동등한 정확도라는 근거로 쓰지 않는다.

검토 당시 로컬 HEAD `8175aac95c82fa70860e07e2e7566797b92b7736`＋기존 WIP, 근거 GitHub HEAD는 위 표와 같다. 현재 작성 대상은 본 Markdown 하나이며 원자료·러너·계수·상태/계획·데스크톱/RL 파일을 수정하지 않았다.
