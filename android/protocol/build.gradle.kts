import com.rextechnologies.textwire.buildlogic.GoldenVectorsTask
import com.rextechnologies.textwire.buildlogic.IdsPropertiesTask

plugins {
    id("textwire.jvm-library")
}

// The committed golden vectors become test resources: one TSV per folder, every field base64,
// so the JVM tests read the same reference cases as Python without a JSON library in the app.
val vectors = rootProject.layout.projectDirectory.dir("../protocol/vectors")
val generated = layout.buildDirectory.dir("generated/vectors")

val frameVectors = tasks.register<GoldenVectorsTask>("frameVectors") {
    source.set(vectors.dir("frames"))
    columns.set(listOf("text", "fault", "alphabet", "frame.tag", "frame.seq", "frame.total", "frame.body_hex"))
    destination.set(generated.map { it.file("frames.tsv") })
}

val envelopeVectors = tasks.register<GoldenVectorsTask>("envelopeVectors") {
    source.set(vectors.dir("envelopes"))
    columns.set(listOf("payload_hex", "fault", "envelope.kind", "envelope.page", "envelope.pages", "envelope.text"))
    destination.set(generated.map { it.file("envelopes.tsv") })
}

val requestVectors = tasks.register<GoldenVectorsTask>("requestVectors") {
    source.set(vectors.dir("requests"))
    columns.set(
        listOf(
            "text", "error", "canonical", "request.verb", "request.tag", "request.size", "request.plain",
            "request.url", "request.words", "request.ref", "request.number", "request.seqs",
        ),
    )
    destination.set(generated.map { it.file("requests.tsv") })
}

val idsVector = tasks.register<IdsPropertiesTask>("idsVector") {
    source.set(vectors.file("ids.json"))
    destination.set(generated.map { it.file("ids.properties") })
}

// The shared dictionary ships inside the module, straight from protocol/dict.
sourceSets.main { resources.srcDir(rootProject.layout.projectDirectory.dir("../protocol/dict")) }
tasks.processResources { exclude("README.md", "corpus-*.txt", "cache/**") }
sourceSets.test { resources.srcDir(generated) }
tasks.processTestResources { dependsOn(frameVectors, envelopeVectors, requestVectors, idsVector) }

textwire {
    coverageFloor(line = 1.0, branch = 1.0)
}

dependencies {
    // The app supplies the Android archive of the same artifact at runtime; here the plain jar is
    // only compiled against, and the desktop natives it carries serve the tests.
    compileOnly(libs.zstd.jni)
    testImplementation(libs.zstd.jni)
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.junit)
}
