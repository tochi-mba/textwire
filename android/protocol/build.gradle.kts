import groovy.json.JsonSlurper
import java.util.Base64

plugins {
    id("textwire.jvm-library")
}

// Translate the committed JSON vectors into a dependency-free test resource. The JVM code
// consumes the same reference cases as Python without adding a JSON library to the app.
val frameVectors = tasks.register("frameVectors") {
    val source = rootProject.file("../protocol/vectors/frames")
    val destination = layout.buildDirectory.file("generated/vectors/frames.tsv")
    inputs.dir(source)
    outputs.file(destination)
    doLast {
        val rows = source.listFiles()!!.sortedBy { it.name }.map { file ->
            val case = JsonSlurper().parse(file) as Map<*, *>
            val frame = case["frame"] as Map<*, *>?
            listOf(
                file.name,
                Base64.getEncoder().encodeToString((case["text"] as String).toByteArray(Charsets.UTF_8)),
                case["fault"] ?: "",
                case["alphabet"] ?: "",
                frame?.get("tag") ?: "",
                frame?.get("seq") ?: "",
                frame?.get("total") ?: "",
                frame?.get("body_hex") ?: "",
            ).joinToString("\t")
        }
        destination.get().asFile.apply { parentFile.mkdirs() }.writeText(rows.joinToString("\n"))
    }
}

sourceSets.test { resources.srcDir(layout.buildDirectory.dir("generated/vectors")) }
tasks.processTestResources { dependsOn(frameVectors) }

textwire {
    coverageFloor(line = 1.0, branch = 1.0)
}

dependencies {
    testImplementation(kotlin("test-junit"))
    testImplementation(libs.junit)
}
