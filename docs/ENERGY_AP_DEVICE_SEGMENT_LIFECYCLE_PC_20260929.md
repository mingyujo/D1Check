# DEVICE-SEGMENT-DIAG-03 lifecycle·host cleanup PC 조사 (2026-09-29)

## 판정

진단의 **앱 실패는 `onDestroy()`가 먼저 설정한 `lifecycle_cancelled`**이며, Activity 파괴를 촉발한 사건은 원본으로 식별할 수 없다. **host의 두 번째 cleanup은 재현 가능한 host 제어 흐름 결함**이다. 첫 회수와 cleanup이 끝난 뒤 `summarize_session()`의 `app completion/identity` 거절이 외부 예외 처리로 흘러가 `shared.cleanup()`을 다시 호출했다. 첫 host force-stop은 이미 기록된 앱 실패 뒤에 있으므로 그 실패의 선행 원인은 아니다. 같은 종료 처리에서 정리를 한 번만 시도하도록 수정했다. 이 수정이 앱의 과거 파괴 원인을 해결한 것은 아니다.

사용자는 휴대폰 설정에서 **“무선 디버깅” 스위치 자체가 OFF→ON으로 바뀌는 현상**을 보았다. 전환 시각·주체가 확인되지 않은 별도 관측이며 DIAG-03 원본의 ADB client 실패 0건과 합쳐 원인을 확정할 수 없다. “ADB 단절 기록 없음”은 무선 디버깅 스위치가 계속 ON이었다는 증거가 아니다. 실행 경로의 host는 `am start`·조회·필요한 `am force-stop`을 쓰지만 무선 디버깅 설정 변경 명령을 생성하지 않는다. `EnergyCollectionActivity`는 화면 밝기/모드/timeout을 `Settings.System.getInt`로 **읽을 뿐** 무선 디버깅 설정을 쓰지 않는다. 연결 실패 뒤 앱 종료 명령은 일반 실패 cleanup에서만 가능하지만 이번에는 연결 실패 자체가 기록되지 않았고, 두 force-stop 모두 앱 실패·회수 뒤다. 스위치 전환과 `onDestroy`의 인과 관계는 미확정이다.

## 원본 시간축과 clock 경계

