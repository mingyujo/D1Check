# 2026-09-20 강제 종료 복구·시뮬레이션 준비 판정

## 1. 최종 판정

**SIM-01 INCOMPLETE. MODEL-02B GPU 실행은 BLOCKED / FIX_REQUIRED.** 시뮬레이션 본 실험·장시간 formal experiment는 실행하지 않았다. 분류 CPU의 한 raw smoke는 artifact/cleanup까지 통과했지만, 탐지 GPU는 bounded timeout으로 실패했다. 모델 품질·전체 요청 서비스시간·정책 평가 PASS는 아니다.

- 기준 지시문: `C:/Users/LG/Documents/D1Check_Codex_Results/PRE_SIMULATION_RECOVERY_PROMPT_20260920_020435.txt` 전체 UTF-8 읽기.
- 최초 Git: `feature/pre-simulation-ready-20260919`, HEAD `f4a7f2a73e03df921b389ce58d82ad404d539b92`, staged 없음, 미커밋 변경 보존.
- 증거 루트(E): `C:/Users/LG/Documents/D1Check_Recovery/resume_20260920_020615/`.
- 검증 시작은 최초 HEAD + dirty source. 이후 변경은 `verified_source_files.json`, `verified_source_files_final.json`, 명령별 JSON의 HEAD/dirty/UTC, diff/파일 복사와 아래 커밋으로 연결한다. 최종 코드 기준은 `3e5b685ad2888c50cb09b9be0ebfd8bf3ef6ca10`이다. 이후 문서만 갱신한다.

## 2. 복구 감사

- 최초 diff/index/log/status와 존재하는 미커밋 파일 15개를 E에 복사했다. UTF-8 strict decode 성공, NUL 0. 컴파일·Python parsing·테스트에서도 절단에 의한 구문 오류가 없었다. 모든 과거 바이트의 원래 의도를 증명했다는 뜻은 아니다.
- HEAD의 debug 6개 파일 및 test 1개 파일을 modelProbe/testModelProbe의 7개 대응 파일과 대조했다. 누락·기존 경로의 중복 클래스 없음. 신규 `ModelProbeArtifacts.kt`는 Activity의 실제 저장 경로에 연결됐다.
- opt-in `-PenableModelProbe=true`에서만 전용 build type을 생성한다. 별도 applicationId, 전용 소스/테스트 및 Tasks dependency를 확인했다. main의 legacy 클래스 접근은 컴파일과 회귀로 확인했다.
- APK DEX와 manifest 직접 검사: debug/release에 probe·MediaPipe 없음, modelProbe에만 존재. 외부 EfficientNet/EfficientDet/sample binary는 모든 APK에 없음. 기존 MobileNet asset은 유지했다.
- MediaPipe 전이 의존성의 INTERNET 권한을 발견해 전용 manifest에서 제거했다. 새 APK manifest에서 부재를 확인했다. ADB entry는 exported, `:model_probe` process이며 기존 launcher와 별개다.
- Android artifact size/hash/identity/event readback, stale output 사전 거부, host 원격 exact set/regular file·실패 identity 검증을 보강했다. Windows ADB의 CRCRLF를 빈 파일명으로 오인하지 않도록 회귀를 추가했다.
- 첫 CPU 실행에서 정상 framework filesDir를 정규화하지 않은 output 검사 결함을 발견했다. 신뢰된 filesDir를 먼저 canonicalize하고 그 아래 traversal/stale를 거부하도록 수정한 뒤 실기기 재실행으로 확인했다.
- 이전 문서의 debug/unfinalized 구현 설명을 현재 계약으로 정정했다. `finalized`는 artifact 완료이며 품질·GPU 승인·service profile 완료가 아니다.

## 3. 작업 ID별 상태

