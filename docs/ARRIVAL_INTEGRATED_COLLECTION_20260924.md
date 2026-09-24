# ARRIVAL-COLLECT-01 — 판단 비용·큐 전환·한정 병행 수집 준비

## 2026-09-24 승인 실행 종료: 설치 timeout·세션 미시작

HEAD `0338433`·clean에서 아래 plan v2의 12세션 예산을 승인받아 준비된 스크립트를 1회 호출했다. 계획·소스·APK·manifest 일치와 기존 출력/registry 부재를 확인했다. **설치 시도1회가120초 timeout으로 중단됐고, 개발0/6·확인0/6 세션 시도, 진단0/48·warmup0/96·총명시적추론0/144, retry·대체·추가0이다.** 미시도12세션을 실패 세션이나 성공으로 계산하지 않는다. 기술적 실패1은 세션 전 설치 단계다. 개발 claim 및 전체 stopped registry가 생성되어 **종료 계획 재개 금지**다. 아래 준비·미승인 표현과 실행 명령은 당시 이력이며 현재 실행 지시가 아니다.

- 단일 SM-A245N·동일 fingerprint·기존/후보 signer와package/version1 일치. 배터리55%·31.1°C·비충전, thermal0, Awake/interactive·밝기81/수동/기존5시간timeout, 앱 프로세스 부재를 확인했다. 화면 설정 변경/복구 없음. 앱 내부 runtime memory admission은 실행에 도달하지 못해 미실시다.
- 설치 명령이 반환하지 않았다는 사실만 확인했다. 후보 `d8db6963…34bc`와 설치 전 APK `9019b85d…2c0`의 인증서는 동일하다. 종료 후10초 상한의 읽기 전용 조회(실제0.593초)에서 설치본은 이전 APK 해시 그대로였다. 서명 불일치·GPU 실패·CAL-02와 같은 원인으로 해석하지 않는다. 전송/무선/패키지 처리 원인은 미확정이다.
- host UTC claim→설치75.180초, 설치→중단120.026초, 중단→cleanup receipt0.687초, claim→cleanup195.893초. 마지막 조회까지283.200초(중간 PC 대기 포함), 최초 기기조회가 포함된 tool wall0.699초를 별도 합산해도283.899초다. 냉각·세션0초, 확인 미시작. 승인5490초 이내이며 회수·cleanup 시간을 밖으로 빼지 않았다. cleanup 단독 정밀 타이머 대신 receipt 간격을 명시한다.
- host force-stop·프로세스 부재·thermal0 확인. 앱 cleanup은 세션 미시작으로N/A다. Activity launch0/설치 단계 종료의 host 제어 흐름이 진단·warmup0의 근거이며 단순 로그 부재로 판정하지 않았다. 원 stopped.json의 일반 `requests_actual=unknown`은 보존하고 별도 receipt에서 근거를 붙였다. preflight helper의 `phase_consumed=false`는 helper 자체 상태이며 실제 소비 판정은 앞서 생성된 registry claim을 따른다.
- 새 비용 표본0, 동결/확인/오차 판정 미실시, 새 PC 연결 없음. 현재 엄격 CPU fallback·전체직렬과 병행 차단을 유지한다. 기존40값/20null/FAIL/부분결과/종료계획·experiment_ready=false 불변. 빌드·완료된 테스트는 반복하지 않았다.

외부 root의 `integrated_collection_execution_v1/FINAL_REPORT.md`, `FINAL_RECEIPT.json`, `REPRODUCE.py`(PC 읽기 전용), `post_stop_observation.json`; 실행 원본은 `integrated_collection_run_v1/development/`, 소비는 `collection_execution_registry/ARRIVAL-COLLECT-01/`에 보존한다. 원본/회수 APK는 Git에 포함하지 않는다.

다음 최소 행동은 **새 설치 진단의 PC 준비**다. timeout 예외의 부분 stdout/stderr와 단계 시간을 보존해 전송/패키지 처리 구간을 구분할 수 있어야 한다. 이번 예외에는 명령·120초만 남아 원인을 좁힐 수 없다. timeout 연장이나 같은 계획 재실행을 하지 않으며, 후속 기기 작업은 별도 승인 대상이다. 수집 성공 뒤에만 개발자료 기반 강한B2 선정·B3/P 결정 차이·공통 목적/제약 동결과 독립 평가를 준비한다. 지금 정책 비교를 추가할 근거는 없다.

