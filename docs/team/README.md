# D1Check 팀 안내 — 2026-09-30 최신 체크포인트

읽을 브랜치는 **`feature/arrival-scheduling-20260923`**이다. 본 안내는 결과·계약·코드의 공유 위치이며 기기 실행 승인을 부여하지 않는다. 현재 연구 상태는 **`experiment_ready=false`**다. 아래 접힌 이력의 “현재/최신/다음”은 당시 상태이며 이 첫 화면과 [STATUS](../PROJECT_STATUS.md)의 최신 절을 우선한다.

## 먼저 읽을 자료

1. [현재 연구 결과·논의 초안](../ENERGY_AP_RESULTS_DISCUSSION_DRAFT_20260930.md): 확보한 근거와 주장 가능한 범위를 한 번에 읽는다.
2. [에너지·AP 통합 결과 화면](../results/ap_simulation_closure_01/readout/index.html): 저장소를 내려받아 HTML을 브라우저에서 열면 기존 관측·모형·지원 범위를 볼 수 있다. GitHub 파일 화면 자체는 대시보드를 실행하지 않는다.
3. [응답·완료 정책 비교](../ARRIVAL_SERVICE_CHOICE_PC_20260930.md) 및 [입력별 서비스 선별](../results/arrival_service_guard_01/README.md): PC 일정의 응답 결과와 미지원 J/AP를 구분한다.
4. [미실행 CG_DC 전이 확인 계획의 목적·예산·명령](../AP_CGDC_TRANSFER_PREP_20260930.md), [공유 입력·분석 계약·PC 검증](../results/energy_ap_cgdc_transfer_01/README.md): 다음 한 세션이 확인하는 질문과 종료 기준이다.

## 지금까지 완료한 것과 남은 것

