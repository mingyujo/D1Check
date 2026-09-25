# ENERGY-THERMAL-COLLECTION-PREP-02 — 두 병행 조합의 실행 준비

## 목적과 현재 판정

동일 작업량·출력 품질 및 대화형 응답·일반 완료 조건 아래 에너지·발열 부담을 평가할 **고정 작업량 보정 수집**이다. 병행 우월성을 전제하지 않는다. 발열·배터리는 필수 목표이고 단순 안전 gate가 아니다. 이번은 PC 구현/검증/서명 APK/계획 준비이며 실기기 실행·배정 정책 최적화는 하지 않는다. 새 실행 ID는 `ENERGY-THERMAL-COLLECT-02`, protocol은 `energy-thermal-collection-v2`다.

시작 `ff03641`/clean, `feature/arrival-scheduling-20260923`. 기존160세션 분석을 재실행하지 않는다. [기존 보정](ENERGY_THERMAL_PC_01_20260925.md)과 [미실행 단독8세션 후보](ENERGY_THERMAL_COLLECTION_PROPOSAL_20260925.md)를 보존한다. 기존 FAIL/부분 결과/40동결값/20null/종료 계획·`experiment_ready=false`는 불변이다. S26/NPU는 별도 협업이고 A24 계수를 자동 적용하지 않는다.

## 최소 조건과 중복 제거

CPU thread1, 동일 exact 두 모델·한 장의 기존 canonical 대표 이미지 `00575b9132bb3746`, 동일 adapter/출력 품질·4-runtime resident를 사용한다. 분류 normal, 탐지 urgent는 이번 역할이며 다른 priority로 자동 전용하지 않는다. 모든 요청은 작업 묶음 시작에 도착한다. 실제 사용자 도착 trace나 UI 부하가 아니다.

| 조건 | 분류678건 | 탐지192건 | 실행 순서/제어 | 개발/확인 |
|---|---|---|---|---|
| CC_DG serial | CPU | GPU | 분류 전량→탐지 전량, 실제 lane 해제 후 다음 요청 | 각1세션 |
| CC_DG parallel | CPU | GPU | 두 lane의 최초 요청 동시 dispatch 시도, 각 lane 안은 순차 | 각1세션 |
| CG_DC serial | GPU | CPU | 분류 전량→탐지 전량, 같은 backend/입력/작업량 | 각1세션 |
| CG_DC parallel | GPU | CPU | 위와 동일한 병행 제어, 반대 배정 별도 확인 | 각1세션 |
| 간격·냉각 | 모두 resident | 모두 resident | 완료 후 공통480초 창까지 idle, 이어180초 냉각 | 모든 세션 포함 |

별도 단독4조건을 직렬 세션의4개 단독 구간으로 대체한다. **실제 직렬 묶음**의 에너지/시간을 측정하며 단독 모형합으로 대조를 대신하지 않는다. 다만 후반 탐지는 분류의 잔열을 받는다. 따라서 같은 초기온도의 독립 단독4조건이 생긴 것이 아니다. 시작 온도와 잔열을 상태에 포함하고, 분리 불가능하면 그 조건의 경험적 곡선/오차만 보고한다. 직렬 순서 역전은 미지원이다.

독립 단위는 세션이다. 개발4조건 각1세션과 확인4조건 각1세션으로 총8세션이다. 세션 안678/192반복은 상관 요청이며 독립 표본을 늘리지 않는다. 개발 순서는 위 표, 확인은 CG_DC serial/parallel→CC_DG serial/parallel로 pair 순서를 반전한다. 각 단계에서 같은 pair의 직렬 적격성이 먼저 확보돼야 병행을 시작한다. serial→parallel 순서를 완전히 균형화하지 못하므로 날짜/순서 효과를 제거한 인과/우월성 검정은 아니다.

기존 단독 후보와 세션 수는 같지만 요청량과 시간 예산은 새로 산정했다. 단독3480요청 대신 **동일 묶음870건×8=6960건**이며 각 세션에 별도 적격성2건을 추가한다. 미실행 단독 후보의 예산을 소비하거나 승계하지 않는다.

## 지원할 선택과 남길 제한

- 직접 관측: 이 입력/역할/작업량/배정의 즉시 직렬 대 동시 시작 병행, 실제 API overlap·한쪽 tail·완료 후 resident idle/냉각.
- 조건부 모형: 관측 온도/기간 안에서 실행 뒤 대기·잔열 전개. 냉각 후 같은 process에서 다음 배치를 재시작하는 전이는 이번에 검증하지 않는다.
- 미지원/가정: 임의 offset의 부분 병행, 요청별 미세 시작 간격, 모든 duty/작업비율/이미지/priority, 고온 스로틀링 곡선. 긴 동시 시작 한 조건을 이 범위로 외삽하지 않는다.
- 두 단독 worker가 존재한다고 병행 적격성을 부여하지 않는다. 특히 분류GPU＋탐지CPU는 별도 on-device gate 전까지 미검증이다. 반대 방향 병행 시간·전력 자료를 대입하지 않는다.

