# ENERGY-AP 세션 내부 ADB 의존성 축소: PC 준비 결과 (2026-09-28)

> 2026-09-28 후속: 승인된 DIAG-03 계획은 1회 소비되어 `stopped_no_resume`다. 연결 소실은 없었고 앱이 `probe.arm` 전 온도 준비에서 `lifecycle_cancelled`로 실패했다. 설치·적격성까지의 소비, 원본·회수·한계는 [실행 결과](ENERGY_AP_DEVICE_SEGMENT_DIAG03_RESULTS_20260928.md)를 따른다. 아래 미승인·미소비 표기는 실행 **이전** 준비 시점의 기록이다.

**판정:** opt-in `device-after-probe-diagnostic-v1`의 구현·PC 검증은 완료했다. 새 진단은 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`이며 기기 명령·설치·추론·실측은 0회다. CONFIRM-06의 연결 소실 원인, 새 APK의 실기기 동작, 동결 모형의 새 계측 프로토콜 전이 정확도는 확인하지 못했다. 기존 개발 3세션·동결 계수·DC_DG 확인과 CG_DC/CC_DG 미완료, `experiment_ready=false`는 유지한다.

## 실시간 의존성의 실제 경계

| 단계 | 앱 진행과 기록 | host 통신의 목적 | 실패 시 기존 동작 / 새 진단 |
|---|---|---|---|
| 입력·실행 시작 | manifest/APK·fingerprint 검증, 고유 session ID와 원본 출력 경로 생성 | 설치본·배터리·화면·AP·메모리 preflight, staging, 단 한 번 launch | 불일치 시 시작 금지. 같은 ID 출력이 있으면 덮어쓰지 않음 |
| runtime·warmup | 4 runtime, 8 warmup, 1 Hz 전류·전압·BAT·thermal·memory·screen 상태와 journal | `warmup.ready` 조회, 품질·두 GPU delegate 근거 확인 후 `warmup.arm` | 양쪽 모두 host 승인 필요. 불확실하면 앱 gate 제한으로 실패 |
| 기술 적격성 | serial/병행 probe 최대 4호출, lane·품질 기록 | `serial_probe`/`probe` 결과와 품질, host의 AP 준비 60초 창·thermal 0 확인 후 arm | host의 numeric AP 센서와 품질 판독은 앱에서 대체하지 않음 |
| 공식 baseline | 앱이 120초 단 한 번 수집하고 durable `baseline.ready` 작성 | 기존: 2초 AP, 10초 화면, 0.25초 완료목록, 간헐 heartbeat 조회; baseline AP 20표본·pair anchor 확인 후 `baseline.arm` | 기존: arm을 못 받으면 60초 뒤 실패. 새 진단: probe arm 뒤 앱이 `baseline.arm` 없이 다음 단계로 진행; host AP baseline은 사후 적격성 관측만 |
| 부하·완료 후 idle·냉각 | 600초 공통 부하/대기, 180초 냉각, sampler·호출 상한·watchdog, 정상 `summary`/`cleanup` | 진행 관찰, AP·화면 외부 관측, 종료 후 회수와 host cleanup | 새 진단도 앱 내부 gate 실패·초과시 중단. 연결이 끊기면 host는 상태 미확인으로 기록하며 재시작·자동 transport 교체·무조건 force-stop 금지 |
| 세션 사이 | 앱은 한 세션만 실행 | 개발 계수 동결·확인 분리 | 새 모드에 자동 6세션이나 동결/재보정 없음 |

`baseline.arm`은 단순 진행 신호가 아니다. 기존 정식 경로에서는 host가 한 번의 공식 baseline AP 표본 수·온도 anchor를 검사한 뒤 부하 시작을 허가했다. 앱은 같은 AP numeric sensor를 직접 읽지 못한다. 이를 생략하면 시작 적격성과 에너지 계측 경계가 바뀌므로 새 모드는 **진단 전용**이다. `probe.arm` 전까지의 GPU/품질·AP 준비·현재 기기 환경 gate는 유지한다. 앱은 배터리≥20%, 비충전, BAT≤35°C, thermal 0, interactive, memory를 기존 1 Hz sampler에서 확인하며 새 모드에서만 밝기 81·수동·화면꺼짐 18,000,000 ms를 함께 확인한다. host만 볼 수 있는 AP 값이 없으면 새 결과의 AP 적격성은 확인 불가다.

## 구현·종료·회수 계약

- `EnergySessionControl`은 기존 `host-gated-v1`을 기본으로 보존한다. 새 모드는 state-calibration·diagnostic manifest에서만 허용된다. 기존 runtime→warmup→probe→준비→baseline→부하→냉각·호출 상한·lane 해제 경계를 재사용한다. session manifest의 계획·APK·기기 fingerprint를 앱이 확인하고, 동일 출력 ID를 중복 생성하지 않는다.
- `probe.arm` 의도를 host가 먼저 durable 기록한다. 전송 결과가 모호하면 앱이 이미 진행 중일 수 있으므로 host 실패 receipt에는 원래 오류와 회수 오류를 나눠 남기고 force-stop을 보류한다. 앱 내부 정상 종료는 `summary.json`/`cleanup.json`, 실패는 `session_failure.json`/`cleanup.json` 등으로 구분한다. sampler 예외·journal overflow는 기존 실패 경로를 사용한다. 파일별 fsync/journal 약 1초 flush는 전원 상실의 완전 보존 보장이 아니다. 앱 watchdog은 native hang 또는 프로세스 전체 정지를 항상 해결하지 못한다.
- 별도 `recover-stopped`는 원래 plan hash·host run ID·PID **및 생성시각/명령**을 검사해 원 host가 종료됐을 때만 현재 A24를 다시 식별한다. remote manifest SHA와 완료/실패 `cleanup.json`을 확인한 경우에만 그 **동일 session ID**의 자료를 읽는다. 앱 상태가 미확인이면 성공으로 표시하지 않는다. 실행·arm·force-stop·설치·추론 호출은 없다. 단일 출력 경로로 중복 회수를 막는다. host가 잠시 보이지 않거나 heartbeat가 오래됐다는 이유만으로 활성 실행을 종료하지 않는다. PC 전원 상실·기기 연결 불가에서는 host가 종료 확인이나 회수를 보장할 수 없다.

## 계측 차이와 동결 모형

| 항목 | 기존 CONFIRM-06 | 새 진단 | 판정 |
|---|---|---|---|
| host AP/화면/listing/heartbeat | 2초/10초/0.25초/간헐 | 연결 중 동일 주기, 연결 소실 뒤 없음 | ADB 기기 전체 소비의 변화량 미계측. 0으로 보정하지 않음 |
| 앱 센서·기록 | 1 Hz sampler, journal 약 1초 flush | 동일 + screen settings 3회/표본, continuation checkpoint | 새 앱 기록 비용은 미계측 |
| runtime·warmup·resident·부하 | 4/8, 같은 CG_DC blocks·250ms·상한 | 동일 코드와 작업 구성 | 부하 의미는 유지하나 설치 APK 계보 변경 |
| 상태 전환·baseline | host가 probe와 baseline 양쪽 arm, AP baseline 후 부하 | probe는 host arm, baseline은 앱 자체 진행; host AP는 사후 관측 | 시작시각·AP 적격성·조회 부하가 다름 |
| 환경·품질 gate | host AP/화면/GPU/품질 + 앱 sampler | 준비 시 동일, 진행 중 앱 sampler·추가 screen settings; host AP 손실 가능 | AP 결측은 적격 통과 아님 |

기존 개발 계수와 DC_DG 확인은 그대로 재사용하여 **전이 진단의 사전 고정 예측값**을 계산할 수 있다. 그 값을 새 결과로 재보정하거나 기존 확인 block에 합치지 않는다. host AP가 끝까지 있으면 새 계측 경로의 AP/에너지 차이를 기술할 수 있지만, 이는 프로토콜 변경에 대한 전이 확인이다. 연결 소실로 AP가 없으면 AP 경로 오차를 계산할 수 없다. 정상적인 정식 확인의 CG_DC/CC_DG는 여전히 미완료다. raw 전류=mA 가설과 절대 J 정확도 미인증도 유지한다.

## 별도 최소 후속 실행 후보

설치 APK는 새 계보 SHA-256 `7589b96f18076c4bf7d178f3ae58c45c4e88348ef7f797ec5de60699d2e9c00d`, 동일 프로젝트 서명이다. 기존 기기에 설치된 `b273f74…a114cf`와 달라 **실행 전 설치 확인/필요시 push·install 각각 최대 1회**가 필요하다. 기기 동일성·fingerprint·현재 비충전/배터리/온도/thermal/화면/memory·GPU/품질 gate는 실행 시 재확인해야 한다. 이번에 설치하거나 조회하지 않았다.

- ID `ENERGY-AP-DEVICE-SEGMENT-DIAG-03`, 계획·해시·재현 경로는 [공유 안내](results/energy_ap_device_segment_01/README.md)에 기재. SHA-256 `5ec12e31b90a17f6f56fdd38d077f0b244e4a19c2bf2ba99635343570ca09068`. 이전 PC 초안 DIAG-01/02는 미소비이며 보존한다.
- **진단 1세션 CG_DC**: runtime≤4, warmup≤8, 적격성≤4, 작업≤1,680, 명시적 추론≤1,692, staging≤1회/7파일, host pull≤1, APK push/install 각≤1, 재시도·대체·추가0. baseline120+공통부하600+냉각180 및 준비 쪽 고정120 = 고정 관측1,020초, resident 준비 최대360초. 세션≤2,100초, 사전설치/확인≤600초, 전체≤2,700초. ADB≤11,000(회수/cleanup 전≤10,900), 보수적 정상 poll·gate 상계10,361. 0.25초 목록, 2초 AP triple, 10초 화면, 간헐 heartbeat를 임의로 삭제하지 않았다. 이 한도는 정상 소요시간/완주 보장이 아니다.
- 성공: host 준비 기록, 앱의 단일 공식 baseline→부하→냉각→정상 `cleanup`, 실제 lane·호출 상한, host 회수와 AP 관측 적격성 구분. 연결 소실 시 같은 세션 결과가 앱에서 완료될 수 있어도 host 관측 누락이면 모형 정확도 PASS가 아니다. 별도 read-only 회수는 원 host 종료 확인 후 **새 승인** 하에 최대90초·ADB12명령, 추론0이다.
- 최소 실행 확인 명령(PC 전용): `& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check`. 현재 계획은 미승인·미소비다. 별도 승인 후에만 `-Action Run -Approved`를 사용한다. 원본 출력·registry는 아직 생성하지 않았다.

PC 검증: 좁은 Kotlin 단위 테스트와 `assembleModelProbe` 프로젝트 서명 빌드, Python 진입/진단 4건과 기존 경계 테스트를 수행했다. fake ADB에서 정상 단일 세션, arm 전달 뒤 연결 실패 시 원래 오류/강제종료 보류, baseline arm 미전송, host 활성 시 회수 금지와 동일 세션 terminal 회수를 확인했다. `Check`는 기기 명령 0회다. 이 결과는 Android 실기기 안정성·정상 AP 계측·연결 소실 후 물리적 계속 실행을 증명하지 않는다.
