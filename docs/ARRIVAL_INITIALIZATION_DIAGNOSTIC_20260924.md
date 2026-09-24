# ARRIVAL-INIT-DIAG-01 — runtime 초기화 단일 진단

## 2026-09-24 승인 실행 종료 — complete_not_cause_resolved

- 사용자 승인으로 `72b3264a77325f1370048665cbfdde86823eebab` clean에서 동결 RUN_AFTER_APPROVAL.ps1을1회 실행했다. d8dfec3 이후 문서4개만 변경됐고 source/plan/manifest/APK/서명 검사가 일치했다. 기존 PC 시험/빌드는 반복하지 않았다.
- **claim1·설치1성공·세션1완료·실패0·미시도0·runtime4시작/4반환·warmup0·명시적추론0·retry/대체/추가0.** 전체209.047초/600초, 예산·timeout·gate 변경 없음. 이 계획은 소비·종료되어 아래 명령의 재실행은 금지한다.
- 동일SM-A245N/fingerprint·서명 확인, 설치 후 정확한 후보 APK/package/version1 확인. 배터리73%·충전분리·30.3°C·thermal0·프로세스 부재 gate, 네 생성 직전 memory admission 모두 통과. 앱 삭제/데이터 초기화 없음.

| runtime(고정 순서) | Java worker thread | journal start→return sequence | 생성 구간 초 | 상태 |
|---|---:|---|---:|---|
| classification_CPU | 107 | 3→12 | 0.384480 | 반환 확인 |
| classification_GPU | 108 | 16→31 | 2.706603 | 반환 확인 |
| detection_CPU | 107 | 35→44 | 4.144036 | 반환 확인 |
| detection_GPU | 108 | 48→63 | 9.608260 | 반환 확인 |

동기 I/O 포함 진단 구간이며 서비스시간·보정값으로 사용하지 않는다. setup thread99의 마지막 이벤트는seq67 cleanup succeeded다. journal68개 완전 기록, 앱 파일5개 회수/hash 대조, OS 증거5명령 회수 성공. timeout·취소·회수실패 없음. 앱 cleanup completed/error=null과 별도 host force-stop/프로세스 부재/thermal0을 확인했다. awaitTermination 개별 완료시각은 기록되지 않았다.

manifest의 빈warmup/requests·setup_only 반환·warmup_trace=[]·호출event/result0으로 앱 명시적 호출0을 확인한다. 라이브러리 내부 compile/prepare 연산0 또는 실제GPU kernel 추론 검증은 아니다. decision_trace records=[]/complete=false는 비평가 경로의 상태이며20null/experiment_ready=false 유지.

현재 PID22563의 준비 로그와 journal이 부합하며 수집 범위에서 이번 native/Java crash 증거는 없다. crash buffer는09-19 PID27217의 과거 오류다. 현재 libEGL context/선택적gms_client 미로드 메시지는 보존하되 뒤이어 생성이 반환됐으므로 과거 실패 원인으로 단정하지 않는다. **CAL-02의125초 대기 소진은 재현되지 않았고 원인은 미확정**이다. 단일 성공은 원인 해결·반복 안정성·시간 보정 완료가 아니다.

로컬 전용 근거: `C:/Users/LG/Documents/D1Check_Arrival_Extension/runtime_initialization_run_v1/`의 `FINAL_REPORT.md`, 원본 `FINAL_RECEIPT.json`, `POST_RUN_VERIFICATION.json`, `artifact_assessment.json`, `partial/`, `pre_cleanup_evidence/`, `host_cleanup.json`. registry `runtime_initialization_registry/ARRIVAL-INIT-DIAG-01/closed.json` 보존. 기존FAIL·fixed-split 부분 결과·CAL 중단/불확실 소비량 불변.

다음 최소 행동은 PC에서 CAL-02와 이번 setup_only의 단계 경계를 대조해 남은 가설과 필요한 별도 진단 범위를 정리하는 것이다. 추가 실측/기존계획 재개는 자동 수행하지 않는다.

