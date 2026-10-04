package com.rextechnologies.textwire.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import com.rextechnologies.textwire.core.Conversation
import com.rextechnologies.textwire.core.CostMeter

/**
 * What the person configures, and the little state that must survive a restart.
 *
 * Every choice has a default that works without touching Settings; the ranges a person may
 * pick from are in [SettingsChoices], so the screen and the tests agree on them.
 */
data class SettingsSnapshot(
    /** The server's phone number, E.164. Nothing is sent until it is set. */
    val serverNumber: String = "",
    /** SMS per page the server is asked for; every page and link request carries it. */
    val pageFrames: Int = 12,
    /** Quiet time after the last text of a reply before the missing ones are asked for again. */
    val nakAfterMillis: Long = Conversation.DEFAULT_NAK_AFTER_MILLIS,
    /** How many times missing texts are asked for before the reply is given up; 0 is never. */
    val resendRounds: Int = Conversation.DEFAULT_NAK_ROUNDS,
    /** The server's price per SMS, only for the estimate. */
    val pricePerSegment: Double = CostMeter.DEFAULT_PRICE,
    val currency: String = "USD",
    /** Texts a day after which the app refuses new requests; 0 is no limit. */
    val dailyLimit: Int = 0,
    /** Show a page in the reader the moment its last text arrives. */
    val openOnArrival: Boolean = true,
    /** Post a notification when a page arrives while the app is not on screen. */
    val notifyOnArrival: Boolean = true,
    /** The reader's text size, as a multiple of the phone's own. */
    val textScale: Float = 1.0f,
    /** Keep the screen awake while the reader is showing. */
    val keepScreenOn: Boolean = false,
    /** Days a page is kept; 0 keeps pages until they are deleted. */
    val historyDays: Int = 30,
    // State, not choices -------------------------------------------------------------------
    val nextTag: Int = 0,
    val segmentsToday: Int = 0,
    val segmentsDay: String = "",
) {
    /** The same snapshot with every choice back at its default; the number and counters stay. */
    fun reset(): SettingsSnapshot = SettingsSnapshot(
        serverNumber = serverNumber,
        nextTag = nextTag,
        segmentsToday = segmentsToday,
        segmentsDay = segmentsDay,
    )
}

/** The values each choice offers on the Settings screen. */
object SettingsChoices {
    val PAGE_FRAMES = 1..40
    val NAK_AFTER_MILLIS = listOf(30_000L, 60_000L, 120_000L, 300_000L)
    val RESEND_ROUNDS = listOf(0, 1, 2, 3, 5)
    val DAILY_LIMITS = listOf(0, 50, 100, 200, 500)
    val TEXT_SCALES = listOf(0.85f, 1.0f, 1.15f, 1.3f)
    val HISTORY_DAYS = listOf(1, 7, 30, 0)
}

/** The preferences file the settings and the update guide share. */
const val PREFERENCES_FILE = "textwire"

/** Settings behind an interface so the controller is tested without Android. */
interface SettingsStore {
    fun read(): SettingsSnapshot

    fun write(snapshot: SettingsSnapshot)
}

/** [SettingsStore] on SharedPreferences. */
class PreferencesSettings(context: Context) : SettingsStore {
    private val prefs: SharedPreferences = context.getSharedPreferences(PREFERENCES_FILE, Context.MODE_PRIVATE)

    override fun read(): SettingsSnapshot {
        val defaults = SettingsSnapshot()
        return SettingsSnapshot(
            serverNumber = prefs.getString("server_number", defaults.serverNumber)!!,
            pageFrames = prefs.getInt("page_frames", defaults.pageFrames),
            nakAfterMillis = prefs.getLong("nak_after_millis", defaults.nakAfterMillis),
            resendRounds = prefs.getInt("resend_rounds", defaults.resendRounds),
            pricePerSegment = prefs.getString("price", null)?.toDoubleOrNull() ?: defaults.pricePerSegment,
            currency = prefs.getString("currency", defaults.currency)!!,
            dailyLimit = prefs.getInt("daily_limit", defaults.dailyLimit),
            openOnArrival = prefs.getBoolean("open_on_arrival", defaults.openOnArrival),
            notifyOnArrival = prefs.getBoolean("notify_on_arrival", defaults.notifyOnArrival),
            textScale = prefs.getFloat("text_scale", defaults.textScale),
            keepScreenOn = prefs.getBoolean("keep_screen_on", defaults.keepScreenOn),
            historyDays = prefs.getInt("history_days", defaults.historyDays),
            nextTag = prefs.getInt("next_tag", defaults.nextTag),
            segmentsToday = prefs.getInt("segments_today", defaults.segmentsToday),
            segmentsDay = prefs.getString("segments_day", defaults.segmentsDay)!!,
        )
    }

    override fun write(snapshot: SettingsSnapshot) {
        prefs.edit {
            putString("server_number", snapshot.serverNumber)
            putInt("page_frames", snapshot.pageFrames)
            putLong("nak_after_millis", snapshot.nakAfterMillis)
            putInt("resend_rounds", snapshot.resendRounds)
            putString("price", snapshot.pricePerSegment.toString())
            putString("currency", snapshot.currency)
            putInt("daily_limit", snapshot.dailyLimit)
            putBoolean("open_on_arrival", snapshot.openOnArrival)
            putBoolean("notify_on_arrival", snapshot.notifyOnArrival)
            putFloat("text_scale", snapshot.textScale)
            putBoolean("keep_screen_on", snapshot.keepScreenOn)
            putInt("history_days", snapshot.historyDays)
            putInt("next_tag", snapshot.nextTag)
            putInt("segments_today", snapshot.segmentsToday)
            putString("segments_day", snapshot.segmentsDay)
        }
    }
}
