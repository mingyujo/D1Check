# MODEL-02B 기기 이식형 모델 probe 계약

- 문서 버전: 2 / 2026-09-18
- 상태: **MODEL_02B_HOST_EXEC_CODE_PASS / host mock 동작 검증, 실제 ADB·Android 실기기 미검증**
- 상위 계획: [PROJECT_PLAN.md](PROJECT_PLAN.md) 개정 4.4
- 입력 판정: [MODEL_02_INVENTORY.md](MODEL_02_INVENTORY.md)의 EfficientNet-Lite0 host PASS와 EfficientDet-Lite0 비배포 연구용 조건부 PASS
- 대상: Galaxy A24 `SM-A245N`을 첫 pilot·주평가 기기로 사용하고, 같은 seam과 manifest로 최소 한 대의 추가 Android 기기를 후속 probe한다. 추가 기기 모델은 아직 미선정이다.
- protocol/schema: `model-probe-v1` / `1`. debug source set과 `tools/d1_model_probe.py execute-seam`에 bounded host 실행기가 구현됐지만 실제 기기 PASS와 finalized 실행기는 아니며 기존 v1/v2/calibration과 분리한다.

## 1. 목적과 현재 코드 경계

이 단계는 두 모델이 각 승인 기기의 CPU와 GPU 후보 경로에서 실제로 초기화·실행되는지, 출력 계약과 최소 품질이 유지되는지, 메모리·cold/warm 비용이 어느 정도인지 확인하는 **실행 가능성 probe**다. 첫 구현·pilot은 A24에서 하되 loader·manifest·artifact schema와 host 도구에 `SM-A245N`을 하드코딩하지 않는다. deadline 선정, 혼합 요청 성능, scheduler 효과, 일반 정확도 평가는 아직 하지 않는다.

현재 `ModelLoader`는 APK asset의 MobileNet V1만 mmap하고, `LiteRtCalibrationRuntimePool`은 FLOAT32 `[1,224,224,3] -> [1,1001]`을 하드코딩한다. 따라서 새 파일을 기기에 복사하는 것만으로는 실행할 수 없다. 기존 loader/calibration 의미를 바꾸지 않고 debug 전용 probe seam을 추가해야 한다.

기존 LiteRT GPU 생성 성공은 full delegation 증명이 아니다. GPU cell은 `delegate_evidence.json`에서 `TfLiteGpuDelegateV2`가 `X/Y` node를 `X=Y>0`으로 대체하고 GPU delegate kernel이 생성됐으며 apply failure·restored plan·unsupported op·CPU fallback 증거가 없을 때만 `verified_full`이다. 로그가 없거나 형식이 달라 판정할 수 없으면 성공으로 추정하지 않고 `unverified`로 남긴다.

## 2. 배포·저장 경계

EfficientDet exact binary의 license 귀속은 미확인이다. 다음 경계를 강제한다.

- model/sample binary를 Git, PR, APK, AAB, 팀 공유 ZIP, 제출 재현 bundle에 넣지 않는다.
- 각 기기 실행자는 version-pinned URL에서 직접 내려받고 host에서 byte count와 SHA-256을 검증한다. 팀원이 내려받은 model/sample binary를 다른 기기 실행자에게 전달하지 않는다.
- app에는 `INTERNET` 권한이나 model downloader를 추가하지 않는다.
- host staging 위치와 기기 입력 위치는 결과 artifact 위치와 분리한다.
- 기기 임시 입력은 실행 종료·실패 cleanup에서 삭제하고 삭제 확인을 기록한다.
- 결과 artifact에는 URL·bytes·SHA-256·license 상태·실행 결과만 남기고 model/sample bytes는 넣지 않는다.
- 시연 APK 또는 공유 가능한 재현 bundle을 만들기 전 exact license/NOTICE를 확보하거나 명시적으로 라이선스된 artifact로 교체한다.

