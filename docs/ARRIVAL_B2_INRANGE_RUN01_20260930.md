# B2 기록 일정의 개발 시작 AP 범위 내 독립 확인 1회

2026-09-30, 출발 HEAD `286048e19e35d98b8288a9fb3dca36725b69d3f8`. 사용자는 새 계획 준비와 실측 진행, 기술 오류의 원인 수정 후 진행을 승인했다. 이번 실행은 `ENERGY-AP-RECORDED-B2-INRANGE-01`이며 이전 소비 계획을 재개하지 않는다. **실행 전 동결 기록**이며 결과는 아래에 추가한다.

기존 서명 APK `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180`의 기존 `numeric-ap-once-v1`을 선택한다. 32.5–34.0°C는 기기 안전 하한이 아닌 이번 확인의 개발 초기조건이다. ready 이후 HAL AP 조회 시작부터 실제 공통창 origin까지 ≤3초이며, 범위 밖·결측·지연은 본 작업을 시작하지 않는다. 추가 warmup/가열/온도 대기는 없다. 일반 환경 gate는 기존 BAT·비충전·thermal·화면·메모리·품질 계약을 유지한다.

## 입력·판독·예산

queue/seed201/B2_PC/원 PC 실현간섭1.5의 24요청과 backend·dispatch 허용시각을 그대로 재생한다. PC 간섭을 실제 감속으로 만들지 않는다. 기존 개발3 동결 SHA `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54`와 [사전 분석 계약](results/energy_ap_recorded_b2_01/analysis_contract.json)을 그대로 사용한다. **실제 일정과 최초 AP에 조건부인 전이 확인**이며 온라인 정책·종단간 예측 검증이 아니다. 이후 전류/AP는 비교 대상이며 예측 입력이 아니다. 짧은 전환은 이번 한 세션으로 strict 자동 승격하지 않고, 정확도 PASS·정책 우열은 미판정이다.

- 실행기 상한: 세션1, runtime4, warmup8, 본 요청24, 적격성 추론0, 총 명시적 추론32. staging1/7파일, 설치본 pull≤1, APK push/설치 각≤1(동일 설치본 생략).
- 실행기 시간: 설치/preflight600 + stage/gate120 + poll485 + 회수50 + cleanup45 = **1,300초**. baseline30·공통창120·냉각60과 앱 승인대기/배수는 poll 안에 포함하며 별도로 더하지 않는다. ADB≤3,200. 계획 내 재시도/대체/추가0.
- 현재 transport를 고르는 읽기 전용 `devices -l` 1회는 별도로 **15초·1명령** 예약한다. 따라서 이번 선택+실행 누적 상한은 **1,315초·3,201명령**이며 정상 예상시간이 아니다. 기기 식별·환경 조회는 실행기 내에서 수행한다. 계획 내 중단 후 같은 계획을 반복하지 않는다. 수리할 수 있는 코드 결함이 확인될 때만 PC 검증과 새 ID/예산을 먼저 남기며, 환경 부적격을 기준 완화로 해결하지 않는다.

## 동결·PC 확인

계획 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_inrange_plan_v1/collection_plan.json`, SHA `acaa4d0ba3fb5b712ea11d26f56a0dd862e4a2d00b8094128078c2e4faf285e4`. 출력은 `energy_ap_recorded_b2_inrange_run_v1`, registry는 별도 experiment ID다. 기존 builder/runner를 재사용하고 새 profile의 ID·기존 gate 선택만 분리했다. Android/APK/부하/계수 수정 없음. 관련 PC 테스트9건 통과: 새 ID·동일 입력/시간/호출, 원 v2 보존, v1 낮은 AP 거절, 실제 회수 parser·부분 기록·중복 cleanup 방지. PowerShell Check는 기기명령0으로 통과했고 서명/소스/계획/manifest/동결 byte와 미소비 경로를 확인했다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_inrange_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_inrange_plan_v1/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 선택한 transport>' -ExpectedPlanSha256 'acaa4d0ba3fb5b712ea11d26f56a0dd862e4a2d00b8094128078c2e4faf285e4'
```

## 실행 결과 — 초기조건 중단, 본 작업 0

**`stopped_no_resume`**. 현재 온라인 A24 transport 한 개를 선택했고 실행기가 동일 기기·fingerprint·프로젝트 서명·패키지·설치본을 검증했다. 설치본은 후보와 같아 APK push/설치0, 설치본 host pull1이었다. preflight 배터리68%·비충전·BAT29.9°C, thermal0이었으며 기존 화면·메모리 gate를 통과했다. runtime4·warmup8이 반환된 뒤 baseline을 거쳐 ready에 도달했지만, 시작 직전 HAL AP가 **30.0°C**, 조회 bracket **0.210초**, thermal0으로 확인돼 사전 연구 범위32.5–34.0°C에서 거절됐다. 이 하한은 안전조건이 아니므로 기기가 위험하거나 모형 예측이 실패했다는 뜻이 아니다.

