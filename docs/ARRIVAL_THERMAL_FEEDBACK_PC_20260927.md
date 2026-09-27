# ARRIVAL-THERMAL-FEEDBACK-PC-01 — 에너지·AP 피드백 후보의 제한된 PC 탐색

**판정.** `THERMAL_ENERGY_PC_V1`을 기존 arrival 이벤트 엔진의 별도 `explore` 정책으로 구현했다. 현재까지 도착한 요청, 두 lane의 관측 상태, 현재 **모형상** AP 온도, CAL-03 개발 시간 추정값, 명시적 전력·열 가정으로 CPU/GPU 즉시 실행 또는 최대 2초 대기를 평가한다. 기한과 연구용 AP 한도를 먼저 검사하고, 적격 후보 중 공통 예측 지평의 기기 전체 에너지를 최소화한다. 이번 192개 PC 실행에서는 일부 가정 아래 에너지 또는 AP 지표가 좋아졌지만 **응답·일반 서비스 손실 없이 에너지까지 개선한 비교는 확인되지 않았다.** 실기기 절감·열 제약 준수·정책 우월성 PASS는 없다.

## 계약과 구현 경계

- `tools/d1_arrival_thermal_feedback.py`: 별도 이름/버전. 도착한 큐만 전달되며 미래 도착·실현 duration은 정책 함수에 없다. 예상 전력/AP와 실현 전력/AP는 다른 입력이다. 같게 둔 profile은 이상적 진단 가정이다. 전력은 상태별 **기기 전체 절대 W**로 한 번만 적분하고, 유휴 전력이나 단독 lane 전력을 병행 상태에 더하지 않는다. AP 평형·시정수는 전력과 독립된 가정이다.
- `tools/d1_arrival_explore.py`: 새 정책을 고른 경우에만 이벤트 간 AP·에너지를 갱신한다. 기존 정책의 배정·응답·저장·worker release·실제 lane 해제 이벤트는 바꾸지 않았다. 모든 정책에 같은 실현 비용 profile을 사후 회계한다. 엄격 모드에서는 미측정 열/전력 profile을 차단한다.
- 후보는 head 요청×현재 빈 backend×{즉시, 250 ms 대기}의 유한 집합이다. 최소 8초에서 최대 30초 사이의 **동일 예측 지평**으로 각 행동을 적분한다. 기한은 원래 요청 도착부터 긴급 1.5초·일반 6초이며 전체 시나리오의 사후 δ를 온라인 정보로 사용하지 않는다. 적격 후보가 없으면 예측 위반을 남기고 즉시 fallback한다. busy lane의 예상 잔여시간이 `UNKNOWN_OVERRUN`이면 0으로 간주하지 않고, 유한 대기 뒤 단독 시간 추정 기반 dispatch와 미정 병행 비용을 기록한다. 실제 lane_available 전에 재사용하거나 선점하지 않는다.
- 대기를 결정하면 명시적 wake 이벤트를 둔다. 새 도착은 wake보다 먼저 처리할 수 있고, busy lane은 실제 완료 이벤트가 재판단을 일으킨다. 대기 상한·aging은 기아/무한 루프를 제한한다. 새 후보 판단 0.5 ms, 기존 비교군 0.1 ms, 공통 기록/dispatch 각 0.1 ms는 **미측정 가정**이며 무료 판단이 아니다. 개발용 5 ms 스트레스는 별도 표기한다.
- 요청이 120초에 미완료면 24건 분모에서 빠지지 않고 위반/미완료로 남는다. 공통창 에너지는 동일 120초 경계이며, 한 후보의 완료시점까지만 적분하는 비교를 하지 않는다. AP 한도 초과 시간은 경로별 1차 전이의 교차 시각으로 계산한다. AP는 BAT/표면 온도나 안전 한도가 아니다. 온도에 따른 실제 추론 감속/스로틀링은 구현하지 않았다.

## 사전에 고정한 작은 비교

