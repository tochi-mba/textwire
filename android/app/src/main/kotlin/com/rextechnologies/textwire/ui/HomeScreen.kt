package com.rextechnologies.textwire.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.Pending
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Kind
import com.rextechnologies.textwire.protocol.encodeTag

/** Looks like a web address rather than search words: has a dot and no spaces. */
internal fun looksLikeUrl(text: String): Boolean {
    val trimmed = text.trim()
    return ' ' !in trimmed && ('.' in trimmed || "://" in trimmed)
}

@Composable
fun HomeScreen(state: UiState, controller: Controller) {
    var input by rememberSaveable { mutableStateOf("") }
    val submit = {
        if (input.isNotBlank()) {
            if (looksLikeUrl(input)) controller.get(input) else controller.search(input)
            input = ""
        }
    }
    LazyColumn(
        modifier = Modifier.testTag("home"),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        item {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("Search words, or a web address") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                keyboardActions = KeyboardActions(onGo = { submit() }),
                modifier = Modifier.fillMaxWidth().testTag("input"),
            )
            Row(modifier = Modifier.padding(top = 8.dp)) {
                Button(
                    onClick = {
                        if (input.isNotBlank()) {
                            controller.search(input)
                            input = ""
                        }
                    },
                    modifier = Modifier.testTag("search"),
                ) { Text("Search") }
                Spacer(Modifier.width(8.dp))
                FilledTonalButton(
                    onClick = {
                        if (input.isNotBlank()) {
                            controller.get(input)
                            input = ""
                        }
                    },
                    modifier = Modifier.testTag("open"),
                ) { Text("Open address") }
                Spacer(Modifier.width(8.dp))
                TextButton(onClick = controller::help) { Text("Help") }
            }
            Text(
                "Today: ${state.meter.describe()} received",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
        items(state.pending, key = { "pending-${it.tag}" }) { pending -> PendingCard(pending, controller) }
        if (state.pages.isEmpty() && state.pending.isEmpty()) {
            item { EmptyHome() }
        } else if (state.pages.isNotEmpty()) {
            item { Text("Pages", style = MaterialTheme.typography.titleMedium) }
        }
        items(state.pages, key = { it.tag }) { page -> PageCard(page) { controller.open(page.tag) } }
    }
}

@Composable
private fun EmptyHome() {
    Column(modifier = Modifier.fillMaxWidth().padding(top = 32.dp)) {
        Text("Nothing here yet", style = MaterialTheme.typography.titleMedium)
        Text(
            "Type a few words to search, or a web address to open. Each reply arrives as a handful of texts and " +
                "appears here as a page.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp),
        )
    }
}

@Composable
private fun PendingCard(pending: Pending, controller: Controller) {
    Card(modifier = Modifier.fillMaxWidth().testTag("pending-${encodeTag(pending.tag)}")) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(pending.request, style = MaterialTheme.typography.bodyMedium)
            val total = pending.total
            if (total == null) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp))
            } else {
                LinearProgressIndicator(
                    progress = { pending.received.toFloat() / total },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                )
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(progressLabel(pending), style = MaterialTheme.typography.bodySmall)
                if (pending.gaveUp) {
                    TextButton(
                        onClick = { controller.retry(pending.tag) },
                        modifier = Modifier.testTag("retry-${encodeTag(pending.tag)}"),
                    ) { Text("Retry") }
                }
            }
        }
    }
}

internal fun progressLabel(pending: Pending): String {
    val progress = pending.total?.let { "${pending.received} of $it texts" } ?: "waiting for the first text"
    val resends = if (pending.resends > 0) ", asked again ${pending.resends}x" else ""
    return if (pending.gaveUp) "Stopped at $progress. Retry to ask again." else "$progress$resends"
}

@Composable
private fun PageCard(page: StoredPage, open: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = open).testTag("page-${encodeTag(page.tag)}"),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(page.text.lineSequence().first().removePrefix("# "), style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            Text(
                pageMeta(page),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

internal fun pageMeta(page: StoredPage): String {
    val kind = when (page.kind) {
        Kind.SEARCH -> "Search results"
        Kind.HELP -> "Help"
        Kind.STATUS -> "Status"
        Kind.PAGE -> "Page ${page.page} of ${page.pages}"
    }
    return "$kind · ${page.smsCount} texts · ${clock(page.receivedAtMillis)}"
}
