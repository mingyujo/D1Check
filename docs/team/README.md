# 팀 안내 — 2026-09-25 현재

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
