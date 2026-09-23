# `npu-runner` 구현 스펙 — S26 NPU 를 CPU/GPU 와 같은 프로토콜로 재기 (G2~G4)

작성: 2026-09-16, 영훈. 대상 독자: 조민규(인프라) / Codex. 상위 문서: `../NPU_ACCESS_PLAN_0916.md` §5.
**원칙**: `benchmark-runner`(LiteRT 1.4.2, Interpreter) 는 한 줄도 바꾸지 않는다. NPU 는 새 Gradle 모듈로 붙인다.

---

## 1. 부품 조달 (G2)

### 1.1 컴파일된 모델 (호스트, Linux x86_64 — Colab/WSL2)

`../tools/s26_npu_aot_compile.py` 산출물을 그대로 쓴다.

```
compiled_e9965/mobilenet_v1_1.0_224_Samsung_E9965.tflite         ← FP32 입력 → NPU(fp16 추정)
compiled_e9965/mobilenet_v1_1.0_224_quant_Samsung_E9965.tflite   ← INT8 (컴파일 성공 시)
compiled_e9965/aot_manifest.json                                  ← 버전·SHA·파티션 통계
```

모델 레지스트리에 **입력 SHA 가 아니라 산출물 SHA** 를 넣는다. `aot_manifest.json` 의 `outputs[].sha256`.

### 1.2 `libLiteRtDispatch_Samsung.so` (arm64-v8a)

1순위 — 릴리스 zip 확인: github.com/google-ai-edge/LiteRT/releases 최신의 `litert_npu_runtime_libraries*.zip` 에 `samsung_runtime/` 이 있으면 그 안의 .so 를 쓴다 (2.2.0 에는 **없음**, 확인 2026-09-16).

2순위 — 소스 빌드 (WSL2 Ubuntu 24.04 또는 Colab, Bazelisk + Android NDK):

```bash
git clone --depth 1 --branch v2.2.0 https://github.com/google-ai-edge/LiteRT.git && cd LiteRT
export ANDROID_HOME=$HOME/android-sdk ANDROID_NDK_HOME=$HOME/android-sdk/ndk/<버전>   # NDK 27+ (제3자 사례: NDK 29, Bazel 7.7)
bazel build -c opt --config=android_arm64 \
  //litert/vendors/samsung/dispatch:dispatch_api_so \
  //litert/vendors/samsung/compiler:compiler_plugin_so        # ← JIT(A′) 에만 필요, AOT 만이면 첫 타깃만
# 산출: bazel-bin/litert/vendors/samsung/dispatch/libLiteRtDispatch_Samsung.so
#       bazel-bin/litert/vendors/samsung/compiler/libLiteRtCompilerPlugin_Samsung.so
python3 ../tools/s26_npu_symbols.py bazel-bin/litert/vendors/samsung/dispatch/libLiteRtDispatch_Samsung.so   # Enn* 는 0개가 정상(UNDEF) — 파일이 ELF64 arm64 인지, 크기(≈470 KB)만 확인
```

- v2.2.0 태그에서 `litert/vendors/samsung` 이 빌드되지 않으면 `main` 으로 (그 경우 런타임 AAR 2.2.0 과 dispatch ABI 가 어긋날 수 있음 — G3 에서 "model/dispatch version" 류 오류가 나면 이 원인부터 의심).
- **2026-09-24 G4 실측**: `main`@9380426b dispatch + AAR 2.2.0 조합은 **동작한다**. 버전 거부 시 런타임은
  `Found Dispatch API with an unsupported version` 을 찍는데 한 번도 나오지 않았다. 대신 앱 매니페스트에
  `<uses-native-library android:name="libenn_public_api_cpp.so" android:required="false"/>` 가 **필수**다
  (targetSdk 31+ 앱은 선언하지 않은 벤더 공개 라이브러리를 못 연다). `results/G4_VERDICT_0924.md`
