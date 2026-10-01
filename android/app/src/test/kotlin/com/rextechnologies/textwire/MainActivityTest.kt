package com.rextechnologies.textwire

import android.Manifest
import android.content.pm.PackageManager
import android.telephony.SmsManager
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.Configuration
import androidx.work.testing.WorkManagerTestInitHelper
import com.rextechnologies.textwire.data.PreferencesSettings
import com.rextechnologies.textwire.data.SettingsSnapshot
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import kotlin.test.assertEquals

/** The real activity over the real application: permissions, and the tick on coming back. */
@RunWith(AndroidJUnit4::class)
class MainActivityTest {
    @get:Rule
    val compose = createEmptyComposeRule()

    private val app: TextwireApp = ApplicationProvider.getApplicationContext()

    @Before
    fun init() {
        WorkManagerTestInitHelper.initializeTestWorkManager(app, Configuration.Builder().build())
    }

    @Test
    fun `with the permissions already granted there is nothing to ask`() {
        shadowOf(app).grantPermissions(*PERMISSIONS)
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("input").assertIsDisplayed()
            compose.onNodeWithTag("grant").assertDoesNotExist()
        }
    }

    @Test
    fun `the banner asks for both SMS permissions and stays until both are granted`() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            compose.onNodeWithTag("grant").performClick()
            scenario.onActivity { activity ->
                assertEquals(
                    PERMISSIONS.toList(),
                    shadowOf(activity).lastRequestedPermission.requestedPermissions.toList(),
                )
                answer(activity, PackageManager.PERMISSION_GRANTED, PackageManager.PERMISSION_DENIED)
            }
            compose.onNodeWithTag("grant").assertIsDisplayed()
            compose.onNodeWithTag("grant").performClick()
            scenario.onActivity { activity ->
                answer(activity, PackageManager.PERMISSION_GRANTED, PackageManager.PERMISSION_GRANTED)
            }
            compose.onNodeWithTag("grant").assertDoesNotExist()
        }
    }

    /** Answers the permission dialog the way the system does: through the activity's callback. */
    @Suppress("DEPRECATION") // The system's entry point; the app itself uses the Activity Result API.
    private fun answer(activity: MainActivity, vararg results: Int) {
        val asked = shadowOf(activity).lastRequestedPermission
        activity.onRequestPermissionsResult(asked.requestCode, asked.requestedPermissions, results)
    }

    @Test
    fun `coming back to the app asks again for a reply that has gone quiet`() {
        // A short quiet time: the timer job stays queued (the test WorkManager does not run
        // delayed work by itself), and the request is overdue by the time the app is opened.
        PreferencesSettings(app).write(SettingsSnapshot(serverNumber = SERVER, nakAfterMillis = QUIET_MILLIS))
        app.controller.get("https://example.com")
        val sms = shadowOf(app.getSystemService(SmsManager::class.java))
        assertEquals("00 g https://example.com", sms.lastSentTextMessageParams.text)
        Thread.sleep(OVERDUE_MILLIS)
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("pending-00").assertIsDisplayed()
            assertEquals("01 r 00 0", sms.lastSentTextMessageParams.text)
            assertEquals(SERVER, sms.lastSentTextMessageParams.destinationAddress)
        }
    }

    private companion object {
        val PERMISSIONS = arrayOf(Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS)
        const val QUIET_MILLIS = 300L
        const val OVERDUE_MILLIS = QUIET_MILLIS + 50
    }
}
