package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Screen

/** One thing an update changed, and where in the app to see it. */
data class Feature(val title: String, val body: String, val screen: Screen)

/**
 * What the update the guide belongs to changed, most useful first. Paired with
 * [com.rextechnologies.textwire.data.UpdateGuide.LATEST_GUIDE]: replace this list and raise
 * that number together, and only for an update a person would want walked through.
 */
val WHATS_NEW = listOf(
    Feature(
        "Settings for everything",
        "Texts per page with the cost of a page, how long to wait before asking for lost texts, a daily " +
            "limit, text size, keeping the screen on, and how long pages are kept.",
        Screen.SETTINGS,
    ),
    Feature(
        "Notified when a page arrives",
        "Close the app while a page is on its way; a notification says when it is ready and opens it.",
        Screen.SETTINGS,
    ),
    Feature(
        "Delete, undo and share",
        "Delete a page from Home or the reader and take it back with Undo. Share a page as plain text.",
        Screen.HOME,
    ),
    Feature(
        "A clearer diagnostics screen",
        "Whether SMS and notifications are allowed, how many replies are on their way, and a log you can clear.",
        Screen.DIAGNOSTICS,
    ),
)

/** The one-time guide to an update; "Show me" goes to the screen a feature lives on. */
@Composable
fun WhatsNewDialog(dismiss: () -> Unit, showMe: (Screen) -> Unit) {
    AlertDialog(
        modifier = Modifier.testTag("whats-new"),
        onDismissRequest = dismiss,
        title = { Text("What’s new in textwire") },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                WHATS_NEW.forEachIndexed { index, feature ->
                    Text(
                        feature.title,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        feature.body,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    TextButton(
                        onClick = { showMe(feature.screen) },
                        modifier = Modifier.testTag("show-me-$index"),
                    ) { Text("Show me") }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = dismiss, modifier = Modifier.testTag("whats-new-done")) { Text("Got it") }
        },
    )
}
