# 배경·열 이력 개발 대조 4세션 — PC 준비 완료, 2026-10-03

> 최신: 새 plan_v3 수집4/4 완료·소비/종료, 시스템 trace 계약 부적격. [Run02 결과](../background_activity_run02/README.md). 아래 준비·중단 기록은 과거 사실이며 이 계획을 재실행하지 않는다.

## 2026-10-03 최신 계획 v3 — 설치 없는 미승인 개발4

이 절이 현재 실행 대상이다. 아래 v2 명령·준비 수치는 **과거 기록**이며 v2는 [stopped_no_resume](../background_activity_run01/README.md)다. 새 ID `BACKGROUND-ACTIVITY-DEVELOPMENT-03`만 준비했다. 상태 `PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED`, 출력·registry·소비 claim 없음. 이번 PC 작업은 Run/기기 명령/재빌드 0회다.

- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v3/collection_plan.json`
- 최종 계획 SHA-256: `dbec1de344b2963f726fc7a873660f021796802c008a6de77f043d1712fff501`
- 예정 출력: `background_activity_run_v3`; registry: `background_activity_registry/BACKGROUND-ACTIVITY-DEVELOPMENT-03`. 어느 것도 생성하지 않았다.
- APK·인증서·패키지·버전·Android 소스는 아래 v2 후보와 동일하다. APK `9d8d55c2742b485e18f8a0812b70bf33ed66f9185c6d47b80c39f086e73fd932`를 재사용한다. 현재 설치본의 동일성은 실행 시 새로 확인한다. 과거 설치 성공은 현재 gate 통과 증거가 아니다.
- `installed_only=True`: 현재 설치본 host pull 최대1, APK push/설치 **0**. 불일치·조회 실패면 앱 시작 전 중단하며 배포 fallback은 없다. inherited `apk_push_timeout_seconds=120`은 이 경로에서 사용하지 않는 필드다.
- C0 → CPU96 → PAR96 → C0, 개발4/독립 확인0. 본192 + warmup32 + 별도 적격성0 = 명시적 추론224; runtime16; staging4·28파일; trace4·trace pull4; 재시도/대체/추가 각각0. resident·900ms sampler·입력·worker/lane·AP observe-v2·부하·판정·조회 주기는 v2와 같다.
- 시간 상한 **4,454초(74분14초)** = 설치본 preflight600 +4×세션896 +3×대기90. preflight600은 설치 시간을 복사해 정상 예상시간으로 쓰는 값이 아니라 현재 설치본 검사 **집계 deadline**이다. 마지막45초를 여유로 두고 명령 및 로컬 APK 검사를 잔여시간에 제한한다. 두 번의 로컬 APK inspect 각각 최대60+30초, host pull180초, identity/환경/remote SHA 조회가 포함된다. 개별 timeout이 모두 최대까지 성공할 것을 보장하지 않으며 deadline 부족이면 중단한다. 설치 예약은0이다.
- 세션896 = stage/gate120 +trace start90 +launch26 +poll485 +앱 회수50 +host cleanup45 +trace 회수80. 고정 관측30+120+60=210초/세션, 합계840초. 회수/종료 예약이 부족하면 새 단계를 시작하지 않는다. 이 상한은 예상시간·완주 보장이 아니다.
- ADB **13,036명령** =preflight200 +4×(기존3200 +trace9). 기존 poll 최대0.25초 listing, thermal2초/3명령, screen10초/1명령 유지. 485초의 간격 기반 ceiling1940+729+49=2718과 staging/arm/기타482를 합한 기존3200, trace start5/recovery4를 더한다. 첫 세션 누적 ceiling에도 preflight가 포함된다. heartbeat30초는 host 파일 기록이며 추가 ADB가 아니다.
- Perfetto 도움말 수정(원본 stderr/exit1+Usage+필수 옵션)을 새 소스 해시에 연결했다. 다른 조회 오류/timeout은 완화하지 않았다. CLI 도움말 수용은 실제 trace 지원·내용 적격성·TraceProcessor 실행 검증을 의미하지 않는다.

PC 검증: `python -B -m unittest tools.test_d1_background_activity_plan` **9건 통과**. 실제 공유 runner의 설치 없는 경로→trace→앱 launch→회수/cleanup 경계를 fake Device로 통과하고 설치 호출은 금지했다. 실제 installed_preflight의 후보 불일치→원래 오류/receipt 보존→추가 명령0을 확인했다. 실제 PowerShell Check 및 Device/server probe 생성 금지 Python Check 통과. [검증 대상·소스 해시·예산](plan_v3/verification.json). 검증 HEAD198c6ac, 이번 host 수정은 미커밋 상태에서 검증했다. Android/기기/장시간 안정성은 새로 검증하지 않았다.

계획 생성 재현(새 빈 폴더에서만, 이미 만든 계획에 재호출하지 않음):
```powershell
& 'C:/Users/LG/anaconda3/python.exe' -B -m tools.d1_background_activity_plan prepare --source-plan C:/Users/LG/Documents/D1Check_Arrival_Extension/separated_power_plan_v4/development/collection_plan.json --build-receipt C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_build_v1/verified_build_receipt.json --output C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v3
```

**새 개발4 실행 승인 후** 현재 A24 transport를 지정해 아래 경로를 쓴다. 이번에는 Check만 수행했다. 실행 전 A24·fingerprint/설치본/배터리·비충전·BAT≤35°C·thermal0·화면·memory·품질/GPU 등 기존 gate를 다시 확인한다. 설정 변경·자동 reconnect·transport 전환·추가 호출은 없다.
```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v3/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 확인한 A24 transport>' -ExpectedPlanSha256 'dbec1de344b2963f726fc7a873660f021796802c008a6de77f043d1712fff501'
```

원래 계획 SHA a214b53e…d78d97e, APK, 공유 모형 SHA5682082a…72db2 및 기존 freeze를 보존한다. gamma 후보는 미채택, 기본/strict/experiment_ready=false 불변. 새 실행이 끝나도 내용 적격성·계수 식별·독립 예측 확인·정책 차이 판정은 서로 다른 단계다. PC 준비 완료를 모형 완성으로 표현하지 않는다.


최신 실행: [Run01 앱 시작 전 중단·PC 판독 수정](../background_activity_run01/README.md). 아래는 실행 전 준비 기록이며 plan_v2는 이제 stopped_no_resume이다.

**PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED.** 기존 후보의 불안정한 gamma와 유휴 AP 상승을 구분할 관측을 구현했다. 새 전력·AP 계수 채택, 정책 우열 확인, 실기기 실행 완료를 뜻하지 않는다. 이번 기기 명령/Run/claim은 0이며 새 계획과 출력 경로는 미소비다.

[준비 화면](index.html) · [고정 계약](contract.json) · [검증·해시](verification.json) · [예산](budget.json) · [기존 후보 미채택 근거](../causal_background_pc_v1/README.md) · [원래 동결 결과](../separated_power_final/README.md)

## 1. 질문과 자료 역할

C0_PRE → CPU_URGENT_ONLINE_V1의 96요청 → B2_PARALLEL_ONLINE_V1의 96요청 → C0_POST. 전부 **개발 대조**이고 독립 확인은 0이다. C0는 동일 runtime 4개와 warmup 8회를 유지하되 본 작업 0회인 기존 resident-control 경로다. 두 부하는 기존 48분류:48탐지, 350ms 독립 도착, 긴급1500ms/일반6000ms 입력을 그대로 재사용한다. backend/worker/lane 해제/정상 종료 경계와 정책은 바꾸지 않는다. 부하 사이 90초는 고정 대기이며 내부 열 평형이나 동일 초기 온도를 보장하지 않는다.

추가 CPU 관측으로 benchmark·tracer·기타 활동과 기기 전체 J/AP 잔차의 동시 변화를 기술할 수 있다. CPU 활동이 잔차의 원인이라고 확정하거나 GPU/무선/각 앱의 전력을 식별하지 않는다. C0 전후는 순서·시간·숨은 열 이력의 영향을 함께 받으므로 인과 대조의 완전한 랜덤화가 아니다. 네 세션은 구조 식별을 위한 최소 대비이며 반복 변동성 정밀 추정이나 gamma 안정성을 보장하지 않는다.

기존 gamma 후보는 계속 미채택이다. 새 자료는 개발 자료로만 사용한다. 사전 지정된 후보군 이외의 자동 탐색/적합/확인 세션 추가는 없다. 관측이 없거나 자극이 구분되지 않으면 계수 미식별로 끝낸다. 기존 모형의 4상태 전력/서비스는 재사용하되 실제 지원 검사를 유지한다. 이 계획 실행만으로 열 모형이나 정책 선택 적격성이 완성되지 않는다.

## 2. 실제 구현과 정보 경계

- APK의 opt-in `background-activity-contrast-v1`만 새 경로를 사용한다. 기존 실행·AP observe-v2·lifecycle 취소와 단일 host cleanup을 유지했다. Android Service나 host supervisor를 추가하지 않았다.
- 기존 power snapshot을 900ms마다 한 번 읽고 자신의 누적 process CPU ms를 한 번 덧붙인다. [Android Process API](https://developer.android.com/reference/android/os/Process#getElapsedCpuTime())는 자신의 프로세스 CPU 시간이며 기기 전체 CPU 사용량이 아니다. 다중 코어에서 CPU초/벽시계초가 1을 넘을 수 있다.
- 128개 bounded ring에는 sensor midpoint와 입력 ready 시각을 따로 저장한다. 긴 잠금 안에 sensor/inference/file IO를 넣지 않는다. common 시작35초 이후, 실제 가용 sampler tick에서 최소10초 간격으로 과거 입력을 발행한다. 900ms tick에서 보통 약10.8초 간격이므로 이전 PC 후보의 정확한35/45/55초 격자와 동일하지 않다. 실제 issue_ns로 재현해야 한다.
- 발행시점까지 ready인 표본만 사용한다. 마지막 midpoint에서 과거10초를 적분하고 ready 신선도3초/공백2.5초를 적용한다. 결측·단위 부적합·충전·과거창 부족은 null이며 미래 표본/부하 후 AP로 채우지 않는다. `task_residual_w=null`이다. 실제 과거 lane 노출 join 전에는 whole-device W를 순수 외란 전력으로 쓰지 않는다. **입력 관측 구현이고 새 온라인 예측기·정책 채택은 아니다.**
- Perfetto CPU sched/frequency/process_stats를 기기 서비스에 UUID key로 한 번 시작한다. 호스트 background Python을 새로 분리 실행하지 않는다. [CLI](https://perfetto.dev/docs/reference/perfetto-cli)와 [detached 세션](https://perfetto.dev/docs/concepts/detached-mode)을 사용하되 기기 기록600초/64MiB 상한, 8MiB DISCARD buffer, 파일 flush5초, process_stats1초를 고정했다. suspend 포함 시간은 플랫폼 best-effort이며 전원 상실·서비스/native hang 종료를 보장하지 않는다.
- trace 시작은 help5초 → query5초 → 지정 파일 부재3초 → start35초 → is_detached5초의 최대5명령이다. CLI/필수 data source가 없으면 앱을 시작하지 않는다. 다른 trace를 임의 종료하지 않으며 기존 trace의 계측 영향을 자동 제거하지 않는다.
- 정상 종료 후 앱 원자료 회수50초 → 대상 앱 cleanup45초 → 자신의 trace 상태5초/조건부 stop10초/stat3초/pull30초의 최대4명령과80초 예약을 사용한다. 복구 시도는 한 번만 소유하고 같은 결과를 재사용한다. stop 실패가 가능한 pull을 막지 않지만 별도 오류로 보존한다. 원격 trace는 삭제하지 않는다. force-stop과 앱 정상 cleanup·프로세스 부재는 별도 사실이다.

## 3. 계측 변화와 아직 기기에서 확인할 것

900ms 센서 표본·원래 host 조회는 유지하고 self CPU API, 과거창 계산/journal, 시스템 trace가 추가됐다. 이 추가 비용도 기기 전체 에너지에 포함된다. 이전 자료와 같은 프로토콜로 합치거나 임의 overhead를 빼지 않는다. numeric AP는 기존 host thermal 관측이며 앱 입력은 부하 직전 승인된 값뿐이다. 부하 이후 AP는 평가 표적이다.

A24의 실제 Perfetto 권한/옵션/기록 내용/손실/clock, 새 APK 안정성, 추가 계측 비용은 미검증이다. 플랫폼에 따라 주파수 기록이 없을 수 있다. trace 파일 크기·pull 성공만으로 내용 적격성을 인정하지 않는다. CPU 활동은 GPU/무선/숨은 열의 완전한 설명이 아니다. raw trace에는 다른 프로세스 이름이 포함될 수 있으므로 외부 원본에 두고 Git에는 그룹 집계만 공유한다.

오프라인 `d1_background_activity_readout`은 BOOTTIME clock 일치, loss/error, sched 겹침과5초 bin coverage를 검사하고 불완전 bin을 null로 남긴다. 관측된 CPU 집합만으로 빠진 CPU 자체를 검출할 수는 없으며 activity 부재를 입증하지 않는다. 주파수 결측은 unsupported다. **이번에는 실제 TraceProcessor binary/SQL/Android trace 실행을 검증하지 않았다.** CSV fixture 판독만 PC에서 검증했다. 향후 회수 후 공식 [Trace Processor](https://perfetto.dev/docs/analysis/trace-processor) binary의 출처/hash를 결합해 SQL export를 수행하고 스키마·clock·손실·내용이 적격한지 먼저 판정해야 한다. 오류가 나면 다른 계산으로 몰래 대체하지 않는다.

## 4. 정확한 상한과 산식

|항목|상한|
|---|---:|
|개발 / 확인|4 / 0세션|
|본 작업 / warmup / 추가 적격성 추론|192 / 32 / 0회|
|명시적 추론 / runtime|224 / 16회|
|staging|4회·28파일|
|현재 설치본 host pull|1회|
|APK push / 데이터 보존 설치|각1회, 동일 설치본이면 생략|
|별도 trace / trace host pull|각4회, 파일당600초·64MiB 제한|
|baseline / common / cooling|세션당30 / 120 / 60초, 고정 합840초|
|세션 사이 고정 대기|90초×3=270초|
|전체 예약|4,454초=74분14초|
|ADB|13,036명령|
|재시도 / 대체 / 추가|각0회|

세션 예약은 stage·gate120 + trace start90 + app launch26 + host poll485 + 앱 회수50 + 앱 cleanup45 + trace 회수80 =896초다. 전체는 preflight·deploy600 +4×896 +3×90 =4454초. 840초는 고정 관측이며 4454초는 최악 예약이지 정상 예상시간·완주 보장이 아니다. trace start53초 timeout 합에 최대5×6초 client 종료 여유를 더해90초, trace recover48초 timeout 합에4×6초 여유와 기록 여유를 더해80초로 잡았다. 새 단계 전에 예약을 확보하지 못하면 중단한다.

원래 host listing 최대 .25초, thermal2초마다3명령, screen10초마다1명령을 유지한다. 485초 poll의 간격만으로 계산한 상한은1940+729+49=2718명령이며 실제 client 대기로 감소할 수 있다. staging/arm/설치본 조회/회수/cleanup 등에 기존482 여유를 더한3200과 trace 최대9를 합쳐 세션3209, preflight200 +4×3209=13036이다. 첫 세션 누적 polling ceiling에도 preflight 소비가 들어가므로 일부 여유를 덜 쓰게 될 수 있다. heartbeat/checkpoint30초는 host 파일 기록이고 별도 ADB가 아니다. 조회를 추가로 빠르게 하지 않는다. 준비 중 기존 precommon-observation-gap-v3만 유지하며 새 재시도는 없다.

개별 핵심 timeout: APK push120/설치120초, listing3초, runtime setup150초, warmup 승인60초, AP 승인30초, 단일 추론30초, 앱 watchdog480초. numeric AP는 유효·신선도3초를 확인하고 개발 시작32.5–34.0°C 범위 밖은 모형 적용 범위로 기록한다. 개발 하한을 실행 차단으로 재추가하지 않는다. 기존 비충전/배터리20% 이상/BAT35°C 이하/thermal0/화면·밝기·memory·출력품질/GPU 증명 gate는 유지한다. 설정 변경·가열·추가 추론·endpoint 자동 전환·daemon 재시작을 하지 않는다.

## 5. APK·계획 동결과 명령

APK는 기존 프로젝트 인증서로 서명했으며 package `com.example.d1check.benchmarkrunner.modelprobe`, versionCode1이다. 인증서 SHA-256 `b253dbb951d85d1a79ea7f2ca2d1ff76a9fa34dc6c793b1df9b5249f3fcc7565`. 기존 설치본에 이번 관측은 없다. 자동 배포는 이번 PC 작업에서 수행하지 않았다.

- APK: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_build_v1/build/_benchmark-runner/outputs/apk/modelProbe/benchmark-runner-modelProbe.apk`
- APK SHA: `9d8d55c2742b485e18f8a0812b70bf33ed66f9185c6d47b80c39f086e73fd932`
- 계획: `C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v2/collection_plan.json`
- 계획 SHA: `a214b53e8aab91ed948f23343a2fbf7eb33e2839e721d16aadc94862ad78d97e`
- 새 출력 예정: `background_activity_run_v2`; 새 registry 예정: `background_activity_registry/BACKGROUND-ACTIVITY-DEVELOPMENT-02`. 둘 다 아직 존재하지 않는다.
- v1은 trace505초였던 미소비 PC 초안으로 보존했다. 시작 지연+앱 상한을 더 확실히 포괄하도록600초인 v2를 최종 대상으로 동결했다. 초안 보존은 실패/소비/중단 계획 기록이 아니다. v1을 실행하지 않는다.
- 기존 공유 모형 SHA: `5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2`; 원래 freeze `19637bf11814e473922c482e752942fb486e4cc74fd74694e6ecf15ee322b825` 불변.