2026-09-24, 시작 `0eae7c01f68e3604f0e331a3f5657ac4fd075e32`, 작업 브랜치 `feature/arrival-scheduling-20260923`. **구현·관련 PC 검증·서명 APK·계획 준비 완료. 새 실측 미승인·미실행, experiment_ready=false.** 사용자 요청으로 잠시 중단 후 같은 변경에서 재개했다. 이 문서는 새 개발 수집 계약이며 기존 CAL-03 확인 자료·동결40값·20null·198요청 FAIL·fixed-split 부분 결과·종료 계획을 변경하지 않는다.

## 현재 가능한 비교와 부족한 근거

[기존 연결 계약](ARRIVAL_CAL03_CONNECTION_20260924.md)의 엄격 PC 정책은 어느 lane이든 busy면 기다리고, 둘 다 AVAILABLE이면 미측정 adaptive 판단→dispatch 비용 때문에 CPU로 배정한다. 이 모드에서 GPU 선택은 **불가능**하다. 이는 backend별 1건 제한이 아니라 **전체 1건 직렬화**다. 현재 단독 이벤트 엔진은 이 fallback 경로의 도착·응답·점유 경계와 명시적 가정 모드만 비교할 수 있다. CPU fallback 결과를 적응형 성능으로 해석하지 않는다.

현재 엔진으로는 병행 FIXED_SPLIT/CONDITIONAL, 최선 정적 B2 선정, 완전한 B3/P, Band 시스템 비교를 검증할 수 없다. 기존 동결 시뮬레이터와 기존 실험 정책은 별도 계약 그대로다. [PLAN](PROJECT_PLAN.md)의 B2/B3/P·기존 시스템 비교 및 축소 기준을 FIFO 비교로 대체하지 않는다.

| 공백 | 영향을 받는 판단·식별 한계 | 이번 처리 |
|---|---|---|
| 실제 Android 판단→dispatch | 절대 응답 예측·스케줄러 점유. CAL-03은 고정 경로여서 새 후보 계산 비용 아님 | 새 경로에서 직접 측정. 공통 비용 하나만으로 backend 순위가 달라지지는 않음 |
| 큐 부하의 A→S 및 P→L | 실행 준비/기록/callback 지연과 CPU 잔여 대기. CAL-03은 5초 간격 단독 | 같은 배정의 sparse/queued 대조. 깊은 큐는 미지원으로 남김 |
| CPU/GPU 병행 S→O·점유 | CPU 대기 대신 GPU 사용의 추가 비용. 단독 자료에 overlap 없음 | 한 가지 역할·배정·시차만 단독/직렬/병행 대조. 정책 비교 전 필요한 최소 관측 |
| 초과 실행의 조건부 잔여 분포 | UNKNOWN_OVERRUN에서 종료시각을 알 수 없음 | 이 작은 수집으로 해소하지 않음. busy 유지, 임의 안전 여유 없음 |
| 모든 배정·역할·깊은 큐·tail·thermal/energy 모형 | 최종 범위가 정해져야 필요 조건 결정 가능 | 이번에는 측정하지 않음. 미지원 또는 명시적 민감도 가정. 전체 B2 후보 검토를 끝냈다는 뜻 아님 |

수집 범위 선정을 위한 **대수적 임계값**만 계산했다. CPU 대기 `R+Q`, backend별 새 판단/준비 차이 `Dcpu−Dgpu`, 단독 전체 응답 중앙값 C/G이면, 합법적 병행이 가능하고 GPU가 비었을 때 GPU가 짧게 예측되는 조건은 `R+Q+(Dcpu−Dgpu) > G−C`다. 개발 공동구간에서 G−C는 분류 urgent141.048ms/normal144.749ms, 탐지 urgent516.318ms/normal508.057ms다(반올림). 이는 선택 경계이며 실제 가능한 대기 분포·신뢰구간·성능 향상 추정이 아니다. 공통 D는 상쇄된다. 현재 엄격 정책은 이 병행 규칙을 사용하지 않는다. 확인 자료를 재튜닝하거나 본 시뮬레이션을 실행하지 않았다.

