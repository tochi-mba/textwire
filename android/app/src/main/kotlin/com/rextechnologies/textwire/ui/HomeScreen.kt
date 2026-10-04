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
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.Pending
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.encodeTag

@Composable
fun HomeScreen(state: UiState, controller: Controller) {
    var input by rememberSaveable { mutableStateOf("") }
    // Each button does what it says; Go on the keyboard guesses from what was typed.
    val send = { action: (String) -> Unit ->
        if (input.isNotBlank()) {
            action(input)
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
                keyboardActions = KeyboardActions(
                    onGo = { send { if (looksLikeUrl(it)) controller.get(it) else controller.search(it) } },
                ),
                modifier = Modifier.fillMaxWidth().testTag("input"),
            )
            Row(modifier = Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = { send(controller::search) }, modifier = Modifier.testTag("search")) {
                    Text("Search")
                }
                Spacer(Modifier.width(8.dp))
                FilledTonalButton(onClick = { send(controller::get) }, modifier = Modifier.testTag("open")) {
                    Text("Open address")
                }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = controller::help, modifier = Modifier.testTag("help")) { Text("Help") }
            }
            Text(
                todayLine(state.meter, state.settings.dailyLimit),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp).testTag("today"),
            )
        }
        items(state.pending, key = { "pending-${it.tag}" }) { pending -> PendingCard(pending, controller) }
        if (state.pages.isEmpty() && state.pending.isEmpty()) {
            item { EmptyHome() }
        } else if (state.pages.isNotEmpty()) {
            item { Text("Pages", style = MaterialTheme.typography.titleMedium) }
        }
        items(state.pages, key = { it.tag }) { page ->
            PageCard(page, open = { controller.open(page.tag) }, delete = { controller.deletePage(page.tag) })
        }
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
    Card(
        modifier = Modifier.fillMaxWidth().testTag("pending-${encodeTag(pending.tag)}"),
        colors = cardColors(),
    ) {
        // Less padding below when a row of buttons ends the card: they carry their own.
        Column(
            modifier = Modifier.padding(
                start = 16.dp,
                end = 16.dp,
                top = 16.dp,
                bottom = if (pending.gaveUp) 4.dp else 16.dp,
            ),
        ) {
            Text(requestLabel(pending.request), style = MaterialTheme.typography.bodyMedium)
            val total = pending.total
            if (total == null) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp))
            } else {
                LinearProgressIndicator(
                    progress = { pending.received.toFloat() / total },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                )
            }
            Text(progressLabel(pending), style = MaterialTheme.typography.bodySmall)
            if (pending.gaveUp) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(
                        onClick = { controller.dismiss(pending.tag) },
                        modifier = Modifier.testTag("dismiss-${encodeTag(pending.tag)}"),
                    ) { Text("Dismiss") }
                    TextButton(
                        onClick = { controller.retry(pending.tag) },
                        modifier = Modifier.testTag("retry-${encodeTag(pending.tag)}"),
                    ) { Text("Retry") }
                }
            }
        }
    }
}

/** Cards on Home: raised from the background, their text at full strength. */
@Composable
private fun cardColors() = CardDefaults.cardColors(
    containerColor = MaterialTheme.colorScheme.surfaceVariant,
    contentColor = MaterialTheme.colorScheme.onSurface,
)

@Composable
private fun PageCard(page: StoredPage, open: () -> Unit, delete: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = open).testTag("page-${encodeTag(page.tag)}"),
        colors = cardColors(),
    ) {
        Row(modifier = Modifier.padding(start = 16.dp, top = 12.dp, bottom = 12.dp, end = 4.dp)) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    page.title,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    pageMeta(page),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = delete, modifier = Modifier.testTag("delete-${encodeTag(page.tag)}")) {
                Icon(
                    Icons.Filled.Delete,
                    contentDescription = "Delete ${page.title}",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
