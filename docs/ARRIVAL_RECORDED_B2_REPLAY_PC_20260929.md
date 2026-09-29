# 저장 B2 짧은 상태 전환의 단일 기기 재생 준비 — 2026-09-29

**판정: PC 준비 완료, 기기·설치본 미검증, 실행 미승인·미소비.** 이번 경로가 묻는 것은 *실제 일정과 관측 시작 AP가 주어졌을 때* 개발 3세션 동결 모형의 공통 120초 기기 전체 J와 AP 경로 오차다. 미래를 기록한 PC 배정의 기기 재생이며 온라인 B2, 예정 도착부터의 종단간 일정 예측, 정책 절감 실증이 아니다. 기존 strict 임의 도착은 계속 `UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS`다.

## 고정한 원본과 재생 의미

| 항목 | 고정값·근거 |
|---|---|
| 원본 | [요청별 저장 PC trace](results/arrival_visualization_01/timeline.csv) SHA `5bfd4f4e735f3af9400ff833fb2a473eac01b5d250c376d1e4a992fd172b7d75`; `explore/queue/B2_PC/seed201`, 예상·실현 간섭 모두 1.5. 이 1.5는 PC 일정 생성 조건이지 기기 설정이 아니다. |
| 교차검사 | [기존 점유 CSV](results/arrival_policy_screen_01/repro_bundle/occupancy_segments.csv) SHA `5aba75c95fb9750710400e7a8c411ef623f136ff42c99a248b68f2cbf65ec7e9`; 원본 24요청의 dispatch→lane-available로 재구성한 49구간이 저장 결과와 시각·상태별로 일치. |
| 선택 이유 | B2는 기존 계수가 있는 분류 GPU·탐지 CPU 단독/병행, resident idle을 120초 모두 거친다. 병행 CG_DC 2.531360211초, 탐지 CPU 단독 9.416370001초, 분류 GPU 단독 0.000900000초, idle 108.051369788초다. B3보다 적은 상태·전환으로 첫 짧은 병행 진단을 할 수 있다. 에너지 이득이나 오차에 따라 선택한 것이 아니다. CC_DG·DC_DG 및 반대 배정은 이번에 검사하지 않는다. |
| 요청 | 분류 긴급 6·탐지 일반 18, queue 도착 0–4.6초(200ms 간격), 요청별 연구 기한 1.5/6초, 공통창 120초. 4개 resident runtime(두 모델×CPU/GPU), 동일 canonical 입력 1개, CPU threads 1. |
| 동결 비용 | `energy_ap_state_run_v5/development_freeze.json` SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`, 기기 전체 W 및 AP 1차 상태식. 계수·시작 개발 범위 32.5–34.0°C 불변. |

[공유 소형 재생 입력](results/energy_ap_recorded_b2_01/source_schedule.json)은 원본 ID와 새 UUID, 예정 도착, 사전 고정 backend, 원본 dispatch 시각에서 얻은 **실행 허용 하한**을 같이 보존한다. 기존 Android arrival 계약의 24요청 의미를 유지한다. 이 실행 허용 시각은 PC 완료시각을 기기에 강요하지 않는다. 도착 전에는 enqueue하지 않고, 허용 시각 이후에도 lane이 busy면 실제 `lane_available` 뒤에만 배정한다. 허용된 여러 요청은 허용 시각→ordinal→원본 ID 순이고, 한 lane이 막혀도 다른 lane의 적격 요청은 처리한다. 앱 내부 예약 wake를 사용하며 요청별 ADB handshake는 없다. 새 모드는 `RECORDED_B2_REPLAY_V1`; 기존 `CPU_URGENT`/`FIXED_SPLIT`과 기존 P를 바꾸지 않았다.

앱은 예정 도착·실제 도착/queue 진입·release gate·dispatch·worker 진입·host inference 시작/반환·output_ready·persist·worker_release·lane_available를 별도 남긴다. 실제 호출 시간을 PC 길이에 맞추는 sleep, 완료 후 lane 점유 연장, 추가 추론은 없다. 공통 120초의 예정 요청 전체를 분모로 남기며, 이후 최대 30초 drain·60초 냉각과 cleanup은 공통창 J에 0으로 더하지 않고 별도 구간이다. 앱 timeout 480초 및 기존 환경·thermal 중단 규칙은 유지된다.

시작 전 warmup 8회와 resident baseline 30초 뒤 기존 HAL numeric AP 1회 승인 gate를 사용한다. 32.5–34.0°C, host 조회 시작→Android `common_start` 3초 이내를 앱에서 재검사한다. 승인 파일 쓰기 비용은 공통창 전이고, `common_start` 뒤의 app 승인 기록·scheduler·sampler 비용은 공통창에 포함된다. AP 센서 내부 갱신 시각은 알려져 있지 않다. 결측·범위 밖·기한 만료면 본 작업 0회로 종료한다. thermal status는 numeric AP의 대체값이 아니다.

## 판독과 종료 기준

[분석 계약](results/energy_ap_recorded_b2_01/analysis_contract.json)과 `tools.d1_arrival_recorded_replay_analysis`는 실제 lane 점유 구간→동결 기기 전체 W/AP 식, 그리고 허용된 초기 AP만으로 **조건부** 경로를 계산한다. 이후 실측 전류·AP는 오차의 대상일 뿐 예측 입력이 아니다. 실제 J는 기존 1Hz 전류/전압 적분, AP는 host numeric 표본을 같은 Android monotonic 120초 창에 정렬한다. 구간별 결측은 0이 아니며 상태 구간별 직접 관측 J는 구간이 센서보다 짧으면 `null`로 남긴다. 전체 관측 J는 전 구간이 적분 가능할 때만 보고한다.

| 결과 | 판정 |
|---|---|
| 시작 AP·품질·시간축·상태 매핑·회수 부적격 | 본 작업 0 또는 자료 부적격; 예측 오차 미판정. 부분 기록과 원래 실패를 보존. |
| 적격 120초 자료 | 원본↔실제 요청별 dispatch/완료/lane 해제 차이, 실제 병행 점유, 전체 J의 부호·절대·상대 오차, 누적 경로, AP MAE·최대절대오차·최고온도 오차를 **숫자로** 산출. |
| 오차 또는 상태별 잔차가 큼 | 해당 짧은 상태·전환의 전이 실패로 기록. 결과를 보고 동결 계수·시작 범위·PASS 기준을 고치지 않음. |

정확도 합격폭과 정책 차이 식별 기준은 근거가 없어 `null`이다. 한 세션은 반복 변동성, 임의 부하 전체, 반대 병행 방향, 온도에 따른 처리시간 변화, 배터리 잔량/사용시간, 정책 우열을 검증하지 못한다. 전류 raw=mA 해석은 A24 조건부이며 절대 J 정확도는 미인증이다. 새 APK의 timer·inference 경계 journal·기존 host 조회가 기기 전체 계측에 포함되므로 과거 개발/확인과 **프로토콜 전이**로 구분하고 보정값을 임의 차감하지 않는다.

## APK·단일세션 예산·재현

- 최종 프로젝트 서명 APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_recorded_b2_build_v2/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, 106,092,116 bytes, SHA-256 `2af45f685bcc4b0f25904907598cabf4f333e9b043980e4298d6304da6d5b544`; package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, 기존 프로젝트 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 격리 빌드 receipt는 같은 외부 `arrival_recorded_b2_build_v2/build_receipt.json`이며 APK·키는 저장소에 넣지 않았다.
- 새 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_plan_v3/collection_plan.json`, SHA-256 `52b0a21be884722b41a80b54ca0a874558a3a38aed3aeb85e89e247c7a830d5c`. 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, 단일 session ID·manifest SHA `87cd16d7…5c514c0`·소스/APK/동결 해시 고정. PowerShell `Check` 기기 명령 0회; 출력·registry 및 claim은 생성하지 않았다. 이 턴 중 만들어진 v1/v2 PC 초안은 소스 변경으로 Check 불일치이며 실행 대상이 아니다. 기존 queue24/FIXED_SPLIT 계획은 미승인·미소비 그대로다.
- 실제 실행 코드 산식: 요청24 + warmup8 + 적격성 추가0 = 명시적 추론 최대32, runtime4, staging 1회·7파일(이미지·anchors·두 모델·두 labels·manifest), 설치본 확인 host pull 최대1. 후보와 설치본이 다를 때만 APK push/데이터 보존 설치 각 최대1(각 timeout120초); 동일하면 생략. 재시도·대체·추가 세션0.
- 단일세션 최대 700초 = stage/환경 gate120 + app 관찰485 + 회수50 + cleanup45. 설치본 preflight·조건부 배포 최대600초, 최초 preflight부터 전체 최대1,300초. 고정 관측 baseline30 + 공통120 + 냉각60 = 210초; 30초 AP 대기·최대30초 drain·설정/warmup/품질/회수는 상한에 포함되지만 정상 예상시간 보장은 아니다. app watchdog480초. ADB 최대3,200명령: 485초 poll의 보수적 상한은 0.25초 listing 1,940 + 2초 thermal 삼중 조회 729 + 10초 screen 49 = 2,718; 나머지 482는 preflight·stage·gate·회수·cleanup 예약이며 poll은 cap-20에서 중단한다. 명령 수를 채우려 실행하지 않는다.