| ID | 상태 | 완료 범위/남은 조건 |
| --- | --- | --- |
| MODEL-02B-RECOVERY | completed | 이동·중간 코드 복구, 회귀, APK 격리, 원본 보존 |
| MODEL-02B-HOST-EXEC-VERIFY | completed | mock fault·실제 CPU artifact·실제 timeout cleanup·실제 replay 거부 |
| MODEL-02B-DEVICE | partial / FIX_REQUIRED | 분류 raw CPU 완료, 탐지 raw GPU timeout; 다른 cell은 이번 직접 검증 없음 |
| MODEL-02B 품질 | INCOMPLETE | raw CPU/GPU 수치 배열 비교, 교체 sample의 decoded golden, peak memory 미완료 |
| TASK-02 | pending / prerequisite blocked | 두 실제 adapter의 사용자 완료 경계·ledger·새 validator 미구현 |
| PROFILE-02 | pending / prerequisite blocked | 기기별 solo/transition/co-run full service·thermal profile 없음 |
| SCHED-02 / EVAL-02 / XDEV-02 | pending | 정책 구현·동결·독립 평가·추가 기기 재현 미실행 |
| SIM-01 | INCOMPLETE | 실측 profile·입력 schema/validator·seed/반복·deadline 등 필수 gate 부족 |

## 4. 생성한 코드 체크포인트

| hash | subject | 범위·검증 근거 |
| --- | --- | --- |
| `aa1b9f0` | Recover isolated modelProbe variant and fail-closed artifact execution | 이전 미커밋 source 이동·결과 계약 복구, INTERNET 제거, 문서; JVM/Python/compile/lint/APK/no-op |
| `852ff24` | Handle Windows ADB line endings in remote artifact inventory | host CRCRLF 처리와 mock; targeted 18·전체 Python 213·compileall |
| `3e5b685` | Normalize Android framework filesDir before probe output validation | output root 수정·stale/traversal 회귀; modelProbe 6·assemble·APK 감사·A24 CPU 재실행 |

커밋 전 staged 파일 목록과 `git diff --cached --check`를 확인했다. APK/keystore/cache/build/.idea/개인환경/실험 원본은 커밋하지 않았다. 최종 문서 체크포인트는 이 보고서·STATUS·PLAN 갱신만 포함한다.

## 5. 검증 결과와 버전 경계

| 검증 | suite / test | failure / error / skip | 근거 |
| --- | ---: | ---: | --- |
| ModelProbeContract targeted, 최종 | 1 / 6 | 0 / 0 / 0 | `25_xml`, `25_probe_root_fix.*` |
| app debug | 3 / 9 | 0 / 0 / 0 | `full_debug_reports/app` |
| benchmark-runner debug | 18 / 97 | 0 / 0 / 0 | `09_runner_jvm.*`, `full_debug_reports/benchmark-runner` |
| telemetry-contract debug | 5 / 13 | 0 / 0 / 0 | `full_debug_reports/telemetry-contract` |
| 전체 debug 합계 | 26 / 119 | 0 / 0 / 0 | `10_full_debug.*`, XML 직접 집계 |
| Python targeted | — / 18 | 0 / 0 / 1 | `21_python_crcrlf_target.*` |
| Python 전체 | — / 213 | 0 / 0 / 2 | `22_python_crcrlf_all.*` |

- runner 97건은 `--rerun-tasks`, probe 최종 6건도 실행됐다. 루트 debug 검사의 변경 없는 app/telemetry 및 lint/assemble 일부는 Gradle `UP-TO-DATE` 재사용이다. 이를 이번에 모두 새로 실행한 것으로 표현하지 않는다. XML/SARIF를 복사하고 현재 입력의 Gradle 결과와 구분해 보존했다.
- Python skip은 Windows symlink 권한 제한이다. 성공 경로 외 extra `.part`, 변경 summary, cleanup 실패, dispatch+cleanup 동시 실패, unsupported, stale, timeout, hash/identity mismatch를 subtest로 검사했다. subtest를 별도 test 수로 부풀리지 않았다.
- lintDebug: error 0, warning 76 = app 20 + runner 54 + telemetry 2. modelProbe manifest unit-test merge의 remove-marker 경고 1건은 별도 build 경고이며 lintDebug 숫자에 합치지 않는다.
- production debug compile, modelProbe compile, compileall, logger self-test, debug/release/modelProbe assemble, APK manifest/DEX/content 검사, dry-run, diff check: exit 0. 최종 모델 APK는 프로젝트 debug keystore 환경으로 빌드했다.
- 실행 명령 예: `gradlew.bat --no-daemon -g .gradle-user :benchmark-runner:compileDebugKotlin`; `-PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest --tests '*ModelProbe*'`; `testDebugUnitTest lintDebug assembleDebug`; `:benchmark-runner:assembleModelProbe :benchmark-runner:assembleRelease`; `python -B -m unittest discover -s tools -p 'test_*.py' -v`. 정확한 argv·시각·return code는 각 JSON에 있다.
- 실패도 보존: 첫 서명 비교 exit 2(설치 전 해소), 업데이트 뒤 오래된 설치 APK 경로를 읽은 외부 검사 스크립트 exit 1(`pm path` 재조회로 해소), 최초 CPU smoke exit 2(코드 수정 후 재검증), GPU smoke exit 2(미해소). 실패 로그를 PASS로 바꾸지 않았다.