후속 PC 비교와 첫warmup 전용 후보는 [ARRIVAL-WARMUP-DIAG-01](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md)에 기록한다. 이 성공 계획은 계속 소비·종료 상태다.

## 이하: 실행 전 준비 계약과 검증 이력

아래 미승인/출력 없음 등의 표기는 준비 당시 기록이다. 위 승인 실행 결과가 현재 상태이며 원 계획·준비 receipt를 소급 수정하지 않았다.

2026-09-24. **APK·계획·manifest·실행 CLI·PC 검증 완료 / 실행 승인 대기 / 실기기 미검증.** 시작은 `feature/arrival-scheduling-20260923` / `6a63e39b6dbdedf13f4b3899a9137311a3f40b0d` / clean이었다. 요청에 언급된744cd75 이후의 S26 협업 문서를 유지했다. [기존 PC 원인 조사](ARRIVAL_FAILURE_DIAGNOSIS_20260924.md)를 반복하지 않고 실행 준비에 필요한 코드만 확인/보완했다.

## 질문과 적용 경계

CAL-02의125초 host 완료 대기 소진 때 어느 생성/대기 단계까지 진행했는지 좁힌다. 네 runtime 생성 순서, CPU/GPU별 단일 worker, setup thread에서 submit→Future.get의 순차 동기화, 같은 worker에 close를 제출하는 구조는 그대로다.

1. classification_CPU
2. classification_GPU
3. detection_CPU
4. detection_GPU

새 `ArrivalRuntimeSetup.initialize`는 위 순서와 정확한4개 key를 검증하고 첫 실패에서 다음 생성을 하지 않는다. `setup_only`는 warmup/requests 배열이 모두 비어 있어야 하며 생성 뒤 **명시적으로 return**한다. warmup loop·arrival 발생·요청 실행은 진입하지 않는다. 기존 opt-out calibration 경로는 유지한다.

생성자 PC 확인: `ProbeTaskAdapter.init`는 labels·anchors 검사 후 `ProbeRawSession.create`를 호출한다. 후자는 options/compatibility/delegate/Interpreter 생성, allocateTensors, tensor 계약 검사를 수행한다. `validateTensors`는 tensor 이름/개수/shape/type/양자화 계약만 검사한다. 앱의 `execute`·`invokePrepared`·`runForMultipleInputsOutputs`는 생성 경로에서 호출하지 않는다. 라이브러리 내부 delegate compile·prepare·할당 과정의 연산까지 없다고 주장하지 않는다. API 내부 작업을 GPU kernel inference 횟수로 계수하지 않는다.

`failure_progress.jsonl`에 session/manifest SHA·monotonic timestamp·sequence·task/backend·thread ID, runtime_wait/runtime_create, labels_anchors·gpu_compatibility·gpu_delegate_construction/attachment·interpreter_construction·tensor_allocation/validation의 start/succeeded를 남긴다. 예외/timeout의 terminal과 부분 cleanup은 기존 실패 journal을 사용한다. 단계 내부 예외는 마지막 start와 상위 runtime 실패를 함께 해석한다. sync append+fsync는 기존 실행에 없던 overhead이며 재현 조건의 차이로 공시한다. CPU/GPU thread를 다른 executor로 옮기거나 생성 순서를 바꾸지 않았다.

동기 기록 때문에 **성능 보정/정책 평가 입력에서 제외**한다. `experiment_ready=false`·20 null은 유지한다. APK 설치 가능성, GPU 초기화 성공, 원인 해결은 PC PASS의 의미가 아니다.

## 정확한 예산과 단일 시계

