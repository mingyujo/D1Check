# 동결 에너지·AP 모형의 최소 도착 확인 설계와 실행 차단

## 후속 구현: 시작 직전 1회 AP gate (2026-09-29)

사용자의 후속 지시에 따라 `start_ap_gate=numeric-ap-once-v1` opt-in을 실제 `ArrivalEnergyActivity`와 host `poll`에 연결했다. 아래 최초 차단 판정은 당시 기록으로 보존한다. 기존 manifest에 필드가 없으면 과거 동작을 유지한다. 새 모드는 resident baseline 종료 후 앱이 manifest hash와 device monotonic ready 시각을 저장하고 최대30초만 대기한다. host는 ready를 읽은 **뒤** 기존 HAL AP 조회를 한 번 수행한다. 범위32.5–34.0°C, numeric/finite, thermal0, 시각 구간을 확인하고 안전한 숫자/hash만 들어간 승인 파일을 원자적으로 게시한다. 부적격·조회 실패면 arm을 보내지 않고 기존 실패 회수/cleanup으로 진행한다. 적격한 순간을 기다리는 반복이나 가열·추가 추론·retry는 없다.

앱은 실제 공통창 origin을 잡는 직전에 승인 hash/ready nonce를 검증하고 **AP 읽기 시작부터 실제 origin까지3초 이하**를 다시 검사한다. 읽기 종료→시작 지연과 읽기 bracket, AP를 `start_ap.accepted.json`에 저장한다. 파일 누락·기한 초과·결측·범위 이탈·시각 역전이면 작업 dispatch 이전에 실패하므로 본 작업0회다. 유효 표본은 HAL 조회 당시 값이라는 의미다. HAL 내부 갱신 시각/0.1°C 양자화 및 판독 후의 물리적 변화를 완벽히 보증하지 않는다. 준비 통과만으로 실제 시작을 허용하지 않고 앱의 최종 freshness 검사를 통과해야 한다.

새로 필요한 통신은 시작 전 **최대5명령**(ready 회수1, uptime→HAL→uptime3, arm 게시1)이며 기존2초 AP·10초 화면 관측 주기를 늘리지 않는다. 시작 승인 후 새 handshake는 없다. 이는 완전한 무통신 시작이 아니라 제한된 pre-load 의존이며 연결 소실 시 arm 대기 timeout으로 본 작업을 차단한다. 앱이 numeric AP를 직접 읽는다고 표현하지 않는다. 읽기/전송/대기는 준비구간에 포함하고120초 공통창 이전이다. 승인 기록 쓰기는 common origin 이후여서 시간·에너지 창 안에 포함된다. 요청 예정 도착은 origin+기존 offset으로 유지되어 기록 지연으로 실제 dispatch가 늦어지면 그대로 응답 오차에 나타난다. 계측 비용을 임의로 빼지 않고 준비 구간 소비도 별도 보존한다. 기존 동결 파일은 변경하지 않으며 새 자료는 프로토콜 전이로 구분한다.

**확인 완료의 의미:** 이번 queue24/고정배정/120초/유효 초기조건 한 세션의 전체 에너지·AP 및 일정·응답 예측 오차를 보고하는 것이다. A는 실제 일정 조건부, B는 사전 시간모형으로 생성한 일정이며 이후 측정값을 예측 입력으로 쓰지 않는다. 예정24 분모에서 실패·미완료를 보존하고 누락 구간은 계산 불가, J 오차(부호/절대/상대)·누적 경로·AP MAE/최대/최고/초과시간·요청별 응답/일정 차이를 모두 보고한다. 근거 없는 정확도 PASS·허용률은 만들지 않는다. 병행 점유0인 기존 PC 일정으로 병행 계수·짧은 개별 J·임의 부하 전체 검증 완료를 선언하지 않는다. 계수 보정이나 strict 지원 확대는 별도 증거 없이 하지 않는다.

