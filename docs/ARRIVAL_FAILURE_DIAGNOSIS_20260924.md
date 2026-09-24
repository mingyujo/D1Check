# ARRIVAL-FAILURE-DIAG-PC-01 — CAL-02 정지와 기록 누락 분리

2026-09-24. 시작 `feature/arrival-scheduling-20260923` / `63f46581347eedf10d4e5f75b6df87e451486790` / clean. **PC 조사·코드 보완·관련 검증 완료, 정지 원인 미확정, 실기기 미검증.** 이번 작업에서 ADB·설치·앱 실행·실기기 추론·APK assemble·simulation은 실행하지 않았다. CAL-02 및 과거 중단 계획을 재개하지 않는다.

## 원본과 실행 버전

외부 공통 root는 `C:/Users/LG/Documents/D1Check_Arrival_Extension/`이다.

- 원래 종료 근거: `timing_cal02_execution_v1/FINAL_RECEIPT.json`, `approved_phase.py`, `session_pid_log.txt`, `crash_after_stop.txt`, `exit_info.txt`, `lifecycle_after_stop.txt`, `remote_after_stop.txt` 및 [기존 종료 보고](ARRIVAL_TIMING_CAL02_RESULTS_20260924.md).
- 실행/회수 근거: `timing_calibration_recovery_development_run_v1/00_78ac4f07-821d-5722-b191-57433ee048b9/`의 attempt·launch·error·recovery·host_cleanup, artifacts/partial의 manifest.
- plan SHA `31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6`; 보존 APK SHA `85c5fd0ab578d48e8af3e2abdda4c836939c5a330631d39dc4df61bd6d3e7ff6`.
- 조사 시작 시 Activity와 host runner는 동결 plan의 source hash와 일치했다. Git b4cc659/63f4658의 해당 코드도 줄바꿈을 제외한 내용이 일치한다. 실행 wrapper는 설치 직후 identity 검사를 추가한 보존 원문으로 대조했다. 서명 감사는 반복하지 않았다.
- 새 PC 근거 root: `timing_failure_diagnosis_pc_v1/`. `starting_evidence.json`에 선별 원본 hash·소스 일치·APK/plan hash를 기록했다. 기존 raw/receipt/APK/계약은 수정하지 않았다. 전체 원자료 재감사를 뜻하지 않는다.

## 확인 수준

| 문제 | 판정과 근거 | 아직 구분할 수 없는 것 |
|---|---|---|
| 실행 진입 | launch KST11:34:13.406550, Status ok/COLD, PID19830. session_start11:34:15.153 | 이후 모든 호출 수 |
| runtime 생성 | 첫 GPU OpenCL 성공 로그11:34:18.317/18.441, CPU 탐지 준비11:34:20.538, 두 번째 GPU 준비 부근 마지막 로그11:34:22.572 | 마지막 로그가 정지 원인이라는 인과 판단, 네 adapter 생성 완료 여부 |
| Java 예외/native crash | 이번 PID의 crash 증거 없음. crash buffer의09-19 예외는 다른 실행 | 로그에 없는 예외, native 정지·VM 정지·교착·장시간 초기화의 구분 |
| host timeout | 구 runner의125초 cleanup poll 소진 후에도 검증으로 진행해 decision_trace FileNotFoundError로 표시 | 앱 내부30초 Future.get와120초 main Handler watchdog이 종료 흔적을 남기지 못한 이유 |
| lifecycle/callback | 종료 기록은11:36:22.066 USER REQUESTED/FORCE STOP, host cleanup과 일치 | Activity 비가시성·main thread 지연이 원인인지 여부. lifecycle 로그만으로 확정 불가 |
| 기록 구조 | Activity.runSession은 environment/rows/timing/warmup을 RAM에 두고 정상 종료/finally에서 저장. runtime별 durable 진행 기록 없음. finally는 close 대기 뒤 trace 저장 | 실제로 어느 RAM 기록까지 있었는지. native crash/kill에서는 finally 보장 없음 |
| 회수 경로 | 실제 원격 목록·artifacts·partial 모두 같은 manifest 하나. 잘못된 경로만으로 설명되지 않음 | cleanup 전 thread 상태, 당시 RAM, 회수되지 않은 일시적 OS 증거 |
| cleanup |11:36:22.464389 완료, 프로세스 부재·thermal0. phase claim→cleanup315.995018초 | 사후 FORCE STOP 증거를 이전 native crash 증거로 사용할 수 없음 |

