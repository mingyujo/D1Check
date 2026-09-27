# 첫 offline 선택의 온라인 정보 의존성 — PC 진단

## 결론

queue·burst의 발견 일정은 모두 시각 0에서 첫 일반 탐지를 CPU에 배정했고, 기존 `THERMAL_ENERGY_PC_V1`은 GPU를 골랐다. 이때 관측 가능한 큐·두 lane·모형 AP·동결 시간 추정과 가정 전력/AP는 동일하지만 후속 도착과 실현시간은 알 수 없다. **CPU 첫 배정의 에너지·응답·AP 손익이 같은 관측 과거의 미래 분기에 따라 달라졌다.** 이번 사전 판정 기준에서 모든 분기에 비악화인 단일 첫 선택 규칙을 얻지 못해 새 온라인 정책은 구현하지 않았다. 이는 온라인 개선 전체의 불가능성 증명이 아니다.

## 고정한 입력과 정보 경계

결과를 보기 전에 [`CONFIG.json`](results/arrival_information_check_01/CONFIG.json)에 사례·분기·수치 허용오차·최대 24재생/60초·규칙 구현 조건을 기록했다. 기존 offline 전체 탐색은 다시 돌리지 않았다. queue/`energy_shift`, burst/`thermal_cap`의 seed 301·첫 3요청과 동결 CAL-03 시간 자료를 재사용했다. 각각의 첫 시점은 다음과 같다. CPU/GPU lane은 모두 `AVAILABLE`이므로 점유 잔여시간 추정은 해당 없음(0으로 대입한 busy 잔여시간이 아님)이다.

| 사례 | 시각·그때 도착한 요청 | 우선순위·남은 기한 | 현재 모형 AP | CPU/GPU 응답 중앙값 | CPU/GPU lane 중앙값 | CPU/GPU 가정 단독 전력·평형 AP | 기존 / offline 첫 행동 |
|---|---|---|---:|---:|---:|---|---|
| queue | 0ms, 탐지 #0만 도착 | 일반, 6000ms | 29.0°C | 624.052/1132.109ms | 627.418/1135.267ms | 3.0/1.5W, 34/34°C | GPU / CPU |
| burst | 0ms, 탐지 #0만 도착 | 일반, 6000ms | 30.0°C | 624.052/1132.109ms | 627.418/1135.267ms | 1.5/3.0W, 34/29°C | GPU / CPU |

응답·lane 값은 동결 자료의 조건부 중앙값이지 실현값이나 보장 상한이 아니다. W와 AP 평형값 및 연구용 AP 한도(queue 100°C, burst 30.03°C)는 **미측정 탐색 가정**이다. 정책 판단·기록·dispatch 비용은 기존 0.5/0.1/0.1ms 가정으로 양쪽에 동일하게 적용했다. 실제 keyed 단계 시간은 [`posthoc_first_realization.csv`](results/arrival_information_check_01/run_v2/posthoc_first_realization.csv)에 사후 정보로만 두었다. 첫 선택 callback에는 후속 요청 목록과 실현 벡터를 전달하지 않았다. 완전 offline 일정은 이 정보를 검색에 사용하므로 온라인과 정보 조건이 다르다.

미래 분기는 추가 도착 없음, 기존 시각의 긴급 1건, 같은 시각의 일반 1건, 원래 3건, 원래 3건에 탐지 CPU 또는 GPU의 실현 단계시간만 1.25배 한 오차 stress로 고정했다. 1.25는 확률분포나 측정된 오차 범위가 아니다. 같은 사례의 모든 분기는 시각 0의 `first_snapshots.json`이 정확히 일치한다. 분기 확률은 없어 평균 정책 가치를 계산하지 않았다.

## 첫 행동만 바꾼 결과

아래 차이는 **CPU 첫 배정 − GPU 첫 배정**, 이후 행동은 양쪽 모두 변경하지 않은 V1이다. 공통 120초의 기기 전체 에너지, 모형 AP 최고·연구용 한도 초과시간과 예정 요청 전체 응답을 비교했다. 모든 분기에서 완료/계획은 각 1/1, 2/2 또는 3/3, 실패·미완료·긴급/일반 기한 위반 증가는 0이었다. 개별 응답 악화가 없다는 뜻은 아니다.

