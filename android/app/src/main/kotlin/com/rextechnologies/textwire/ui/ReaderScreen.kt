package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.core.parseDocument
import com.rextechnologies.textwire.protocol.encodeTag

@Composable
fun ReaderScreen(state: UiState, controller: Controller) {
    val page = state.reading
    if (page == null) {
        Column(modifier = Modifier.fillMaxWidth().padding(top = 32.dp)) {
            Text("Nothing open yet", style = MaterialTheme.typography.titleMedium)
            Text(
                "Search or open a page from Home. It shows here when every text has arrived.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }
    val awaiting = state.pending.any { it.request.contains(" p ") || it.request.contains(" l ") }
    Column {
        LazyColumn(modifier = Modifier.weight(1f).testTag("reader"), contentPadding = PaddingValues(vertical = 12.dp)) {
            items(parseDocument(page.text)) { block -> BlockView(block, controller::followLink) }
            item {
                Text(
                    "Tap a number in brackets to follow that link. ${page.smsCount} texts, reply ${encodeTag(
                        page.tag,
                    )}.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilledTonalIconButton(
                onClick = { controller.turnPage(-1) },
                enabled = page.page > 1 && !awaiting,
                modifier = Modifier.testTag("previous"),
            ) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Previous page") }
            Text(
                if (awaiting) "Asking for the next page…" else "Page ${page.page} of ${page.pages}",
                style = MaterialTheme.typography.labelLarge,
            )
            FilledTonalIconButton(
                onClick = { controller.turnPage(1) },
                enabled = page.page < page.pages && !awaiting,
                modifier = Modifier.testTag("next"),
            ) { Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "Next page") }
        }
    }
}
