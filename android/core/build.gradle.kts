plugins {
    id("textwire.jvm-library")
}

textwire {
    coverageFloor(line = 1.0, branch = 1.0)
}

dependencies {
    api(project(":protocol"))
    testImplementation(libs.zstd.jni)
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.junit)
}
