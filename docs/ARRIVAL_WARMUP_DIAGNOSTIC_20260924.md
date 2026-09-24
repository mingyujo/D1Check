# ARRIVAL-WARMUP-DIAG-01 — 생성 완료에서 첫 warmup으로의 전이 진단

## 2026-09-24 승인 실행 결과 — 완료, 과거 원인 미확정

실행 HEAD `38556fe53aa315b002af309885ceabe46ccaf2a9`, 작업 브랜치 clean에서 시작했다. 아래 PC 비교·미승인 후보 문구는 준비 당시 이력이며, 현재 이 계획은 **1회 소비 후 종료/no_resume**다. 실행전 mandatory identity 검사와 동일 A24·설치본 서명·환경 gate를 통과했고 준비된 script를 한 번 실행했다.

| 항목 | 실제 결과 |
|---|---|
| 설치/세션 | 업데이트 설치1 성공, 세션1 완료·실패0·미시도0 |
| runtime | classification_CPU → classification_GPU → detection_CPU → detection_GPU, 각각 start/return; 4/4 |
| 첫 warmup | classification_CPU1회, CPU Java thread106. 제출 직전 의도→worker 진입→입력 준비→host API 반환→output readback/decode→호출 반환 모두 기록 |
| 추론/평가 | 명시적 추론1은 위 warmup에 포함. 평가요청0, retry/대체/추가0 |
| 시간/종료 | host 전체181.0/600초, 기존545/10/45·wait30·watchdog120·host125 유지. 앱 cleanup과 host 종료/프로세스 부재 확인 완료 |
| 기록 | journal80개, partial5파일 크기/hash 일치, OS증거5명령 회수. 마지막 seq79 cleanup succeeded, setup Java thread98 |

현재 PID23909에서 crash/timeout/취소 증거는 없다. crash 버퍼 FATAL은9월19일 PID27217, 최신 exit_info는 직전 PID22563의 force-stop이며 이번 실패가 아니다. 회수 실패와 앱 실패도 관측되지 않았다. warmup_trace=[]은 특수 경로의 기록 방식이며 warmup0을 뜻하지 않는다. 실제 호출1은 journal start/return으로 확인했다.

Android 같은 monotonic clock의 session→cleanup journal 간격은3.425916308초이고 host181초와 다른 경계다. 동기 기록을 포함한 host_inference journal 간격37.068692ms도 공식 inference timer/성능 보정값 또는 GPU kernel 시간이 아니다. 과거 실행과 성능 개선률을 계산하지 않는다. GPU runtime 생성은 GPU 추론 검증이 아니며 출력 처리 반환은 품질 PASS가 아니다.

**CAL-02 원인 해결은 미입증**이다. 간헐적 초기화 문제를 기각하지 않으며 나머지7warmup/정규요청·dispatch/persist는 이번에 실행하지 않았다. 과거 ProbeRawAdapter Git blob↔working-tree hash 대응 미확인은 유지한다. 이번 후보 source103개 일치는 별도의 현재 identity 검증이다. 기존 FAIL·부분결과·종료계획·20null/experiment_ready=false 불변.

외부 root 아래 `first_warmup_run_v1/FINAL_REPORT.md`에 단계별 sequence/thread/시간·gate·판독을, `POST_RUN_VERIFICATION.json`에 검증 대상/hash를 기록했다. 원본은 같은 root의 `FINAL_RECEIPT.json`, `partial/`, `pre_cleanup_evidence/`와 registry closed에 있다. 로컬 외부 자료는 GitHub에 포함하지 않는다. 실행전 check/실행 script는 아래 명령과 같으며 **종료 계획 재실행용으로 사용하면 안 된다**.

다음 최소 행동은 PC에서 CAL-02의 두 번째 CPU warmup과 이후 GPU warmup의 미관측 경계를 정리하고, 필요한 경우 별도 최소 진단을 설계하는 것이다. 후속 기기 실행과16세션 보정 재개는 이번 결과에서 자동 승인되지 않는다.

## 이하: PC 준비 당시 비교·동결 계약

2026-09-24. 시작 `67e6b10d4a8ae7f2b67ec54012311b42dac2a131`, feature/arrival-scheduling-20260923, clean. **PC 비교·후속 실행 준비이며 실기기 실행은 미승인·미실행.** CAL-02 정지 원인 수정 완료가 아니다. [이전 성공 결과](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md), [CAL-02 실패](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md), [기록 보완](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md)을 보존한다.

