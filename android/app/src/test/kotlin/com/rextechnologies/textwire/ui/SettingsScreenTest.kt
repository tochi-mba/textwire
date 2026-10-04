package com.rextechnologies.textwire.ui

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.test.performTextReplacement
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.SERVER
import com.rextechnologies.textwire.data.SettingsChoices
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Kind
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Every setting: it shows what is saved, and changing it saves at once. */
@RunWith(AndroidJUnit4::class)
class SettingsScreenTest : ScreenHarness() {
    @Before
    fun open() {
        show()
        compose.onNodeWithTag("nav-settings").performClick()
    }

    private fun control(tag: String) = reach("settings", hasTestTag(tag))

    @Test
    fun `the server number applies once it is a whole number, and says what is wrong until then`() {
        control("server-number").performTextReplacement("07700")
        reach("settings", hasText("A number like +447700900000, with the country code")).assertIsDisplayed()
        assertEquals(SERVER, settings.snapshot.serverNumber)
        control("server-number").performTextReplacement(" +447700900111 ")
        compose.waitForIdle()
        assertEquals("+447700900111", settings.snapshot.serverNumber)
    }

    @Test
    fun `the page size slider saves when let go and shows what a page holds and costs`() {
        control("page-estimate").assertTextContains("12 texts · about 800 words · ~0.67 USD")
        control("page-frames").performSemanticsAction(SemanticsActions.SetProgress) { it(20f) }
        compose.waitForIdle()
        assertEquals(20, settings.snapshot.pageFrames)
        control("page-estimate").assertTextContains("20 texts · about 1300 words · ~1.12 USD")
    }

    @Test
    fun `each switch turns its setting on and off`() {
        val switches = mapOf<String, (SettingsSnapshot) -> Boolean>(
            "open-on-arrival" to { it.openOnArrival },
            "keep-screen-on" to { it.keepScreenOn },
            "notify" to { it.notifyOnArrival },
        )
        for ((tag, value) in switches) {
            val before = value(settings.snapshot)
            if (before) control(tag).assertIsOn() else control(tag).assertIsOff()
            control(tag).performClick()
            compose.waitForIdle()
            assertEquals(!before, value(settings.snapshot), tag)
            control(tag).performClick()
            compose.waitForIdle()
            assertEquals(before, value(settings.snapshot), tag)
        }
    }

    @Test
    fun `each row of choices saves the one tapped and shows it selected`() {
        val rows = listOf<Triple<String, List<Any>, (SettingsSnapshot) -> Any>>(
            Triple("nak-after", SettingsChoices.NAK_AFTER_MILLIS, { it.nakAfterMillis }),
            Triple("resend-rounds", SettingsChoices.RESEND_ROUNDS, { it.resendRounds }),
            Triple("daily-limit", SettingsChoices.DAILY_LIMITS, { it.dailyLimit }),
            Triple("text-size", SettingsChoices.TEXT_SCALES, { it.textScale }),
            Triple("history-days", SettingsChoices.HISTORY_DAYS, { it.historyDays }),
        )
        for ((tag, options, value) in rows) {
            for (index in options.indices) {
                control("$tag-$index").performClick()
                compose.waitForIdle()
                assertEquals(options[index], value(settings.snapshot), "$tag-$index")
                control("$tag-$index").assertIsSelected()
            }
        }
    }

    @Test
    fun `each row of choices is labelled the way a person says it`() {
        val labels = mapOf(
            "nak-after" to listOf("30 s", "1 min", "2 min", "5 min"),
            "resend-rounds" to listOf("Never", "1x", "2x", "3x", "5x"),
            "daily-limit" to listOf("Off", "50", "100", "200", "500"),
            "text-size" to listOf("Small", "Default", "Large", "Largest"),
            "history-days" to listOf("1 day", "7 days", "30 days", "Always"),
        )
        for ((tag, words) in labels) {
            words.forEachIndexed { index, word -> control("$tag-$index").assertTextContains(word) }
        }
    }

    @Test
    fun `price and currency apply when valid and explain themselves when not`() {
        control("price").performTextReplacement("cheap")
        reach("settings", hasText("A price per text, such as 0.056")).assertIsDisplayed()
        control("price").performTextReplacement("0.03")
        control("currency").performTextReplacement("gb")
        reach("settings", hasText("Three letters, such as GBP")).assertIsDisplayed()
        control("currency").performTextReplacement("gbp")
        compose.waitForIdle()
        assertEquals(0.03, settings.snapshot.pricePerSegment)
        assertEquals("GBP", settings.snapshot.currency)
        control("page-estimate").assertTextContains("~0.36 GBP", substring = true)
    }

    @Test
    fun `the text size shows a sample at the chosen size`() {
        control("text-preview").assertTextContains("A page reads like this.")
        control("text-size-3").performClick()
        control("text-preview").assertIsDisplayed()
    }

    @Test
    fun `when Android blocks notifications the screen offers to ask again`() {
        compose.onNodeWithTag("allow-notifications").assertDoesNotExist()
        notificationsAllowed = false
        control("allow-notifications").performClick()
        assertEquals(1, permissionRequests)
        control("notify").performClick()
        compose.onNodeWithTag("allow-notifications").assertDoesNotExist()
    }

    @Test
    fun `clearing history asks first, and Cancel keeps everything`() {
        storage.savePage(StoredPage(1, Kind.PAGE, 1, 1, "# Kept", 1, clock.now))
        control("clear-history").performClick()
        compose.onNodeWithText("Clear history?").assertIsDisplayed()
        compose.onNodeWithTag("cancel").performClick()
        assertEquals(1, storage.pagesByTag.size)
        control("clear-history").performClick()
        compose.onNodeWithTag("confirm").assertTextContains("Clear").performClick()
        assertTrue(storage.pagesByTag.isEmpty())
        compose.onNodeWithText("History cleared.").assertIsDisplayed()
    }

    @Test
    fun `reset asks first, keeps the number and reloads what the fields show`() {
        control("price").performTextReplacement("0.5")
        control("currency").performTextReplacement("EUR")
        control("daily-limit-2").performClick()
        control("reset-settings").performClick()
        compose.onNodeWithText("Reset settings?").assertIsDisplayed()
        compose.onNodeWithTag("confirm").assertTextContains("Reset").performClick()
        compose.waitForIdle()
        assertEquals(SettingsSnapshot(serverNumber = SERVER), settings.snapshot)
        control("price").assertTextContains("0.056")
        control("currency").assertTextContains("USD")
        control("daily-limit-0").assertIsSelected()
    }

    @Test
    fun `the about card names the version`() {
        reach("settings", hasText("About")).assertIsDisplayed()
        reach("settings", hasText("A REX Technologies product.", substring = true))
            .assertTextContains("textwire 0.1.0", substring = true)
    }

    companion object {
        /** Every control on the screen, for the small-phone reachability test. */
        val CONTROLS = listOf(
            "server-number", "page-frames", "open-on-arrival", "nak-after-0", "resend-rounds-0", "price",
            "currency", "daily-limit-0", "text-size-0", "keep-screen-on", "notify", "history-days-0",
            "clear-history", "reset-settings",
        )
    }
}
