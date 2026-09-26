# ARRIVAL-ENERGY-SYNTHETIC-COLLECT-01 — Android 재생·기기 전체 에너지/AP 관측 후보

2026-09-26. [채택된 합성 연구 범위](ARRIVAL_ENERGY_SYNTHETIC_RESEARCH_20260926.md)의 **목적 A: 고정 trace의 정책별 전체 결과 비교**를 위한 새 개발 계보다. 기존 도착 평가·고정 870건 에너지 원본, FAIL, 동결값, 종료 계획을 변경하지 않는다. 이번에는 PC 구현·검증·APK·계획만 준비했고 기기 명령과 수집 소비는 0이다. 실행은 별도 승인·현재 기기 gate가 필요하다.

## 비교의 실제 의미

| 항목 | `CPU_URGENT` | `FIXED_SPLIT` |
|---|---|---|
| 큐 순서 | 긴급 우선, 등급 내 도착 순서 | 동일 |
| 배정 | 두 작업 모두 CPU | 긴급 분류 CPU, 일반 탐지 GPU |
| 대기 | CPU 점유 중 새 요청 대기 | 선호 lane 점유 시 대기; 다른 lane의 합법적 요청은 진행 |
| 병행 | 없음 | 분류 CPU＋탐지 GPU 최대 2건; 실제 완료 callback 전 lane 재사용 금지 |
| 작업 | 각 trace 분류6·탐지18, 동일 이미지/모델/입력 | 동일 |

두 arm은 **배정과 병행 가능성**이 함께 달라진다. CPU 우선순위 규칙은 같지만 그 효과를 단독 원인으로 분리하지 않는다. `FIXED_SPLIT`은 기존의 강한 정적 B2와 동의어가 아니다. 기존 B2의 탐색 선정 배정은 분류 GPU＋탐지 CPU이고 그 반대 방향의 도착별 에너지/AP는 미측정이다. 이번에는 정책을 재선정하거나 약화된 arm으로 B2 최종 비교를 대체하지 않는다. 기존 조건부 B3/P는 시간 가정·대기 규칙이 다르고 도착별 전력/열 지원 범위가 없어 제외한다. 새 적응형 튜닝은 없다. 모든 GPU 결과는 기존 품질 참조와 실제 두 GPU runtime의 delegate 로그를 gate로 요구한다. API overlap은 GPU kernel 동시 실행 증명이 아니다.

## 입력·시간·계측 경계

- [기존 trace 식별자](results/arrival_energy_research_01/scenario_manifest.json)의 low(1,200ms)·queue(200ms)·burst(80ms+6건마다 1초) 각24개 예정 도착을 재사용한다. 매 4번째 중 index 1이 긴급 분류, 나머지는 일반 탐지다. 긴급 1.5초·일반 6초는 **연구용 기한**, 실사용 SLA가 아니다. 독립 scheduled executor가 예정 도착을 예약하므로 dispatch 지연이 다음 예정 도착을 밀지 않는다. 예정/실제 도착·queue·판단·dispatch·worker 시작·output_ready·persist_complete·worker_release·lane_available을 별도 시각으로 보존한다.
- 앱 `SystemClock.elapsedRealtimeNanos`와 `/proc/uptime`의 동일 기기 monotonic 축을 사용한다. 앱 전류/전압/배터리·상태는 약 1초마다 조회하고 snapshot 시작/종료를 기록한다. host AP는 thermalservice 조회 전후 uptime bracket을 남기며 약 2초마다 관측한다. host wall clock은 예산·명령 증거에만 사용하고 두 시계를 직접 빼지 않는다. 화면 조회는 기존 축소 parser·2초 timeout으로 최소 10초 간격이다. host AP/화면 조회와 앱 journal은 부하를 줄 수 있어 조건마다 동일하게 적용하고 비용 없음으로 주장하지 않는다.
- 모든 arm의 공통 에너지 창은 첫 예정 도착 기준 정확히 `0..120초`다. 실제 창 종료 관측시각은 별도 기록한다. 미완료/실패도 예정24개 분모에 남긴다. 긴급 응답은 예정 도착→output_ready, 일반 응답·작업 완료는 예정 도착→persist_complete다. worker_release와 lane_available 및 앱/host cleanup은 별도다. 창 이후 작업 에너지는 공통창에 넣지 않고 작업 완료시점까지의 별도 적분에만 포함한다. 끝내 완료되지 않으면 완료시점 에너지는 성공값이 아니라 미산출이다. low/queue/burst의 마지막 도착은 27.6/4.6/4.84초라 120초의 긴 idle이 차이를 희석할 수 있으나 결과를 보고 창을 바꾸지 않는다.
- 앱은 runtime4·warmup8 이후 30초 resident baseline을 한 번 관측하고 120초 공통창→최대30초 drain→60초 resident cooling으로 종료한다. 앱 sampler는 검증된 짧은 snapshot lock만 사용한다. 센서 조회·파일 쓰기·추론은 lock 밖이다. 예외 class/stack/thread/phase/time sidecar, bounded journal, 부분 회수, host cleanup을 보존한다. 다만 비동기 journal의 마지막 미동기 prefix는 native/process 종료 시 사라질 수 있으므로 기록 부재를 호출0으로 판정하지 않는다.
- 전류 raw의 A24 `mA` 해석은 가장 유력한 **조건부 가설**이다. 기기 전체 에너지이지 CPU/GPU 전원 rail이 아니다. 충전/unsupported/gap/중복을 배제하고 완전 coverage가 없으면 절대 J를 `null`로 둔다. AP 센서의 온도는 BAT·표면·공식 안전온도가 아니다. 동일 resident idle 대비 추가 소비는 별도 산술이고 음수도 그대로 둔다. 준비·초기화·gate·냉각의 계측 범위와 host staging/설치의 미계측 비용을 구분한다.