## 실행 버전과 직접 증거

공통 외부 root(담당자 PC 전용, GitHub 미포함): `C:/Users/LG/Documents/D1Check_Arrival_Extension/`.

| 항목 | CAL-02 | setup_only 성공 |
|---|---|---|
| 실행 소스 checkpoint | b4cc659 | 72b3264 (실행 코드는 d8dfec3와 동일) |
| plan SHA | 31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6 | bbb2d6428056af88abc7f0a88fda461c01fea045f8ccb9db55a78919cdcbaf78 |
| APK SHA | 85c5fd0ab578d48e8af3e2abdda4c836939c5a330631d39dc4df61bd6d3e7ff6 | 9af4f9ba89236702330ea57763066827116112a73353b4bb7ff668bc7631431c |
| 세션 | 78ac4f07-821d-5722-b191-57433ee048b9 | 1d6f3933-3ea8-52ed-8236-a8470367adeb |
| 직접 원본 | timing_cal02_execution_v1/receipt·PID log·approved_phase.py, timing_calibration_recovery_development_run_v1 첫 세션 | runtime_initialization_run_v1/FINAL_REPORT·FINAL_RECEIPT·partial·OS증거 |

이번에 두 보존 APK의 실제 hash를 계획과 대조했다. Activity/TaskAdapter의 Git 소스는 두 계획의 byte hash와 각각 일치한다. **ProbeRawAdapter는 두 실행 모두 Git blob SHA와 계획의 원 working-tree SHA가 달랐고 단순 LF/CRLF 변환으로 일치하지 않았다. 원래 바이트 배열은 이번에 재구성하지 못했다.** 보존 Git 코드는 비교 참고이고 이 파일의 exact-byte 동일성을 새로 확인했다고 주장하지 않는다. 실행 당시 source gate 통과 기록/APK hash는 그대로 보존한다. 이를 손상이나 과거 정지 원인으로 단정하지 않는다. 새 후보는 현재 소스·build receipt·APK의 mandatory identity를 별도로 검사하며 이 공백을 이유로 완화하지 않는다. 선별 소스/diff·hash·시간 계산은 `warmup_transition_pc_v1/comparison_evidence.json`에 있다.

## 단계별 비교: 직접 관측과 코드/미관측의 구분

| 단계 | CAL-02 직접 확인 | setup_only 직접 확인 | 코드로 확인한 동작 | 여전히 미관측/한계 |
|---|---|---|---|---|
| 진입 | Activity COLD, PID19830, session_start11:34:15.153 | COLD, PID22563, journal session start | main Handler watchdog 등록 후 단일 setup executor | 과거 main/VM 정지 여부 |
| 생성 순서 | CPU/GPU delegate 로그가 순서대로 존재, 두 번째 GPU 준비 부근에서 관련 로그 종료 | C_CPU→C_GPU→D_CPU→D_GPU start/return 각각4 | sorted key, 단일 CPU/GPU worker, setup submit→get30초를 순차 실행 | 과거 네 번째 adapter 반환 여부; 마지막 GPU 로그는 완료/원인 증거 아님 |
| thread/동기화 | OS TID19878(CPU)/19882(GPU) 로그 | Java107(CPU)/108(GPU), setup99 | 생성·warmup·close는 같은 lane, Future.get의 happens-before로 adapter map 전달. 생성/warmup에 dispatch callback을 쓰지 않음 | Java ID와 OS TID는 서로 다른 식별자. 과거 native stack/lock 상태 없음 |
| 생성→warmup | warmup 완료·진입 기록 없음 | setup_only succeeded 후 return | CAL-02 warmup 전체 순서는 C_CPU×2→C_GPU×2→D_CPU×2→D_GPU×2로 총8이며 첫 호출은 classification_CPU. setup_only는 배열0·명시적 return | 과거 CPU 첫 warmup까지 도달했는지, 후속 warmup/요청이 시작됐는지 미확인 |
| 호출/후속 요청 | warmup0~8·진단0~4 실제 수 미확인 | warmup/추론0 명시적 차단 | warmup lane.submit→get30초 후 before_workload gate, 독립 도착/dispatch callback·latch 경로 | setup_only는 입력 decode/invoke/output decode/dispatch·persist 경로를 검증하지 않음 |
| 기록/lock | manifest만 원격/회수본에 존재 | journal68개·파일5개 | 과거 RAM→정상/finally flush; 이후 opt-in ReentrantLock50ms·append/fsync·상한128기록, sticky 오류 및 stop. 새 동기 I/O는 재현 조건 차이 | journal fsync/VM/native 정지에 finally 보장 없음; 새 관측 overhead가 과거 현상을 바꿀 수 있음 |
| watchdog | 종료 artifact 없음 | timeout 미발생 | onCreate의 main Handler postDelayed120초, 생성/호출/cleanup 포함. 진단은 별도 best-effort journal thread 후 kill, 구 경로는 watchdog 파일 후 kill | 지연 handler의 실제 실행 여부를 과거 자료로 판단 불가; 원인 해결 증거 아님 |
| host | 125초 poll 소진 뒤 파일 검증 실패, host force-stop | 완료poll 반환·OS증거·partial 회수·cleanup | 구 poll은 소진 후 묵시적 반환; 새 poll은 명시적 timeout. host125초는 am start 반환 후, 앱120초와 시작점 다름 | 총 host시간을 앱 timeout/초기화 시간과 혼동 금지 |
| 종료 | host cleanup·process부재 확인, 앱 cleanup 없음 | 앱 cleanup completed와 별도 host cleanup | lane close get5초, shutdown/awaitTermination 각1초. 새 lifecycle stop/interrupt와 durable catch 기록, 강제종료 가능 | 정상 close 반환과 native 자원/worker 최종 소멸시각은 동일하지 않음 |