## 앱·host 단계 gate와 관측

새 `EnergyCollectionActivity`를 별도로 추가했다. 기존 ArrivalSchedulerActivity/120초 watchdog/기존 정책은 바꾸지 않는다. 기존 ProbeTaskAdapter/ProbeRawSession·ArrivalRuntimeSetup·V4Gate·host 서명/preflight·기록된 ADB client·thermal parser를 재사용한다.

1. 앱 신규 output·manifest 저장→CPU/GPU 소유 worker에서 기존 정렬 순서로 runtime4생성→각2회 warmup(총8). GPU 생성/사용/close는 동일 GPU executor다. runtime/native 준비 연산은 명시적 warmup과 구분한다.
2. `warmup` ready에서 host가 기존 CAL-03 **개발**의 같은 backend/입력 출력과 대조하고 GPU runtime2개 전체 위임 로그를 확인한다. 탐지: 기존 비교기의 label/count 일치, score≤0.001, box≤2px. 분류: top5 label/index 일치, score≤0.001의 명시적 출력 회귀 gate다. 대표 입력의 기존 품질 근거 유지이지 새 task 정확도 인증이 아니다. 비트 동일/비동일을 GPU 증명으로 사용하지 않는다.
3. hash arm 후 각 모델1건, serial 또는 해당 병행 조합으로 짧은 적격성 호출2건. host가 출력·시간 순서·lane·실제 API overlap·환경 근거를 확인한다. 미검증 긴 병행 부하는 이 gate 전에는 불가능하다. 짧은 probe는 새 동시 실행 지원을 확인하기 위한 승인 예산 내 진단이며 장기 안정성 PASS가 아니다.
4. resident baseline120초. host가 baseline 경계와 AP 관측을 확인한다. pair의 첫 개발 직렬 baseline을 anchor로 같은 pair의 후속 조건/확인 median이±0.5°C 이내여야 부하를 허용한다. 0.1°C 해상도의5단계 환경 통제 허용폭이며 효과/정확도 margin이 아니다. 부족하면 추가 냉각·재시도 없이 중단한다. gate 대기 자체의 온도와 전력도 기록한다.
5. arm 후 고정 작업량. 각 요청에 도착/dispatch/worker 시작/입력 준비/host inference 시작·끝/출력/output_ready/persist_complete/worker_release/실제 lane_available을 기록한다. 실제 Future 완료를 확인한 후에만 lane을 재사용한다. GPU kernel 구간이라고 부르지 않는다. lane별 실제 겹침과 먼저 끝난 뒤 tail을 분리한다.
6. 먼저 완료해도 공통 workload480초 창까지 resident 대기한다. 이어180초 resident 냉각 후 앱 close·host 회수·force-stop/프로세스 부재를 별도 확인한다. 종료된 계획 재개·실패 후 다음 세션 강행은 없다.

에너지 전류 raw·API 명목 단위·valid·voltage mV·charge counter raw/valid·plugged·battery temp/level·memory·thermal status·interactive·활성 runtime/lane를 약1Hz의 앱 monotonic clock으로 기록한다. unsupported MIN값은 raw로 보존하며 0/abs로 바꾸지 않는다. A24 mA 가설×1000은 가장 유력한 조건부 해석이지 확정 보정계수가 아니다. 배터리/기기 전체 전력이며 CPU/GPU rail 전력이 아니다.

AP/BAT/PA/SKIN은 host의 기존 HAL parser를 사용한다. `/proc/uptime` 앞뒤 bracket과 원문·type을 보존하고 중간 시각/불확실성을 기록한다. 약2초 주기로 시도하되 실제 간격을 남긴다. 누락 센서는 missing이며 AP 외 센서 미지원만으로 다른 관측을 0 처리하지 않는다. sparse 화면 확인10초, 진행 heartbeat도 관측한다. host명령·메모리 관측·logger·저장 비용은 실행에 포함된다. 이를 관측 없는 앱의 절대 전력/순수 inference 에너지로 주장하지 않는다.

## 기록 내구성과 시간 상한

