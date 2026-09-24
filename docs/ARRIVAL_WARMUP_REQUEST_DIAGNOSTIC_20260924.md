# ARRIVAL-WARMUP-REQUEST-DIAG-01 — 전체 warmup에서 정규 요청까지의 단일 진단

2026-09-24. 시작 `3130f0199f99c319ee80e30e5b2307f477302d42`, `feature/arrival-scheduling-20260923`, clean. **PC 준비 작업이며 기기 실행은 별도 승인 전 금지**다. 초기화/첫 CPU warmup의 성공은 CAL-02 원인 해결이 아니다. [첫 warmup 결과와 과거 코드 차이](ARRIVAL_WARMUP_DIAGNOSTIC_20260924.md), [초기화 성공](ARRIVAL_INITIALIZATION_DIAGNOSTIC_20260924.md), [CAL-02 실패](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md)를 보존한다.

## 확인한 순서와 이번 최소 범위

CAL-02 보존 계획 `timing_calibration_recovery_plan_v1`의 첫 manifest와 Activity를 대조했다. 실제 과거 호출수는 기록 누락 때문에 여전히 미확인이다. 아래 순서는 **소스·계약의 예정 실행 순서**이며 CAL-02가 모두 실행했다는 뜻이 아니다.

| 순서 | CAL-02 경로 | 직접 관측한 범위 | 새 진단 |
|---|---|---|---|
| 초기화 | classification_CPU → classification_GPU → detection_CPU → detection_GPU | setup_only 및 first_warmup 각각4개 반환 | 새 프로세스에서4개 다시 생성, 예산 포함 |
| warmup1–2 | classification_CPU 2회 | 별도 first_warmup에서 첫1회만 반환 | 두 회 모두 단계 기록 |
| warmup3–4 | classification_GPU 2회 | 이번 진단 계열에서 미관측 | 두 회 모두 단계 기록 |
| warmup5–6 | detection_CPU 2회 | 미관측 | 두 회 모두 단계 기록 |
| warmup7–8 | detection_GPU 2회 | 미관측 | 두 회 모두 단계 기록 |
| 정규 요청 | 첫 CAL-02 조건: classification/urgent/GPU, offset0/5/10/15초의4건 | CAL-02에서0~4건 미확인 | **첫1건(offset0)만** 동일 condition·입력으로 실행 |
| 완료 | output_ready → persist_complete → worker_release 표식 → event 저장 → callback/lane 재사용 | CAL-02 정규 요청에서는 불명 | 첫 정규1건의 전체 경계와 cleanup 확인 |

정규1건은 warmup 루프 이후 environment admission, scheduled arrival→dispatch queue→GPU worker, adapter 반환→출력 저장→scheduler callback 전이를 확인하기 위한 최소 수다. 이미 warmup에서 네 task/backend를 모두 호출하므로 정규 요청에 조합을 추가하지 않는다. normal 응답 분기·다른 정규 task/backend·반복 도착·큐/병행을 이 한 건으로 검증했다고 하지 않는다. 첫 요청 후 도착을 추가하지 않는 것이 원 CAL-02와의 의도된 차이다.

## 발견한 관측 공백과 최소 보완

