plugins { id("com.android.application") }
android {
    namespace = "com.example.d1check.currentdiagnostic"
    compileSdk { version = release(37) }
    defaultConfig {
        applicationId = "com.example.d1check.currentdiagnostic"
        minSdk = 24
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_11; targetCompatibility = JavaVersion.VERSION_11 }
}
