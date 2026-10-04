package com.rextechnologies.textwire

import com.rextechnologies.textwire.core.Conversation
import com.rextechnologies.textwire.core.CostMeter
import com.rextechnologies.textwire.core.Decision
import com.rextechnologies.textwire.core.Phase
import com.rextechnologies.textwire.core.TagAllocator
import com.rextechnologies.textwire.data.LogEntry
import com.rextechnologies.textwire.data.SentRequest
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.data.SettingsStore
import com.rextechnologies.textwire.data.Storage
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.notify.Notifier
import com.rextechnologies.textwire.protocol.Envelope
import com.rextechnologies.textwire.protocol.EnvelopeException
import com.rextechnologies.textwire.protocol.FrameException
import com.rextechnologies.textwire.protocol.Request
import com.rextechnologies.textwire.protocol.Verb
import com.rextechnologies.textwire.protocol.ZstdDictionary
import com.rextechnologies.textwire.protocol.decodeFrame
import com.rextechnologies.textwire.protocol.encodeTag
import com.rextechnologies.textwire.protocol.formatRequest
import com.rextechnologies.textwire.protocol.unpackEnvelope
import com.rextechnologies.textwire.sms.SmsGateway
import com.rextechnologies.textwire.sms.sameNumber
import com.rextechnologies.textwire.work.NakScheduler
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import java.time.Instant
import java.time.ZoneOffset

/** Which screen is showing. */
enum class Screen { HOME, READER, DIAGNOSTICS, SETTINGS }

/** A reply still arriving. */
data class Pending(
    val tag: Int,
    val request: String,
    val received: Int,
    val total: Int?,
    val resends: Int,
    val gaveUp: Boolean,
)

/** Something the app tells the person, with at most one thing they can do about it. */
data class Notice(val text: String, val action: NoticeAction? = null)

/** What the button on a [Notice] does. */
sealed interface NoticeAction {
    val label: String

    /** Open a page that arrived while another screen was showing. */
    data class Read(val tag: Int) : NoticeAction {
        override val label: String get() = "Read"
    }

    /** Put back a page that was just deleted. */
    data class Restore(val page: StoredPage) : NoticeAction {
        override val label: String get() = "Undo"
    }
}

/** Everything the UI draws. */
data class UiState(
    val screen: Screen = Screen.HOME,
    val settings: SettingsSnapshot = SettingsSnapshot(),
    val pages: List<StoredPage> = emptyList(),
    val reading: StoredPage? = null,
    val pending: List<Pending> = emptyList(),
    val meter: CostMeter = CostMeter(),
    val log: List<LogEntry> = emptyList(),
    val notice: Notice? = null,
    /** Bumped when settings change other than by typing, so text fields reload their values. */
    val settingsGeneration: Int = 0,
)

/**
 * The app's brain, hand-wired (no framework): requests out, frames in, pages to the screen.
 *
 * Not a ViewModel: it lives in the Application so the SMS receiver and the resend worker
 * reach the same instance the activity draws. Every method is synchronous and takes the
 * current time from [now], so tests drive it with a fake clock.
 */