## 6. A24 직접 실행

- 공개 device ID: `a24-sm-a245n-primary`; 고정 serial: `adb-R59W802RW5F-yZ5QCN._adb-tls-connect._tcp`. 정확히 한 device 확인. manufacturer/model/product: samsung / SM-A245N / a24ks.
- Android 16 / API 36; fingerprint: `samsung/a24ks/a24:16/BP2A.250605.031.A3/A245NKSS9EZB5:user/release-keys`; primary ABI arm64-v8a; SoC property MT6789 / Mediatek. 나머지 ABI·RAM·환경은 manifest/preflight에 있다.
- 초기 배터리 77%, status 3, AC/USB/Wireless 비충전, 31.7°C, thermal 0. 화면 off/keyguard/AOD 관측. data 여유 98,538,696 KiB. 기존 benchmarkrunner process는 관측·보존했고 probe process는 시작 전 부재였다. 원격 기존 결과 5 session은 보존했다.
- 초기 설치본 인증서와 프로젝트 `.android-user/debug.keystore` SHA-256은 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 전역 키 불일치를 발견하고 `ANDROID_USER_HOME`을 프로젝트 경로로 지정해 서명했다. uninstall/clear 없이 `adb -s <serial> install -r <apk>` 후 설치 파일 hash를 재확인했다.
- 최종 smoke APK SHA-256: `1edd2fb16bd06473b46494adebbf20cf81c46df14800b5421025d2743c0d4547` (106,182,786 bytes).
- 분류 모델 SHA-256: `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0`.
- 탐지 모델 SHA-256: `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58`.
- 각 모델을 version-pinned 원 URL에서 HTTP 200으로 직접 확보하고 bytes/hash 및 내장 labels hash/행 수를 검사했다. host·Android artifact 모두 모델/APK/manifest hash로 연결한다.

| session | 직접 결과 | 환경·cleanup |
| --- | --- | --- |
| `ed8c1147-e91c-43dd-90e1-f3bcab54b54f` | 최초 분류 CPU: 추론 전 output-root 거부, host bounded timeout, exit 2 | 최초 오류 원문 `java.lang.IllegalArgumentException: Stale or invalid probe output root`; force-stop·입력 cleanup 성공 |
| `8f7258a7-ee6c-41d6-a510-28bd4ab1331c` | 수정 후 분류 raw CPU: 3 cold + 1 warmup + 10 warm, succeeded, 8-file/identity/hash PASS, host exit 0 | CPU/XNNPACK, requested CPU=observed CPU, CPU threads 설정 4; 77%, 30.7→30.7°C, thermal 0→0, 화면 off; cleanup 성공 |
| `fb8a750f-9b3d-4d03-8df9-e8c1410a4180` | 탐지 raw GPU: `timed out waiting for device summary`, host exit 2, finalized false | requested GPU, completed actual backend 미확정. 77%, 29.7→29.7°C, thermal 0→0; force-stop·입력 cleanup 성공, suppressed cleanup error 0 |