두 실행 사이에 journal·runtime helper·세부 생성 mark·watchdog/lifecycle 실패기록·host 명시적 timeout/cleanup 전 회수가 추가됐다. 이는 관측 보완이고 CAL-02 특정 deadlock 치료의 증거가 아니다. 과거 host poll 진단 누락은 이미 수정됐으므로 다시 수정하지 않았다. 이번 비교에서 새로운 정지 원인을 확정할 결함은 발견하지 못했다.

## 시계와 시간 분리

- host monotonic 전체 **209.047초**: 동일성/서명·업데이트 설치·cooling120초·입력 전송·Activity·회수·cleanup을 포함한다. runtime 초기화 시간이 아니다.
- Android elapsedRealtimeNanos journal: session start→첫 runtime_wait **0.557823초**, 첫 runtime_wait start→네 번째 wait success **17.409608초**, session start→setup_only success **17.968992초**, session start→마지막 cleanup journal **18.045962초**.
- 네 runtime_create start→success는0.384480/2.706603/4.144036/9.608260초. 모델 open·초기화·동기 기록을 포함하며 host API 추론 시간이 아니다. 이 합계는 admission·submit·wait 전후 비용을 포함하는17.409608초와 다르다.
- CAL-02 logcat은 wall clock이며 생성의 완전한 monotonic 쌍이 없다. 두 실행의 초기화 속도 개선량을 계산하지 않는다. host·logcat·앱 시계를 서로 빼지 않는다. 동기 자료는 보정/성능 표본에서 제외한다.

## 가장 작은 후속 후보와 남은 가설

**네 runtime을 같은 순서로 생성한 뒤, CAL-02의 첫 classification_CPU warmup 한 번만 실행하고 종료**한다. setup_only 반복만으로는 미관측 frontier를 넓힐 수 없으므로 선택했다. 첫 CPU 호출이 성공해도 뒤 GPU warmup·두 번째 호출·정규 요청은 미검증이다. 이전의 간헐 초기화 문제도 한 번 성공으로 기각하지 않는다.

| 관측 | 구분에 도움이 되는 가설 | 확정할 수 없는 것 |
|---|---|---|
| runtime_create 반환 전 중단 | 초기화/기록 I/O/native 준비 구간 재발 | 마지막 stage 내부의 원인, GPU 인과 |
| warmup_wait start, warmup start 없음 | CPU executor 진입/대기/기록 단계 | native deadlock 확정 |
| input_preparation start만 있음 | 파일 검증·decode·resize·tensor 준비 | 어느 연산인지 세부 원인 |
| host_inference start만 있음 | host API 진입 직전~반환 사이 | start 의도만으로 실제 kernel 실행/완료 단정 |
| host_inference succeeded 이후 정지 | 출력 readback/hash/decode/반환/기록 단계 | GPU/CPU 품질 검증 |
| 첫 warmup와 cleanup 성공 | 이 조건의 첫 호출 전이·유한 종료 | CAL-02 원인 해결·나머지7warmup/4요청·반복 안정성 |

## 구현·기록 계약