| 작업 | 확보한 결과 | 해석과 근거 |
|---|---|---|
| A24 두 작업·CPU/GPU 요청 계측 | adapter·출력/품질·도착/resident·실제 lane 경계 구현 및 실측. 기존 독립 평가의 주 결합 FAIL과 fixed-split 부분 종료 보존 | [모델 inventory](../MODEL_02_INVENTORY.md), [기존 평가](../ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md), [부분 결과](../ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md) |
| 고정 CC_DG 직렬·병행4세션 | 같은870건에서 병행이 빠르고 AP가 높음. 공통480초 에너지 차이 방향은 개발과 확인에서 뒤집힘 | [실측 상충·제한 모형](../ENERGY_OPERATIONAL_DECISION_PC_20260926.md). 온라인 정책의 절감 입증은 아님 |
| 상태별 개발3→동결→DC_DG 확인1 | 전력/AP 식과 개발·확인 자료 연결 보존. CG_DC·CC_DG의 원래 동일조건 확인은 미완료 | [COLLECT-05 결과](../ENERGY_AP_STATE_COLLECT05_RESULTS_20260928.md). 중단 계획은 재개하지 않음 |
| 다른 프로토콜의 CG_DC 진단 | 실제 lane/센서와 동결식의 전이 오차 확보 | [DIAG-04 전이 분석](../ENERGY_AP_REGIMEN_TRANSFER_PC_20260929.md). 원래 확인 block과 합치지 않음 |
| B2의24요청 기록 일정 재생 | 공통120초·실제 CG_DC1.683초. 관측154.696J 대 동결식155.758J(+1.062J), AP MAE3.555°C | [에너지 상쇄·AP 형태·사후 후보](../ARRIVAL_RECORDED_B2_RESIDUAL_MODEL_PC_20260929.md). 시작 AP29.9°C/짧은 전환은 외삽 진단 |
| 유휴 AP 반응 개발1→절차 동결→확인1 | 부하 전 AP 조건부 후보의 확인 MAE0.418°C(원래식5.461°C). 확인 유휴에서 상승→하강 형태 한계도 남음 | [실행·확인](../ENERGY_AP_IDLE_RESPONSE_RUN01_20260929.md), [현재 출력 제한](../AP_SIMULATION_CLOSURE_PC_20260930.md). AP 최고/한도·정책 순위 지원으로 확대하지 않음 |
| 저장 low/queue/burst 정책135사례 | 응답·완료와 연구용 선별 규칙 판독. B2 적격21/45·B3 적격22/45·둘 다7/45 | [서비스 결과](../ARRIVAL_SERVICE_CHOICE_PC_20260930.md). 독립 기기135세션이 아니며 동적 전체창 J/AP 지원0 |
| 실행·종료·회수·관측 보완 | host 소유권/checkpoint·단일 cleanup, Activity lifecycle 기록, 앱 세션 내부 진행, 실행 적격성과 AP 모형 범위 분리 | [host 계약](../ENERGY_AP_HOST_LIFECYCLE_PC_20260928.md), [기기 내부 세션](../ENERGY_AP_DEVICE_SEGMENT_PC_20260928.md), [lifecycle PC 검토](../ARRIVAL_RECORDED_B2_LIFECYCLE_PC_20260929.md). 과거 host/onDestroy 외부 원인은 미확정 |
| PC 시뮬레이터·판독·보고 | 고정 묶음 회고 비교, 제한된 조건부 AP, 미지원 비용/순위 null 차단, CSV/그림/HTML 판독 자동화, 결과·논의 본문 | [지원 경계](../AP_SIMULATION_CLOSURE_PC_20260930.md), [판독 자동화](../AP_CGDC_TRANSFER_PREP_20260930.md#실측-후-pc-판독과-그림-자동화-2026-09-30). PC 통과와 실기기 예측 확인은 별개 |

실측 전류 raw=mA 해석은 조건부이며 절대 에너지 정확도는 미인증이다. AP를 BAT·표면온도·SOC·사용 가능 시간으로 바꾸어 표현하지 않는다. 기존 FAIL·원자료·동결 계수·소비된 종료 계획을 보존한다. 무선 디버깅 스위치 OFF→ON이라는 사용자 관측과 실행 로그는 별도 근거이며, 로그상 단절 미관측을 스위치 유지의 증거로 해석하지 않는다. 원인 미확정과 구현·기록 개선은 구분한다.

## 현재 준비된 실측과 팀원 담당 경계

| 대상 | 현재 해야 할 일 | 실행 상태 |
|---|---|---|
| A24 | 기존 후보/동결 W를 다른 짧은 CG_DC 일정에 적용하는 **전이 확인1**. 저장 burst/201/B2의 원래 도착을 유지하고 release만+35초 | `ENERGY-AP-CGDC-TRANSFER-02`/plan_v2, **미승인·미소비**. 담당자 PC의 실행 묶음·현재 기기 gate·승인이 필요 |
| S26 CPU/GPU | 이미 보유한 두 모델의 기기·runtime·품질·요청·센서 근거를 먼저 제출. 그 근거를 보고 기기별 지원/실측 공백을 판단 | 공통 [다기기 계약](../MULTITASK_EXPERIMENT_PROTOCOL.md)은 있으나 최신 S26 두 모델의 확정 실행 계획/예산은 이 브랜치에 없음 |
| S26 NPU | 별도 npu-runner/CompiledModel 소스·변환/실행 장치·대표 입력 품질을 먼저 제출 | MobileNet 보고나 과거 합성32입력을 EfficientNet/EfficientDet NPU 검증으로 전용하지 않음. A24 준비 계획을 S26에 실행하지 않음 |

A24 권고 계획의 상한은 **확인1·runtime4·warmup8·본작업24·명시적추론32·staging1/7파일·설치본pull≤1·선택적APK push/설치 각≤1·전체1,300초·ADB≤3,200·재시도/대체/추가0**이다. 정상 소요시간이나 배터리 완주 보장이 아니다. 계수 재적합·기본/strict 지원 확대·온라인 B2 정책 검증은 포함하지 않는다. 이 한 세션이 성공해도 DC_DG 짧은 전이·AP 최고/한도·정책 간 J/AP 차이 판별은 미완료다.

기기 실행 전에는 현재 동일 A24·유일 transport·설치본/서명·환경·품질·memory gate를 계약대로 확인한다. 중복 연결을 자동 해제하거나 연결 소실 후 다른 transport로 전환하지 않는다. 개발 시작 AP32.5–34.0°C는 모형 범위 표시이며 numeric-ap-observe-v2의 별도 실행 하한으로 적용하지 않는다. 유효 AP/신선도 및 기존 BAT/thermal/비충전 등 실행 조건은 유지한다. 과거 계획/plan_v1 초안/queue24를 현재 실행 대상으로 사용하지 않는다.

## GitHub에 있는 것과 별도 확보할 것

| 항목 | 확보 경로 |
|---|---|
| 코드·테스트·문서·작은 CSV/그림·결과·분석 계약 | 이 작업 브랜치. 최신 수정본의 검사 버전은 각 보고서/verification JSON에 있음 |
| 다음 입력 | [schedule.json](../results/energy_ap_cgdc_transfer_01/schedule.json), [analysis_contract.json](../results/energy_ap_cgdc_transfer_01/analysis_contract.json). 미래 입력이며 새 실측 결과가 아님 |
| 동결된 실제 실행 묶음 | 담당자 PC의 `energy_ap_cgdc_transfer_plan_v2/collection_plan.json`·`manifests/`·`RUN_AFTER_APPROVAL.ps1`. GitHub에는 생성/검사 코드와 계약이 있고 실제 로컬 묶음은 없음 |
| 서명 APK·빌드 receipt·검증 도구 | 담당자 PC에 보존. 서명 키/비밀번호를 공유 저장소에 넣지 않음. 개인 debug 키로 대체해 같은 APK라고 하지 않음 |
| 원래 개발3 freeze·유휴 후보 절차 freeze | 담당자 PC의 `energy_ap_state_run_v5/development_freeze.json`, `energy_ap_idle_response_run_v1/ap_model_freeze.json`. GitHub에 휴대용 일부 진단 입력은 있지만 현재 실제 Check에 필요한 전체 외부 파일은 별도 |
| 모델/입력6파일·참조 출력4파일 | 정확한 경로·SHA는 실제 계획의 source_files/references에 있음. 모델은 고정된 출처에서 실행자가 확보. EfficientDet exact binary의 배포 권한 미확인 경계를 유지 |
| 대용량 원자료·receipt·상세 client 기록 | 담당자가 원본 보존. 공유 가능한 파일 목록/체크섬을 먼저 정하고 별도 전달. 기존 문서의 `C:/Users/LG/Documents/...`는 팀원 PC나 GitHub에서 열리는 주소가 아님 |

현재 준비본의 동일성:

| 대상 | SHA-256 |
|---|---|
| 계획v2 | `e18268538174f49e98789dcf191318dbf5b57cdbc2a7f2cb1b4aaa4c449f3234` |
| 재사용 APK | `747ce77e07c7c79f7c7d912d0ff749cf230e0c0483f4a160784fe549043f6180` |
| 원래 개발3 모형 | `35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54` |
| 유휴 후보 절차 freeze | `8507adc10485940c36853786ba39a4f42439a9fbd3d71a5da1c7d55e2cbc7ec5` |

위 식별값만으로 설치/실측이 승인되는 것은 아니다. 다른 PC로 옮긴 경로·서명·파일 대응과 Check를 다시 확인해야 한다. 소비 registry를 복사해 초기화하거나 종료 계획을 재개하지 않는다.

## S26/NPU 담당자가 먼저 제공할 최소 자료

- 최신 branch/commit·모듈/variant·재현 명령·runtime/compiler 버전. 정확한 기기/SoC·fingerprint는 민감정보를 제거한 전달 방식으로 제공한다.
- exact 모델/입력·원본/AOT SHA·출처·정밀도·변환 옵션·전후처리와 대표 입력의 사전 품질 계약. 두 모델별 위임·partition·CPU 잔여/fallback·실행 장치 근거를 구분한다.
- session manifest·전체 시도/실패/미지원 분모·runtime/resident/warmup·환경/memory/thermal 조건·원본 receipt/체크섬.
- 요청 dispatch/execution/output/persist/worker_release/lane_available 및 monotonic 기준 전류·전압·AP 원문. 개발/확인/이미 본 자료의 역할을 명시한다.

이미 자료가 있으면 먼저 재사용한다. 자료 접근 부족을 곧바로 추가 실측 필요로 판정하지 않는다. S26 에너지·온도·스로틀 계수를 A24에 적용하지 않으며, 개별 NPU 실행 지원만으로3건 병행이나3자원 정책 완료를 허용하지 않는다. 과거 [S26 MobileNet 요약](../ENERGY_THERMAL_PC_01_20260925.md)은 방법 참고이며 현재 두 모델/NPU의 근거가 아니다.

## 팀원에게 전달할 요약

> 최신 진행 상황은 `feature/arrival-scheduling-20260923`의 `docs/team/README.md`에 정리했습니다. A24 고정 실측·B2 재생·유휴 AP 후보 확인·저장 정책 서비스 비교·판독 자동화·결과 초안까지 반영돼 있습니다. 동적 정책의 에너지/열 우월성은 아직 미입증입니다. 다음 A24 CG_DC 전이 확인1은 PC 준비만 완료했고 미승인·미소비입니다. 실행에는 별도 로컬 APK/계획/모형/입력 묶음과 현재 gate 확인이 필요합니다. S26/NPU 담당자는 보유한 두 모델의 소스/장치·품질·요청·센서 원본 근거를 위 목록대로 먼저 제출해 주세요.

<details>
<summary>2026-09-26 이전 안내·협업 이력 (현재 실행 지시가 아님)</summary>

## 이전 팀 안내 — 2026-09-26 당시 상태

> **PC 결과 시각화:** 작업 브랜치에서 [오프라인 HTML 대시보드](../results/arrival_visualization_01/dashboard.html)와 [그림·CSV·재현 안내](../results/arrival_visualization_01/README.md)를 열 수 있다. low/queue/burst의 응답은 합성 PC 탐색이고, 에너지·AP는 도착 상태별 계수 미측정으로 `계산 불가`다. 별도 고정870건 참고 그래프를 합성 도착 정책의 에너지 결과로 읽지 않는다. Android 합성 도착 수집은 아직 미실행이다.

> **현재 우선:** 작업 브랜치 `feature/arrival-scheduling-20260923`에서 [STATUS](../PROJECT_STATUS.md) → [합성 도착 Android 수집 후보](../ARRIVAL_ENERGY_ANDROID_PREP_20260926.md) → [검증·명령](../results/arrival_energy_android_prep_01/README.md) 순으로 읽는다. CPU 긴급우선/고정 분리의 24요청×3조건 재생·기기 전체 전류/AP 계측을 PC 준비했으나 기기 실행과 에너지 절감 검증은 하지 않았다. 목적 B의 상태별 모형·강한 B2 비교도 미완료다. 기존 FAIL·부분 결과·`experiment_ready=false`와 별도 S26/NPU 협업을 유지한다. 아래의 “현재/최신” 문구는 각 당시 이력이다. 외부 계획/APK/원본은 로컬 PC 전용으로 GitHub 링크가 아니다.

> 현재: [반복 온도 중단 검토와4세션 운영 후보](../ENERGY_DESIGN_REVIEW_20260926.md)를 먼저 읽는다. sampler 직렬 진단은 성공했으나 COLLECT-04/05는 온도 gate에서 종료돼 긴 병행 효과는 미판정이다. 새 동일 기술준비·고정노출·AB/BA 운영 경로와 에너지 ledger를 PC 검증하고 실행 후보만 준비했다. 실측0, 실행 미승인, 동일 초기 열 상태/절감 PASS 아님. 필수 발열·배터리 목표·S26/NPU 별도 협업·experiment_ready=false 유지. 아래의 “최신/현재” 문구는 각 날짜의 이력이다.

> 최신 PC 수정: [sampler snapshot 결함 재현·보완](../ENERGY_SAMPLER_PC_20260925.md). 과거 발생 행은 stack 부재로 미확정이지만 실제 toMap 경쟁을 재현해 수정했다. 새 APK·진단1세션(880추론/35분 상한) 후보만 준비, 기기 실행0·별도 승인 필요. 기존 FAIL/부분 기록/experiment_ready=false와 S26/NPU 별도 협업 유지.

> 최신 결과: [COLLECT-03 sampler 예외 중단](../ENERGY_THERMAL_COLLECT03_RESULTS_20260925.md). 설치0·개발1시도0완료·동결/확인 없음. 화면23조회 성공이지만 수집은 미완료이며 다음은 PC snapshot 경쟁/예외 기록 검토다. 종료계획 재개 금지·experiment_ready=false 유지.

> 최신 PC 준비: [새 에너지 직렬/병행 COLLECT-03](../ENERGY_THERMAL_COLLECTION_REPREP_20260925.md). 실제 수집 gate 원문 재생·새 plan_v5/서명/Check 완료, 실행은 별도 승인 대기다. 무추론 화면32조회 성공은 부하 안정성 증거가 아니다. 옛 중단자료 제외, 새 개발/확인 모두 같은 관측 방식. ADB/실측0·experiment_ready=false·S26/NPU 별도 협업 유지. 아래는 당시 상태 기록이다.

> 최신 실행: [에너지·열 수집 첫 세션 중단](../ENERGY_THERMAL_COLLECTION_EXECUTION_20260925.md). 설치 성공 후 화면 상태 조회timeout으로8세션 중1시도/0완료, host cleanup 확인. 동결·확인 미실행, 종료계획 재개 금지. 아래 준비 당시 승인대기/실행0 문구는 과거 상태이며 현재는 PC 원인 검토 단계다. S26/NPU 별도 협업은 유지한다.

## 최신 우선 안내: ENERGY-THERMAL-COLLECTION-PREP-02

작업 브랜치 **`feature/arrival-scheduling-20260923`**에서 [STATUS](../PROJECT_STATUS.md) → [두 병행 조합 수집 계약](../ENERGY_THERMAL_COLLECTION_PREP_02_20260925.md) → [준비 파일·명령·검증](../results/energy_thermal_collection_prep_02/README.md) → [PLAN](../PROJECT_PLAN.md)·[DECISIONS](../DECISIONS.md)를 읽는다. master가 아니다.

- **발열·배터리 최적화는 필수 목표**다. 기존 MobileNet 에너지·열 PC 보정은 완료했고, 현재 두 모델의 실제 직렬/병행 동일 작업량 수집 경로를 새로 준비했다. 독립 개발4/확인4, 진단6976/warmup64, 상한220분은 새 승인 대기이며 **기기 실행0**이다.
- Kotlin6/Python17·관련 APK/서명/PC dry-run 완료와 실기기 미검증을 구분한다. 기기 gate·분류GPU+탐지CPU 병행 적격성·현재 두 모델의 에너지/열 정확도 및 절감은 아직 미확인이다. 일시정지 Android 연결/P 튜닝은 보류한다.
- S26/NPU 기존 별도 협업·모델별 실행/품질 근거 요구를 유지한다. 계수를 A24로 전용하지 않는다. 기존 FAIL·부분 결과·40값/20null·experiment_ready=false는 유지한다.
- 외부 원본/계획/APK/상세 보고서 `Documents/D1Check_Arrival_Extension/energy_collection_pc_v2` 등은 해당 PC에만 있고 GitHub에 포함되지 않는다. 저장소에는 코드·계약·작은 요약만 있다. 아래 진행상황은 각 당시 이력이다.

## 현재 우선 안내: REPLAN-PC-01

읽을 브랜치는 **`feature/arrival-scheduling-20260923`**이며 master가 아니다. [STATUS](../PROJECT_STATUS.md) → [새 후속 계약·PC 재현](../REPLAN_PC_01_20260925.md) → [PLAN](../PROJECT_PLAN.md)·[DECISIONS](../DECISIONS.md) 순으로 읽는다. 아래 09-24 진단 기록의 “현재/다음”은 당시 이력이다.

- A24 두 모델 요청 실측·27세션 독립 평가가 완료됐고 주 결합 **FAIL**을 보존한다. fixed-split은 부분 종료다. CAL-03은 개발8/확인8·40초기값을 확보했고, 통합 수집의 부분 종료 후 별도 확인3세션도 완료했다. [확인·PC 탐색](../ARRIVAL_FOLLOWUP_AND_EXPLORATION_20260925.md), [서비스 비교](../ARRIVAL_SERVICE_COMPARISON_20260925.md), [허용폭 분석](../ARRIVAL_DELTA_SELECTION_20260925.md)이 최신 근거다.
- 기존 P의 단독 최선 구간은 확보하지 못했다. 이를 지우거나 계수를 튜닝하지 않고, **조작에 따른 배경 시작 제한과 우선순위·정적 배정 효과를 구분하는 별도 후속 개발**을 시작했다. PC 조작/timer/dispatch gate·배경 persist 완료·공통 drain을 구현하고 기능 검증했다. 성능 비교 또는 Android 구현 완료는 아니다.
- 다음은 기존 arrival worker·계측에 새 의미를 연결할 최소 Android 개발과, 양 기준에 공정한 정적 후보/측정 예산의 준비다. 합성 조작은 UI 성능 자료가 아니며 새 실측은 아직 승인·실행되지 않았다. `experiment_ready=false`다.
- S26 선정과 별도 npu-runner/CompiledModel 개발은 유지한다. 최신 팀원 commit·모델/AOT/위임·품질 근거는 아래 제출 목록을 따른다. 이 브랜치의 계약 모델 NPU 지원·품질·성능은 여전히 미검증이며 A24 후속의 필수조건으로 확대하지 않는다.
- 이번 코드·계약·작은 기능 검증 요약은 GitHub에서 읽을 수 있다. 외부 `C:/Users/LG/Documents/D1Check_Arrival_Extension/...` 원본과 상세 실행 산출물은 담당자 PC 전용이다. GitHub에 모델·키·APK·외부 원자료 전체를 올리지 않는다.

## 이전 진단과 협업 기록

> 최신 CAL-03: [개발8→동결→확인8 완료](../ARRIVAL_CAL03_EXECUTION_20260924.md). 진단64·warmup128, 실패/재시도0, 단독 lane 재사용48쌍 확인. 초기40구간 관측을 얻었지만 정확도·정책 우수성 PASS는 아니며 기존20null/experiment_ready=false와 과거 FAIL·미확정 원인은 유지한다. 원본은 로컬 전용이며 [STATUS](../PROJECT_STATUS.md)를 우선한다.

> 최신(2026-09-24): [독립host 관측 통합진단](../ARRIVAL_STALL_OBSERVATION_DIAGNOSTIC_20260924.md) 1회완료(runtime4/warmup8/정규1,209.390초). CAL-02/직전실패원인은미확정이다. [동기journal없는CAL-03 후보](../ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md)는PC준비만완료·별도승인대기. 현재판정은[STATUS](../PROJECT_STATUS.md)를우선하며아래과거실패기록은보존한다.

최신 공유 브랜치는 `feature/arrival-scheduling-20260923`이다. **master에는 이 진행상황이 아직 반영되지 않았다.** 이 안내는 `72b3264`에서 승인 실행한 초기화 진단 결과와 S26·NPU 협업 결정을 정리한다. 아래 상대 링크는 같은 브랜치의 추적 문서다. 문서의 옛 일정/미구현 문구는 당시 이력이며 현재 상태는 이 안내와 STATUS의 최신 절을 먼저 본다.

D1Check는 한 Android 앱에 비동시에 도착하는 분류·탐지 요청을 CPU/GPU에 배정하여 긴급 응답과 일반 서비스의 상충을 평가한다. A24가 개발·주평가 기기다. 단순 기준정책 대비 추가 기여와 기기 이식성은 검증할 질문이며 성공을 전제하지 않는다. 통역·OCR·OS 전체 스케줄링 검증 프로젝트는 아니다.

## 이미 한 작업과 남은 작업

| 구분 | 현재 확인된 상태 | 아직 아닌 것 |
|---|---|---|
| A24 두 모델 | EfficientNet-Lite0 분류·EfficientDet-Lite0 탐지 adapter, CPU/GPU 실행·독립 도착/resident/비선점 계측, 두 모델 실측 진행 완료 | 모든 이미지/기기/부하의 품질·성능 보장 |
| arrival 독립 평가 | pilot19세션 후 독립27세션·198요청·216warmup 완료. 주 결합 판정 **FAIL** (`conditional_joint_primary_pass=false`) 보존 | 일반 처리효율 개선으로 긴급10% 최소효과 실패를 대체하지 않음 |
| fixed-split 비교 | 24/27시도·23완료·실행 전 연결 실패1·미시도3, 평가142/162·warmup184/216, retry/대체0으로 종료 | 전체 평가 완료/주 CI/우월성 입증. 남은 세션 재개 금지 |
| 시간 경계 보완 | 별도 CONDITIONAL_TIMING_DEV_1, dispatch/실행/API 호출/output/persist/실제 lane release 구분, PC 검증 | 완전한 B3/P·간섭 보정·개선 입증.20추정값 null, experiment_ready=false |
| CAL-02 | 업데이트 설치 성공 후 첫 세션 필수 기록 누락. 시도1/16·완료0·실패1·미시도15, cleanup 완료 | 호출 수 확정 불가: 진단0~4/warmup0~8 미확인. 추정 동결/확인 단계 미실행 |
| 초기화 단일 진단 | 준비 후 승인 실행: 설치1·세션1완료·runtime4반환·추론/warmup0·209.047초/600초·회수·cleanup 완료 | **CAL-02 실패 원인 미확정**, 이번에는 미재현. 시간 보정·반복 안정성·GPU 추론 검증이 아니며 소비 계획 재실행 금지 |

2026-09-24 후속: [ARRIVAL-INIT-DIAG-01](../ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md)은 별도 승인으로1회 실행·종료했다. 기존 생성 순서/worker와timeout/gate를 유지했고 journal68개와원본을 보존했다. **다음은 PC에서 단계 경계·잔여 가설 정리**이며 추가 실측은 별도 계획/승인 대상이다. 중단 CAL-02 재개나20개 추정값 보정은 하지 않았다.

[첫 CPU warmup 전이 진단](../ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md)도 승인 후 **실행 완료**했다. 설치1·세션1·runtime4반환·첫 CPU warmup1(명시적 추론총1에 포함)·평가요청0·181.0초/600초·회수/cleanup 완료, 재시도0이다. CAL-02 원인은 미확정이며 나머지 warmup/정규요청과 성능 보정은 미완료다. 20null/experiment_ready=false 및 기존 FAIL을 유지한다. 다음은 PC에서 미관측 경계를 정리하는 작업이고, 종료한 진단 재실행·후속 실측 자동 실행은 금지한다.

[통합 warmup→정규 요청 진단](../ARRIVAL_WARMUP_REQUEST_DIAGNOSTIC_20260924.md)은 승인 후1회 실행했으나 host125초 timeout으로 **중단**됐다. 설치1성공/세션1실패·runtime반환1, 마지막기록은GPU분류 Interpreter 생성시작이다. warmup0~8·정규0~1·총추론0~9는미확인, 총311.344초/600초·원본회수/host cleanup완료·retry0이다. 보정준비완료나CAL-02원인해결이아니다. 다음은PC에서앱대기/watchdog/lifecycle무기록조건검토이며, 소비계획재실행·추가실측은자동진행하지않는다.

## S26·NPU 협업 결정

- **S26을 XDEV-02 추가 검증 기기로 선정**, 정확한 모델명·SoC·fingerprint는 새 device manifest로 확인한다. 확인 전에는 팀원 보고다.
- 팀원이 **별도 npu-runner + CompiledModel**로 NPU 확장을 개발한다. A24 초기화 진단과 병행하며 기존 A24 benchmark-runner 런타임을 바꾸지 않는다. 이 브랜치에는 npu-runner가 아직 포함되지 않았고 팀원 최신 구현은 검토 대기다.
- **S26 CPU/GPU probe와 동결 정책 축소 재현(XDEV-02)**, **NPU 경로 개발·평가**를 분리한다. 과거 S26 80런 또는 model-probe-v1 통과만으로 XDEV-02를 완료 처리하지 않는다.
- 모델별 실행 장치와 품질을 각각 통과한 경로만 후보로 허용한다. 한 모델만 지원하면 그 모델로 제한한다. 기기별 지원 경로를 정책 입력으로 사용하는 구조는 개발 후 동결·평가한다. 현재 정책은3자원 지원 완료가 아니며, 개별 지원만으로 CPU/GPU/NPU3건 병행을 허용하지 않는다.
- `npu_full`/`npu_partial`은 후보 경로 이름이며 자동 검증 결과가 아니다. 모델별 위임·실행 근거로 구분하고, CPU 잔여 연산과 fallback 의미를 밝혀야 한다. 근거가 부족하면 구분도 미확정으로 둔다. DispatchDelegate1/1은 변환 graph 기준인지 확인하고 원 모델 partition/컴파일 매핑·실행 증거와 연결한다. `bit_identical_to_cpu`는 관찰값이며 장치/품질 PASS·FAIL 조건에서 제외한다. 비트 비동일은 NPU 실행 증명이 아니고 비트 동일은 실패 조건이 아니다.
- FP16 등 변환과 엔진 차이를 공개하고 공통 품질 요구를 결과 열람 전에 고정한다. 분류는 대표 이미지·출력/품질, 탐지는 box/class/score·task 품질을 확인한다. 합성 입력32개를 대표 이미지 품질 증거로 승격하지 않는다. 기존 열 상수·전환비용도 새 경로에 전용하지 않는다.

MobileNet V1 NPU 성공·합성 입력32개·manifest 수정 원인은 **팀원 보고이며 원본/코드/사전 기준 미검토**다. **계약 모델 EfficientNet-Lite0 / EfficientDet-Lite0의 NPU 지원·품질·성능은 미검증**이며 MobileNet 보고를 전용하지 않는다. NPU 채택은 품질·속도·에너지 절감·정책 이식성 검증 완료 선언이 아니다. 상세 판정은 아래 DECISIONS가 기준이다.

## 읽는 순서

1. [STATUS 최신 절](../PROJECT_STATUS.md): 현재 작업·장애·다음 행동. 아래 옛 상태는 이력.
2. [S26·NPU 채택/판정 기준](../DECISIONS.md#s26-npu-20260924) → [PLAN](../PROJECT_PLAN.md): 이번 범위와 B2/B3/P 목표, 과거 일정과의 우선순위.
3. [모델 inventory](../MODEL_02_INVENTORY.md) → [model-probe 계약](../MODEL_02B_PROBE.md) → [다기기 프로토콜](../MULTITASK_EXPERIMENT_PROTOCOL.md): exact artifact·실행/품질·재현평가 경계. NPU 결과를 기존 CPU/GPU probe schema에 조용히 끼워 넣지 않는다.
4. [arrival 계약](../ARRIVAL_SCHEDULING_EXTENSION_20260923.md) → [독립 평가 후처리](../ARRIVAL_EXTENSION_POST_ANALYSIS_20260923.md) → [fixed-split 부분 결과](../ARRIVAL_FIXED_SPLIT_RESULTS_20260923.md): 이미 진행한 측정과 FAIL/부분 결과의 한계.
5. [시간 경계 개발](../ARRIVAL_TIMING_DEV_20260924.md) → [CAL-02 종료](../ARRIVAL_TIMING_CAL02_RESULTS_20260924.md) → [초기화 진단 보완](../ARRIVAL_FAILURE_DIAGNOSIS_20260924.md) → [단일 초기화 진단 결과](../ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md): 현재 A24 완료 상태와 남은 한계. 종료된 실험 명령은 실행하지 않는다.

## NPU 담당자가 제공할 최소 자료

| 자료 | 반드시 구분할 내용 |
|---|---|
| 소스/재현 | 최신 branch·commit, 관련 diff(특히 manifest 수정 전후/이유), 모듈·variant, 빌드/컴파일/실행 명령과 도구 버전. 키·비밀번호 제외 |
| 기기/실행 | 정확한 모델명·SoC·fingerprint, engine/runtime/compiler 버전, CPU thread·resident/warmup·메모리/thermal 조건, 장치 실행 근거·CPU 잔여/fallback·partition/compile mapping |
| 모델/입출력 | 원본/AOT 각각의 SHA-256·출처·target·정밀도·변환 옵션, dtype/shape/layout·전후처리·label·탐지 threshold. 배포 제한 binary는 첨부하지 않음 |
| 사전 품질 계약 | 기준을 정한 시점/버전/hash, 대표 입력 목록·출처/hash, 모델별 공통 품질 요구·수용 기준·분모. 이미 본32개 결과는 개발 자료로 표시하고 향후 독립 확인과 분리 |
| 원본/판정 | session/request ID·명령/시각·원본 로그/manifest·출력·실행 장치 판정과 품질 판정을 별도 제공. 실패/미지원/미완료·시도/재시도/전체 분모 포함. 민감정보 제거한 전달 방법과 checksum 목록을 먼저 공유 |

자료를 받으면 먼저 식별정보·장치 실행·품질 기준을 검토한다. 부족한 항목은 미확인으로 유지하며, 성능 비교나3자원 정책 실측으로 자동 확대하지 않는다.

## 공유 경계

GitHub에는 소스·검증 도구·계약·요약 문서를 공유한다. 모델/컴파일 binary, APK, 키·토큰·개인 설정, 외부 raw 전체·캐시는 새로 넣지 않는다. **기존 legacy MobileNet asset은 이미 추적된 과거 파일**이며 이번에 추가한 모델이 아니다. EfficientDet exact binary와 배포 권한 미확인 파생 AOT는 저장소·PR·APK·팀 bundle에 포함하지 않는다. 승인 실행자가 고정 원 URL에서 직접 확보하는 비배포 경계를 유지한다.

기존 상세 보고서의 `C:/Users/LG/Documents/...`는 담당자 PC의 **로컬 전용 위치**다. GitHub나 팀원 PC에서 열리는 링크가 아니다. 기존 원본은 담당자가 보존하고 필요한 경우 공유 가능 범위를 검토한 뒤 별도 checksum/산출물 목록으로 전달한다. 이 안내의 상대 링크는 저장소 문서만 가리킨다. master merge·타인 브랜치 변경·실기기 실행은 이번 문서 공유에 포함하지 않는다.

</details>
