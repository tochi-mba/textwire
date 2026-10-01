package com.rextechnologies.textwire.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.core.CostMeter
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals

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
            pricePerSegment = 0.031,
            currency = "GBP",
            nextTag = 41,
            segmentsToday = 17,
            segmentsDay = "2026-10-01",
        )
        PreferencesSettings(context).write(written)
        // A new instance stands in for the app starting again.
        assertEquals(written, PreferencesSettings(context).read())
    }

    @Test
    fun `a stored price that is not a number falls back to the default`() {
        context.getSharedPreferences("textwire", Context.MODE_PRIVATE).edit().putString("price", "cheap").commit()
        assertEquals(CostMeter.DEFAULT_PRICE, PreferencesSettings(context).read().pricePerSegment)
    }
}
