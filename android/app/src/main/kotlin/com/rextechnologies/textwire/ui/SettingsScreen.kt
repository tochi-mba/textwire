package com.rextechnologies.textwire.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rextechnologies.textwire.Controller
import com.rextechnologies.textwire.UiState
import com.rextechnologies.textwire.data.SettingsChoices
import com.rextechnologies.textwire.data.SettingsSnapshot
import kotlin.math.roundToInt

private val E164 = Regex("""\+[1-9]\d{6,14}""")
private val CURRENCY = Regex("""[A-Z]{3}""")

/** Why a server number cannot be used, or null when it can. */
internal fun numberProblem(number: String): String? =
    if (E164.matches(number.trim())) null else "A number like +447700900000, with the country code"

/** Why a price cannot be used, or null when it can. */
internal fun priceProblem(price: String): String? {
    val value = price.trim().toDoubleOrNull()
    return if (value == null || value < 0 || !value.isFinite()) "A price per text, such as 0.056" else null
}

/** Why a currency cannot be used, or null when it can. */
internal fun currencyProblem(currency: String): String? =
    if (CURRENCY.matches(currency.trim())) null else "Three letters, such as GBP"

/** What the confirmation dialog is asking about. */
private enum class Confirm { HISTORY, RESET }

/**
 * Every choice the app offers, grouped by what it changes. A change applies at once; a typed
 * value applies as soon as it is valid, and says what is wrong until then.
 */
@Composable
fun SettingsScreen(
    state: UiState,
    controller: Controller,
    notificationsAllowed: Boolean,
    requestPermissions: () -> Unit,
    showUpdateGuide: () -> Unit,
) {
    val saved = state.settings
    val update = controller::updateSettings
    var confirm by rememberSaveable { mutableStateOf<Confirm?>(null) }
    LazyColumn(
        modifier = Modifier.testTag("settings"),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(vertical = 12.dp),
    ) {
        if (saved.serverNumber.isBlank()) item { FirstRunCard() }
        item { Section("Server") }
        item { NumberField(saved, state.settingsGeneration, update) }

        item { Section("Pages") }
        item { PageSize(saved, update) }
        item {
            SwitchRow(
                "Open pages as they arrive",
                "Otherwise a notice offers to open them, and you stay where you are.",
                saved.openOnArrival,
                "open-on-arrival",
            ) { on -> update { it.copy(openOnArrival = on) } }
        }

        item { Section("Lost texts") }
        item {
            Choices(
                "Ask again after",
                "This long without a new text means some went missing.",
                SettingsChoices.NAK_AFTER_MILLIS,
                saved.nakAfterMillis,
                ::duration,
                "nak-after",
            ) { millis -> update { it.copy(nakAfterMillis = millis) } }
        }
        item {
            Choices(
                "Ask again up to",
                "Then the reply stops, with a Retry button.",
                SettingsChoices.RESEND_ROUNDS,
                saved.resendRounds,
                ::rounds,
                "resend-rounds",
            ) { count -> update { it.copy(resendRounds = count) } }
        }

        item { Section("Cost") }
        item { PriceFields(saved, state.settingsGeneration, update) }
        item {
            Choices(
                "Daily limit",
                "No new requests once this many texts have arrived today. Replies on their way still finish.",
                SettingsChoices.DAILY_LIMITS,
                saved.dailyLimit,
                ::limit,
                "daily-limit",
            ) { texts -> update { it.copy(dailyLimit = texts) } }
        }

        item { Section("Reading") }
        item { TextSize(saved, update) }
        item {
            SwitchRow(
                "Keep the screen on while reading",
                null,
                saved.keepScreenOn,
                "keep-screen-on",
            ) { on -> update { it.copy(keepScreenOn = on) } }
        }

        item { Section("Notifications") }
        item {
            SwitchRow(
                "Tell me when a page arrives",
                "Only while textwire is not on screen. Tapping it opens the page.",
                saved.notifyOnArrival,
                "notify",
            ) { on -> update { it.copy(notifyOnArrival = on) } }
        }
        if (saved.notifyOnArrival && !notificationsAllowed) {
            item { AllowNotifications(requestPermissions) }
        }

        item { Section("History") }
        item {
            Choices(
                "Keep pages for",
                "Older pages are deleted when the app starts and when a page arrives.",
                SettingsChoices.HISTORY_DAYS,
                saved.historyDays,
                ::keep,
                "history-days",
            ) { days -> update { it.copy(historyDays = days) } }
        }
        item {
            OutlinedButton(onClick = { confirm = Confirm.HISTORY }, modifier = Modifier.testTag("clear-history")) {
                Text("Clear history")
            }
        }

        item { Section("Reset") }
        item {
            OutlinedButton(onClick = { confirm = Confirm.RESET }, modifier = Modifier.testTag("reset-settings")) {
                Text("Reset settings")
            }
        }
        item { AboutCard(saved, showUpdateGuide) }
    }
    confirm?.let { asked ->
        ConfirmDialog(asked, dismiss = { confirm = null }) {
            if (asked == Confirm.HISTORY) controller.clearHistory() else controller.resetSettings()
            confirm = null
        }
    }
}