새 manifest scope `first_warmup`, experiment `ARRIVAL-WARMUP-DIAG-01`이다. 기존 정책 ID 의미는 바꾸지 않는다. Activity는 requests0/warmup1/classification_CPU를 검증하고 전용 helper 후 return한다. 원래8warmup/4요청 calibration 경로·setup_only0/0은 유지한다. 부모manifest의 calibration_backend=GPU는 실패한평가slot의식별값을보존한것이며 이번warmup의backend가아니다. requests는비어있고유일한warmup model_key=classification_CPU와CPU executor가실제경로를고정한다. task와priority를동일개념으로취급하지않는다.

`ArrivalRuntimeSetup.runFirstWarmup`이 기존 CPU executor의 submit/get30초를 사용한다. journal의 warmup_wait는 setup thread, warmup 및 input_preparation/host_inference/output_readback/output_decode는 CPU worker다. 첫 오류 뒤 후속 호출 없음. 각 start는 의도이며 succeeded는 해당 API/함수 경계 반환 증거다. 공식 inference timer 내부에는 기록을 넣지 않고 직전/직후 진단 mark를 둔다. 따라서 공식 host API 경계는 보존되지만 동기 I/O가 실행 조건을 교란하므로 성능 수치를 사용하지 않는다. GPU kernel interval로 부르지 않는다.

output_readback succeeded 이후 raw hash/반환 객체 구성부터 output_decode start까지의 작은 구간은 별도 내부 이벤트가 없다. 그 위치에서 멈추면 adapter-level 미완료로만 해석한다. 성공 경로 journal은 약80개로 기존128개 상한 안이며 overflow/저장 오류는 중단·부분 기록을 보존한다. warmup_trace는 기존loop를 거치지 않아 비어 있을 수 있으므로 이 scope의 호출 근거는 durable journal이다. 최초 성공 응답이 있어도 정식 output 품질/정책 평가가 아니다.

기존 host 실행기를 scope에 따라 확장했다. 새 registry/UUID/root, mandatory source/APK/plan/manifest/input/signature binding, 미소비 gate와600초 단일 예산을 재사용한다. warmup/inference 실제 수는 실패 시null과0~1범위를 보존하고 계획1을 성공1로 채우지 않는다. 완료 이벤트·stage순서·request/lane identity·cleanup이 있어야 완료다. 과거 실행은 당시 Git 버전/원 계획으로 보존하며 종료 계획 재실행은 금지다.

## 제안 예산 — 실행 승인 전 금지

| 항목 | 상한/의미 |
|---|---|
| claim / 설치 / session | 각각1, 데이터 유지 update만 |
| runtime 생성 | 최대4, 기존순서/resident4/CPU thread1 |
| warmup | 최대1: 첫 classification_CPU 전이·호출 확인 |
| 앱 명시적 inference | 총최대1, 위warmup에 포함; 추가1이 아님 |
| 진단/평가 요청 | 0, persist workload·도착 정책 비교 없음 |
| retry / 대체 / 추가 | 모두0 |
| 전체 | 600초: 작업545·증거10·cleanup45 |
| timeout | runtime30·warmup Future30·앱120·host125, 연장 없음 |
| 환경 | 동일A24/fingerprint, 배터리≥55%·분리충전·≤35°C·thermal0·앱부재, 생성전기존memory admission, cooling120초 |

예상 약3~5분, 최대10분. 성공한 setup_only의host209초에 첫 호출≤30초를 고려한 운영 예상이며 확률/정밀도 보장이 아니다. 남은launch30+poll125초가 없으면session을 시작하지 않는다. preflight부터claim소비, 설치/Activity명령직전각시도소비, start기록만으로실제완료인정금지. gate/timeout/실패/연결중단/회수실패는한번종료; 부분증거최대10초후cleanup최대45초,동일계획retry금지. 다음실험으로자동확대없음.

## 준비 산출물·실행 명령

준비 검증 결과와 정확한 해시는 아래 완료 절에 기록한다. 외부root의 `first_warmup_apk_v1`, `first_warmup_plan_v1`, `warmup_transition_pc_v1`를 사용한다. 실행root `first_warmup_run_v1`와 registry `runtime_initialization_registry/ARRIVAL-WARMUP-DIAG-01`은 실행 전 없어야 한다. 과거 원본/receipt/registry는 변경하지 않는다.

