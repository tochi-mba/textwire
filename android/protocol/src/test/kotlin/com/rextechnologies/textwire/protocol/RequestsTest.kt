package com.rextechnologies.textwire.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RequestsTest {
    @Test
    fun `every parsed Python request vector formats to its canonical text`() {
        val rows = Vectors.rows("requests")
        assertTrue(rows.size >= 30)
        var formatted = 0
        for (fields in rows) {
            val (name, _, error, canonical) = fields
            if (error.isNotEmpty()) continue
            val verb = Verb.entries.first { it.letter == fields[4] }
            val request = Request(
                verb = verb,
                tag = fields[5].toIntOrNull(),
                size = fields[6].toIntOrNull(),
                plain = fields[7] == "true",
                url = fields[8].ifEmpty { null },
                words = fields[9].ifEmpty { null },
                ref = fields[10].toIntOrNull(),
                number = fields[11].toIntOrNull(),
                seqs = fields[12].split(',').filter { it.isNotEmpty() }.map { it.toInt() },
            )
            assertEquals(canonical, formatRequest(request), name)
            formatted++
        }
        assertTrue(formatted >= 15)
    }

    @Test
    fun `frame lists use the shortest ranges`() {
        assertEquals("3", formatSeqs(listOf(3)))
        assertEquals("3,5-7", formatSeqs(listOf(7, 3, 5, 6, 5)))
        assertEquals("0-2,9,11-12", formatSeqs(listOf(0, 1, 2, 9, 11, 12)))
        assertFailsWith<IllegalArgumentException> { formatSeqs(emptyList()) }
    }

    @Test
    fun `requests the grammar forbids cannot be built`() {
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.SEARCH, words = "") }
        assertFailsWith<IllegalArgumentException> { Request(Verb.HELP, size = 3) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, size = 0, url = "https://x") }
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, tag = 1296, url = "https://x") }
        assertFailsWith<IllegalArgumentException> { Request(Verb.PAGE, number = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.PAGE, ref = 1, number = 0) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1, seqs = listOf(255)) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1, seqs = listOf(1), plain = true) }
        assertEquals("?", formatRequest(Request(Verb.STATUS)))
        assertEquals("a7 h!", formatRequest(Request(Verb.HELP, tag = 367, plain = true)))
    }

    @Test
    fun `tags round trip in either case`() {
        for (tag in 0 until TAG_COUNT) assertEquals(tag, decodeTag(encodeTag(tag)))
        assertEquals(367, decodeTag("A7"))
        assertEquals("z0", encodeTag(SERVER_TAG_FIRST))
        assertNull(decodeTag("a"))
        assertNull(decodeTag("a!"))
        assertNull(decodeTag("!a"))
        assertFailsWith<IllegalArgumentException> { encodeTag(1296) }
        assertFailsWith<IllegalArgumentException> { encodeTag(-1) }
    }
}