- 일반 warmup 루프는 worker의 호출 시작/끝만 journal에 남기고 제출 대기와 adapter 내부 mark를 전달하지 않았다. 새 `warmup_and_request` scope에서만 `warmup_wait`(setup)·`warmup`(해당 worker)·input_preparation/host_inference/output_readback/output_decode를 연결했다. 생성·warmup 순서, CPU/GPU executor 소유권, submit/get30초를 유지한다. helper 추출은 순서/동기화 변경이 아니다.
- 정규 요청의 adapter 내부 단계, 제출/worker 진입, 출력/저장, event 저장과 lane callback을 journal에도 남긴다. phase recorder는 원래대로 보존하고 성공 시 기존 Python trace replay로 선택 없는 판단까지 검증한다. journal의 `decision_wait`는 무선택 발생 표식이지 완전한 입력 snapshot이 아니다. 실패로 RAM decision_trace가 사라지면 전체 정책 재생은 미확인으로 남긴다. 이 고정 GPU 진단에서 적응형 결정을 검증하지 않는다.
- 기존 `worker_release_ns`는 event 저장 **이전**의 worker 종료 준비 표식이다. 실제 executor idle 시각으로 소급 해석하지 않는다. 새 `event_commit start/succeeded`가 그 뒤 저장 구간을, `lane_available observed`가 dispatch callback에서 recorder AVAILABLE 및 busy=false로 바뀐 직후를 구분한다. callback 표식도 CPU/GPU OS thread가 물리적으로 완전히 멈춘 시각은 아니다. 같은 worker에 다음 작업을 넣는 기존 직렬 executor 소유권은 그대로다.
- 진단은 fsync journal을 사용한다. 정상 경로는 이전 생성 prefix65 + warmup96 + 요청/환경/종료 약30개로 약191개가 필요하여, **새 scope만256개 상한**을 사용한다. 기존 scope128은 보존한다. event당8KiB/최대256개, lock50ms·sticky 저장 실패/overflow 시 후속 호출 차단. native crash/강제 종료에서 finally나 마지막 mark 저장을 보장하지 않는다.
- 제한된 회수 시간에는 manifest→journal→cleanup을 우선한다. 나머지 자료가 회수되지 않으면 회수 실패/불완전과 앱 성공 여부를 분리한다. 안전 cleanup을 위해 회수10초를 늘리지 않는다.
- journal의 제출/start는 호출 의도다. 완료 mark가 없으면 완료로 인정하지 않는다. 사후 실제 완료시각을 당시 입력으로 사용하지 않는다. host monotonic, Android elapsedRealtimeNanos, logcat wall clock을 교차 차감하지 않는다. host_inference는 host API 경계이며 GPU kernel 시간/실행장치 검증이 아니다.

CAL-02에는 이 durable 기록이 없었고, setup_only에는 warmup이 없으며, first_warmup에는 최초1회 뒤 return이 있었다. 새 진단은 기록량·fsync 부하가 증가한다. 이 차이가 실행 조건을 바꿀 수 있으므로 간헐적 문제의 원래 재현 조건과 같다고 하지 않는다. 과거 ProbeRawAdapter Git blob↔working-tree hash 대응 미확인도 그대로다. 원인을 고친다는 추측성 runtime 수정은 없다.

## 제안 예산·시간·중단 규칙

| 항목 | 승인 요청할 상한 |
|---|---|
| 실행 claim / 설치 / 세션 | 각각1회, 새 프로세스, 데이터 유지 update만 |
| runtime 생성 | 4회, resident4·CPU thread1·동일 두 모델/입력/LiteRT1.4.2 |
| warmup | 8회, 위 고정 순서로 각 task/backend2회 |
| 정규 진단 요청 | classification/urgent/GPU1건, persist_all, 평가요청0 |
| 명시적 추론 총수 | **9회 = warmup8 + 정규 요청1**, library prepare 내부 연산 별도 |
| retry / 대체 / 추가 | 각각0 |
| 전체 | **600초 = 작업545 + 증거 회수10 + cleanup45** |
| 개별 timeout | runtime/warmup Future30초, 앱 onCreate watchdog120초, am start30초 후 host poll125초, 요청 drain100초, 기존 close5초/worker |
| 환경 | 같은 A24/fingerprint/현재 설치 서명, 시작 battery≥55%·충전 분리·≤35°C·thermal0·앱 부재, runtime/요청 admission·기존memory gate, cooling120초 |

예상 운영3~6분, 최대10분. 이전 실행181/209초는 설치·cooling·회수 포함 관측이며 새 warmup7개/정규1개의 시간 예측 표본이 아니다. 각 대기 상한의 단순 합은 앱120초보다 길다. **모든 최악 지연을 끝까지 기다리는 계획이 아니라 기존120초 내 완료 또는 마지막 진행 구간을 확보하는 진단**이다. 완주 가능성/성공 확률은 보장하지 않는다. 부족하면 새 작업을 시작하지 않고 종료하며 timeout/gate를 연장하지 않는다. host는 launch30+poll125초 여유가 없으면 Activity를 시작하지 않는다.