분류 완료의 monotonic 시작/끝은 `1581215351757539` / `1581221520522845` ns. 6,168,765,306 ns는 전체 probe 구간이며 사용자 요청 service profile이 아니다. GPU 로그에는 해당 PID/session의 263/263 `TfLiteGpuDelegateV2` 및 GPU kernel 생성이 있지만 terminal output이 없어 GPU 승인하지 않는다. GPU success artifact/성능값/실제 CPU thread 관측값은 없다. NPU는 not_probed이며 unsupported로 꾸미지 않는다. timeout의 native 호출 단계·화면 off/대기 영향은 현재 증거로 확정할 수 없다. 한계를 늘려 성공시키거나 CPU fallback하지 않았다.

결과 위치: E의 `new_probe_results/<session>/`. CPU의 `device/provenance.json` SHA-256은 `18e09041649a813ae653e4e37a4c0c292f97c87833d99a2dacf174c48ae1126a`, `device/summary.json`은 `e9bb35c04cbb6399d5ff5176a6911dc45c92b42d84c472cee1c7a65166705061`. 나머지 6개 hash는 `classification-raw-cpu_context.json`의 `artifact_sha256`에 있다. 실패는 `host_execution.json`, context·stdout/stderr·원문 logcat으로 남기며 성공 8-file artifact를 만들지 않았다.

실기기 replay는 같은 CPU manifest/session과 새 host output root로 검사했다. 원격 기존 session에서 dispatch·ownership·삭제 전에 거부됐고 기존 summary bytes 불변을 확인했다(`32_device_replay.*`, `replay_validation.json`). 실패 cleanup은 두 timeout 실제 실행과 mock 주입 양쪽에서 확인했다.

## 7. 다기기 확장

동일 model-probe manifest schema 1/artifact contract 2, runner, 원 URL/hash, comparator와 validator를 재사용한다. 새 `device_id`, 고정 serial, 독립 session/output root를 사용하고 device identity/OS/SoC/ABI/RAM/driver/thermal capability·서명·APK를 다시 기록한다. 각 실행자가 원 URL에서 직접 입력을 확보한다. 기기별 task/backend capability, 실제 backend, CPU thread 설정·service/transition/co-run/메모리·thermal parameter는 재측정한다. A24 수치를 미측정 기기의 값으로 대체하지 않는다.

MODEL-02B 통과 후 해당 기기의 profile을 만들고, 정책 동결 후 추가 기기에서 absolute-SLA와 capacity-normalized를 분리한다. 기기별 CPU/GPU 우열 및 실패/미지원 차이를 허용한다. 기기 ID는 simulation profile과 request/result의 명시적 차원으로 유지해야 한다. 기존 S26는 이번 직접 측정이나 새 두 작업 재현평가가 아니다.

## 8. Simulation 준비 상태

| 필수 조건 | 현재 근거/상태 |
| --- | --- |
| workload/request class | PLAN/MULTITASK에 W-low/W-burst/W-peer/W-sustain, task와 urgent/일반 독립 정의. 실제 동결 arrival trace 없음 |
| arrival/service/deadline | 예정 도착 a, enqueue e, 완료 C, `d=a+D(task,priority)` 설계. full service 측정 없음, D는 calibration_pending |
| device/thermal/capability | A24 한 CPU smoke와 실패 GPU 관측만 존재. profile·thermal parameter·허용 co-run 집합 미확정 |
| 실측/합성 분리 | arrival는 합성 가정, service는 기기별 실측 필요. smoke/host 시간은 service distribution으로 사용 금지 |
| baseline | B0 고정경로 FIFO 직렬, B1 긴급/EDF+aging 직렬, B2 개발에서 고른 정적 배정·합법 병행, B3 solo earliest-finish. 개정 4.4 설계이며 코드·선정 결과 없음 |
| proposed P | 공통 순서/aging + 측정된 간섭·준비 비용으로 예상 완료와 시작/대기 비교. 구현·튜닝·freeze 없음 |
| 결정변수 | 다음 요청·CPU/GPU 경로·시작/대기·승인 병행 조합 |
| 목적함수 | 안전/품질/메모리/일반 서비스 제약하 긴급 기한 위반, 이어 완료 응답 P95를 사전적 순서로 최소화. 전역 최적성 주장 없음 |
| 제약 | 비선점, 최대 2 in-flight 및 검증된 CPU+GPU 조합, 동일 thread/인스턴스 예산·queue/admission/expiry/drain·열 gate. 실제 수치 일부 pending |
| KPI | 완료 R=C-a의 nearest-rank P95와 완료 표본 수; on-time/전체 예정 도착; succeeded/전체 도착; 실패/거절/만료/late/unfinished 별도. 일반 backlog·최대 대기·완료량·처리량 병기 |
| seed/반복 | calibration/development/evaluation 분리·동일 trace 정책 대응·독립 block 계획만 있음. 공식 seed 목록·최종 반복 수 thresholds_pending. probe 3+1+10을 simulation 반복으로 전용하지 않음 |
| input schema / validator | simulation 전용 schema·validator 미구현. model-probe validator로 대체할 수 없음 |
| provenance / holdout | device/profile/trace/policy/model/APK/Git/hash/seed 연결 설계. full profile·보정/독립 holdout session 없음 |
| no-op / 저장 / 명령 | model-probe dry-run만 exit 0. simulation no-op·결과 root·실행 CLI는 미구현/미동결이며 실행 예정 명령을 꾸며 쓰지 않음 |