PC 검증: `tools.test_d1_arrival_start_ap`은 가짜 기기 경로로 실패시 승인0회·정상 승인1회·실제 host poll에서 warmup→AP 승인 단일호출을 검사한다. `ArrivalStartApGateTest`는 경계/결측/NaN/다른 manifest/과거 nonce/실제 시작 시 만료를 검사하고 `ArrivalEnergyContractTest`는 기존24요청·배정 규칙을 회귀 검사한다. 기기 실행/실물 연결 내성 검증은 아니다. 새 서명 APK·현재 기기 적격성·새 단일세션 총예산 계획은 아직 발행하지 않았다. 과거 차단 입력/Check를 실행 가능으로 바꾸지 않으며 다음은 이 소스의 APK 및 단일세션 계획을 준비하는 일이다.

**판정:** PC 입력·시작 AP 사후 판독·원본 센서 해상도 감사는 완료했다. **현재 APK와 host 경로로는 부하 시작 시 numeric AP 적격성을 집행할 수 없어 기기 실행 계획은 아직 만들 수 없다.** 기존 준비 gate를 통과한 뒤 resident baseline 동안 AP가 변하며, 앱은 baseline 뒤 host 승인 없이 load를 시작한다. 새 host 실시간 handshake를 넣어 과거 연결 의존을 다시 늘리거나, thermal status를 numeric AP 대신 쓰거나, 모형 범위를 넓히지 않았다. [입력·해시·PC 명령](results/energy_ap_arrival_confirmation_01/README.md) · [기존 진단과 범위 밖 +23.280J의 정확한 의미](ENERGY_AP_SHORT_TRANSITION_DIAG01_20260929.md).