execution claim은 preflight 전에, 설치·세션 시도는 명령 직전에 소비한다. 앱 미실행 gate 실패와 설치 실패를 구분한다. 세션 시작 뒤 증거가 부족하면 warmup0~8·정규0~1·추론0~9 범위를 보존한다. 반환 증거가 있으면 하한만 높이고 계획값을 성공값으로 채우지 않는다. 실패/timeout/연결단절/기록손실 후 같은계획 재진입 금지. 과거 종료 CAL/fixed-split/진단 계획과 분모를 합치지 않는다.

## 판독과 성공 후 남는 필수 검증

- 성공은 네 생성/8warmup/1정규 호출 각각의 순서·ID·worker·내부 단계 반환, output_ready/저장/event/callback, 정상 trace replay와 같은시계의 요청 경계, 앱 및 host cleanup/회수까지 모두 확인돼야 한다. 상태는 `WARMUP_REQUEST_COMPLETED_NOT_CAUSE_RESOLVED`다.
- runtime start만 남으면 생성 내부 마지막 확인 단계, warmup_wait만 있으면 executor 진입 전후, input/API/output 단일 start만 있으면 해당 구간 미완료로 판독한다. diagnostic 반환 뒤 persist/lane mark가 없으면 저장·callback 경계로 좁힌다. 마지막 GPU 로그를 원인으로 단정하지 않는다. PC fault injection은 native/GPU 성공·crash 복구 검증이 아니다.
- **성공하면 별도의 시간 보정 계획 준비로 넘어갈 수 있다.** 순서·필수 기록·정규 요청의 경계/cleanup에 불일치가 없고 환경/identity gate가 확인돼야 한다. 동기 journal을 제거한 성능 수집 경로의 계측 완전성과 8개 task/backend/priority 조건, N/A/missing·개발→동결→확인 분리·반복 예산은 새 보정 계획에서 확인한다. 종료한16세션 계획을 재사용하지 않는다.
- normal 완료 분기/다른 정규 조건은 새 보정 계획의 개발 수집에서 함께 확인할 항목이지 자동으로 개별1세션 진단을 추가할 이유가 아니다. 구체적 결함이 새로 드러날 때만 별도 진단을 설계한다. 작은 성공1회는 안정적 tail·병행 간섭·정책 우수성·과거 원인 해결을 증명하지 않는다.
- 20개 null/experiment_ready=false, 기존198요청 FAIL/fixed-split 부분결과·원본/모든 소비 계획을 보존한다. 동기 진단값을 추정값으로 채우거나 새 독립 검증으로 재사용하지 않는다.

## 준비 파일과 실행 명령

외부 PC 전용 root: `C:/Users/LG/Documents/D1Check_Arrival_Extension/` (GitHub 미포함).

- `warmup_request_apk_v1/`: 격리 build APK·source_snapshot·build_receipt.
- `warmup_request_plan_v1/`: initialization_plan.json·manifest.json·PC_CHECK.json·RUN_AFTER_APPROVAL.ps1.
- `warmup_request_pc_v1/`: PC 검증 로그·FINAL_REPORT/FINAL_RECEIPT·Git 종료 기록.
- 승인 후에만 생성: `warmup_request_run_v1/`, registry `runtime_initialization_registry/ARRIVAL-WARMUP-REQUEST-DIAG-01`.

```powershell
# PC identity/dry-run만. ADB/설치/추론/가상 실측 생성 없음.
python -B -m tools.d1_arrival_initialization check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/warmup_request_plan_v1/initialization_plan.json
# 아래는 새 실행 승인을 받은 후에만 실행. 이번 작업에서는 실행하지 않는다.
& C:/Users/LG/Documents/D1Check_Arrival_Extension/warmup_request_plan_v1/RUN_AFTER_APPROVAL.ps1 -Serial '<실행 당일 유일한 A24 serial>'
```

