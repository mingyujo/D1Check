# ARRIVAL-STALL-OBS-DIAG-01 — 독립 host 관측 진단

> **실행 종료: COMPLETE_NOT_CAUSE_RESOLVED.** 설치1·세션1완료·runtime4반환·warmup8·정규1·총추론9, 평가/retry/대체/추가0. 209.390/600초. journal191/256와원본10파일검증, 앱/hostcleanup·프로세스부재확인. 이전실패원인은미확정이다. 아래준비계약은실행당시동결기록이며재실행금지.
> 추가증거:5초snapshot의Dozing/top-sleeping/isFrozen=false, kernel stack권한거부. 35/105초관측은정상완료로생략. 전체구간상태나정지원인을입증하지않는다.
> 후속 [CAL-03 PC 후보](ARRIVAL_TIMING_CAL03_PREPARATION_20260924.md)는준비만완료·별도승인대기. 외부`stall_observation_run_v1/FINAL_REPORT.md`, `POST_RUN_VERIFICATION.json`, `FINAL_RECEIPT.json`에상세근거. 실행host snapshot과후속calibration host변경을구분한다.

2026-09-24. 시작 HEAD `29b8543fe1c0dea84e37d56b59209aaaf31020e6`, branch `feature/arrival-scheduling-20260923`, clean/원격 일치. 사용자의 새 1회 실행 승인 범위다. 이전 종료 계획은 재개하지 않는다.

## 직접 관측·코드·가설의 구분

| 항목 | 직접 관측 | 코드로 확인 / 미확인 |
|---|---|---|
| setup_only 성공 | runtime4 반환, warmup0, 총209.047초 | 합계는 설치/회수/cleanup 포함. 원 CAL-02 해결 증거 아님 |
| 첫 CPU warmup 성공 | runtime4와 classification_CPU warmup1 반환, 총181초 | 뒤7warmup/정규요청 미관측 |
| 통합 진단 실패 | CPU 반환, GPU interpreter_construction 시작 seq25, journal26/256, host125초 소진, PID 생존 | 생성 반환·Future timeout·watchdog·앱cleanup 없음. native 교착/VM 정지/기록 정지 구분 불가 |
| 생성·Future | 원 순서 C_CPU→C_GPU→D_CPU→D_GPU | setup thread가 lane.submit().get(30초); GPU 생성/사용/해제는 같은 GPU worker. cancel/interrupt는 native 종료 보장 아님 |
| watchdog | 실패 실행에서 kill 로그 없음 | onCreate main Handler 등록120초, journal bestEffort는 별도 daemon, kill은 journal 완료를 기다리지 않음. 실행 자체가 막힘과 실행 후 기록 누락은 미구분 |
| journal | 마지막 JSON은 완전한 시작 이벤트 | tryLock50ms 뒤 동기 fd.sync에는 별도 시간 상한 없음. Future 예외 처리 기록은 I/O에 의존하지만 watchdog kill은 같은 lock에 의존하지 않음 |
| lifecycle | 실패 log에 invisible, setup_only 성공에도 invisible | invisible만으로 원인 확정 불가. onDestroy는 stop/interrupt/별도daemon 기록, finally의 정상 close 보장 아님 |
| 시간 기준 | journal Android elapsedRealtimeNanos, host monotonic/UTC | Handler는 uptime 기반으로 deep sleep 시 지연. 실제 sleep/freezer/GC 정지는 미확인. 서로 다른 시계를 직접 빼지 않음 |

