pluginManagement {
    // The convention plugins every module applies. An included build rather than buildSrc, which
    // Gradle puts on the classpath of every project whether it uses the plugins or not.
    includeBuild("build-logic")
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    // Provisions the JDK a toolchain asks for when this machine does not have it.
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "textwire"

include(":protocol", ":core", ":app")