@Composable
private fun Section(title: String) {
    Text(
        title.uppercase(),
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 16.dp).semantics { heading() }.testTag("section-$title"),
    )
}

@Composable
private fun NumberField(
    saved: SettingsSnapshot,
    generation: Int,
    update: ((SettingsSnapshot) -> SettingsSnapshot) -> Unit,
) {
    var number by rememberSaveable(generation) { mutableStateOf(saved.serverNumber) }
    val problem = numberProblem(number)
    OutlinedTextField(
        value = number,
        onValueChange = { typed ->
            number = typed
            if (numberProblem(typed) == null) update { it.copy(serverNumber = typed.trim()) }
        },
        label = { Text("Server number") },
        supportingText = { Text(problem ?: "The textwire server's phone number, as it appears in Messages.") },
        isError = problem != null,
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
        modifier = Modifier.fillMaxWidth().testTag("server-number"),
    )
}

@Composable
private fun PageSize(saved: SettingsSnapshot, update: ((SettingsSnapshot) -> SettingsSnapshot) -> Unit) {
    var frames by rememberSaveable(saved.pageFrames) { mutableIntStateOf(saved.pageFrames) }
    Column {
        Text("Texts per page", style = MaterialTheme.typography.bodyLarge)
        Text(
            pageEstimate(frames, saved.pricePerSegment, saved.currency),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.testTag("page-estimate"),
        )
        Slider(
            value = frames.toFloat(),
            onValueChange = { frames = it.roundToInt() },
            onValueChangeFinished = { update { it.copy(pageFrames = frames) } },
            valueRange = SettingsChoices.PAGE_FRAMES.first.toFloat()..SettingsChoices.PAGE_FRAMES.last.toFloat(),
            modifier = Modifier.fillMaxWidth().testTag("page-frames"),
        )
        Text(
            "Fewer texts make a page cheaper and quicker; more make fewer pages to turn.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PriceFields(
    saved: SettingsSnapshot,
    generation: Int,
    update: ((SettingsSnapshot) -> SettingsSnapshot) -> Unit,
) {
    var price by rememberSaveable(generation) { mutableStateOf(saved.pricePerSegment.toString()) }
    var currency by rememberSaveable(generation) { mutableStateOf(saved.currency) }
    val priceError = priceProblem(price)
    val currencyError = currencyProblem(currency)
    Row(verticalAlignment = Alignment.Top) {
        OutlinedTextField(
            value = price,
            onValueChange = { typed ->
                price = typed
                if (priceProblem(typed) == null) update { it.copy(pricePerSegment = typed.trim().toDouble()) }
            },
            label = { Text("Price per text") },
            supportingText = { Text(priceError ?: "What the server pays; only for the estimates.") },
            isError = priceError != null,
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            modifier = Modifier.weight(1f).testTag("price"),
        )
        OutlinedTextField(
            value = currency,
            onValueChange = { typed ->
                currency = typed.uppercase()
                if (currencyProblem(currency) == null) update { it.copy(currency = currency.trim()) }
            },
            label = { Text("Currency") },
            supportingText = currencyError?.let { { Text(it) } },
            isError = currencyError != null,
            singleLine = true,
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
            modifier = Modifier.padding(start = 8.dp).width(112.dp).testTag("currency"),
        )
    }
}

@Composable
private fun TextSize(saved: SettingsSnapshot, update: ((SettingsSnapshot) -> SettingsSnapshot) -> Unit) {
    Choices("Text size", null, SettingsChoices.TEXT_SCALES, saved.textScale, ::textSize, "text-size") { scale ->
        update { it.copy(textScale = scale) }
    }
    Text(
        "A page reads like this.",
        style = MaterialTheme.typography.bodyLarge.copy(fontSize = 17.sp * saved.textScale),
        modifier = Modifier.padding(top = 8.dp).testTag("text-preview"),
    )
}

/** A row of mutually exclusive choices with a title and an optional explanation. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> Choices(
    title: String,
    help: String?,
    options: List<T>,
    selected: T,
    label: (T) -> String,
    tag: String,
    choose: (T) -> Unit,
) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(title, style = MaterialTheme.typography.bodyLarge)
        if (help != null) {
            Text(help, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
            options.forEachIndexed { index, option ->
                SegmentedButton(
                    selected = option == selected,
                    onClick = { choose(option) },
                    shape = SegmentedButtonDefaults.itemShape(index, options.size),
                    modifier = Modifier.testTag("$tag-$index"),
                ) { Text(label(option), maxLines = 1) }
            }
        }
    }
}

/** A setting that is on or off; the whole row is the touch target. */
@Composable
private fun SwitchRow(title: String, help: String?, on: Boolean, tag: String, change: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
            .semantics { stateDescription = if (on) "On" else "Off" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f).padding(end = 12.dp)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            if (help != null) {
                Text(
                    help,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Switch(checked = on, onCheckedChange = change, modifier = Modifier.testTag(tag))
    }
}

@Composable
private fun AllowNotifications(requestPermissions: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            "Android is not letting textwire post notifications.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.weight(1f),
        )
        TextButton(onClick = requestPermissions, modifier = Modifier.testTag("allow-notifications")) {
            Text("Allow")
        }
    }
}

@Composable
private fun ConfirmDialog(asked: Confirm, dismiss: () -> Unit, confirm: () -> Unit) {
    val (title, text, action) = when (asked) {
        Confirm.HISTORY -> Triple(
            "Clear history?",
            "Every page is deleted from this phone. Replies still on their way keep coming.",
            "Clear",
        )
        Confirm.RESET -> Triple(
            "Reset settings?",
            "Every choice goes back to its default. The server number is kept.",
            "Reset",
        )
    }
    AlertDialog(
        onDismissRequest = dismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = { TextButton(onClick = confirm, modifier = Modifier.testTag("confirm")) { Text(action) } },
        dismissButton = { TextButton(onClick = dismiss, modifier = Modifier.testTag("cancel")) { Text("Cancel") } },
    )
}

@Composable
private fun FirstRunCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Welcome to textwire", style = MaterialTheme.typography.titleMedium)
            Text("1. Enter the server's phone number below.", style = MaterialTheme.typography.bodyMedium)
            Text("2. Allow the SMS permissions when asked.", style = MaterialTheme.typography.bodyMedium)
            Text(
                "3. In Messages, mute that number: its texts are pages for this app, not for reading there.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text("4. Go to Home and search for something.", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun AboutCard(settings: SettingsSnapshot, showUpdateGuide: () -> Unit) {
    val context = LocalContext.current
    val version = context.packageManager.getPackageInfo(context.packageName, 0).versionName
    Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("About", style = MaterialTheme.typography.titleMedium)
            Text(
                "textwire $version: the web over SMS. A REX Technologies product.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                "Every page costs the server about ${settings.pricePerSegment} ${settings.currency} per text. " +
                    "Your own texts ride on your plan.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(onClick = showUpdateGuide, modifier = Modifier.testTag("show-whats-new")) {
                Text("What’s new")
            }
        }
    }
}
