package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.LogEntry
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val CLOCK: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")

internal fun clock(millis: Long): String = CLOCK.format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

private const val LOG_PREVIEW = 90

@Composable
fun DiagnosticsScreen(state: UiState, controller: Controller, permissionsGranted: Boolean) {
    LazyColumn(
        modifier = Modifier.testTag("diagnostics"),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    CheckRow(
                        "SMS permissions",
                        if (permissionsGranted) "granted" else "not granted",
                        permissionsGranted,
                    )
                    CheckRow(
                        "Server number",
                        state.settings.serverNumber.ifBlank { "not set" },
                        state.settings.serverNumber.isNotBlank(),
                    )
                    CheckRow("Dictionary", "v1, packaged", true)
                    CheckRow("Texts today", state.meter.describe(), true)
                }
            }
        }
        item {
            Text(
                "Send ? to the server. The answer is a status line with today's usage; the frame it arrives in " +
                    "is logged below, so you can see the route works end to end.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = controller::status, modifier = Modifier.padding(top = 8.dp).testTag("probe")) {
                Text("Send ?")
            }
        }
        item { Text("Recent texts", style = MaterialTheme.typography.titleMedium) }
        if (state.log.isEmpty()) {
            item {
                Text(
                    "No texts yet.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        items(state.log) { entry -> LogLine(entry) }
    }
}

@Composable
private fun CheckRow(label: String, value: String, ok: Boolean) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Text(
            value,
            style = MaterialTheme.typography.bodyMedium,
            color = if (ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
        )
    }
}

@Composable
private fun LogLine(entry: LogEntry) {
    val (arrow, color) = when (entry.direction) {
        LogEntry.Direction.IN -> "←" to MaterialTheme.colorScheme.primary
        LogEntry.Direction.OUT -> "→" to MaterialTheme.colorScheme.tertiary
        LogEntry.Direction.NOTE -> "•" to Color.Unspecified
    }
    Column(modifier = Modifier.padding(vertical = 2.dp)) {
        Text("${clock(entry.atMillis)} $arrow ${entry.note}", style = MaterialTheme.typography.bodySmall, color = color)
        Text(
            entry.text.take(LOG_PREVIEW),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
