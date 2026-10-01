package com.rextechnologies.textwire.core

import com.rextechnologies.textwire.protocol.Frame
import com.rextechnologies.textwire.protocol.joinFrames

/** What the app should do after an event reached a [Conversation]. */
sealed interface Decision {
    /** Nothing yet; keep waiting. */
    data object Wait : Decision

    /** Every frame is in: [payload] is the reassembled envelope bytes. */
    data class Complete(val payload: ByteArray) : Decision {
        override fun equals(other: Any?): Boolean = other is Complete && payload.contentEquals(other.payload)

        override fun hashCode(): Int = payload.contentHashCode()
    }

    /** Ask the server for these frame numbers again (PROTOCOL.md section 8). */
    data class Resend(val missing: List<Int>) : Decision

    /** The resend rounds are spent; show what arrived and offer a retry. */
    data class GiveUp(val received: Int, val total: Int?, val missing: List<Int>) : Decision
}

/** The states a conversation moves through. */
enum class Phase { SENT, RECEIVING, COMPLETE, INCOMPLETE }

/**
 * One request and the reply it waits for: the state machine of PROTOCOL.md section 8.
 *
 * Pure and clock-free: the caller passes the time of every event in milliseconds and is told
 * what to do. After [nakRounds] resend requests without completion it gives up, but a late
 * frame can still complete it, in which case [onFrame] answers [Decision.Complete].
 */
class Conversation(
    val tag: Int,
    private val sentAtMillis: Long,
    private val nakAfterMillis: Long = DEFAULT_NAK_AFTER_MILLIS,
    private val nakRounds: Int = DEFAULT_NAK_ROUNDS,
) {
    private val frames = HashMap<Int, Frame>()

    /** How many frames the reply has; unknown until the first one arrives. */
    var total: Int? = null
        private set

    private var lastFrameAtMillis = sentAtMillis
    private var resendsSent = 0
    private var quietSinceMillis = sentAtMillis

    var phase: Phase = Phase.SENT
        private set

    /** Frames received so far. */
    val received: Int get() = frames.size

    /** The frames still missing, in order; empty until the first frame says how many there are. */
    val missing: List<Int> get() = total?.let { count -> (0 until count).filter { it !in frames } } ?: emptyList()

    /** How many resend requests have been sent. */
    val resends: Int get() = resendsSent

    /** A frame of this conversation arrived at [nowMillis]. */
    fun onFrame(frame: Frame, nowMillis: Long): Decision {
        require(frame.tag == tag) { "frame for tag ${frame.tag} given to conversation $tag" }
        if (phase == Phase.COMPLETE) return Decision.Wait
        lastFrameAtMillis = nowMillis
        quietSinceMillis = nowMillis
        total = frame.total
        frames.putIfAbsent(frame.seq, frame)
        if (phase == Phase.SENT) phase = Phase.RECEIVING
        if (frames.size == frame.total) {
            phase = Phase.COMPLETE
            return Decision.Complete(joinFrames(frames.values))
        }
        return Decision.Wait
    }

    /** Time passed; [nowMillis] is now. Call it whenever a timer fires or the app wakes. */
    fun onTick(nowMillis: Long): Decision {
        if (phase == Phase.COMPLETE || phase == Phase.INCOMPLETE) return Decision.Wait
        if (nowMillis - quietSinceMillis < nakAfterMillis) return Decision.Wait
        if (resendsSent >= nakRounds) return giveUp()
        resendsSent++
        quietSinceMillis = nowMillis
        // Before any frame arrives there are no numbers to ask for; frame 0 stands in for them.
        return Decision.Resend(if (total == null) listOf(0) else missing.take(MAX_RESEND_LIST))
    }

    /** The next moment [onTick] could decide something, for scheduling a timer; null when settled. */
    fun nextTickAtMillis(): Long? =
        if (phase == Phase.COMPLETE || phase == Phase.INCOMPLETE) null else quietSinceMillis + nakAfterMillis

    private fun giveUp(): Decision {
        phase = Phase.INCOMPLETE
        return Decision.GiveUp(frames.size, total, missing)
    }

    companion object {
        const val DEFAULT_NAK_AFTER_MILLIS = 60_000L
        const val DEFAULT_NAK_ROUNDS = 3

        /** Frame numbers one resend request lists at most, so it stays one SMS. */
        const val MAX_RESEND_LIST = 40
    }
}
