plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Nom du fichier produit : kab-board-debug.apk, et non app-debug.apk.
base { archivesName.set("kab-board") }

android {
    namespace = "taqbaylit.clavier"
    compileSdk = 35
    ndkVersion = "28.2.13676358"

    defaultConfig {
        applicationId = "taqbaylit.clavier"
        minSdk = 24
        targetSdk = 35

        // Les deux architectures des telephones reels. x86 et x86_64 ne servent qu'aux emulateurs
        // et coutaient 43 Mio d'APK, dont 30 pour le seul ONNX Runtime.
        ndk { abiFilters += listOf("arm64-v8a") }
        versionCode = 1
        versionName = "0.1"
        externalNativeBuild {
            cmake {
                // Pas de RTTI ni d'exceptions superflues : ce sont des
                // bibliothèques de requête, pas des applications.
                arguments += listOf("-DANDROID_STL=c++_shared")
            }
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    // Le moteur vit dans moteur/, partagé avec les tests de conformité
    // qui tournent sur JVM de bureau.
    sourceSets["main"].java.srcDirs("../moteur/src/main/kotlin")

    // Les ressources du correcteur ne doivent pas être compressées : elles sont lues par projection
    // mémoire.
    androidResources { noCompress += listOf("mots", "freq", "nsrc", "cat",
                                            "sdx", "sids", "ancrages", "voisins",
                                            "crfsuite", "txt",
                                            "noms", "formes", "gloses",
                                            "src", "srcnoms", "frequents",
                                            // « onnx ». Meme piege que pour le modele de langue,
                                            // corrige de la meme facon.
                                            "onnx") }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    // Les tests JVM appellent du code qui journalise via android.util.Log :
    // sans cette option, chaque appel leve « Method i not mocked ».
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    implementation("androidx.core:core-ktx:1.13.1")
    // Exigees par le panneau emoji repris de KreyolKeyb (grille virtualisee).
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.viewpager2:viewpager2:1.1.0")
    // Dispatchers.Main ne fonctionne pas sans le module Android :
    // ça compile, et ça casse au premier lancement.
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
