package com.rextechnologies.textwire.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * The value types are data classes, and Kotlin generates copy, component and toString members
 * for them. They are part of the module's surface, so they are exercised here rather than
 * excluded from the coverage floor.
 */
class ValueTypesTest {
    @Test
    fun `decisions and phases are values`() {
        val resend = Decision.Resend(listOf(1, 2))
        assertEquals(resend, resend.copy())
        assertEquals(listOf(1, 2), resend.component1())
        assertTrue(resend.toString().contains("1, 2"))
        val giveUp = Decision.GiveUp(1, 3, listOf(0, 2))
        assertEquals(giveUp, giveUp.copy(received = 1))
        assertEquals(Triple(1, 3, listOf(0, 2)), Triple(giveUp.component1(), giveUp.component2(), giveUp.component3()))
        assertTrue(giveUp.toString().startsWith("GiveUp"))
        assertEquals(Decision.Complete(byteArrayOf(5)), Decision.Complete(byteArrayOf(5)).copy())
        assertTrue(Decision.Complete(byteArrayOf(5)).toString().startsWith("Complete"))
        assertEquals("Wait", Decision.Wait.toString())
        assertEquals(Phase.COMPLETE, Phase.valueOf("COMPLETE"))
        assertEquals(4, Phase.entries.size)
    }

    @Test
    fun `spans and blocks are values`() {
        val chip = Span.Chip(3)
        assertEquals(chip, chip.copy())
        assertEquals(3, chip.component1())
        assertNotEquals(chip, Span.Chip(4))
        val text = Span.Text("x")
        assertEquals("x", text.copy().component1())
        assertTrue(text.toString().contains("x"))
        val lines = listOf(listOf<Span>(text))
        for (block in listOf(
            Block.Title("t"),
            Block.Heading("h"),
            Block.Paragraph(lines),
            Block.Bullets(lines),
            Block.Numbered(listOf(1 to lines[0])),
        )) {
            assertEquals(block, block)
            assertTrue(block.toString().isNotEmpty())
            assertEquals(block.hashCode(), block.hashCode())
        }
        assertEquals("t", Block.Title("t").copy().component1())
        assertEquals("h", Block.Heading("h").copy().component1())
        assertEquals(lines, Block.Paragraph(lines).copy().component1())
        assertEquals(lines, Block.Bullets(lines).copy().component1())
        assertEquals(listOf(1 to lines[0]), Block.Numbered(listOf(1 to lines[0])).copy().component1())
    }

    @Test
    fun `every property reads back`() {
        assertEquals(listOf(0, 2), Decision.GiveUp(1, 3, listOf(0, 2)).missing)
        assertEquals(1, Decision.GiveUp(1, 3, listOf(0, 2)).received)
        assertEquals(3, Decision.GiveUp(1, 3, listOf(0, 2)).total)
        assertEquals(listOf<Byte>(5), Decision.Complete(byteArrayOf(5)).payload.toList())
        assertEquals("t", Block.Title("t").text)
        assertEquals("h", Block.Heading("h").text)
        assertEquals("x", Span.Text("x").text)
        assertEquals(3, Span.Chip(3).number)
        val lines = listOf(listOf<Span>(Span.Text("x")))
        assertEquals(lines, Block.Paragraph(lines).lines)
        assertEquals(lines, Block.Bullets(lines).items)
        assertEquals(listOf(1 to lines[0]), Block.Numbered(listOf(1 to lines[0])).items)
        assertEquals(0.5, CostMeter(1, 0.5, "EUR").pricePerSegment)
        assertEquals("EUR", CostMeter(1, 0.5, "EUR").currency)
        val conversation = Conversation(7, 0)
        assertEquals(7, conversation.tag)
        assertEquals(Conversation.DEFAULT_NAK_AFTER_MILLIS, conversation.nextTickAtMillis())
        assertEquals(
            Decision.Resend(listOf(0)),
            Conversation(7, 0, nakRounds = 1).onTick(Conversation.DEFAULT_NAK_AFTER_MILLIS),
        )
    }

    @Test
    fun `the cost meter is a value`() {
        val meter = CostMeter(3, 0.5, "EUR")
        assertEquals(Triple(3, 0.5, "EUR"), Triple(meter.component1(), meter.component2(), meter.component3()))
        assertEquals(meter, meter.copy())
        assertTrue(meter.toString().contains("EUR"))
        assertEquals(meter.hashCode(), meter.copy().hashCode())
    }
}