```powershell
# PC 전용 identity/dry-run, ADB·추론 없음
python -B -m tools.d1_arrival_initialization check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/first_warmup_plan_v1/initialization_plan.json
# 별도 실행 승인 이후에만, 현재 미실행
& C:/Users/LG/Documents/D1Check_Arrival_Extension/first_warmup_plan_v1/RUN_AFTER_APPROVAL.ps1 -Serial '<실행 당일 유일한 A24 serial>'
```

실행 전 별도 승인과 최신설치본서명/기기/환경gate가 필요하다. 이번에는 ADB·설치·앱실행0. 기존 FAIL·부분결과·CAL-02의warmup0~8/진단0~4불확실성·20null/experiment_ready=false 불변. NPU/Band/EDF/간섭모형은 범위밖이다.

## PC 준비 완료 기록

2026-09-24, 시작HEAD67e6b10+이번 미커밋 변경 대상으로 확인했다. **Kotlin16(초기화/전이9·journal7), Python10, 관련컴파일·격리assemble·서명검사·prepare/check dry-run·script구문검사 PASS.** 실기기검증/실행0. 기존 전체시험/전체실험감사 반복 없음. v1 테스트3개는잘못된session/hash fixture, v2 테스트3개는JSONObject의Robolectric runner 누락으로실패했고테스트설정수정후v3 전체16통과. 초기실패로그도보존한다. mock/executor 검증은 native/GPU·Android lifecycle 실기기검증이 아니다.

| 후보 | 외부root 아래경로/identity |
|---|---|
| 계획 | first_warmup_plan_v1/initialization_plan.json |
| plan SHA | e6f99611ea329bbe7532de3cb8b949551a0f2aa63201ddfd12d3417679e6ad61 |
| manifest | first_warmup_plan_v1/manifest.json |
| manifest SHA | 6bfc038032b96b1a171e56012e24b381071cc2fcf3dc6c5294db7e3522c9dbf7 |
| 새 session | bfede527-5309-5603-8330-8a29b8dab3d8 |
| APK | first_warmup_apk_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk |
| APK SHA | 8c6d41aa2cc7f37011f791fed01cf10bf021754d190e53d4ed8c46f8d42c3b75 |
| SDK apksigner/aapt2 | package com.example.d1check.benchmarkrunner.modelprobe, versionCode1, signer b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565 |
| 빌드근거 | first_warmup_apk_v1/build_attempt.json·build_receipt.json·build.log·source_snapshot/ |
| 실행명령 | first_warmup_plan_v1/RUN_AFTER_APPROVAL.ps1 (구문만검사·미실행) |
| PC판정 | warmup_transition_pc_v1/FINAL_RECEIPT.json·comparison_evidence.json·kotlin_v3.log·시험XML·python_checks.json·old_artifact_compatibility.json |

프로젝트전용기존키는로컬환경으로만참조했고 키/비밀번호를복사/공개하지않았다. 보존설치본인증서와PC에서일치하지만 현재기기설치본은조회하지않았으므로실행직전preflight필수다. APK내EfficientNet/EfficientDet포함없음(기존legacy asset만). 새source snapshot으로현재APK출처의exact bytes를보존했다. 소비된계획과원본의hash불변을선별확인했다.

재생성/검증 명령(PC, 기존출력을덮어쓰지않으려면 prepare에는새빈출력root필요):

```powershell
python -B -m tools.d1_arrival_initialization prepare --parent C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_recovery_plan_v1/calibration_plan.json --apk C:/Users/LG/Documents/D1Check_Arrival_Extension/first_warmup_apk_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk --build-receipt C:/Users/LG/Documents/D1Check_Arrival_Extension/first_warmup_apk_v1/build_receipt.json --output '<새 PC 출력 경로>' --scope first_warmup
python -B -m unittest tools.test_d1_arrival_initialization -v
# Kotlin 실행에는 외부 격리 build root와 기존 프로젝트 서명환경 사용; 이전 완료결과를 반복할 필요 없음.
.\gradlew.bat --no-configuration-cache --init-script tools/arrival_timing_isolated_build.gradle :benchmark-runner:testModelProbeUnitTest --tests '*ArrivalRuntimeSetupTest' --tests '*ArrivalFailureJournalTest' -PenableModelProbe=true --console=plain
```

실행후판독은같은runner가수행한다. FIRST_WARMUP_COMPLETED_NOT_CAUSE_RESOLVED는생성4반환·순서/worker/requestidentity·warmup/API/출력단계반환·앱/hostcleanup이모두필요하다. start만남거나누락/오류가있으면중단상태와호출범위를보존하고재실행하지않는다. 이완료판정은독립품질/보정/정책우수성판정이아니다.
