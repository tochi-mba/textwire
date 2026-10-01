package com.rextechnologies.textwire.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.click
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performImeAction
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextReplacement
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.text.TextLayoutResult
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.FakeClock
import com.rextechnologies.textwire.FakeGateway
import com.rextechnologies.textwire.FakeScheduler
import com.rextechnologies.textwire.FakeSettings
import com.rextechnologies.textwire.FakeStorage
import com.rextechnologies.textwire.Pending
import com.rextechnologies.textwire.SERVER
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.encodeFrame
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@RunWith(AndroidJUnit4::class)
class UiTest {
    @get:Rule
    val compose = createComposeRule()

    private val storage = FakeStorage()
    private val settings = FakeSettings()
    private val gateway = FakeGateway()
    private val clock = FakeClock()
    private val controller =
        Controller(storage, settings, gateway, FakeScheduler(), ZstdDictionary.packaged()) { clock.now }

    private fun deliver(tag: Int, text: String, kind: Kind = Kind.PAGE, page: Int = 1, pages: Int = 1) {
        val payload = byteArrayOf(kind.code.toByte(), 0, page.toByte(), pages.toByte()) + text.toByteArray()
        val bodies = payload.toList().chunked(114)
        bodies.forEachIndexed { seq, body ->
            controller.onSms(SERVER, encodeFrame(Frame(tag, seq, bodies.size, body), Alphabet.B64))
        }
    }

    private fun show(granted: Boolean = true) {
        compose.setContent {
            TextwireUi(controller = controller, permissionsGranted = granted, requestPermissions = {})
        }
    }

    /** Scrolls the list tagged [list] until something matching [what] is on screen, and returns it. */
    private fun reach(list: String, what: SemanticsMatcher): SemanticsNodeInteraction {
        compose.onNodeWithTag(list).performScrollToNode(what)
        return compose.onNode(what)
    }

    /** Taps the link chip [chip] inside the line of text [line], where a finger would. */
    private fun tapChip(line: String, chip: String) {
        val node = compose.onNodeWithText(line)
        val layouts = mutableListOf<TextLayoutResult>()
        node.fetchSemanticsNode().config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action?.invoke(layouts)
        val box = layouts.single().getBoundingBox(line.indexOf(chip) + 1)
        node.performTouchInput { click(box.center) }
    }

    @Test
    fun `an empty field sends nothing`() {
        show()
        compose.onNodeWithTag("search").performClick()
        compose.onNodeWithTag("open").performClick()
        compose.onNodeWithTag("input").performImeAction()
        compose.onNodeWithTag("input").performTextInput("   ")
        compose.onNodeWithTag("search").performClick()
        assertEquals(emptyList(), gateway.texts())
        compose.onNodeWithText("Help").performClick()
        assertEquals(listOf("00 h"), gateway.texts())
    }

