package com.rextechnologies.textwire.core

/** What today's replies have cost so far, estimated from a price per SMS (ADR-0012). */
data class CostMeter(val segments: Int = 0, val pricePerSegment: Double = DEFAULT_PRICE, val currency: String = "USD") {
    /** The meter after [count] more SMS arrived. */
    fun plus(count: Int): CostMeter {
        require(count >= 0) { "a count cannot be negative" }
        return copy(segments = segments + count)
    }

    /** The estimated spend. */
    val estimate: Double get() = segments * pricePerSegment

    /** `12 SMS, ~0.67 USD`. */
    fun describe(): String = "$segments SMS, ~${"%.2f".format(estimate)} $currency"

    companion object {
        /** Twilio's UK outbound rate in 2026-09; the app's settings can change it. */
        const val DEFAULT_PRICE = 0.056
    }
}
