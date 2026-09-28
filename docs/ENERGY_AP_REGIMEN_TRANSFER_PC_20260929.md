# A24 상태 에너지·AP 동결 모형의 DIAG-04 전이 평가 (2026-09-29)

**판정:** 개발3세션 동결 모형을 byte 변경 없이 새 APK의 CG_DC 진단1세션에 적용했다. 실제 블록 상태와 전환 시각이 주어진 **사후 일정 조건부 예측**은 재현 가능하지만, AP 최고를 1.612°C 높게 예측했고 병행 구간부터 큰 열 잔차가 보인다. 이 한 세션으로 새 프로토콜의 일반 오차나 임의 도착 정책 순위를 검증할 수 없다. 별도 후보 모형은 만들지 않았다. [대시보드](results/energy_ap_transition_01/dashboard.html)에서 관측·예측·구간 잔차를 볼 수 있다.

## 계보·경계

동결 파일 `energy_ap_state_run_v5/development_freeze.json` SHA-256 **`35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`**, 버전 `energy-ap-state-regimen-fit-v1`. `CC_DG→CG_DC→DC_DG` 개발3세션에서 8개 상태의 **기기 전체 평균 W**와 AP 1차 기울기/공통 냉각률을 적합했다. 이후 같은 과거 계보의 확인 `DC_DG` 1세션만 완료했다. 새 DIAG-04는 별도 CG_DC 진단이며 확인 자료가 이미 알려진 뒤의 사후 전이 평가다. 독립 세션은 개발 조건당1, 기존 확인 DC_DG1, 새 전이 CG_DC1이다. 센서 표본·추론 건수를 독립 반복으로 세지 않는다.

| 비교 항목 | 개발3·기존 DC_DG 확인 | DIAG-04 CG_DC | 판정 |
|---|---|---|---|
| 기기·두 모델 SHA·입력 SHA·CPU thread1·4 resident runtime | A24·동일 exact 모델/입력 | 동일 | 동일성 검사 통과 |
| 앱 APK | `b273f74b…114cf` | `933d202e…831f7` | lifecycle 기록/진단 제어 변경; 동등 계측 비용 미검증 |
| 세션 제어 | host가 공식 baseline arm과 단계 조회 수행 | host probe 승인 뒤 앱이 baseline→부하→냉각 진행 | **프로토콜 변경**; host ADB와 앱 기록 비용을 임의로 빼지 않음 |
| 부하/상태 | 고정600초 상태 regimen, 250ms 제출 | 같은 CG_DC 블록·120/30/90/30/90/120초와 완료 후 대기 | 작업1,073회(개발 CG_DC1,074회), 실제 lane 공동 점유120.037초; host 추론 invocation 겹침9.062초 |
| 시작 AP | 개발32.5–34.0°C; 기존 DC_DG 확인34.1°C | 32.6°C | 개발 **시작** 범위 안. 전체 내부 열상태/주변 조건 동등은 미확인 |
| AP/전력 센서 | AP `mType=0`, 약2.65초/앱 전류 약1초 | AP390표본 전체·앱 전력1,038표본 전체; 공통창 gap 검사 통과 | 같은 센서·조건부 mA 단위. 새 host 조회 비용의 효과는 미계측 |

원본 [DIAG-04 receipt](<C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v4/FINAL_RECEIPT.json>)와 [실행 판독](ENERGY_AP_DEVICE_SEGMENT_DIAG04_RESULTS_20260929.md)을 수정하지 않았다. 개발 원본·동결값·기존 FAIL·COLLECT-05/CONFIRM-06/DIAG-03 종료 상태는 유지한다. 현재 실행 중 동일 산출물 생성 프로세스는 착수 시 없었고 로컬/원격 HEAD `347a006a…5ab`에서 시작했다.

## 동결값의 실제 전이 오차

두 조건 모두 실제 상태·전환 시각을 입력받았다. 예측 에너지는 각 상태 전체 W×점유초의 합이며 idle을 중복 더하지 않는다. AP는 관측 **시작값만** 사용해 매 구간 경계의 예측 온도를 연속 전달한다. 이후 전류/AP 관측을 재입력하지 않았다. 고정 부하/일정 재생인 **A** 수준이고, 도착·계획으로 일정까지 만드는 종단간 **B** 수준은 미지원이다.

