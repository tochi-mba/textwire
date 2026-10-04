package com.rextechnologies.textwire.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performImeAction
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.SERVER
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Home, the reader and diagnostics: what a person sees and what each control sends. */
@RunWith(AndroidJUnit4::class)
class UiTest : ScreenHarness() {
    @Test
    fun `an empty field sends nothing`() {
        show()
        compose.onNodeWithTag("search").performClick()
        compose.onNodeWithTag("open").performClick()
        compose.onNodeWithTag("input").performImeAction()
        compose.onNodeWithTag("input").performTextInput("   ")
        compose.onNodeWithTag("search").performClick()
        assertEquals(emptyList(), gateway.texts())
        compose.onNodeWithTag("help").performClick()
        assertEquals(listOf("00 h"), gateway.texts())
    }

    @Test
    fun `words typed on the home screen search and an address opens`() {
        show()
        compose.onNodeWithTag("input").performTextInput("weather london")
        compose.onNodeWithTag("search").performClick()
        assertEquals(listOf("00 s12 weather london"), gateway.texts())
        compose.onNodeWithTag("pending-00").assertIsDisplayed()
        compose.onNodeWithText("Searching: weather london").assertIsDisplayed()
        compose.onNodeWithTag("input").performTextInput("bbc.co.uk/news")
        compose.onNodeWithTag("input").performImeAction()
        assertEquals("01 g12 bbc.co.uk/news", gateway.texts().last())
        compose.onNodeWithTag("input").performTextInput("just words")
        compose.onNodeWithTag("input").performImeAction()
        assertEquals("02 s12 just words", gateway.texts().last())
        compose.onNodeWithTag("input").performTextInput("just words")
        compose.onNodeWithTag("open").performClick()
        assertEquals("03 g12 just words", gateway.texts().last())
    }

    @Test
    fun `the home screen has an empty state until something arrives`() {
        show()
        compose.onNodeWithText("Nothing here yet").assertIsDisplayed()
        deliver(500, "# Unasked\n\nx")
        compose.onNodeWithTag("nav-home").performClick()
        compose.onNodeWithText("Pages").assertIsDisplayed()
        compose.onNodeWithTag("page-dw").assertTextContains("Unasked", substring = true)
    }

    @Test
    fun `today's line says how many texts arrived and the daily limit when there is one`() {
        show()
        compose.onNodeWithTag("today").assertTextContains("Received today: nothing yet")
        controller.updateSettings { it.copy(dailyLimit = 50) }
        compose.onNodeWithTag("today").assertTextContains("Received today: nothing yet · limit 50 a day")
        controller.get("https://example.com")
        deliver(0, "# One\n\nx")
        compose.onNodeWithTag("nav-home").performClick()
        compose.onNodeWithTag("today")
            .assertTextContains("Received today: 1 text · ~0.06 USD · limit 50 a day")
    }

