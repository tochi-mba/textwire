package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.SettingsSnapshot

private const val MAX_PAGE_FRAMES = 40
private val E164 = Regex("""\+[1-9]\d{6,14}""")

/** What is wrong with a settings form, field by field; empty when it can be saved. */
internal fun settingsProblems(number: String, frames: String, price: String): Map<String, String> {
    val problems = mutableMapOf<String, String>()
    if (!E164.matches(number.trim())) problems["number"] = "A number like +447700900000"
    val count = frames.trim().toIntOrNull()
    if (count == null || count !in 1..MAX_PAGE_FRAMES) problems["frames"] = "1 to $MAX_PAGE_FRAMES"
    val cost = price.trim().toDoubleOrNull()
    if (cost == null || cost < 0) problems["price"] = "A price per text, such as 0.056"
    return problems
}

@Composable
fun SettingsScreen(state: UiState, controller: Controller) {
    val saved = state.settings
    var number by rememberSaveable(saved.serverNumber) { mutableStateOf(saved.serverNumber) }
    var frames by rememberSaveable(saved.pageFrames) { mutableStateOf(saved.pageFrames.toString()) }
    var price by rememberSaveable(saved.pricePerSegment) { mutableStateOf(saved.pricePerSegment.toString()) }
    val problems = settingsProblems(number, frames, price)
    LazyColumn(
        modifier = Modifier.testTag("settings"),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        if (saved.serverNumber.isBlank()) {
            item { FirstRunCard() }
        }
        item {
            OutlinedTextField(
                value = number,
                onValueChange = { number = it },
                label = { Text("Server number") },
                supportingText = {
                    Text(problems["number"] ?: "The textwire server's phone number, as it appears in Messages.")
                },
                isError = "number" in problems,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth().testTag("server-number"),
            )
        }
        item {
            OutlinedTextField(
                value = frames,
                onValueChange = { frames = it },
                label = { Text("Texts per page") },
                supportingText = { Text(problems["frames"] ?: "12 is about 800 words. Fewer texts, more pages.") },
                isError = "frames" in problems,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth().testTag("page-frames"),
            )
        }
        item {
            OutlinedTextField(
                value = price,
                onValueChange = { price = it },
                label = { Text("Price per text (${saved.currency})") },
                supportingText = {
                    Text(problems["price"] ?: "Only for the cost estimate. Twilio UK was 0.056 USD in 2026.")
                },
                isError = "price" in problems,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth().testTag("price"),
            )
        }
        item {
            Button(
                onClick = {
                    controller.saveSettings(
                        saved.copy(
                            serverNumber = number.trim(),
                            pageFrames = frames.trim().toInt(),
                            pricePerSegment = price.trim().toDouble(),
                        ),
                    )
                },
                enabled = problems.isEmpty(),
                modifier = Modifier.testTag("save"),
            ) { Text("Save") }
        }
        item { AboutCard(saved) }
    }
}

@Composable
private fun FirstRunCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Welcome to textwire", style = MaterialTheme.typography.titleMedium)
            Text("1. Enter the server's phone number below and save.", style = MaterialTheme.typography.bodyMedium)
            Text("2. Grant the SMS permissions when asked.", style = MaterialTheme.typography.bodyMedium)
            Text(
                "3. In Messages, mute that number: its texts are pages for this app, not for reading there.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text("4. Go to Home and search for something.", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun AboutCard(settings: SettingsSnapshot) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("About", style = MaterialTheme.typography.titleMedium)
            Text("textwire: the web over SMS. A REX Technologies product.", style = MaterialTheme.typography.bodyMedium)
            Text(
                "Every page costs the server about ${settings.pricePerSegment} ${settings.currency} per text. " +
                    "Your own texts ride on your plan.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