**정지 원인은 미확정이다. 기록 누락에는 확인된 구조적 취약점이 있다.** timeout을 늘리거나 GPU 초기화 성공을 가정하지 않는다. 이번 수정은 원인 치료 완료가 아니라 다음 실패의 관측 가능성을 높이는 변경이다.

## 소비량의 복원 한계

설치1 성공, 세션 시도1/16·완료0·기술적 실패1·미시도15, retry/대체/추가0을 그대로 보존한다. 실패 세션의 진단 실제 호출은 **0~4 미확인**, warmup은 **0~8 미확인**이며 완료 증거는 각각0이다. 나머지 진단60/warmup120은 미실행이다. 전체 계획 분모64/128을 유지한다. 추정값 동결/확인8 미실행,20 null, `experiment_ready=false` 불변.

새 PC CLI로 원래 manifest와 누락 journal을 읽어 `old_session_consumption.json`을 생성했다. `no_start_evidence`는 미호출 증명이 아니다. `within_valid_prefix_call_bounds`는 확보된 기록 범위의 수치이며 전체 실제 소비량은 `actual_call_bounds`를 사용한다. 시작 기록만으로 adapter 반환·응답 완료·저장 완료를 인정하지 않는다.

## 최소 코드 보완과 계약

### 앱: 명시적 실패 진단 전용

`ArrivalFailureJournal.kt`와 `ArrivalSchedulerActivity.runSession`의 명시적 opt-in 경로다. 기존 calibration protocol의 manifest에 다음 필드가 모두 있어야 하며 기존 manifest에 자동 적용하지 않는다.

```json
{
  "failure_diagnostic_contract": "arrival-failure-journal-v1",
  "failure_diagnostic_scope": "setup_only",
  "performance_excluded": true,
  "experiment_ready": false
}
```

이는 완성된 실행 manifest가 아닌 **추가 필드 명세**다. 나머지 모델·입력·APK·fingerprint·memory·thermal·timing 계약 검사는 유지한다. 별도 실행 plan/host CLI는 아직 준비하지 않았다. 기존16세션 실행 명령에 이 필드를 끼워 재실행하지 않는다.

- 기본 session identity 확인 직후 manifest와 `failure_progress.jsonl`을 생성한다. APK/gate 확인과 runtime 생성 전에 session start를 남긴다. 같은 경로의 기존 journal은 재사용하지 않는다.
- `runtime_wait`는 setup thread의 submit→Future 반환/timeout, `runtime_create`는 worker의 모델 open/adapter 생성 시작→반환/예외다. key는 task/backend를 함께 기록한다. admission 결과도 별도 기록한다. 기다림 timeout은 native 작업 종료를 뜻하지 않는다.
- `scope=setup_only`는 동일 네 resident runtime을 기존 순서(classification_CPU/GPU, detection_CPU/GPU)로 생성하고 종료하며 warmup/진단 배열을 빈 배열로 강제한다. 임의 추정값을 넣지 않는다. `scope=calls`는 기존4진단/8warmup 계약을 유지하되 각 adapter.execute를 별도 start/terminal 기록으로 감싼다.
- session/manifest SHA·sequence·monotonic 시각·thread·task/backend·request ID·stage/edge를 저장한다. `start`는 호출 전 durable **의도**이며 실제 native 진입 증명은 아니다. `succeeded`는 adapter 반환 증거다. 공식 output_ready/persist_complete 또는 GPU kernel 완료와 동일하지 않다.
- catch는 resource close 전에 session stopped를 기록한다. timeout/cancel/실패, 부분 초기화 cleanup 시작/결과를 구분한다. lifecycle 취소는 stop 신호와 setup interrupt를 보내며 native 중단을 보장하지 않는다. watchdog은 best-effort 별도 thread에 기록을 요청하고 기다리지 않고 kill한다. kill 직전 이벤트 저장을 보장하지 않는다.
- 기록은 append+fsync, 최대128개×각8KiB, detail1024자다. write 실패/lock50ms 초과/capacity 초과는 sticky failure로 이후 보호된 호출을 차단한다. cleanup은 계속 시도한다. 파일을 쓸 수 없으면 logcat에 실패를 mirror하며 disk와 logcat 모두 실패하면 기록 복구를 보장하지 않는다.
- fsync 자체에는 앱 수준의 유한 완료 보장이 없다. native crash/전원 손실/OS I/O 정지에는 host timeout과 bounded cleanup이 필요하다. prefix·찢긴 마지막 행을 구분한다. 마지막 end 저장에 실패하면 실제 반환했더라도 완료로 세지 않는다.
- 동기 I/O는 **성능 경로가 아닌 실패 진단**에만 적용한다. 비용은 runtime 대기/adapter 구간을 바꿀 수 있다. 이전 append 비용을 `previous_append_ns`로 기록하지만 최종 append와 전체 교란을 정밀 추정하지 않는다. `d1_arrival_timing_calibration.observations`는 이 manifest를 거절하므로 초기 보정·확인 표본으로 섞지 못한다. 기존 정책 ID/동작/과거 로그의 의미는 유지한다.

