package com.rextechnologies.textwire.data

import android.content.Context
import android.content.SharedPreferences
import com.rextechnologies.textwire.core.Conversation
import com.rextechnologies.textwire.core.CostMeter

/** What the person configures, and the little state that must survive a restart. */
data class SettingsSnapshot(
    val serverNumber: String = "",
    val pageFrames: Int = 12,
    val nakAfterMillis: Long = Conversation.DEFAULT_NAK_AFTER_MILLIS,
    val pricePerSegment: Double = CostMeter.DEFAULT_PRICE,
    val currency: String = "USD",
    val nextTag: Int = 0,
    val segmentsToday: Int = 0,
    val segmentsDay: String = "",
)

/** Settings behind an interface so the controller is tested without Android. */
interface SettingsStore {
    fun read(): SettingsSnapshot

    fun write(snapshot: SettingsSnapshot)
}

/** [SettingsStore] on SharedPreferences. */
class PreferencesSettings(context: Context) : SettingsStore {
    private val prefs: SharedPreferences = context.getSharedPreferences("textwire", Context.MODE_PRIVATE)

    override fun read(): SettingsSnapshot {
        val defaults = SettingsSnapshot()
        return SettingsSnapshot(
            serverNumber = prefs.getString("server_number", defaults.serverNumber)!!,
            pageFrames = prefs.getInt("page_frames", defaults.pageFrames),
            nakAfterMillis = prefs.getLong("nak_after_millis", defaults.nakAfterMillis),
            pricePerSegment = prefs.getString("price", null)?.toDoubleOrNull() ?: defaults.pricePerSegment,
            currency = prefs.getString("currency", defaults.currency)!!,
            nextTag = prefs.getInt("next_tag", defaults.nextTag),
            segmentsToday = prefs.getInt("segments_today", defaults.segmentsToday),
            segmentsDay = prefs.getString("segments_day", defaults.segmentsDay)!!,
        )
    }

    override fun write(snapshot: SettingsSnapshot) {
        prefs.edit()
            .putString("server_number", snapshot.serverNumber)
            .putInt("page_frames", snapshot.pageFrames)
            .putLong("nak_after_millis", snapshot.nakAfterMillis)
            .putString("price", snapshot.pricePerSegment.toString())
            .putString("currency", snapshot.currency)
            .putInt("next_tag", snapshot.nextTag)
            .putInt("segments_today", snapshot.segmentsToday)
            .putString("segments_day", snapshot.segmentsDay)
            .apply()
    }
}
