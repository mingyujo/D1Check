# B2 기록 일정의 시작 AP 관측 진단 v2 — PC 준비

**판정:** 32.5–34.0°C는 A24 동결 모형 개발 3세션의 **시작 AP 관측 범위**다. 수식의 정의역이나 기기 안전 하한으로 제시된 근거는 없다. 기존 `numeric-ap-once-v1`과 소비된 plan_v3·v4의 중단 결과는 그대로 둔다. 별도 `numeric-ap-observe-v2`는 기존 환경·앱 gate가 통과하고 시작 직전 HAL numeric AP가 유효하고 신선하면 관측을 시작할 수 있다. AP 28.8°C 자체의 안전성을 새로 인증한 결정은 아니다. 이번 턴은 PC 준비뿐이며 기기 실행·새 예측 오차는 없다.

## 근거와 판정 분리

| 구분 | 동결 근거와 코드 | 새 진단 판정 |
|---|---|---|
| 실행 적격성 | `d1_energy_collection_device.gates`, 앱 `ArrivalEnergyActivity.snapshot`, warmup 품질, 서명·기기 동일성 | 배터리 ≥20%, 비충전, BAT ≤35.0°C, thermal status 0, 화면·메모리·품질 및 설치본 gate 유지. 시작 직전 `dumpsys thermalservice`의 HAL type 0 AP는 finite, ready 이후 bracket, bracket ≤3초, 읽기 시작→실제 공통창 origin ≤3초. 미확인·지연이면 arm 없음 또는 본 작업 0회. 센서 내부 갱신 시각까지 증명하지는 않음. |
| 모형 초기조건 | 동결 `development_freeze.json` SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`: 시작 AP 32.5–34.0°C, 관측 경로 32.5–39.5°C | 시작값 안/밖 및 관측·예측 경로 밖을 각각 표시. 개발 범위 밖 계산은 `extrapolation_diagnostic`, strict 지원 아님. 범위 안이어도 짧은 임의 상태 전환은 strict 미지원. |
| 관측 자료 적격성 | 24개 요청·실제 lane release, 공통 120초 전류·전압·AP | 누락·미완료·미지원 구간을 0으로 채우지 않음. 전체창 적격 여부는 실행 후 별도 판정. |

[이전 1회 중단](ARRIVAL_RECORDED_B2_REPLAY_RUN02_20260929.md)은 ready 후 AP 조회 28.8°C, bracket 0.190초·thermal 0이었으나 **당시 계약의 개발 범위 gate**에서 arm이 거절된 사례다. 런타임 4·warmup 8 반환 후 본 작업 0, 공식창 미진입이며 동결 모형 예측 실패가 아니다. 같은 결과를 새 프로토콜의 완료 표본으로 소급하지 않는다.

## 이번 단일 세션이 추가하는 근거

원본 `queue/seed201/B2_PC/realized1.5`의 24요청·backend·기록 dispatch 허용 하한·120초 공통창을 변경하지 않는다. 실제 처리시간과 lane 점유를 PC 값에 맞추지 않는다. 유효 자료가 회수되면 실제 짧은 단독↔CG_DC 병행↔유휴 전환, 전체창 기기 전력 적분과 AP 경로를 기술하고, 실제 일정·**관측 초기 AP만** 동결식 입력에 사용한다. 이후 전류·AP는 예측 입력이 아니라 비교 대상이다. 전력 계수는 각 상태의 기기 **전체** 전력이며 idle을 재가산하지 않는다. 시작 AP가 개발 범위 밖이면 에너지·AP 각각의 수치 계산 가능성과 경험적 지원 여부를 별도 표시한다. 계수가 없거나 상태가 매핑되지 않으면 예측 `null`; 가능하면 외삽 진단으로만 오차를 산출한다. AP 곡선 평행 이동·동결 계수 보정·정확도 PASS·strict 범위 확대는 하지 않는다.

이번 세션은 온라인 B2, 예정 도착부터의 종단간 일정 예측, 개별 요청 J, 모든 온도, 열 회복 정책의 우월성 또는 절대 에너지 정확도를 검증하지 않는다. 새 프로토콜과 APK의 관측 비용은 미측정이므로 이전 세션과 하나의 동일 프로토콜 확인 block으로 합치지 않는다. 기존 전류 raw=mA 해석도 조건부다. 종료 기준은 **실행 gate 통과/중단**, **관측 전체창 적격/부분**, **에너지 및 AP 계산 가능/외삽/지원 안**, **실제 병행 유무**를 각각 보고하는 것이다. 결과를 보고 합격선을 만들지 않는다.

## 구현·시간·예산

- 앱은 `start_ap_gate=numeric-ap-observe-v2`를 B2 기록 재생에만 허용한다. 기존 v1의 32.5–34.0°C 거절은 유지한다. 새 모드에서도 동일 manifest hash·앱 monotonic ready/start·30초 승인 대기·3초 신선도·thermal 0을 검사하고 `start_ap.accepted.json`에 모드와 개발 범위 판정을 남긴다. host와 Android monotonic 시각을 서로 직접 빼지 않으며 앱의 ready/조회/start와 host 제출 시각을 각 시계별로 기록한다.
- 기존 배포·stage·warmup gate·poll·회수·cleanup을 재사용한다. AP 조회는 baseline 뒤 기존 한 번뿐이며 낮은 값을 맞추는 가열·반복 대기·추가 warmup은 없다. 공통창은 승인 뒤 시작하므로 조회 지연은 120초 에너지/J 창 밖이지만 준비열·초기 AP에 영향을 줄 수 있어 읽기→시작 지연을 기록한다.
- 최대 1세션, runtime 4, warmup 8, 작업 24, 적격성 추론 0, **총 명시적 추론 32**. staging 1회·7파일, 설치본 host pull≤1, APK push≤1·설치≤1. 설치/preflight 600초 + stage/gate 120초 + poll 485초 + 회수 50초 + cleanup 45초 = **전체 1,300초**, 단일 세션 700초. ADB **3,200명령** 상한은 기존 한 세션의 0.25초 listing 최대1,940, 2초 thermal 최대약243, 10초 화면 최대49 및 preflight·stage·회수·cleanup 예약을 포함하며 새 진단에서 추가 조회는 없다. 재시도·대체·추가 세션 0. 이는 정상 소요시간이나 기기 완주 보장이 아니다.

## PC 검증·계획

- Python host gate·실제 poll·검증·동결식 경계 관련 13건 PASS. Android `ArrivalStartApGateTest`와 기존 `ArrivalEnergyContractTest` 대상 JVM 테스트 PASS. 이들은 실제 HAL 신선도·GPU·장시간 동작의 실기기 검증은 아니다.
- 프로젝트 서명 APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_b2_ap_observe_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, SHA-256 `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180`. `build_receipt.json`에 소스별 SHA와 빌드 명령을 보존했다. APK 검사에서 패키지 `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, 프로젝트 서명 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`를 확인했다. Android 소스 변경 때문에 구 설치 APK SHA `120ee894…1d50f5`와 구 프로토콜 자료는 구분한다. APK·키·모델은 저장소에 넣지 않는다.
- 새 미승인 계획 경로: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_plan_v6/collection_plan.json`, SHA-256 `38c9eb2fc403ec7d849bd1f31d067e3ef2742f81801fe4c34eb7ec1f8ce00ced`. PowerShell `Check`는 소스·계획·manifest·서명·APK·입력·동결 파일·예산을 확인했고 `device_commands=0`이다. 실행 출력·registry claim은 만들지 않았다. 현재 기기·설치본·환경은 **미검증**이다. 기존 계획은 재개하지 않는다. AP 경로 지원 표시 보완 전 만들어진 plan_v5는 미소비·미승인 PC 초안이며 현재 코드 Check가 불일치하므로 실행 대상이 아니다.

승인 후에만 실행할 명령(이번에는 **Run 금지**):

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_plan_v6/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_diag_plan_v6/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport>' -ExpectedPlanSha256 '38c9eb2fc403ec7d849bd1f31d067e3ef2742f81801fe4c34eb7ec1f8ce00ced'
```

완료 기록: PC 준비와 Check 완료, **실행 승인 아님**. 착수 HEAD `76bb7e7988e65ffeb0e4511e4d752befce2fc23d`, 당시 작업 트리 clean. 이번 변경의 Python 13건/JVM 대상 테스트 PASS, `git diff --check` PASS. 새 plan·run·registry를 구분했고 기기 명령 0. 판독 계약은 [JSON](results/energy_ap_recorded_b2_01/diagnostic_analysis_contract_v2.json), 저장 일정은 [원본 번들](results/energy_ap_recorded_b2_01/source_schedule.json)이다. 동결 모형과 기존 원자료·FAIL·`experiment_ready=false`는 불변이다.