`docs/results/arrival_thermal_feedback_01/CONFIG.json`을 새 seed 결과 열람 전에 고정했다. low/queue/burst × 전력·열 가정 4개 × 기존에 열람한 개발 seed 201·202 / 별도 PC 확인 seed 301·302 × CPU_URGENT·개발 고정 B2·B3·새 후보 = 192개 실행이다. 요청 24건(긴급 6, 일반 18), CAL-03 frozen 시간 입력, 실현 간섭 1.5, 공통 120초, 같은 seed별 요청/실현 벡터를 썼다. B2는 기존 개발 freeze의 `GPU_CPU_parallel`이고 평가 결과로 다시 고르지 않았다. `loose_cpu`는 느슨한 AP/CPU 저전력, `thermal_cap`은 임의 연구용 AP 30.03°C, `energy_shift`는 GPU 저전력, `cost_miss`는 GPU 저전력 예상과 높은 실현 전력의 불일치다. **모든 W/AP 수치와 한도는 미측정 스트레스 가정이며 A24 가능 범위가 아니다.** 새 seed 확인은 같은 PC 벡터 원천의 모형 확인이지 독립 실기기 확인이 아니다. 확인 결과로 계수·한도·정책을 재조정하지 않았다.

동결 순서: `run_v1/SOURCE_MANIFEST.json` → 개발 96개 → `development_metrics.csv` → `freeze_before_confirmation.json` → 확인 96개. 원본 입력·B2 freeze·설정·정책 SHA를 보존한다. 실행 뒤 엔진에 추가한 변경은 strict에서 가정 profile을 거부하는 guard뿐이며 explore 결과에는 영향이 없다. `tools/test_d1_arrival_thermal_feedback.py`가 보존된 queue/thermal_cap/seed301 결과의 재생 일치를 검사한다.

## 확인 seed 301·302의 대표 상충

아래 P95·일반 평균·에너지·AP는 **seed별 지표의 단순 평균**이며 실기기 독립 세션 수는 0이다. 위반 건수는 두 seed의 36개 일반 요청 전체 분모로 표시한다. 모든 조건에서 계획 24건/seed가 완료되고 미완료·모형 실패는 0이었다.

| 조건 | 비교 | 긴급 P95 ms | 일반 평균 ms | 일반 위반/36 | 공통120초 J 가정 | AP 최고 °C 가정 | AP 한도 초과 초/seed 평균 |
|---|---|---:|---:|---:|---:|---:|---:|
| queue / energy_shift | B3 | 1045.64 | 4013.95 | 7/36 | 137.36 | 30.30 | 0 |
| queue / energy_shift | 새 후보 | 847.04 | 4334.71 | 10/36 | 136.78 | 30.35 | 0 |
| low / thermal_cap | CPU_URGENT | 159.20 | 623.93 | 0/36 | 126.16 | 30.45 | 47.78 |
| low / thermal_cap | 새 후보 | 284.60 | 941.83 | 0/36 | 146.71 | 30.03 | 0 |
| low / cost_miss | CPU_URGENT | 159.20 | 623.93 | 0/36 | 128.63 | 29.82 | 0 |
| low / cost_miss | 새 후보 | 307.18 | 1132.29 | 0/36 | 175.88 | 32.86 | 0 |

`energy_shift/queue`는 B3 대비 에너지 약 0.58 J와 긴급 P95 약 199 ms가 작지만 일반 응답 약 321 ms와 위반 3건/36이 악화된다. `thermal_cap/low`는 모형상 AP 초과를 없애지만 20.55 J와 응답 지연을 더 사용한다. `cost_miss/low`는 예상 전력 오류만으로 CPU 대비 에너지 약 47.25 J·AP 약 3.03°C 손해를 보인다. 확인 24개 scenario×profile×seed 조건에서 새 후보의 에너지가 CPU/B2/B3보다 낮은 경우는 각각 **6/24·8/24·6/24**다. 각각의 상대 정책보다 긴급·일반 응답과 위반·미완료 모두 손해 없이 에너지도 낮은 경우는 **0/72 짝 비교**다. 이것은 고정 profile·seed의 비교이지 일반적 정책 지배 검정이 아니다. `thermal_cap` queue/burst에서는 fallback 때문에 연구용 한도를 오히려 크게 넘는다. 한도 준수 보장은 없다.

