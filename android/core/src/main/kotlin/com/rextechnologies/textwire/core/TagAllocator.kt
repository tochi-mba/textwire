package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.SERVER_TAG_FIRST

/**
 * Hands out request tags in turn, `00` to `yz`, never one that is still in use.
 *
 * The phone's range is `0` until [SERVER_TAG_FIRST]; the server keeps `z0` to `zz` for
 * requests that arrive without a tag (PROTOCOL.md section 3). [next] is persisted by the
 * caller so tags keep cycling across restarts.
 */
class TagAllocator(start: Int = 0) {
    var next: Int = start.mod(SERVER_TAG_FIRST)
        private set

    /** The next free tag; [inUse] holds the tags of conversations still waiting. */
    fun allocate(inUse: Set<Int> = emptySet()): Int {
        require(inUse.size < SERVER_TAG_FIRST) { "every tag is in use" }
        var candidate = next
        while (candidate in inUse) candidate = (candidate + 1) % SERVER_TAG_FIRST
        next = (candidate + 1) % SERVER_TAG_FIRST
        return candidate
    }
}
