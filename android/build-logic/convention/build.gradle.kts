plugins {
    `kotlin-dsl`
}

// The gates every other module is held to are written here, so this project is held to them too.
kotlin {
    compilerOptions {
        allWarningsAsErrors.set(true)
    }
}

val ktlint: Configuration by configurations.creating

dependencies {
    // Compiled against, never bundled: the build that applies these plugins already has the Android
    // and Kotlin Gradle plugins on its classpath, at the versions the catalog pins.
    compileOnly(libs.android.gradle.plugin)
    compileOnly(libs.kotlin.gradle.plugin)

    ktlint(libs.ktlint.cli)
}

// The same check textwire.quality gives every other module, written out by hand because this
// project cannot apply a plugin it is itself compiling.
val ktlintCheck by tasks.registering(JavaExec::class) {
    group = "verification"
    description = "Checks the convention plugins' own formatting."
    classpath = ktlint
    mainClass.set("com.pinterest.ktlint.Main")
    workingDir = projectDir
    args("src/**/*.kt", "--reporter=plain", "--relative")

    inputs.files(fileTree("src") { include("**/*.kt") }).withPathSensitivity(PathSensitivity.RELATIVE)
    inputs.file(rootProject.layout.projectDirectory.file("../../.editorconfig"))
    val marker = layout.buildDirectory.file("ktlint/passed.txt")
    outputs.file(marker)
    doLast {
        marker.get().asFile.apply { parentFile.mkdirs() }.writeText("ok\n")
    }
}

tasks.named("check") {
    dependsOn(ktlintCheck)
}

gradlePlugin {
    plugins {
        register("jvmLibrary") {
            id = "textwire.jvm-library"
            implementationClass = "com.rextechnologies.textwire.buildlogic.JvmLibraryConventionPlugin"
        }
        register("androidApplication") {
            id = "textwire.android-application"
            implementationClass = "com.rextechnologies.textwire.buildlogic.AndroidApplicationConventionPlugin"
        }
        register("compose") {
            id = "textwire.compose"
            implementationClass = "com.rextechnologies.textwire.buildlogic.ComposeConventionPlugin"
        }
        register("quality") {
            id = "textwire.quality"
            implementationClass = "com.rextechnologies.textwire.buildlogic.QualityConventionPlugin"
        }
    }
}
