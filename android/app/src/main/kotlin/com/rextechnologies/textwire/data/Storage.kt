package com.rextechnologies.textwire.data

import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind

/** A request the app sent, by its tag. */
data class SentRequest(val tag: Int, val text: String, val sentAtMillis: Long, val resends: Int = 0)

/** A complete page the app received and decoded. */
data class StoredPage(
    val tag: Int,
    val kind: Kind,
    val page: Int,
    val pages: Int,
    val text: String,
    val smsCount: Int,
    val receivedAtMillis: Long,
)

/** One line of the diagnostics log: an SMS in or out, or a note. */
data class LogEntry(val atMillis: Long, val direction: Direction, val text: String, val note: String) {
    enum class Direction { IN, OUT, NOTE }
}

/**
 * What the app keeps on disk, behind an interface so the controller is tested without Android.
 *
 * Everything is keyed by tag. Frames are kept until their page is complete, so a reply that
 * arrives while the app is dead is still assembled when it wakes.
 */
interface Storage {
    fun saveRequest(request: SentRequest)

    fun request(tag: Int): SentRequest?

    fun openRequests(): List<SentRequest>

    fun saveFrame(frame: Frame, atMillis: Long)

    fun frames(tag: Int): List<Frame>

    fun savePage(page: StoredPage)

    fun page(tag: Int): StoredPage?

    fun pages(): List<StoredPage>

    fun forget(tag: Int)

    fun log(entry: LogEntry)

    fun recentLog(limit: Int): List<LogEntry>

    fun smsReceived(): Int
}
