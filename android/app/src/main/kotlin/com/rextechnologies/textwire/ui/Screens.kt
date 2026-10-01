package com.rextechnologies.textwire.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.core.parseDocument
import com.rextechnologies.textwire.data.LogEntry
import com.rextechnologies.textwire.protocol.encodeTag
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val CLOCK: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")

private fun clock(millis: Long): String = CLOCK.format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

@Composable
fun HomeScreen(state: UiState, controller: Controller) {
    var input by rememberSaveable { mutableStateOf("") }
    Column {
        OutlinedTextField(
            value = input,
            onValueChange = { input = it },
            label = { Text("Search words, or a web address") },
            modifier = Modifier.fillMaxWidth().testTag("input"),
        )
        Row(modifier = Modifier.padding(top = 8.dp)) {
            Button(onClick = {
                if (input.isNotBlank()) controller.search(input)
            }, modifier = Modifier.testTag("search")) {
                Text("Search")
            }
            Spacer(Modifier.width(8.dp))
            Button(onClick = { if (input.isNotBlank()) controller.get(input) }, modifier = Modifier.testTag("open")) {
                Text("Open")
            }
            Spacer(Modifier.width(8.dp))
            TextButton(onClick = controller::help) { Text("Help") }
        }
        Text(
            "Today: ${state.meter.describe()}",
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 8.dp),
        )
        PendingList(state, controller)
        Text("Pages", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
        LazyColumn {
            items(state.pages, key = { it.tag }) { page ->
                Column(
                    modifier = Modifier.fillMaxWidth().clickable { controller.open(page.tag) }.padding(vertical = 8.dp)
                        .testTag("page-${encodeTag(page.tag)}"),
                ) {
                    Text(
                        page.text.lineSequence().first().removePrefix("# "),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Text(
                        "${page.kind.name.lowercase()} ${page.page}/${page.pages}, ${page.smsCount} SMS, ${clock(
                            page.receivedAtMillis,
                        )}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun PendingList(state: UiState, controller: Controller) {
    for (pending in state.pending) {
        Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp).testTag("pending-${encodeTag(pending.tag)}")) {
            Column(modifier = Modifier.weight(1f)) {
                Text(pending.request, style = MaterialTheme.typography.bodyMedium)
                val progress = if (pending.total == null) "waiting" else "${pending.received}/${pending.total} SMS"
                val extra = if (pending.resends > 0) ", asked again ${pending.resends}x" else ""
                Text(
                    if (pending.gaveUp) "stopped at $progress" else "$progress$extra",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (pending.gaveUp) {
                TextButton(onClick = {
                    controller.retry(pending.tag)
                }, modifier = Modifier.testTag("retry-${encodeTag(pending.tag)}")) {
                    Text("Retry")
                }
            }
        }
    }
}

@Composable
fun ReaderScreen(state: UiState, controller: Controller) {
    val page = state.reading
    if (page == null) {
        Text("Nothing open yet. Search or open a page from Home.")
        return
    }
    Column {
        LazyColumn(modifier = Modifier.weight(1f).testTag("reader")) {
            items(parseDocument(page.text)) { block -> BlockView(block, controller::followLink) }
        }
        Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            TextButton(onClick = {
                controller.turnPage(-1)
            }, enabled = page.page > 1, modifier = Modifier.testTag("previous")) {
                Text("Previous")
            }
            Text(
                "page ${page.page}/${page.pages} - ${page.smsCount} SMS - reply ${encodeTag(page.tag)}",
                modifier = Modifier.weight(1f).padding(top = 12.dp),
                style = MaterialTheme.typography.bodySmall,
            )
            TextButton(onClick = {
                controller.turnPage(1)
            }, enabled = page.page < page.pages, modifier = Modifier.testTag("next")) {
                Text("Next")
            }
        }
    }
}

@Composable
fun DiagnosticsScreen(state: UiState, controller: Controller) {
    Column {
        Text("Server number: ${state.settings.serverNumber.ifBlank { "not set" }}")
        Text("Today: ${state.meter.describe()}")
        Text("Dictionary: v1 packaged")
        Row(modifier = Modifier.padding(vertical = 8.dp)) {
            Button(onClick = controller::status, modifier = Modifier.testTag("probe")) { Text("Send ?") }
        }
        Text("Recent SMS", style = MaterialTheme.typography.titleMedium)
        LazyColumn {
            items(state.log) { entry -> LogLine(entry) }
        }
    }
}

@Composable
private fun LogLine(entry: LogEntry) {
    val arrow = when (entry.direction) {
        LogEntry.Direction.IN -> "<-"
        LogEntry.Direction.OUT -> "->"
        LogEntry.Direction.NOTE -> "--"
    }
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text("${clock(entry.atMillis)} $arrow ${entry.note}", style = MaterialTheme.typography.bodySmall)
        Text(entry.text.take(LOG_PREVIEW), style = MaterialTheme.typography.bodySmall)
    }
}

private const val LOG_PREVIEW = 80

@Composable
fun SettingsScreen(state: UiState, controller: Controller) {
    var number by rememberSaveable(state.settings.serverNumber) { mutableStateOf(state.settings.serverNumber) }
    var frames by rememberSaveable(state.settings.pageFrames) { mutableStateOf(state.settings.pageFrames.toString()) }
    var price by rememberSaveable(state.settings.pricePerSegment) {
        mutableStateOf(state.settings.pricePerSegment.toString())
    }
    Column {
        OutlinedTextField(
            value = number,
            onValueChange = { number = it },
            label = { Text("Server number (+44...)") },
            modifier = Modifier.fillMaxWidth().testTag("server-number"),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = frames,
            onValueChange = { frames = it },
            label = { Text("SMS per page (1-40)") },
            modifier = Modifier.fillMaxWidth().testTag("page-frames"),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = price,
            onValueChange = { price = it },
            label = { Text("Price per SMS (${state.settings.currency})") },
            modifier = Modifier.fillMaxWidth().testTag("price"),
        )
        Button(
            onClick = {
                controller.saveSettings(
                    state.settings.copy(
                        serverNumber = number.trim(),
                        pageFrames = frames.toIntOrNull()?.coerceIn(1, MAX_PAGE_FRAMES) ?: state.settings.pageFrames,
                        pricePerSegment = price.toDoubleOrNull() ?: state.settings.pricePerSegment,
                    ),
                )
            },
            modifier = Modifier.padding(top = 8.dp).testTag("save"),
        ) { Text("Save") }
    }
}

private const val MAX_PAGE_FRAMES = 40