| 근거 항목 | 고정 사실과 한계 |
|---|---|
| 동결 파일 | COLLECT-05 개발 3세션 `development_freeze.json`, SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`; `energy-ap-state-regimen-fit-v1`, 8개 상태의 기기 전체 W, AP 1차식. 변경 0. |
| 구성·지원 | A24, EfficientNet-Lite0 분류/EfficientDet-Lite0 탐지, 입력·CPU 1 thread·4 resident runtime의 기존 manifest 동일성 필요. 단독 분류/탐지 CPU/GPU, CC_DG·CG_DC·DC_DG, resident idle의 **계수 값은 존재**하지만 동결 검증 경로는 기록된 600초 상태 블록 일정으로 제한. 임의 도착 strict는 unsupported. 분류 CPU＋탐지 GPU를 반대 배정과 합치지 않음. |
| AP 범위 | `initial_ap_development_range_c=[32.5,34.0]`은 실제 개발 시작점; `ap_development_observed_range_c=[32.5,39.5]`는 전체 경로. 물리 한도 아님. 기존 `evaluate`의 범위 검사는 후자를 쓰므로 새 **사전 시작 gate 계약**에 전자를 사용. 32.3°C 진단은 양쪽 하한 밖이고 확인 표본 아님. |
| 센서/요청 | 단기 전환 원본 공통창 전류 600개, 1.000초 중앙·1.093초 최대 간격; numeric AP 229개, 2.630초 중앙·3.525초 최대; 단일 호출 lane 점유 중앙 0.163초·최대 1.209초. host AP 조회 간격은 하드웨어 내부 갱신 간격의 증명이 아님. 개별 호출 J는 식별 불가. 6개 pair 블록의 12.908–13.352초 공동 lane 점유는 블록 비용/경로 점검 수준. |
| 진단 산술 | 실제 전체 공통창 600.094초·903.842J. 상태 매핑 600.056초의 관측903.793J·동결식 대입927.073J의 **+23.280J는 범위 밖 탐색 외삽**. 제외 0.0376초·0.049J를 0으로 처리하지 않았고 전체창 검증 오차로 보고하지 않음. |
| 선택 입력 | 기존 queue 24요청, `FIXED_SPLIT`, 200ms 간격 0–4.6초, urgent6/normal18, 연구 기한 1.5/6초, 공통창120초. 기존 seed201 PC 화면은 정책 결과가 아닌 **상태 길이 화면**으로만 사용. 그 일정은 CC_DG 공동 점유 0초·단독 최대1.145초여서 병행 계수 또는 요청별 전력의 적격성 검사는 불가. |

## 예측과 판독 경계

A(조건부): 같은 세션에서 확인한 실제 도착/dispatch/worker release/lane_available로 상태 경계를 만들고, 관측 시작 AP **한 값**을 초기조건으로 둔다. 동결 상태별 전체 W를 공통 120초에 중복 없이 적분하고 AP 경로를 잔열 연속으로 예측한다. 실제 공통창 J/누적 경로, AP MAE·최대절대·최고·기존 연구용 한도 초과시간과 비교한다. 실제 출력/저장/worker/lane 경계가 없는 부분은 계산 불가로 남긴다. 1초·2.63초 표본보다 짧은 상태의 개별 오차를 주장하지 않는다.

B(종단간): 같은 24개 예정 도착·고정 배정과 **사전 동결된** 처리시간 추정만으로 일정을 만들고, 예정 24개 전체의 완료·실패·미완료 및 긴급 output_ready/일반 persist_complete 응답·기한 위반과 A의 에너지/AP 지표를 비교한다. 실제 미래 완료시각·전류·AP를 입력으로 사용하면 B가 아니다. 현재 PC 시뮬레이터는 이런 연구용 일정을 만들지만 설치된 새 APK의 시간/host callback 오차를 별도로 확인하지 못했고, 동결 에너지 strict는 임의 전환을 차단한다. 따라서 B는 **설계된 확인 질문**이지 아직 검증 가능한 수치 출력이 아니다. 24요청을 길게 만든 블록 진단과도 다르다.

자료 적격성은 시작 AP 범위·시각/센서 공백·상태 매핑·공통창 포함·예정 요청 전체 분모를 먼저 검사한다. 적격해도 예측 정확도 PASS가 자동으로 나오지 않는다. 오차의 부호·크기·구간별 상쇄와 정책 간 차이를 함께 보고하며 임의 허용오차는 만들지 않는다. 온도에 따른 처리시간 감속, BAT 온도, 잔량/사용시간, 절대 J 정확도는 범위 밖이다. 시작 뒤 AP가 개발 경로 범위를 벗어나면 이후 AP 예측은 그 시각부터 unsupported로 표기해야 한다. 에너지 상태가 별도 지원 가능해도 같은 구간이 완전 계측됐을 때만 J를 독립 보고한다. 과거 판정은 바꾸지 않는다.

## 시작 gate와 실행 준비 판정

기존 `ArrivalEnergyActivity.gate()`는 warmup 후에만 호출된다. `resident_baseline` 30초 후 `commonStart=now()`로 바로 load에 진입한다. host `d1_arrival_energy_collection_device.poll()`은 AP를 약 2초마다 기록하지만 baseline 뒤 시작을 보류시키지 않는다. 기기 자체 `EnergyCollectionActivity` 진단도 numeric AP를 앱에서 읽지 못해 host 준비 후 120초 baseline과 실제 load 시작 사이의 AP 하한을 보장하지 못했다. 직전 세션의 32.3°C가 실제 사례다. 새 자료 화면의 마지막 3초 이내 표본 검사는 **사후 판독**이며 실시간 차단이 아니다. 시작까지의 드리프트·0.1°C 양자화로 경계 근처를 보증할 수 없다.

따라서 `input_manifest.json`은 계획 ID를 가진 **PC 고정 입력**이나 `session_budget=0`, `device_command_budget=0`, `Run` 없음, `PC_INPUT_FIXED_RUN_BLOCKED`다. 단일 세션 후보라도 현재 지원 밖인 병행 상태 계수를 확인한다고 속일 수 없고, 설치 APK 소스도 옛 12세션 계획과 일치하지 않는다. 정확한 작업/ADB/설치/전체 시간 예산이나 승인 후 명령을 이 상태에서 확정하지 않았다. 실행 가능 계획으로 바꾸려면 먼저 **부하 시작 경계에서 numeric AP를 읽고 적격하지 않으면 작업 0회로 종료하는 기기/host 연결을 PC에서 검증**해야 한다. 한 번의 제한된 시작 판정과 실패 종료를 설계해야 하며 기존 실시간 반복 handshake를 무심코 재도입해서는 안 된다. 그 변경의 APK·관측 부하·동결 모형 전이 비교 영향과 호출/시간 상한을 확인한 뒤에만 별도 미승인 실행 계획을 발행한다. 이 단계는 이번에 임의 구현하지 않았다.

이번 검증은 `python -B -m unittest tools.test_d1_energy_ap_arrival_confirmation -v`, `python -B -m tools.d1_energy_ap_arrival_confirmation check --manifest docs/results/energy_ap_arrival_confirmation_01/input_manifest.json`, `git diff --check`다. Check는 ADB 0회, 외부 원본을 읽지 않는다. 코드/CSV/JSON 화면은 실측 결과가 아닌 실행 전 설계와 이전 원본의 해상도 감사다.
### 후속 PC 검증 명령

```powershell
python -B -m unittest tools.test_d1_arrival_start_ap -v
# ANDROID_HOME: existing Android SDK; no SDK/runtime change
.\gradlew.bat -g .gradle-user --project-cache-dir .gradle-lifecycle -PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.ArrivalStartApGateTest --tests com.example.d1check.benchmarkrunner.ArrivalEnergyContractTest --offline --no-daemon --no-configuration-cache --console=plain
```

착수 HEAD `cfea8d366bc087e6b546950edd79d0ec27369532`와 이번 미커밋 소스 대상. Python3건/JVM4건, skipped0·실패0. 최초 Gradle은 SDK 환경변수 부재로 구성 단계에서 실패했고 기존 SDK 경로를 설정한 뒤 실제 본문/테스트 컴파일과 테스트를 완료했다. SDK/NDK/의존성 버전 변경0. 실제 도착 실행에서 예상 밖 병행이 나타나면 그 구간과 일정 오차를 보존하고 사후 제외하지 않는다. 해당 전환의 모형 적용 여부를 별도로 표시하며 PC의 병행0 가정을 실측 사실로 바꾸지 않는다.

## 2026-09-29 — 시작 AP gate APK·단일세션 계획 후속 준비

위의 `PC_INPUT_FIXED_RUN_BLOCKED`는 **당시 입력 판정 이력**이다. 별도 `ENERGY-AP-ARRIVAL-CONFIRM-01`은 동일 queue24/FIXED_SPLIT/120초를 새 APK와 `numeric-ap-once-v1`로 실행하기 위한 미승인 계획이다. 기존 12세션 계획·동결 모형·과거 결과를 재사용/재실행하지 않는다. 분석 판독은 [고정 JSON](results/energy_ap_arrival_confirmation_01/analysis_contract.json)으로 실행 전에 정했다.

| 확인 경계 | 코드상 사실 | 한계 |
|---|---|---|
| AP 값 | host `d1_energy_thermal.thermal()`이 `/proc/uptime` 앞뒤와 `dumpsys thermalservice`의 HAL `mName=AP,mType=0`을 읽고 status0·32.5–34.0°C 검사 | 질의 시계 구간은 알지만 HAL 센서 내부 최신 갱신 시각은 없다. 반복된 같은 숫자도 갱신 증거가 아니다. |
| 승인 | 앱 baseline30초 종료 뒤 `ready`의 manifest SHA/기기 monotonic 시각을 게시. host가 그 뒤 1회 읽고 원자적 arm 전송. host 전송 전·반환 후 시각과 앱 `accepted`를 따로 기록 | host와 기기 wall clock은 직접 빼지 않는다. 중복 session/output 파일은 새 ID·미소비 경로 검사로 차단한다. |
| 실제 시작 | 앱이 `arm`의 hash·ready nonce·AP·status·읽기 구간을 다시 검사하고, `common_start_ns−read_before_ns≤3초`일 때만 시작 | 3초는 **ADB 질의 시작→앱 origin** 상한이지 센서 물리적 갱신 나이 보증이 아니다. 결측·범위 밖·전달 지연·30초 gate 만료면 본 작업0회, 재시도0. |
| 비용 경계 | AP 질의/승인과 30초 resident baseline은 공통120초 **전**. 120초 뒤 미완료는 전체24요청 분모에 남기고 drain30초·cooling60초·cleanup은 별도 | AP 조회가 시작을 늦추고 잔열에 영향을 줄 수 있으며 그 물리적 비용은 미계측. 과거 동결 계수에서 빼거나 같은 프로토콜 확인으로 합치지 않는다. |

예정 도착은 앱의 **실제** `common_start_ns` + 고정 offset(0–4.6초)으로 각각 예약한다. 지연된 dispatch가 뒤의 예정 도착을 밀지 않는다. `scheduled_arrival`, actual arrival/queue, dispatch, execution, urgent `output_ready`, normal `persist_complete`, worker release, lane available을 구분한다. 공통창 종료 뒤 작업이 이어지면 창 내부 J에 이후 소비를 섞지 않으며, 실패·미완료를 제외해 서비스 분모를 줄이지 않는다. 실행된 상태에 병행이 나타나면 PC 예상 병행0초와의 차이로 기록하고 그 모형 지원을 따로 판정한다.

**A와 B의 판독:** A는 회수한 실제 상태·전환 시각과 origin의 관측 AP를 넣은 **조건부** 기기 전체 J/AP 경로 오차다. 상태 매핑이나 전류/AP coverage가 없으면 해당 지표는 `unsupported`; 누락을 0으로 메우지 않는다. B는 예정 도착·FIXED_SPLIT·실행 **전 동결** 처리시간 모델만으로 일정·응답을 예측하는 종단간 질문이다. 실제 미래 완료·전류·AP·상태 일정은 B 입력이 아니다. 기존 PC schedule의 병행0은 미래 실기기 병행0을 보장하지 않는다. 동결 에너지 strict의 임의 도착 전환은 여전히 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`여서 B의 에너지/AP는 지원 확인 전에는 계산 불가다. A 수치가 나와도 B 검증으로 승격하지 않는다.

