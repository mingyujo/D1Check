# ENERGY-THERMAL-PC-01 — 기존 자료의 조건부 에너지·열 보정과 PC 연결

## 결론과 채택 범위

발열·배터리 최적화는 사용자 지정 **필수 목표**다. 동일 작업량·출력 품질 및 대화형 응답·일반 완료 조건을 지키면서 에너지와 발열 부담을 함께 평가한다. 온도 로그/중단 gate로 축소하지 않는다. 시간 중심 P의 불리한 결과만으로 전체 목표의 성공·실패를 판정하지 않는다.

이번 완료는 기존 MobileNet 자료 추출·사후 보정·PC 기능이다. 현재 EfficientNet-Lite0/EfficientDet-Lite0의 절감 검증은 아니다. 일시정지 Android 연결·P 튜닝은 보류하며 S26/NPU 별도 협업은 유지한다. 원래 FAIL·부분 결과·40동결값·20null·종료 계획과 `experiment_ready=false`는 불변이다.

시작 HEAD `38d5959d5c364e35cec8cf0f49a2e45933d24a48`, 작업 브랜치 `feature/arrival-scheduling-20260923`, clean. ADB/설치/실측/정책 비교 배치는 없다.

## 입력·추출·시간 계약

- A24: 로컬 `Documents/D1Check_A24_formal_strict_20260911_114101`, completed formal80만 포함. CPU1/2/4·GPU, duty25/50/75/100, 각5세션. MobileNet tensor-only, 별도 출력 동등성 사전 확인과 timed 요청 품질 측정을 구분한다.
- S26: 로컬 `Documents/카카오톡 받은 파일/S26_formal_audit_20260915.zip`의 canonical `02_runs`, `12_exports-v2`, `01_experiment_manifest`만 읽는다. 중복 reference export·실패 raw run은 완료80에 합치지 않는다. 기존 실패 이력은 삭제하지 않는다.
- 원본 불변, 외부 `Documents/D1Check_Arrival_Extension/energy_thermal_pc_v2`에 CSV/설정/그림/receipt를 생성했다. 사용한 입력을 읽는 동안 경로·bytes·SHA를 provenance에 기록하며 원본 전체 재감사를 실행하지 않았다.
- `TelemetryForegroundService.sample()`은 CURRENT_NOW/CHARGE_COUNTER 원시 정수, voltage mV, temperature÷10°C, plugged를 저장한다. `current_valid`는 MIN sentinel 검사이며 정확도 판정이 아니다. 평균전류·energy counter API는 수집하지 않았다. Samsung 덤프의 희소 `current_avg` 이력은 별도 vendor 자료로 정규 시계열에 혼합하지 않는다.
- 에너지 시각은 앱 elapsedRealtimeNanos. HAL 시각은 host logger가 `/proc/uptime` 앞뒤를 bracket한 midpoint이고 uncertainty를 보존한다. 세션 내 boot 혼합을 차단한다. host wall clock과 직접 차분하지 않는다. thermal export의 기존 phase assignment 범위와 제외 표본은 기존 의미 그대로다.
- 동일 시각의 동일 표본은 한 번만 적분하고 상충 중복은 오류다. 표본 사이 전력 P=−I·V를 선형 보간한 사다리꼴을 단계 경계에서 잘라 적분한다. 긴 gap>2.5초·충전/미지원·끝점 밖은 누락시간으로 남기며 0 또는 forward-fill로 메우지 않는다. gap 한계는 약1초 수집의 구조적 분석 설정이지 정확도 허용폭이 아니다.
- baseline/setup/warmup/ready/load/shutdown/cooling을 lifecycle로 분리한다. 1Hz보다 짧은 setup·warmup의 배분은 **보간 회계값**이지 직접 식별한 개별 호출 에너지가 아니다. 계수에는 충분한 길이의 load/cooling만 사용한다.
- old baseline은 runtime 생성 전, cooling은 종료 후다. 새4-runtime resident idle로 전용할 수 없다. 화면·통신·host 관측 부담을 포함한 기기 전체 배터리 전력이며 CPU/GPU rail 전력이 아니다. 주변온도 미측정/위치 변화 한계도 보존한다.

## 단위와 에너지 결과

단위 후보는 raw당1 또는1000μA만 비교한다. 전하량을 정답으로 놓고 임의 계수를 맞추지 않는다. 전체 세션, 비중첩60/120초 창에서 전류 적분과 counter 감소를 대조하며 counter가 정체한 창도 원자료/분모에 남긴다. 양자화·갱신 지연과 충전 구간은 따로 표시한다.