개발 seed201·202에만 미리 설정한 판단 비용 0.5→5 ms 스트레스를 추가 적용했다. low 긴급/일반 응답 +4.5 ms, queue 긴급 +151~370 ms·일반 +269~732 ms, burst에서는 긴급 −7.8~+129.5 ms·일반 +519~538 ms였다. 에너지 차이는 0~+1.23 J였다. 이는 사후에 본 seed의 진단이고 확인/실측 표본이 아니다.

## 검증·지원·다음 행동

PC 관련 31개 테스트가 통과했다. 입력 상태 누락·strict 차단, 전력/AP 변경에 따른 실제 dispatch, 예상/실현 분리, 미래 도착·실현 duration 누설, 대기 중 새 도착, 유한 종료, 이벤트 경계/lane 해제, 기존 정책 회귀, 온라인/사후 공통창 에너지·AP 일치를 확인했다. Chrome 로컬 HTML의 기본 렌더와 필터 변경, SVG 렌더, 상대 경로 번들의 별도 폴더 byte-identical 재현을 확인했다. 이 검증은 Android 안정성·물리 전력 정확성·실사용 열 제약 검증이 아니다.

현재 답할 수 있는 질문은 **명시한 합성 요청·상태별 가정 아래 이 후보가 언제 배정/대기를 바꾸며 어떤 지표를 희생하는가**다. 임의의 A24 실제 idle/단독/병행 상태 W·AP 동특성, 전력·열 예측 오류 분포, 판단 비용, BAT 및 열→성능 피드백은 검증되지 않았다. 결론을 바꿀 가능성이 있는 측정 항목은 (1) 실제 사용되는 task×backend 단독·병행 상태의 기기 전체 전력, 특히 B2 `classification:GPU+detection:CPU`와 B3 병행 상태, (2) 같은 상태의 AP 경로/잔열, (3) 새 후보 계산·dispatch 시간이다. 측정은 이 후보를 실제 선택/절감 주장으로 발전시킬 때에만 별도 계약이 필요하다. 현 단계의 다음 행동은 대시보드에서 응답·에너지·AP 상충을 검토하고, 연구용 가정 아래의 후보를 유지할지 결정하는 것이다. 자동 실측·P 수정은 없다. 기존 `experiment_ready=false`, FAIL·원자료·동결값·종료 계획을 유지한다.

검증 기록: 2026-09-27 12:42 KST, 착수 HEAD `1c55c239eb0d56d050f9b1dd0c9fcb038e43b45e`, 이번 관련 코드·문서 미커밋 상태에서 위의 unittest **31개 통과**, dry-run 192건, 실제 PC 192건/기기 0건, Chrome 기본/필터 렌더·대표 SVG 확인, 별도 임시 폴더 상대 번들 HTML byte 일치. 고정 입력·설정·실행 당시 엔진/정책/runner SHA는 `run_v1/SOURCE_MANIFEST.json`에 있다. 테스트는 이후 commit할 이번 파일 상태를 대상으로 했다.

재현: `python -m unittest tools.test_d1_arrival_thermal_feedback tools.test_d1_arrival_explore tools.test_d1_arrival_policy_screen -q`; `python -m tools.d1_arrival_thermal_feedback_batch --dry-run`; PC 행렬 전체는 새 출력 경로를 주어 `python -m tools.d1_arrival_thermal_feedback_batch --output <새-폴더>`; `python -m tools.d1_arrival_thermal_feedback_analysis`; `python -m tools.d1_arrival_policy_screen --attach-thermal`. 이미 계산한 결과/HTML만 재현하려면 `docs/results/arrival_policy_screen_01/repro_bundle`을 복사한 뒤 그 폴더에서 `python reproduce.py --bundle . --output ..`를 사용한다.
