package com.rextechnologies.textwire.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.core.CostMeter
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@RunWith(AndroidJUnit4::class)
class SettingsTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `a fresh install reads the defaults`() {
        assertEquals(SettingsSnapshot(), PreferencesSettings(context).read())
    }

    @Test
    fun `what is written is read back after a restart`() {
        val written = SettingsSnapshot(
            serverNumber = "+447700900000",
            pageFrames = 20,
            nakAfterMillis = 90_000,
            resendRounds = 5,
            pricePerSegment = 0.031,
            currency = "GBP",
            dailyLimit = 100,
            openOnArrival = false,
            notifyOnArrival = false,
            textScale = 1.3f,
            keepScreenOn = true,
            historyDays = 7,
            nextTag = 41,
            segmentsToday = 17,
            segmentsDay = "2026-10-01",
        )
        PreferencesSettings(context).write(written)
        // A new instance stands in for the app starting again.
        assertEquals(written, PreferencesSettings(context).read())
    }

    @Test
    fun `reset puts every choice back and keeps the number and the counters`() {
        val changed = SettingsSnapshot(
            serverNumber = "+447700900000",
            pageFrames = 3,
            nakAfterMillis = 30_000,
            resendRounds = 0,
            pricePerSegment = 1.0,
            currency = "EUR",
            dailyLimit = 50,
            openOnArrival = false,
            notifyOnArrival = false,
            textScale = 0.85f,
            keepScreenOn = true,
            historyDays = 1,
            nextTag = 9,
            segmentsToday = 4,
            segmentsDay = "2026-10-02",
        )
        assertEquals(
            SettingsSnapshot(
                serverNumber = "+447700900000",
                nextTag = 9,
                segmentsToday = 4,
                segmentsDay = "2026-10-02",
            ),
            changed.reset(),
        )
    }

    @Test
    fun `every default is one of the choices the screen offers`() {
        val defaults = SettingsSnapshot()
        assertTrue(defaults.pageFrames in SettingsChoices.PAGE_FRAMES)
        assertTrue(defaults.nakAfterMillis in SettingsChoices.NAK_AFTER_MILLIS)
        assertTrue(defaults.resendRounds in SettingsChoices.RESEND_ROUNDS)
        assertTrue(defaults.dailyLimit in SettingsChoices.DAILY_LIMITS)
        assertTrue(defaults.textScale in SettingsChoices.TEXT_SCALES)
        assertTrue(defaults.historyDays in SettingsChoices.HISTORY_DAYS)
    }

    @Test
    fun `a stored price that is not a number falls back to the default`() {
        context.getSharedPreferences(PREFERENCES_FILE, Context.MODE_PRIVATE).edit().putString("price", "cheap").commit()
        assertEquals(CostMeter.DEFAULT_PRICE, PreferencesSettings(context).read().pricePerSegment)
    }
}
