plugins {
    alias(libs.plugins.android.application)
}

// request-runner — S26 혼합 요청 (분류 긴급 + 탐지 일반 · CPU 직렬 / 병행 / NPU 병행) 실행기.
// A24 `SUSTAINED-CPU-PAR-CONFIRM-01` (benchmark-runner modelProbe ArrivalEnergyActivity, LiteRT 1.4.2 Interpreter)
// 를 S26 스택 (LiteRT CompiledModel 2.2.0) 으로 옮긴 별도 앱이다. 측정 앱 npu-runner (설치본 5ac485e3…) 는 바꾸지 않는다.
// 빌드 함정은 npu-runner/build.gradle.kts 와 같다 (useLegacyPackaging · noCompress tflite · uniquePackageNames=false ·
// uses-native-library). 근거: d1sim/docs/혼합요청_사전등록_v1.md §3 · s26/npu/results/G4_APP_RUNNER_0924.md §2
android {
    namespace = "com.example.d1check.requestrunner"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.d1check.requestrunner"
        minSdk = 31
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        ndk {
            // dispatch .so 가 arm64 전용 (npu-runner 와 같음)
            abiFilters += "arm64-v8a"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    androidResources {
        // 모델은 APK 에 넣지 않는다 (/data/local/tmp/mixreq 에서 연다). 관례상 유지.
        noCompress += "tflite"
    }

    packaging {
        jniLibs {
            // ★ npu-runner 와 같은 이유: dispatch 로더가 nativeLibraryDir 를 스캔한다 (G4_APP_RUNNER_0924.md §2.3)
            useLegacyPackaging = true
            keepDebugSymbols += "**/libLiteRtDispatch_Samsung.so"
        }
    }

    testOptions {
        unitTests {
            // Robolectric 세션 왕복 시험 (SessionRoundTripTest) 용. APK 에는 영향 없다.
            isIncludeAndroidResources = true
        }
    }
}

dependencies {
    // npu-runner 와 같은 좌표 · 버전 (litert 2.2.0 — CompiledModel · Accelerator.NPU · CpuOptions · GpuOptions)
    implementation(libs.ai.edge.litert.next)

    testImplementation(libs.junit)
    // npu-runner 와 같은 Robolectric · ASM 조합 (JDK 25 class file 69)
    testImplementation("org.robolectric:robolectric:4.14.1")
    listOf("asm", "asm-analysis", "asm-commons", "asm-tree", "asm-util").forEach {
        testImplementation("org.ow2.asm:$it:9.10.1")
    }
}
