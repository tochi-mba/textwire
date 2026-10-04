package com.rextechnologies.textwire

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.data.UpdateGuide
import com.rextechnologies.textwire.notify.AndroidNotifier
import com.rextechnologies.textwire.ui.TextwireUi
import com.rextechnologies.textwire.ui.shareableText

/**
 * The one activity: it draws the controller's state, asks for permissions, tells the
 * controller when it is on screen, and opens the page a notification was tapped for.
 */
class MainActivity : ComponentActivity() {
    private var granted by mutableStateOf(false)
    private var notifications by mutableStateOf(false)
    private var updateGuideVisible by mutableStateOf(false)

    private val controller: Controller get() = (application as TextwireApp).controller
    private val updateGuide by lazy { UpdateGuide(this) }

    private val ask = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        readPermissions()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // First, before anything can write a preference: an empty store is what marks a fresh install.
        updateGuideVisible = updateGuide.opensOnLaunch()
        readPermissions()
        openFrom(intent)
        setContent {
            TextwireUi(
                controller = controller,
                permissionsGranted = granted,
                notificationsAllowed = notifications,
                requestPermissions = { ask.launch(ASKED) },
                share = ::share,
                updateGuideVisible = updateGuideVisible,
                dismissUpdateGuide = {
                    updateGuide.markSeen()
                    updateGuideVisible = false
                },
                showUpdateGuide = { updateGuideVisible = true },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        openFrom(intent)
    }

    override fun onStart() {
        super.onStart()
        controller.setVisible(true)
    }

    override fun onResume() {
        super.onResume()
        readPermissions()
        controller.tick()
    }

    override fun onStop() {
        controller.setVisible(false)
        super.onStop()
    }

    /** Hands a page to the share sheet as plain text, titled, without its link numbers. */
    private fun share(page: StoredPage) {
        val send = Intent(Intent.ACTION_SEND)
            .setType("text/plain")
            .putExtra(Intent.EXTRA_SUBJECT, page.title)
            .putExtra(Intent.EXTRA_TEXT, shareableText(page))
        startActivity(Intent.createChooser(send, "Share page"))
    }

    /** Opens the page a tapped notification names; any other intent opens nothing. */
    private fun openFrom(intent: Intent) {
        val tag = intent.getIntExtra(AndroidNotifier.EXTRA_TAG, -1)
        if (tag >= 0) controller.open(tag)
    }

    private fun readPermissions() {
        granted = SMS.all(::has)
        notifications = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || has(NOTIFY)
    }

    private fun has(permission: String) =
        ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED

    // POST_NOTIFICATIONS is a string the compiler inlines; it is only asked for or checked on 33+.
    @SuppressLint("InlinedApi")
    private companion object {
        val SMS = arrayOf(Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS)
        const val NOTIFY = Manifest.permission.POST_NOTIFICATIONS

        /** Asked together: SMS to work at all, notifications for pages that arrive while away. */
        val ASKED = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) SMS + NOTIFY else SMS
    }
}
