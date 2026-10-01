package com.rextechnologies.textwire

import com.rextechnologies.textwire.data.LogEntry
import com.rextechnologies.textwire.data.SentRequest
import com.rextechnologies.textwire.data.SettingsSnapshot
import com.rextechnologies.textwire.data.SettingsStore
import com.rextechnologies.textwire.data.Storage
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.sms.SmsGateway
import com.rextechnologies.textwire.work.NakScheduler

/** The server's number and the phone's, from Ofcom's drama range. */
const val SERVER = "+447700900000"

class FakeStorage : Storage {
    val requests = HashMap<Int, SentRequest>()
    val frames = HashMap<Int, MutableList<Frame>>()
    val pagesByTag = HashMap<Int, StoredPage>()
    val entries = mutableListOf<LogEntry>()

    override fun saveRequest(request: SentRequest) {
        requests[request.tag] = request
    }

    override fun request(tag: Int): SentRequest? = requests[tag]

    override fun openRequests(): List<SentRequest> =
        requests.values.filter { it.tag !in pagesByTag }.sortedBy { it.sentAtMillis }

    override fun saveFrame(frame: Frame, atMillis: Long) {
        val list = frames.getOrPut(frame.tag) { mutableListOf() }
        if (list.none { it.seq == frame.seq }) list.add(frame)
    }

    override fun frames(tag: Int): List<Frame> = frames[tag]?.sortedBy { it.seq } ?: emptyList()

    override fun savePage(page: StoredPage) {
        pagesByTag[page.tag] = page
        frames.remove(page.tag)
    }

    override fun page(tag: Int): StoredPage? = pagesByTag[tag]

    override fun pages(): List<StoredPage> = pagesByTag.values.sortedByDescending { it.receivedAtMillis }

    override fun forget(tag: Int) {
        requests.remove(tag)
        frames.remove(tag)
        pagesByTag.remove(tag)
    }

    override fun log(entry: LogEntry) {
        entries.add(entry)
    }

    override fun recentLog(limit: Int): List<LogEntry> = entries.asReversed().take(limit)

    override fun smsReceived(): Int = pagesByTag.values.sumOf { it.smsCount }
}

class FakeSettings(var snapshot: SettingsSnapshot = SettingsSnapshot(serverNumber = SERVER)) : SettingsStore {
    override fun read(): SettingsSnapshot = snapshot

    override fun write(snapshot: SettingsSnapshot) {
        this.snapshot = snapshot
    }
}

class FakeGateway : SmsGateway {
    val sent = mutableListOf<Pair<String, String>>()

    override fun send(destination: String, text: String) {
        sent.add(destination to text)
    }

    fun texts(): List<String> = sent.map { it.second }
}

class FakeScheduler : NakScheduler {
    var wakeAt: Long? = null
    var cancelled = 0

    override fun wakeAt(atMillis: Long, nowMillis: Long) {
        wakeAt = atMillis
    }

    override fun cancel() {
        wakeAt = null
        cancelled++
    }
}

/** A clock that moves only when told. */
class FakeClock(var now: Long = 1_000_000L) {
    fun advance(millis: Long) {
        now += millis
    }
}