## 별도 Android 실행 경로와 PC 대응

- protocol `arrival-collection-dev-v1`, 수집 배정 ID `COLLECTION_DISPATCH_DEV_1`. [ArrivalCollectionDev.kt](../benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalCollectionDev.kt), 기존 Activity/Recorder에 명시적 확장으로 연결한다. 기존 CONDITIONAL/20필드 정책의 ID·동작은 보존한다.
- `strict_active`: PC `CAL03_SOLO_CONDITIONAL_PC_DEV_1`의 엄격 결정을 실제 배정에 사용한다. 현재 결과는 CPU fallback/전체 직렬화다. P나 완성된 B3가 아니다.
- `fixed_shadow`: 같은 snapshot에서 엄격 정책의 예측·대기 이유만 기록하며, **실제** 배정은 CPU 고정 또는 urgent CPU/normal GPU 고정이다. concurrency1은 전체 직렬,2는 backend별 1건이다. shadow 선택을 실행 결과로 보고하지 않는다.
- 도착한 큐(urgent→ordinal→ID)와 실제 관측 lane/task/priority/phase만 입력한다. 후보 A→response/A→L, phase별 잔여와 UNKNOWN_OVERRUN, 선택 없는 호출도 기록한다. 미래 요청·실제 미래 완료시각을 입력하지 않는다. 실제 callback의 AVAILABLE 이전에는 busy다.
- task×backend×priority 공동구간 설정은 CAL-03 개발자료 파생 설정을 hash/bytes로 묶어 읽는다. 동결40값과 기존20null에 대입하지 않는다. 미측정 adaptive D→A도 null 그대로다. 모든 실행은 개발 전용/experiment_ready=false다.

시간 표기: D=snapshot, A=dispatch, S=execution_start, O=output_ready, P=persist_complete, W=worker_release, L=scheduler AVAILABLE. 모두 앱 monotonic ns. urgent 응답은 예정도착→O, normal은 예정도착→P이며 저장은 양쪽 모두 수행한다. host inference 시작/종료는 CPU/GPU API 호출 구간이지 GPU kernel 구간이 아니다.

새 기록은 snapshot→compute_start→compute_end→selection_end→record_end를 구분한다. compute에는 snapshot map/잔여/후보/결정 객체 생성이 포함되므로 순수 산술 시간으로 부르지 않는다. 이후 실제 배정 선택과 메모리 기록 append 비용은 별도다. 외부 Recorder 기록·lock·row 작업은 D→A에 포함되며 따로 빼지 않는다. 마지막 timestamp를 map에 쓰는 비용 자체와 선택 없는 호출의 외부 기록 전체 비용은 이 세부 계측에 완전히 포함되지 않는다. 기록이 없는 경로와의 인과적 overhead 측정은 아니다.

collection trace128/기존 phase trace512의 고정 버퍼를 사용하고 dispatch 경로에 JSON 직렬화·동기 journal·fsync를 추가하지 않는다. 종료 시 파일로 저장한다. overflow는 배정을 중단하고 적격성 실패로 남긴다. native crash/강제 종료에서 finally 보장·무손실 기록을 주장하지 않는다. 원 manifest/부분 event/host 관측으로 확인할 수 없는 호출 수는 범위로 남기며0으로 채우지 않는다. 기존 앱 실패 journal을 활성화해 이 수집 시간과 섞지 않는다.

## 최소 수집 설계 — 예산 제안, 실행 승인 전 금지

각 세션은 새 프로세스의 resident4 runtime, CPUthread1, 기존 순서의 warmup8(분류CPU2→분류GPU2→탐지CPU2→탐지GPU2), 진단4요청이다. exact EfficientNet-Lite0/EfficientDet-Lite0·기존 단일 이미지·저장/품질·memory gate는 동일하다. 새 모델/역할 반전/NPU는 추가하지 않는다.

모든 세션 요청 순서는 탐지normal, 분류urgent, 탐지normal, 분류urgent다. sparse 예정 도착은 `[0,5000,10000,15000]ms`, queue는 `[0,100,5000,5100]ms`다. 생성은 완료와 독립적이다. arrival lag 상한100ms, deadline5000ms는 진단 시나리오이며 UX SLA·차별 지표가 아니다.

