import com.rextechnologies.textwire.buildlogic.PagePayloadsTask

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

// Every page of every document vector, as the server sends it: what the phone benchmark replays.
val pagePayloads = tasks.register<PagePayloadsTask>("pagePayloads") {
    source.set(rootProject.layout.projectDirectory.dir("../protocol/vectors/documents"))
    destination.set(layout.buildDirectory.file("generated/vectors/pages.tsv"))
}
sourceSets.test { resources.srcDir(layout.buildDirectory.dir("generated/vectors")) }
tasks.processTestResources { dependsOn(pagePayloads) }

// `./gradlew :core:bench` compares with benchmarks/phone.json; `-Precord` replaces it.
val baseline = rootProject.layout.projectDirectory.file("../benchmarks/phone.json")
tasks.register<JavaExec>("bench") {
    group = "verification"
    description = "Times what the phone does with every fixture page, against benchmarks/phone.json."
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("com.rextechnologies.textwire.core.PhoneBenchKt")
    args(baseline.asFile.absolutePath, if (providers.gradleProperty("record").isPresent) "record" else "compare")
}
