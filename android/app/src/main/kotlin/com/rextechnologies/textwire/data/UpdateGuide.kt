package com.rextechnologies.textwire.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/**
 * Whether the one-time guide to an update ([com.rextechnologies.textwire.ui.WHATS_NEW]) opens.
 *
 * The guide is numbered: [LATEST_GUIDE] rises only with an update worth walking someone
 * through, and the number last seen is kept beside the settings. A new install has nothing
 * stored at all and gets the first-run guide instead, so it is recorded as having seen the
 * current one. An install with settings but no number predates the guide: an update.
 */
class UpdateGuide(context: Context, private val latestGuide: Int = LATEST_GUIDE) {
    private val prefs: SharedPreferences = context.getSharedPreferences(PREFERENCES_FILE, Context.MODE_PRIVATE)

    /**
     * Whether to open the guide as the app starts. Ask before anything else writes a setting:
     * on a new install it records the current guide as seen, which is what makes it once only.
     */
    fun opensOnLaunch(): Boolean {
        if (prefs.getInt(SEEN, 0) >= latestGuide) return false
        if (prefs.all.isEmpty()) {
            markSeen()
            return false
        }
        return true
    }

    fun markSeen() {
        prefs.edit { putInt(SEEN, latestGuide) }
    }

    companion object {
        /** Raise by one together with a new [com.rextechnologies.textwire.ui.WHATS_NEW] (CONTRIBUTING.md). */
        const val LATEST_GUIDE = 1
        private const val SEEN = "update_guide_seen"
    }
}
