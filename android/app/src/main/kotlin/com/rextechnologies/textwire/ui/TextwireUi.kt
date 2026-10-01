package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.Screen
import com.rextechnologies.textwire.UiState

/** The whole app: a bar of four screens and the one that is showing. */
@Composable
fun TextwireUi(controller: Controller, permissionsGranted: Boolean, requestPermissions: () -> Unit) {
    val state by controller.state.collectAsState()
    MaterialTheme {
        Scaffold(
            bottomBar = { NavigationBar(state.screen, controller::show) },
            snackbarHost = {
                state.notice?.let { notice ->
                    Snackbar(
                        modifier = Modifier.padding(12.dp).testTag("notice"),
                        action = { TextButton(onClick = controller::dismissNotice) { Text("OK") } },
                    ) { Text(notice) }
                }
            },
        ) { padding ->
            Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                if (!permissionsGranted) {
                    PermissionCard(requestPermissions)
                }
                Screens(state, controller)
            }
        }
    }
}

@Composable
private fun Screens(state: UiState, controller: Controller) {
    when (state.screen) {
        Screen.HOME -> HomeScreen(state, controller)
        Screen.READER -> ReaderScreen(state, controller)
        Screen.DIAGNOSTICS -> DiagnosticsScreen(state, controller)
        Screen.SETTINGS -> SettingsScreen(state, controller)
    }
}

@Composable
private fun NavigationBar(current: Screen, show: (Screen) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth().padding(8.dp)) {
        for (screen in Screen.entries) {
            TextButton(onClick = { show(screen) }, modifier = Modifier.testTag("nav-${screen.name.lowercase()}")) {
                Text(
                    text = screen.name.lowercase().replaceFirstChar { it.uppercase() },
                    style = if (screen ==
                        current
                    ) {
                        MaterialTheme.typography.titleMedium
                    } else {
                        MaterialTheme.typography.bodyMedium
                    },
                )
            }
        }
    }
}

@Composable
private fun PermissionCard(requestPermissions: () -> Unit) {
    Column(modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp)) {
        Text("textwire needs to send and receive SMS. Nothing else.", style = MaterialTheme.typography.bodyLarge)
        Button(onClick = requestPermissions, modifier = Modifier.padding(top = 8.dp).testTag("grant")) {
            Text("Grant SMS permissions")
        }
    }
}