host가 `start_ap.arm`을 쓰기 전에 예외가 발생했고, 회수된 progress95개 완전 레코드는 phase=`start_ap_gate`, runtime 시작/반환4/4, warmup8/8, request_start/output_ready/lane_available 각각0이다. 따라서 이번 본 작업0 판정은 기록 부재만을 근거로 하지 않고 **승인 신호 미전달과 본 작업 전 제어 경계**를 함께 사용한다. 공식120초 창·새 에너지/AP 오차는 없으며 그림을 만들지 않는다. 새로운 lifecycle_cancelled·ADB timeout/연결 소실은 관측하지 않았다.

| 항목 | 동결 상한 | 실제 |
|---|---:|---:|
| 세션 | 1 | 시도1·완료0 |
| runtime / warmup / 본 작업 / 명시적 추론 | 4 / 8 / 24 / 32 | 4 / 8 / 0 / 8 |
| staging / 파일 | 1 / 7 | 1 / 7 |
| 설치본 pull / APK push / 설치 | 각1 | 1 / 0 / 0 |
| 실행기 ADB + transport선택 | 3,200 + 1 | 231 + 1 = **232** |
| 실행기 + 선택 작업시간 | 1,300 + 15초 | 74.500 + 1.707 = **76.207초** |
| 같은 계획 재시도 / 대체 / 추가 | 0 / 0 / 0 | 0 / 0 / 0 |

시간은 두 작업의 활성시간 합이며 그 사이 PC 판독 공백은 포함하지 않는다. 선택과 실행 사이 공백까지 포함한 벽시각은 원본 명령/claim UTC로 재구성할 수 있다. 기존 timeout을 늘리지 않았다. client 비정상 exit3은 staging의 새 원격 경로 부재 검사이며 timeout0이다. 실패 후 일부 미생성 파일 회수는 JSON 검증 실패로 별도 남겼고, 원래 오류는 `start AP invalid; no arm, no retry`로 receipt에 보존됐다.

## 종료와 보존

원 실행 소유자가 대상 앱을 force-stop하고 프로세스 부재·thermal0을 확인했다. force-stop은 설치본 확인 이후1회와 세션 중단 후1회로 **서로 다른 단계**이며 같은 실패 정리의 중복 호출이 아니다. 앱 자체 `cleanup.json`은 종료 전에 회수되지 않았으므로 앱 정상 cleanup은 미확인이다. host cleanup은 completed, Python 실행 종료 및 원 host 프로세스 부재를 PC에서 확인했다. 앱 정상 완료로 표시하지 않는다.

- 원본: `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_inrange_run_v1/FINAL_RECEIPT.json`, SHA `f043f4bf285978f1fb0f5611c55b171c2c29faa1eba865fc727007077b387365`.
- PC 판독/원자료 inventory: `energy_ap_recorded_b2_inrange_readout_v1/summary.json`, `raw_inventory.json`. 회수된 원본은 수정하지 않았다. [공유 작은 요약](results/energy_ap_recorded_b2_01/inrange_v1/summary.json).
- PC 부분 자료 판독: `python -X utf8 -B -m tools.d1_arrival_recorded_replay_analysis --session '<원본/00_session>' --frozen '<기존 development_freeze.json>' --output '<새 빈 PC 경로>'`. 결과는 `not_evaluable`, J/AP 오차 null이다. 실행 후 Check는 소비 경로를 거절하므로 재실행할 수 없다.

**이번에는 수정할 실행 코드 결함이 확인되지 않았다.** 사용자의 실패 후 수리·진행 승인도 결과에 맞춘 초기조건 삭제, 임의 가열, 같은 gate 반복을 뜻하지 않는다. 따라서 성공할 때까지 반복 호출하지 않았다. 현재 자연 상태의 저온에서 자료를 얻으려면 새 저온 질문/모형 적용 범위를 정해야 하며, 기존 저온 진단을 다시 하는 것만으로 동결 모형의 범위 안 독립 확인이 되지는 않는다. **다음 PC 행동 하나:** 이번 정상 비충전 저온과 기존 저온3세션을 바탕으로, 저온에서 필요한 AP 예측 출력을 어디까지 제한할지 확정한다. 현재 계획·소비 기록은 종료하고 동결/원자료/FAIL/`experiment_ready=false`는 유지한다.
