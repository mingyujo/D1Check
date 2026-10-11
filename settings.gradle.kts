pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "D1Check"
include(":app")
include(":telemetry-contract")
include(":benchmark-runner")
// S26 NPU 전용 실행기 (LiteRT Next CompiledModel). benchmark-runner 와 엔진이 달라 모듈을 분리한다.
// 근거: measure/s26/npu/runner/NPU_RUNNER_SPEC.md
include(":npu-runner")

// S26 혼합 요청 (A24 SUSTAINED-CPU-PAR-CONFIRM-01 이식) 전용 앱. npu-runner 와 별도 APK 라 측정 앱 설치본을 바꾸지 않는다.
// 근거: d1sim/docs/혼합요청_사전등록_v1.md §3-1 · §9 (request-runner = 새 모듈)
include(":request-runner")

// S26 대표 입력 20장 품질 실행기 (Q20). npu-runner · request-runner 설치본을 바꾸지 않는 별도 APK.
// 근거: d1sim/docs/품질20장_사전등록_v1.md §2 · 조민규 10/8 회신 #7 (그 APK 에 귀속)
include(":quality-runner")
