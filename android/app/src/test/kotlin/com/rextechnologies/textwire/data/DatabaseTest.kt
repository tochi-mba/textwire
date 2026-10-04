package com.rextechnologies.textwire.data

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind
import org.junit.After
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertEquals
import kotlin.test.assertNull

@RunWith(AndroidJUnit4::class)
class DatabaseTest {
    private val db = Database(ApplicationProvider.getApplicationContext(), name = null)

    @After
    fun close() = db.close()

    @Test
    fun `requests are stored by tag and open until their page arrives`() {
        db.saveRequest(SentRequest(7, "07 g https://x", 1_000))
        db.saveRequest(SentRequest(8, "08 ?", 2_000))
        assertEquals(SentRequest(7, "07 g https://x", 1_000), db.request(7))
        assertNull(db.request(9))
        assertEquals(listOf(7, 8), db.openRequests().map { it.tag })
        db.savePage(StoredPage(7, Kind.PAGE, 1, 1, "# x", 2, 3_000))
        assertEquals(listOf(8), db.openRequests().map { it.tag })
        db.saveRequest(SentRequest(8, "08 ?", 2_000, resends = 2))
        assertEquals(2, db.request(8)?.resends)
    }

    @Test
    fun `frames are kept in order until the page is saved and a duplicate is ignored`() {
        val a = Frame(7, 1, 2, listOf(1, 2))
        val b = Frame(7, 0, 2, listOf(3))
        db.saveFrame(a, 1_000)
        db.saveFrame(b, 1_001)
        db.saveFrame(Frame(7, 1, 2, listOf(9)), 1_002)
        assertEquals(listOf(b, a), db.frames(7))
        assertEquals(emptyList(), db.frames(8))
        db.savePage(StoredPage(7, Kind.PAGE, 1, 1, "# x", 2, 3_000))
        assertEquals(emptyList(), db.frames(7))
    }

    @Test
    fun `pages are listed newest first and forgotten one at a time`() {
        db.savePage(StoredPage(1, Kind.SEARCH, 1, 1, "# a", 3, 1_000))
        db.savePage(StoredPage(2, Kind.PAGE, 2, 5, "# b", 12, 2_000))
        db.savePage(StoredPage(2, Kind.PAGE, 2, 5, "# b2", 11, 2_500))
        assertEquals(listOf(2, 1), db.pages().map { it.tag })
        assertEquals("# b2", db.page(2)?.text)
        assertEquals(Kind.SEARCH, db.page(1)?.kind)
        db.forget(2)
        assertNull(db.page(2))
        assertEquals(listOf(1), db.pages().map { it.tag })
    }

    @Test
    fun `clearing history deletes pages and what made them but keeps replies on their way`() {
        db.saveRequest(SentRequest(1, "01 s12 a", 100))
        db.savePage(StoredPage(1, Kind.SEARCH, 1, 1, "# a", 3, 1_000))
        db.saveRequest(SentRequest(2, "02 g12 b", 200))
        db.saveFrame(Frame(2, 0, 2, listOf(1)), 300)
        db.clearPages()
        assertEquals(emptyList(), db.pages())
        assertNull(db.request(1))
        assertEquals(listOf(2), db.openRequests().map { it.tag })
        assertEquals(1, db.frames(2).size)
    }

    @Test
    fun `pages older than a moment are deleted with their requests`() {
        db.saveRequest(SentRequest(1, "01 s12 a", 100))
        db.savePage(StoredPage(1, Kind.SEARCH, 1, 1, "# a", 3, 1_000))
        db.saveRequest(SentRequest(2, "02 s12 b", 100))
        db.savePage(StoredPage(2, Kind.SEARCH, 1, 1, "# b", 3, 5_000))
        assertEquals(1, db.deletePagesBefore(5_000))
        assertEquals(listOf(2), db.pages().map { it.tag })
        assertNull(db.request(1))
        assertEquals(0, db.deletePagesBefore(5_000))
    }

    @Test
    fun `the log can be cleared`() {
        db.log(LogEntry(1, LogEntry.Direction.IN, "t", "n"))
        db.clearLog()
        assertEquals(emptyList(), db.recentLog(10))
    }

    @Test
    fun `an unknown kind code reads back as a page`() {
        db.savePage(StoredPage(3, Kind.HELP, 1, 1, "# h", 1, 1_000))
        db.writableDatabase.execSQL("UPDATE pages SET kind = 99 WHERE tag = 3")
        assertEquals(Kind.PAGE, db.page(3)?.kind)
    }

    @Test
    fun `the log keeps the newest two hundred lines`() {
        for (n in 0 until 205) db.log(LogEntry(n.toLong(), LogEntry.Direction.IN, "t$n", "n"))
        db.log(LogEntry(999, LogEntry.Direction.OUT, "last", "note"))
        val recent = db.recentLog(3)
        assertEquals(listOf("last", "t204", "t203"), recent.map { it.text })
        assertEquals(LogEntry.Direction.OUT, recent[0].direction)
        assertEquals("note", recent[0].note)
        assertEquals(Database.LOG_KEEP, db.recentLog(1_000).size)
    }

    @Test
    fun `an upgrade is a no-op at version one`() {
        db.onUpgrade(db.writableDatabase, 1, 1)
        assertEquals(Database.VERSION, db.readableDatabase.version)
    }
}