| 600초 공통창 | 관측 | 동결 예측 | 예측−관측 |
|---|---:|---:|---:|
| 기기 전체 J, 실제 상태가 매핑된 600.090초 | 953.055 | 966.176 | **+13.121J (+1.377%)** |
| 전체 600.098초 관측 J | 953.069 | 전체창 예측 **계산 불가** | 상태 미매핑 0.008323초·관측0.013383J; 이를 0으로 넣지 않음 |
| AP 최고 °C | 37.600 | 39.212 | **+1.612°C** |
| AP 경로 | 225개 비교 표본 | — | MAE **0.834°C**, 최대 절대 **2.278°C** |
| 기존 연구용 30°C 초과 | 양쪽 유효 AP 구간596.690초 | 596.690초 | 0.000초; 이미 시작32.6°C라 구별력이 거의 없음 |

기존 평가 함수의 출력 `+13.108J`는 **전체 600.098초 관측량**에서 600.090초의 상태 예측량을 뺀 값이다. 약 0.008초의 미매핑 구간을 관측 쪽에만 포함한 경계 차이가 있다. 새 판독의 주 지표는 두 쪽 모두 매핑 구간만 비교한 **+13.121J**이며 기존 함수/동결 파일은 변경하지 않았다. 공통창 전체 전류 coverage는600.098초·결측0이지만 **상태 매핑 coverage**와 구분해야 한다. 기존 누적 경로 진단(10초 격자)은 MAE9.921J·최대16.679J이고 같은 경계 차이를 유지해 보조 표시만 한다.

| CG_DC 구간 | 관측 J | 예측 J | 예측−관측 J | AP MAE °C |
|---|---:|---:|---:|---:|
| 병행 pair | 271.440 | 279.759 | **+8.320** | 1.777 |
| 첫 유휴 | 37.890 | 36.830 | −1.060 | 1.447 |
| 탐지 CPU 단독 | 175.924 | 174.133 | −1.791 | 0.752 |
| 둘째 유휴 | 35.597 | 36.845 | +1.248 | 0.547 |
| 분류 GPU 단독 | 140.924 | 145.009 | +4.085 | 0.214 |
| 긴 유휴 | 144.365 | 147.151 | +2.786 | 0.432 |
| 완료 후 대기 | 146.915 | 146.449 | −0.466 | 0.727 |

구간 오차의 부호가 섞여 총량에서 상쇄된다. 개발 동결 CG_DC 병행 전력2.327W에 비해 이번 pair 구간 평균2.258W였지만, 이것은 요청별/순수 동시 실행 전력 변화의 식별이 아니다. lane 공동 점유120.037초와 host inference 교집합9.062초, callback·250ms 제출·전압/열상태 등이 섞였다. AP는 pair 구간에서 관측보다 빠르게 올라가며, 최고온도 1.612°C 차이는 기존 합성 정책 탐색에서 사용한 작은 열 상충을 판별할 오차 보장으로 쓸 수 없다. 전류 raw=mA는 조건부 해석, 절대 J 정확도 미인증이다.

## 연결한 시뮬레이터 지원 범위와 보완 결정