class Controller(
    private val storage: Storage,
    private val settings: SettingsStore,
    private val gateway: SmsGateway,
    private val scheduler: NakScheduler,
    private val dictionary: ZstdDictionary,
    private val notifier: Notifier,
    private val now: () -> Long = System::currentTimeMillis,
) {
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    private val conversations = HashMap<Int, Conversation>()
    private val allocator: TagAllocator

    /** Whether the activity is on screen; a page that arrives otherwise is notified. */
    private var visible = false

    init {
        val snapshot = settings.read()
        allocator = TagAllocator(snapshot.nextTag)
        purge(snapshot, now())
        for (request in storage.openRequests()) {
            val conversation = conversation(request.tag, request.sentAtMillis, snapshot)
            for (frame in storage.frames(request.tag)) conversation.onFrame(frame, request.sentAtMillis)
            conversations[request.tag] = conversation
        }
        refresh(snapshot)
    }

    // Navigation -------------------------------------------------------------------------------

    fun show(screen: Screen) = _state.update { it.copy(screen = screen, notice = null) }

    fun open(tag: Int) {
        val page = storage.page(tag) ?: return
        _state.update { it.copy(screen = Screen.READER, reading = page, notice = null) }
    }

    /** The activity came on screen or left it. */
    fun setVisible(on: Boolean) {
        visible = on
    }

    fun dismissNotice() = _state.update { it.copy(notice = null) }

    /** The notice's button was pressed: do what it offers, or just close a notice that offers nothing. */
    fun act() {
        when (val action = _state.value.notice?.action) {
            is NoticeAction.Read -> open(action.tag)
            is NoticeAction.Restore -> {
                storage.savePage(action.page)
                _state.update { it.copy(notice = null) }
                refresh(settings.read())
            }
            else -> dismissNotice()
        }
    }

    // Settings and history ---------------------------------------------------------------------

    /** Replaces every choice; the tag counter and today's count are kept as they are. */
    fun saveSettings(snapshot: SettingsSnapshot) {
        val current = settings.read()
        val next = snapshot.copy(
            nextTag = allocator.next,
            segmentsToday = current.segmentsToday,
            segmentsDay = current.segmentsDay,
        )
        settings.write(next)
        purge(next, now())
        refresh(next)
    }

    /** Changes the current settings, read fresh so no other change is lost. */
    fun updateSettings(change: (SettingsSnapshot) -> SettingsSnapshot) = saveSettings(change(settings.read()))

    /** Every choice back to its default; the server number stays. */
    fun resetSettings() {
        updateSettings { it.reset() }
        _state.update {
            it.copy(
                notice = Notice("Settings are back to their defaults."),
                settingsGeneration = it.settingsGeneration + 1,
            )
        }
    }

    /** Deletes a page; the notice offers to put it back. */
    fun deletePage(tag: Int) {
        val page = storage.page(tag) ?: return
        storage.forget(tag)
        _state.update {
            val wasReading = it.reading?.tag == tag
            it.copy(
                reading = if (wasReading) null else it.reading,
                screen = if (wasReading && it.screen == Screen.READER) Screen.HOME else it.screen,
                notice = Notice("Page deleted.", NoticeAction.Restore(page)),
            )
        }
        refresh(settings.read())
    }

    /** Deletes every page; replies still arriving are kept. */
    fun clearHistory() {
        storage.clearPages()
        _state.update { it.copy(reading = null, notice = Notice("History cleared.")) }
        refresh(settings.read())
    }

    fun clearLog() {
        storage.clearLog()
        refresh(settings.read())
    }

    // Requests ---------------------------------------------------------------------------------

    fun get(url: String) = send(Request(Verb.GET, size = pageSize(), url = url.trim()))

    fun search(words: String) = send(Request(Verb.SEARCH, size = pageSize(), words = words.trim()))

    fun status() = send(Request(Verb.STATUS))

    fun help() = send(Request(Verb.HELP))

    fun followLink(number: Int) {
        val reading = _state.value.reading ?: return
        send(Request(Verb.LINK, size = pageSize(), ref = reading.tag, number = number))
    }

    fun turnPage(delta: Int) {
        val reading = _state.value.reading ?: return
        val target = reading.page + delta
        if (target !in 1..reading.pages) return
        send(Request(Verb.PAGE, ref = reading.tag, number = target))
    }

    /** Asks again for a reply that stopped: the same request, word for word, under a fresh tag. */
    fun retry(tag: Int) {
        val request = storage.request(tag) ?: return
        storage.forget(tag)
        conversations.remove(tag)
        val words = request.text.substringAfter(' ')
        send { fresh -> "${encodeTag(fresh)} $words" }
    }

    /** Stops waiting for a reply that gave up, without asking again. */
    fun dismiss(tag: Int) {
        storage.forget(tag)
        conversations.remove(tag)
        scheduleNextTick()
        refresh(settings.read())
    }

    /** Always sent, so the app's setting holds whatever the server's default is. */
    private fun pageSize(): Int = settings.read().pageFrames

    private fun send(request: Request) = send { tag -> formatRequest(request.copy(tag = tag)) }

    /** Sends the text [textFor] makes of a freshly allocated tag, and starts waiting for its reply. */
    private fun send(textFor: (Int) -> String) {
        val snapshot = settings.read()
        val at = now()
        if (snapshot.serverNumber.isBlank()) {
            _state.update {
                it.copy(notice = Notice("Set the server number in Settings first."), screen = Screen.SETTINGS)
            }
            return
        }
        if (snapshot.dailyLimit > 0 && segmentsOn(snapshot, at) >= snapshot.dailyLimit) {
            _state.update {
                it.copy(
                    notice = Notice("Today's limit of ${snapshot.dailyLimit} texts is reached. Change it in Settings."),
                )
            }
            return
        }
        val tag = allocator.allocate(conversations.keys)
        settings.write(snapshot.copy(nextTag = allocator.next))
        val text = textFor(tag)
        storage.saveRequest(SentRequest(tag, text, at))
        conversations[tag] = conversation(tag, at, snapshot)
        gateway.send(snapshot.serverNumber, text)
        storage.log(LogEntry(at, LogEntry.Direction.OUT, text, "request"))
        scheduleNextTick()
        refresh(settings.read())
    }

    // Frames in --------------------------------------------------------------------------------

    /** An SMS arrived; frames from the server are stored and assembled, anything else is noted. */
    fun onSms(sender: String, body: String) {
        val snapshot = settings.read()
        val at = now()
        if (!sameNumber(sender, snapshot.serverNumber)) return
        val frame = try {
            decodeFrame(body)
        } catch (error: FrameException) {
            storage.log(LogEntry(at, LogEntry.Direction.IN, body, "not a frame: ${error.fault}"))
            refresh(snapshot)
            return
        }
        storage.saveFrame(frame, at)
        storage.log(
            LogEntry(at, LogEntry.Direction.IN, body, "frame ${encodeTag(frame.tag)} ${frame.seq + 1}/${frame.total}"),
        )
        countSegment(snapshot, at)
        val conversation = conversations.getOrPut(frame.tag) { conversation(frame.tag, at, snapshot) }
        when (val decision = conversation.onFrame(frame, at)) {
            is Decision.Complete -> complete(frame.tag, decision.payload, frame.total, at)
            else -> Unit
        }
        scheduleNextTick()
        refresh(settings.read())
    }

    private fun complete(tag: Int, payload: ByteArray, frames: Int, at: Long) {
        val envelope: Envelope = try {
            unpackEnvelope(payload, dictionary)
        } catch (error: EnvelopeException) {
            storage.log(LogEntry(at, LogEntry.Direction.NOTE, encodeTag(tag), "reply unreadable: ${error.fault}"))
            storage.forget(tag)
            conversations.remove(tag)
            return
        }
        val page = StoredPage(tag, envelope.kind, envelope.page, envelope.pages, envelope.text, frames, at)
        storage.savePage(page)
        conversations.remove(tag)
        val snapshot = settings.read()
        purge(snapshot, at)
        if (snapshot.openOnArrival) {
            _state.update { it.copy(screen = Screen.READER, reading = page, notice = null) }
        } else if (visible) {
            _state.update { it.copy(notice = Notice("“${page.title}” arrived.", NoticeAction.Read(tag))) }
        }
        if (!visible && snapshot.notifyOnArrival) notifier.pageArrived(page)
    }

    /** Time passed: every open conversation decides whether to ask again or give up. */
    fun tick() {
        val at = now()
        val snapshot = settings.read()
        for (conversation in conversations.values.toList()) {
            when (val decision = conversation.onTick(at)) {
                is Decision.Resend -> {
                    val request = Request(Verb.RESEND, ref = conversation.tag, seqs = decision.missing)
                    val tag = allocator.allocate(conversations.keys)
                    settings.write(settings.read().copy(nextTag = allocator.next))
                    val text = formatRequest(request.copy(tag = tag))
                    gateway.send(snapshot.serverNumber, text)
                    storage.log(LogEntry(at, LogEntry.Direction.OUT, text, "resend"))
                    storage.request(conversation.tag)?.let {
                        storage.saveRequest(it.copy(resends = conversation.resends))
                    }
                }
                is Decision.GiveUp -> storage.log(
                    LogEntry(at, LogEntry.Direction.NOTE, encodeTag(conversation.tag), "gave up"),
                )
                else -> Unit
            }
        }
        scheduleNextTick()
        refresh(settings.read())
    }

    private fun conversation(tag: Int, at: Long, snapshot: SettingsSnapshot) =
        Conversation(tag, at, snapshot.nakAfterMillis, snapshot.resendRounds)

    private fun scheduleNextTick() {
        val next = conversations.values.mapNotNull { it.nextTickAtMillis() }.minOrNull()
        if (next == null) scheduler.cancel() else scheduler.wakeAt(next, now())
    }

    /** Pages older than the history setting are deleted; the reader lets go of one that was. */
    private fun purge(snapshot: SettingsSnapshot, at: Long) {
        if (snapshot.historyDays == 0) return
        if (storage.deletePagesBefore(at - snapshot.historyDays * DAY_MILLIS) == 0) return
        val reading = _state.value.reading
        if (reading != null && storage.page(reading.tag) == null) _state.update { it.copy(reading = null) }
    }

    private fun countSegment(snapshot: SettingsSnapshot, at: Long) {
        settings.write(snapshot.copy(segmentsToday = segmentsOn(snapshot, at) + 1, segmentsDay = utcDay(at)))
    }

    private fun refresh(snapshot: SettingsSnapshot) {
        val pending = conversations.values.map { conversation ->
            Pending(
                tag = conversation.tag,
                request = storage.request(conversation.tag)?.text ?: UNASKED,
                received = conversation.received,
                total = conversation.total,
                resends = conversation.resends,
                gaveUp = conversation.phase == Phase.INCOMPLETE,
            )
        }
        _state.update {
            it.copy(
                settings = snapshot,
                pages = storage.pages(),
                pending = pending.sortedBy { p -> p.tag },
                meter = CostMeter(segmentsOn(snapshot, now()), snapshot.pricePerSegment, snapshot.currency),
                log = storage.recentLog(LOG_LINES),
            )
        }
    }

    companion object {
        const val LOG_LINES = 50
        const val DAY_MILLIS = 86_400_000L

        /** What a reply in flight is called when this app holds no request for it. */
        const val UNASKED = "a reply to a request this app did not send"

        /** The UTC date of [millis], as the day the count of texts belongs to. */
        fun utcDay(
            millis: Long,
        ): String = Instant.ofEpochMilli(millis).atOffset(ZoneOffset.UTC).toLocalDate().toString()

        /** Texts received on the UTC day of [at]: the stored count only if it is that day's. */
        fun segmentsOn(snapshot: SettingsSnapshot, at: Long): Int =
            if (snapshot.segmentsDay == utcDay(at)) snapshot.segmentsToday else 0
    }
}