- 신규 protocol만 앱 watchdog1200초, host poll1220초. 각 runtime 생성/명시적 호출 최대30초, 초기화+warmup 구간150초(각 호출의30초가 전체 제한을 초기화하지 않음), 적격성 작업30초, 각 host arm 대기60초, workload480초. 기존120/125초 계약은 불변이다.
- 부하 경로는 독립 bounded writer(32768대기 row)로 기록한다. 약1초마다 fsync, gate 전 최대2초 durable flush. per-call 동기 journal은 없지만 결과 저장 fsync와 enqueue/관측 overhead는 측정에 포함된다. queue overflow/저장 실패/heartbeat 정체면 중단한다. native crash/강제 종료는 finally 보장 없음, 최근1초와 queue의 미확인 범위를 남긴다.
- 앱 close는 lane당5초와 종료 확인으로 유한 대기한다. interrupt가 native 종료를 보장한다고 가정하지 않는다. 멈춘 worker로 close를 제출해 무기한 기다리지 않는다. host cleanup45초를 예약한다.
- host 회수는 identity/progress/cleanup 우선 snapshot 후 한 번의 tar 회수로 결과 수백건을 가져온다. 경로 탈출/중복/크기 초과를 차단한다. partial JSONL의 완료되지 않은 마지막 줄과 시작만 남은 호출은 성공으로 세지 않는다. 회수 오류와 앱 오류를 구분한다.
- 모든 ADB 명령에 명시적 serial·timeout·부분stdout/stderr·client 종료 대상 기록을 적용한다. 기존 server가 없으면 자동 daemon 재시작/복구하지 않는다. 이번 준비에서는 ADB 호출0이다.

## 새 권고 예산과 근거

678/192는 CAL-03 개발 dispatch→lane 중앙값의 가장 빠른 task 경로도 약120초 부하를 갖게 하는 기존 점추정에서 출발한다. classCPU120.15s/GPU218.06s, detectionCPU120.03s/GPU220.49s. 따라서 직렬 CC_DG 약340.64s/CG_DC338.09s, 무간섭 병행 약220.49/218.06s, API overlap 가능 구간은 약120초와 나머지 tail 약98~100초다. **계측·간섭이 없는 단순 예약 계산**이지 실제 병행 시간 예측/보장/상한이 아니다. workload480초 안에 끝나지 않으면 미완료로 중단한다.

baseline120초는 기존 약60초 counter 갱신의2주기, 냉각180초는 옛 A24 AP 관측 시정수 최대 약58초의3배를 참고했다. 새 모델/resident에서 같은 τ나 완전 냉각을 보장하지 않는다. 공통480초 창은 두 직렬 작업량과 여유를 포함하고 비교군마다 다른 idle 에너지를 숨기지 않기 위한 고정 창이다.

| 항목 | 전체 계획 상한/예약 |
|---|---:|
| 세션 | 개발4→동결→확인4 = 8 |
| runtime 생성 | 32 |
| 고정 작업량 요청 | 6,960 |
| 사전 적격성 요청 | 16 |
| 진단 요청 합계 | **6,976** (정책 평가 요청0) |
| warmup | 64 |
| 총 명시적 추론 | **7,040** |
| APK 전송/설치 | 각 최대1, 정확히 같은 설치본이면 생략 |
| 입력 전송 | 최대8회 세션 staging, 각6입력+manifest=56파일; APK전송과 별개 |
| 재시도/대체/추가 | 0/0/0 |
| baseline / 공통 workload 창 / 냉각 | 16분 / 64분 / 24분 = 고정104분 |
| 한 세션 전체 | 최대1500초=25분: gate/staging120, launch≤20, hostpoll1220, 회수60, cleanup45, 나머지35초 여유 |
| 설치/preflight/전송/확인/cleanup | 최대600초=10분 |
| 개발 분석·동결/검토 | 최대600초=10분, 부족하면 확인 시작 금지 |
| 전체 hard 상한 | **13,200초=220분** (8×25+10+10), 모든 냉각·gate·회수·cleanup 포함 |

고정 관측은104분이며 실제 설치·준비·조회 속도는 현재 PC에서 알 수 없다. 각 앱 단계/setup·host arm·probe·close와 host stage/launch/회수/cleanup의 예약을 합친 **timeout 합산 예약시간206분40초**, 전체 상한220분을 권고한다. 정상 평균 소요시간과 완주 가능한 시작 배터리 잔량은 미확인이다. 고정104분에 실제 준비·gate·회수·동결 시간이 추가되며 watchdog/host poll은 별도로 중복 합산하지 않는다. 배터리 부족·온도 이탈 시 충전한 채 강행하거나 예산 밖 무제한 환경 대기를 하지 않는다. 2026-09-25 사용자 승인으로220분과6976진단/64warmup 실행이 허용됐다. 비교군·순서·timeout·중단 규칙은 불변이다.