[조건부 adapter](../tools/d1_energy_ap_regimen_transition.py)는 새 진단의 manifest·원본 해시와 동결 byte SHA를 검사하고 **실제 CG_DC 블록 일정, 같은 모델/입력/runtime/기기, 개발 시작 AP 32.5–34.0°C**에서만 계산한다. 출력은 `posthoc_protocol_transfer_only`다. 고정 블록 밖·다른 시작온도·미지원 상태·불완전 에너지에는 수치 대신 unsupported다. [도착 연구 엔진](../tools/d1_arrival_energy_research.py)에 이 동결 profile을 명시해도 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`와 J/AP `null`을 반환하며 기존 strict·explore 결과를 바꾸지 않는다. 이는 모형의 한계를 화면에 연결한 것이지, 임의 도착을 실측 기반으로 예측하게 만든 것이 아니다.

보완 후보는 **생성하지 않았다**. 새 APK와 host 조회 변경의 소비 차이·세션별 열상태·1회뿐인 CG_DC 전이 자료 때문에 pair AP 잔차를 모형 구조 결함이나 특정 계수로 분리할 수 없다. 확인 자료에 새 계수를 맞추면 개발·확인 분리가 무너진다. AP 잔열·초기 온도 평행 이동을 임의 보정하지 않았고 기존 DC_DG 확인의 +4.550J·AP MAE0.645°C도 덮어쓰지 않았다. 정책 효과의 수 J 차이를 이 오차가 넘는 조건에서는 정책 선택에 충분한 모형이 아니다.

## 추가 측정 필요성: 하나의 목적만 남김

### 짧은 도착 1입력의 PC 계측 가능성 감사 (후속, 2026-09-29)

결과를 보기 전에 기존 생성 규칙의 **queue·seed 201·strict·24요청**을 하나의 기계적 감사 입력으로 고정하고, 저장된 `timeline.csv`의 `CPU_URGENT`와 Android 도착 활동이 실제 지원하는 `FIXED_SPLIT`만 읽었다. 재시뮬레이션·기기 명령·계수 적합은 0회다. `dispatch→lane_available` 점유와 `execution_start→output_ready` 추론 구간을 따로 sweep했으며 120초 공통창 전체를 idle 포함으로 분할했다. [CSV](results/energy_ap_transition_01/short_transition_occupancy.csv)·[SVG](results/energy_ap_transition_01/short_transition_occupancy.svg)·[입력 SHA/가정](results/energy_ap_transition_01/short_transition_audit.json)을 보존한다. 기존 `CPU_URGENT`의 상태별 점유 합계는 별도 보존된 occupancy ledger와 1µs 안에서 일치한다. **모두 PC 모형 일정이며 Android 실측 점유가 아니다.**

| 고정 입력의 lane 상태 | 전체 점유 | 연속 구간·최대 | 2회 전류 주기(2초) 이상 | 2회 AP 주기(약5.3초) 이상 |
|---|---:|---:|---:|---:|
| CPU_URGENT 분류 CPU | 1.073초 | 6·0.183초 | 0 | 0 |
| CPU_URGENT 탐지 CPU | 11.329초 | 18·0.633초 | 0 | 0 |
| FIXED_SPLIT 분류 CPU | 1.073초 | 6·0.183초 | 0 | 0 |
| FIXED_SPLIT 탐지 GPU | 20.472초 | 18·1.145초 | 0 | 0 |
| FIXED_SPLIT 분류 CPU＋탐지 GPU | **0초** | **0** | 0 | 0 |
| 완료 후 긴 유휴 | CPU 107.591초 / split 98.448초 | 각1구간 | 각1 | 각1 |

`FIXED_SPLIT`은 이 **한 PC seed에서** 실제 배정은 CPU/GPU로 갈렸지만 병행 점유가 생기지 않았다. 추론 invocation 구간도 병행0이며 탐지 GPU 합계19.023초다. 병행 0은 다른 seed나 Android의 결과가 0이라는 뜻이 아니다. 현재 약1초 전류·DIAG-04에서 확인한 약2.65초 AP 갱신의 서로 다른 phase/불규칙 간격을 감안하면, 위 2주기 길이 검사는 보수적인 *가능성 화면*이지 표본 확보 보장이 아니다. 요청 24건을 독립 전력·열 표본 24개로 세지 않는다. 긴 idle이 120초 전체 J를 지배하므로 이 입력은 상태별 **병행** 계수나 짧은 전환 AP 잔열을 식별하는 수집안이 될 수 없다. 동결 모형의 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS` 차단은 유지한다.

Android의 [`ArrivalEnergyActivity`](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalEnergyActivity.kt)는 같은 low/queue/burst·24요청·2정책을 검증하고 `warmup.arm`을 host로부터 받아야 baseline에 진입한다. 전류 1초·host AP 2초 조회, resident baseline30초·공통120초·drain 최대30초·냉각60초, runtime4·warmup8·작업24/세션이 현재 **코드상 산술**이다. 실제 병행 보장은 없고, host 조회가 끊기면 AP 경로가 결측된다. 이전 12세션 계획 v4의 PC `Check`는 현재 소스에 대해 `source changed`로 실패한다. 이전 APK/host 계측 계약과 최신 DIAG-04 lifecycle APK를 동일한 새 확인 경로로 자동 전용할 수 없다.

따라서 후속 실측은 **목적상 필요하지만 현재 실행 계획은 미준비·미승인·미소비**다. 권고하는 *다음 작업 하나*는 PC에서 별도 opt-in 단일 세션에 분류 CPU＋탐지 GPU의 **실제 공동 점유**와 단독↔pair↔idle 전환을 확인할 수 있는 입력/기록/적격성 경로를 먼저 구현·검증하는 것이다. 연속 상태마다 실제 AP 표본 수·최대 gap을 검사하고 실패 시 계수 식별 불가로 남겨야 한다. 이때 앱 종료·host 회수, 설치 APK 동일성, 장치 내부/host gate, ADB 명령·시간 상한을 새 코드에 맞춰 산정한다. 지금 24요청 경로의 4 runtime·8 warmup·24작업 및 옛 세션700초를 새 패턴의 예산으로 **확정하지 않는다**. 지속 병행을 위한 반복 호출 수와 실제 전환·센서 coverage가 미정이라 정확한 실행 상한/Check·해시 계획을 동결할 근거가 없다. 그 전에는 새 실측을 시작하지 않는다. 기술 적격성 1세션과 추후 독립 예측 확인은 구분하고, 기존 확인 결과를 새 후보 개발에 재사용하지 않는다.

