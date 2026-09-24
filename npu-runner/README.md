# `npu-runner` — S26 NPU 실행기 (G3/G4)

`benchmark-runner` 는 **한 줄도 바꾸지 않았다.** NPU 는 delegate 가 아니라 두 번째 실행 엔진
(LiteRT Next `CompiledModel`) 이라 별도 모듈로 붙인다. 상위 스펙: `measure/s26/npu/runner/NPU_RUNNER_SPEC.md`.

## 왜 앱인가

`run_model` 셸 바이너리로는 G3 가 두 번 막혔다 (`npu/results/G3_run_model_*.txt`).

| 시도 | 실패 | 원인 |
|---|---|---|
| 셸 + ENN 체인 | `MediumInterface initialization failed` | 셸 프로세스에 binder 스레드 풀이 없다 |
| 셸 + `/vendor/lib64` 통째 LD_LIBRARY_PATH | `CANNOT LINK EXECUTABLE … libandroidfw.so` | 시스템 lib 이 vendor 사본에 가려진다 |

둘 다 **앱 프로세스에는 없는 제약**이다. Geekbench AI 1.7(TFLite+ENN)이 같은 폰·같은 펌웨어에서
완주했으므로 폰이나 ENN 이 아니라 실행 방식의 문제로 본다.

## 구성

```
npu-runner/
  build.gradle.kts
  src/main/AndroidManifest.xml
  src/main/java/NpuRunnerActivity.kt      실행·기록·intent 프로토콜
  src/main/java/NpuBenchmarkEngine.kt     CompiledModel 래퍼 (측정 경계 정의)
  src/main/java/NpuDeterministicInput.kt  benchmark-runner 와 비트 동일한 합성 입력
  src/main/java/NpuQualityGate.kt         NPU 품질 동등성 판정 (아래 "NPU 합격 기준")
  src/main/jniLibs/arm64-v8a/
    libLiteRtDispatch_Samsung.so          f08656a642c46e7b…  (LiteRT main @9380426b, NDK r27c, Bazel 7.7.0)
  src/main/assets/models/
    mobilenet_v1_1.0_224_Samsung_E9965.tflite        8,901,712 B  1415b2c87d01b67a…  31/31 ops → 1 partition
    mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite  4,605,104 B  36c75e6acdb71162…  31/31 ops → 1 partition
    aot_manifest.json                                컴파일 provenance
```

원본 `mobilenet_v1_1.0_224.tflite` 는 `benchmark-runner` 의 assets 를 소스셋으로 공유한다
(17 MB 를 두 번 커밋하지 않기 위함). CPU 대조 실행에 쓴다.

> `*_Samsung_E9965.tflite` 는 `DISPATCH_OP` 커스텀 op 가 든 **AOT 산출물**이다.
> CPU Interpreter 로 열리지 않는 것이 정상이다 — "동작 확인" 을 CPU 로 하려 하지 말 것.

## 실행

**수동** — 앱 아이콘 실행. 기본값 = NPU / FP32 컴파일 모델 / warmup 5 / 50회. 화면에 결과가 뜬다.

**자동**

```
adb shell am start -n com.example.d1check.npurunner/.NpuRunnerActivity ^
  --es accelerator NPU --es dtype float --ei iterations 50 --ez autofinish true
```

| extra | 기본값 | 뜻 |
|---|---|---|
| `accelerator` | `NPU` | `NPU` / `CPU` / `GPU`. **폴백을 나열하지 않는다** — 조용히 다른 자원으로 떨어지면 기록이 거짓이 된다 |
| `model_asset` | `models/mobilenet_v1_1.0_224_Samsung_E9965.tflite` | assets 안 경로 |
| `model_path` | — | 파일 경로. 주면 asset 대신 이것을 쓴다 (리빌드 없이 모델 교체) |
| `dtype` | `float` | `float` / `uint8` (INT8 컴파일 모델용) |
| `iterations` | `50` | 기록 대상 추론 횟수 |
| `warmup` | `5` | 기록에서 제외 |
| `run_id` | 자동 | 결과 파일명 |
| `autofinish` | `false` | 끝나면 Activity 종료 (배치 실행용) |
| `quality_n` | `0` (끔) | 품질 게이트 샘플 수. NPU 판정은 `32`. 타이밍 루프가 끝난 뒤에 돈다 |
| `ref_model_asset` | `models/mobilenet_v1_1.0_224.tflite` | 품질 게이트의 CPU 기준 모델 |
| `input_spec` | `lcg-unit` | 입력 생성·정규화. 아래 표. **기본값은 9/24 G4 게이트 입력 그대로** |
| `elements` | 입력 텐서에서 읽음 | 주면 텐서 원소 수와 대조만 한다 (다르면 FAILED) |