- Samsung compiler plugin 은 `@exynos_ai_litecore` (LiteCore v1.2.0 tarball, 공개 URL) 를 Bazel 이 자동으로 받는다. 프록시 환경이면 `EXYNOS_AI_LITECORE_ROOT` 로 수동 지정.
- 산출물은 `../artifacts/` 에 **SHA-256 + 빌드 커밋 + NDK/Bazel 버전**을 적은 README 와 함께 보관. GitHub 에는 .so 를 올리지 말고(용량·라이선스) SHA 만.

### 1.3 JIT(A′) 를 할 경우 추가

LiteCore tarball 의 `lib/arm64-v8a/*.so` (`libgraph_wrapper.so`, `libgraphgen_api.so` 등) 를 `jniLibs/arm64-v8a/` 에 같이 넣고, 모델은 **컴파일 안 한 원본** `.tflite` 를 쓴다. `Environment.Option.CompilerPluginLibraryDir` 가 같은 디렉터리를 가리키면 LiteRT 가 첫 실행에 컴파일하고 캐시한다(`enableCompilerCache=true`). 첫 실행 컴파일 시간을 `npu_jit_compile_ms` 로 남긴다.

---

## 2. 모듈 구조

```
D1Check/
  app/                 (텔레메트리, 무변경)
  benchmark-runner/    (LiteRT 1.4.2, 무변경)
  telemetry-contract/  (무변경 — NPU 필드는 optional 로 추가만)
  npu-runner/          ← 신규
    build.gradle.kts
    src/main/AndroidManifest.xml
    src/main/jniLibs/arm64-v8a/libLiteRtDispatch_Samsung.so      (+ JIT 시 compiler plugin, litecore libs)
    src/main/assets/models/mobilenet_v1_1.0_224_Samsung_E9965.tflite (+ quant)
    src/main/kotlin/.../npurunner/
      NpuRunnerActivity.kt        benchmark-runner 의 Activity/intent 프로토콜 복제 (START/STOP, run_id, config extras)
      NpuBenchmarkEngine.kt       §3
      NpuEvidenceCollector.kt     §4 (logcat 수집은 orchestrator 가 이미 하므로 앱 쪽은 예외·버전·파티션만)
      NpuRunConfig.kt             resource=NPU 고정, precision ∈ {FP32→fp16, INT8}, duty, duration, count
```

### 2.1 `build.gradle.kts` 핵심

```kotlin
android {
    defaultConfig {
        applicationId = "com.example.d1check.npurunner"   // benchmark-runner 와 다른 패키지, 같은 debug 서명
        minSdk = 31
        ndk { abiFilters += "arm64-v8a" }
    }
    packaging { jniLibs { useLegacyPackaging = false } }     // nativeLibraryDir 에서 dlopen 가능해야 함
}
dependencies {
    implementation("com.google.ai.edge.litert:litert:2.2.0")   // CompiledModel + Environment + Accelerator.NPU
    implementation(project(":telemetry-contract"))
}
```

`AndroidManifest.xml` 에 `<uses-feature android:name="android.hardware.npu" android:required="false"/>` (Android 17 대비, Android 16 에선 무해).
`jniLibs` 에 dispatch 라이브러리는 **Samsung 것 하나만** (여러 벤더 dispatch 공존 시 선택 불안정).

---

## 3. `NpuBenchmarkEngine.kt` — 스케치 (빌드 전, API 명은 2.2.0 javadoc 으로 재확인)