이번에는 Check까지만 수행했다. **별도 개발4 실행 승인 후에만** 다음 Run을 사용한다. Serial은 과거 값을 복사하지 않고 현재 승인 A24 transport로 지정한다. 실행기가 동일 기기·설치본·환경을 다시 확인한다.

```powershell
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Check
& 'C:/Users/LG/Documents/D1Check_Arrival_Extension/background_activity_plan_v2/RUN_AFTER_APPROVAL.ps1' -Action Run -Approved -Serial '<현재 A24 transport>' -ExpectedPlanSha256 'a214b53e8aab91ed948f23343a2fbf7eb33e2839e721d16aadc94862ad78d97e'
```

## 6. PC 검증과 종료 기준

- 신규 Python7검사 + 관련 recorded replay9검사 =16검사 통과. 별도 기존 energy lifecycle cleanup3검사도 통과했다. 가짜 Device/Popen 차단으로 실제 공유 runner의 trace 시작→앱 진입→단일 cleanup→trace 회수, 소비 후 재실행 차단, stop 실패 후 부분 회수, 중복 복구 차단을 검증했다. CSV fixture의 clock/loss/주파수 결측/부분 coverage/null/중복 합산 차단도 확인했다.
- Android12검사 통과: 신규 계약·과거 입력3, 실제 Robolectric Activity 경계5, 기존 policyStudy4. 앞선 fixture 타입 오류는 수정 후 재실행했고 assertion/실행 gate를 약화하지 않았다. APK assemble·서명·package·버전·소스 출처 확인 완료. 실기기 callback/native/GPU·장시간 안정성 검증은 아니다.
- 실제 PowerShell Check 통과. ObservedDevice/legacy Device/server probe를 금지한 실제 Python Check도 통과했다. 0/96/96/0 manifest·hash·APK source 대응·출력/registry 부재 확인. Run은 호출하지 않았다.