| 사례·후속 분기 | Δ에너지 J | ΔAP 최고 °C | ΔAP 초과 s | 최악 요청 응답 손실 ms |
|---|---:|---:|---:|---:|
| queue·추가 없음 | +0.655 | −0.043 | 0 | 0 (첫 요청은 516ms 빠름) |
| queue·긴급 도착 | +0.416 | −0.025 | 0 | +224 |
| queue·일반 도착 | +0.029 | −0.007 | 0 | +409 |
| queue·원래 3건 | −0.057 | +0.00047 | 0 | +539 |
| burst·추가 없음 | −1.943 | +0.042 | +0.874 | 0 (첫 요청은 497ms 빠름) |
| burst·긴급 도착 | −1.223 | +0.064 | +4.086 | +205 |
| burst·일반 도착 | −0.070 | −0.016 | −0.887 | +481 |
| burst·원래 3건 | +0.259 | −0.066 | −3.693 | +536 |

나머지 CPU/GPU 시간오차 1.25배 분기는 [전체 CSV](results/arrival_information_check_01/run_v2/branch_deltas.csv)에 있다. 최대 관측 응답 손실은 queue 825ms, burst 814ms이며, 이는 합성 분기 최악값일 뿐 tail 추정이 아니다. 원래 3건에서 첫 행동만 CPU로 바꾸면 queue 121.865→121.808J, burst 123.461→123.720J이다. 기존 **완전 offline 일정**은 후속 행동까지 바꿔 queue −0.127J, burst −2.004J였다. 특히 burst의 offline 개선을 시각 0의 CPU 선택만으로 설명할 수 없다. 이후 도착에 따른 lane 점유·기다림·배정이 중요하다. 이전 offline 500ms 허용폭은 작은 진단 전용으로, 본 결과나 24요청의 서비스 기준으로 전용하지 않았다.

## 구현·검증·판정

[`tools/d1_arrival_information_check.py`](../tools/d1_arrival_information_check.py)는 기존 엔진과 동결 설정을 사용한다. 첫 결정에만 합법적인 즉시 CPU/GPU를 주입하고, 이후 `feedback.choose`를 그대로 호출한다. CPU/GPU 양쪽의 예정 분모·완료·기한 위반·요청별 응답·120초 에너지·AP를 보존한다. 강제 GPU의 원래 3건 ledger·열 회계는 수정하지 않은 V1 결과와 일치했다. 같은 사례의 모든 미래 분기에서 첫 관측 snapshot도 일치했다. 응답 완료, persist, worker release, 실제 lane_available 순서와 재생 열/에너지 적분을 관련 테스트로 확인했다.

사전 규칙 gate는 CPU 첫 행동이 모든 개발 분기에서 모든 요청의 응답, 기한 위반, 미완료, 에너지, AP 최고·초과시간을 수치 오차 이내로 비악화하고 한 분기 이상 에너지/AP를 줄이는 경우였다. 통과하지 못했다. 수치 허용오차는 의미 있는 절감량이 아니다. 따라서 새 규칙과 조건부 확인 seed/24요청 실행은 **미실시**이고 기존 P·V1·동결값은 그대로다. 명시적 확률·예측 신호 또는 서비스 상충 허용 근거가 없으면 두 미래를 동일 snapshot에서 식별할 수 없다.

이 진단은 2개 작은 사례, 예전에 본 seed 301, 미측정 W/AP stress 및 keyed 개발/평가 자료의 회고적 사용으로 한정된다. 실기기 독립 검증, 물리적 에너지 정확성, BAT 온도, 열 throttling, 모든 온라인 규칙의 불가능성을 주장하지 않는다. 다음 행동은 **새 규칙 개발을 보류하고 이 정보 한계와 완전 offline 참고값을 현재 연구 결과의 경계로 명시하는 것**이다. `experiment_ready=false`를 유지한다.

## 재현

```powershell
python -X utf8 -m tools.d1_arrival_information_check --output <새 빈 출력 경로>
python -X utf8 -m unittest tools.test_d1_arrival_information_check -v
python -X utf8 -m tools.d1_arrival_policy_screen --attach-information
```

기존 24요청·offline 전체 배치와 기기 실행은 수행하지 않는다. [CSV·SVG·설정·해시·대시보드 안내](results/arrival_information_check_01/README.md)를 함께 본다.