| 기기 | 전류 샘플 | 유력한 해석 | 전체 세션 비율 중앙값 / 범위 | 전체 적분합 / counter 감소합 |
|---|---:|---|---|---:|
| A24 | 19,023 | raw mA, ×1000→μA | 1.0375 / 0.6738~1.7808 | 1.0214 |
| S26 | 37,864 | raw μA | 0.9356 / 0.6995~1.1748 | 0.9280 |

이는 **가장 유력한 단위 해석**이고 절대 에너지 정확도 인증이 아니다. 서로 같은 fuel gauge에서 나온 counter/전류 일치도 외부 전력계의 독립 검증이 아니다. A24 약4000μAh, S26 약4275μAh counter 양자화와 경계 지연 때문에 짧은 창 비율은 크게 튄다. S26의 약7% 차이를 보정계수로 흡수하지 않았다. API 명목 단위와 device 실제 반환을 구분한다: [BatteryManager](https://developer.android.com/reference/android/os/BatteryManager).

선택 가설 아래 60초 load 전체 에너지는 A24 50.55~127.47J, S26 110.32~515.76J다. **두 기기 효율 비교가 아니며 조건·완료량이 서로 다르다.** 모든 load80/기기에서 적분 구간은 충족했다. `phase_energy.csv`는 전체/covered 에너지, 누락시간, 평균전력, 실제 완료 추론당 에너지, 같은 세션 pre-runtime baseline 대비 추가 소비를 분리한다. 음의 추가 소비를0으로 자르지 않는다. 냉각 끝에서 마지막1Hz 표본 이후는 미측정으로 남는다.

## 열모형·사후 내부 확인

기기×condition×sensor×load/cooling별 최소 모형:

`T(t) = B + g + (T(0) − B − g) exp(−t/τ)`

B는 해당 세션 baseline의 관측 중앙값이며 **실제 주변온도가 아니다**. g와τ를 전력계수와 동시에 맞추지 않는다. 상태 기반 경험적 가열/냉각 모형이며 에너지 단위의 불확실성이 수치적으로 열에 전달되는 구조가 아니다. 두 모형의 현실 전이 불확실성은 각각 유지한다.

결과 열람 전에 저장한 METHOD는 block1~3 적합,4~5 사후 내부 확인이다. 세션당 같은 가중치를 사용하며 샘플 랜덤 분할은 없다. 이미 열람한 과거 자료이므로 독립 검증이 아니다. 확인 오차는 각 단계 첫 관측 T에 조건부인 예측이며 전체 세션 free-running 정확도가 아니다.

τ grid1~1200초; 최소손실의1.05배 이내 profile 폭, grid 경계, 관측 신호≥0.3°C(3단계 해상도)를 **식별성 진단**에 사용했다. CI·성능 PASS 기준이 아니다. 평평한 신호/넓은 profile/경계 해는 미식별로 남긴다. 경험적 온도 곡선은 계수 식별 여부와 무관하게 보존한다.

| 기기/센서 | load 확인 세션 MAE 중앙값 | load 최대 표본 절대오차 | load+cooling 식별성 진단 충족 |
|---|---:|---:|---:|
| A24 AP | 0.194°C | 1.441°C | 29/32 |
| A24 BAT | 0.014°C | 0.117°C | 0/32 |
| A24 PA | 0.123°C | 0.833°C | 19/32 |
| A24 SKIN | 0.055°C | 0.313°C | 2/32 |
| S26 AP | 1.888°C | 7.302°C | 29/32 |
| S26 BAT | 0.190°C | 0.953°C | 25/32 |
| S26 PA | 0.960°C | 4.610°C | 32/32 |
| S26 SKIN | 0.222°C | 1.019°C | 32/32 |

기기별 총128개 모형 중 A24 50, S26 118개가 식별성 점검을 충족했다. 작은 오차의 A24 BAT는 거의 평평해 계수를 식별하지 못한다. **식별성과 예측 정확도는 별개**이며 위 숫자는 정확도 PASS가 아니다. 잔차 lag1 상관이 높고, S26 AP 오차도 커서 단순1차 모형의 한계를 그대로 남긴다. τ>0 지수의 수치적 장시간 안정성을 확인하지만 fitted equilibrium의 물리적 장시간 예측은 금지한다.

`session_energy_temperature_latency.csv`/`association_summary.csv`는 조건 내5세션의 지연·AP·전력 연관성이다. 위치/초기온도/잔열/관측부담을 제거한 인과효과가 아니며 고온 스로틀링 곡선을 생성하지 않는다. thermal status0을 모든 DVFS 부재로 해석하지 않는다. 센서는 HAL 의미를 유지하며 실제 표면/die 정밀온도로 승격하지 않는다: [AOSP thermal](https://source.android.com/docs/core/power/thermal-mitigation).

## PC 연결과 지원 차단

`d1_energy_thermal.py`는 기존 엔진을 수정하지 않는 ledger 후처리 계층이다. 실제 lane_available까지 prepare/execute/store/worker_release/callback 점유를 보존하며 idle을 lane별 중복 합산하지 않는다. waiting 요청 수와 기기 idle 상태를 구분한다. 공통 구간에 에너지·peak·선언된 기준 온도 위의 degree-seconds를 누적하며 기준 온도를 안전 임계값으로 부르지 않는다.

1. `observed_replay`: legacy의 고정 recorded schedule을 사용한 상태모형 재생. 원시 적분과 모형 회계값을 구분한다.
2. `conditional_prediction`: fingerprint/model hash/condition/sensor와 상태 순서·누적 지속시간·온도 지원 범위를 검사한다. 미식별 계수, 반복 cycle 외삽, arbitrary 병행은 차단한다. 초기값/단위의 조건부 추정이지 정확도 인증이 아니다.
3. `assumption_exploration`: 현재 두 모델은 명시적 상태별 W·열계수를 전부 제공해야 한다. 결과에 synthetic/assumption을 남긴다. 병행 W를 단독합으로 자동 생성하지 않는다.

실행·미완료 전체 분모를 남기며 모든 작업 완료와 외부 서비스 제약 충족이 명시되지 않으면 equal-work 비교 적격이 아니다. 어떤 모드도 `optimization_pass`나 `experiment_ready`를 true로 하지 않는다. 에너지 모듈의 사후 실행 상태를 정책의 미래 입력으로 전달하지 않는다.

## 구현·재현·검증·실행 이력

- [분석 도구](../tools/d1_energy_thermal_analysis.py), [PC 회계 모듈](../tools/d1_energy_thermal.py), [요약/작은 재생](../tools/d1_energy_thermal_report.py), [관련 테스트](../tools/test_d1_energy_thermal.py).
- [공유 요약·그림·검증 기록](results/energy_thermal_pc_01/README.md). 상세CSV/모형/입력식별/곡선은 외부 출력에 있다. 모델/키/원본 대용량 자료는 Git에 없다.
- v1 추출은 run_id 중복 키 구성 오류로 중단해 METHOD와 failure 기록을 보존했다. 수정 후 v2 추출/적합 완료. 후처리에서 냉각 끝점 미측정 때문에 coefficient가 누락된 것을 확인했다. 전체 에너지로 메우지 않고 관측 coverage≥95%인 부분의 평균전력을 쓰는 **개발용 계수**로 분리했다. 이 후처리 규칙 추가는 정확도 기준 완화가 아니며 누락시간/전체 에너지 null은 유지한다. `profiles.json` 초기 파생본과 최종 `profiles_connected_v1.json`을 구분한다.
- Windows 기본 cp949로 UTF-8 provenance를 읽던 후처리 오류를 수정했다. thermal fit/원자료는 재실행·재튜닝하지 않았고 후처리만 갱신했다. verification에 최종 source hash를 별도로 보존한다.
- 관련18개 테스트: 단위/부호/충전/중복/gap/경계 적분/음의 추가소비/센서·기기·condition 혼합 차단/대기·냉각·잔열/미완료/병행 차단/기존 엔진 출력·lane 해제 보존. 추가로 실제 대표2세션의 단계별 적분합 보존, legacy 재생2건, 합성 engine 연결1건을 실행한다. CPU/GPU 실기기 검증이 아니다.

```powershell
python -B -m unittest tools.test_d1_energy_thermal -v
python -B -m tools.d1_energy_thermal_analysis --a24 C:/Users/LG/Documents/D1Check_A24_formal_strict_20260911_114101 --s26 'C:/Users/LG/Documents/카카오톡 받은 파일/S26_formal_audit_20260915.zip' --output C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_thermal_pc_reproduce_NEW
python -B -m tools.d1_energy_thermal_report --analysis C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_thermal_pc_reproduce_NEW
```

출력 root는 새 경로만 허용한다. 후처리는 해당 새 분석 root의 파생 요약을 생성한다. 그림은 알파벳 첫 condition의 block4를 기기별 모든 센서에 동일하게 선택하며 유리한 세션을 선택하지 않는다. PNG/SVG/그래프 원본CSV를 제공한다.

다음은 [현재 두 모델의 최소 추가 수집 계약 후보](ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md)의 PC 준비다. 아직 설치·실측 승인이나 device 실행 manifest를 생성한 것이 아니다.
