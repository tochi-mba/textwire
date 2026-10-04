package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.MailOutline
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.Screen
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.StoredPage

/**
 * The whole app: a top bar, the screen that is showing, and a bar of four destinations.
 *
 * Everything that needs Android (asking for permissions, the share sheet, whether the guide to
 * an update is open) comes in from the activity as a value or a function, so the screens are
 * tested without one.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TextwireUi(
    controller: Controller,
    permissionsGranted: Boolean,
    notificationsAllowed: Boolean,
    requestPermissions: () -> Unit,
    share: (StoredPage) -> Unit,
    updateGuideVisible: Boolean,
    dismissUpdateGuide: () -> Unit,
    showUpdateGuide: () -> Unit,
) {
    val state by controller.state.collectAsState()
    TextwireTheme {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text(title(state), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    actions = { ReaderActions(state, controller, share) },
                )
            },
            bottomBar = { Destinations(state.screen, controller::show) },
            snackbarHost = {
                state.notice?.let { notice ->
                    Snackbar(
                        modifier = Modifier.padding(12.dp).testTag("notice"),
                        action = {
                            TextButton(onClick = controller::act, modifier = Modifier.testTag("notice-action")) {
                                Text(notice.action?.label ?: "OK")
                            }
                        },
                    ) { Text(notice.text) }
                }
            },
        ) { padding ->
            Column(modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp)) {
                if (!permissionsGranted) PermissionBanner(requestPermissions)
                when (state.screen) {
                    Screen.HOME -> HomeScreen(state, controller)
                    Screen.READER -> ReaderScreen(state, controller)
                    Screen.DIAGNOSTICS -> DiagnosticsScreen(state, controller, permissionsGranted, notificationsAllowed)
                    Screen.SETTINGS -> SettingsScreen(
                        state,
                        controller,
                        notificationsAllowed,
                        requestPermissions,
                        showUpdateGuide,
                    )
                }
            }
        }
        if (updateGuideVisible) {
            WhatsNewDialog(dismiss = dismissUpdateGuide) { screen ->
                dismissUpdateGuide()
                controller.show(screen)
            }
        }
    }
}

private fun title(state: UiState): String = when (state.screen) {
    Screen.HOME -> "textwire"
    Screen.READER -> state.reading?.title ?: "Reader"
    Screen.DIAGNOSTICS -> "Diagnostics"
    Screen.SETTINGS -> "Settings"
}

/** Share and delete, while a page is open in the reader. */
@Composable
private fun ReaderActions(state: UiState, controller: Controller, share: (StoredPage) -> Unit) {
    val page = state.reading
    if (state.screen != Screen.READER || page == null) return
    IconButton(onClick = { share(page) }, modifier = Modifier.testTag("share")) {
        Icon(Icons.Filled.Share, contentDescription = "Share this page")
    }
    IconButton(onClick = { controller.deletePage(page.tag) }, modifier = Modifier.testTag("delete-page")) {
        Icon(Icons.Filled.Delete, contentDescription = "Delete this page")
    }
}

private data class Destination(val screen: Screen, val label: String, val icon: ImageVector)

private val DESTINATIONS = listOf(
    Destination(Screen.HOME, "Home", Icons.Filled.Home),
    Destination(Screen.READER, "Reader", Icons.Filled.MailOutline),
    Destination(Screen.DIAGNOSTICS, "Diagnostics", Icons.Filled.Info),
    Destination(Screen.SETTINGS, "Settings", Icons.Filled.Settings),
)

@Composable
private fun Destinations(current: Screen, show: (Screen) -> Unit) {
    NavigationBar {
        for (destination in DESTINATIONS) {
            NavigationBarItem(
                selected = destination.screen == current,
                onClick = { show(destination.screen) },
                icon = { Icon(destination.icon, contentDescription = null) },
                label = { Text(destination.label) },
                modifier = Modifier.testTag("nav-${destination.screen.name.lowercase()}"),
            )
        }
    }
}

@Composable
private fun PermissionBanner(requestPermissions: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Row(
            modifier = Modifier.padding(start = 16.dp, end = 12.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "textwire sends requests and receives pages as SMS. It needs your permission to do both.",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            Button(onClick = requestPermissions, modifier = Modifier.padding(start = 12.dp).testTag("grant")) {
                Text("Allow")
            }
        }
    }
}
