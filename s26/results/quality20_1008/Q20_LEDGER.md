# Q20 대표 입력 20장 품질 — 원장 (레포 사본, `D1_ondevice\sim\out_quality20\freeze_q20.txt` 와 같은 내용)

> 작업 클론 `C:\Users\rhoyo\AndroidStudioProjects\D1Check_quality` · 브랜치 **`s26-quality20`** (시작 HEAD `e2bedf1` = `origin/s26-mixreq`, R3 v2 코드) · 새 모듈 `:quality-runner` (`com.example.d1check.qualityrunner`) · 측정 앱 `npu-runner` (`5ac485e3…`) · `request-runner` 무변경.
> 표기 [P] 실측 · [D] 인용 · [E] 추정 · `미확인`. 주소 · 시리얼은 `<IP:PORT>` · `<SERIAL>`. **결과 (판정 · 지표) 는 2부 판정기 출력 전에 이 파일에 쓰지 않는다.**
> 우선순위: 프롬프트 Q20 > 등록 v1 (`48b59382…`) > 조민규 10/8 회신 #7 > CLAUDE.md.

## Cowork 10/8 20:4x 결정 (영훈) — 결과 전 고정

- **품질 20장은 새 APK 를 만들어 돌린다** (조민규 요청 #7 의 (a)). 조민규 10/8 회신 #7 [D `D1_1008_reply\01_reply_13.txt`]: "새 APK의 20장 확인은 그 APK·모델·전처리·엔진에 귀속하고 이전 측정 APK의 품질 인증으로 자동 전용하지 않는다. 20장만으로 일반 정확도를 인증하지 않는다." → 이 결과는 **`quality-runner` APK · CompiledModel 2.2.0 · 받은 텐서 그대로 (전처리 0)** 에 귀속하며 측정 앱 `5ac485e3…` · `request-runner` 의 품질 인증이 아니다.
- 영훈 10/9 18:3x: "핸드폰 연결 되어 있으니까 포트, 온도 이런거 묻지 말고 나한테 질문하는거 없이 쭉 진행해" → 질문 없이 진행 · 2부 연결은 `adb devices -l` 로 스스로.

## 결과 전 고정 (1부, 폰 0) [P]

- **동률 규칙**: top-k = 점수 내림차순 → class index 오름차순 (R1 `ClassificationDecoder.top5` · A24 decoder · 참조 JSON `decoder.ordering` "score descending then class index ascending" 과 같음). cosine 은 0-norm · 비유한이면 null = "계산 불가" (기록 · 필수 실패 아님 — 비유한은 이미 필수 실패).
- **후보 = 1회째 출력 (run0)**. 2회째 (run1) 는 "2회 비트 동일" 열에만 (비트가 다르면 run1 의 최대|차| 도 기록).
- **필수**: 1000개 전부 finite · 원소 수 1000 (= `[1,1000]`) · float32 (앱이 `readFloat()` 을 LE float32 로 적음, 4,000 B) · 라벨 순서 = 참조 (CPU/GPU 는 참조와 같은 모델 `6c7ab0a6…` · NPU 는 그 모델에서 컴파일한 AOT `311e4aac…` [D aot_manifest input_sha256]).
- **판정 문구** (등록 §3 그대로): CPU 위반 0 → "참조와 일치 (FP32 기존 경로 기준)" / 위반 → "불일치 (허용식 위반 이미지 […])" / 필수 실패 → "실패 (필수 항목: 이미지 […])" · GPU 실제 정밀도 FP32 로그 확인 시 CPU 기준, 아니면 "지표만 · PASS 보류 (GPU 실제 정밀도 미확인)" · NPU "지표만 · 품질 PASS 보류 (FP16 합격선 미등록)" (허용식 미적용 · 위반 수는 기록만) · runtime 미생성 "실패 (runtime 생성 실패)" · 증거 FAIL 꼬리표 "실행 증거 FAIL — 실행 장치 미확인" · CPU 가 일치 아니면 GPU · NPU 에 "CPU 기준 미달 — 품질로 해석하지 않음".
- **GPU 실제 정밀도 읽기 규칙** (등록 §2 "로그에서 읽을 수 있으면"): 창 안 러너 PID 줄이 `/precision.*(fp32|f32|float32)/i` 에 맞고 `/(fp16|f16|float16|half)/i` 줄이 없을 때만 FP32, 아니면 `미확인`. R3 S1 실기기 로그 (같은 엔진) 에는 그런 줄이 없었다 → `미확인` 이 예상 결과.
- **증거 창** = `D1Q20 runtime create_start` ~ 첫 이미지 `image_end idx=0` (생성 창 ∪ 첫 이미지 창). 함수 = R2 `mixreq_validate.gpu_evidence` · `npu_evidence` import (무변경, 표시 이름만 번역) · CPU 는 `compiled_model_evidence.evaluate_cpu` 조건을 같은 창에 (XNNPACK x==y>0 · "Created … XNNPACK delegate" · 다른 delegate 교체 0 · 실패 줄 0). ENN 로드 줄은 필요조건일 뿐.
- **2부 운영 규칙**: backend 마다 앱 1회 (CPU → GPU → NPU) · 사이 60 s · 열 확인 HAL SKIN ≤ 34 · BAT ≤ 32 (start_gate 는 plugged 0 을 요구하고 플래그로 못 끔 → 직접 확인) · 상한 15 분 · backend 실패 (앱 실패 · 생성 실패 · 증거 FAIL) 는 새 run_id 로 한 번만 재시도 · `screen_off_timeout 86400000` 맨 먼저, 끝에 600000 · `/data/local/tmp/quality20/` 보존.

## 1-1 클론 · Git 밖 파일 (10/9 18:3x) [P]

- `git clone -b s26-mixreq` → `D1Check_quality` · `switch -c s26-quality20` · `core.autocrlf true` · HEAD `e2bedf1`.
- 등록 blob `git show a56ebbf:d1sim/docs/품질20장_사전등록_v1.md` SHA-256 `48b593828af36a1b98830dde9d8da0224ce5b881185f69cdaa5d9ede8317d670` = OneDrive 원본 동일 ✔.
- Git 밖 복사 (원본 `D1Check_mixreq`, 읽기만): `local_models/efficientnet_lite0.tflite` `6c7ab0a6…` ✔ · `npu-runner/src/main/assets/models/efficientnet_lite0_Samsung_E9965.tflite` `311e4aac…` ✔ · dispatch `.so` `f08656a6…` → `quality-runner/src/main/jniLibs/arm64-v8a/` ✔ (ignore 규칙 = request-runner 와 같음). 회귀 시험용으로 npu-runner 의 MobileNet AOT 2개 (`1415b2c8…` · `36c75e6a…`) · npu-runner dispatch `.so` · `local_inputs/{reference_pc,canonical_v123,canonical,public}` 도 복사 (전부 git 밖 · `.git/info/exclude`).

## 1-2 입력 수신 검증 (18:3x) [P] — `INPUT_CHECK.md`

①~⑤ 전부 통과 (zip `3bf46599…` 3,807,484 B · manifest 42/42 · 참조 JSON `148e3be8…` · input SHA 재계산 20/20 · 602,112 B 20/20) + 참조 raw = JSON 값 비트 동일 20/20 (값 미출력). 보관 `D1_ondevice\quality_inputs_1006\` (zip 사본 + extracted).

## 1-3 `:quality-runner` (18:4x) [P]

- 파일: `build.gradle.kts` (request-runner 본 · litert 2.2.0 · minSdk 31 · arm64 · useLegacyPackaging · noCompress tflite) · `AndroidManifest.xml` (`uses-native-library libenn_public_api_cpp.so` · `QualityActivity`) · `Runtimes.kt` (request-runner blob `7f9ba0a7…` 의 Backend · RuntimeSpec · InferenceRuntime · CompiledModelRuntime **무변경 사본**, TaskRuntime 제외) · `Json.kt` (blob `c2bac7dd…` 사본) · `ArtifactStore.kt` (EventLog.kt blob `b9c88e3b…` 의 ArtifactStore) · `MixreqContractSubset.kt` (laneOf · taskOf · ENGINE · LITERT_VERSION 만) · `FileSha256.kt` · `MiniJson.kt` · `F32le.kt` · `QualityContract.kt` · `QualityManifest.kt` (fail-closed) · `QualityEngine.kt` · `QualityActivity.kt` (intent `d1_q20_manifest` · `d1_q20_backend` · `d1_q20_run_id`, 태그 `D1Q20`, watchdog 840 s).
- 분류 키: `classification_CPU` (원본 · `CpuOptions(numThreads=1)`) · `classification_GPU` (원본 · `GpuOptions(FP32)`) · `classification_NPU` (AOT · `Accelerator.NPU` 하나 — litert-api 가 native 에 {NPU, CPU} 로 넘기는 사실은 `optionsRecord.accelerators_passed_to_native` 에 기록). 입력 602,112 B → LE FloatArray 그대로 → `writeFloat` (변환 0) · run 2회 · 출력 `readFloat()` → `<idx>_<id>.run{0,1}.f32le` + SHA · finite · 원소 수 · `run()` ns · `.part`→fsync→rename · `summary.json`.
- JVM 시험 **11/11** (F32leStoreTest 3 · QualityManifestTest 2 (위반 20종 전부 거부) · QualityEngineRoundTripTest 6: 왕복 20장 40 raw · SHA 실패 + run 실패 보존 · NaN/드리프트 기록만 · 생성 실패 summary · 모델 SHA 불일치 → 생성 안 함 · 폴더 존재 거부). Robolectric 없음 (엔진이 Context 무관).
- APK `quality-runner/build/outputs/apk/debug/quality-runner-debug.apk` **14,321,588 B · SHA-256 `bc9701e334baa397e4a26d91eef88ab6b7c1b52f890cd06fb95026dfcce97844`** (18:44, `gradlew :quality-runner:assembleDebug`) → 사본 `local_inputs\apk\quality-runner-debug_bc9701e3.apk` (git 밖). 안에 `.tflite` 0 · `lib/arm64-v8a/libLiteRtDispatch_Samsung.so` 포함.
- 기존 모듈: `git diff --stat origin/s26-mixreq -- npu-runner request-runner benchmark-runner app telemetry-contract tools d1sim gradle` **빈 diff** · `settings.gradle.kts` +4 줄 (주석 3 + include 1).

## 1-4 호스트 `s26/tools/quality20/` (18:5x) [P]

| 파일 | SHA-256 (커밋 ② 전 · 결과 전) | 시험 |
|---|---|---|
| `q20_common.py` | `fcb6f3016bdb09014f1f1ef806e756611f6eeed12af7db07f71aeece0a192e6d` | pytest |
| `q20_run.py` | `8863ee6954d50a7d70d801fd7983c1d2effe15875e1efebfc0abfe5c75eead39` | `--dry-run` (가짜 모델 → SHA 거부 · 등록 모델 → CPU→GPU→NPU 순 · force-stop 은 quality-runner 만) |
| `q20_evidence.py` | `8d45c551e941de43e1658bac495420d4648888b336894c268ec076559715886d` | `--selftest` **21/21** (CPU 5 · GPU 7 · NPU 7 + run_id/backend 오매칭 2) |
| **`q20_judge.py` (판정기)** | **`616e7490d5eafd9534453d872cc71c473d28f0d189687097e0a5f11bf8964d42`** | `--selftest` **PASS 26 항목** (참조=후보 → CPU 일치 · +1e-3 → 위반 1 불일치 · NaN → 필수 실패 · top-1 바꿈 · top-5 순서만 (5/5) · 2회 비트 다름 · NPU 허용식 미적용 · GPU 미확인 → 보류 · GPU FP32 → CPU 기준 · CPU 미달 꼬리표 · 증거 FAIL 꼬리표 · runtime 미생성 · 이미지 실패 보존 · 0-norm 계산 불가 · 동률 · 허용식 경계) — 합성 참조만 사용, 실제 참조 값 열람 0 |
| `test_quality20.py` | `bfcd7ae8384013aa2bf3dec1fa1541db60e21da6a59d4a6726f6239996a442aa` | `py -3 -m pytest s26/tools/quality20` **7 passed** |

실제 참조 loader (`q20_judge.load_reference`) 를 1부에서 한 번 실행 → 20장 fail-closed 검사 전부 통과 (runtime ai-edge-litert 2.2.0 · cpu_threads 1 · 값 미출력).

## 1-5 회귀 · 커밋 (19:0x) [P]

- 회귀: `gradlew :request-runner:testDebugUnitTest :npu-runner:testDebugUnitTest --rerun-tasks` → **request-runner 32/32 (skipped 0) · npu-runner 61/61** = 기준 (첫 실행은 git 밖 파일이 없어 npu-runner 9 실패 · request-runner 2 skipped → MobileNet AOT 2 · npu-runner dispatch `.so` · `local_inputs/{reference_pc,canonical_v123,canonical,public}` 를 `D1Check_mixreq` 에서 복사한 뒤 기준과 같음 — 코드 원인 아님).
- `:quality-runner:assembleDebug` 재실행 (커밋 ① 뒤) → UP-TO-DATE · APK SHA `bc9701e3…` 그대로 (= 커밋 ① 소스).
- **커밋 ① `c600a20bd6035f33075829be5c3bbadc9f7a31c1`** (2026-10-09 19:00:03 +0900) "quality-runner: S26 대표 입력 20장 품질 실행기 (CompiledModel 2.2.0 · 폰 실행 전)" — 19 파일 +1,195 · PAT 0 · 바이너리 0 · `.so/.tflite/.apk` 0.
- 커밋 ② = `s26/tools/quality20/` 5 파일 + `s26/results/quality20_1008/{INPUT_CHECK.md,Q20_LEDGER.md}` (`git add -f`, 루트 `.gitignore` `results/` 때문) — SHA 는 OneDrive `freeze_q20.txt` 와 2부 커밋 ③ 의 원장에 적는다.
