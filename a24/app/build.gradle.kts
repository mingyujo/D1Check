plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.d1check"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.d1check"
        minSdk = 24
        targetSdk = 37
        versionCode = 2
        versionName = "4.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
}
