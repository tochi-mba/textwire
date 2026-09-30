package com.rextechnologies.textwire.protocol

import kotlin.test.Test
import kotlin.test.assertEquals

class WireTest {
    @Test
    fun `a full frame is exactly one single-segment SMS`() {
        // 160 base64url characters carry 6 bits each.
        assertEquals(FRAME_CHARS * 6 / 8, FRAME_BYTES)
        assertEquals(114, BODY_BYTES)
        assertEquals(1, FRAME_VERSION)
        assertEquals(255, MAX_FRAMES)
    }
}