세션/시간을 줄이려면 한 pair 자체를 제외하여4세션으로 축소하는 것이 가능하지만, 그러면 그 배정의 병행 비교는 미지원이다. 이번 필수 두 병행 조합을 유지하면서 직렬 대조·확인 단계를 없애는 축소는 권고하지 않는다. 임의 offset/duty 추가를 하지 않아 조건 수를 줄였다.

## 사전 분석·동결·확인 계약

모든 예정량/실패/미완료를 분모에 남긴다. 완료된 세션만 원래 전체 계획이 완주했다고 쓰지 않는다. 같은 입력/task/backend의 serial 대비 parallel을 같은 단계에서 기술적으로 비교한다. 개발/확인 각각 condition당1독립세션으로 CI·안정된 tail·우월성/절감 PASS를 부여하지 않는다.

- 출력·backend·시간 순서·lane/실제overlap·warmup/호출 분모·기록 연속성·환경이 적격해야 한다. power 주요구간 coverage≥95%, gap>2.5초는 적분하지 않음. AP 관측 누락≤5%, gap≤10초, clock 반폭≤2초. baseline 위 AP 신호≥0.3°C가 없으면 열 보정 적격성을 미확정으로 중단한다. BAT 등 평평한 센서는 미식별로 남긴다. 이는 수집 적격성이지 정확도 기준이 아니다.
- 전류는 단위 가설을 유지하고 counter 양자화/유효 변화 개수·분할 창을 별도 보고한다. 전하량도 외부 참값이 아니다. 단위 모호성을 없애기 위한 임의 fitting은 없다.
- 동일 작업량 persist 완료까지 J/시간, 공통480초 J/완료량, 냉각 포함 J/잔열을 분리한다. 급한 응답은 예정 도착→output_ready, 일반은 persist_complete. UX deadline은 미정이므로 새 위반율을 꾸미지 않는다. 고정 batch의 긴 queue 지연을 실제 사용자 분포로 해석하지 않는다.
- AP peak/상승폭 및 **자기 세션 resident baseline AP 중앙값 위 degree-seconds**를 사전 열 부담 지표로 쓴다. 손상/표면 안전 임계값이 아니다. interval별 actual lane점유/host API overlap과 one-lane tail/idle의 조건부 에너지를 분리하고 병행 W를 단독합으로 만들지 않는다.
- 개발4세션 적격성 뒤 condition별 구간 평균전력·AP 경험적 시작/끝/peak와 모든 입력 hash를 동결한다. 확인4세션은 동결 예측값과의 signed/absolute 오차를 보고하며 재보정하지 않는다. 실용 정확도 margin은 미확정이므로 정확도 PASS 없이 descriptive 결과만 남긴다. 적격 실패 시 남은 확인은 소비하지 않는다.
- 성공해도 지원 범위는 관측된 두 역할/배정/직렬순서/동시시작/단일 workload/잔열뿐이다. 현재 PC 에너지 모형의 새 연결과 정확도 수용은 별도 판독이 필요하다. `experiment_ready=false`는 수집 완료만으로 바뀌지 않는다.

## 실행 준비와 재현

도구: [PC 계획/검증/분석](../tools/d1_energy_collection.py), [승인 후 bounded host](../tools/d1_energy_collection_device.py), [관련 Python 테스트](../tools/test_d1_energy_collection.py). 새 APK와 프로젝트 서명·source/manifest hash는 외부 계획과 검증 receipt로 결합한다. 기존 APK/소비계획을 덮어쓰지 않는다.

정확한 최종 준비 경로와 검증 대상은 [공유 준비 결과](results/energy_thermal_collection_prep_02/README.md)를 따른다. 해당 PowerShell의 `-Action Check`는 서명 검사와 PC dry-run뿐이며 ADB/가상 실측/registry 생성을 하지 않는다. **`-Action Run -Approved -Serial ...`은 새 예산 승인 후에만 실행한다.** 현재 실행 상태는 미실행이다.

실행 전 동일 A24 serial/fingerprint, 현재 설치본 package/version/서명/hash, 배터리≥20%·비충전·battery≤35°C·thermal0·memory·Awake/interactive·brightness81/manual/기존timeout 설정을 다시 확인한다. 설정 변경·화면 깨우기·사용자 잠금 해제 우회는 없다. 환경이 다르면 변경해 강행하지 않고 중단한다. APK동일성 확인 전 collection 시작 금지, 수집 중 재설치 금지다.
