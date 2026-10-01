package com.rextechnologies.textwire.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextReplacement
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.FakeClock
import com.rextechnologies.textwire.FakeGateway
import com.rextechnologies.textwire.FakeScheduler
import com.rextechnologies.textwire.FakeSettings
import com.rextechnologies.textwire.FakeStorage
import com.rextechnologies.textwire.SERVER
import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.encodeFrame
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals

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

    @Test
    fun `a search typed on the home screen is sent`() {
        show()
        compose.onNodeWithTag("input").performTextInput("weather london")
        compose.onNodeWithTag("search").performClick()
        assertEquals(listOf("00 s weather london"), gateway.texts())
        compose.onNodeWithTag("pending-00").assertIsDisplayed()
    }

    @Test
    fun `a reply opens in the reader and its chip and next page can be tapped`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\nSee the council[3].\n\n- one\n- two\n\n1. first", pages = 2)
        compose.onNodeWithTag("reader").assertIsDisplayed()
        compose.onNodeWithText("Title").assertIsDisplayed()
        compose.onNodeWithTag("next").performClick()
        assertEquals("01 p 00 2", gateway.texts().last())
        compose.onNodeWithTag("nav-home").performClick()
        compose.onNodeWithTag("page-00").assertIsDisplayed()
        compose.onNodeWithTag("page-00").performClick()
        compose.onNodeWithTag("reader").assertIsDisplayed()
        compose.onNodeWithTag("previous").performClick()
        assertEquals(2, gateway.sent.size)
    }

    @Test
    fun `the reader says so when nothing is open`() {
        show()
        compose.onNodeWithTag("nav-reader").performClick()
        compose.onNodeWithText("Nothing open yet. Search or open a page from Home.").assertIsDisplayed()
    }

    @Test
    fun `diagnostics sends the probe and lists the log`() {
        show()
        compose.onNodeWithTag("nav-diagnostics").performClick()
        compose.onNodeWithTag("probe").performClick()
        assertEquals(listOf("00 ?"), gateway.texts())
        compose.onNodeWithText("Server number: $SERVER").assertIsDisplayed()
    }

    @Test
    fun `settings are saved from the form`() {
        show()
        compose.onNodeWithTag("nav-settings").performClick()
        compose.onNodeWithTag("page-frames").performTextReplacement("120")
        compose.waitForIdle()
        compose.onNodeWithTag("save").performClick()
        compose.waitForIdle()
        assertEquals(40, settings.snapshot.pageFrames)
        compose.onNodeWithTag("price").performTextReplacement("x")
        compose.waitForIdle()
        compose.onNodeWithTag("save").performClick()
        compose.waitForIdle()
        assertEquals(0.056, settings.snapshot.pricePerSegment)
    }

    @Test
    fun `without permissions the grant card shows and a notice can be dismissed`() {
        settings.snapshot = settings.snapshot.copy(serverNumber = "")
        show(granted = false)
        compose.onNodeWithTag("grant").assertIsDisplayed()
        compose.onNodeWithTag("input").performTextInput("x")
        compose.onNodeWithTag("open").performClick()
        compose.onNodeWithTag("notice").assertIsDisplayed()
        compose.onNodeWithText("OK").performClick()
        compose.onNodeWithTag("server-number").assertIsDisplayed()
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
}