PC 재현/Check(ADB 0회):

```powershell
python -B -m unittest tools.test_d1_arrival_recorded_replay tools.test_d1_arrival_ap_confirmation -v
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
```

별도 실행 승인이 내려온 뒤에만 현재 transport·기기/설치본/환경 gate를 실행기가 확인하고 다음 명령을 **1회** 사용할 수 있다. 현재 승인은 이 명령을 실행할 권한이 아니다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<그때 확인한 transport>' -ExpectedPlanSha256 '52b0a21be884722b41a80b54ca0a874558a3a38aed3aeb85e89e247c7a830d5c'
```

향후 완료된 세션의 조건부 판독(새 분석 출력 경로; 실행 전에는 관측 결과 없음):

```powershell
python -B -m tools.d1_arrival_recorded_replay_analysis --session 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v3/00_5891be99-066e-503f-bbf6-474f095e9ce4' --frozen 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_state_run_v5/development_freeze.json' --output 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_analysis_v1'
```

공유 가능한 원본은 저장소의 [source_schedule.json](results/energy_ap_recorded_b2_01/source_schedule.json)과 [analysis_contract.json](results/energy_ap_recorded_b2_01/analysis_contract.json)이다. 외부 6 staging 파일·품질 reference·APK·동결 파일은 이 PC의 별도 경로가 필요하고 해당 SHA를 계획 Check가 검사한다. 다른 PC에서 동일 실기기 계획을 재현하려면 이 파일들의 정당한 별도 확보와 경로 대응이 필요하다. 그림/대시보드는 기존 [통합 화면](results/arrival_policy_screen_01/dashboard.html)의 재생 준비 구역을 따른다. **실측 그래프·오차는 아직 없다.**

검증 기록: 2026-09-29, 착수 HEAD `cde393e2a9e5797651ffb2045aa37387926467bc`와 이번 미커밋 변경. `python -B -m unittest tools.test_d1_arrival_recorded_replay tools.test_d1_arrival_ap_confirmation -v` 11건 통과, `:benchmark-runner:testModelProbeUnitTest --tests ...ArrivalRecordedReplayTest --tests ...ArrivalEnergyContractTest` 4건 통과/건너뜀0, 격리 `:benchmark-runner:assembleModelProbe` 성공, APK 서명·패키지·버전·SHA 확인, PowerShell `Check` 통과/기기 명령0. Python fake runner와 JVM 테스트는 실제 GPU delegate·온도 센서·기기 장시간 동작의 증거가 아니다. 원본·동결·FAIL·종료 계획 및 `experiment_ready=false`는 유지했다.
