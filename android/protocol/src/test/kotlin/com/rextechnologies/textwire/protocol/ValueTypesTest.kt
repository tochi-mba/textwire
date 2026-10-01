package com.rextechnologies.textwire.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/** Data-class members Kotlin generates are part of the surface, so they are exercised, not excluded. */
class ValueTypesTest {
    @Test
    fun `requests envelopes and frames are values`() {
        val request = Request(Verb.LINK, tag = 1, size = 2, plain = true, ref = 3, number = 4)
        assertEquals(request, request.copy())
        assertEquals(
            listOf(Verb.LINK, 1, 2, true, null, null, 3, 4, emptyList<Int>()),
            listOf(
                request.component1(), request.component2(), request.component3(), request.component4(),
                request.component5(), request.component6(), request.component7(), request.component8(),
                request.component9(),
            ),
        )
        assertTrue(request.toString().startsWith("Request("))
        assertEquals(request.hashCode(), request.copy().hashCode())
        val envelope = Envelope(Kind.PAGE, 1, 2, "t")
        assertEquals(envelope, envelope.copy())
        assertEquals(Kind.PAGE, envelope.kind)
        assertEquals("t", envelope.text)
        assertEquals(1, envelope.page)
        assertEquals(2, envelope.pages)
        assertEquals(
            listOf(Kind.PAGE, 1, 2, "t"),
            listOf(envelope.component1(), envelope.component2(), envelope.component3(), envelope.component4()),
        )
        assertTrue(envelope.toString().contains("PAGE"))
        val frame = Frame(1, 0, 1, listOf(9))
        assertEquals(frame, frame.copy())
        assertEquals(
            listOf(1, 0, 1, listOf(9.toByte())),
            listOf(frame.component1(), frame.component2(), frame.component3(), frame.component4()),
        )
        assertTrue(frame.toString().startsWith("Frame("))
        assertEquals("encoding", FrameException("encoding").fault)
        assertEquals("short", EnvelopeException("short").message)
    }

    @Test
    fun `every request rule is checked when a request is built`() {
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, tag = -1, url = "https://x") }
        Request(Verb.GET, tag = 0, url = "https://x")
        assertFailsWith<IllegalArgumentException> { Request(Verb.STATUS, size = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, size = 256, url = "https://x") }
        Request(Verb.GET, size = 255, url = "https://x")
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, url = null) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.SEARCH, words = null) }
        Request(Verb.SEARCH, words = "w", plain = true)
        assertFailsWith<IllegalArgumentException> { Request(Verb.LINK, ref = null, number = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.LINK, ref = 1296, number = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.LINK, ref = 1, number = null) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.LINK, ref = 1, number = 256) }
        Request(Verb.LINK, ref = 1295, number = 255)
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = null, seqs = listOf(1)) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1296, seqs = listOf(1)) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1, seqs = emptyList()) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1, seqs = listOf(-1)) }
        Request(Verb.RESEND, ref = 1, seqs = listOf(0, 254))
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = -1, seqs = listOf(1)) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.PAGE, ref = -1, number = 1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.PAGE, ref = 1, number = -1) }
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, size = -1, url = "https://x") }
        assertFailsWith<IllegalArgumentException> { Request(Verb.GET, url = "") }
        assertFailsWith<IllegalArgumentException> { Request(Verb.RESEND, ref = 1, seqs = listOf(0, 300)) }
        assertEquals("0,254", formatSeqs(listOf(254, 0)))
        assertEquals("1-2", formatSeqs(listOf(2, 1)))
        assertEquals("4", formatSeqs(setOf(4)))
        assertEquals("1,3-4", formatSeqs(listOf(1, 3, 4)))
        Request(Verb.GET, url = "https://x", plain = true)
        Request(Verb.RESEND, tag = 5, ref = 1, seqs = listOf(1))
        Request(Verb.HELP, tag = 5)
        Request(Verb.HELP, plain = true)
    }

    @Test
    fun `the packaged dictionary must be on the classpath`() {
        assertFailsWith<IllegalArgumentException> { ZstdDictionary.packaged("/missing.zdict") }
        assertEquals(ZstdDictionary.packaged().sha256, ZstdDictionary.packaged(DICTIONARY_RESOURCE).sha256)
    }

    @Test
    fun `identical duplicate frames join and different ones do not`() {
        val a = Frame(1, 0, 2, listOf(1))
        val b = Frame(1, 1, 2, listOf(2))
        assertEquals(listOf<Byte>(1, 2), joinFrames(listOf(a, b, a)).toList())
        assertFailsWith<IllegalArgumentException> { joinFrames(listOf(a, b, Frame(1, 0, 2, listOf(9)))) }
        assertFailsWith<IllegalArgumentException> { joinFrames(listOf(a, Frame(1, 1, 3, listOf(2)))) }
        assertFailsWith<IllegalArgumentException> { joinFrames(listOf(a, Frame(2, 1, 2, listOf(2)))) }
    }
}