| 조건 | 실제 배정 | 동시성 | 도착 | 답할 질문 |
|---|---|---:|---|---|
| A active_cpu_sparse | 엄격 PC 정책을 active 사용, 현재 CPU fallback | 전체1 | sparse | 실제 판단→dispatch와 후보 계산 경계 |
| B shadow_cpu_sparse | CPU 고정+엄격 shadow | 전체1 | sparse | A와 실제 선택 분기 차이. 양쪽 모두 기록하므로 기록 on/off 비교 아님 |
| C shadow_split_sparse | urgent CPU/normal GPU+shadow | 전체1 | sparse | 같은 runtime/입력에서 고정 분리의 단독 기준 |
| D shadow_cpu_queue | CPU 고정+shadow | 전체1 | queue | B 대비 큐 대기 후 준비/callback 전이 |
| E shadow_split_queue_serial | 고정 분리+shadow | 전체1 | queue | C 대비 부하, F의 같은 trace 직렬 대조 |
| F shadow_split_queue_lanes | 같은 고정 분리+shadow | backend별1, 전체2 | queue | E 대비 병행 허용 효과·실제 API overlap |

개발 A→B→C→D→E→F, 확인 E→D→C→B→A→F. seed2026092402, 결정적 session/request ID, 동일 조건의 workload 대응. 첫5조건은 역순으로 순서 효과를 일부 줄이지만 **F는 안전 gate 때문에 항상 마지막**이어서 시간 순서 교란이 남는다. 독립 반복 단위는 세션이며 단계별 조건당1개, 같은 세션 두 task-pair 반복은 상관 자료다. 여섯 조건을 묶어 원인을 완전히 식별했다고 하지 않는다.

F는 같은 단계의 앞5세션 artifact/cleanup 검증 성공 뒤에만 시작한다. 기존 GPU 생성·사용·해제 전용 worker와 CPU worker, resident memory admission을 그대로 사용한다. F에서 허용하는 새 병행은 **normal 탐지GPU+urgent 분류CPU**뿐이다. 실제 host API overlap2쌍, D/E에서는 실제 queued handoff≥2가 필요하다. 관측되지 않아도 요청·반복을 추가하지 않고 적격성 부족으로 계획 전체 중단한다. 반대 배정이나 두 GPU/두 CPU 동시 실행을 검증하지 않는다.

| 예산 항목 | 제안 상한·근거 |
|---|---|
| 세션 | 개발6→기술 적격성 확인/기술통계 동결→확인6 =12 |
| 진단 요청 / warmup | 48 /96, 총 명시적 추론144. 평가 요청0, runtime 생성 최대48 |
| 설치 | 단계별 업데이트1회, 최대2. 삭제/초기화 없음 |
| cooling | 각 단계 최초120초+세션 사이5×120초, 합24분. 조건 미달 시 늘리며 대기하지 않고 중단 |
| 예상 실행시간 | 약32~45분(과거 CAL-03 약43.43분/16세션, 동일 staging/cooling 기반 운영 추정). 냉각24분+예정 도착 구간 약2.17분 외 초기화·전송·회수·검증 비용 추가. 보장된 최소 시간 아님 |
| 절대 상한 | 단계별 작업2700초(실패 증거10초 예약 포함)+cleanup45초, 총5490초=91.5분. PC 중간 검토 시간은 기기 실행 상한 밖 |
| retry / 대체 / 추가 | 모두0. 실패 세션·미시도 분모 보존, 소비한 단계/종료 계획 재개 금지 |

runtime Future30초, 앱 watchdog120초, host poll125초를 유지한다. install≤120초, launch≤30초; 외부 명령은 자체 timeout과 남은 단계 deadline 중 작은 값이다. stage/launch 전 최소165초(launch30+poll125+증거10)를 확인한다. 정상 회수·검증·세션 cleanup도 단계 시간 안에서 수행하며 마지막에45초를 확보한다. 실패 증거는 최대10초, cleanup은 최대45초/절대 상한 내. native cancel이 반환을 보장한다고 가정하지 않는다.

## gate·소비·중단·분석 규칙