공식 시간 계약: [Handler.postDelayed](https://developer.android.com/reference/android/os/Handler#postDelayed(java.lang.Runnable,long)), [SystemClock](https://developer.android.com/reference/android/os/SystemClock). Future 구현의 정확한 suspend 처리는 이 조사에서 검증하지 않았다.

CAL-02 APK와 성공 진단 사이에는 durable journal/부분 실패 회수/setup_only 범위가 추가되었고, 첫 warmup APK에는 첫 호출 단계 기록, 통합 APK에는 전체warmup/정규요청과256 journal이 추가됐다. 각 원 build receipt/source snapshot을 유지한다. 기존 ProbeRawAdapter Git blob/과거 working-tree hash 대응 미확인은 그대로다. 이번에는 **앱 코드 변경 없음**: 실패 통합 APK `9019b85d527fcbcd49e49741bf1fd1bcb274281434032f13dc60bb471e2bf2c0` 재사용. 생성 순서·worker·동기화·기록 구조를 변경하지 않고 host Python만 변경한다. 원인 근거 없는 runtime 수정을 하지 않는다.

### 311.344초의 구성

원 host UTC 표식 기준(시계 점프 부재 가정, 반올림): 시작→install intent9.247초, install intent→result34.729초, result→before_launch128.770초(서명 재검증·고정120초 cooling·gate 포함), before_launch→session intent7.399초(입력 staging 포함), session intent→poll 오류127.102초(am start와pid확인 포함), 오류→cleanup완료3.684초. 이 합은 약310.931초이고 최종receipt 등 잔여 약0.413초다. 원 기록만으로 세부 ADB 명령별 시간을 분리할 수 없다. 125초는 host 완료 대기이며 GPU 초기화 시간이 아니다. 새 runner는 각 host phase를 monotonic으로 기록한다.

## 새 계약과 추가 증거

- ID `ARRIVAL-STALL-OBS-DIAG-01`, scope `observed_warmup_request`; 앱에는 기존 `warmup_and_request` scope. 새 session/manifest/root/registry, 동일 모델/입력/CPUthread1/resident4/최대동시1.
- 설치1·세션1·runtime4. 순서 C_CPU→C_GPU→D_CPU→D_GPU. warmup은 원 순서로 조합당2회=8회, 뒤 classification/urgent/GPU 정규진단1회, 명시적 추론 합9회(평가0). 최대치이며 실패시 후속 호출 금지. 라이브러리 내부 준비는 앱 explicit inference와 구분한다.
- setup_only 단순 반복이 아니다. warmup/정규 경계까지 유지하면서 **앱 executor/lock에 의존하지 않는 host 관측**을 추가한다. 새 모델/정책/성능평가 없음.
- poll 시작 후5·35·105초, 완료 marker가 먼저 생기면 남은 관측 생략. 각 snapshot≤8초, 각명령≤2초, 모두 기존125초 poll 내부. journal 읽기→power→package process→thread→proc status→kernel stack 순. snapshot의 요청 offset/host시작끝/rc/오류/잘림 보존. 주기 관측 총상한24초(추가125초가 아님).
- /proc stack은 read-only 접근만 시도한다. 권한거부는 미확인이다. kernel stack은 Java/native userspace stack 대체가 아니다. 신호/강제abort/debugger/새권한/root 없이 기존 crash log/exit-info를 회수한다. 현재 자료로 Java/native stack 확보 보장 없음.
- ADB/log/proc 조회가 실행·절전 상태에 영향을 줄 수 있으므로 모든 시간은 진단 자료이며 성능 보정에서 제외한다. 순간 power/process 상태만으로 전체 구간을 설명하지 않는다.

## 시간·gate·소비·중단 규칙

총600초=작업545(서명preflight/설치/고정cooling120/gate/staging/launch/poll+관측 포함)+마지막증거10+cleanup45. Future30/watchdog120/poll125 유지. ADB 각 호출은 절대 deadline과 개별timeout 중 작은 값. 설치120, pull180, launch30, 일반30초; 실행 직전 launch30+poll125 잔여155초 없으면 시작 금지. timeout을 단계마다600초로 재설정하지 않는다.

동일 A24 serial·fingerprint·설치본 서명/package/version, battery≥55%/≤35°C/unplugged, thermal0, 앱 프로세스 부재를 설치 전과 launch 전 확인한다. 메모리 raw와 앱의 runtime별 admission을 유지하며 앱 gate 실패시 중단한다. 연결 유일성 실패·환경 이탈·설치실패·기술실패는 재시도/대체/추가0. 앱 삭제/초기화/재부팅/설정변경 없음.

claim은 preflight전 소비registry에1회 기록, 설치시도는 install-r 직전, 세션시도는 am-start 직전, runtime시작의도와반환은 구분한다. 기록 없는 호출은0으로 채우지 않는다. 실패/미실행도 계획 분모에 남긴다. host 관측저장 실패는 회수오류이며 앱실패와 분리, finally cleanup 실행. phase telemetry 저장 실패도 cleanup을 건너뛰게 하지 않는다.

최종회수10초: 기존 OS증거≤5초, manifest→journal→cleanup→나머지 partial≤5초. host snapshot은 별도 경로로 보존하고 원 journal을 대체하지 않는다. cleanup≤45초 force-stop/프로세스부재/thermal 확인; 앱 normal close와 구분. journal/앱 marker 부재 또는 validator 실패는 증거불충분, 성공으로 승격하지 않는다.

## 판독 및 후속 조건

성공은 runtime4+warmup8+정규1의 올바른 순서/worker/입력/API/출력/반환·result/event/시간계약·lane_available·앱cleanup 및 host cleanup 증거가 모두 있을 때다. lane_available는 scheduler가 재사용 가능으로 표시한 것이며 요청1개로 실제 후속 재사용은 검증하지 못한다. urgent output_ready와 이후 persist/event는 구분한다.

실패면 마지막 journal·동일PID OS상태·app timer 로그·host phase를 함께 보고한다. frozen/잠든 상태가 직접 기록돼도 과거 실패와 동일 원인 또는 특정 native 내부 원인으로 단정하지 않는다. 성공도 CAL-02 원인해결/반복안정성/다른조건/보정완료가 아니다.

성공 후에는 동기 journal 없는 별도 시간 보정 계획의 PC 준비 가능성을 검토한다. 동기 자료로20개null을 채우지 않으며 experiment_ready=false 유지. 실제 보정은 별도 승인이다. 다른8조건과 개발→동결→확인·지원범위·실제lane 재사용 검증은 남는다. 구체적 미해결 위험 없이 추가 기기진단을 늘리지 않는다.

## 실행 파일·검증

외부 로컬 전용 root `C:/Users/LG/Documents/D1Check_Arrival_Extension/`: `stall_observation_plan_v1`(계획/manifest/script), `stall_observation_pc_v1`(검증/hash/보고서), `stall_observation_run_v1`(새 실행/원본/receipt). GitHub에는 원본/APK/key/model이 없다.

```powershell
python -B -m tools.d1_arrival_initialization check --plan C:/Users/LG/Documents/D1Check_Arrival_Extension/stall_observation_plan_v1/initialization_plan.json
& C:/Users/LG/Documents/D1Check_Arrival_Extension/stall_observation_plan_v1/RUN_AFTER_APPROVAL.ps1 -Serial '<gate에서 확인한 유일한 A24>'
```

Python 신규host observer6건과 관련runner14건20 PASS(초기 출력의 PowerShell NativeCommandError는 unittest stderr 표시; test결과OK). blocking app/journal·지연/실패관측·권한거부·연결끊김·절대deadline·조기완료·소비중복·부분회수·기존scope를 검증했다. 기존 Kotlin/Gradle/native시험은 반복하지 않는다. 앱소스/APK unchanged이므로 PC mock을 GPU/native 해결 증거로 사용하지 않는다. 최종 source hash/명령/시점/diff 상태는 외부 PC receipt에 고정한다.

실행 동결 identity: plan `35a70808471fe44ebd058acfc945f6e2e35400e5207ed1d7d51863a0baf014fb`, manifest `2f4ed1a710013b43286486dd5f63ba0c767e3f248106a8ace06c9955c16bbc36`, session `191c94d5-ae6b-510b-b816-a6cf0c4e7e1e`. APK는 위9019b85…f2c0이며 apksigner로 기존 프로젝트 signer/package/version 확인. 준비 command의 NOT_APPROVED 표시는 일반 CLI의 기본 문구이고, 이번 승인은 외부 `EXECUTION_AUTHORIZATION.json`과 사용자 명시 지시에 별도로 기록했다. source snapshot/PC receipt/미소비 확인 후 준비script를 단1회 호출한다.