기기 입력 root는 app-private `files/model-probe-inputs/<session UUID>/`, 결과 root는 `files/model-probe-v1/<session UUID>/`로 분리한다. host가 먼저 `/data/local/tmp/d1check-model-probe/<session UUID>/`의 `.part`에 전송하고, debuggable APK의 `run-as`로 app-private `.part`에 복사한 뒤 size/hash readback과 atomic rename을 완료한다. 어느 단계든 기존 파일·symlink·경로 이탈·hash 불일치는 fail-closed다. shared temp는 app-private 검증 직후 삭제한다.

## 3. 외부 manifest 계약

실행별 `model_probe_manifest.json`은 저장소 밖에서 만들고 그 파일 자체의 SHA-256을 실험 manifest에 기록한다. 최상위 key는 정확히 `identity`, `target`, `model`, `tensor`, `runtime`, `input`, `comparator`, `execution` 객체 8개다. 알 수 없는 key, 절대경로, 경로 구분자가 든 filename, 중복 ID/hash, `latest` URL, 대문자 또는 64자리 아닌 SHA-256을 거부한다.

| 영역 | 필수 필드 |
| --- | --- |
| identity | `schema_version=1`, `protocol_version=model-probe-v1`, UUID `session_id`, `created_utc` |
| target | 공개용 `device_id`, package, APK SHA-256, 로컬 serial, manufacturer/model, SoC/ABI, RAM, Android release/API/build fingerprint, CPU ABI/features, GPU vendor/renderer/driver 식별값, thermal capability |
| model | `task_id`, `model_id`, version-pinned HTTPS URL, filename, bytes, SHA-256, distribution policy, metadata license 상태, associated label filename/rows/SHA-256 |
| tensor | input/output count·name·shape·dtype·quantization, normalization, raw output 의미 |
| runtime | LiteRT version, CPU thread 수·XNNPACK, GPU profile/config hash, Tasks Vision exact version 또는 `not_used` |
| input | input ID, 생성 규칙 또는 URL, bytes/SHA-256, decode·resize·normalization 계약 |
| comparator | comparator ID, `atol`, `rtol`, epsilon, decoded label/box/score 규칙 |
| execution | backend, cold/warm 반복, maximum duration, timeout·cleanup policy |

고정 model 항목은 다음과 같다.

| task | model ID | bytes | SHA-256 | 정책 |
| --- | --- | ---: | --- | --- |
| classification | `efficientnet-lite0-float32-v1` | 18,582,189 | `6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0` | external verified input; metadata Apache-2.0 |
| detection | `efficientdet-lite0-float32-v1` | 13,836,895 | `40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58` | external research-only; no redistribution |

EfficientNet은 내장 `labels_without_background.txt` 1000행, SHA-256 `e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f`를 사용한다. EfficientDet는 내장 `labels.txt` 90행, SHA-256 `f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2`를 사용한다. 외부 label을 조용히 바꾸지 않는다.

## 4. 입력과 비교 규칙

### 4.1 raw LiteRT 배선 입력

정책 효과나 일반 품질이 아니라 CPU/GPU tensor·수치 배선을 검사하기 위해 seed 0, 1, 2의 deterministic RGB pattern을 기기에서 생성한다.

```text
R=(3*x + 5*y + 17 + 29*seed) mod 256
G=(11*x + 7*y + 29 + 31*seed) mod 256
B=(13*x + 19*y + 43 + 37*seed) mod 256
```

EfficientNet은 224×224와 metadata의 `(RGB-127.0)/128.0`, EfficientDet는 320×320와 `(RGB-127.5)/127.5`를 사용한다. 입력 FLOAT32 little-endian bytes와 SHA-256을 backend마다 비교한다.