| 항목 | 고정 상한/적용 위치 |
|---|---|
| 실행 시도 | 새 registry claim1. preflight 전에 claim하며 실패해도 재진입 금지 |
| 설치 시도 | 최대1, 기존 데이터 유지 `install -r`만 허용. 호출 직전 install_attempt 기록 |
| 세션 시도 | 최대1, am start 직전 session_attempt 기록. 설치/preflight 실패는 session0 |
| runtime 생성 | 최대4. journal runtime_create start는 생성 의도, succeeded는 adapter 반환. start만으로 완료를 인정하지 않음 |
| 명시적 warmup/모델 inference | 각각0. 이전 계획64/128 요청과 합치지 않음 |
| retry/대체/추가 | 모두0. output을 바꿔도 같은 registry/실험 ID 재사용 불가 |
| 전체 wall | 실행 함수 진입 T0부터600초. PC 실행 전 hash 검사 시간도 포함 |
| 작업 cutoff | T0+545초. 기기/서명 preflight·설치·설치본 확인·cooling·staging·Activity·완료 poll 포함 |
| 증거 회수 | 작업 종료 후 최대10초, 늦어도 T0+555초. OS 증거5초 + partial 파일5초 |
| host cleanup | 최대45초이며 절대 T0+600초를 넘겨 새 deadline을 주지 않음 |
| runtime 대기 | 각 Future.get30초, 첫 timeout에서 다음 runtime 생성 중단. 앱 내부120초 watchdog도 유지 |
| host 완료 poll | am start 반환 후 PID 조회부터125초. 전체 work cutoff와 둘 중 빠른 시각 적용 |
| Activity 시작 여유 | staging 뒤 work cutoff까지 launch30초+poll125초가 남지 않으면 session0으로 중단 |
| 앱 close | CPU/GPU 각5초 Future 대기, shutdownNow 후 각1초 종료 확인. 멈춘 worker의 close 완료를 무한 대기하지 않음 |
| cooling/환경 | 기존 최초120초, 배터리≥55%·분리 충전·온도≤35°C·thermal0·앱 프로세스 부재. 모델별 기존 V4 memory admission은 앱에서 생성 직전 필수 |

단계 timeout은 모두 남은 절대 예산으로 제한한다. apksigner/aapt2 PC subprocess도 실행 중에는 동일 deadline으로 제한한다. 기존 host cleanup API에 선택적 hard_deadline을 추가했으며 구 실행기의 기본45초 의미는 유지한다. 초기화/서명/전송이 느리면 남은 시간에서 시작을 거절하며 timeout이나 환경 gate를 완화하지 않는다.

정상 앱 해제(`cleanup.json`+journal)와 host 강제 종료/프로세스 부재(`host_cleanup.json`)를 구분한다. host cleanup이 성공해도 정상 native 해제의 증거는 아니다. process가 native 또는 I/O에서 정지하면 앱 finally를 보장할 수 없으며 host가 제한 시간 내 force-stop을 시도한다. 연결 실패 때 기기 종료 성공을 꾸며내지 않고 cleanup_error를 남긴다. OS/PC 로컬 디스크 자체 정지에 대한 엄밀한 실시간 보장은 없으며 파일 저장 실패 시 registry만 남을 수도 있다. 이 경우도 재실행하지 않는다.

## 후보 산출물과 동일성

아래 경로는 담당자 PC 로컬 전용이며 Git에 넣지 않는다. 공통 root: `C:/Users/LG/Documents/D1Check_Arrival_Extension/`.

| 산출물 | root 아래 상대 경로 |
|---|---|
| 새 계획 | `runtime_initialization_plan_v1/initialization_plan.json` |
| 새 manifest | `runtime_initialization_plan_v1/manifest.json` |
| 서명 APK | `runtime_initialization_apk_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk` |
| 빌드 출처 | `runtime_initialization_apk_v1/build_receipt.json`, `build_attempt.json`, `build.log` |
| PC 보고/서명/검증 | `runtime_initialization_pc_v1/FINAL_REPORT.md`, `FINAL_RECEIPT.json`, `apk_identity.json`, `dry_run.json` |
| 승인 후 명령 파일 | `runtime_initialization_plan_v1/RUN_AFTER_APPROVAL.ps1` |
| PC 검사 명령 파일 | `runtime_initialization_plan_v1/PC_CHECK.ps1` |
| 실행 출력(현재 없음) | `runtime_initialization_run_v1` |
| 소비 registry(현재 없음) | `runtime_initialization_registry/ARRIVAL-INIT-DIAG-01` |

