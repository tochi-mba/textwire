package com.rextechnologies.textwire

import com.rextechnologies.textwire.data.LogEntry
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.encodeFrame
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The controller over fakes, driven by a fake clock. Replies are built the way the server
 * builds them: an envelope (uncompressed, so no server code is needed) cut into frames.
 */
class ControllerTest {
    private val storage = FakeStorage()
    private val settings = FakeSettings()
    private val gateway = FakeGateway()
    private val scheduler = FakeScheduler()
    private val clock = FakeClock()
    private val dictionary = ZstdDictionary.packaged()

    private fun controller() = Controller(storage, settings, gateway, scheduler, dictionary) { clock.now }

    /** Frames of a reply: envelope kind/codec 0/page/pages then UTF-8 text, 114 bytes a frame. */
    private fun reply(tag: Int, text: String, kind: Kind = Kind.PAGE, page: Int = 1, pages: Int = 1): List<String> {
        val payload = byteArrayOf(kind.code.toByte(), 0, page.toByte(), pages.toByte()) + text.toByteArray()
        val bodies = payload.toList().chunked(114).ifEmpty { listOf(emptyList()) }
        return bodies.mapIndexed { seq, body -> encodeFrame(Frame(tag, seq, bodies.size, body), Alphabet.B64) }
    }

    @Test
    fun `a search is sent with a fresh tag and the reply opens in the reader`() {
        val c = controller()
        c.search("weather london")
        assertEquals(listOf(SERVER to "00 s weather london"), gateway.sent)
        assertEquals(1, c.state.value.pending.size)
        assertEquals(Screen.HOME, c.state.value.screen)
        for (frame in reply(0, "# Search: weather london\n\n1. BBC[1] (bbc.co.uk)", Kind.SEARCH)) c.onSms(SERVER, frame)
        val state = c.state.value
        assertEquals(Screen.READER, state.screen)
        assertEquals("# Search: weather london\n\n1. BBC[1] (bbc.co.uk)", state.reading?.text)
        assertEquals(Kind.SEARCH, state.reading?.kind)
        assertTrue(state.pending.isEmpty())
        assertEquals(1, state.meter.segments)
        assertNull(scheduler.wakeAt)
    }

    @Test
    fun `frames arrive in any order and a page is read back from storage after a restart`() {
        val c = controller()
        c.get("https://example.com/long")
        val frames = reply(0, "# Long\n\n" + "word ".repeat(100))
        assertTrue(frames.size > 1)
        c.onSms(SERVER, frames.last())
        assertEquals(1, c.state.value.pending.single().received)
        assertEquals(frames.size, c.state.value.pending.single().total)
        // The app dies here; a new controller picks the open request and its frames back up.
        val again = controller()
        assertEquals(1, again.state.value.pending.single().received)
        for (frame in frames.dropLast(1)) again.onSms(SERVER, frame)
        assertEquals(frames.size, again.state.value.reading?.smsCount)
        assertEquals(1, again.state.value.pages.size)
    }

    @Test
    fun `silence asks for the missing frames and then gives up with a retry`() {
        val c = controller()
        c.get("https://example.com/long")
        val frames = reply(0, "# Long\n\n" + "word ".repeat(100))
        c.onSms(SERVER, frames[0])
        assertEquals(clock.now + SettingsSnapshot().nakAfterMillis, scheduler.wakeAt)
        clock.advance(SettingsSnapshot().nakAfterMillis)
        c.tick()
        val missing = (1 until frames.size).joinToString(",").let {
            if (frames.size ==
                2
            ) {
                "1"
            } else {
                "1-${frames.size - 1}"
            }
        }
        assertEquals("01 r 00 $missing", gateway.texts().last())
        assertEquals(1, c.state.value.pending.single().resends)
        repeat(3) {
            clock.advance(SettingsSnapshot().nakAfterMillis)
            c.tick()
        }
        assertTrue(c.state.value.pending.single().gaveUp)
        assertEquals("gave up", storage.entries.last().note)
        c.retry(0)
        assertEquals("04 g https://example.com/long", gateway.texts().last())
        assertNull(storage.request(0))
    }