raw CPU/GPU 비교는 기존 `combined-tolerance-v1` 규칙을 재사용한다: `atol=1e-4`, `rtol=1e-3`, relative epsilon `1e-6`, 같은 tensor 계약, non-finite 0. EfficientNet은 argmax·top-5도 기록한다. EfficientDet의 raw score/location은 decode 전 값이라고 명시하고 각각 비교한다. full delegation이 검증되지 않으면 수치가 맞아도 GPU cell은 PASS가 아니다.

### 4.2 decoded detector golden

Tasks API 배선은 공식 `cat_and_dog.jpg` 69,041 bytes, SHA-256 `cfa90c34bb93021165e48bd22cfc20dbbb0440ff638a54878939bf30d362e824`, score threshold 0.5로 확인한다. 파일도 외부 입력으로 취급해 저장소·APK·결과 bundle에 넣지 않는다.

CPU 기준과 GPU 후보를 score 내림차순, label, box 순으로 canonicalize한다. detection count와 label 순서는 같아야 하고, 각 pixel box 좌표의 절대 차이는 2 이하, score 절대 차이는 `1e-3` 이하, non-finite는 0이어야 한다. 이 engineering smoke 기준은 첫 A24 결과를 본 뒤 완화하지 않는다. host의 cat/dog 두 detection은 배선 golden일 뿐 일반 정확도 기준이 아니다.

