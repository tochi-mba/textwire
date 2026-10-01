package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.Frame
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

class ConversationTest {
    private val tag = 367
    private val frames = (0 until 4).map { Frame(tag, it, 4, List(3) { b -> (it * 3 + b).toByte() }) }
    private val whole = frames.flatMap { it.body }.toByteArray()

    private fun conversation(sentAt: Long = 0) = Conversation(tag, sentAt, nakAfterMillis = 60_000, nakRounds = 3)

    @Test
    fun `frames in any order complete the conversation`() {
        val c = conversation()
        assertEquals(Phase.SENT, c.phase)
        assertNull(c.total)
        assertEquals(Decision.Wait, c.onFrame(frames[2], 1_000))
        assertEquals(Phase.RECEIVING, c.phase)
        assertEquals(4, c.total)
        assertEquals(listOf(0, 1, 3), c.missing)
        assertEquals(Decision.Wait, c.onFrame(frames[0], 2_000))
        assertEquals(Decision.Wait, c.onFrame(frames[2], 2_500)) // a duplicate
        assertEquals(Decision.Wait, c.onFrame(frames[3], 3_000))
        assertEquals(Decision.Complete(whole), c.onFrame(frames[1], 4_000))
        assertEquals(Phase.COMPLETE, c.phase)
        assertEquals(4, c.received)
        assertNull(c.nextTickAtMillis())
        assertEquals(Decision.Wait, c.onFrame(frames[1], 5_000))
        assertEquals(Decision.Wait, c.onTick(999_999))
    }

    @Test
    fun `silence after a partial reply asks for the missing frames then gives up`() {
        val c = conversation()
        c.onFrame(frames[1], 1_000)
        assertEquals(Decision.Wait, c.onTick(60_999))
        assertEquals(61_000L, c.nextTickAtMillis())
        assertEquals(Decision.Resend(listOf(0, 2, 3)), c.onTick(61_000))
        assertEquals(1, c.resends)
        assertEquals(Decision.Wait, c.onTick(100_000))
        assertEquals(Decision.Resend(listOf(0, 2, 3)), c.onTick(121_000))
        c.onFrame(frames[0], 130_000) // one came back; the clock restarts from here
        assertEquals(Decision.Wait, c.onTick(189_999))
        assertEquals(Decision.Resend(listOf(2, 3)), c.onTick(190_000))
        assertEquals(Decision.GiveUp(2, 4, listOf(2, 3)), c.onTick(250_000))
        assertEquals(Phase.INCOMPLETE, c.phase)
        assertNull(c.nextTickAtMillis())
        assertEquals(Decision.Wait, c.onTick(999_999))
    }

    @Test
    fun `a late frame still completes an abandoned conversation`() {
        val c = conversation()
        c.onFrame(frames[0], 1_000)
        repeat(3) { c.onTick(1_000 + (it + 1) * 60_000L) }
        assertEquals(Phase.RECEIVING, c.phase)
        c.onTick(1_000 + 4 * 60_000L)
        assertEquals(Phase.INCOMPLETE, c.phase)
        c.onFrame(frames[1], 500_000)
        c.onFrame(frames[2], 500_000)
        assertEquals(Decision.Complete(whole), c.onFrame(frames[3], 500_000))
        assertEquals(Phase.COMPLETE, c.phase)
    }

    @Test
    fun `when nothing arrived at all the first frame is asked for`() {
        val c = conversation(sentAt = 10_000)
        assertEquals(Decision.Wait, c.onTick(69_999))
        assertEquals(Decision.Resend(listOf(0)), c.onTick(70_000))
        assertEquals(Decision.Resend(listOf(0)), c.onTick(130_000))
        assertEquals(Decision.Resend(listOf(0)), c.onTick(190_000))
        assertEquals(Decision.GiveUp(0, null, emptyList()), c.onTick(250_000))
    }

    @Test
    fun `a resend request lists at most forty frames`() {
        val big = Frame(tag, 0, 255, emptyList())
        val c = conversation()
        c.onFrame(big, 0)
        val decision = c.onTick(60_000) as Decision.Resend
        assertEquals((1..40).toList(), decision.missing)
    }

    @Test
    fun `a frame for another tag is refused`() {
        assertFailsWith<IllegalArgumentException> { conversation().onFrame(Frame(1, 0, 1, emptyList()), 0) }
    }

    @Test
    fun `complete decisions compare by payload`() {
        assertEquals(Decision.Complete(byteArrayOf(1, 2)), Decision.Complete(byteArrayOf(1, 2)))
        assertEquals(Decision.Complete(byteArrayOf(1, 2)).hashCode(), Decision.Complete(byteArrayOf(1, 2)).hashCode())
        assert(Decision.Complete(byteArrayOf(1)) != Decision.Complete(byteArrayOf(2)))
        assert(!Decision.Complete(byteArrayOf(1)).equals("x"))
    }
}