원본은 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_device_segment_diag_run_v3`에 그대로 둔다. 앱 `progress.jsonl`의 `mono_ns`는 기기 elapsedRealtime, host checkpoint/명령의 UTC는 PC wall clock이다. 서로 단순 대입하지 않는다. host가 앱 `cleanup.json`을 조회·회수한 순서와 host 명령의 UTC로 **앱 terminal이 host force-stop보다 먼저임**은 증명된다. 정확한 앱 callback의 UTC 시각은 별도 lifecycle 기록이 없어 미상이다.

| 사건 | 앱 monotonic ns 또는 host UTC | 근거·해석 |
|---|---|---|
| host 세션 시작/launch 반환 | 05:29:15.046 / 05:29:31.203 UTC | `host_checkpoints/0003`, `0007`; 앞서 APK 설치 확인 완료 |
| 앱 `session_start` | 2315682026247839 ns | `progress.jsonl`; Activity instance/lifecycle 기록은 구 APK에 없음 |
| runtime 4, warmup 8, 적격성 4 반환·lane 해제 | 준비 구간; 마지막 병행 `lane_available` 2315695121077686 ns | 전체 journal. 본 작업 시작 없음 |
| host `warmup.arm`, `serial_probe.arm`; 앱 온도 준비 진입 | host 05:29:40.807 / 05:29:43.453 UTC; 앱 `phase_start` 2315695130889378 ns | host `0008`·`0009`, 앱 progress. `probe.arm` 전 대기 |
| host 온도 준비 관측 | 05:29:45.787, 05:30:01.439, 05:30:31.746, 05:31:02.033 UTC | checkpoint `0010`–`0013`; host process가 관측을 지속했다는 증거이며 앱 lifecycle의 정확한 시각은 아님 |
| `onDestroy()`가 첫 stop 설정 → `gate(probe)`의 `healthy()` 실패 | 앱 `phase_start` 이후, `session_failed` 2315800886195231 ns 이전 | 기존 Activity 코드와 `session_failure.json` stack으로 순서 확인. `onPause/onStop`·파괴 이유·외부 조작 기록 없음 |
| 앱 실패 cleanup | `app_cleanup` 2315800951841769 ns, `cleanup.json` 2315800954422692 ns | `status=failed`, 원래 stack은 `EnergyCollectionActivity.healthy→gate→run`; 앱 자체 **정상** 완료 아님 |
| host terminal 관측·회수 | 05:31:30.599 / 05:31:30.615 UTC 이후 | checkpoint `0014`·`0015`; 14파일 archive. 앱 failure/cleanup 파일 포함 |
| 첫 host cleanup/force-stop·프로세스 부재 | checkpoint 05:31:31.316–31.637 UTC, force-stop client 05:31:31.331–31.413 UTC | `host_cleanup.json(status=completed)`, slot0502. 앱 실패의 원인일 수 없음 |
| PC 요약 거절·예외 처리·두 번째 force-stop | failure checkpoint 05:31:31.686 UTC, force-stop 05:31:32.435–32.541 UTC | `ValueError('app completion/identity')`, `failure_host_cleanup.json(status=completed)`, slot0510. 추가 추론은 없지만 종료 명령 중복 |
| 최종 종료 | 05:31:32.849 UTC | `stopped_no_resume`, 전체 193.094초; 재개 금지 |

앱 monotonic과 host wall clock의 offset은 이 표에서 가정하지 않는다. 원본 journal에 lifecycle callback 자체가 없으므로 `onDestroy`의 시각을 더 좁히거나 무선 디버깅 전환과 맞출 수 없다. 원본에 연결 소실·ADB timeout은 없었다. 이는 무선 디버깅 설정의 연속 상태를 관측했다는 뜻이 아니다.

## 실제 Activity·host 경로

`benchmark-runner/src/modelProbe/AndroidManifest.xml`의 `EnergyCollectionActivity`는 `:model_probe`, `noHistory=true`, 기본 launch mode이며 전용 `configChanges`가 없다. host `d1_energy_collection_device.run()`은 단일 `am start -W -n ... --es session_id`를 기록한다. Activity `onCreate()`가 setup executor 하나에 `run()`을 제출하며, 같은 ID의 기존 출력은 생성 실패로 막는다. `onNewIntent`/재생성 시 발생한 실제 사건은 과거 로그에 없다. 앱의 유일한 명시적 `finish()`는 `run()`의 `finally`에서 `done=true` 뒤 UI thread에 요청한다. watchdog은 직접 프로세스를 kill한다. `onDestroy()`는 `!done`일 때만 `stop.compareAndSet(null,"lifecycle_cancelled")`를 하며, gate의 `healthy()`가 원인을 가진 실패를 만든다. `finish()`의 정상 순서와 다르지만 Activity가 왜 파괴됐는지는 코드만으로 알 수 없다. `noHistory`/구성 변경/외부 화면 전환은 조사 후보일 뿐 관측 사실이 아니다.

이 Activity에는 `lifecycleScope`가 없고 `onDestroy()`가 worker `Future`를 직접 취소하거나 runtime을 해제하지도 않는다. setup worker는 `gate()`의 `healthy()`에서 stop을 읽고 실패 경로의 `finally`가 sampler·lane·runtime을 닫는다. 앱 내부 gate·watchdog·품질 실패는 각각 기존 stop/예외/프로세스 종료 경로이며, 이번 원본에는 gate 전의 환경 위반이나 watchdog 발동 증거가 없다. host의 실패 cleanup은 별도의 `shared.cleanup()`으로서 앱 자체 `finally`와 동일하지 않다.

host `poll()`은 `cleanup.json`을 보면 종료 관찰을 마치고, `recover()`가 파일을 회수한다. 기존에는 회수 뒤 `shared.cleanup()`을 무조건 먼저 하고, 이후 `summarize_session()`이 완료 요건을 거절하면 외부 `except`가 `shared.cleanup()`을 다시 호출했다. 실패한 앱 원본 stack과 host 후처리 오류를 분리해야 한다.

host 명령 목록의 더 이른 slot0025 `force-stop`은 설치/preflight 정리로 **이번 Activity launch 전에** 끝났다. 실패 뒤 중복 정리는 slot0502·0510 두 건이다. 세 force-stop을 동일 사건으로 합산해 앱 취소 원인을 추론하지 않는다.

## 최소 변경과 경계

- host는 세션마다 `cleanup_attempted`/결과를 보유한다. 첫 cleanup 시도 전에 표시하고, 이후 요약·receipt 오류가 나도 같은 종료 처리에서 재호출하지 않는다. 첫 시도가 부분 실패하면 `attempted_outcome_unknown_no_retry`로 남기며 추가 force-stop을 자동 실행하지 않는다. 첫 시도가 아직 없고 예외가 난 경우 기존 실패 경로의 **최초** cleanup은 유지한다. 자율 세그먼트 arm 전달이 모호한 경우의 force-stop 보류도 유지한다.
- 회수된 `cleanup.json`의 앱 오류와 `session_failure.json` stack을 최종 실패 receipt의 `app_terminal_evidence`에 함께 복사한다. PC 요약 오류는 별도 `error`/`exception_stack`으로 보존한다. 앱 정상 cleanup, host force-stop, 프로세스 부재는 동일한 성공 상태로 합치지 않는다.
- Android는 종료 의미를 바꾸지 않고 **opt-in device-after-probe 진단 모드에서만** Activity instance ID, 생성/재생성, `onStart/onResume/onPause/onStop/onNewIntent/onDestroy`, `isFinishing`·`isChangingConfigurations`, 자체 finish 요청과 최초 stop 사유를 기존 bounded progress journal에 소수 이벤트로 남긴다. 기존 host-gated 모드의 journal 항목은 추가하지 않는다. `onDestroy`의 기존 취소는 유지한다. lifecycle 기록 실패는 Logcat 경고만 남기며 최초 사유를 덮지 않는다. 이는 다음 발생의 분별력을 높일 뿐 OS/사용자 동작의 원인을 자동 식별하지 못한다.
- 기존 설치 APK SHA `7589b96f…2e9c00d`에는 새 lifecycle 이벤트가 없다. Android 소스 변경으로 새 빌드는 별도 계보이며, 이전 계획·manifest·동결 모형과 동일 APK로 간주할 수 없다. 추가 journal 이벤트의 작은 비용도 미계측이다. 과거 자료와 새 APK 자료를 동일 계측 조건의 확인 block으로 자동 합치지 않는다. APK 전송·설치·기기 실행은 이번에 0회다.

## PC 검증과 남은 한계

`tools/test_d1_energy_device_lifecycle_cleanup.py`는 실제 `run()` 진입을 fake `ObservedDevice`로 통과시켜 앱 실패 뒤 summary 거절 시 cleanup 1회와 원래 stack 보존, cleanup 부분 실패의 무재시도, 회수 실패 시 첫 cleanup 수행을 검사한다. 기존 `tools/test_d1_energy_ap_autonomous_diag.py`의 arm 모호성/회수 경계도 함께 실행한다. Kotlin `EnergyCollectionLifecycleTest`는 실제 Activity callback, 최초 취소 사유 유지, instance별 lifecycle 기록을 Robolectric에서 검증한다. 초기 제한 환경에서는 Android 35 jar 다운로드와 NDK compiler 실행이 막혔지만, 권한 조정 후 공식 테스트 의존성을 받아 callback 2건을 실제 실행했고 APK도 빌드했다. Android callback의 실제 기기 순서와 무선 디버깅 스위치 변화는 PC Robolectric으로 입증할 수 없다.

| 명령·검증 대상 | 결과 |
|---|---|
| `& 'C:/Program Files/QGIS 3.40.13/apps/Python312/python.exe' -B -m unittest tools.test_d1_energy_device_lifecycle_cleanup tools.test_d1_energy_ap_autonomous_diag` | 7건 PASS. fake ADB만 사용; 실제 ADB 명령 0 |
| `gradlew.bat -g .gradle-user --project-cache-dir .gradle-lifecycle -PenableModelProbe=true :benchmark-runner:compileModelProbeKotlin :benchmark-runner:compileModelProbeUnitTestKotlin --offline --no-daemon --no-configuration-cache` | 최종 Kotlin 본문·Activity 테스트 소스 컴파일 PASS (33 tasks); 새 APK는 아님 |
| `gradlew.bat ... :benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.EnergyCollectionLifecycleTest --offline` | 테스트 Kotlin 컴파일 PASS, 2건은 `android-all` jar 다운로드 차단으로 실행 불가. 첫 시도는 기본 `C:\.robolectric-download-lock` 쓰기 불가, `JAVA_TOOL_OPTIONS=-Duser.home=<workspace>`로 수정한 뒤 의존성 네트워크 차단 확인 |
| `gradlew.bat ... :benchmark-runner:assembleModelProbe --offline` | Android/Kotlin 컴파일 후 native link에서 NDK `clang++.exe: Permission denied`. APK 완성·서명 검증 불가 |

검증 시점 2026-09-29 KST, 시작 HEAD `872e568f2883286dd746820061f0a537ee259505`에 본문의 미커밋 변경을 적용했다. 재현 시 Gradle의 프로젝트 cache 경로는 작업공간 안에 둬야 한다. 기존 외부 격리 빌드의 task output을 이 환경에서 지우려다 실패한 기록은 소스 오류가 아니다. `git diff --check`와 최종 Git 상태는 종료 시 다시 확인한다. 호스트 Python 검증은 실제 진입 함수지만, mock callback이나 코드 컴파일을 실기기 안정성·과거 `onDestroy` 원인 증거로 해석하지 않는다.

## 2026-09-29 권한 조정 후속 검증 — 앞선 환경 제한 기록 갱신

위 표의 다운로드·NDK 차단은 **권한 조정 이전** 사실이다. 같은 작업 트리와 Activity SHA-256 `f7ffa6016f1089bb7c9cdb7d153876288afd94a28be70a52e8b15ab12d553b19`에서 다음을 추가 확인했다. 소스·테스트 assertion 수정은 없었다.

- 기존 프로젝트 Gradle 설정에서 공식 Robolectric Android 35 의존성을 받아 `:benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.EnergyCollectionLifecycleTest`를 실제 실행했다. JUnit XML은 **2건·skipped 0·failures 0·errors 0**이다. Android callback의 실기기 순서나 과거 `onDestroy` trigger 검증은 아니다.
- NDK 28.2.13676358 compiler 실행 후 같은 `-PenableModelProbe=true`의 `:benchmark-runner:assembleModelProbe --offline`이 성공했다. APK: `benchmark-runner/build/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, 106,092,116 bytes, SHA-256 `933d202e5c6e2244ea1216a0935daa03088d550552e88be8f009be68f4d831f7`. `apksigner verify --print-certs` 통과, 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`는 기존 APK와 같다. `aapt dump badging`: `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, versionName 1.0. 키·비밀번호는 출력·공유하지 않았다.
- 재현: `ANDROID_HOME=<Android SDK>`, `ANDROID_USER_HOME=<repo>/.android-user`, `JAVA_TOOL_OPTIONS=-Duser.home=<repo>`에서 `gradlew.bat -g .gradle-user --project-cache-dir .gradle-lifecycle -PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.EnergyCollectionLifecycleTest --no-daemon --no-configuration-cache --console=plain`; 이어 같은 옵션의 `:benchmark-runner:assembleModelProbe --offline`. 기존 host 7건과 Kotlin 컴파일은 변경이 없어 반복하지 않았다.
- 실제 `git ls-remote --heads origin feature/arrival-scheduling-20260923`에서 원격 HEAD `872e568f2883286dd746820061f0a537ee259505`를 확인했다. Git index는 정상 linked-worktree 관리 경로다. APK·키·모델은 commit 대상에서 제외하고 기기 명령은 0회다.
- Robolectric 다운로드와 격리 Gradle/Android 빌드가 작업공간에 만든 `/.m2/`, `/.gradle-lifecycle/`, `/.android/`는 `.gitignore`에 추가했다. 재현용 로컬 캐시는 유지하되 Git 공유물에 포함하지 않는다.

다음 행동은 새 APK로 제한된 lifecycle 관찰을 수행할지 **별도 승인·현재 gate를 전제로 결정**하는 것이다. 이 APK가 생성됐어도 기존 설치본이나 중단된 계획이 자동으로 갱신되지는 않는다. 과거 앱 종료 원인·무선 디버깅 전환과의 인과 관계, 계측 비용은 여전히 미확정이다.