## A와 B, 개발·확인

**A는 이 계획으로 기술적으로 관측 가능하다.** 같은 24요청/120초에 대해 성공/미완료 분모·긴급 P95·일반 평균/기한 위반·전체 기기 에너지/AP 경로 및 완료시점과 냉각 포함 시간을 기술한다. 조건당 개발1·확인1 **독립 세션**뿐이어서 우월성·tail·열 평형·인과효과 PASS는 부여하지 않는다. 시작 AP·배터리·순서·대기 시간을 함께 보고하고 과거 실패한 첫 직렬 AP anchor를 되살리지 않는다.

**B(다른 trace용 idle/단독/overlap 상태별 전력·열 모형 보정)는 이 계획의 자동 결과가 아니다.** 기존 전류 약1초·AP 약2초의 실제 갱신보다 짧은 요청 전환이 많아 요청별 소비, queue 대기와 resident idle의 물리적 전력 차이, 짧은 CC_DG overlap 열계수를 식별하지 못할 수 있다. software 상태와 overlap 길이는 기록하지만 충분한 독립 dwell·시계 coverage가 확인되지 않으면 상태별 계수는 미지원으로 둔다. 고정870건 계수를 이 trace에 자동 전용하지 않고, 목적 B가 나중에 정말 필요하면 별도 상태 유지 관측을 설계한다.

개발6세션은 재생·품질·clock·coverage·실제 정책 차이의 적격성과 기술 지표를 본다. 정책·trace·기한·120초·분석 규칙은 **계획에서 이미 고정**했으며 개발 자료로 계수를 맞추거나 두 arm을 고르지 않는다. 전부 적격할 때 개발 artifact hash/분석 규칙을 동결하고 확인6세션을 별도 평가한다. 확인 자료로 계수·arm·기준을 변경하지 않는다. 이미 본 PC 탐색 trace를 재사용하므로 확인 세션이라도 새로운 시나리오에 대한 완전한 독립 정책 평가가 아니다. 미적격 시 즉시 중단하고 미시도 분모와 부분 소비를 남긴다. 재시도·대체·추가0.

## 실행 후보 예산과 gate

| 항목 | 상한/고정 | 근거 |
|---|---:|---|
| 세션 | 개발6→동결→확인6, 총12 | 2 arm×3조건×2단계; 조건당 단계별 독립1회라 정밀/안정성 판정 불가 |
| 요청·warmup·runtime | 요청288, warmup96, 명시적 추론384, runtime48 | 세션당24＋8, runtime4 |
| staging·설치 | staging12회·84파일; APK 전송/설치 각각≤1 | 세션당 입력6＋manifest1, 설치본 exact 동일이면 설치 생략 |
| 고정 관측 | 공통창24분＋resident baseline6분＋앱 cooling12분＋세션 사이 cooling22분 = **64분** | 앱 watchdog/host poll은 포함 경계이며 더하지 않음 |
| 세션 예약 | 700초×12=140분 | 세션당 gate/stage120＋host poll485(앱 watchdog480 포함)＋회수50＋cleanup45; 일반 예상시간 아님 |
| 별도 예약·전체 상한 | 설치600초＋동결300초＋세션8,400초＋세션 사이1,320초 = **10,620초/177분** | 준비·설치·회수·cleanup·냉각 포함 hard 상한. 정상 평균시간/배터리 완주 미확인 |

앱 단일 watchdog480초는 내부 setup≤150초·host warmup gate≤60초·baseline30초·공통120초·drain≤30초·cooling60초·cleanup 여유를 함께 감싼다. host poll485초와 더하지 않는다. runtime/warmup/요청 호출별 기존30초 timeout, 화면 조회2초/재시도0을 유지한다. 남은 예약이 모자라면 다음 단계/세션을 시작하지 않는다. 실행 전 동일 A24 transport serial·fingerprint/하드웨어 serial, 앱 서명/설치본 APK 해시, 배터리≥20%·비충전·≤35°C·thermal0, awake/interactive와 기존 밝기81/수동0/자동꺼짐5시간, memory admission/모델 입력·품질/GPU delegate를 현재 값으로 검사한다. 설치/기기 설정 변경은 후보의 명시된 설치 범위 외에는 하지 않는다. 현재 연결·배터리/열·설치본·실제 GPU/계측 coverage와 177분 완주 가능성은 **PC에서 미검증**이다.

## 준비물·재현

[작은 PC 검증·정확한 경로/해시](results/arrival_energy_android_prep_01/README.md)를 따른다. 외부 `arrival_energy_synthetic_build_v2`의 프로젝트 서명 APK와 `arrival_energy_collection_plan_v1`의 계획/12 manifest/실행 스크립트는 로컬 전용이다. `Check`와 dry-run은 ADB·설치·앱 실행·소비 registry 생성 0이다. `Run`은 이 문서의 실행 승인이 아니라 **나중에 별도 승인과 해당 계획 SHA를 받은 경우에만** 단일 사용한다. 기존 종료 계획은 재개하지 않는다.

PC 테스트는 Android/native 안정성·출력 품질·전력/AP 측정 적격성의 실기기 PASS가 아니다. 다음 행동은 준비된 새 계획의 조건·예산에 대한 별도 실행 승인과 현재 기기 gate 확인이다. `experiment_ready=false`를 유지한다.