현재 설치본의 서명·기기·환경은 이번에 조회하지 않았다. PC 인증서 일치는 실제 업데이트 설치 성공을 보장하지 않으며 실행전 preflight를 생략할 근거가 아니다. 새 APK를 기존 APK와 별도 경로에 보존하고 키/비밀번호/모델 바이너리는 공유하지 않는다.

## PC 준비 완료·검증 대상

2026-09-24, 시작HEAD3130f01+이번 관련 변경으로 Kotlin19건/Python24건 PASS, 관련 modelProbe 컴파일·격리 APK assemble PASS, SDK apksigner/aapt2 identity·prepare/check dry-run·PowerShell 구문 PASS. **ADB/설치/앱/추론 실행0**, run/registry 부재를 확인했다. 기존 전체 시험/감사 반복은 하지 않았다. 초기 빌드는 SDK 환경 누락, 다음 빌드는 기존 journal.open 호출 호환성 오류로 실패했고 환경 지정/overload 보존 후 통과했다. Python 추가 validator의 tuple/list 오류1건도 수정 후 통과했으며 실패 이력을 PC receipt에 보존한다.

| 산출물 | 고정 identity |
|---|---|
| plan SHA-256 | `0100c50eeec461011850b205546914957c0aba0f6fff21f239b186d391cb853d` |
| manifest SHA-256 | `66e97c8a884dfff21eebd4bc07dd32e1a6e5e8d46efd718e5d88a003425be7ad` |
| APK SHA-256 | `9019b85d527fcbcd49e49741bf1fd1bcb274281434032f13dc60bb471e2bf2c0` |
| session | `ade06a05-c31c-5680-8d89-1c194235ce56` |
| package/version | com.example.d1check.benchmarkrunner.modelprobe / 1 |
| signer SHA-256 | b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565 |

APK 상대 경로는 `warmup_request_apk_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`다. 기존 프로젝트 전용 키를 로컬 환경으로만 참조했다. APK에는 계약 EfficientNet/EfficientDet 바이너리를 포함하지 않았고 key/model/raw는 Git에 추가하지 않는다. 정확한 현재 source bytes를 새 source_snapshot으로 보존했다.

검증 범위는 전체8warmup 순서/각 위치 fault 후 중단, 대기 timeout·유한 close,256 overflow/sticky 기록 실패, 완전·부분 journal의 구분과 잘린 모든 prefix, 잘못된 worker/추가 inference/저장·lane mark 누락, host 성공/미확인 소비량과 회수 우선순위다. 기존 두 완료 진단은 새 host 판독기에서도 같은 상태로 해석됐다. 이는 호환성 확인이며 과거 원인 재조사/성능 재검증이 아니다. Activity/native runtime의 실기기 동작과 새로운 단계 기록의 회수 가능성은 아직 미검증이다.

재현(PC만, 기존 root를 덮어쓰지 않고 새 격리 build root를 사용):

```powershell
python -B -m unittest tools.test_d1_arrival_initialization tools.test_d1_arrival_failure_evidence -v
# JAVA_HOME/ANDROID_HOME/ANDROID_USER_HOME은 기존 로컬 JBR/SDK/프로젝트 서명 환경으로 설정.
# D1_TIMING_BUILD_ROOT는 새 PC build root여야 한다.
.\gradlew.bat --no-configuration-cache --init-script tools/arrival_timing_isolated_build.gradle :benchmark-runner:testModelProbeUnitTest --tests '*ArrivalRuntimeSetupTest' --tests '*ArrivalFailureJournalTest' :benchmark-runner:assembleModelProbe -PenableModelProbe=true --console=plain
python -B -m tools.d1_arrival_initialization prepare --parent C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_recovery_plan_v1/calibration_plan.json --apk '<새 APK>' --build-receipt '<같은 source의 build_receipt.json>' --output '<새 PC 계획 경로>' --scope warmup_and_request
```

새 계획 후보는 **미실행·승인 대기**이며 앞선1회 진단 승인이나 과거16세션 예산을 전용하지 않는다.
