plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "nz.studyguider"
    compileSdk = 36
    defaultConfig {
        applicationId = "nz.studyguider"; minSdk = 26; targetSdk = 36; versionCode = 111; versionName = "1.1.1"; testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("boolean", "TEST_SYSTEM", "false")
        buildConfigField("String", "TEST_SERVER", "\"\"")
        manifestPlaceholders["appLabel"] = "StudyGuider"
    }
    buildFeatures { compose = true; buildConfig = true }
    buildTypes {
        // The test system's app (docs/test-system.md): installs beside the real one, talks plain HTTP to the test server on this PC
        // (scripts/test-system.sh apk passes -PtestServer=http://<this PC>:8100) and shows Report a problem.
        create("qa") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".test"
            versionNameSuffix = "-test"
            buildConfigField("boolean", "TEST_SYSTEM", "true")
            buildConfigField("String", "TEST_SERVER", "\"" + (project.findProperty("testServer") ?: "") + "\"")
            manifestPlaceholders["appLabel"] = "StudyGuider Test"
            matchingFallbacks += "debug"
        }
        create("benchmark") {
            initWith(getByName("debug"))
            isDebuggable = false
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("debug")
            matchingFallbacks += "release"
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
        }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }

dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.05.01"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.material3:material3")
    androidTestImplementation(platform("androidx.compose:compose-bom:2025.05.01"))
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
    testImplementation("junit:junit:4.13.2")
}