실행 승인 후에도 현재 설치본/후보 package·version·서명, 계획/APK/입력/소스 hash, 단일 online SM-A245N·동일 fingerprint, 앱 프로세스 부재를 확인한다. phase 시작 배터리≥55%, 이후≥30%, battery≤35°C, 비충전, thermal0, low_memory=false와 기존 `android-low-memory-resident-v1` admission을 유지한다. host meminfo는 관측이며 임의 새 메모리 임계값을 만들지 않는다. 앱의 생성 전/호출 전 gate 실패는 중단한다.

화면은 Awake/interactive, 밝기81/수동, 기존 timeout18000000ms를 읽기 전용으로 확인한다. 앱 KEEP_SCREEN_ON 유지, 설정 변경·자동 wake/unlock 없음. 설치 전/시작 전/host poll10초 간격/회수 후 관측한다. 표본 사이 상태는 미확인이다. 관측 경과는 별도 기록하고 요청 시간에서 차감하지 않는다. 연결·조회·환경·품질·기록·coverage 실패 모두 중단하며 gate를 유리하게 바꾸지 않는다.

새 registry는 **preflight 전에 단계 사용을 claim**한다. preflight 실패는 설치/세션 시도0과 별개로 전체 계획 중단 상태다. install_attempt 파일은 설치 호출 전, session attempt는 해당 조건 gate 전, launch_attempt는 Activity 호출 전에 만든다. 그러므로 attempt 수와 실제 Activity/추론 수는 별도 보고한다. 실패/미도착/미완료는 planned48 및 단계별24 분모에 남기고 실제 arrived/호출 완료 분모를 분리한다. 이전 CAL 소비 규칙은 소급 변경하지 않는다.

회수는 manifest/실패 진행/cleanup 우선, 나머지 파일이다. 회수 실패와 앱 실패를 구분한다. 최대10초 내 가능한 부분 회수·프로세스/crash 증거를 남기고 cleanup을 지연하지 않는다. 앱 cleanup.json과 host force-stop/프로세스 부재를 각각 보고한다. 완전 자료에는 requests/events/결과해시, warmup_trace, decision_trace, collection_trace, summary/environment/cleanup, 원 delegate log와 추출 증거가 필요하다.

개발6세션 모두 자료 적격성 통과 시 `freeze`가 검증된 회수 파일 목록·bytes·hash를 다시 대조하고 조건별 compute/record/D→A, task×backend×priority별 A→S/P→L/S→O의 중앙값·최솟값·최댓값·n과 원자료 hash를 **새 파일**에 동결한다. 확인 실행 claim은 이 개발 규칙으로 재산출한 값·hash의 동일성만 허용한다. 확인6세션은 독립 새 세션이지만 조건당1개이며 정책 성능 독립 평가가 아니다. 확인 중앙값−동결 중앙값을 그대로 보고하고 재보정하지 않는다.

사전 분석 대조는 A−B, D−B, E−C, F−E의 방향/기술통계다. F−E에는 overlap뿐 아니라 시작/대기/순서 변화가 함께 있으므로 이를 kernel 간섭의 인과 계수로 쓰지 않는다. 서비스 구간은 동일 task/backend/input별로 나눠 제시하고 pooling하지 않는다. 요청2개를 독립세션2개로 계산하지 않으며 CI·p-value·tail·정확도 허용폭·우월성 PASS를 만들지 않는다. 확인 오차가 크면 그대로 남기며 추가 수집하지 않는다. 이 기술통계 동결은 CAL-03의40개 추정값 교체나 적응형 설정 자동 보정이 아니다.

## 준비 파일과 실제 명령