```kotlin
package com.example.d1check.npurunner

import android.content.Context
import android.os.SystemClock
import com.google.ai.edge.litert.Accelerator
import com.google.ai.edge.litert.CompiledModel
import com.google.ai.edge.litert.Environment
import com.google.ai.edge.litert.TensorBuffer

class NpuBenchmarkEngine(private val context: Context, private val modelAssetPath: String) {
    data class InitSpans(val envInitNs: Long, val modelInitNs: Long, val bufferInitNs: Long)
    data class RunSpans(val totalNs: Long, val runOnlyNs: Long)

    private lateinit var env: Environment
    private lateinit var model: CompiledModel
    private lateinit var inputs: List<TensorBuffer>
    private lateinit var outputs: List<TensorBuffer>

    /** 준비 비용 = idle->NPU 전환비용. 예외는 그대로 던진다 (silent fallback 금지). */
    fun init(): InitSpans {
        val libDir = context.applicationInfo.nativeLibraryDir
        val t0 = SystemClock.elapsedRealtimeNanos()
        env = Environment.create(
            context,
            mapOf(
                Environment.Option.DispatchLibraryDir to libDir,
                Environment.Option.CompilerPluginLibraryDir to libDir,   // AOT 만이면 없어도 되지만 무해
            ),
        )
        val t1 = SystemClock.elapsedRealtimeNanos()
        // NPU 하나만 지정: 다른 가속기로의 자동 폴백을 막아 실패가 예외로 드러나게 한다.
        model = CompiledModel.create(context.assets, modelAssetPath, CompiledModel.Options(Accelerator.NPU), env)
        val t2 = SystemClock.elapsedRealtimeNanos()
        inputs = model.createInputBuffers()
        outputs = model.createOutputBuffers()
        val t3 = SystemClock.elapsedRealtimeNanos()
        return InitSpans(t1 - t0, t2 - t1, t3 - t2)
    }

    /** 추론 1회. latency_ms 경계 = write + run + read (CPU/GPU 의 Interpreter.run 과 같은 사용자 체감 범위). */
    fun runOnce(input: FloatArray, out: FloatArray): RunSpans {
        val t0 = SystemClock.elapsedRealtimeNanos()
        inputs[0].writeFloat(input)
        val r0 = SystemClock.elapsedRealtimeNanos()
        model.run(inputs, outputs)
        val r1 = SystemClock.elapsedRealtimeNanos()
        val result = outputs[0].readFloat()
        System.arraycopy(result, 0, out, 0, out.size)
        val t1 = SystemClock.elapsedRealtimeNanos()
        return RunSpans(totalNs = t1 - t0, runOnlyNs = r1 - r0)
    }

    fun close() {
        inputs.forEach { it.close() }; outputs.forEach { it.close() }
        model.close(); env.close()
    }
}
```

주의
- 입력은 benchmark-runner 와 **같은 LCG seed(0x12345678) 합성 텐서** 를 같은 코드로 생성한다 (텐서 생성 함수는 복사해 오되 seed·순서 동일 확인).
- INT8 산출물의 입력형이 uint8 이면 `writeInt8`/바이트 경로로 분기 — `.d1tset` FLOAT32 페이로드를 scale/zero_point 로 양자화(NEXT_3WEEKS §3.4 3번 항목과 동일 로직).
- duty 제어(sleep) 는 benchmark-runner 의 것을 그대로 옮긴다. 타이밍 클럭도 동일(`elapsedRealtimeNanos`).
- `close()` 순서: 버퍼 → 모델 → 환경.

---

## 4. 기록 필드 (JSONL / summary.json 에 추가, 전부 optional)

| 필드 | 값 | 출처 |
|---|---|---|
| `resource` | `"NPU"` | config |
| `engine` | `"litert-compiled-model"` (CPU/GPU 는 `"litert-interpreter"` 로 소급 기록 가능) | 상수 |
| `litert_runtime_version` | `"2.2.0"` | BuildConfig |
| `npu_dispatch_lib_sha256`, `npu_dispatch_lib_source` | 파일 SHA / `"litert@<commit>, bazel <v>, ndk <v>"` | artifacts README |
| `npu_model_partition` | `{dispatch_ops, non_dispatch_ops}` | `aot_manifest.json` 값을 assets 에 복사해 읽음 |
| `npu_compile_mode` | `"aot"` / `"jit"` | config |
| `npu_jit_compile_ms` | JIT 첫 실행 컴파일 시간, AOT 면 null | init span |
| `npu_env_init_ms`, `npu_model_init_ms`, `npu_buffer_init_ms` | §3 InitSpans | init |
| `npu_run_only_ms` (per inference) | `run()` 만 | RunSpans |
| `npu_precision` | `"fp16(compiler-default)"` / `"int8"` | 컴파일 로그·모델 |
| `npu_evidence` | `{dispatch_log_lines[], enn_log_lines[], fallback_evidence[], exception: null|str, bit_identical_to_cpu: bool, argmax_agreement: "32/32", cosine_min: float}` | orchestrator 의 logcat(태그 `LiteRt`, `LiteRtDispatch`, `ENN`, `enn`) + accuracy preflight |

