package com.rextechnologies.textwire

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.rextechnologies.textwire.ui.TextwireUi

/** The one activity: it draws the controller's state and asks for the SMS permissions. */
class MainActivity : ComponentActivity() {
    private var granted by mutableStateOf(false)

    private val ask = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
        granted = results.values.all { it }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val controller = (application as TextwireApp).controller
        granted = PERMISSIONS.all { ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }
        setContent {
            TextwireUi(controller = controller, permissionsGranted = granted, requestPermissions = {
                ask.launch(PERMISSIONS)
            })
        }
    }

    override fun onResume() {
        super.onResume()
        (application as TextwireApp).controller.tick()
    }

    private companion object {
        val PERMISSIONS = arrayOf(Manifest.permission.SEND_SMS, Manifest.permission.RECEIVE_SMS)
    }
}
