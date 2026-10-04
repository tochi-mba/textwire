package com.rextechnologies.textwire.notify

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.rextechnologies.textwire.MainActivity
import com.rextechnologies.textwire.R
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.ui.pageMeta

/** Tells the person a page arrived while the app was not on screen. */
fun interface Notifier {
    fun pageArrived(page: StoredPage)
}

/**
 * [Notifier] as an Android notification: one per page, tapped to open it in the reader.
 *
 * Posts nothing when the person has turned notifications off or not granted them; the page
 * is still on the Home screen.
 */
class AndroidNotifier(private val context: Context) : Notifier {
    override fun pageArrived(page: StoredPage) {
        val tiramisu = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        if (tiramisu &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        val notifications = NotificationManagerCompat.from(context)
        if (!notifications.areNotificationsEnabled()) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Pages that arrive", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "A page you asked for has arrived while textwire was closed."
            },
        )
        val open = Intent(context, MainActivity::class.java)
            .putExtra(EXTRA_TAG, page.tag)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val tap = PendingIntent.getActivity(
            context,
            page.tag,
            open,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(page.title)
            .setContentText(pageMeta(page))
            .setContentIntent(tap)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .build()
        notifications.notify(page.tag, notification)
    }

    companion object {
        const val CHANNEL = "pages"

        /** The tag of the page a notification opens. */
        const val EXTRA_TAG = "com.rextechnologies.textwire.TAG"
    }
}
