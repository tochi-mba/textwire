package com.rextechnologies.textwire.ui

import com.rextechnologies.textwire.Pending
import com.rextechnologies.textwire.core.CostMeter
import com.rextechnologies.textwire.data.StoredPage
import com.rextechnologies.textwire.protocol.Kind
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The wording of everything the screens say, without drawing them. */
class FormatsTest {
    private val page = StoredPage(1, Kind.SEARCH, 1, 1, "# S", 4, 0)

    @Test
    fun `an address is told from search words`() {
        assertTrue(looksLikeUrl("bbc.co.uk/news"))
        assertTrue(looksLikeUrl(" https://x "))
        assertTrue(looksLikeUrl("http://localhost"))
        assertFalse(looksLikeUrl("weather london"))
        assertFalse(looksLikeUrl("hello"))
        assertFalse(looksLikeUrl("a.b c"))
    }

    @Test
    fun `a reply in flight says how far it got`() {
        assertEquals("waiting for the first text", progressLabel(Pending(1, "r", 0, null, 0, false)))
        assertEquals("3 of 12 texts, asked again 1x", progressLabel(Pending(1, "r", 3, 12, 1, false)))
        assertEquals("Stopped at 3 of 12 texts. Retry to ask again.", progressLabel(Pending(1, "r", 3, 12, 3, true)))
    }

    @Test
    fun `page turns and links are told from other requests by their verb`() {
        assertTrue(turnsThePage("04 p 00 2"))
        assertTrue(turnsThePage("05 l12 00 3"))
        assertFalse(turnsThePage("06 s12 london"))
        assertFalse(turnsThePage("07 g12 lemonde.fr"))
        assertFalse(turnsThePage("08"))
        assertFalse(turnsThePage(""))
    }

    @Test
    fun `a page is described by its kind, size and arrival`() {
        assertTrue(pageMeta(page).startsWith("Search results · 4 texts · "))
        assertTrue(pageMeta(page.copy(smsCount = 1)).startsWith("Search results · 1 text · "))
        assertTrue(pageMeta(page.copy(kind = Kind.HELP)).startsWith("Help"))
        assertTrue(pageMeta(page.copy(kind = Kind.STATUS)).startsWith("Status"))
        assertTrue(pageMeta(page.copy(kind = Kind.PAGE, page = 2, pages = 5)).startsWith("Page 2 of 5"))
        assertTrue(Regex("""\d\d:\d\d:\d\d""").matches(clock(0)))
        assertTrue(Regex("""\d\d:\d\d""").matches(clockMinutes(0)))
    }

    @Test
    fun `a page's title is its first line, and never empty`() {
        assertEquals("S", page.title)
        assertEquals("Plain", page.copy(text = "Plain\nbody").title)
        assertEquals("Untitled", page.copy(text = "#  \nbody").title)
        assertEquals("Untitled", page.copy(text = "").title)
    }

    @Test
    fun `a page size is estimated in words and money`() {
        assertEquals("12 texts · about 800 words · ~0.67 USD", pageEstimate(12, 0.056, "USD"))
        assertEquals("1 text · about 50 words · ~0.06 GBP", pageEstimate(1, 0.056, "GBP"))
        assertEquals("40 texts · about 2600 words · ~0.00 EUR", pageEstimate(40, 0.0, "EUR"))
    }

    @Test
    fun `every choice is labelled the way a person says it`() {
        assertEquals(
            listOf("30 s", "1 min", "2 min", "5 min"),
            listOf(30_000L, 60_000L, 120_000L, 300_000L).map(::duration),
        )
        assertEquals(listOf("Never", "1x", "5x"), listOf(0, 1, 5).map(::rounds))
        assertEquals(listOf("Off", "50"), listOf(0, 50).map(::limit))
        assertEquals(listOf("1 day", "7 days", "Always"), listOf(1, 7, 0).map(::keep))
        assertEquals(listOf("Small", "Default", "Large", "Largest"), listOf(0.85f, 1f, 1.15f, 1.3f).map(::textSize))
        assertEquals(listOf("no replies", "1 reply", "2 replies"), listOf(0, 1, 2).map(::replies))
        assertEquals(listOf("0 texts", "1 text", "2 texts"), listOf(0, 1, 2).map(::texts))
    }

    @Test
    fun `the day's line says what arrived and the limit when one is set`() {
        assertEquals("Received today: nothing yet", todayLine(CostMeter(0, 0.056, "USD"), 0))
        assertEquals("Received today: nothing yet · limit 50 a day", todayLine(CostMeter(0, 0.056, "USD"), 50))
        assertEquals("Received today: 1 text · ~0.06 USD", todayLine(CostMeter(1, 0.056, "USD"), 0))
        assertEquals(
            "Received today: 12 texts · ~0.67 USD · limit 200 a day",
            todayLine(CostMeter(12, 0.056, "USD"), 200),
        )
    }

    @Test
    fun `a reply in flight is titled by what was asked, not by wire text`() {
        assertEquals("Opening bbc.co.uk/news", requestLabel("02 g12 bbc.co.uk/news"))
        assertEquals("Opening https://a b", requestLabel("02 g https://a b"))
        assertEquals("Searching: weather london", requestLabel("00 s12 weather london"))
        assertEquals("Getting page 3", requestLabel("04 p 00 3"))
        assertEquals("Following link 7", requestLabel("05 l12 00 7"))
        assertEquals("Following link ?", requestLabel("05 l12"))
        assertEquals("Asking for lost texts", requestLabel("03 r 02 1-4"))
        assertEquals("Checking the server", requestLabel("06 ?"))
        assertEquals("Asking for help", requestLabel("07 h"))
        assertEquals(
            "a reply to a request this app did not send",
            requestLabel("a reply to a request this app did not send"),
        )
        assertEquals("a! r 02 1-4", requestLabel("a! r 02 1-4"))
        assertEquals("a7 reply", requestLabel("a7 reply"))
        assertEquals("", requestLabel(""))
    }

    @Test
    fun `a shared page loses its link numbers`() {
        val shared = page.copy(text = "# Title\n\nSee the council[3] and [12] more.\n")
        assertEquals("# Title\n\nSee the council and  more.", shareableText(shared))
    }

    @Test
    fun `typed settings say exactly what is wrong`() {
        assertNull(numberProblem(" +447700900000 "))
        assertEquals("A number like +447700900000, with the country code", numberProblem("07700900000"))
        assertNull(priceProblem("0"))
        assertNull(priceProblem(" 0.056 "))
        assertEquals("A price per text, such as 0.056", priceProblem("-1"))
        assertEquals("A price per text, such as 0.056", priceProblem("cheap"))
        assertEquals("A price per text, such as 0.056", priceProblem("Infinity"))
        assertEquals("A price per text, such as 0.056", priceProblem("NaN"))
        assertNull(currencyProblem("GBP"))
        assertEquals("Three letters, such as GBP", currencyProblem("gbp"))
        assertEquals("Three letters, such as GBP", currencyProblem("POUND"))
    }
}
