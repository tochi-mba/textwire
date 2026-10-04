package com.rextechnologies.textwire

import com.rextechnologies.textwire.data.LogEntry
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.data.StoredPage
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
    private val notifier = FakeNotifier()

    private fun controller() = Controller(storage, settings, gateway, scheduler, dictionary, notifier) { clock.now }

    private val day = Controller.DAY_MILLIS

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
        assertEquals(listOf(SERVER to "00 s12 weather london"), gateway.sent)
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
        assertEquals("04 g12 https://example.com/long", gateway.texts().last())
        assertNull(storage.request(0))
    }

    @Test
    fun `links and pages are followed by the reply's tag`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Page\n\nSee the council[3].", pages = 2)) c.onSms(SERVER, frame)
        c.followLink(3)
        assertEquals("01 l12 00 3", gateway.texts().last())
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
    fun `the page size always travels with the request, so the app's setting holds`() {
        val c = controller()
        c.get("example.com")
        assertEquals("00 g12 example.com", gateway.texts().last())
        c.updateSettings { it.copy(pageFrames = 4) }
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
        assertEquals("1 text · ~0.10 GBP", c.state.value.meter.describe())
        clock.advance(2 * day)
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

    @Test
    fun `part of a reply nobody asked for is waited for and asked for again`() {
        val c = controller()
        val frames = reply(500, "# Unasked\n\n" + "word ".repeat(100))
        c.onSms(SERVER, frames[0])
        val pending = c.state.value.pending.single()
        assertEquals(Controller.UNASKED, pending.request)
        assertEquals(1, pending.received)
        assertEquals(frames.size, pending.total)
        clock.advance(SettingsSnapshot().nakAfterMillis)
        c.tick()
        // Tag 500 is "dw"; there is no request of ours to count the resend against.
        assertTrue(gateway.texts().single().startsWith("00 r dw 1"))
        assertEquals(1, c.state.value.pending.single().resends)
        assertTrue(storage.requests.isEmpty())
    }

    @Test
    fun `a tick before the quiet time has passed asks for nothing`() {
        val c = controller()
        c.get("https://example.com")
        clock.advance(SettingsSnapshot().nakAfterMillis - 1)
        c.tick()
        assertEquals(listOf("00 g12 https://example.com"), gateway.texts())
        val pending = c.state.value.pending.single()
        assertEquals(0, pending.resends)
        assertEquals(0, pending.received)
        assertNull(pending.total)
    }

    @Test
    fun `retry asks again in the same words whatever the request was`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Page\n\ntext", pages = 3)) c.onSms(SERVER, frame)
        c.turnPage(1)
        assertEquals("01 p 00 2", gateway.texts().last())
        c.retry(1)
        assertEquals("02 p 00 2", gateway.texts().last())
        assertNull(storage.request(1))
        assertEquals(listOf(2), c.state.value.pending.map { it.tag })
        c.search("tea")
        c.retry(3)
        assertEquals("04 s12 tea", gateway.texts().last())
        val sent = gateway.sent.size
        c.retry(999)
        assertEquals(sent, gateway.sent.size)
    }

    // Settings ---------------------------------------------------------------------------------

    @Test
    fun `the quiet time and the number of rounds come from the settings`() {
        settings.snapshot = settings.snapshot.copy(nakAfterMillis = 30_000, resendRounds = 1)
        val c = controller()
        c.get("https://example.com")
        assertEquals(clock.now + 30_000, scheduler.wakeAt)
        clock.advance(30_000)
        c.tick()
        assertEquals("01 r 00 0", gateway.texts().last())
        clock.advance(30_000)
        c.tick()
        assertTrue(c.state.value.pending.single().gaveUp)
        assertEquals(2, gateway.sent.size)
    }

    @Test
    fun `with no rounds a quiet reply stops without asking again`() {
        settings.snapshot = settings.snapshot.copy(resendRounds = 0)
        val c = controller()
        c.get("https://example.com")
        clock.advance(SettingsSnapshot().nakAfterMillis)
        c.tick()
        assertTrue(c.state.value.pending.single().gaveUp)
        assertEquals(1, gateway.sent.size)
    }

    @Test
    fun `a daily limit refuses new requests once reached, and lifts the next day`() {
        settings.snapshot = settings.snapshot.copy(dailyLimit = 2)
        val c = controller()
        c.search("a")
        c.search("b")
        for (frame in reply(0, "# A", Kind.SEARCH) + reply(1, "# B", Kind.SEARCH)) c.onSms(SERVER, frame)
        assertEquals(2, c.state.value.meter.segments)
        c.search("c")
        assertEquals(2, gateway.sent.size)
        assertEquals("Today's limit of 2 texts is reached. Change it in Settings.", c.state.value.notice?.text)
        clock.advance(day)
        c.search("c")
        assertEquals(3, gateway.sent.size)
    }

    @Test
    fun `today's count starts again at midnight, before any text arrives`() {
        val c = controller()
        c.search("a")
        for (frame in reply(0, "# A", Kind.SEARCH)) c.onSms(SERVER, frame)
        assertEquals(1, c.state.value.meter.segments)
        clock.advance(day)
        c.tick()
        assertEquals(0, c.state.value.meter.segments)
    }

    @Test
    fun `saving settings keeps the day's count even from an older snapshot`() {
        val c = controller()
        val before = settings.snapshot
        c.search("a")
        for (frame in reply(0, "# A", Kind.SEARCH)) c.onSms(SERVER, frame)
        c.saveSettings(before.copy(currency = "EUR"))
        assertEquals(1, settings.snapshot.segmentsToday)
        assertEquals(1, settings.snapshot.nextTag)
        assertEquals("EUR", settings.snapshot.currency)
    }

    @Test
    fun `with open on arrival off, a page waits behind a notice that opens it`() {
        settings.snapshot = settings.snapshot.copy(openOnArrival = false)
        val c = controller()
        c.setVisible(true)
        c.get("https://example.com")
        for (frame in reply(0, "# Weather\n\nsun")) c.onSms(SERVER, frame)
        assertEquals(Screen.HOME, c.state.value.screen)
        assertEquals(Notice("\u201cWeather\u201d arrived.", NoticeAction.Read(0)), c.state.value.notice)
        assertEquals("Read", c.state.value.notice?.action?.label)
        c.act()
        assertEquals(Screen.READER, c.state.value.screen)
        assertEquals("Weather", c.state.value.reading?.title)
        assertNull(c.state.value.notice)
    }

    @Test
    fun `a page that arrives while the app is away is notified, unless that is off`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Away\n\nx")) c.onSms(SERVER, frame)
        assertEquals(listOf("Away"), notifier.pages.map { it.title })
        // Opened anyway, so it is on screen when the app comes back.
        assertEquals(Screen.READER, c.state.value.screen)
        c.setVisible(true)
        c.get("https://example.com/2")
        for (frame in reply(1, "# Here\n\nx")) c.onSms(SERVER, frame)
        assertEquals(1, notifier.pages.size)
        c.setVisible(false)
        c.updateSettings { it.copy(notifyOnArrival = false, openOnArrival = false) }
        c.get("https://example.com/3")
        for (frame in reply(2, "# Quiet\n\nx")) c.onSms(SERVER, frame)
        assertEquals(1, notifier.pages.size)
        assertNull(c.state.value.notice)
    }

    @Test
    fun `a deleted page can be put back`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Gone\n\nx")) c.onSms(SERVER, frame)
        val page = c.state.value.reading!!
        c.deletePage(0)
        assertNull(c.state.value.reading)
        assertEquals(Screen.HOME, c.state.value.screen)
        assertTrue(c.state.value.pages.isEmpty())
        assertEquals(Notice("Page deleted.", NoticeAction.Restore(page)), c.state.value.notice)
        assertEquals("Undo", c.state.value.notice?.action?.label)
        c.act()
        assertEquals(listOf(page), c.state.value.pages)
        assertNull(c.state.value.notice)
        c.deletePage(99)
        assertEquals(1, c.state.value.pages.size)
    }

    @Test
    fun `deleting a page that is not open leaves the reader and the screen alone`() {
        val c = controller()
        c.search("a")
        c.search("b")
        for (frame in reply(0, "# A", Kind.SEARCH) + reply(1, "# B", Kind.SEARCH)) c.onSms(SERVER, frame)
        c.show(Screen.DIAGNOSTICS)
        c.deletePage(1)
        assertEquals(Screen.DIAGNOSTICS, c.state.value.screen)
        c.open(0)
        storage.savePage(StoredPage(2, Kind.PAGE, 1, 1, "# C", 1, clock.now))
        c.deletePage(2)
        assertEquals("A", c.state.value.reading?.title)
        assertEquals(Screen.READER, c.state.value.screen)
        c.show(Screen.HOME)
        c.deletePage(0)
        assertEquals(Screen.HOME, c.state.value.screen)
    }

    @Test
    fun `clearing history keeps replies on their way and clearing the log empties it`() {
        val c = controller()
        c.search("a")
        for (frame in reply(0, "# A", Kind.SEARCH)) c.onSms(SERVER, frame)
        c.get("https://example.com")
        c.clearHistory()
        assertTrue(c.state.value.pages.isEmpty())
        assertNull(c.state.value.reading)
        assertEquals(listOf(1), c.state.value.pending.map { it.tag })
        assertEquals("History cleared.", c.state.value.notice?.text)
        c.act()
        assertNull(c.state.value.notice)
        c.clearLog()
        assertTrue(c.state.value.log.isEmpty())
    }

    @Test
    fun `pages older than the history setting go at start and when a page arrives`() {
        storage.savePage(StoredPage(5, Kind.PAGE, 1, 1, "# Old", 3, clock.now - 2 * day))
        storage.savePage(StoredPage(6, Kind.PAGE, 1, 1, "# Recent", 3, clock.now - day / 2))
        settings.snapshot = settings.snapshot.copy(historyDays = 1)
        val c = controller()
        assertEquals(listOf("Recent"), c.state.value.pages.map { it.title })
        c.open(6)
        clock.advance(day)
        c.get("https://example.com")
        for (frame in reply(0, "# New")) c.onSms(SERVER, frame)
        assertEquals(listOf("New"), c.state.value.pages.map { it.title })
    }

    @Test
    fun `shortening history lets go of the page being read, and always keeps everything`() {
        val c = controller()
        c.get("https://example.com")
        for (frame in reply(0, "# Kept")) c.onSms(SERVER, frame)
        clock.advance(40 * day)
        c.updateSettings { it.copy(historyDays = 0) }
        assertEquals("Kept", c.state.value.reading?.title)
        c.updateSettings { it.copy(historyDays = 30) }
        assertNull(c.state.value.reading)
        assertTrue(c.state.value.pages.isEmpty())
    }

    @Test
    fun `purging pages others than the one being read keeps the reader`() {
        storage.savePage(StoredPage(5, Kind.PAGE, 1, 1, "# Old", 3, clock.now - 40 * day))
        val c = controller()
        assertTrue(c.state.value.pages.isEmpty())
        c.get("https://example.com")
        for (frame in reply(0, "# Fresh")) c.onSms(SERVER, frame)
        storage.savePage(StoredPage(7, Kind.PAGE, 1, 1, "# Older", 3, clock.now - 40 * day))
        c.updateSettings { it.copy(currency = "GBP") }
        assertEquals("Fresh", c.state.value.reading?.title)
        assertEquals(listOf("Fresh"), c.state.value.pages.map { it.title })
    }

    @Test
    fun `reset puts every choice back, keeps the number and tells the screen to reload`() {
        val c = controller()
        c.updateSettings { it.copy(pageFrames = 3, dailyLimit = 50, textScale = 1.3f) }
        c.resetSettings()
        assertEquals(SettingsSnapshot(serverNumber = SERVER), settings.snapshot.copy(segmentsDay = ""))
        assertEquals(1, c.state.value.settingsGeneration)
        assertEquals("Settings are back to their defaults.", c.state.value.notice?.text)
    }

    @Test
    fun `dismissing a stopped reply forgets it`() {
        settings.snapshot = settings.snapshot.copy(resendRounds = 0)
        val c = controller()
        c.get("https://example.com")
        clock.advance(SettingsSnapshot().nakAfterMillis)
        c.tick()
        c.dismiss(0)
        assertTrue(c.state.value.pending.isEmpty())
        assertNull(storage.request(0))
        assertNull(scheduler.wakeAt)
    }

    @Test
    fun `the button on a plain notice only dismisses it`() {
        val c = controller()
        c.act()
        assertNull(c.state.value.notice)
        settings.snapshot = SettingsSnapshot()
        c.search("x")
        c.act()
        assertNull(c.state.value.notice)
        assertEquals(Screen.SETTINGS, c.state.value.screen)
    }
}
