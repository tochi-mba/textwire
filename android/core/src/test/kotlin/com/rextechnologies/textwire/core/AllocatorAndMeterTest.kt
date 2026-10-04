package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.SERVER_TAG_FIRST
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class AllocatorAndMeterTest {
    @Test
    fun `tags are handed out in turn and wrap before the server range`() {
        val allocator = TagAllocator(SERVER_TAG_FIRST - 2)
        assertEquals(SERVER_TAG_FIRST - 2, allocator.allocate())
        assertEquals(SERVER_TAG_FIRST - 1, allocator.allocate())
        assertEquals(0, allocator.allocate())
        assertEquals(1, allocator.next)
    }

    @Test
    fun `tags still in use are skipped`() {
        val allocator = TagAllocator(5)
        assertEquals(7, allocator.allocate(setOf(5, 6)))
        assertEquals(8, allocator.next)
        assertEquals(0, TagAllocator(SERVER_TAG_FIRST - 1).allocate(setOf(SERVER_TAG_FIRST - 1)))
        assertEquals(3, TagAllocator(SERVER_TAG_FIRST + 3).next)
    }

    @Test
    fun `an allocator with every tag in use refuses`() {
        assertFailsWith<IllegalArgumentException> { TagAllocator().allocate((0 until SERVER_TAG_FIRST).toSet()) }
    }

    @Test
    fun `the cost meter adds up and describes itself`() {
        val meter = CostMeter().plus(12).plus(3)
        assertEquals(15, meter.segments)
        assertEquals(0.84, meter.estimate, 1e-9)
        assertEquals("15 texts \u00b7 ~0.84 USD", meter.describe())
        assertEquals("2 texts \u00b7 ~0.10 GBP", CostMeter(2, 0.05, "GBP").describe())
        assertEquals("1 text \u00b7 ~0.06 USD", CostMeter(1, 0.056, "USD").describe())
        assertFailsWith<IllegalArgumentException> { meter.plus(-1) }
    }
}