| `input_spec` | 생성 | 정규화 | 대상 |
|---|---|---|---|
| `lcg-unit` (기본) | LCG 연속 스트림 | 없음 `[0,1]` | MobileNet V1 (9/24 G4, `input_sha256 5dc1cb09…`) |
| `lcg-rgb-127-128` | 같은 LCG 의 상위 8 bit = RGB | `(RGB-127.0)/128.0` | EfficientNet-Lite0, 품질 게이트 n=32 |
| `lcg-rgb-127.5-127.5` | 〃 | `(RGB-127.5)/127.5` | EfficientDet-Lite0 (게이트는 미구현 — `NPU_DETECTOR_GATE_NOTE.md`) |
| `coordinate-rgb-classification` | 조민규 `coordinate-rgb-v1`, 표본 i = seed i (≤ 3개) | `(RGB-127.0)/128.0` | 팀 probe 입력과 비트 동일 대조용 |
| `coordinate-rgb-detection` | 〃 (320×320) | `(RGB-127.5)/127.5` | 〃 |

정규화 값은 조민규 `MODEL_02_INVENTORY.md` §4. 출력 길이(1001 / 1000)는 하드코딩하지 않는다.
출력이 2개 이상인 모델(검출)은 품질 게이트가 `NOT_APPLICABLE` 로 막는다 — `outputs[0]` 만 보고 PASS 시키지 않기 위함.

`measure/s26/npu/tools/s26_npu_go.bat` 이 연결 → 빌드·설치 → logcat 초기화 → 실행 → 결과 회수까지 한다.
NPU float 실행에는 `quality_n 32` 를 자동으로 붙인다.

## 모델 슬롯 — `aot_manifest.json` 스키마

`src/main/assets/models/aot_manifest.json` 은 **두 컴파일 배치의 병합본**이다 (`schema: npu-runner-aot-manifest-merged-v1`).
원본 manifest 두 개는 무변경으로 따로 있다 — G1 = `s26/npu/artifacts/compiled_e9965/aot_manifest.json`,
G1-B = `s26/npu/results/G1B_aot_manifest_20260924.json`. 병합하면서 모델마다 SDK 필드를 붙였다:
**배치마다 컴파일러가 다르기 때문이다 (SDK skew).**

| 슬롯 | 모델 | 배치 / SDK | 출력 SHA (앞 16) | 파티션 | 파일 위치 | APK |
|---|---|---|---|---|---|---|
| 1 | MobileNet V1 FP32 | G1 / `2.3.0.dev20260917` | `1415b2c87d01b67a` | 1/1 PASS | assets (커밋됨) | ✅ |
| 2 | MobileNet V1 INT8 | G1 / `2.3.0.dev20260917` | `36c75e6acdb71162` | 1/1 PASS | assets (커밋됨) | ✅ |
| 3 | EfficientNet-Lite0 FP32 | G1-B / `2.3.0.dev20260922` | `311e4aac8fa1d8de` | 62 ops → 1, PASS | assets (git 제외) | ✅ (Apache-2.0) |
| 4 | EfficientDet-Lite0 FP32 | G1-B / `2.3.0.dev20260922` | `f51d082dbf68bef9` | 263 ops → 1, PASS | **`local_models/`** (git 제외) | ❌ 라이선스 미확인 → `adb push` + `--es model_path` |

모델 항목 스키마 (`models[]`):

```jsonc
{
  "input": "efficientnet_lite0.tflite", "input_sha256": "6c7ab0a6…", "input_size": 18582189,
  "compile_seconds": 2.3, "failed_backends": [],
  "outputs": [ { "file": "efficientnet_lite0_Samsung_E9965.tflite",   // G1 은 "compiled_e9965/…" 접두어 → 파일명 말고 SHA 로 대조
                 "size": 10033376, "sha256": "311e4aac…",
                 "operators": { "DISPATCH_OP": 1 }, "dispatch_ops": 1, "non_dispatch_ops": 0, "verdict": "PASS" } ],
  // ↓ 병합 때 추가한 필드
  "compile_batch": "G1-B", "ai_edge_litert": "2.3.0.dev20260922", "ai_edge_litert_sdk_samsung": "2.3.0.dev20260922",
  "compiled_at": "2026-09-24T03:20:14+0000", "in_apk_assets": true, "placement_note": "…"
}
```

| 키 | `formal_npu_valid` 에서 쓰는 곳 |
|---|---|
| `outputs[].sha256` | 조건 4 — 실행한 모델 SHA 가 알려진 AOT 산출물이어야 한다 |
| `outputs[].dispatch_ops` / `non_dispatch_ops` | 조건 6 — logcat `Replacing X out of Y (DispatchDelegate)` 와 대조, `npu_partial_delegation` |
| `ai_edge_litert` | 기록만. dev20260922 산출물은 **기기 미검증** (`results/G1B_NEWMODELS_VERDICT_0924.md`) |

## 결과 읽는 법

logcat 태그 `D1NPU`. `SUMMARY_BEGIN` ~ `SUMMARY_END` 사이의 `SUMMARY[i/n]` 청크를 이어 붙이면
JSON 전문이 된다 (`run-as` 없이 회수 가능하도록 나눠 찍는다). 같은 내용이 앱 전용 저장소의
`files/npu-runner-v1/summary-latest.json` 에도 남는다.