| 원래 목표의 고리 | 현재 근거 | 이 1세션의 완료 범위 |
|---|---|---|
| 상태→기기 전체 전력 | 개발3세션에서 상태별 계수 동결, 짧은 임의 요청 전이는 미검증 | 실제 상태 일정 조건부 공통창·구간 잔차 확인만 가능. 요청별 전력이나 병행 계수의 독립 확인은 불가. |
| 상태·잔열→AP | 동결 1차 AP 경로, 초기 AP 개발 범위32.5–34.0°C | 관측 origin과 상태 전환에서 경로/최고/한도시간 오차 확인. 새로운 초기 범위·다른 APK 전이의 정확도 PASS 아님. |
| AP→처리시간/throttling | 검증된 함수 없음 | 확인 불가; 감속식을 만들지 않는다. |
| 도착·정책→일정·응답·J·AP | 연구용 24요청 생성기와 PC 엔진, 임의 전환 strict 미지원 | 일정·응답 진단과 A 지원 판정. 전체 동적 열 피드백 정책 비교 완료 아님. |

정확도 허용폭은 외부 근거가 없어 숫자 PASS를 만들지 않는다. 자료 적격성(시계·AP·전류·상태·완료/실패)과 오차 크기·부호·구간 상쇄·정책 간 예상 차이보다 큰지 여부를 따로 보고한다. A24 raw 전류=mA 해석은 조건부이고 절대 에너지 정확도는 인증되지 않았다. BAT/표면온도·배터리 잔량·실사용 절감은 대상 밖이다.