이 후속은 clean HEAD `b8b646e44653a4d2f65ea4850bf09230058001c0`에서 미커밋 새 감사 코드·문서를 대상으로 수행했다. `python -B -m unittest tools.test_d1_energy_ap_arrival_observability -v` 4건 통과, 저장된 CPU occupancy ledger와 120초 전력 회계 경계 일치, SVG XML/CSV/HTML 링크 검사 및 로컬 Edge headless 화면 시각 검사를 완료했다. 기존 v4 `Check`는 `source changed`로 실패했으며 이는 새 경로의 Check 통과를 뜻하지 않는다. 동결 파일 SHA `35ed6987…34c54` 유지, ADB·추론·실측 0회. 과거의 11건 회귀/전이 평가·전체 빌드는 반복하지 않았다.

정식 `CG_DC·CC_DG` 완료를 위한 반복 전체 재수집은 현재 모형의 임의 도착 적격성을 해결하지 못한다. 기존 자료는 긴 상태 regimen 전력/AP와 DC_DG 한 번의 동일 프로토콜 확인, CG_DC 한 번의 새 프로토콜 전이 잔차까지만 제공한다. **합성 도착 정책의 에너지·열 우열을 실측 기반으로 주장하려면** 독립된 새 프로토콜에서 짧은 단독↔pair↔유휴 전환과 큐 대기/완료 후 유휴가 실제로 나타나는 제한된 도착 패턴을 측정해야 한다. 이는 **확인용** 자료이며 이번 CG_DC 결과로 후보를 적합한 개발 자료로 돌리지 않는다. 최소 질문은 “동결 상태 모형의 일정 조건부 J/AP 경로 오차가 짧은 전환에서도 정책 간 차이보다 작은가?”다.

현재 Android 진단은 고정120/90초 블록 실행기이며 짧은 전환 패턴을 재생하는 별도 APK/호출 경계와 적격성·시간 상한이 동결되지 않았다. 기존 [`ArrivalEnergyActivity`](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalEnergyActivity.kt)는 24요청 합성 도착과 lane/전류 표본을 기록하지만 `warmup.arm` 등 host gate와 별도 정책 비교 계획에 묶여 있다. 그 **이전 앱 경로를 새 진단 APK의 자율 세션·동결 모형 확인으로 그대로 전용할 수 없다**. 위 단일 입력 감사에서도 병행 상태가 없음을 확인했다. 따라서 세션·작업·runtime·ADB·설치·총시간 숫자를 근거 없이 확정한 실행 계획은 만들지 않았다. **실행 준비 상태: 미준비·미승인·소비0**. 전환 입력과 센서 coverage·호출 상한을 PC에서 검증할 때만 제한 확인 계획/예산을 동결한다. 그 결과 없이 12세션안이나 또 다른 6세션 수집을 자동 제안하지 않는다. 실기기 전체·BAT/잔량/수명·throttling은 계속 미지원이다.

## 검증·재현

[작은 공유 번들·명령](results/energy_ap_transition_01/README.md). 원본 SHA·동결 SHA·모델/입력/runtime·계산 경계·CSV/그림 일치를 검사한다. `python -m unittest tools.test_d1_energy_ap_regimen_transition tools.test_d1_arrival_energy_research -q` **11건 통과**. 기존 DC_DG `state.evaluate` 결과가 저장 원본과 정확히 같고 동결 SHA가 불변임을 별도 확인했다. 로컬 HTML을 Edge headless로 열어 한글·표·SVG 배치를 시각 확인하고 내부 링크9개 및 표/곡선 수치를 검사했다. 시작 HEAD `347a006a1e177685843b29b419ab01c2c45c58ab`에서 PC 분석을 수행했으며 새 코드·미커밋 변경 대상으로 검증했다. 이번 작업의 기기 명령0, 기존 APK/동결값 변경0, `experiment_ready=false` 유지.