Plan SHA-256: `bbb2d6428056af88abc7f0a88fda461c01fea045f8ccb9db55a78919cdcbaf78`.

APK SHA-256: `9af4f9ba89236702330ea57763066827116112a73353b4bb7ff668bc7631431c`.

SDK apksigner PC 검증: package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1, signer SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 기존 프로젝트 전용 서명 환경으로 격리 빌드했으며 보존된 설치본의 인증서/package/version과 일치한다. 키 생성/복사/재생성 없음, 키·비밀번호를 문서/Git에 포함하지 않는다. **현재 기기 설치본은 이번에 조회하지 않았으므로 실행 직전 재확인한다.** APK ZIP에는 기존 legacy MobileNet asset만 있고 외부 EfficientNet/EfficientDet는 포함되지 않았다.

부모 CAL-02 plan SHA `31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6`와 첫 실패 session을 새 plan에 연결했다. 부모 plan/manifest를 read-only template로 쓰되 새 session UUID·APK hash·실험 ID·root/registry·source identity로 분리한다. 이전 stopped/consumed 상태는 변경하지 않는다. 동일 외부 모델·labels·anchors·대표 입력 identity, CPU thread1, XNNPACK/LiteRT1.4.2/GPU profile/compatibility gate를 재사용한다. 입력 파일은 준비/identity 확인용이며 warmup/추론에는 사용하지 않는다.

## 실행과 판독

현재 실행 승인은 없다. 준비 완료 후 별도 승인과 실제 serial/환경 gate를 만족할 때만 아래 **구현된** 명령을 사용한다. 설치·세션이0이어도 claim 후 실패한 계획은 재실행하지 않는다.

```powershell
# PC 전용: ADB·설치·앱 실행 없음
python -B -m tools.d1_arrival_initialization check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/runtime_initialization_plan_v1/initialization_plan.json

# 별도 실행 승인 후에만: 실행 당일 확인한 A24 serial을 전달
& C:/Users/LG/Documents/D1Check_Arrival_Extension/runtime_initialization_plan_v1/RUN_AFTER_APPROVAL.ps1 -Serial '<현재 A24 ADB serial>'
```

RUN script의 실제 CLI는 `python -B -m tools.d1_arrival_initialization run --plan ... --adb ... --serial ... --expected-plan-sha256 bbb2d6428056af88abc7f0a88fda461c01fea045f8ccb9db55a78919cdcbaf78 --approved-experiment ARRIVAL-INIT-DIAG-01`이다. 새 wrapper나 수동 Activity 실행으로 cap/claim을 우회하지 않는다. `prepare`는 PC 후보 생성, `check`는 signature/source/input/manifest 검사이며 모델 호출/가상 실측 산출물을 만들지 않는다.