### PC 결과와 미승인 실행 예산

새 프로젝트 서명 APK는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_ap_gate_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk` (106,092,116 bytes), SHA-256 `d2af6d0a2ba8e995cf2a1b8682d50ac306d174a507eb6959377364e1780ea771`이다. `modelProbe`의 `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1이며 기존 프로젝트 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`와 같다. 격리 빌드 receipt `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_ap_gate_build_v1/build_receipt.json`의 Android 소스 SHA에는 `ArrivalEnergyActivity`와 `ArrivalStartApGate`가 들어 있다. `assembleModelProbe` 성공은 기기 설치·실행 적격성 증거가 아니다. APK/키/모델은 Git에 넣지 않는다.

새 계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_arrival_confirm_plan_v1/collection_plan.json`, SHA-256 `5dfc940d8fb67c3f2fe91399c670965b48493db50a4d4f47184c53eedffa641c`, 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`. 별도 ID·output·registry이며 둘 다 미생성이다. 이전 차단 manifest·12세션 종료/준비 계획을 재개하지 않는다. 현재 설치본은 **조회하지 않았고**, 실행 전 동일 A24·fingerprint·프로젝트 서명·현재 설치본·배터리/비충전/온도/thermal/화면/메모리/품질/GPU gate를 새로 확인해야 한다. 서로 다른 APK이면 계획 내 push·설치 각 최대1회만 허용하되 이 턴에서는 0회다.

| 단계 | 상한과 근거 |
|---|---|
| 설치/동일성·환경 preflight | 600초. 기존 `installation`의 현재 설치본 host pull 최대1, 필요 시 APK push 최대1(120초 timeout)·설치 최대1(120초 timeout), 원격/설치본 해시와 cleanup 포함. 동일 설치본이면 push/설치 생략. |
| 세션 stage/gate | 120초. 여섯 외부 입력 + manifest 총7파일 stage 1회, 현재 환경·설치본 재확인. |
| 앱·host 관측 | 485초. 앱 watchdog480초, host warmup 품질 승인과 시작 AP 1회 조회/승인, baseline30초, 공통120초, drain 최대30초, cooling60초 포함. 시작 AP arm 대기 최대30초; 실패 시 본 작업0·재시도0. |
| 회수·cleanup | 50초 + 45초. 원본 prefix/archive와 앱 cleanup·host force-stop·프로세스 부재를 구분. 실패 뒤 남은 예약을 회수/cleanup에 우선 사용. |
| 전체 | 위 설치600 + 세션(120+485+50+45)=**1,300초(21분40초) 상한**, 정상 예상시간/완주 보장 아님. 앱 runtime 최대4, warmup 최대8, 적격성 추론0, 본 작업 최대24, 명시적 추론 최대32. 추가·대체·재시도0. |

ADB hard cap **3,000명령**은 `ObservedDevice.command_limit`로 집행한다. 최대 poll485초의 250ms 간격 목록 조회는 이론상1,940회, 2초 thermal(3명령) 최대243×3=729회, 10초 screen 최대49회로 관측 루프 상한2,718회다. 설치/환경·staging(7×4+5=33)·warmup/AP 각 최대5·회수·cleanup·실패 prefix를 합친 나머지는 282명령 이내로 예약하며, poll은 cap 20명령 전에 중단해 회수·종료 슬롯을 남긴다. 실제 명령 수는 클라이언트 지연과 단계 조기 종료에 따라 달라지며, host 관측 주기와 전력 기여는 과거 동결 모형의 조건과 동일하다고 가정하지 않는다. 모든 `Check`는 APK와 외부 입력을 읽을 뿐 ADB를 호출하지 않는다.

PC 검증: 착수 HEAD `405b73f98b7bb730b0efabe96737e5ec448a546b`, 작업트리 clean·실제 원격 HEAD 동일. 기존 Kotlin 시작 AP gate/24요청 테스트4건은 직전 변경에서 통과했고 Android 소스는 이번에 변경하지 않았다. 이번 host 진입·예산 테스트7건과 기존 입력 회귀2건 통과(단일세션 실제 runner 진입의 preflight 실패 receipt 포함), 격리 `assembleModelProbe` 성공(63 tasks), `RUN_AFTER_APPROVAL.ps1 -Action Check`에서 계획 해시/소스/서명/입력/동결 SHA 대조와 `device_commands=0` 확인. 승인 없는 `Run`은 registry 생성 전 거절했다. PC 검증은 AP 센서 내부 갱신·실기기 설치/시작 지연·연결 안정성이나 예측 정확도를 입증하지 않는다.

재현(PC, 기기 명령0):

```powershell
python -B -m unittest tools.test_d1_arrival_ap_confirmation tools.test_d1_arrival_start_ap -q
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_arrival_confirm_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
```

나중에 **별도 승인과 현재 transport 확인을 받은 경우에만** 계획의 Run을 한 번 사용한다. 이번 턴에는 실행 승인·기기 조회·APK 전송·설치·실측이 없으며 `experiment_ready=false`를 유지한다. 현 단계의 완료는 *실행 가능한 단일세션 입력/게이트/예산의 PC 준비*다. 본 확인을 통과하더라도 병행 계수·짧은 개별 요청 비용·임의 부하 전체·열→시간 피드백·정책 간 절감 비교는 여전히 필요 범위 밖이다.