재현: 저장소 root에서 `python -B -m unittest tools.test_d1_background_activity_plan tools.test_d1_arrival_recorded_replay`. APK 빌드는 기존 `tools/arrival_timing_isolated_build.gradle`의 격리 build root로 `:benchmark-runner:testModelProbeUnitTest`의 위3 class와 `:benchmark-runner:assembleModelProbe`를 수행했다. `ANDROID_HOME`, `ANDROID_USER_HOME`, `D1_TIMING_BUILD_ROOT`는 기존 SDK/격리 경로를 사용했다. build·실패 fixture·서명·Check 로그는 외부 `background_activity_build_v1` 및 `background_activity_final_build_v1.log`에 보존한다.

향후 trace 판독은 아래처럼 외부 raw에 대해 수행한다. start/end는 회수된 해당 앱 `common_boundary.json`의 monotonic ns를 사용하며 AP가 잘 맞도록 시계를 이동하지 않는다.

```powershell
python -B -m tools.d1_background_activity_readout export --processor '<공식 TraceProcessor 로컬 파일>' --trace '<해당 세션 system_activity.pftrace>' --output '<새 CSV export 폴더>'
python -B -m tools.d1_background_activity_readout summarize --folder '<위 export 폴더>' --start-ns '<common start ns>' --end-ns '<planned end ns>'
```

완료 판독은 앱 정상 완료/실제 호출/lane·센서 적격성/trace의 별도 내용 적격성/배경 자극과 후보 식별을 분리한다. 오류·자료 부족·식별 실패면 원래 실패와 후속 회수/cleanup 오류를 보존하고 종료한다. 상태를 볼 수 없으면 unknown으로 남긴다. 현재는 **코드·APK·계획 준비 완료**, 계수 식별·독립 예측 확인·에너지/열 정책 선택은 미완료다. 기본 모형·strict·experiment_ready=false를 그대로 유지한다.