- preflight: 같은 SM-A245N/fingerprint·단일 연결, 현재 설치본 회수/서명 비교, 배터리/thermal/프로세스 부재. 시스템 메모리는 참고 snapshot으로 보존하고 앱 생성 직전 기존 memory admission을 실제 gate로 적용한다. 설치 후 다시 회수한 APK hash·package/version/signer가 정확한 후보와 일치해야 한다.
- 재사용한 signature_preflight/installed_identity 내부 receipt의 install0/session0·`PREFLIGHT_COMPATIBLE_NOT_INSTALLED`는 **해당 읽기 전용 검사 자체**의 동작이다. 새 실행 전체의 소비량은 root의 install_attempt/session_attempt/FINAL_RECEIPT 및 execution_claim으로 판단한다. 새 계획에는 calibration phase가 없으며 generic receipt의 phase_consumed=false가 실행 claim 미소비를 뜻하지 않는다.
- 완료/timeout/예외 뒤 cleanup **전**에 기존 `ps -A`, 가능하면 PID의 `ps -T -p`, PID logcat, crash buffer, ApplicationExitInfo를 회수한다. 명령당2초·전체5초·파일당256KiB 한도를 유지하며 누락/절단/권한 실패를 표시한다. 이후 journal·manifest·cleanup/failure 등의 partial 파일을 최대5초 회수한다. 회수 실패는 host_error의 앱 상태 unknown과 별도 기록이다.
- 추가 권한/root·debugger·Perfetto·stack dump 도구는 요구/실행하지 않는다. thread 목록은 native stack이 아니다. 해당 기기에서 `ps -T`/exit-info 접근 가능성은 미검증이며 실패해도 root 권한으로 우회하지 않는다. 로그 시각은 Android logcat과 monotonic journal의 다른 시간 축으로 구분한다.
- 앱 완료 판독: 정확한4개 runtime의 순서/각 반환·admission, backend별 thread 일치, setup_only 성공, 정상 cleanup, 오류/호출 event 없음, 입력 manifest identity가 있어야 `SETUP_COMPLETED_NOT_CAUSE_RESOLVED`다. host cleanup까지 확인한 종료는 `complete_not_cause_resolved`다. 이는 GPU kernel 실행 검증이나 과거 실패 해결을 뜻하지 않는다.
- prefix만 있으면 start 의도/반환 수·마지막 확인 단계·미확인 범위를 별도 보고한다. 예: 두 반환+세 번째 start는 세 번째가 끝났다는 증거가 아니다. 모델 파일 확인·delegate 준비·native compiler 내부 중 어떤 원인인지는 추가 로그 없이 확정하지 않는다. warmup0/명시적 inference0은 이 APK/manifest의 차단 계약에서 나오며 라이브러리 내부 연산0 주장이 아니다.
- preflight 실패·설치 실패·session 실패·capture/recovery 실패·host cleanup 실패는 개별 파일과 FINAL_RECEIPT로 구분한다. local 저장 자체 실패로 FINAL_RECEIPT가 없어도 claim이 남아 재실행은 차단된다. 이 경우 원본 회수/종료 여부 확인부터 별도 판단한다.

## PC 검증과 보존

2026-09-24, `6a63e39`+이번 미커밋 소스 대상으로 **Kotlin5·Python15 PASS**, modelProbe 관련 컴파일·격리 APK assemble PASS, plan/manifest/signature/input dry-run PASS. source SHA·명령·시점·시험 XML/로그는 외부 FINAL_RECEIPT에 결합한다. 기존 원인 조사·실험 분석·전체 테스트는 반복하지 않았다.

- Kotlin5: setup-only 반환/0호출/정렬 순서, 잘못된 호출 배열 차단, 중간 생성 예외 후 다음 생성 없음, 실제 Executor의 정지 worker에 대한 close timeout과 thread 소유권, legacy 경로 계속 실행. native delegate는 mock/미실행이다.
- Python 신규8: prepare/check의 무Device·0호출, single-use claim, 찢긴 journal/부분 생성·미확인 범위, 완전 생성과 GPU 검증 구분, cleanup 절대 deadline, 서명 subprocess 공유 deadline, host125초/회수 실패/cleanup 분리, preflight 실패의install0/session0·재실행 차단. 서명 경계 변경 관련 기존7도 통과했다.
- APK 생성3분36초, 관련 Kotlin 시험1분12초는 PC 실행시간이며 기기 예산에 합치지 않는다. 실제 기기 시도/설치/runtime 생성은 모두0이다. 이전 불변 journal 테스트/전체 회귀를 반복하여 새 GPU 초기화 검증으로 주장하지 않는다.

실행 전 남은 조건은 **별도1세션 승인**, 실제 연결·동일 기기/fingerprint·현재 설치본 서명 및 환경 gate, 새 출력/registry가 미소비 상태라는 확인이다. 기존 A24 FAIL·fixed-split 부분 결과·CAL-02 실패와 호출 수 불확실성, NPU 협업 경계는 그대로다. push·merge·ADB·기기 실행은 이번에 하지 않았다.
