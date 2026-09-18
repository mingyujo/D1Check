import java.security.MessageDigest

plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.d1check.benchmarkrunner"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.d1check.benchmarkrunner"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        externalNativeBuild {
            cmake {
                cppFlags += "-std=c++17"
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }

    androidResources {
        noCompress += "tflite"
    }
}

dependencies {
    implementation(project(":telemetry-contract"))
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    implementation("androidx.exifinterface:exifinterface:1.4.2")
    implementation(libs.ai.edge.litert.runtime)
    implementation(libs.ai.edge.litert.gpu.api)
    implementation(libs.ai.edge.litert.gpu.runtime)
    debugImplementation("com.google.mediapipe:tasks-vision:1.0.0")
    testImplementation(libs.junit)
    testImplementation("org.robolectric:robolectric:4.14.1")
}

val verifyBenchmarkModel by tasks.registering {
    val model = layout.projectDirectory.file(
        "src/main/assets/models/mobilenet_v1_1.0_224.tflite"
    )
    inputs.file(model)
    doLast {
        val file = model.asFile
        check(file.length() == 16_901_128L) { "Unexpected MobileNet V1 file size" }
        val digest = MessageDigest.getInstance("SHA-256")
        val hash = file.inputStream().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
            digest.digest().joinToString("") { "%02X".format(it) }
        }
        check(hash == "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB") {
            "Unexpected MobileNet V1 SHA-256: $hash"
        }
    }
}

tasks.named("preBuild").configure {
    dependsOn(verifyBenchmarkModel)
}
