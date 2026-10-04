package com.rextechnologies.textwire

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.telephony.SmsManager
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.Configuration
import androidx.work.testing.WorkManagerTestInitHelper
import com.rextechnologies.textwire.data.Database
import com.rextechnologies.textwire.data.PREFERENCES_FILE
import com.rextechnologies.textwire.data.PreferencesSettings
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.data.UpdateGuide
import com.rextechnologies.textwire.notify.AndroidNotifier
import com.rextechnologies.textwire.protocol.Alphabet
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.encodeFrame
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The real activity over the real application: permissions, the tick on coming back, pages
 * opened from notifications, notifications only while away, and the share sheet.
 */
@RunWith(AndroidJUnit4::class)
class MainActivityTest {
    @get:Rule
    val compose = createEmptyComposeRule()

    private val app: TextwireApp = ApplicationProvider.getApplicationContext()

    @Before
    fun init() {
        WorkManagerTestInitHelper.initializeTestWorkManager(app, Configuration.Builder().build())
        // The guide to the update is tested on its own below; elsewhere it would sit on top.
        UpdateGuide(app).markSeen()
    }

    /** The phone as it is straight after an install: no preferences at all. */
    private fun freshInstall() = app.getSharedPreferences(
        PREFERENCES_FILE,
        Context.MODE_PRIVATE,
    ).edit().clear().commit()

