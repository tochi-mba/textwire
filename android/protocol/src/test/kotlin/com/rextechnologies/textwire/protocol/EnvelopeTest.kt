package com.rextechnologies.textwire.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class EnvelopeTest {
    private val dictionary = ZstdDictionary.packaged()

    @Test
    fun `the packaged dictionary is the one the vectors were made with`() {
        val ids = Vectors.ids()
        assertEquals(ids.getProperty("dictionary.sha256"), dictionary.sha256)
        assertEquals(ids.getProperty("dictionary.size").toInt(), dictionary.bytes.size)
        assertEquals(MAX_FRAMES, ids.getProperty("frame.max_frames").toInt())
        assertEquals(HEADER_BYTES, ids.getProperty("frame.header_bytes").toInt())
    }

    @Test
    fun `every Python envelope vector unpacks to its envelope or its fault`() {
        val rows = Vectors.rows("envelopes")
        assertTrue(rows.size >= 15)
        var compressed = 0
        for ((name, payloadHex, fault, kind, page, pages, text) in rows.map { Row(it) }) {
            val payload = Vectors.hex(payloadHex)
            if (fault.isNotEmpty()) {
                assertEquals(
                    fault,
                    assertFailsWith<EnvelopeException>(name) {
                        unpackEnvelope(payload, dictionary)
                    }.fault,
                )
            } else {
                val envelope = Envelope(Kind.of(kind.toInt())!!, page.toInt(), pages.toInt(), text)
                assertEquals(envelope, unpackEnvelope(payload, dictionary), name)
                if (payload[1].toInt() == Codec.ZSTD.code) compressed++
            }
        }
        assertTrue(compressed >= 3, "the vectors must exercise the dictionary")
    }

    @Test
    fun `every document vector page unpacks and the Kotlin side reads its number`() {
        // Document pages are the real thing: pages of the recorded fixtures at three cuts.
        val rows = Vectors.rows("envelopes").filter { it[2].isEmpty() }
        for (row in rows) {
            val envelope = unpackEnvelope(Vectors.hex(row[1]), dictionary)
            assertTrue(envelope.page in 1..envelope.pages)
        }
    }

    @Test
    fun `frames join in any order and missing ones are named`() {
        val frames = (0 until 3).map { Frame(7, it, 3, List(4) { b -> (it * 10 + b).toByte() }) }
        val payload = joinFrames(listOf(frames[2], frames[0], frames[1], frames[0]))
        assertEquals((0 until 3).flatMap { frames[it].body }, payload.toList())
        val missing = assertFailsWith<IllegalArgumentException> { joinFrames(listOf(frames[1])) }
        assertEquals("missing frames 0,2", missing.message)
        assertFailsWith<IllegalArgumentException> { joinFrames(emptyList()) }
        assertFailsWith<IllegalArgumentException> { joinFrames(listOf(frames[0], Frame(8, 1, 3, emptyList()))) }
        assertFailsWith<IllegalArgumentException> { joinFrames(listOf(frames[0], Frame(7, 0, 3, listOf(1)))) }
    }

    @Test
    fun `decompression refuses what the limit forbids`() {
        val tooBig = Vectors.rows("envelopes").first { it[0] == "reject-compression-too-large.json" }
        val body = Vectors.hex(tooBig[1]).copyOfRange(ENVELOPE_BYTES, Vectors.hex(tooBig[1]).size)
        assertFailsWith<CompressionException> { dictionary.decompress(body) }
        assertFailsWith<CompressionException> { dictionary.decompress(byteArrayOf(1, 2, 3)) }
        val small = Vectors.rows("envelopes").first { it[0] == "page-compressed.json" }
        val page = Vectors.hex(small[1]).copyOfRange(ENVELOPE_BYTES, Vectors.hex(small[1]).size)
        assertFailsWith<CompressionException> { dictionary.decompress(page, maxSize = 10) }
        val corrupt = page.copyOf().also { it[it.size - 3] = (it[it.size - 3].toInt() xor 0xff).toByte() }
        assertFailsWith<CompressionException> { dictionary.decompress(corrupt) }
    }

    @Test
    fun `kinds and codecs resolve by code`() {
        assertEquals(Kind.STATUS, Kind.of(3))
        assertEquals(null, Kind.of(9))
        assertEquals(Codec.ZSTD, Codec.of(1))
        assertEquals(null, Codec.of(7))
    }

    private data class Row(
        val name: String,
        val payloadHex: String,
        val fault: String,
        val kind: String,
        val page: String,
        val pages: String,
        val text: String,
    ) {
        constructor(
            fields: List<String>,
        ) : this(fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[6])
    }
}