### host: 원인·회수·cleanup 분리

`d1_arrival_timing_calibration_device.wait_for_cleanup`는125초 소진을 명시적 host timeout/app outcome unknown으로 낸다. `run`은 environment_gate/activity_launch/completion_poll/artifact_recovery/artifact_validation 단계를 보존한다. `pull`은 파일 부재와 연결/권한 등 조회 실패를 구분한다.

`failed_attempt_evidence`는 cleanup 전 **기존 phase wall 안에서 OS 증거 수집 최대5초 + partial 회수 최대5초**를 사용한다. `collect_failure`는 read-only process/thread 목록·해당 PID logcat·crash buffer·exit-info를 명령당2초/전체5초, 파일당256KiB로 제한하고 생략·절단·회수 실패를 기록한다. thread 목록은 native stack trace가 아니다. 앱 실패와 host capture/recovery 오류를 별도 파일로 남기며 caller finally의 cleanup은 항상 실행한다. host 로컬 파일 시스템 자체가 정지하면 엄밀한 wall 보장은 불가하다. 로컬 저장 오류 때 가능한 오류 기록도 실패할 수 있지만 cleanup finally를 건너뛰지 않는다.

기존 cleanup45초·phase3600초 상한, retry0·consumed registry는 유지한다. 새 소스는 기존 frozen plan identity를 통과시키지 않는다. 과거 실행은 보존 Git 버전으로 재현하며 중단 계획을 갱신/해제하지 않는다.

## PC 검증

2026-09-24, 시작 HEAD63f4658+이번 소스 변경 대상으로 실행했다. 최종 source SHA와 명령·로그는 외부 `FINAL_RECEIPT.json`에 결합한다.

| 검증 | 결과/범위 |
|---|---|
| Kotlin 신규7 | 첫/후속 runtime 실패, warmup/요청 실패, 실제 Executor/Future timeout, 취소·start 저장 실패, 임시 파일 fsync prefix/overflow, terminal 저장 실패, opt-out 동작 |
| Kotlin 기존 calibration7 | 관련 calibration 계약 회귀; 총14건 PASS, modelProbe/test Kotlin 컴파일 PASS |
| Python 신규10 | 누락/torn prefix·원본 manifest 바이트 hash identity·중복/고아 완료, 회수 실패/예산, 명시적 poll timeout, output 부재와 연결 실패 구분, fit 유입 금지, 실제 runner에 mocked Device/회수 실패 주입 시 cleanup과 중단 |
| Python 기존2 | urgent/normal 완료 경계·실제 lane release, consumed plan 재실행 차단; 총12건 PASS |
| 기존 실패 자료 PC 요약 | 진단0~4·warmup0~8 미확인 유지, 원본 수정 없음 |

