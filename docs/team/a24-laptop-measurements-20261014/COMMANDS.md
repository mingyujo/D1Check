# 노트북 명령과 실제 실행 중단 경계

이번에 실행 가능한 것은 **PC 준비·검사·APK 빌드·로컬 복사본 검산**이다. 아래 PC 명령은 기기를 조회하지 않는다. 실제 측정 명령은 별도 승인과 DEVICE_UNVERIFIED 해제 이후 검토하며 이번에는 실행하지 않는다.

## PC 전용 재현

별도 worktree `D1Check-a24-prep-20261014`, 브랜치 `codex/a24-laptop-prep-20261014`를 사용한다. Python3.11.9와 JDK17.0.20.1, Gradle9.5.0 wrapper, AGP9.3.2, SDK37, build-tools36.0.0, LiteRT1.4.2를 고정한다. host 도구는 표준 라이브러리만 사용한다. 개인 경로는 `.local/a24-laptop.paths.json`과 ignored output에만 둔다.

```powershell
# PC 단위·mock·기존 Python 회귀. ADB/모델 추론 없음.
.\.venv-a24\Scripts\python.exe -B -m unittest discover -s tools -p 'test_d1_a24_laptop*.py' -v

# 새 이름/빈 출력 폴더만 사용. START/claim을 만들지 않는 계획 생성.
python -B tools/d1_a24_laptop_plan.py --output output/a24_laptop_prep_reproduction --plan-id A24-PC-PREP-NEW-ID --bindings output/a24_laptop_prep_20261014/input_bindings.json

# 새 opt-in APK와 JVM 단위시험만. 설치/connected 테스트를 호출하지 않는다.
.\gradlew.bat --offline --no-daemon --max-workers=2 -PenableA24Preparation=true :benchmark-runner:testA24PreparationUnitTest --tests 'com.example.d1check.benchmarkrunner.A24*' :benchmark-runner:assembleA24Preparation

# 기존 MobileNet asset 계약을 가진 별도 variant에서 기존 회귀 검증.
.\gradlew.bat --offline --no-daemon --max-workers=2 -PenableModelProbe=true :benchmark-runner:testModelProbeUnitTest :telemetry-contract:testDebugUnitTest

# 로컬 파일19개 역할의 SHA만 검사. DEVICE_UNVERIFIED를 유지.
.\.venv-a24\Scripts\python.exe -B tools/d1_a24_laptop_prep.py preflight .local/a24-laptop.preflight.json

# 미래 제어기의 기본 검토: 실행 옵션 없음, 기기/원장 작업 없음.
.\.venv-a24\Scripts\python.exe -B tools/d1_a24_laptop_control.py review-only .local/a24-laptop.paths.json

# 환경 경로 탐색만. adb 실행/기기 enumeration 없음.
python tools/d1_a24_laptop_prep.py --help
python tools/d1_a24_laptop_validator.py --help
python tools/d1_a24_laptop_recover.py --help
python tools/d1_a24_laptop_commands.py --help
```

host 모듈은 `tools` 경로의 동료 파일을 직접 import하므로 위처럼 스크립트 경로로 실행한다. `python -m tools.d1_a24_laptop_*` 패키지 호출은 지원하지 않는다.

회수 후에만 사용할 PC 명령은 다음과 같다. 입력 폴더는 미래 회수 경로로 바꾸며, 이 명령은 기기에서 pull하거나 세션을 시작하지 않는다.

```powershell
# 로컬 회수 원물의 전수 SHA 검사. 새 복사본이 필요하면 --destination <새 빈 경로> 추가.
python -B tools/d1_a24_laptop_recover.py output/recovered_session output/recovered_session/transport_manifest.json

# manifest/events/requests의 시간·lane·대기·완료·전체 분모 검산.
python -B tools/d1_a24_laptop_validator.py trace output/recovered_session
```

노트북의 기존 Gradle cache는 복사하지 않고 사용했으며 기존 사용자 소스/원자료는 변경하지 않는다. 공간이 부족할 때 원자료·checkpoint를 자동 삭제하지 않는다. 현재 전용 host 환경에는 torch/RL 학습환경을 설치하지 않는다.

## 계획과 향후 실제 흐름

기존 Python 전체 회귀는 `python -B -m unittest discover -s tools -p 'test*.py' -v`로 당시241개(기존 skip1)를 검사했다. 최종 새 host는 전용 표준 라이브러리 환경에서103개를 별도 검사했다. 새 no-model variant에서 기존 bundled calibration 검사까지 실행하면 asset 계약 차이로 실패하므로 위처럼 variant별로 검증한다. 재빌드하면 debug 서명·APK SHA가 달라질 수 있어 새 identity/manifest를 다시 결합해야 하며, 여기 기록된 기존 APK SHA를 전용하지 않는다.

최종 준비 bank와64세션 계획은 `output/a24_laptop_prep_20261014/plan_v3/`에 있다. 앞 v1/v2는 소프트웨어 정합 보완 과정의 미소비 초안으로 보존하고 실제 측정에 사용하지 않는다. 준비용 registry template는 활성 원장이 아니며 START/claim/lock을 생성하지 않는다.