    @Test
    fun `a new install opens on Home, without the guide to an update`() {
        freshInstall()
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("input").assertIsDisplayed()
            compose.onNodeWithTag("whats-new").assertDoesNotExist()
        }
    }

    @Test
    fun `after an update the guide opens once, and Got it means it stays closed`() {
        freshInstall()
        PreferencesSettings(app).write(SettingsSnapshot(serverNumber = SERVER))
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("whats-new").assertIsDisplayed()
            compose.onNodeWithTag("whats-new-done").performClick()
            compose.onNodeWithTag("whats-new").assertDoesNotExist()
        }
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("input").assertIsDisplayed()
            compose.onNodeWithTag("whats-new").assertDoesNotExist()
        }
    }

    @Test
    fun `Settings opens the guide again`() {
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("nav-settings").performClick()
            compose.onNodeWithTag("settings").performScrollToNode(hasTestTag("show-whats-new"))
            compose.onNodeWithTag("show-whats-new").performClick()
            compose.onNodeWithTag("whats-new").assertIsDisplayed()
        }
    }

    @Test
    fun `with the permissions already granted there is nothing to ask`() {
        shadowOf(app).grantPermissions(*SMS)
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("input").assertIsDisplayed()
            compose.onNodeWithTag("grant").assertDoesNotExist()
        }
    }

    @Test
    fun `the banner asks for SMS and notifications and stays until both SMS permissions are granted`() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            compose.onNodeWithTag("grant").performClick()
            scenario.onActivity { activity ->
                assertEquals(
                    (SMS + NOTIFY).toList(),
                    shadowOf(activity).lastRequestedPermission.requestedPermissions.toList(),
                )
                answer(activity, GRANTED, DENIED, GRANTED)
            }
            compose.onNodeWithTag("grant").assertIsDisplayed()
            compose.onNodeWithTag("grant").performClick()
            scenario.onActivity { activity -> answer(activity, GRANTED, GRANTED, DENIED) }
            // Closing the platform permission sheet resumes the activity. ActivityScenario's
            // direct result callback does not synthesize that lifecycle edge for Robolectric.
            scenario.moveToState(Lifecycle.State.STARTED)
            scenario.moveToState(Lifecycle.State.RESUMED)
            compose.onNodeWithTag("grant").assertDoesNotExist()
        }
    }

    @Test
    @Config(sdk = [32])
    fun `before Android 13 only the SMS permissions are asked for`() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            compose.onNodeWithTag("grant").performClick()
            scenario.onActivity { activity ->
                assertEquals(SMS.toList(), shadowOf(activity).lastRequestedPermission.requestedPermissions.toList())
            }
        }
    }

    /** Answers the permission dialog the way the system does: it grants, then calls back. */
    @Suppress("DEPRECATION") // The system's entry point; the app itself uses the Activity Result API.
    private fun answer(activity: MainActivity, vararg results: Int) {
        val asked = shadowOf(activity).lastRequestedPermission
        asked.requestedPermissions.forEachIndexed { index, permission ->
            if (results[index] ==
                GRANTED
            ) {
                shadowOf(app).grantPermissions(permission)
            } else {
                shadowOf(app).denyPermissions(permission)
            }
        }
        activity.onRequestPermissionsResult(asked.requestCode, asked.requestedPermissions, results)
    }

    @Test
    fun `coming back to the app asks again for a reply that has gone quiet`() {
        // A short quiet time: the timer job stays queued (the test WorkManager does not run
        // delayed work by itself), and the request is overdue by the time the app is opened.
        PreferencesSettings(app).write(SettingsSnapshot(serverNumber = SERVER, nakAfterMillis = QUIET_MILLIS))
        app.controller.get("https://example.com")
        val sms = shadowOf(app.getSystemService(SmsManager::class.java))
        assertEquals("00 g12 https://example.com", sms.lastSentTextMessageParams.text)
        Thread.sleep(OVERDUE_MILLIS)
        ActivityScenario.launch(MainActivity::class.java).use {
            compose.onNodeWithTag("pending-00").assertIsDisplayed()
            assertEquals("01 r 00 0", sms.lastSentTextMessageParams.text)
            assertEquals(SERVER, sms.lastSentTextMessageParams.destinationAddress)
        }
    }

    @Test
    fun `a tapped notification opens its page, whether the app was closed or open`() {
        Database(app).apply {
            savePage(StoredPage(7, Kind.PAGE, 1, 1, "# Seven\n\nx", 1, System.currentTimeMillis()))
            savePage(StoredPage(8, Kind.PAGE, 1, 1, "# Eight\n\nx", 1, System.currentTimeMillis()))
        }
        val tapped = Intent(app, MainActivity::class.java).putExtra(AndroidNotifier.EXTRA_TAG, 7)
        // Robolectric's controller delivers a second intent the way the system does to a
        // single-top activity that is already open.
        val activity = Robolectric.buildActivity(MainActivity::class.java, tapped).setup()
        compose.onNodeWithTag("reader").assertIsDisplayed()
        compose.onAllNodesWithText("Seven").assertCountEquals(2)
        activity.newIntent(Intent().putExtra(AndroidNotifier.EXTRA_TAG, 8))
        activity.newIntent(Intent())
        compose.onAllNodesWithText("Eight").assertCountEquals(2)
        activity.pause().stop().destroy()
    }

    @Test
    fun `a page is notified only while the app is not on screen`() {
        shadowOf(app).grantPermissions(*SMS, NOTIFY)
        PreferencesSettings(app).write(SettingsSnapshot(serverNumber = SERVER))
        val manager = shadowOf(app.getSystemService(NotificationManager::class.java))
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            app.controller.onSms(SERVER, frame(0, "# Here\n\nx"))
            assertTrue(manager.allNotifications.isEmpty())
            scenario.moveToState(Lifecycle.State.CREATED)
            app.controller.onSms(SERVER, frame(1, "# Away\n\nx"))
            assertEquals(1, manager.allNotifications.size)
        }
    }

    @Test
    fun `share hands the open page to the share sheet as plain text`() {
        shadowOf(app).grantPermissions(*SMS)
        Database(
            app,
        ).savePage(StoredPage(3, Kind.PAGE, 1, 1, "# Shared\n\nSee this[2].", 1, System.currentTimeMillis()))
        val tapped = Intent(app, MainActivity::class.java).putExtra(AndroidNotifier.EXTRA_TAG, 3)
        ActivityScenario.launch<MainActivity>(tapped).use { scenario ->
            compose.onNodeWithTag("share").performClick()
            scenario.onActivity { activity ->
                val chooser = shadowOf(activity).nextStartedActivity
                assertEquals(Intent.ACTION_CHOOSER, chooser.action)
                @Suppress("DEPRECATION") // The typed overload needs API 33; the tests also run on 32.
                val send = chooser.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)!!
                assertEquals("text/plain", send.type)
                assertEquals("Shared", send.getStringExtra(Intent.EXTRA_SUBJECT))
                assertEquals("# Shared\n\nSee this.", send.getStringExtra(Intent.EXTRA_TEXT))
            }
        }
    }

    /** A one-frame reply with tag [tag]. */
    private fun frame(tag: Int, text: String): String {
        val payload = byteArrayOf(Kind.PAGE.code.toByte(), 0, 1, 1) + text.toByteArray()
        return encodeFrame(Frame(tag, 0, 1, payload.toList()), Alphabet.B64)
    }

    private companion object {
        val SMS = arrayOf(Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS)
        const val NOTIFY = Manifest.permission.POST_NOTIFICATIONS
        const val GRANTED = PackageManager.PERMISSION_GRANTED
        const val DENIED = PackageManager.PERMISSION_DENIED
        const val QUIET_MILLIS = 300L
        const val OVERDUE_MILLIS = QUIET_MILLIS + 50
    }
}
