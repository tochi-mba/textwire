package com.rextechnologies.textwire.data

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.Kind

/** The app's SQLite database: [Storage] on disk. */
class Database(context: Context, name: String? = "textwire.db") :
    SQLiteOpenHelper(context, name, null, VERSION),
    Storage {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE requests (tag INTEGER PRIMARY KEY, text TEXT NOT NULL, sent_at INTEGER NOT NULL," +
                " resends INTEGER NOT NULL DEFAULT 0)",
        )
        db.execSQL(
            "CREATE TABLE frames (tag INTEGER NOT NULL, seq INTEGER NOT NULL, total INTEGER NOT NULL," +
                " body BLOB NOT NULL, received_at INTEGER NOT NULL, PRIMARY KEY (tag, seq))",
        )
        db.execSQL(
            "CREATE TABLE pages (tag INTEGER PRIMARY KEY, kind INTEGER NOT NULL, page INTEGER NOT NULL," +
                " pages INTEGER NOT NULL, text TEXT NOT NULL, sms_count INTEGER NOT NULL, received_at INTEGER NOT NULL)",
        )
        db.execSQL(
            "CREATE TABLE log (id INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER NOT NULL, direction TEXT NOT NULL," +
                " text TEXT NOT NULL, note TEXT NOT NULL)",
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Version 1 is the first schema; nothing to migrate yet.
    }

    override fun saveRequest(request: SentRequest) {
        val values = ContentValues().apply {
            put("tag", request.tag)
            put("text", request.text)
            put("sent_at", request.sentAtMillis)
            put("resends", request.resends)
        }
        writableDatabase.insertWithOnConflict("requests", null, values, SQLiteDatabase.CONFLICT_REPLACE)
    }

    override fun request(tag: Int): SentRequest? =
        readableDatabase.query("requests", null, "tag = ?", arrayOf("$tag"), null, null, null).use { cursor ->
            if (cursor.moveToFirst()) cursor.request() else null
        }

    override fun openRequests(): List<SentRequest> =
        readableDatabase.rawQuery(
            "SELECT r.* FROM requests r LEFT JOIN pages p ON p.tag = r.tag WHERE p.tag IS NULL ORDER BY r.sent_at",
            null,
        ).use { cursor -> generateSequence { if (cursor.moveToNext()) cursor.request() else null }.toList() }

    private fun Cursor.request() = SentRequest(
        tag = getInt(getColumnIndexOrThrow("tag")),
        text = getString(getColumnIndexOrThrow("text")),
        sentAtMillis = getLong(getColumnIndexOrThrow("sent_at")),
        resends = getInt(getColumnIndexOrThrow("resends")),
    )

    override fun saveFrame(frame: Frame, atMillis: Long) {
        val values = ContentValues().apply {
            put("tag", frame.tag)
            put("seq", frame.seq)
            put("total", frame.total)
            put("body", frame.body.toByteArray())
            put("received_at", atMillis)
        }
        writableDatabase.insertWithOnConflict("frames", null, values, SQLiteDatabase.CONFLICT_IGNORE)
    }

    override fun frames(tag: Int): List<Frame> =
        readableDatabase.query("frames", null, "tag = ?", arrayOf("$tag"), null, null, "seq").use { cursor ->
            generateSequence {
                if (!cursor.moveToNext()) {
                    null
                } else {
                    Frame(
                        tag = cursor.getInt(cursor.getColumnIndexOrThrow("tag")),
                        seq = cursor.getInt(cursor.getColumnIndexOrThrow("seq")),
                        total = cursor.getInt(cursor.getColumnIndexOrThrow("total")),
                        body = cursor.getBlob(cursor.getColumnIndexOrThrow("body")).toList(),
                    )
                }
            }.toList()
        }

    override fun savePage(page: StoredPage) {
        val values = ContentValues().apply {
            put("tag", page.tag)
            put("kind", page.kind.code)
            put("page", page.page)
            put("pages", page.pages)
            put("text", page.text)
            put("sms_count", page.smsCount)
            put("received_at", page.receivedAtMillis)
        }
        writableDatabase.insertWithOnConflict("pages", null, values, SQLiteDatabase.CONFLICT_REPLACE)
        writableDatabase.delete("frames", "tag = ?", arrayOf("${page.tag}"))
    }

    override fun page(tag: Int): StoredPage? =
        readableDatabase.query("pages", null, "tag = ?", arrayOf("$tag"), null, null, null).use { cursor ->
            if (cursor.moveToFirst()) cursor.page() else null
        }

    override fun pages(): List<StoredPage> =
        readableDatabase.query("pages", null, null, null, null, null, "received_at DESC").use { cursor ->
            generateSequence { if (cursor.moveToNext()) cursor.page() else null }.toList()
        }

    private fun Cursor.page() = StoredPage(
        tag = getInt(getColumnIndexOrThrow("tag")),
        kind = Kind.of(getInt(getColumnIndexOrThrow("kind"))) ?: Kind.PAGE,
        page = getInt(getColumnIndexOrThrow("page")),
        pages = getInt(getColumnIndexOrThrow("pages")),
        text = getString(getColumnIndexOrThrow("text")),
        smsCount = getInt(getColumnIndexOrThrow("sms_count")),
        receivedAtMillis = getLong(getColumnIndexOrThrow("received_at")),
    )

    override fun forget(tag: Int) {
        for (table in listOf("requests", "frames", "pages")) writableDatabase.delete(table, "tag = ?", arrayOf("$tag"))
    }

    override fun log(entry: LogEntry) {
        val values = ContentValues().apply {
            put("at", entry.atMillis)
            put("direction", entry.direction.name)
            put("text", entry.text)
            put("note", entry.note)
        }
        writableDatabase.insert("log", null, values)
        writableDatabase.execSQL(
            "DELETE FROM log WHERE id NOT IN (SELECT id FROM log ORDER BY id DESC LIMIT $LOG_KEEP)",
        )
    }

    override fun recentLog(limit: Int): List<LogEntry> =
        readableDatabase.query("log", null, null, null, null, null, "id DESC", "$limit").use { cursor ->
            generateSequence {
                if (!cursor.moveToNext()) {
                    null
                } else {
                    LogEntry(
                        atMillis = cursor.getLong(cursor.getColumnIndexOrThrow("at")),
                        direction = LogEntry.Direction.valueOf(
                            cursor.getString(cursor.getColumnIndexOrThrow("direction")),
                        ),
                        text = cursor.getString(cursor.getColumnIndexOrThrow("text")),
                        note = cursor.getString(cursor.getColumnIndexOrThrow("note")),
                    )
                }
            }.toList()
        }

    override fun smsReceived(): Int =
        readableDatabase.rawQuery("SELECT coalesce(sum(sms_count), 0) FROM pages", null).use { cursor ->
            cursor.moveToFirst()
            cursor.getInt(0)
        }

    companion object {
        const val VERSION = 1
        const val LOG_KEEP = 200
    }
}