**가장 먼저 볼 것: `available_accelerators`.**

| 관측 | 해석 | 다음 행동 |
|---|---|---|
| `NPU` 포함, 추론 성공 | **G3 통과** | CPU 대조 → pilot → formal (SPEC §6) |
| `NPU` 포함, `CompiledModel.create` 실패 | dispatch 는 떴는데 ENN 초기화가 실패 | 예외 전문을 `results/G4_*.md` 에. G0 판정 문서와 대조 |
| `NPU` 포함, `run()` 에서 `Failed to allocate tensors` | dispatch 커널 생성 실패 | logcat **`litert`**(소문자) 태그로 아래 세 줄 중 무엇이 찍혔는지 본다 |
| `NPU` 없음 | 런타임 AAR ↔ dispatch ABI 불일치 (미확인 가설) | `libs.versions.toml` 의 `litertNext` 를 올리거나 dispatch 를 그 버전으로 재빌드 |
| `System.loadLibrary("litert_jni")` 실패 | AAR 이 arm64 JNI 를 안 넣었다 | `abiFilters`, `useLegacyPackaging=false` 확인 |

`Failed to allocate tensors` 앞의 `litert` 로그 (2026-09-24 실측으로 셋 다 봤다):

| `litert` 로그 | 원인 | 조치 |
|---|---|---|
| `No dispatch library found in …/lib/arm64` | `.so` 가 디렉터리에 안 풀렸다 | `useLegacyPackaging = true` (build.gradle.kts) |
| `Loading shared library: …Dispatch…` → `Failed to load enn runtime` | 벤더 ENN 라이브러리가 앱 네임스페이스에서 안 보인다 (targetSdk 31+) | 매니페스트 `<uses-native-library android:name="libenn_public_api_cpp.so">` |
| `Found Dispatch API with an unsupported version` | 런타임 AAR ↔ dispatch ABI 불일치 | dispatch 를 AAR 과 같은 리비전으로 재빌드 (아직 관측된 적 없음) |

⚠ `available_accelerators` 의 `NPU` 는 dispatch `.so` 를 찾지 못해도 등록된다(9/24 04:14 실측).
`NPU` 가 목록에 있다는 것만으로 ABI 가 맞다고 판단하지 말 것.

## 측정 필드 이름을 분리한 이유

`Interpreter.run()` 과 `CompiledModel.run()` 은 다른 엔진이다. 조민규 계약도
"API 내부를 볼 수 없으면 API-call latency 로만 기록하고 `Interpreter.run()` 이라 부르지 않는다"
(`docs/MULTITASK_EXPERIMENT_PROTOCOL.md` §3) 라고 못 박았다. 그래서

- `engine = "litert-compiled-model"` 를 항상 같이 남긴다
- `latency_ms` = write + run + read (사용자 체감 1회 추론) — CPU/GPU 열과 같은 의미
- `run_only_ms` = `run()` 만 — 엔진 간 비교는 이쪽으로

## NPU 합격 기준은 수치 동등성이 아니다

AOT 산출물은 FP32 입력이라도 **가중치가 FP16 으로 저장**된다 (16.9 MB → 8.9 MB, 0.53배).
그래서 CPU/GPU 의 `atol=1e-4, rtol=1e-3` 동등성 게이트는 통과하지 못하는 것이 정상이다.

NPU cell 판정은 **품질 동등성**으로 한다 (SPEC §5, 결과 보기 전에 고정):

- `bit_identical_to_cpu == false` — **비트 동일이면 실패다.** NPU 가 아니라 CPU 로 돈 것
- `argmax_agreement` 32/32
- `cosine_min ≥ 0.99`

구현: `NpuQualityGate.kt`. `--ei quality_n 32` 를 주면 benchmark-runner `AccuracyPreflightEngine` 과
같은 LCG 스트림(seed `0x12345678`)으로 32 개 입력을 만들어 후보(설정된 가속기)와 CPU 기준(원본 FP32,
같은 CompiledModel 엔진)에 넣고, 요약 JSON 의 `quality_gate` 에 `verdict` 와 샘플별 값을 남긴다.
`bit_identical_to_cpu` 는 보수적으로 "32 개 중 하나라도 출력 전체가 비트 동일하면 true" 로 정의했다.

한계: 합성 입력 32 개는 CPU·NPU 모두 argmax 가 전부 112 다(9/24 실측). argmax 32/32 는 이 입력에서는
변별력이 약하고, 실질 근거는 `cosine_min` 과 비트 비동일이다. 대표 이미지셋으로 재확인할 것.

⚠ 같은 폰에서 Geekbench AI 의 ENN INT8 이미지 분류 정확도가 0.014 로 붕괴한 기록이 있다
(`npu/results/EXTERNAL_REF_GEEKBENCH_0919.md`). INT8 경로는 품질 게이트에서 떨어질 수 있다.
그것도 결과이므로 기준을 먼저 고정하고 측정한다.