Android decoded 경로는 MediaPipe Tasks ObjectDetector의 정확한 API 호출 전체를 `tasks_detect_ns`로 측정한다. 내부 inference만 분리되지 않으면 이를 `Interpreter.run_ns`라고 부르지 않는다. [공식 Android sample](https://github.com/google-ai-edge/mediapipe-samples/blob/main/examples/object_detection/android/app/build.gradle)이 사용하는 Tasks Vision `1.0.0`을 debug-scoped **build 후보**로 고정했다. 기존 LiteRT `1.4.2`와의 native dependency 충돌·APK 크기·A24 로딩 검증 전에는 승인 runtime으로 승격하지 않는다. `latest.release`는 금지한다.

## 5. debug 전용 구현 seam

`MODEL-02B-SEAM`은 다음 최소 단위로 구현한다.

1. `src/debug`의 unexported probe component와 debug-only host entry를 사용한다. release variant와 기존 calibration/formal/diagnostic entry에는 연결하지 않는다.
2. `ProbeModelFile`은 app-private session root 아래 regular non-symlink file만 허용하고 canonical containment·filename·bytes·SHA-256을 확인한 뒤 read-only mmap한다. 기존 `ModelLoader`는 변경하지 않는다.
3. raw adapter는 manifest tensor 계약과 실제 Interpreter tensor를 대조하고 CPU/GPU 사이에 silent fallback하지 않는다.
4. decoded adapter는 Tasks Vision dependency를 debug scope에만 추가하고 검증된 read-only direct/mapped buffer를 `BaseOptions.setModelAssetBuffer()`로 전달한다. CPU/GPU delegate, threshold, max results를 명시하고 초기화·호출·close는 같은 전용 worker thread에서 수행한다.
5. timeout은 host와 device 양쪽에서 bounded로 집행하고 최초 오류를 보존한다. cleanup 오류는 suppressed로 기록한다.
6. host 도구는 download→hash→stage→launch→log/artifact pull→validate→input cleanup 확인을 담당한다. 임의 shell 문자열을 조립하지 않고 고정 argv와 검증된 UUID/filename만 사용한다.
7. 기기별 capability와 결과는 `device_id`로 분리한다. serial·model 문자열로 코드 분기하거나 특정 모델명을 allowlist하여 통과시키지 않는다. 지원 여부는 실제 runtime 초기화·tensor/quality·delegate evidence로 판정한다.

Tasks Vision dependency가 기존 LiteRT native library와 충돌하면 기존 runner 의존성을 억지로 교체하지 않는다. 별도 debug probe module을 만들거나 decoded A24 cell을 보류하고 `SCOPE-03`에서 범위를 재판정한다.


현재 첫 구현은 manifest/file fail-closed, raw adapter, decoded adapter, 격리 debug entry와 host validation·argv plan까지만 제공한다. debug entry 결과는 `seam_smoke_only_unfinalized`이며 성공 provenance를 만들지 않는다. 실제 download/subprocess/ready/pull/delegate-log finalization과 고정 artifact 전체 생성은 다음 구현 gate다.

## 6. 실행 순서와 반복

실기기 실행은 별도 승인 후 먼저 A24에서 다음 순서로 한 session만 pilot한다.

1. ADB serial·package/APK hash·기기 정보·battery·charging·screen·thermal status를 기록한다. thermal status 2 이상이면 시작하지 않는다.
2. shared/app-private stale input과 이전 probe process가 없음을 확인한다.
3. manifest와 두 model, sample input을 host에서 다시 검증하고 app-private staging을 완료한다.
4. 각 model/backend cell에서 독립 cold create→1회 invoke→close를 3회, 같은 instance warm invoke를 10회 수행한다. 이는 smoke 반복이며 formal 반복 수가 아니다.
5. raw equivalence, decoded detector, peak Java/native/PSS, initialization·invoke·close 시간을 기록한다.
6. delegate log를 session 경계로 수집해 host에서 `delegate_evidence.json`을 만든다.
7. artifact exact set·identity·hash를 검증한 뒤 app-private input과 shared temp를 삭제하고 부재를 확인한다.

성능 순서 무작위화와 thermal cooling/stability는 `PROFILE-02`에서 별도로 강화한다. 이 smoke의 시간으로 deadline이나 simulator service distribution을 정하지 않는다.

A24에서 seam과 cleanup까지 통과한 뒤 추가 기기는 같은 APK·model/input hash·manifest schema·comparator/tolerance로 별도 session을 실행한다. 기기 identity와 capability 값만 달라질 수 있다. 첫 추가 기기 결과를 본 뒤 tolerance·모델·runtime·GPU gate를 완화하지 않는다. GPU가 unsupported/unverified여도 CPU probe는 계속할 수 있으며, 해당 기기의 허용 cell 축소를 결과로 남긴다.

## 7. 결과 artifact와 판정

결과 root의 고정 집합은 `metadata.json`, `events.jsonl`, `raw_equivalence.json`, `decoded_results.json`, `memory.json`, `delegate_evidence.json`, `summary.json`, `provenance.json`이다. 모든 파일은 같은 `device_id`, session ID, APK/model/input/config hash를 가져야 한다. 실패 session도 가능한 범위에서 오류·cleanup 상태를 남기되 성공 provenance로 위장하지 않는다. model/sample bytes, `.part`, 추가 파일은 허용하지 않는다.

cell 상태는 `passed`, `failed`, `unsupported`, `unverified` 중 하나다.

| 전체 판정 | 조건 | 다음 단계 |
| --- | --- | --- |
| `MODEL_02B_FULL_PASS(device_id)` | 해당 기기에서 두 task의 CPU와 verified GPU cell, raw equivalence, detector decoded gate 모두 통과 | 해당 기기의 두 task·두 backend profile 허용 |
| `MODEL_02B_REDUCED_PASS(device_id)` | 해당 기기에서 두 task CPU 통과, 최소 한 task의 verified GPU 통과 | 가능한 cell만 scheduler 후보로 사용하고 task별 자유 routing 주장을 축소 |
| `MODEL_02B_CPU_ONLY(device_id)` | 두 task CPU 통과, GPU는 모두 unsupported/unverified | queue/order 중심 축소 재현만 허용; GPU 효과 추정 금지 |
| `MODEL_02B_FIX_REQUIRED(device_id)` | 실행·artifact·cleanup의 수정 가능한 production 결함 | 결함 수정·회귀 검증 후 같은 manifest로 재실행 |
| `MODEL_02B_SCOPE_REVIEW(device_id)` | task CPU 실패, Tasks 충돌 또는 연구 gate 충족 불가 | 해당 기기 제외 또는 SCOPE-03에서 작업쌍·runtime 재판정 |

프로젝트는 A24가 `FULL` 또는 `REDUCED`여야 CPU/GPU 배정 주평가로 진행한다. 추가 기기는 `CPU_ONLY`도 축소 재현으로 유효하지만 A24 결과의 GPU 일반화 근거가 아니다. 기기별 판정을 합쳐 하나의 PASS로 만들지 않는다.

## 8. 구현 전 검증 목록

- debug source set이 release APK에 포함되지 않는 빌드 테스트.
- exact Tasks Vision dependency와 transitive native library 목록·라이선스·APK delta 기록.
- external file containment/hash/size/symlink/duplicate/stale/.part fail-closed 테스트.
- model tensor mismatch, CPU/GPU init failure, timeout, close failure, missing delegate evidence 테스트.
- raw comparator와 decoded canonicalization/tolerance 테스트.
- host dry-run에서 network·ADB·manifest write 0회 확인.
- A24와 다른 합성 device manifest를 사용한 host 테스트에서 path·argv·artifact identity가 섞이지 않고 model 문자열 하드코딩 없이 분리되는지 확인.
- 기존 119 JVM, Python, lint, assemble과 v1/v2/calibration 회귀 검증.

이 문서의 경로·protocol·명령은 구현 계약이다. 실제 파일·CLI가 생기기 전 존재하는 기능처럼 사용하지 않는다.



## 10. Host 실행기 구현 상태

`tools/d1_model_probe.py execute-seam`은 다음 단계만 실제로 수행한다.

1. manifest·model·sample·APK의 고정 파일 집합과 SHA-256을 ADB 호출 전에 검증한다.
2. manifest의 `adb_serial`과 CLI `--serial`을 일치시키고 허용된 serial 문자만 받는다.
3. canonical session UUID 아래의 shared/app-private 입력 경로가 기존에 없음을 확인한다.
4. 각 입력을 `.part`로 push/copy하고 shared·app-private 양쪽 SHA-256을 확인한 뒤 atomic rename한다.
5. `am start -W` 성공을 Activity dispatch acknowledgement로만 기록한다. 이를 모델 ready로 해석하지 않는다.
6. app-private `summary.json`의 non-empty 상태를 device maximum duration과 최대 60초 host grace 안에서 polling한다.
7. summary를 `exec-out run-as ... cat`으로 pull하고 protocol/session/device/model/backend identity와 `seam_smoke_only_unfinalized` 상태를 검증한다.
8. 성공·실패·timeout 모두 exact session 입력 경로만 bounded cleanup하고 부재를 확인한다.
9. host에는 `<output-root>/<session>/summary.json`과 `host_execution.json`을 남긴다. 두 파일은 실행·실패 관측 증거이며 finalized 8-file provenance를 대신하지 않는다.

실행 형식:

```powershell
& $python -B tools/d1_model_probe.py execute-seam `
  --manifest $manifest `
  --input-root $inputRoot `
  --apk $runnerApk `
  --adb $adb `
  --serial $serial `
  --output-root $outputRoot
```

host 실행기는 APK를 설치·삭제하거나 `pm clear`를 실행하지 않는다. 설치 APK hash는 device Activity가 manifest와 대조한다. 서명이 다르거나 APK가 설치되지 않았거나 `run-as`가 불가능하면 fail-closed다. GPU 결과는 device summary가 성공해도 delegate log finalization 전까지 `unfinalized`다.

2026-09-18 격리 검증에서는 `tools.test_d1_model_probe` 14건과 `compileall`이 통과했다. 성공 경로, shared SHA 불일치, bounded summary timeout, cleanup, fixed argv/`shell=False`를 mock subprocess로 관찰했다. 전체 저장소 Python 회귀와 실제 ADB·A24·추가 Android 기기는 이 변경 이후 아직 실행하지 않았다.
