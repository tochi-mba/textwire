package com.rextechnologies.textwire.protocol

import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FrameCodecTest {
    @Test
    fun `every Python frame vector agrees in both directions`() {
        val rows = Vectors.rows("frames")
        assertTrue(rows.size >= 30)
        for (fields in rows) {
            val (name, text, fault, alphabet) = fields
            if (fault.isNotEmpty()) {
                assertEquals(fault, assertFailsWith<FrameException>(name) { decodeFrame(text) }.fault)
            } else {
                val body = fields[7].chunked(2).map { it.toInt(16).toByte() }
                val frame = Frame(fields[4].toInt(), fields[5].toInt(), fields[6].toInt(), body)
                assertEquals(frame, decodeFrame(text), name)
                val chosen = if (alphabet == "b64") Alphabet.B64 else Alphabet.Z85G
                assertEquals(text.trim(), encodeFrame(frame, chosen), name)
            }
        }
    }

    @Test
    fun `all payload lengths round trip in each alphabet`() {
        val random = Random(421)
        for (alphabet in Alphabet.entries) {
            for (size in 0..alphabet.frameBytes - HEADER_BYTES) {
                val frame = Frame(367, 3, 12, random.nextBytes(size).toList())
                val text = encodeFrame(frame, alphabet)
                assertTrue(text.length <= FRAME_CHARS)
                assertEquals(frame, decodeFrame(text))
            }
        }
        assertEquals(244, crc8("123456789".toByteArray().toList()))
        val empty = Frame(0, 0, 1, emptyList())
        assertEquals(encodeFrame(empty, Alphabet.B64), encodeFrame(empty))
    }

    @Test
    fun `invalid outgoing values cannot silently truncate`() {
        for (frame in listOf(
            Frame(-1, 0, 1, emptyList()),
            Frame(1296, 0, 1, emptyList()),
            Frame(0, 0, 0, emptyList()),
            Frame(0, 0, 256, emptyList()),
            Frame(0, -1, 1, emptyList()),
            Frame(0, 1, 1, emptyList()),
            Frame(0, 0, 1, List(115) { 0.toByte() }),
        )) {
            assertFailsWith<IllegalArgumentException> { encodeFrame(frame) }
        }
    }
}
