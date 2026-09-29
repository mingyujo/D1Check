# B2 기록 일정 재생의 Activity 종료·실행 소유권 PC 판독

**판정:** `RECORDED_B2_REPLAY_V1`의 resident baseline 중 `onDestroy`가 세션 취소를 설정한 경로는 확인된다. **무엇이 `onDestroy`를 일으켰는지는 원본으로 확정할 수 없다.** 본 요청 시작 0/24, 시작 AP gate와 공식 120초 창 미진입이므로 J/AP 예측 오차나 B2 성능을 산출하지 않는다. 소비된 plan_v3은 `stopped_no_resume`로 보존한다. 이번 작업은 기기 명령 0회이며 새 실행 계획·claim을 만들지 않았다.

## 원본 시간축과 시계 경계

원본은 별도 보존된 `C:/Users/LG/Documents/D1Check_Arrival_Extension/energy_ap_recorded_b2_run_v3`의 `FINAL_RECEIPT.json`, `00_5891be99-066e-503f-bbf6-474f095e9ce4/artifacts/{progress.jsonl,session_failure.json,cleanup.json}`, `host_commands/*/client/result.json`, `screen_observations/*`, `thermal.jsonl`이다. 앱의 `mono_ns`는 Android `elapsedRealtimeNanos`; host 명령은 UTC와 host monotonic을 함께 쓴다. 아래 host UTC와 앱 monotonic은 동일 시계가 아니다. 인접 host thermal 조회에서 `/proc/uptime`의 기기 단조시계를 앞뒤로 읽은 bracket만 교차 근거로 삼았다. 시계 정렬을 밀리초 단위 사건시각으로 단정하지 않는다.

| 관측 | host UTC 또는 Android monotonic | 의미와 한계 |
|---|---|---|
| launch 명령 | 08:35:03.232717 UTC부터 | `host_commands/0077`; Activity의 실제 `onCreate` 시각은 구 APK에 없음 |
| 앱 `session_start`, warmup arm 수신, resident baseline 시작 | 2413214887110875, 2413224450765721, 2413224452187875 ns | `progress.jsonl`; runtime 4개와 warmup 8회 반환 뒤 baseline 진입 |
| 마지막 screen 표본 | 08:35:25.993876 UTC | awake/interactive만 확인. 전경 Activity, 터치, 설정 변경은 알 수 없음 |
| 기기 시계 bracket 및 마지막 전력 표본 | `host_commands/0188`~`0190`의 기기 2413245920000000~2413246120000000 ns, 마지막 앱 표본 2413246171353415 ns | thermal 조회의 기기 시각 bracket 약 0.2초; 인접 순서의 제한된 정렬 근거이며 실제 lifecycle callback 시각은 없음 |
| `session_failed`, `app_cleanup` | 2413246274689338, 2413246305857107 ns | `session_failure.json`의 `healthy()` stack은 `stopped: lifecycle_cancelled/null`, `cleanup.json`은 실패. `onPause`·`onStop`·`onDestroy` 자체 로그는 없음 |
| host 실패 파일 회수, force-stop, 프로세스 부재 조회 | 08:35:35.874~36.302, 36.353~36.451 UTC, 그 뒤 `host_commands/0198` | 회수는 앱 실패 뒤. 세션 종료용 host force-stop은 원인보다 **뒤**이며 정상 앱 cleanup과 다른 조치 |