**latency_ms 는 `RunSpans.totalNs`** 로 기록해 CPU/GPU 열과 같은 의미를 유지한다.

---

## 5. Orchestrator / logger 변경 (`tools/`)

- `d1_experiment_orchestrator.py`: `--resources` 에 `NPU` 허용. `resource == "NPU"` 이면 대상 패키지/Activity 를 `npu-runner` 것으로 치환. 나머지(안전 게이트·thermal conditioning·cooling·checkpoint·resume) **동일**. logcat 필터에 위 태그 4개 추가.
- accuracy preflight: NPU 는 **CPU(Interpreter, benchmark-runner) 출력을 기준**으로 비교. 게이트 = argmax 32/32 AND cosine ≥ 0.99 (pilot 후 고정). GPU strict 의 atol/rtol 을 적용하지 않는다. **비트동일이면 실패**(NPU 가 아니라 CPU 로 돈 것).
- `d1_logger_v4.py`: `formal_npu_valid` 신설 (GPU 의 9조건에 대응):
  1. `mode == formal`
  2. `device_model` prefix ∈ `FORMAL_NPU_VALIDATED_DEVICE_PREFIXES = ("SM-S942",)`
  3. `npu_model_partition.dispatch_ops ≥ 1`
  4. `npu_evidence.exception is None` and `fallback_evidence == []`
  5. `bit_identical_to_cpu == False`
  6. `argmax_agreement == "32/32"` and `cosine_min ≥ 0.99`
  7. `npu_dispatch_lib_sha256` 가 artifacts README 의 값과 일치
  8. 모델 SHA 가 `aot_manifest.json` 의 출력 SHA 와 일치
  9. 기존 공통 조건(런 완료, 표본 수, 텔레메트리 정합) 그대로
  + 공시 필드 `npu_partial_delegation = non_dispatch_ops > 0`
- exports-v2: `resource` 열에 `NPU` 가 들어가고 `threads` 는 빈 값. 스키마 v2 열 수(74/61/30)는 유지하고 NPU 전용 필드는 JSONL 에만.

---

## 6. 검증 순서 (G3 → G4)

1. **스모크 1회** (USB 가능, 안전 게이트 안 탐): `npu-runner` 를 손으로 실행 → 로그에 init span 3개 + 1회 추론 + 출력 상위 5 클래스. 예외면 메시지 전문을 `../results/G3_log.md` 에.
2. **CPU 대조**: 같은 입력을 benchmark-runner CPU 로 → argmax·cosine·비트동일 여부.
3. **엔진 대조 3런**: `npu-runner` 에서 `Accelerator.CPU` 로 duty100 60 s × 3 → Interpreter CPU4 4.37 ms 와 비교 (계획서 §5.6).
4. **pilot**: `--resources NPU --mode pilot` 60 s × duty 4.
5. **formal 20런**: `--resources NPU --mode formal --repeat 5`, cooling `stable`. 무선 adb.
6. `s26_verify_exports.py` 류로 exports-v2 교차검증 후 `../results/NPU_FORMAL_RESULTS.md`.

---

## 7. 하지 말 것

- `Accelerator.NPU, Accelerator.GPU` 처럼 폴백을 나열하지 않는다 (조용히 GPU 로 떨어진 것을 NPU 로 기록하게 됨).
- benchmark-runner 의 LiteRT 를 2.2.0 으로 올리지 않는다 (A24·S26 80런이 무효가 됨).
- `jniLibs` 에 Qualcomm/MediaTek dispatch 를 같이 넣지 않는다.
- `adb shell dumpsys battery unplug` 로 게이트를 속이지 않는다 (기존 규칙).
- 컴파일 산출물 .tflite 를 CPU Interpreter 로 열어 "동작 확인" 하지 않는다 — `DISPATCH_OP` 는 Interpreter 가 모르는 커스텀 op 라 실패하는 게 정상.
