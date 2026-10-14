import java.security.MessageDigest

plugins {
    alias(libs.plugins.android.application)
}

val modelProbeEnabled = providers.gradleProperty("enableModelProbe").orNull == "true"
val a24PreparationEnabled = providers.gradleProperty("enableA24Preparation").orNull == "true"

if (a24PreparationEnabled) {
    dependencyLocking { lockAllConfigurations() }
}

android {
    namespace = "com.example.d1check.benchmarkrunner"
    if (a24PreparationEnabled) ndkVersion = "28.2.13676358"
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

    buildTypes {
        if (modelProbeEnabled) {
            create("modelProbe") {
                initWith(getByName("debug"))
                applicationIdSuffix = ".modelprobe"
                isDebuggable = true
                matchingFallbacks += listOf("debug")
            }
        }
        if (a24PreparationEnabled) {
            create("a24Preparation") {
                initWith(getByName("debug"))
                // The exact legacy ModelProbeManifest target package remains stable.
                applicationIdSuffix = ".modelprobe"
                isDebuggable = true
                matchingFallbacks += listOf("debug")
            }
        }
    }
    if (a24PreparationEnabled) {
        // This explicitly requested preparation build loads exact models from external files.
        // With the flag absent the original default asset contract is unchanged.
        sourceSets.getByName("main").assets.setSrcDirs(emptyList<String>())
        sourceSets.getByName("a24Preparation").apply {
            kotlin.srcDir("src/modelProbe/java")
            manifest.srcFile("src/modelProbe/AndroidManifest.xml")
        }
        sourceSets.getByName("testA24Preparation").kotlin.srcDir("src/testModelProbe/java")
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

androidComponents {
    beforeVariants(selector().withBuildType("modelProbe")) { variant ->
        variant.hostTests[com.android.build.api.variant.HostTestBuilder.UNIT_TEST_TYPE]?.enable = true
    }
    beforeVariants(selector().withBuildType("a24Preparation")) { variant ->
        variant.hostTests[com.android.build.api.variant.HostTestBuilder.UNIT_TEST_TYPE]?.enable = true
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
    if (modelProbeEnabled) {
        add("modelProbeImplementation", "com.google.mediapipe:tasks-vision:1.0.0")
    }
    if (a24PreparationEnabled) {
        add("a24PreparationImplementation", "com.google.mediapipe:tasks-vision:1.0.0")
    }
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
