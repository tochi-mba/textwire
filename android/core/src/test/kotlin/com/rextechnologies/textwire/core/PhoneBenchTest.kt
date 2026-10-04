package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.decodeFrame
import com.rextechnologies.textwire.protocol.joinFrames
import com.rextechnologies.textwire.protocol.unpackEnvelope
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The phone benchmark replays real pages correctly, and its arithmetic is right. */
class PhoneBenchTest {
    @Test
    fun `every page of every fixture document is replayed, in both alphabets`() {
        val pages = PhoneBench.pages()
        assertEquals(
            setOf("dunmore-gazette-example", "en-wikipedia-org", "notes-example", "search-bbc-weather-london"),
            pages.map { it.document }.toSet(),
        )
        assertEquals(setOf("b64/12", "b64/4", "z85g/12"), pages.map { it.cut }.toSet())
        val dictionary = ZstdDictionary.packaged()
        for (page in pages) {
            // What the phone would rebuild from the texts is exactly the page's text.
            val payload = joinFrames(page.frames().map(::decodeFrame))
            assertTrue(payload.contentEquals(page.payload), "${page.document} ${page.cut} ${page.number}")
            assertEquals(page.text, unpackEnvelope(payload, dictionary).text)
        }
        assertTrue(pages.any { it.frames().first().startsWith(".") })
    }

    @Test
    fun `every stage is timed`() {
        val speed = PhoneBench.measure(repeats = 1)
        assertEquals(
            listOf(
                "load_dictionary_ms",
                "decode_frames_ms",
                "decompress_pages_ms",
                "parse_pages_ms",
                "receive_every_page_ms",
            ),
            speed.keys.toList(),
        )
        assertTrue(speed.values.all { it >= 0 })
    }

    @Test
    fun `timed is the median after a warm-up`() {
        var calls = 0
        PhoneBench.timed(9) { calls++ }
        assertEquals(12, calls)
    }

    @Test
    fun `a result is written and read back, and only real moves are reported`() {
        val before = linkedMapOf("a_ms" to 10.0, "b_ms" to 2.0, "c_ms" to 1.0)
        assertEquals(before, PhoneBench.speed(PhoneBench.json(before)))
        val after = mapOf("a_ms" to 14.0, "b_ms" to 4.0, "c_ms" to 0.25, "new_ms" to 9.0)
        assertEquals(
            listOf("b_ms: 2.0 -> 4.0 (worse)", "c_ms: 1.0 -> 0.25 (better)"),
            PhoneBench.compare(before, after),
        )
    }
}