    @Test
    fun `every kind of block is drawn and a chip in the text follows its link`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\n## Section\n\nSee the council[3].\n\n- one\n- two\n\n1. first\n2. second")
        for (text in listOf("Title", "Section", "See the council[3].", "- one", "- two", "1. first", "2. second")) {
            reach("reader", hasText(text)).assertIsDisplayed()
        }
        tapChip("See the council[3].", "[3]")
        assertEquals("01 l 00 3", gateway.texts().last())
    }

    @Test
    fun `diagnostics lists texts in, texts out and notes, newest first`() {
        show()
        controller.get("https://example.com/long")
        val payload = byteArrayOf(1, 0, 1, 1) + "word ".repeat(100).toByteArray()
        val bodies = payload.toList().chunked(114)
        controller.onSms(SERVER, encodeFrame(Frame(0, 0, bodies.size, bodies[0]), Alphabet.B64))
        controller.onSms(SERVER, "hello from a person")
        repeat(4) {
            clock.advance(60_000)
            controller.tick()
        }
        compose.onNodeWithTag("nav-diagnostics").performClick()
        // Three resend requests went out before it gave up, so some notes appear more than once.
        for (note in listOf("gave up", "resend", "not a frame", "frame 00 1/${bodies.size}", "request")) {
            val line = hasText(note, substring = true)
            compose.onNodeWithTag("diagnostics").performScrollToNode(line)
            compose.onAllNodes(line).onFirst().assertIsDisplayed()
        }
        reach("diagnostics", hasText("hello from a person")).assertIsDisplayed()
    }

    @Test
    fun `words typed on the home screen search and an address opens`() {
        show()
        compose.onNodeWithTag("input").performTextInput("weather london")
        compose.onNodeWithTag("search").performClick()
        assertEquals(listOf("00 s weather london"), gateway.texts())
        compose.onNodeWithTag("pending-00").assertIsDisplayed()
        compose.onNodeWithTag("input").performTextInput("bbc.co.uk/news")
        compose.onNodeWithTag("input").performImeAction()
        assertEquals("01 g bbc.co.uk/news", gateway.texts().last())
        compose.onNodeWithTag("input").performTextInput("just words")
        compose.onNodeWithTag("open").performClick()
        assertEquals("02 g just words", gateway.texts().last())
    }

    @Test
    fun `a reply opens in the reader and its chip and next page can be tapped`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\nSee the council[3].\n\n- one\n- two\n\n1. first", pages = 2)
        compose.onNodeWithTag("reader").assertIsDisplayed()
        compose.onNodeWithText("Title").assertIsDisplayed()
        compose.onNodeWithTag("previous").assertIsNotEnabled()
        compose.onNodeWithContentDescription("Previous page").assertIsDisplayed()
        compose.onNodeWithContentDescription("Next page").assertIsDisplayed()
        compose.onNodeWithTag("next").performClick()
        assertEquals("01 p 00 2", gateway.texts().last())
        compose.onNodeWithText("Asking for the next page…").assertIsDisplayed()
        compose.onNodeWithTag("next").assertIsNotEnabled()
        deliver(1, "# Title\n\nmore", page = 2, pages = 2)
        compose.onNodeWithTag("next").assertIsNotEnabled()
        compose.onNodeWithTag("previous").assertIsEnabled()
        compose.onNodeWithTag("nav-home").performClick()
        compose.onNodeWithTag("page-00").assertIsDisplayed()
        compose.onNodeWithTag("page-00").performClick()
        compose.onNodeWithTag("reader").assertIsDisplayed()
    }

    @Test
    fun `the reader says so when nothing is open`() {
        show()
        compose.onNodeWithTag("nav-reader").performClick()
        compose.onNodeWithText("Nothing open yet").assertIsDisplayed()
    }

    @Test
    fun `diagnostics shows the checks sends the probe and lists the log`() {
        show()
        compose.onNodeWithTag("nav-diagnostics").performClick()
        reach("diagnostics", hasText("No texts yet.")).assertIsDisplayed()
        reach("diagnostics", hasTestTag("probe")).performClick()
        assertEquals(listOf("00 ?"), gateway.texts())
        reach("diagnostics", hasText(SERVER)).assertIsDisplayed()
        reach("diagnostics", hasText("granted")).assertIsDisplayed()
    }

    @Test
    fun `settings are validated and saved from the form`() {
        show()
        compose.onNodeWithTag("nav-settings").performClick()
        reach("settings", hasTestTag("page-frames")).performTextReplacement("120")
        reach("settings", hasTestTag("save")).assertIsNotEnabled()
        reach("settings", hasText("1 to 40")).assertIsDisplayed()
        reach("settings", hasTestTag("page-frames")).performTextReplacement("20")
        reach("settings", hasTestTag("price")).performTextReplacement("0.03")
        reach("settings", hasTestTag("save")).performClick()
        compose.waitForIdle()
        assertEquals(20, settings.snapshot.pageFrames)
        assertEquals(0.03, settings.snapshot.pricePerSegment)
        reach("settings", hasTestTag("server-number")).performTextReplacement("07700")
        reach("settings", hasText("A number like +447700900000")).assertIsDisplayed()
        reach("settings", hasTestTag("save")).assertIsNotEnabled()
    }

    @Test
    fun `without permissions the grant card shows and a notice can be dismissed`() {
        controller.saveSettings(settings.snapshot.copy(serverNumber = ""))
        show(granted = false)
        compose.onNodeWithTag("grant").assertIsDisplayed()
        compose.onNodeWithTag("input").performTextInput("x")
        compose.onNodeWithTag("open").performClick()
        compose.onNodeWithTag("notice").assertIsDisplayed()
        compose.onNodeWithText("OK").performClick()
        reach("settings", hasTestTag("server-number")).assertIsDisplayed()
        reach("settings", hasText("Welcome to textwire")).assertIsDisplayed()
    }

    @Test
    @Config(qualifiers = "w320dp-h480dp")
    fun `on a small phone every control is still reachable`() {
        controller.saveSettings(settings.snapshot.copy(serverNumber = ""))
        show(granted = false)
        compose.onNodeWithTag("grant").assertIsDisplayed()
        for (tag in listOf("input", "search", "open")) reach("home", hasTestTag(tag)).assertIsDisplayed()
        compose.onNodeWithTag("nav-settings").performClick()
        for (tag in listOf("server-number", "page-frames", "price", "save")) {
            reach("settings", hasTestTag(tag)).assertIsDisplayed()
        }
        reach("settings", hasText("About")).assertIsDisplayed()
        compose.onNodeWithTag("nav-diagnostics").performClick()
        reach("diagnostics", hasTestTag("probe")).assertIsDisplayed()
        for (screen in listOf("home", "reader", "diagnostics", "settings")) {
            compose.onNodeWithTag("nav-$screen").assertIsDisplayed()
        }
    }

    @Test
    fun `the theme is the REX ink and signal palette`() {
        var primary = Color.Unspecified
        var background = Color.Unspecified
        compose.setContent {
            TextwireTheme {
                primary = MaterialTheme.colorScheme.primary
                background = MaterialTheme.colorScheme.background
            }
        }
        compose.waitForIdle()
        assertEquals(Color(0xFFD7FF3F), primary)
        assertEquals(Color(0xFF080A09), background)
    }

    @Test
    fun `a stopped reply offers a retry`() {
        show()
        controller.get("https://example.com/long")
        val payload = byteArrayOf(1, 0, 1, 1) + "word ".repeat(100).toByteArray()
        val bodies = payload.toList().chunked(114)
        controller.onSms(SERVER, encodeFrame(Frame(0, 0, bodies.size, bodies[0]), Alphabet.B64))
        repeat(4) {
            clock.advance(60_000)
            controller.tick()
        }
        compose.onNodeWithTag("retry-00").performClick()
        assertEquals("04 g https://example.com/long", gateway.texts().last())
    }

    @Test
    fun `the home screen has an empty state until something arrives`() {
        show()
        compose.onNodeWithText("Nothing here yet").assertIsDisplayed()
        deliver(500, "# Unasked\n\nx")
        compose.onNodeWithTag("nav-home").performClick()
        compose.onNodeWithText("Pages").assertIsDisplayed()
    }

    @Test
    fun `the pure helpers describe things the way the screens show them`() {
        assertTrue(looksLikeUrl("bbc.co.uk/news"))
        assertTrue(looksLikeUrl(" https://x "))
        assertFalse(looksLikeUrl("weather london"))
        assertFalse(looksLikeUrl("hello"))
        assertEquals("waiting for the first text", progressLabel(Pending(1, "r", 0, null, 0, false)))
        assertEquals("3 of 12 texts, asked again 1x", progressLabel(Pending(1, "r", 3, 12, 1, false)))
        assertEquals("Stopped at 3 of 12 texts. Retry to ask again.", progressLabel(Pending(1, "r", 3, 12, 3, true)))
        val page = StoredPage(1, Kind.SEARCH, 1, 1, "# S", 4, 0)
        assertTrue(pageMeta(page).startsWith("Search results · 4 texts"))
        assertTrue(pageMeta(page.copy(kind = Kind.HELP)).startsWith("Help"))
        assertTrue(pageMeta(page.copy(kind = Kind.STATUS)).startsWith("Status"))
        assertTrue(pageMeta(page.copy(kind = Kind.PAGE, page = 2, pages = 5)).startsWith("Page 2 of 5"))
        assertEquals(emptyMap(), settingsProblems("+447700900000", "12", "0.056"))
        assertEquals(setOf("number", "frames", "price"), settingsProblems("07700", "0", "-1").keys)
        assertEquals(setOf("frames", "price"), settingsProblems("+447700900000", "x", "y").keys)
    }
}
