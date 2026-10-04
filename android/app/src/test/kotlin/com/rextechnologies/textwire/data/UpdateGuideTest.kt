package com.rextechnologies.textwire.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** The guide to an update opens once for someone who updated, and never for a new install. */
@RunWith(AndroidJUnit4::class)
class UpdateGuideTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `a fresh install skips the guide and remembers that it did`() {
        assertFalse(UpdateGuide(context).opensOnLaunch())
        // Settings written afterwards do not make it look like an update.
        PreferencesSettings(context).write(SettingsSnapshot(serverNumber = "+447700900000"))
        assertFalse(UpdateGuide(context).opensOnLaunch())
    }

    @Test
    fun `an update from before the guide existed shows it until it is seen`() {
        PreferencesSettings(context).write(SettingsSnapshot(serverNumber = "+447700900000"))
        assertTrue(UpdateGuide(context).opensOnLaunch())
        assertTrue(UpdateGuide(context).opensOnLaunch())
        UpdateGuide(context).markSeen()
        assertFalse(UpdateGuide(context).opensOnLaunch())
    }

    @Test
    fun `a later guide shows once more to someone who saw the earlier one`() {
        PreferencesSettings(context).write(SettingsSnapshot())
        UpdateGuide(context, latestGuide = 1).markSeen()
        assertFalse(UpdateGuide(context, latestGuide = 1).opensOnLaunch())
        assertTrue(UpdateGuide(context, latestGuide = 2).opensOnLaunch())
        UpdateGuide(context, latestGuide = 2).markSeen()
        assertFalse(UpdateGuide(context, latestGuide = 2).opensOnLaunch())
    }
}