1. 별도 실측 승인 후 정확 단일 A24와 연결/충전 조건을 등록한다. APK 정적 identity, 실제 설치 identity, 모델·입력·tensor와 새 세션 identity를 결합한다.
2. 새 session_manifest에 해당 session/bank/모델4runtime를 결합하고 실제 device fingerprint/APK SHA를 채운다. 종료된 Resident/CAL-03 원장을 재사용하지 않는다.
3. 승인된 설치·입력 staging·opt-in Activity 준비를 실행한다. runtime/warmup ready 이후60초 AP/환경 이력을 확인한다. PRESTART_REJECT는 실패/미시작 원장에 남긴다.
4. 실제 gate를 통과한 경우에만 새 claim과 start_approval를 생성한다. I4→F4→DEV16까지만 먼저 수집한다. 120초 dispatch 종료·비선점 drain·210초 이상 센서 양경계를 보존한다.
5. 기기 원자료와 host HAL raw/읽기시각을 회수하고 bytes/SHA 목록을 만든다. 로컬 회수 도구와 validator로 요청 전량·센서·실패/미완료를 검산한다.
6. DEV 검토 후 freeze를 등록하고 새 독립 CONFIRM40을 수행한다. 결과에 따라 기한·작업량·평가창을 바꾸지 않는다.

`d1_a24_laptop_commands.py`는 정확 바이트·서명·도구·manifest와 별도 승인 결합을 검사해 **나중의 argv만 출력**한다. subprocess/기기 실행 기능이 없다. 미승인·미결합 입력에서는 BLOCKED로 반환하며, 오늘의 준비 파일로 실행가능 명령을 발급하지 않는다. 실제 AP gate와 새 claim 작성은 별도 승인된 실측 단계에서 수행한다.

기기 단계에서 검토할 command 종류는 `adb -s <승인 serial> install`, `push`/`run-as` staging, 정확 component `com.example.d1check.benchmarkrunner.modelprobe/com.example.d1check.benchmarkrunner.A24PreparationActivity`의 `am start`, `dumpsys thermalservice` raw 수집, `run-as` tar/회수다. 이 문서는 자동 실행 스크립트가 아니다. 구체 argv는 exact local bindings와 별도 future authorization을 넣은 명령 검토 도구가 출력한다.

아래는 **별도 실측 지시 이후에만** 채울 미래 제어기 호출 형식이다. 현재 로컬 paths/preflight 파일은 실행 config/허가 파일이 아니므로 여기에 그대로 넣지 않는다. 새 등록과 동결 gate가 없으면 실행을 거절한다.

```powershell
python -B tools/d1_a24_laptop_control.py '<새 승인 session_manifest.json>' '<미래 execution_config.json>' --future-authorization '<별도 control_authorization.json>' --frozen-gate '<실제 검증 뒤 frozen_gate.json>' --execute-authorized
```

`execution_config`에는 exact manifest/gate SHA, APK·ADB 파일 경로/SHA와 signer identity, flat input bundle·전 파일 bytes/SHA, 새 registry/output root, `source_root`·SOURCE_SHA256.json 경로/SHA, host dependency lock 경로/SHA를 결합한다. 제어기는 목록의 source 파일을 전수 재검산한다. ON이면 실제 Perfetto CLI 검증과 profile SHA도 필요하다. CONFIRM에는 I4/F4/DEV16 시도 원장과 예측/분석 동결 certificate를 추가한다. actual gate/기기 identity 값은 준비 단계에서 만들어 넣지 않는다.

argv만 출력하는 `d1_a24_laptop_commands.py`의 preview 허가 스키마는 `a24-laptop-future-authorization-v1`이고, 실제 제어기의 허가 스키마는 `a24-laptop-control-authorization-v1`다. preview 출력은 설치 전 프로세스 검사·실제 gate·원장·cleanup 확인을 수행하지 않으므로 그 argv를 일괄 실행 스크립트로 사용하지 않는다. 나중의 실행은 제어기로 모든 검사를 거친다.

## 회수 후의 해석

미래 제어기는 base/:model_probe/:a24_preparation 세 프로세스와 owner를 설치 전에 확인한다. summary만으로 완료 처리하지 않으며 정상 summary와 `DRAINED` cleanup·실제 worker 반환 확인을 기다리고 tar 회수본을 재검산한다. 오류·timeout·회수본 불일치는 FAIL과 부분 원자료를 보존한다. cleanup 다음의 최종 journal `fd.sync/close` 자체는 host가 별도로 관측하지 않는다는 한계를 회수 metadata에 남긴다.

모의 실행의 임의 duration은 회귀 fixture이며 기기 예측·실측 값이 아니다. actual timer overshoot와 명목 WAIT3.2초를 구분한다. C는 output_ready, D는 durable readback 완료를 응답으로 쓰고 AVAILABLE은 점유 종료로만 쓴다. 서비스/비용의 창, 일반 late drain, 미완료 요청을 모두 남긴다. 이전 성공 세션을 새 소스/APK 검증으로 전용하지 않는다.