    @Test
    fun `links and pages are followed by the reply's tag`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Page\n\nSee the council[3].", pages = 2)) c.onSms(SERVER, frame)
        c.followLink(3)
        assertEquals("01 l 00 3", gateway.texts().last())
        c.turnPage(1)
        assertEquals("02 p 00 2", gateway.texts().last())
        c.turnPage(-1)
        assertEquals(3, gateway.sent.size)
        for (frame in reply(2, "# Page\n\nmore", page = 2, pages = 2)) c.onSms(SERVER, frame)
        assertEquals(2, c.state.value.reading?.page)
        c.turnPage(1)
        assertEquals(3, gateway.sent.size)
    }

    @Test
    fun `a chosen page size travels with the request`() {
        settings.snapshot = settings.snapshot.copy(pageFrames = 4)
        val c = controller()
        c.get("example.com")
        assertEquals("00 g4 example.com", gateway.texts().last())
        c.search("x")
        assertEquals("01 s4 x", gateway.texts().last())
    }

    @Test
    fun `texts from other numbers and unreadable texts are ignored or noted`() {
        val c = controller()
        c.get("https://example.com")
        c.onSms("+447700900999", reply(0, "# Page\n\nx")[0])
        assertEquals(1, c.state.value.pending.size)
        c.onSms("07700 900000", "[00 1/1] plain reply")
        assertEquals("not a frame: encoding", storage.entries.last().note)
        assertEquals(1, c.state.value.pending.size)
    }

    @Test
    fun `an unreadable reply is dropped with a note`() {
        val c = controller()
        c.get("https://example.com")
        val bad = byteArrayOf(9, 0, 1, 1, 65)
        c.onSms(SERVER, encodeFrame(Frame(0, 0, 1, bad.toList()), Alphabet.B64))
        assertEquals("reply unreadable: kind", storage.entries.last().note)
        assertTrue(c.state.value.pending.isEmpty())
        assertTrue(c.state.value.pages.isEmpty())
    }

    @Test
    fun `without a server number nothing is sent and settings open`() {
        settings.snapshot = SettingsSnapshot()
        val c = controller()
        c.search("x")
        assertTrue(gateway.sent.isEmpty())
        assertEquals(Screen.SETTINGS, c.state.value.screen)
        assertNotNull(c.state.value.notice)
        c.dismissNotice()
        assertNull(c.state.value.notice)
    }

    @Test
    fun `settings are saved with the tag counter and the day's count rolls over`() {
        val c = controller()
        c.search("a")
        c.saveSettings(settings.snapshot.copy(pricePerSegment = 0.1, currency = "GBP"))
        assertEquals(1, settings.snapshot.nextTag)
        assertEquals("GBP", c.state.value.settings.currency)
        for (frame in reply(0, "# A\n\nx", Kind.SEARCH)) c.onSms(SERVER, frame)
        assertEquals("1 SMS, ~0.10 GBP", c.state.value.meter.describe())
        clock.advance(2L * 24 * 60 * 60 * 1000)
        c.search("b")
        for (frame in reply(1, "# B\n\nx", Kind.SEARCH)) c.onSms(SERVER, frame)
        assertEquals(1, c.state.value.meter.segments)
    }

    @Test
    fun `navigation and the help and status requests`() {
        val c = controller()
        c.show(Screen.DIAGNOSTICS)
        assertEquals(Screen.DIAGNOSTICS, c.state.value.screen)
        c.status()
        c.help()
        assertEquals(listOf("00 ?", "01 h"), gateway.texts())
        c.open(99)
        assertNull(c.state.value.reading)
        c.followLink(1)
        c.turnPage(1)
        c.retry(99)
        assertEquals(2, gateway.sent.size)
        assertEquals(LogEntry.Direction.OUT, c.state.value.log.first().direction)
    }

    @Test
    fun `a reply that was never requested is still read`() {
        val c = controller()
        for (frame in reply(500, "# Unasked\n\nx")) c.onSms(SERVER, frame)
        assertEquals("# Unasked\n\nx", c.state.value.reading?.text)
    }
}
