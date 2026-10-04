package com.rextechnologies.textwire.notify

import android.Manifest
import android.app.NotificationManager
import androidx.core.app.NotificationCompat
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.MainActivity
import com.rextechnologies.textwire.TextwireApp
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Kind
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@RunWith(AndroidJUnit4::class)
@Config(application = TextwireApp::class)
class NotifierTest {
    private val app: TextwireApp = ApplicationProvider.getApplicationContext()
    private val manager = app.getSystemService(NotificationManager::class.java)
    private val page = StoredPage(7, Kind.PAGE, 1, 3, "# Weather in London\n\nSun.", 12, 0)

    @Test
    fun `a page that arrives is one notification that opens it`() {
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        AndroidNotifier(app).pageArrived(page)
        val posted = shadowOf(manager).allNotifications.single()
        assertEquals("Weather in London", posted.extras.getString(NotificationCompat.EXTRA_TITLE))
        assertTrue(posted.extras.getString(NotificationCompat.EXTRA_TEXT)!!.startsWith("Page 1 of 3 · 12 texts"))
        assertEquals(AndroidNotifier.CHANNEL, posted.channelId)
        assertEquals("Pages that arrive", manager.getNotificationChannel(AndroidNotifier.CHANNEL).name)
        val opens = shadowOf(posted.contentIntent).savedIntent
        assertEquals(MainActivity::class.java.name, opens.component?.className)
        assertEquals(7, opens.getIntExtra(AndroidNotifier.EXTRA_TAG, -1))
        // A second page is a second notification, not a replacement.
        AndroidNotifier(app).pageArrived(page.copy(tag = 8))
        assertEquals(2, shadowOf(manager).allNotifications.size)
    }

    @Test
    fun `nothing is posted without the permission`() {
        AndroidNotifier(app).pageArrived(page)
        assertTrue(shadowOf(manager).allNotifications.isEmpty())
    }

    @Test
    fun `nothing is posted when notifications are turned off for the app`() {
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        shadowOf(manager).setNotificationsEnabled(false)
        AndroidNotifier(app).pageArrived(page)
        assertTrue(shadowOf(manager).allNotifications.isEmpty())
    }

    @Test
    @Config(sdk = [32])
    fun `before Android 13 no permission is needed`() {
        AndroidNotifier(app).pageArrived(page)
        assertEquals(1, shadowOf(manager).allNotifications.size)
    }
}