mock runtime/Device는 GPU 생성·native crash 복구·Android lifecycle/watchdog 실기기 검증을 대체하지 않는다. 전체 테스트·기존 서명 감사·전체 실험 분석·APK build는 반복하지 않았다.

재현 명령(저장소 root, **PC 전용**):

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:ANDROID_HOME='C:\Users\LG\AppData\Local\Android\Sdk'
.\gradlew.bat :benchmark-runner:testModelProbeUnitTest --tests '*ArrivalFailureJournalTest' --tests '*ArrivalTimingCalibrationTest' -PenableModelProbe=true --console=plain
python -B -m unittest tools.test_d1_arrival_failure_evidence tools.test_d1_arrival_timing_calibration.CalibrationTest.test_normal_and_urgent_boundaries_and_actual_release tools.test_d1_arrival_timing_calibration.CalibrationTest.test_consumed_plan_cannot_restart_with_new_output -v
python -B -m tools.d1_arrival_failure_evidence --artifacts C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_calibration_recovery_development_run_v1/00_78ac4f07-821d-5722-b191-57433ee048b9/artifacts --output C:/Users/LG/Documents/D1Check_Arrival_Extension/timing_failure_diagnosis_pc_v1/old_session_consumption_recheck.json
```

출력은 write-once다. 이미 존재하면 새로운 PC 출력 파일명을 써야 한다. 이 CLI는 ADB·추론을 호출하지 않는다.

## 다음 최소 진단 제안 — 미승인·미실행

16세션 보정을 다시 준비하지 않는다. 남은 질문은 **어느 runtime 생성/대기까지 진입하고 반환하는지, host timeout 전에 어느 thread/process가 살아 있으며 예외·timeout 종료 기록이 가능한지**다.

- 새 UUID/실험 ID/출력 root의 setup_only **최대1시도**, adapter 생성 최대4회, **warmup0·진단 inference0**, retry/대체/추가0. runtime 생성 내부의 delegate compile/초기화는 있을 수 있으나 명시적 adapter.execute는0이다. 같은 모델·입력 identity·CPU thread1·resident 구성·초기 순서·기존 환경 gate를 유지한다.
- Future.get30초/runtime, 앱 watchdog120초, host 완료 poll125초를 늘리지 않는다. 첫 실패에서 후속 runtime을 시작하지 않는다. 종료 확인/증거 회수 최대10초, cleanup45초. 설치/사전 gate·최초 cooling120초·staging을 포함한 별도 전체 wall 상한 **600초 제안**. gate/설치가 시간을 소진하면 시작하지 않는다. 실행 중 작업의 native 반환은 보장하지 않으며 host cleanup으로 종료한다.
- 예상 관측/실행 약3~5분, 총 예약 상한10분은 지연 원인·진행 기록 확인용 운영 한도이며 성공률/정밀도 근거가 아니다. signature 호환 업데이트 후보, 새로운 manifest/단일시도 runner와 소비 기록, 이 합상한 검증 및 **별도 사용자 승인**이 있어야 실행할 수 있다. 이번에는 후보 APK·실행 plan·실기기 명령을 만들거나 실행하지 않았다.
- 필수 산출물: 새 manifest·journal prefix·오류/cleanup·기존 환경/admission·host launch/poll 시각·pre-cleanup process/thread/PID/crash/exit evidence·각 회수 상태. journal I/O 자체가 막히면 host 로그와 마지막 durable prefix를 같이 사용한다. 기존 분석과 단독 시간 추정의 표본으로 사용하지 않는다.
- 네 생성이 모두 끝나도 호출 경로는 미검증이다. 이 경우에만 다음 별도 호출 진단 필요성을 판단한다. 다시 정지하면 마지막 행만으로 GPU 인과를 선언하지 않고 runtime_wait/worker 기록 및 OS 증거로 가설을 좁힌다. 16세션·간섭 측정·정책 비교로 자동 확대하지 않는다.

기존198요청 `conditional_joint_primary_pass=false`, fixed-split 부분 결과, 원래 CAL-02 분모와20 null/experiment_ready=false는 모두 유지한다.
