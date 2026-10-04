package com.rextechnologies.textwire.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.Screen
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** The guide to an update: what it lists, where Show me goes, and how it comes back. */
@RunWith(AndroidJUnit4::class)
class WhatsNewTest : ScreenHarness() {
    @Test
    fun `the guide lists every feature of the update and Got it closes it for good`() {
        guideVisible = true
        show()
        compose.onNodeWithText("What\u2019s new in textwire").assertIsDisplayed()
        WHATS_NEW.forEachIndexed { index, feature ->
            compose.onNodeWithText(feature.title).performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("show-me-$index").assertIsDisplayed()
        }
        compose.onNodeWithTag("whats-new-done").performClick()
        compose.onNodeWithTag("whats-new").assertDoesNotExist()
        assertEquals(1, guideDismissals)
    }

    @Test
    fun `Show me closes the guide and opens the screen the feature lives on`() {
        WHATS_NEW.forEachIndexed { index, feature ->
            guideVisible = true
            if (index == 0) show()
            compose.onNodeWithTag("show-me-$index").performScrollTo().performClick()
            compose.onNodeWithTag("whats-new").assertDoesNotExist()
            assertEquals(feature.screen, controller.state.value.screen, feature.title)
        }
        assertEquals(WHATS_NEW.size, guideDismissals)
    }

    @Test
    fun `the guide can be opened again from Settings`() {
        show()
        compose.onNodeWithTag("nav-settings").performClick()
        reach("settings", hasTestTag("show-whats-new")).performClick()
        compose.onNodeWithTag("whats-new").assertIsDisplayed()
    }

    @Test
    fun `every feature says something and points somewhere`() {
        assertTrue(WHATS_NEW.isNotEmpty())
        for (feature in WHATS_NEW) {
            assertTrue(feature.title.isNotBlank() && feature.body.length > 20, feature.title)
            assertTrue(feature.screen in Screen.entries)
        }
    }
}