따라서 MODEL-02B→TASK-02→PROFILE-02의 선행 gate를 건너뛰지 않았다. 서비스/열·deadline/seed 숫자나 가상 완료를 만들어 SIM_01_READY로 표시하지 않는다. 현재 복구 결과 폴더명과 이전 `SIM-01_READY_20260919` 폴더명은 준비 판정이 아니다.

## 9. 보존 및 최종 Git

`33_preservation.*`/`preservation_result.json`: legacy 분석·diagnostic 40파일, A24 formal 834파일(80-slot manifest의 기존 SHA 일치), S26 ZIP, 이전 probe 91파일, 기존 기기 artifact 33파일 모두 SHA/bytes 보존. 마지막 source inventory 124파일도 검증 버전과 일치했다. 세 신규 시도의 app-private/shared 입력 부재 및 probe process 부재를 확인했다. CPU 결과와 기존 session 결과는 남겼다.

formal v1/diagnostic v2/calibration-v1, image-v3/EXIF, 공식 timer, 기존 main·app·telemetry production 및 원시 데이터는 이번 변경 대상이 아니다. reset/restore/clean/discard/master 수정/push/PR/merge/uninstall/pm clear를 하지 않았다. 초기 미커밋 작업은 복구 체크포인트에 반영했고 초기 복사본도 남겼다. 최종 문서 커밋 후 feature 작업 트리의 clean 여부를 별도로 기록한다.

## 10. 남은 blocker와 최소 다음 단계

다음 작업은 **MODEL-02B-GPU-DIAG**다. create/allocate/invoke/readback/close의 단계별 monotonic 진행 로그를 보존하도록 계측하고, 기존 120초 gate 안에서 탐지 GPU의 정지 단계와 원인을 규명한다. 현재 로그만으로 native hang·화면 off·GC·GPU runtime 문제 중 하나를 확정하지 않는다. gate/tolerance/deadline을 임의로 완화하지 않는다.

수정 후 먼저 아래 targeted 검증을 실행하고 서명·APK-source hash를 다시 확인한다.

```powershell
$env:ANDROID_USER_HOME = 'C:\Users\LG\AndroidStudioProjects\D1Check-model02b\.android-user'
.\gradlew.bat --no-daemon --no-configuration-cache -g .gradle-user -PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest --tests '*ModelProbe*' :benchmark-runner:assembleModelProbe
python -B -m unittest tools.test_d1_model_probe -v
```

그 다음 새 UUID/현재 APK hash의 manifest를 만들어 `python -B tools/d1_model_probe.py execute-seam --manifest <새 manifest> --input-root <검증 input root> --apk <현재 APK> --adb <adb.exe> --serial <고정 A24 serial> --output-root <새 output root>`로 한 번만 재검증한다. 구 manifest/APK 해시를 그대로 재사용하지 않는다. GPU timeout 해결 후 raw 수치·decoded golden·품질/메모리 gate를 완료해야 TASK-02로 넘어갈 수 있다.