공통 외부 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`는 GitHub에 포함되지 않는다.

- `integrated_collection_plan_v2/collection_plan.json`, manifests12, `RUN_AFTER_APPROVAL.ps1`. v1은 중단 당시 후보로 보존하며 **v2만 현재 후보**다. v2는 host의 동결 전 원자료 hash 재대조 추가를 반영했다. 예산·APK·조건·ID는 같다. 두 버전을 각각 실행할 수 없도록 같은 소비 registry를 쓴다.
- plan SHA-256 `914a43ce439fe7113edcdaaa4350d5c5f4e20a523f9ae3bec554cc03dd4e0566`.
- `integrated_collection_apk_v1/build_receipt.json` 및 별도 APK. APK SHA-256 `d8db696374d43696e2a7aed84800345ad5c2dc363fcc3f8176df015350c634bc`. 기존 프로젝트 signer 일치 PC검사 완료. 설치 성공/기기 호환성은 미검증.
- `integrated_collection_pc_v1/FINAL_REPORT.md`, `VERIFICATION.json`, 테스트 로그·Kotlin snapshot·민감도 경계·재현 명령. 출력 예정 root `integrated_collection_run_v1`, registry `collection_execution_registry/ARRIVAL-COLLECT-01`은 준비 시 존재하지 않았다.

저장소 root에서 실행한다. **아래 RunDevelopment/RunConfirmation은 새 예산 승인 이후에만 사용한다.** serial은 당일 승인 A24 연결 주소를 명시하며 스크립트/실행기가 단일 기기·fingerprint를 재검증한다.

```powershell
$script = 'C:/Users/LG/Documents/D1Check_Arrival_Extension/integrated_collection_plan_v2/RUN_AFTER_APPROVAL.ps1'
& $script -Action Check
# 새 12세션 예산 승인 후에만:
& $script -Action RunDevelopment -Approved -Serial '<당일 A24 serial>'
& $script -Action Freeze
& $script -Action RunConfirmation -Approved -Serial '<당일 A24 serial>'
& $script -Action Confirm
```

스크립트는 `python -B -m tools.d1_arrival_collection`의 실제 check/run/freeze/confirm을 호출한다. 개발 실패 후 Freeze/확인은 차단된다. 생성된 파일을 덮어쓰지 않으며 자동 재시도하지 않는다.

## PC 검증과 준비 완료의 한계

Kotlin28건(새 collection8+기존 timing13+calibration7), 기존 Python timing validator9건을 변경 당시 통과했다. 새 Python collection은 초기12건 통과 후 원자료 변경 감지 테스트1건을 추가해 **최종13/13, skip0** 통과했다. Kotlin 실제 export12개와 Python 정책 snapshot이 일치했다. source 해시는 APK receipt·plan·외부 VERIFICATION에 연결한다. 재개 시 Android 코드 변경이 없어 Gradle/APK 빌드를 반복하지 않았다.

검증 범위는 fallback/전체직렬·per-lane 구분, shadow/active 차이, priority 비용/초과 잔여/busy/미래도착, no-selection/overflow, 구버전 명시적 확장, 소비 재개 차단, 동결/변조 거절, 서명 실패 시 설치0, 회수 실패 시 cleanup/no retry, budget/workload/manifest, dry-run에서 Device 호출0이다. dry-run은 가상 실측 파일·소비 registry를 만들지 않는다. PC mock은 실제 GPU 병행·환경·callback 성능을 검증하지 않는다.

| experiment_ready 요건 | 현재 |
|---|---|
| 개발 설정 출처·priority·공동구간·UNKNOWN_OVERRUN 보존 | 구현/PC 통과 |
| Android 실제 배정 분기 및 PC strict 의미 대응 | 구현/PC 통과, 새 기기 검증 미실행 |
| 판단/기록/D→A·queued callback 관측 | 수집 경로 준비, 미측정 |
| 합법적 병행 비용·지원 범위 | 한 조합 단계 gate 준비, 새 비용 미측정 |
| 정확도 허용폭·초과 잔여/부하 범위·강한 B2/B3/P·가치 제약·독립 평가 | 미확정/미충족 |

수집 성공 뒤에도 전체 experiment_ready=false다. 성공은 특정 조건의 기록과 전환·한 병행 조합에 대한 개발 근거를 준다. 다음은 그 자료로 **필요한 배정 후보/지원 범위와 B3 대비 결정 차이를 선정·동결**하고, 같은 조건의 강한 정적 B2/B3/P·기존 시스템 비교 및 새 독립 평가를 준비하는 일이다. 반대 배정/역할·깊은 큐가 최종 정책에 필요할 때만 부족한 조건을 별도 승인 측정한다. 새로운 정책 기여가 없으면 복잡한 정책 확대를 중단한다. 추가 실측을 성공할 때까지 늘리지 않는다.
