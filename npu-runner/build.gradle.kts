plugins {
    alias(libs.plugins.android.application)
}

// npu-runner — S26(Exynos 2600) NPU 를 LiteRT Next CompiledModel 로 실행하는 별도 앱.
// benchmark-runner(LiteRT 1.4.2 Interpreter)는 한 줄도 바꾸지 않는다. 엔진이 다르므로 모듈을 분리한다.
// 근거: measure/s26/npu/runner/NPU_RUNNER_SPEC.md §2
android {
    namespace = "com.example.d1check.npurunner"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.d1check.npurunner"
        // LiteRT Next 는 API 31+ 를 요구한다. S26 은 SDK 36 이므로 문제없다.
        minSdk = 31
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        ndk {
            // dispatch .so 가 arm64 전용이고, 다른 ABI 를 넣으면 APK 만 커진다.
            abiFilters += "arm64-v8a"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    androidResources {
        // .tflite 를 압축하면 mmap 이 안 된다 (benchmark-runner 와 동일 설정)
        noCompress += "tflite"
    }

    packaging {
        jniLibs {
            // ★ true 여야 설치 시 .so 가 nativeLibraryDir(/data/app/.../lib/arm64) 에 실제 파일로 풀린다.
            // LiteRT 의 dispatch 로더는 그 "디렉터리를 스캔"해서 libLiteRtDispatch_*.so 를 찾는다
            // (litert_dispatch.cc:122). false 로 두면 .so 가 APK 안에 무압축으로 남고 그 디렉터리가
            // 생성조차 되지 않아 "No dispatch library found" -> "Failed to allocate tensors" 가 난다.
            // 2026-09-24 실측으로 확인 (results/G4_DIAG_NPU_*.txt).
            useLegacyPackaging = true
            keepDebugSymbols += "**/libLiteRtDispatch_Samsung.so"
        }
    }

    sourceSets {
        getByName("main") {
            // benchmark-runner 의 원본 MobileNet(16.9 MB)을 그대로 재사용한다.
            // 같은 파일을 두 번 커밋하지 않기 위함이며, CPU 대조 실행(SPEC §6-3)에 필요하다.
            assets.srcDirs("src/main/assets", "../benchmark-runner/src/main/assets")
        }
    }
}

dependencies {
    // ⚠ 버전 주의 (NPU_RUNNER_SPEC §1.2)
    // jniLibs 의 libLiteRtDispatch_Samsung.so 는 LiteRT main @ 9380426b (2026-09-18) 에서 빌드했다.
    // 런타임 AAR 과 dispatch ABI 가 어긋나면 CompiledModel.create(NPU) 가 실패한다.
    // 실패 시: NpuRunnerActivity 로그의 available_accelerators 를 먼저 볼 것.
    //   - NPU 가 목록에 없다 → 런타임/dispatch 짝이 안 맞음 → litertNext 버전을 올리거나 dispatch 재빌드
    //   - NPU 가 있는데 create 실패 → ENN 쪽 문제 (G0 판정 문서 참조)
    implementation(libs.ai.edge.litert.next)

    // JVM 단위 테스트 전용 (APK 에 안 들어간다). 입력 생성기·품질 게이트의 순수 로직 고정용
    testImplementation(libs.junit)
}
