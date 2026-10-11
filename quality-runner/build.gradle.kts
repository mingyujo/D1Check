plugins {
    alias(libs.plugins.android.application)
}

// quality-runner — S26 대표 입력 20장 품질 실행기 (Q20). 조민규 CPU 참조 출력과의 일치를 backend (CPU · GPU · NPU) 마다 따로 잰다.
// request-runner/build.gradle.kts (s26-mixreq e2bedf1) 를 바탕으로 했다 — 같은 LiteRT 좌표 (litert 2.2.0) · minSdk 31 · arm64 ·
// useLegacyPackaging · noCompress tflite · uses-native-library. 측정 앱 npu-runner (설치본 5ac485e3…) · request-runner 는 바꾸지 않는다.
// 모델 · 입력 텐서는 APK 에 넣지 않고 /data/local/tmp/quality20/ 에서 연다 (등록 §1 "레포·APK 에 넣지 않는다").
// 근거: d1sim/docs/품질20장_사전등록_v1.md §1 · §2 · 조민규 10/8 회신 #7 (20장 확인은 그 APK · 모델 · 전처리 · 엔진에 귀속)
android {
    namespace = "com.example.d1check.qualityrunner"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.d1check.qualityrunner"
        minSdk = 31
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        ndk {
            // dispatch .so 가 arm64 전용 (npu-runner · request-runner 와 같음)
            abiFilters += "arm64-v8a"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    androidResources {
        // 모델은 APK 에 넣지 않는다. 관례상 유지 (request-runner 와 같음).
        noCompress += "tflite"
    }

    packaging {
        jniLibs {
            // ★ npu-runner 와 같은 이유: dispatch 로더가 nativeLibraryDir 를 스캔한다 (G4_APP_RUNNER_0924.md §2.3)
            useLegacyPackaging = true
            keepDebugSymbols += "**/libLiteRtDispatch_Samsung.so"
        }
    }
}

dependencies {
    // npu-runner · request-runner 와 같은 좌표 · 버전 (litert 2.2.0 — CompiledModel · Accelerator.NPU · CpuOptions · GpuOptions)
    implementation(libs.ai.edge.litert.next)

    // JVM 단위 시험 (Robolectric 없음 — 엔진은 Context 없이 돌도록 짰다)
    testImplementation(libs.junit)
}
