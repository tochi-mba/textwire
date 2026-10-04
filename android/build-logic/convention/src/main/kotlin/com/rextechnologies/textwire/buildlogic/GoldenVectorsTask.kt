package com.rextechnologies.textwire.buildlogic

import groovy.json.JsonSlurper
import org.gradle.api.DefaultTask
import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.RegularFileProperty
import org.gradle.api.provider.ListProperty
import org.gradle.api.tasks.CacheableTask
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.InputDirectory
import org.gradle.api.tasks.OutputFile
import org.gradle.api.tasks.PathSensitive
import org.gradle.api.tasks.PathSensitivity
import org.gradle.api.tasks.TaskAction
import java.util.Base64

/**
 * Translates a folder of golden-vector JSON cases into one tab-separated test resource.
 *
 * Each row is the file name followed by the values at [columns], every field base64 so tabs,
 * newlines and any Unicode in a case survive. A column is a dotted path into the case
 * (`frame.tag`); a list value is joined with commas. The JVM tests then read the same
 * reference cases as Python without the app taking on a JSON library.
 */
@CacheableTask
abstract class GoldenVectorsTask : DefaultTask() {
    @get:InputDirectory
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val source: DirectoryProperty

    @get:Input
    abstract val columns: ListProperty<String>

    @get:OutputFile
    abstract val destination: RegularFileProperty

    @TaskAction
    fun translate() {
        val files = source.get().asFile.listFiles { file -> file.extension == "json" }!!.sortedBy { it.name }
        val rows = files.map { file ->
            val case = JsonSlurper().parse(file, "UTF-8") as Map<*, *>
            (listOf(file.name) + columns.get().map { column -> render(lookup(case, column)) }).joinToString("\t") { encode(it) }
        }
        destination.get().asFile.apply { parentFile.mkdirs() }.writeText(rows.joinToString("\n"))
    }

    private fun lookup(case: Map<*, *>, column: String): Any? =
        column.split('.').fold(case as Any?) { current, key -> (current as Map<*, *>?)?.get(key) }

    private fun render(value: Any?): String = when (value) {
        null -> ""
        is List<*> -> value.joinToString(",")
        else -> value.toString()
    }

    private fun encode(text: String): String = Base64.getEncoder().encodeToString(text.toByteArray(Charsets.UTF_8))
}

/**
 * Writes every page of every document vector as one row: the document, the cut (`b64/12`), the
 * page number, the payload the server sends and the page's text, every field base64. The
 * phone benchmark replays these the way the server would send them.
 */
@CacheableTask
abstract class PagePayloadsTask : DefaultTask() {
    @get:InputDirectory
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val source: DirectoryProperty

    @get:OutputFile
    abstract val destination: RegularFileProperty

    @TaskAction
    fun translate() {
        val encoder = Base64.getEncoder()
        val rows = mutableListOf<String>()
        val files = source.get().asFile.listFiles { file -> file.extension == "json" }!!.sortedBy { it.name }
        for (file in files) {
            val pages = (JsonSlurper().parse(file, "UTF-8") as Map<*, *>)["pages"] as Map<*, *>
            for ((cut, list) in pages.entries.sortedBy { it.key.toString() }) {
                (list as List<*>).forEachIndexed { index, page ->
                    page as Map<*, *>
                    val fields = listOf(
                        file.nameWithoutExtension,
                        cut.toString(),
                        "${index + 1}",
                        "${page["payload_hex"]}",
                        "${page["text"]}",
                    )
                    rows.add(fields.joinToString("\t") { encoder.encodeToString(it.toByteArray(Charsets.UTF_8)) })
                }
            }
        }
        destination.get().asFile.apply { parentFile.mkdirs() }.writeText(rows.joinToString("\n"))
    }
}

/** Writes the numbered constants of `protocol/vectors/ids.json` as a properties resource. */
@CacheableTask
abstract class IdsPropertiesTask : DefaultTask() {
    @get:org.gradle.api.tasks.InputFile
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val source: RegularFileProperty

    @get:OutputFile
    abstract val destination: RegularFileProperty

    @TaskAction
    fun translate() {
        val ids = JsonSlurper().parse(source.get().asFile, "UTF-8") as Map<*, *>
        val lines = mutableListOf<String>()
        fun walk(prefix: String, value: Any?) {
            when (value) {
                is Map<*, *> -> value.forEach { (key, child) -> walk(if (prefix.isEmpty()) "$key" else "$prefix.$key", child) }
                is List<*> -> lines.add("$prefix=${value.joinToString(",")}")
                else -> lines.add("$prefix=$value")
            }
        }
        walk("", ids)
        destination.get().asFile.apply { parentFile.mkdirs() }.writeText(lines.sorted().joinToString("\n"))
    }
}
