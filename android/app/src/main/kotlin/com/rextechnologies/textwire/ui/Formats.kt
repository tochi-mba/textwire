package com.rextechnologies.textwire.ui

import com.rextechnologies.textwire.Pending
import com.rextechnologies.textwire.core.CostMeter
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Kind
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt

// How things are worded on screen: pure functions, so every wording has a plain unit test.

private val CLOCK: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm:ss")
private val CLOCK_MINUTES: DateTimeFormatter = DateTimeFormatter.ofPattern("HH:mm")

/** A moment as the phone's local time of day, to the second: the diagnostics log's precision. */
internal fun clock(millis: Long): String = CLOCK.format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

/** A moment to the minute: when a page arrived, where seconds are noise. */
internal fun clockMinutes(millis: Long): String =
    CLOCK_MINUTES.format(Instant.ofEpochMilli(millis).atZone(ZoneId.systemDefault()))

/** A count of texts: `1 text`, `12 texts`. */
internal fun texts(count: Int): String = if (count == 1) "1 text" else "$count texts"

/** Looks like a web address rather than search words: has a dot or a scheme, and no spaces. */
internal fun looksLikeUrl(text: String): Boolean {
    val trimmed = text.trim()
    return ' ' !in trimmed && ('.' in trimmed || "://" in trimmed)
}

/** How far a reply in flight has got. */
internal fun progressLabel(pending: Pending): String {
    val progress = pending.total?.let { "${pending.received} of $it texts" } ?: "waiting for the first text"
    val resends = if (pending.resends > 0) ", asked again ${pending.resends}x" else ""
    return if (pending.gaveUp) "Stopped at $progress. Retry to ask again." else "$progress$resends"
}

/** Whether a request asks for another page or a link: `04 p 00 2`, `05 l12 00 3`. */
internal fun turnsThePage(request: String): Boolean = request.split(' ').getOrNull(1)?.firstOrNull() in setOf('p', 'l')

/** What kind of page it is, how many texts it took and when it came. */
internal fun pageMeta(page: StoredPage): String {
    val kind = when (page.kind) {
        Kind.SEARCH -> "Search results"
        Kind.HELP -> "Help"
        Kind.STATUS -> "Status"
        Kind.PAGE -> "Page ${page.page} of ${page.pages}"
    }
    return "$kind · ${texts(page.smsCount)} · ${clockMinutes(page.receivedAtMillis)}"
}

/** Words of article a text carries once compressed, measured on the held-out pages. */
private const val WORDS_PER_TEXT = 65

/** What a page of [frames] texts holds and costs: `12 texts · about 800 words · ~0.67 USD`. */
internal fun pageEstimate(frames: Int, price: Double, currency: String): String {
    val words = ((frames * WORDS_PER_TEXT) / 50.0).roundToInt().coerceAtLeast(1) * 50
    val cost = String.format(Locale.ROOT, "%.2f", frames * price)
    return "${texts(frames)} · about $words words · ~$cost $currency"
}

/** Home's summary of the day: what has arrived, and the limit when one is set. */
internal fun todayLine(meter: CostMeter, dailyLimit: Int): String {
    val arrived = if (meter.segments == 0) "nothing yet" else meter.describe()
    val limit = if (dailyLimit > 0) " · limit $dailyLimit a day" else ""
    return "Received today: $arrived$limit"
}

/** A request as the person meant it, for the card of a reply in flight. */
internal fun requestLabel(request: String): String {
    val words = request.split(' ')
    val tag = words.getOrNull(0)
    val verb = words.getOrNull(1)
    if (tag?.length != 2 || tag.any { !it.isDigit() && it !in 'a'..'z' } || verb?.matches(REQUEST_VERB) != true) {
        return request
    }
    val argument = { from: Int -> words.drop(from).joinToString(" ") }
    return when (verb.first()) {
        'g' -> "Opening ${argument(2)}"
        's' -> "Searching: ${argument(2)}"
        'p' -> "Getting page ${words.getOrNull(3) ?: "?"}"
        'l' -> "Following link ${words.getOrNull(3) ?: "?"}"
        'r' -> "Asking for lost texts"
        '?' -> "Checking the server"
        'h' -> "Asking for help"
        else -> request
    }
}

private val REQUEST_VERB = Regex("""(?:[gspl]\d*!?|r|\?|h)""")

/** A count of replies: `no replies`, `1 reply`, `3 replies`. */
internal fun replies(count: Int): String = when (count) {
    0 -> "no replies"
    1 -> "1 reply"
    else -> "$count replies"
}

/** A duration as a person says it: `30 s`, `1 min`, `5 min`. */
internal fun duration(millis: Long): String {
    val seconds = millis / 1000
    return if (seconds < 60) "$seconds s" else "${seconds / 60} min"
}

/** A count of resend rounds: `Never`, `1x`, `3x`. */
internal fun rounds(count: Int): String = if (count == 0) "Never" else "${count}x"

/** A daily limit: `Off` or the number of texts. */
internal fun limit(texts: Int): String = if (texts == 0) "Off" else "$texts"

/** A history length: `1 day`, `30 days`, `Always`. */
internal fun keep(days: Int): String = when (days) {
    0 -> "Always"
    1 -> "1 day"
    else -> "$days days"
}

/** A text size as a label: the four steps the reader offers. */
internal fun textSize(scale: Float): String = when {
    scale < 1f -> "Small"
    scale == 1f -> "Default"
    scale < 1.2f -> "Large"
    else -> "Largest"
}

private val CHIP = Regex("""\[\d+]""")

/** A page as text to share outside the app: the link numbers mean nothing there. */
internal fun shareableText(page: StoredPage): String = page.text.replace(CHIP, "").trim()