세션 전 host의 `force-stop`은 08:34:48.931989 UTC (`host_commands/0025`)로 launch 이전 준비 단계다. 실행 도중 ADB timeout·연결 소실 증거는 없지만, 그것이 무선 디버깅 설정이 내내 켜져 있었다는 뜻은 아니다. 사용자 조작 가능성과 과거 무선 디버깅 스위치 관측은 별도 사실이며 이 종료와 시각·인과 관계를 연결할 기록이 없다. 앱이 실패 파일을 썼으므로 그 시점까지 프로세스는 살아 있었다. 이 Activity 코드의 자체 `finish()`는 `runSession` finally 끝에만 있어 최초 실패의 선행 trigger로 보기 어렵다. 그 밖의 사용자 조작·구성 변경 재생성·시스템 lifecycle 처리 중 무엇이 최초 trigger인지는 callback/instance 기록 없이 구분할 수 없다. 앞선 [DIAG-03 판독](ENERGY_AP_DEVICE_SEGMENT_LIFECYCLE_PC_20260929.md)도 `lifecycle_cancelled`였으나 phase와 APK·기록 범위가 달라 동일 원인으로 합치지 않는다.

## 실제 소유권과 수정 판단

`benchmark-runner/src/modelProbe/AndroidManifest.xml`의 `ArrivalEnergyActivity`는 `:model_probe` 프로세스의 `noHistory=true` Activity다. [Android 공식 manifest 계약](https://developer.android.com/guide/topics/manifest/activity-element)에 따르면 화면을 떠난 no-history Activity는 완료될 수 있다. 이는 가능한 메커니즘이며 이번에 화면 이탈을 관측했다는 증거는 아니다. 현재 Activity 인스턴스가 setup·dispatch·CPU/GPU worker·arrivals·samples executor, runtime, stop 토큰, journal, watchdog을 소유한다. `onPause`/`onStop`에는 취소가 없고 `onDestroy`는 미완료 세션에 `lifecycle_cancelled`를 설정한다. `runSession`의 `healthy()`가 이를 확인해 최초 stack을 기록하고 finally에서 worker/runtime·sampler·파일을 정리한다. `pump`의 stop guard는 취소 뒤 새 요청을 막는다. host는 gate·조회·회수와 실패 후 대상 앱 force-stop/부재 확인을 담당한다. 프로세스 자체가 사라지면 앱 finally 기록은 보장되지 않는다.

구성 변경이나 Activity 재생성 시 기존 인스턴스의 세션은 계속 이어지지 않는다. 새 인스턴스는 별도 executor를 만들지만 같은 session 출력 root가 이미 있으면 `canonicalProbeOutputRoot`가 기존 root를 거부하여 두 번째 전체 실행/기존 기록 덮어쓰기를 막는다. 최초 root 생성 전의 아주 이른 재생성 및 실제 Android callback 순서는 PC만으로 완전히 입증하지 못한다. 짧은 화면 이동 뒤 기존 세션을 무조건 계속해야 한다는 계약은 없고, 비충전·화면·열 gate와 일치하는 취소는 현재 안전 경계다. 반대로 `noHistory`와 Activity 소유권은 전경 변화에 세션 수명이 민감한 구조적 한계다. 원인 미확정 상태에서 취소를 삭제하거나 Service로 옮기면 소유권·계측 프로토콜이 달라지므로 이번에는 실행 의미를 바꾸지 않았다.

구 APK의 확인 가능한 **관측 결함**은 `ArrivalEnergyActivity`가 lifecycle callback·Activity instance·명시적 `finish` 의도를 기록하지 않아 위 후보를 구분하지 못하는 점이다. 기존 `EnergyCollectionActivity`의 기록 방식을 따라, 같은 bounded progress journal이 열려 있을 때 instance ID, 생성 단조시각, `onCreate`/`onStart`/`onResume`/`onPause`/`onStop`/`onNewIntent`/`onDestroy`, `isFinishing`, `isChangingConfigurations`, saved-state 유무, session finish 요청, 최초 stop reason을 기록한다. `session_start`를 첫 이벤트로 유지하고 정상/실패 정리 끝에는 `finish_requested`를 기록한다. journal 오류가 원래 앱 실패를 덮지 않게 한다. journal이 열리기 전 callback이나 닫힌 뒤 callback, native hang·프로세스 강제 종료는 기록되지 않을 수 있다. 이것은 원인 식별력을 높일 뿐 이번 원인을 해결한 증거가 아니다.

## PC 검증, APK 계보, 다음 실행 경계

착수 HEAD `67169047b1eb96b50e900813a81e9cd235b82c20`, 변경 소스 SHA-256 `b4eac2d9ae26baf2e0bf5ab28e128d8201adddabae0c9cd0b041cab654cc475b`. 프로젝트 Gradle/Robolectric의 `ArrivalEnergyLifecycleTest` 3건은 실제 Activity callback 경계에서 pause/stop 중 비취소, destroy 취소와 최초 오류 보존, 완료 세션 비취소, 기존 출력 root의 중복 실행 차단을 검사했다. 관련 `ArrivalEnergyContractTest` 2건과 `ArrivalRecordedReplayTest` 2건도 통과했다. JUnit XML은 7건·skipped/failure/error 0이다. `python -B -m unittest tools.test_d1_arrival_recorded_replay -v`의 8건도 통과해 기존 host 앱 실패 우선 판독·중복 cleanup 차단을 확인했다. 이는 실제 Android의 외부 종료 trigger나 장시간 기기 동작을 검증하지 않는다. `git diff --check` 통과.

기존 격리 빌더 `tools.d1_arrival_timing_calibration_device.package`로 별도 출력 `C:/Users/LG/Documents/D1Check_Arrival_Extension/arrival_b2_lifecycle_build_v1/`에 APK를 생성했다. `build_receipt.json`이 빌드 전후 소스 해시를 고정한다. APK는 `build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`, 106,092,116 bytes, SHA-256 `120ee894a0d91bdb93c57b634bce1f7bd8f1c2cb7d65cf6b14cf1158101d50f5`; `apksigner verify --print-certs` 통과, 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`가 기존 프로젝트 APK와 같다. `aapt dump badging`: `com.example.d1check.benchmarkrunner.modelprobe`, versionCode 1, versionName 1.0. 키·APK는 commit하지 않았다. 빌드 초기 1회는 `ANDROID_HOME` 누락으로 Gradle 설정 단계에서 실패했고, 올바른 SDK 경로를 지정한 targeted test와 격리 빌드는 성공했다.

기존 설치 APK SHA `2af45f685bcc4b0f25904907598cabf4f333e9b043980e4298d6304da6d5b544`에는 새 journal이 없다. 새 이벤트의 쓰기 비용은 미측정이며 동일 프로토콜 실측으로 자동 합치지 않는다. 이 빌드는 설치/실행하지 않았고 중단된 plan_v3의 APK/manifest를 바꾸지 않았다. **다음 실행 준비 판정:** 코드·서명 PC 검증은 완료, 기기/설치본/환경·새 계획 동일성은 미확인. 기존 plan_v3을 재실행할 수 없으며 별도 승인된 새 계획 없이는 기기 실행 불가다. 이번 PC 판독으로 과거 최초 trigger는 미확정으로 닫고 같은 원본 감사를 반복하지 않는다.

재현(기기 명령 없음): `ANDROID_HOME=<Android SDK>`와 `ANDROID_USER_HOME=<repo>/.android-user`, `JAVA_TOOL_OPTIONS=-Duser.home=<repo>`에서 `gradlew.bat -g .gradle-user --project-cache-dir .gradle-lifecycle -PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest --tests com.example.d1check.benchmarkrunner.ArrivalEnergyLifecycleTest --tests com.example.d1check.benchmarkrunner.ArrivalEnergyContractTest --tests com.example.d1check.benchmarkrunner.ArrivalRecordedReplayTest --offline --no-daemon --no-configuration-cache --console=plain`. APK 재생성은 `python -B -c "from tools.d1_arrival_timing_calibration_device import package; package(r'<새 외부 출력 폴더>')"`를 사용하고 `build_receipt.json`과 서명·package identity를 검증한다.
