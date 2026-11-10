plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

android {
    namespace = "com.example.jannatai"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.jannatai"
        minSdk = 24
        targetSdk = 35

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        pip {
            install("flask")
        }
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.1")
}
