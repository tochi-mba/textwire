package com.rextechnologies.textwire.protocol

import java.util.Base64
import java.util.Properties

/** The committed golden vectors, translated to TSV by the build (every field base64). */
object Vectors {
    fun rows(name: String): List<List<String>> {
        val text = Vectors::class.java.getResource("/$name.tsv")!!.readText()
        return text.lines().filter { it.isNotEmpty() }.map { row ->
            row.split('\t').map { String(Base64.getDecoder().decode(it), Charsets.UTF_8) }
        }
    }

    fun ids(): Properties = Properties().apply {
        Vectors::class.java.getResourceAsStream("/ids.properties")!!.use { load(it) }
    }

    fun hex(text: String): ByteArray = text.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
}