    @Test
    fun `every kind of block is drawn and a chip in the text follows its link`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\n## Section\n\nSee the council[3].\n\n- one\n- two\n\n1. first\n2. second")
        for (text in listOf("Title", "Section", "See the council[3].", "- one", "- two", "1. first", "2. second")) {
            reach("reader", hasText(text)).assertIsDisplayed()
        }
        tapChip(reach("reader", hasText("See the council[3].")), "See the council[3].", "[3]")
        assertEquals("01 l12 00 3", gateway.texts().last())
    }

    @Test
    fun `a reply opens in the reader, named in the bar, and its next page can be asked for`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\nSee the council[3].\n\n- one\n- two\n\n1. first", pages = 2)
        compose.onNodeWithTag("reader").assertIsDisplayed()
        // Once in the bar and once as the page's own heading.
        compose.onAllNodesWithText("Title").assertCountEquals(2)
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
        compose.onNodeWithTag("page-00").performClick()
        compose.onNodeWithTag("reader").assertIsDisplayed()
    }

    @Test
    fun `a search for a word starting with l does not look like a page turn`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Title\n\ntext", pages = 2)
        controller.search("london")
        compose.onNodeWithTag("next").assertIsEnabled()
        compose.onNodeWithText("Page 1 of 2").assertIsDisplayed()
    }

    @Test
    fun `the reader says so when nothing is open`() {
        show()
        compose.onNodeWithTag("nav-reader").performClick()
        compose.onNodeWithText("Nothing open yet").assertIsDisplayed()
        compose.onNodeWithTag("share").assertDoesNotExist()
    }

    @Test
    fun `the open page can be shared and deleted, and the delete undone`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Keep me\n\ntext")
        compose.onNodeWithTag("share").performClick()
        assertEquals(listOf("Keep me"), shared.map { it.title })
        compose.onNodeWithTag("delete-page").performClick()
        compose.onNodeWithText("Page deleted.").assertIsDisplayed()
        compose.onNodeWithText("Nothing here yet").assertIsDisplayed()
        compose.onNodeWithTag("notice-action").assertTextContains("Undo").performClick()
        compose.onNodeWithTag("page-00").assertIsDisplayed()
    }

    @Test
    fun `a page can be deleted from its card on Home`() {
        show()
        controller.updateSettings { it.copy(openOnArrival = false) }
        controller.get("https://example.com")
        deliver(0, "# Card\n\ntext")
        compose.onNodeWithContentDescription("Delete Card").performClick()
        compose.onNodeWithTag("page-00").assertDoesNotExist()
        compose.onNodeWithTag("notice").assertIsDisplayed()
    }

    @Test
    fun `with open on arrival off, the notice opens the page`() {
        controller.setVisible(true)
        controller.updateSettings { it.copy(openOnArrival = false) }
        show()
        controller.get("https://example.com")
        deliver(0, "# Later\n\ntext")
        compose.onNodeWithText("“Later” arrived.").assertIsDisplayed()
        compose.onNodeWithTag("notice-action").assertTextContains("Read").performClick()
        compose.onNodeWithTag("reader").assertIsDisplayed()
    }

    @Test
    fun `the reader keeps the screen on only when asked, and only while it shows`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Long read\n\ntext")
        compose.waitForIdle()
        assertFalse(view.keepScreenOn)
        controller.updateSettings { it.copy(keepScreenOn = true) }
        compose.waitForIdle()
        assertTrue(view.keepScreenOn)
        compose.onNodeWithTag("nav-home").performClick()
        compose.waitForIdle()
        assertFalse(view.keepScreenOn)
    }

    @Test
    fun `the text size setting makes the page's text larger`() {
        show()
        controller.get("https://example.com")
        deliver(0, "# Heading\n\nbody")
        val height = { reach("reader", hasText("body")).fetchSemanticsNode().boundsInRoot.height }
        val normal = height()
        controller.updateSettings { it.copy(textScale = 1.3f) }
        compose.waitForIdle()
        assertTrue(height() > normal * 1.2f, "larger text: ${height()} against $normal")
    }

    @Test
    fun `a stopped reply offers a retry and can be dismissed`() {
        show()
        controller.get("https://example.com/long")
        stall(0)
        compose.onNodeWithTag("retry-00").performClick()
        assertEquals("04 g12 https://example.com/long", gateway.texts().last())
        stall(4)
        compose.onNodeWithTag("dismiss-04").performClick()
        compose.onNodeWithTag("pending-04").assertDoesNotExist()
    }

    @Test
    fun `diagnostics shows the checks, sends the probe and lists the log`() {
        show()
        compose.onNodeWithTag("nav-diagnostics").performClick()
        reach("diagnostics", hasText("No texts yet.")).assertIsDisplayed()
        compose.onNodeWithTag("clear-log").assertDoesNotExist()
        reach("diagnostics", hasTestTag("probe")).performClick()
        assertEquals(listOf("00 ?"), gateway.texts())
        reach("diagnostics", hasText(SERVER)).assertIsDisplayed()
        reach("diagnostics", hasText("granted")).assertIsDisplayed()
        reach("diagnostics", hasText("allowed")).assertIsDisplayed()
        reach("diagnostics", hasText("1 reply")).assertIsDisplayed()
        reach("diagnostics", hasTestTag("clear-log")).performClick()
        reach("diagnostics", hasText("No texts yet.")).assertIsDisplayed()
    }

    @Test
    fun `diagnostics says why notifications will not arrive`() {
        show(notifications = false)
        compose.onNodeWithTag("nav-diagnostics").performClick()
        reach("diagnostics", hasText("not allowed")).assertIsDisplayed()
        controller.updateSettings { it.copy(notifyOnArrival = false) }
        reach("diagnostics", hasText("off in Settings")).assertIsDisplayed()
    }

    @Test
    fun `diagnostics lists texts in, texts out and notes, newest first`() {
        show()
        controller.get("https://example.com/long")
        controller.onSms(SERVER, "hello from a person")
        stall(0)
        compose.onNodeWithTag("nav-diagnostics").performClick()
        // Three resend requests went out before it gave up, so some notes appear more than once.
        for (note in listOf("gave up", "resend", "not a frame", "frame 00 1/", "request")) {
            val line = hasText(note, substring = true)
            compose.onNodeWithTag("diagnostics").performScrollToNode(line)
            compose.onAllNodes(line).onFirst().assertIsDisplayed()
        }
        reach("diagnostics", hasText("hello from a person")).assertIsDisplayed()
    }

    @Test
    fun `without permissions the banner asks for them and a notice can be dismissed`() {
        controller.saveSettings(settings.snapshot.copy(serverNumber = ""))
        show(granted = false)
        compose.onNodeWithTag("grant").performClick()
        assertEquals(1, permissionRequests)
        compose.onNodeWithTag("input").performTextInput("x")
        compose.onNodeWithTag("open").performClick()
        compose.onNodeWithTag("notice").assertIsDisplayed()
        compose.onNodeWithTag("notice-action").assertTextContains("OK").performClick()
        compose.onNodeWithTag("notice").assertDoesNotExist()
        reach("settings", hasText("Welcome to textwire")).assertIsDisplayed()
    }

    @Test
    @Config(qualifiers = "w320dp-h480dp")
    fun `on a small phone every control is still reachable`() {
        controller.saveSettings(settings.snapshot.copy(serverNumber = ""))
        show(granted = false)
        compose.onNodeWithTag("grant").assertIsDisplayed()
        for (tag in listOf("input", "search", "open", "help")) reach("home", hasTestTag(tag)).assertIsDisplayed()
        compose.onNodeWithTag("nav-settings").performClick()
        for (tag in SettingsScreenTest.CONTROLS) reach("settings", hasTestTag(tag)).assertIsDisplayed()
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
}
